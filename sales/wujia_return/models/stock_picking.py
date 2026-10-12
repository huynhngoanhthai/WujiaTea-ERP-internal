from odoo import _, fields, models

EPS = 1e-6


class StockPicking(models.Model):
    """Hook giao thực tế → cập nhật số đã bù (BA K2 điểm 4).

    `compensated_qty` CHỈ tăng ở đây (từ picking done), không từ lúc tạo/confirm
    SO bù. Giao nhiều đợt / backorder → cộng dồn từng phiếu. Kho giao thiếu không
    backorder → hoàn lại phần chênh để bù kỳ sau.
    """

    _inherit = 'stock.picking'

    def _action_done(self):
        res = super()._action_done()
        self._wujia_apply_compensation_delivery()
        return res

    def _wujia_apply_compensation_delivery(self):
        Move = self.env['stock.move']
        if 'sale_line_id' not in Move._fields:
            return
        Allocation = self.env['wujia.compensation.allocation'].sudo()
        cancel_backorder = bool(self.env.context.get('cancel_backorder'))
        touched = self.env['wujia.return.request'].sudo()
        # CHỈ phiếu XUẤT (giao cho cửa hàng): early-exit phiếu nhập/nội bộ (perf
        # 1500 user) + không đếm nhầm move của phiếu TRẢ HÀNG (incoming, cũng mang
        # sale_line_id) là "đã giao".
        for picking in self.filtered(
                lambda p: p.picking_type_id.code == 'outgoing'):
            comp_moves = picking.move_ids.filtered(
                lambda m: m.sale_line_id
                and m.sale_line_id.order_id.is_return_order)
            for sale_line in comp_moves.mapped('sale_line_id'):
                allocations = Allocation.search([
                    ('sale_order_line_id', '=', sale_line.id),
                    ('state', '!=', 'cancel'),
                ], order='allocation_date, id')
                if not allocations:
                    continue
                delivered = sum(
                    self._move_qty_in_line_uom(m, sale_line)
                    for m in comp_moves
                    if m.sale_line_id == sale_line and m.state == 'done')
                touched |= self._fill_allocations(allocations, delivered)
                # Điểm 4b: giao xong (không backorder) mà allocation còn open → hoàn.
                # Chỉ xét move XUẤT còn treo (bỏ qua move phiếu trả hàng incoming).
                pending = sale_line.move_ids.filtered(
                    lambda m: m.state not in ('done', 'cancel')
                    and m.picking_id.picking_type_id.code == 'outgoing')
                if cancel_backorder or not pending:
                    touched |= self._release_shortfall(allocations)
        if touched:
            touched._apply_compensation_delivery()

    @staticmethod
    def _move_qty_in_line_uom(move, sale_line):
        line_uom = sale_line.product_uom_id
        if move.product_uom and line_uom and move.product_uom != line_uom:
            return move.product_uom._compute_quantity(move.quantity, line_uom)
        return move.quantity

    @staticmethod
    def _delivery_to_claim(qty_delivery, request):
        """SL giao (ĐVT giao) → quyền lợi (ĐVT approved = allocation_uom)."""
        if request.compensation_policy == 'accumulate':
            return qty_delivery * (request.compensation_unit_qty or 0.0)
        du, cu = request.compensation_delivery_uom_id, request.approved_uom_id
        if du and cu and du != cu:
            return du._compute_quantity(qty_delivery, cu, rounding_method='DOWN')
        return qty_delivery

    def _fill_allocations(self, allocations, delivered_delivery_qty):
        touched = self.env['wujia.return.request'].sudo()
        open_allocs = allocations.filtered(lambda a: a.open_qty > EPS)
        if not open_allocs or delivered_delivery_qty <= EPS:
            return touched
        pool = self._delivery_to_claim(delivered_delivery_qty, open_allocs[0].request_id)
        now = fields.Datetime.now()
        for alloc in open_allocs:
            if pool <= EPS:
                break
            take = min(pool, alloc.open_qty)
            delivered = alloc.delivered_qty + take
            new_open = alloc.allocated_qty - delivered - alloc.released_qty
            alloc.write({
                'delivered_qty': delivered,
                'delivered_date': now,
                'state': 'done' if new_open <= EPS else 'partial',
            })
            pool -= take
            touched |= alloc.request_id
        return touched

    def _release_shortfall(self, allocations):
        touched = self.env['wujia.return.request'].sudo()
        now = fields.Datetime.now()
        for alloc in allocations.filtered(
                lambda a: a.state != 'cancel' and a.open_qty > EPS):
            alloc.write({
                'released_qty': alloc.released_qty + alloc.open_qty,
                'release_reason': _("Warehouse delivered short; returned for the next compensation round."),
                'state': 'done',
                'delivered_date': alloc.delivered_date or now,
            })
            touched |= alloc.request_id
        return touched
