from odoo import api, fields, models

# Field đổi giá trị → cần tính lại badge công nợ (portal). Chỉ đúng những field ảnh
# hưởng "còn nợ / quá hạn": posting, số dư, hạn, cửa hàng. Không đụng các field khác.
_DEBT_TRIGGER_FIELDS = frozenset({
    'state', 'payment_state', 'amount_residual', 'invoice_date_due', 'franchise_id',
})


class AccountMove(models.Model):
    _inherit = 'account.move'

    franchise_id = fields.Many2one(
        'wujia.franchise.management',
        string='Franchise store',
        compute='_compute_franchise_id',
        store=True,
        readonly=False,
        index=True,
        copy=False,
        tracking=True,
        help='Store scope of this invoice / credit note — used for portal debt filtering '
             '(BA Model/Field N). Derived from the partner when it maps to exactly one '
             'store; the originating sale order and invoice reversals also propagate it.',
    )

    @api.depends('partner_id')
    def _compute_franchise_id(self):
        for move in self:
            # Partner không map / map nhiều: giữ nguyên giá trị đang có, không đoán.
            move.franchise_id = move.partner_id._wujia_unique_franchise() or move.franchise_id

    @api.onchange('partner_id')
    def _onchange_partner_id_franchise_warning(self):
        return self.partner_id._wujia_multi_mapping_warning()

    def action_post(self):
        # WJ-FRANCHISE-002: chỉ soi hoá đơn/giấy báo có khách hàng — bút toán và
        # hoá đơn nhà cung cấp không thuộc phạm vi công nợ portal.
        for move in self:
            if move.move_type in ('out_invoice', 'out_refund'):
                move.partner_id._wujia_assert_document_franchise(
                    move.franchise_id, move.display_name,
                )
        return super().action_post()

    # ------------------------------------------------------------------
    # WJ-DEBT-006: giấy báo có kế thừa cửa hàng của hoá đơn gốc.
    # Field khai copy=False (giữ nguyên hành vi nút Nhân bản) nên phải nhồi
    # tường minh vào default values của luồng reversal chuẩn Odoo.
    # ------------------------------------------------------------------
    def _reverse_moves(self, default_values_list=None, cancel=False):
        if default_values_list is None:
            default_values_list = [{} for _move in self]
        for move, default_values in zip(self, default_values_list):
            default_values.setdefault('franchise_id', move.franchise_id.id)
        return super()._reverse_moves(default_values_list, cancel=cancel)

    # ------------------------------------------------------------------
    # Giữ badge công nợ portal tươi khi hoá đơn đổi (post / đối soát / đổi hạn).
    # Recompute idempotent + chỉ chạm franchise bị ảnh hưởng ⇒ double-fire vô hại.
    # ------------------------------------------------------------------
    def _debt_refresh(self, extra_franchises=None):
        franchises = self.franchise_id
        if extra_franchises:
            franchises |= extra_franchises
        if franchises:
            franchises._recompute_portal_debt_batch()

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        moves._debt_refresh()
        return moves

    def write(self, vals):
        before = self.franchise_id if 'franchise_id' in vals else None
        res = super().write(vals)
        if _DEBT_TRIGGER_FIELDS.intersection(vals):
            self._debt_refresh(extra_franchises=before)
        return res
