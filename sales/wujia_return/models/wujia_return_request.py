from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


STATE_SELECTION = [
    ('draft', 'Draft'),
    ('submitted', 'Submitted'),
    ('reviewing', 'Under review'),
    ('approved', 'Request approved'),
    ('processing', 'In progress'),
    ('done', 'Processed'),
    ('rejected', 'Rejected'),
    ('cancelled', 'Voided'),
]

RESOLUTION_SELECTION = [
    ('exchange', 'Exchange'),
    ('return', 'Return'),
    ('compensation', 'Compensation'),
    ('refuse', 'Reject'),
]

MIN_IMAGES_BEFORE_SEND = 3

# Luật portal: 10 ngày kể từ khi đơn giao hoàn tất toàn bộ, minh chứng (#7).
ORDER_WINDOW_DAYS = 10
IMAGE_MIME = ('image/jpeg', 'image/jpg', 'image/png')
VIDEO_MIME = ('video/mp4', 'video/quicktime')
MAX_IMAGES = 5
MAX_IMAGE_MB = 5
MAX_VIDEOS = 1
MAX_VIDEO_MB = 10
MAX_TOTAL_MB = 30
# Yêu cầu còn mở (Home KPI) — BA: không tính nháp.
OPEN_STATES = ('submitted', 'processing', 'approved')


