from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    franchise_id = fields.Many2one(
        'wujia.franchise.management',
        string='Franchise store',
        compute='_compute_franchise_id',
        store=True,
        index=True,
        readonly=False,
        tracking=True,
        help='Store scope of this payment — derived from the reconciled invoices '
             '(one payment belongs to one store). Accountant can override.',
    )

    @api.depends('reconciled_invoice_ids.franchise_id')
    def _compute_franchise_id(self):
        """BA r1457: lấy từ hoá đơn được đối soát; một payment chỉ thuộc một franchise.
        Nhiều franchise khác nhau (đối soát nhiều cửa hàng) hoặc chưa đối soát → để trống,
        không đoán bừa. `readonly=False` cho kế toán sửa tay khi cần."""
        for pay in self:
            franchises = pay.reconciled_invoice_ids.franchise_id
            pay.franchise_id = franchises if len(franchises) == 1 else pay.franchise_id

    def write(self, vals):
        before = self.franchise_id if 'franchise_id' in vals else None
        res = super().write(vals)
        if {'state', 'franchise_id'}.intersection(vals):
            affected = self.franchise_id
            if before:
                affected |= before
            if affected:
                affected._recompute_portal_debt_batch()
        return res
