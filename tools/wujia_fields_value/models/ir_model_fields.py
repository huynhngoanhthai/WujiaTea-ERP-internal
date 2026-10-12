# -*- coding: utf-8 -*-

from odoo import models, api

class IrModelFields(models.Model):
    _inherit = 'ir.model.fields'

    @api.depends('field_description', 'name')
    def _compute_display_name(self):
        if self.env.context.get('from_fields_value'):
            for rec in self:
                rec.display_name = rec.field_description or rec.name
        else:
            super()._compute_display_name()
