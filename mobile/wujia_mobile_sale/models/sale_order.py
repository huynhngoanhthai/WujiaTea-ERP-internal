# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = ['sale.order', 'wujia.mobile.mixin']

    mobile_badge_class = fields.Char(
        string='Mobile Badge Class',
        compute='_compute_mobile_card_helpers',
        store=False,
    )
    mobile_card_title = fields.Char(
        string='Mobile Card Title',
        compute='_compute_mobile_card_helpers',
        store=False,
    )

    @api.depends('state', 'partner_id', 'partner_id.name', 'name')
    def _compute_mobile_card_helpers(self):
        for rec in self:
            rec.mobile_badge_class = rec.get_mobile_badge_class(rec.state)

            if 'franchise_id' in self._fields and getattr(rec, 'franchise_id', False):
                if 'area_id' in self._fields and getattr(rec, 'area_id', False):
                    rec.mobile_card_title = f"{rec.franchise_id.name} ({rec.area_id.name})"
                else:
                    rec.mobile_card_title = rec.franchise_id.name
            elif rec.partner_id:
                rec.mobile_card_title = rec.partner_id.name
            else:
                rec.mobile_card_title = rec.name or ""

