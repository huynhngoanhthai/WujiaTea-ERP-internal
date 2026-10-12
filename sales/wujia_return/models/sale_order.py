from odoo import _, api, fields, models


class SaleOrder(models.Model):
    """Huỷ SO bù → đóng quyền lợi (BA STT3 acceptance 12).

    Rule BA: allocation chuyển 'Đã huỷ', request cũ chuyển 'Hoàn tất', KHÔNG
    release/khôi phục quyền lợi — cần bù tiếp thì cửa hàng tạo yêu cầu mới.
    Khác hẳn `_release_shortfall` (kho giao thiếu, cố ý hoàn lại để bù kỳ sau).
    """

    _inherit = 'sale.order'

    wj_delivery_done_date = fields.Datetime(
        string='Fully delivered on', compute='_compute_wj_delivery_done_date',
        store=True, index=True, copy=False,
        help='Last validated delivery slip, set only once every outgoing slip of the order is done or cancelled.',
    )

    @api.depends('picking_ids.state', 'picking_ids.date_done', 'picking_ids.picking_type_id')
    def _compute_wj_delivery_done_date(self):
        for order in self:
            outgoing = order.picking_ids.filtered(lambda p: p.picking_type_id.code == 'outgoing')
            done = outgoing.filtered(lambda p: p.state == 'done')
            complete = done and all(p.state in ('done', 'cancel') for p in outgoing)
            order.wj_delivery_done_date = max(filter(None, done.mapped('date_done')), default=False) if complete else False

    def _action_cancel(self):
        res = super()._action_cancel()
        self._wujia_cancel_compensation()
        return res

    def _wujia_cancel_compensation(self):
        comp_orders = self.filtered('is_return_order')
        if not comp_orders:
            return
        allocations = self.env['wujia.compensation.allocation'].sudo().search([
            ('sale_order_id', 'in', comp_orders.ids),
            ('state', '!=', 'cancel'),
        ])
        if not allocations:
            return
        requests = allocations.request_id
        # KHÔNG đụng released_qty: quyền lợi đóng lại theo request chứ không quay
        # về hàng đợi phân bổ.
        allocations.write({
            'state': 'cancel',
            'release_reason': _("Compensation order cancelled — entitlement closed per request."),
        })
        to_close = requests.filtered(
            lambda r: r.state not in ('done', 'cancelled', 'rejected'))
        to_close.write({'state': 'done', 'resolved_date': fields.Datetime.now()})
        for req in to_close:
            req.message_post(body=_(
                "This compensation order was cancelled. If you still need compensation, please create a new request."))