class WujiaReturnRequest(models.Model):
    """Yêu cầu đổi trả / bù hàng — 1 sản phẩm/phiếu (BA spec K, model/field tab).

    Sprint K1: redesign từ multi-line → single-product header + approval block +
    allocation tracking (compute). Xử lý bù hàng (wizard + SO 0đ) = K2.
    """

    _name = 'wujia.return.request'
    _description = 'Wujia Return Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'

    name = fields.Char(
        string='Request code', required=True, copy=False,
        readonly=True, default=lambda self: '/', tracking=True,
    )
    request_date = fields.Datetime(
        string='Request date', default=fields.Datetime.now,
        index=True, required=True, readonly=True, tracking=True,
    )
    requester_user_id = fields.Many2one(
        'res.users', string='Created by',
        default=lambda self: self.env.user, readonly=True, index=True,
        tracking=True,
    )
    franchise_id = fields.Many2one(
        'wujia.franchise.management', string='Franchise store',
        required=True, index=True, ondelete='restrict', tracking=True,
    )
    partner_id = fields.Many2one(
        'res.partner', string='Store partner',
        related='franchise_id.partner_id', store=True, index=True,
    )

    # --- Đơn hàng gốc (1 sản phẩm/phiếu) ---
    sale_order_id = fields.Many2one(
        'sale.order', string='Original order',
        domain="[('franchise_id', '=', franchise_id)]",
        ondelete='restrict', tracking=True,
    )
    sale_order_line_id = fields.Many2one(
        'sale.order.line', string='Order line',
        domain="[('order_id', '=', sale_order_id)]",
        ondelete='restrict', tracking=True,
    )
    product_id = fields.Many2one(
        'product.product', string='Product',
        related='sale_order_line_id.product_id', store=True,
        readonly=True, index=True,
    )
    product_uom_id = fields.Many2one(
        'uom.uom', string='Original order UoM',
        related='sale_order_line_id.product_uom_id', store=True, readonly=True,
    )
    batch_id = fields.Many2one(
        'stock.picking.batch', string='Delivery trip',
        related='sale_order_id.batch_id', store=True, readonly=True, index=True,
    )
    picking_id = fields.Many2one(
        'stock.picking', string='Delivery slip', ondelete='set null',
    )

    # --- Nội dung yêu cầu ---
    request_qty = fields.Float(
        string='Requested quantity', default=1.0,
        digits='Product Unit of Measure',
    )
    request_uom_id = fields.Many2one(
        'uom.uom', string='Requested UoM', required=True,
        help='Unit the franchise records the entitlement in (convertible with the compensation entitlement UoM).',
    )
    opening_datetime = fields.Datetime(string='Unboxing time', required=True)
    production_date = fields.Date(string='Production date')
    issue_type_id = fields.Many2one(
        'wujia.return.issue.type', string='Issue type',
        required=True, ondelete='restrict', tracking=True,
    )
    note = fields.Text(string='Note from the store')
    image_attachment_ids = fields.Many2many(
        'ir.attachment', 'wujia_return_image_rel',
        'request_id', 'attachment_id', string='Evidence photos',
        help='At least 3 photos are required when submitting (BA POR-036).',
    )
    video_attachment_ids = fields.Many2many(
        'ir.attachment', 'wujia_return_video_rel',
        'request_id', 'attachment_id', string='Evidence video',
    )

    # --- Workflow / xử lý ---
    state = fields.Selection(
        STATE_SELECTION, string='Status',
        default='submitted', required=True, index=True, tracking=True,
    )
    backend_note = fields.Text(string='Internal note')
    reject_reason = fields.Text(string='Rejection reason', tracking=True)
    resolution_type = fields.Selection(
        RESOLUTION_SELECTION, string='Resolution type', tracking=True,
    )
    resolved_date = fields.Datetime(string='Completion date', readonly=True, tracking=True)

    # --- Duyệt ---
    approved_qty = fields.Float(
        string='Approved qty', digits='Product Unit of Measure', tracking=True,
    )
    approved_uom_id = fields.Many2one('uom.uom', string='Approved UoM')
    approved_by_id = fields.Many2one('res.users', string='Approved by', readonly=True)
    approved_date = fields.Datetime(string='Approval date', readonly=True)
    approval_note = fields.Text(string='Approval note')
    compensation_product_id = fields.Many2one(
        'product.product', string='Compensation product (snapshot)',
    )
    compensation_delivery_uom_id = fields.Many2one(
        'uom.uom', string='Compensation delivery UoM (snapshot)',
    )
    compensation_unit_qty = fields.Float(
        string='Entitlement qty per delivery unit', digits='Product Unit of Measure',
        help='Entitlement quantity matching one compensation delivery unit (e.g. 1 bag = 10 kg).',
    )
    compensation_policy = fields.Selection(
        [('exact', 'Exact quantity'), ('accumulate', 'Whole-pack accumulation')],
        string='Compensation policy (snapshot)',
    )

    # --- Theo dõi phân bổ bù (K2 populate qua allocation) ---
    allocation_ids = fields.One2many(
        'wujia.compensation.allocation', 'request_id', string='Compensation allocations',
    )
    allocated_qty = fields.Float(
        string='Allocated', compute='_compute_allocation_totals', store=True,
        digits='Product Unit of Measure',
    )
    compensated_qty = fields.Float(
        string='Actually compensated', compute='_compute_allocation_totals', store=True,
        digits='Product Unit of Measure',
    )
    unallocated_qty = fields.Float(
        string='Not allocated', compute='_compute_allocation_totals', store=True,
        digits='Product Unit of Measure',
    )
    remaining_qty = fields.Float(
        string='Still short', compute='_compute_allocation_totals', store=True,
        digits='Product Unit of Measure',
    )
    compensation_status = fields.Selection(
        [('none', 'Not allocated'), ('allocated', 'Allocated'),
         ('partial', 'Partially compensated'), ('done', 'Fully compensated')],
        string='Compensation state', compute='_compute_allocation_totals', store=True,
    )
    compensation_so_ids = fields.Many2many(
        'sale.order', string='Compensation sales order',
        compute='_compute_compensation_so_ids',
    )
    compensation_so_count = fields.Integer(
        string='Compensation SO count', compute='_compute_compensation_so_ids',
    )

    @api.depends('allocation_ids.allocated_qty', 'allocation_ids.released_qty',
                 'allocation_ids.delivered_qty', 'allocation_ids.state',
                 'approved_qty')
    def _compute_allocation_totals(self):
        # 1 query read_group thay vì loop từng allocation (perf 1500 user).
        data = {}
        if self.ids:
            groups = self.env['wujia.compensation.allocation'].sudo()._read_group(
                domain=[('request_id', 'in', self.ids),
                        ('state', '!=', 'cancel')],
                groupby=['request_id'],
                aggregates=['allocated_qty:sum', 'released_qty:sum',
                            'delivered_qty:sum'],
            )
            for req, alloc, rel, deliv in groups:
                data[req.id] = (alloc or 0.0, rel or 0.0, deliv or 0.0)
        for rec in self:
            alloc, rel, deliv = data.get(rec.id, (0.0, 0.0, 0.0))
            rec.allocated_qty = alloc - rel
            rec.compensated_qty = deliv
            rec.unallocated_qty = (rec.approved_qty or 0.0) - rec.allocated_qty
            rec.remaining_qty = (rec.approved_qty or 0.0) - rec.compensated_qty
            if not rec.allocation_ids:
                rec.compensation_status = 'none'
            elif rec.remaining_qty <= 0:
                rec.compensation_status = 'done'
            elif rec.compensated_qty > 0:
                rec.compensation_status = 'partial'
            else:
                rec.compensation_status = 'allocated'

    @api.depends('allocation_ids.sale_order_id')
    def _compute_compensation_so_ids(self):
        for rec in self:
            sos = rec.allocation_ids.mapped('sale_order_id')
            rec.compensation_so_ids = sos
            rec.compensation_so_count = len(sos)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'wujia.return.request') or '/'
        return super().create(vals_list)

    @api.constrains('sale_order_line_id', 'sale_order_id')
    def _check_line_belongs_to_order(self):
        for rec in self:
            if rec.sale_order_line_id and rec.sale_order_id and \
                    rec.sale_order_line_id.order_id != rec.sale_order_id:
                raise ValidationError(_(
                    "The product line must belong to the selected original order."))

    @api.onchange('resolution_type', 'product_id')
    def _onchange_prefill_compensation(self):
        """Gợi ý snapshot bù từ cấu hình product khi HQ chọn phương án bù.

        Chỉ điền ô còn trống → HQ sửa tay không bị ghi đè.
        """
        for rec in self:
            if rec.resolution_type != 'compensation' or not rec.product_id:
                continue
            product = rec.product_id
            if not rec.compensation_product_id:
                rec.compensation_product_id = (
                    product.compensation_product_id or product)
            if not rec.compensation_delivery_uom_id:
                rec.compensation_delivery_uom_id = (
                    product.compensation_delivery_uom_id or product.uom_id)
            if not rec.compensation_unit_qty:
                rec.compensation_unit_qty = product.compensation_unit_qty
            if not rec.compensation_policy:
                rec.compensation_policy = product.compensation_policy
            if not rec.approved_uom_id:
                rec.approved_uom_id = (
                    product.compensation_claim_uom_id or rec.request_uom_id)
            if not rec.approved_qty:
                rec.approved_qty = rec.request_qty

    # ============================================================ workflow
    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            if len(rec.image_attachment_ids) < MIN_IMAGES_BEFORE_SEND:
                raise ValidationError(_(
                    "At least %s evidence photos are required before submitting.",
                    MIN_IMAGES_BEFORE_SEND))
            rec.state = 'submitted'
            rec.message_post(body=_("Request submitted."))

    def action_start_review(self):
        for rec in self:
            if rec.state == 'submitted':
                rec.state = 'reviewing'

    def action_approve(self):
        for rec in self:
            if rec.state not in ('submitted', 'reviewing'):
                raise ValidationError(_("Only submitted or in-review requests can be approved."))
            if rec.approved_qty <= 0:
                raise ValidationError(_("Enter the approved compensation qty (> 0) before approving."))
            if not rec.resolution_type:
                raise ValidationError(_("Select a resolution before approving."))
            rec.write({
                'state': 'approved',
                'approved_by_id': self.env.uid,
                'approved_date': fields.Datetime.now(),
            })
            rec.message_post(body=_("Request approved."))

    def action_reject(self):
        for rec in self:
            if rec.state in ('done', 'cancelled', 'rejected'):
                raise ValidationError(_("This request cannot be rejected."))
            if not rec.reject_reason:
                raise ValidationError(_("Enter a rejection reason before rejecting."))
            rec.write({'state': 'rejected', 'resolved_date': fields.Datetime.now()})
            rec.message_post(body=_("Request rejected: %s", rec.reject_reason))

    def action_cancel(self):
        for rec in self:
            if rec.state in ('done', 'cancelled'):
                raise ValidationError(_("This request cannot be cancelled."))
            rec.state = 'cancelled'
            rec.message_post(body=_("Request cancelled."))

    def action_mark_done(self):
        for rec in self:
            if rec.state != 'approved' or rec.resolution_type == 'compensation':
                raise ValidationError(_(
                    "Only approved non-compensation requests can be marked as done."))
            rec.write({'state': 'done', 'resolved_date': fields.Datetime.now()})
            rec.message_post(body=_("Request completed."))

    def _apply_compensation_delivery(self):
        """Chuyển processing→done khi đã bù đủ (gọi từ hook stock.picking).

        Rollup số liệu do `_compute_allocation_totals` lo; đây chỉ chuyển state
        sau khi delivered_qty của allocation được cập nhật từ giao thực tế.
        """
        for rec in self:
            if rec.state != 'processing':
                continue
            if rec.approved_qty > 0 and rec.remaining_qty <= 1e-6:
                rec.write({'state': 'done', 'resolved_date': fields.Datetime.now()})
                rec.message_post(body=_("Fully compensated — request completed."))

    def action_view_compensation_sos(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Compensation sales order'),
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.compensation_so_ids.ids)],
        }

    # ------------------------------------------------------------------
    # Portal — luật dùng chung cho mọi kênh (ADR-027)
    # ------------------------------------------------------------------
    @api.model
    def _portal_scope_domain(self, franchise_ids):
        return [('franchise_id', 'in', list(franchise_ids))]

    @api.model
    def _portal_open_domain(self, franchise_ids):
        return self._portal_scope_domain(franchise_ids) + [('state', 'in', list(OPEN_STATES))]

    @api.model
    def _portal_recent_domain(self, franchise_ids):
        return self._portal_scope_domain(franchise_ids) + [('state', 'not in', ['rejected', 'cancelled'])]

    def _portal_status_key(self):
        """Trạng thái portal: 'Đang xét' gộp 'Đang xử lý'; 'partial' = đang bù dở (không có trong schema)."""
        self.ensure_one()
        if self.state == 'processing' and self.compensation_status == 'partial':
            return 'partial'
        return 'processing' if self.state == 'reviewing' else self.state

    @api.model
    def _portal_status_domain(self, key):
        if key == 'partial':
            return [('state', '=', 'processing'), ('compensation_status', '=', 'partial')]
        if key == 'processing':
            return [('state', 'in', ('reviewing', 'processing')),
                    '!', ('compensation_status', '=', 'partial')]
        if key in dict(STATE_SELECTION) and key != 'reviewing':
            return [('state', '=', key)]
        return []

    @api.model
    def _portal_scope_order_domain(self, franchise_ids):
        return [('franchise_id', 'in', list(franchise_ids)), ('state', 'in', ['sale', 'done'])]

    @api.model
    def _portal_eligible_order_domain(self, franchise_ids):
        cutoff = fields.Datetime.now() - timedelta(days=ORDER_WINDOW_DAYS)
        return self._portal_scope_order_domain(franchise_ids) + [('wj_delivery_done_date', '>=', cutoff)]

    @api.model
    def _portal_check_order_window(self, order):
        done_date = order.wj_delivery_done_date
        if not done_date:
            raise ValidationError(_("This order has not been fully delivered yet, so a request cannot be created."))
        if done_date < fields.Datetime.now() - timedelta(days=ORDER_WINDOW_DAYS):
            local = fields.Datetime.context_timestamp(self, done_date)
            raise ValidationError(_(
                "More than %(days)s days have passed since the order was fully delivered (%(date)s).",
                days=ORDER_WINDOW_DAYS, date=local.strftime('%d/%m/%Y')))

    @api.model
    def _portal_check_product_config(self, product):
        """Câu báo nếu sản phẩm chưa cấu hình bù hợp lệ (BA STT3 #6), None nếu hợp lệ."""
        msg = self.env.company._wj_brand_text(_("This product has no compensation policy configured. Please contact {brand}."))
        if not product.compensation_enabled or not product.compensation_claim_uom_id:
            return msg
        delivery_uom = product.compensation_delivery_uom_id
        if product.compensation_policy == 'accumulate':
            unit = product.compensation_unit_qty or 0.0
            # tỷ lệ quy đổi chỉ hỗ trợ số nguyên > 0
            if not delivery_uom or unit <= 0 or abs(unit - round(unit)) > 1e-6:
                return msg
        elif delivery_uom and delivery_uom != product.compensation_claim_uom_id:
            root = self.env['wujia.compensation.process.wizard']._uom_root
            if root(delivery_uom) != root(product.compensation_claim_uom_id):
                return msg
        return None

    @api.model
    def _portal_check_evidence(self, images, videos):
        """``images``/``videos``: list ``(size_bytes, mime_thật)``; kênh tự đọc MIME từ nội dung."""
        if not MIN_IMAGES_BEFORE_SEND <= len(images) <= MAX_IMAGES:
            raise ValidationError(_("Please upload %(min)s to %(max)s evidence photos.",
                                    min=MIN_IMAGES_BEFORE_SEND, max=MAX_IMAGES))
        if len(videos) > MAX_VIDEOS:
            raise ValidationError(_("You can upload at most %s evidence video(s).", MAX_VIDEOS))
        bad = _("The file has an invalid format or exceeds the allowed size.")
        for files, allowed, max_mb in ((images, IMAGE_MIME, MAX_IMAGE_MB),
                                       (videos, VIDEO_MIME, MAX_VIDEO_MB)):
            for size, mime in files:
                if size > max_mb * 1024 * 1024 or mime not in allowed:
                    raise ValidationError(bad)
        if sum(size for size, _mime in images + videos) > MAX_TOTAL_MB * 1024 * 1024:
            raise ValidationError(_("Total evidence size cannot exceed %s MB.", MAX_TOTAL_MB))

    @api.model
    def _portal_prepare_vals(self, post, franchise_ids):
        """Form portal → vals; kiểm lại ở server mọi thứ client sửa được."""
        try:
            franchise_id = int(post.get('franchise_id') or 0)
        except (TypeError, ValueError):
            raise ValidationError(_("Invalid store."))
        if franchise_id not in set(franchise_ids):
            raise ValidationError(_("You cannot access this store."))
        try:
            order_id = int(post.get('sale_order_id') or 0)
            line_id = int(post.get('sale_order_line_id') or 0)
        except (TypeError, ValueError):
            raise ValidationError(_("Invalid order / product."))
        if not order_id or not line_id:
            raise ValidationError(_("Please select the original order and product."))
        order = self.env['sale.order'].sudo().search(
            self._portal_scope_order_domain([franchise_id]) + [('id', '=', order_id)], limit=1)
        if not order:
            raise ValidationError(_("The original order is invalid."))
        self._portal_check_order_window(order)
        line = order.order_line.filtered(lambda l: l.id == line_id)
        if not line or not line.product_id:
            raise ValidationError(_("The product must belong to the store's original order."))
        config_error = self._portal_check_product_config(line.product_id)
        if config_error:
            raise ValidationError(config_error)
        try:
            issue_type_id = int(post.get('issue_type_id'))
        except (TypeError, ValueError):
            issue_type_id = 0
        issue_type = self.env['wujia.return.issue.type'].sudo().search(
            [('id', '=', issue_type_id), ('active', '=', True)], limit=1)
        if not issue_type:
            raise ValidationError(_("Please select an issue type."))
        try:
            request_qty = float(post.get('request_qty') or 0)
        except (TypeError, ValueError):
            request_qty = 0.0
        if request_qty <= 0:
            raise ValidationError(_("The requested quantity must be greater than 0."))
        opening, opening_dt = post.get('opening_datetime') or '', False
        for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
            try:
                opening_dt = datetime.strptime(opening, fmt)
                break
            except ValueError:
                continue
        if not opening_dt:
            raise ValidationError(_("Please enter a valid unboxing time."))
        return {
            'franchise_id': franchise_id,
            'sale_order_id': order_id,
            'sale_order_line_id': line_id,
            # ĐVT khai = Claim UoM của sản phẩm (spec K), chưa cấu hình thì ĐVT đơn gốc
            'request_uom_id': line.product_id.compensation_claim_uom_id.id or line.product_uom_id.id,
            'request_qty': request_qty,
            'opening_datetime': opening_dt,
            'production_date': post.get('production_date') or False,
            'issue_type_id': issue_type.id,
            'note': (post.get('note') or '').strip()[:5000],
            'state': 'draft',
        }

    @api.model
    def create_from_portal(self, post, franchise_ids, images=(), videos=(), attach=None):
        """Kiểm → tạo → đính kèm (``attach(rr)``) → gửi, trong một savepoint; portal không có Lưu nháp.

        ``images``/``videos`` như ``_portal_check_evidence``. Lỗi nghiệp vụ ném ``ValidationError``.
        """
        vals = self._portal_prepare_vals(post, franchise_ids)
        self._portal_check_evidence(list(images), list(videos))
        with self.env.cr.savepoint():
            rr = self.sudo().create(vals)
            if attach:
                attach(rr)
            rr.action_submit()
        return rr

    def _portal_compensation_view(self):
        """Số liệu tiến độ bù cho cửa hàng (chỉ đọc); None khi HQ chưa chốt phương án."""
        self.ensure_one()
        if not self.resolution_type:
            return None
        if self.resolution_type != 'compensation':
            return {'is_compensation': False}
        approved, compensated = self.approved_qty or 0.0, self.compensated_qty or 0.0
        allocations = self.allocation_ids
        return {
            'is_compensation': True,
            'approved_qty': approved,
            'allocated_qty': self.allocated_qty or 0.0,
            'compensated_qty': compensated,
            'remaining_qty': self.remaining_qty or 0.0,
            'progress_pct': min(100, round(compensated / approved * 100)) if approved > 0 else 0,
            # BA STT3 #12: SO bù bị huỷ ⇒ quyền lợi đóng, cửa hàng tạo yêu cầu mới
            'all_cancelled': bool(allocations) and all(a.state == 'cancel' for a in allocations),
        }
