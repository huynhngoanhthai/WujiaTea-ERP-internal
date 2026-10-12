# Copyright (C) NexGen Solutions
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DynamicDashboardTargetLine(models.Model):
    _name = 'dynamic.dashboard.target.line'
    _description = 'Dashboard Item Target Line'
    _check_company_auto = True

    item_id = fields.Many2one(
        'dynamic.dashboard.item', string='Dashboard Item', ondelete='cascade',
        check_company=True,
    )
    date_start = fields.Date(string='Start Date', required=True)
    date_end = fields.Date(string='End Date', required=True)
    target_value = fields.Float(string='Target Value', required=True)
    company_id = fields.Many2one(
        'res.company', string='Company', related='item_id.company_id', store=True, index=True,
    )

    @api.constrains('date_start', 'date_end')
    def _check_date_range(self):
        for line in self:
            if line.date_start and line.date_end and line.date_start > line.date_end:
                raise ValidationError(
                    _('Target line Start Date must be on or before End Date.')
                )
