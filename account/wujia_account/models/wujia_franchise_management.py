from odoo import api, fields, models


class WujiaFranchiseManagement(models.Model):
    _inherit = 'wujia.franchise.management'

    # Aggregate công nợ cho badge portal. get_shell_badge() chạy trên MỌI trang mobile
    # (1500 user) ⇒ PHẢI là field store, đọc 0 query. Nguồn cập nhật: cron daily +
    # hook account.move/account.payment (xem models tương ứng). KHÔNG compute on-the-fly.
    portal_overdue_invoice_count = fields.Integer(
        string='Portal overdue invoices',
        default=0,
        readonly=True,
        help='Number of posted customer invoices past their due date with a remaining '
             'balance. Refreshed by daily cron + on invoice/payment changes.',
    )
    portal_debt_remaining = fields.Float(
        string='Portal debt remaining',
        default=0.0,
        readonly=True,
        help='Net outstanding balance in company currency (invoices minus credit notes). '
             'Refreshed by daily cron + on invoice/payment changes.',
    )

    def _recompute_portal_debt_batch(self):
        """Tính lại 2 aggregate cho các franchise trong self — 2 `_read_group` group-by
        franchise_id ⇒ O(1) query bất kể số cửa hàng (perf 1500 store)."""
        if not self:
            return
        today = fields.Date.context_today(self)
        Move = self.env['account.move'].sudo()
        ids = self.ids
        open_domain = [
            ('franchise_id', 'in', ids),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')),
        ]
        # Còn nợ ròng, tiền công ty: out_invoice dương, out_refund âm ⇒ cộng thẳng.
        remaining_map = {
            fr.id: total or 0.0
            for fr, total in Move._read_group(
                open_domain, groupby=['franchise_id'],
                aggregates=['amount_residual_signed:sum'])
        }
        # Quá hạn: chỉ hoá đơn khách (out_invoice) qua hạn còn dư.
        overdue_map = {
            fr.id: count
            for fr, count in Move._read_group(
                open_domain + [
                    ('move_type', '=', 'out_invoice'),
                    ('invoice_date_due', '<', today),
                    ('amount_residual', '>', 0),
                ],
                groupby=['franchise_id'], aggregates=['__count'])
        }
        for fr in self:
            fr.portal_overdue_invoice_count = overdue_map.get(fr.id, 0)
            fr.portal_debt_remaining = remaining_map.get(fr.id, 0.0)

    @api.model
    def _cron_recompute_portal_debt(self):
        """Cron daily — quá hạn đổi theo ngày nên phải quét lại toàn bộ. Cũng là lưới an
        toàn cho các đường đối soát không đi qua hook write() (recompute stored field)."""
        self.search([])._recompute_portal_debt_batch()
