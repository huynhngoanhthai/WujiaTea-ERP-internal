import re

from odoo import api, fields, models
from odoo.tools.mail import html_to_inner_content


STATE_SELECTION = [
    ('draft', 'Draft'),
    ('published', 'Published'),
    ('archived', 'Archived'),
]

PORTAL_BADGE_SELECTION = [
    ('normal', 'Normal'),
    ('new', 'New'),
    ('important', 'Important'),
    ('mandatory', 'Mandatory'),
]


class WujiaKnowledgeArticle(models.Model):
    """Knowledge article (SOP / training / marketing) for franchise portal.

    Slug for SEO-friendly URL `/portal/knowledge/<slug>`."""

    _name = 'wujia.knowledge.article'
    _description = 'Wujia Knowledge Article'
    _order = 'sequence, publish_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(
        string='Article Code', readonly=True, copy=False, default='/',
        index=True, help='Auto sequence, e.g. KNW-000001.',
    )
    name = fields.Char(string='Title', required=True, translate=True, tracking=True)
    slug = fields.Char(
        string='Slug', required=True, copy=False, index=True,
        help='SEO-friendly URL segment. Auto-derived from name.',
    )
    category_id = fields.Many2one(
        'wujia.knowledge.category', string='Category',
        required=True, index=True, ondelete='restrict', tracking=True,
    )
    summary = fields.Text(string='Summary', translate=True)
    content = fields.Html(string='Content', translate=True, sanitize=True)
    wujia_content_text = fields.Text(
        string='Content (plain text)', compute='_compute_wujia_content_text',
        store=True, copy=False,
        help='HTML-stripped content, used by portal search.',
    )
    cover_image = fields.Binary(string='Cover image', attachment=True)
    cover_image_filename = fields.Char()

    state = fields.Selection(
        STATE_SELECTION, string='State',
        default='draft', required=True, index=True, tracking=True,
        copy=False,
    )
    portal_badge = fields.Selection(
        PORTAL_BADGE_SELECTION, string='Portal badge',
        default='normal', required=True,
        help='Badge shown on portal article card.',
    )
    publish_date = fields.Datetime(string='Publish date', index=True, tracking=True)
    expired_date = fields.Datetime(
        string='Expired date', index=True,
        help='Article hidden from portal after this datetime.',
    )
    sequence = fields.Integer(string='Sequence', default=10, index=True)

    is_published_portal = fields.Boolean(
        string='Visible on portal',
        compute='_compute_is_published_portal',
        store=True, index=True,
        help='True iff state=published AND (expired_date is null OR > now). '
             'Cron daily re-evaluates expired articles.',
    )

    view_count = fields.Integer(string='Views', default=0, copy=False)
    author_id = fields.Many2one(
        'res.users', string='Author',
        default=lambda self: self.env.user, index=True, tracking=True,
    )
    tag_ids = fields.Many2many(
        'wujia.knowledge.tag', 'wujia_knowledge_article_tag_rel',
        'article_id', 'tag_id', string='Tags',
    )
    attachment_ids = fields.Many2many(
        'ir.attachment', 'wujia_knowledge_article_attachment_rel',
        'article_id', 'attachment_id', string='Attachments',
    )
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('uniq_slug', 'unique(slug)', 'Article slug must be unique.'),
        ('uniq_code', 'unique(code)', 'Article code must be unique.'),
    ]

    # -----------------------------------------------------------------
    # Compute / cron
    # -----------------------------------------------------------------
    @api.depends('state', 'expired_date')
    def _compute_is_published_portal(self):
        # expired_date > now không tự re-trigger theo thời gian
        # → _cron_recompute_is_published chạy daily 03:00 re-write field cho article hết hạn.
        now = fields.Datetime.now()
        for rec in self:
            rec.is_published_portal = (
                rec.state == 'published'
                and (not rec.expired_date or rec.expired_date > now)
            )

    @api.depends('content')
    def _compute_wujia_content_text(self):
        # Search phải khớp cả khi keyword bị thẻ HTML cắt ngang → so trên text đã strip.
        for rec in self:
            rec.wujia_content_text = (
                ' '.join(html_to_inner_content(rec.content).split()) or False
            )

    @api.model
    def _cron_recompute_is_published(self):
        """Daily cron: invalidate is_published_portal cho article hết hạn."""
        now = fields.Datetime.now()
        expired = self.search([
            ('is_published_portal', '=', True),
            ('expired_date', '!=', False),
            ('expired_date', '<=', now),
        ])
        if expired:
            expired._compute_is_published_portal()

    # -----------------------------------------------------------------
    # Create / write hooks
    # -----------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code') or vals['code'] == '/':
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'wujia.knowledge.article'
                ) or '/'
            if vals.get('name') and not vals.get('slug'):
                vals['slug'] = self._make_slug(vals['name'])
            if vals.get('state') == 'published' and not vals.get('publish_date'):
                vals['publish_date'] = fields.Datetime.now()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('state') == 'published':
            for rec in self:
                if rec.state != 'published' and not vals.get('publish_date'):
                    vals.setdefault('publish_date', fields.Datetime.now())
                    break
        return super().write(vals)

    @staticmethod
    def _make_slug(name):
        s = re.sub(r'[^\w\s-]', '', name.lower(), flags=re.UNICODE).strip()
        s = re.sub(r'[\s_-]+', '-', s)
        return s[:80] or 'article'

    # -----------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------
    def action_publish(self):
        self.write({'state': 'published'})

    def action_archive_article(self):
        self.write({'state': 'archived'})

    def action_back_to_draft(self):
        self.write({'state': 'draft'})

    # -----------------------------------------------------------------
    # Portal — luật dùng chung cho mọi kênh (portal, Home, mobile)
    # -----------------------------------------------------------------
    @api.model
    def _portal_visible_domain(self):
        """Bài được phép hiện trên portal: đã publish, đã tới ngày phát hành, chưa hết hạn.

        `active` do active_test loại sẵn; `is_published_portal` đã gộp state + expired_date.
        """
        return [
            ('is_published_portal', '=', True),
            '|', ('publish_date', '=', False),
                 ('publish_date', '<=', fields.Datetime.now()),
        ]

    @api.model
    def _portal_search_domain(self, keyword):
        return [
            '|', '|', ('name', 'ilike', keyword),
                      ('summary', 'ilike', keyword),
                      ('wujia_content_text', 'ilike', keyword),
        ]

    def _portal_get_attachment(self, att_id):
        """Attachment ``att_id`` nếu thuộc bài (m2m hoặc res_model/res_id), không thì rỗng.

        Knowledge là toàn cục, không lọc theo cửa hàng; người gọi kiểm bài đang hiện trước.
        """
        self.ensure_one()
        return self.env['ir.attachment'].sudo().search([
            ('id', '=', att_id),
            '|',
              '&', ('res_model', '=', self._name),
                   ('res_id', '=', self.id),
              ('id', 'in', self.attachment_ids.ids),
        ], limit=1)

    def action_increment_view(self):
        # Atomic SQL update — tránh race condition trên view_count cao tải.
        self.ensure_one()
        self.env.cr.execute(
            "UPDATE wujia_knowledge_article SET view_count = view_count + 1 WHERE id = %s",
            (self.id,),
        )
        self.invalidate_recordset(['view_count'])
