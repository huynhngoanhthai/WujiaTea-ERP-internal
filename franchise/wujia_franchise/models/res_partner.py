from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    franchise_ids = fields.One2many(
        'wujia.franchise.management',
        'partner_id',
        string='Franchise store',
    )
    is_franchise = fields.Boolean(
        string='Is a franchise store',
        compute='_compute_is_franchise',
        store=True,
        index=True,
        help='TRUE when the partner is used as the contact of at least one wujia.franchise.management.',
    )
    franchise_count = fields.Integer(
        string='Store count',
        compute='_compute_franchise_count',
    )

    @api.depends('franchise_ids')
    def _compute_is_franchise(self):
        for rec in self:
            rec.is_franchise = bool(rec.franchise_ids)

    @api.depends('franchise_ids')
    def _compute_franchise_count(self):
        for rec in self:
            rec.franchise_count = len(rec.franchise_ids)

    # ------------------------------------------------------------------
    # Mapping partner → cửa hàng (WJ-FRANCHISE-001/002, WJ-DEBT-006)
    # Nguồn duy nhất cho onchange cảnh báo, compute tự điền và lớp chặn.
    # ------------------------------------------------------------------
    def _wujia_franchise_mapping(self):
        """('none'|'unique'|'multi', franchises) của partner này.

        Dùng O2m đã prefetch nên gọi trên recordset không phát sinh query/bản ghi.
        Địa chỉ giao hàng là partner con ⇒ không map thì thử commercial_partner_id.
        Nhiều cửa hàng ⇒ thu hẹp theo store còn hiệu lực; vẫn nhiều thì KHÔNG đoán.
        """
        if not self:
            return 'none', self.env['wujia.franchise.management']
        self.ensure_one()
        franchises = self.franchise_ids
        if not franchises and self.commercial_partner_id != self:
            franchises = self.commercial_partner_id.franchise_ids
        if len(franchises) > 1:
            live = franchises.filtered(lambda f: f.status not in ('closed', 'expired'))
            if len(live) == 1:
                franchises = live
        if len(franchises) == 1:
            return 'unique', franchises
        if len(franchises) > 1:
            return 'multi', franchises
        return 'none', franchises

    def _wujia_unique_franchise(self):
        """Cửa hàng duy nhất của partner, recordset rỗng khi 0 hoặc nhiều."""
        Franchise = self.env['wujia.franchise.management']
        if not self:
            return Franchise
        state, franchises = self._wujia_franchise_mapping()
        return franchises if state == 'unique' else Franchise

    def _wujia_multi_mapping_warning(self):
        """Cảnh báo onchange khi partner map nhiều cửa hàng — không tự đoán."""
        if not self:
            return None
        state, franchises = self._wujia_franchise_mapping()
        if state != 'multi':
            return None
        return {'warning': {
            'title': _('Partner linked to multiple stores'),
            'message': _(
                "Partner '%(partner)s' is linked with %(count)s franchise stores: %(stores)s.\n"
                "The system cannot select automatically — please select franchise store manually.",
                partner=self.display_name,
                count=len(franchises),
                stores=', '.join(franchises.mapped('display_name')),
            ),
        }}

    def _wujia_assert_document_franchise(self, franchise, doc_label):
        """Chặn xác nhận/ghi sổ khi partner map duy nhất mà chứng từ trống/lệch cửa hàng.

        Partner không map (khách lẻ, nhà cung cấp) hoặc map nhiều ⇒ không chặn, để hoá
        đơn mua hàng và bút toán không bị vạ lây (LIMIT đã ghi cho BA)."""
        if not self:
            return
        expected = self._wujia_unique_franchise()
        if not expected or franchise == expected:
            return
        if not franchise:
            raise UserError(_(
                "Document '%(doc)s' has no franchise store specified.\nPartner '%(partner)s' belongs to store '%(store)s' — please fill the Franchise Store field and retry.",
                doc=doc_label, partner=self.display_name,
                store=expected.display_name,
            ))
        raise UserError(_(
            "Document '%(doc)s' is linked with store '%(current)s' but partner "
            "'%(partner)s' thuộc cửa hàng '%(store)s'.\n"
            "Hãy sửa lại cho khớp rồi thao tác lại.",
            doc=doc_label, current=franchise.display_name,
            partner=self.display_name, store=expected.display_name,
        ))

    def action_view_franchises(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Franchise Stores of %s', self.display_name),
            'res_model': 'wujia.franchise.management',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
