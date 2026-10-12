from odoo import fields, models


class WujiaKnowledgeCategory(models.Model):
    _name = 'wujia.knowledge.category'
    _description = 'Wujia Knowledge Category'
    _order = 'sequence, name'
    _parent_store = True
    _parent_name = 'parent_id'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', help='Short slug for URL filter.')
    description = fields.Text(string='Description', translate=True)
    parent_id = fields.Many2one(
        'wujia.knowledge.category', string='Parent category',
        ondelete='set null', index=True,
    )
    parent_path = fields.Char(index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    article_count = fields.Integer(
        string='Articles', compute='_compute_article_count',
    )
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('uniq_code', 'unique(code)', 'Category code must be unique.'),
    ]

    def _compute_article_count(self):
        Article = self.env['wujia.knowledge.article'].sudo()
        groups = Article._read_group(
            [('category_id', 'in', self.ids), ('state', '=', 'published')],
            groupby=['category_id'], aggregates=['__count'],
        )
        mapping = {cat.id: count for cat, count in groups}
        for cat in self:
            cat.article_count = mapping.get(cat.id, 0)
