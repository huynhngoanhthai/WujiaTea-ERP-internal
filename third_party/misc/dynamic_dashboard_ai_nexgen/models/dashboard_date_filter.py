# Copyright (C) NexGen Solutions
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
import datetime


class DynamicDashboardDateFilter(models.Model):
    _name = 'dynamic.dashboard.date.filter'
    _description = 'Custom Dashboard Date Filter'
    _order = 'sequence, name'
    _check_company_auto = True

    name = fields.Char(string='Name', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    offset_start = fields.Integer(
        string='Start Offset (days)',
        required=True,
        default=-30,
        help='Days relative to today for the range start. Negative = past (e.g. -7 = 7 days ago).',
    )
    offset_end = fields.Integer(
        string='End Offset (days)',
        required=True,
        default=0,
        help='Days relative to today for the range end. 0 = today.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )

    @api.constrains('offset_start', 'offset_end')
    def _check_offsets(self):
        for filt in self:
            if filt.offset_start > filt.offset_end:
                raise ValidationError(
                    _('Start Offset must be less than or equal to End Offset on date filter "%s".')
                    % filt.display_name
                )

    def resolve_range(self, today=None):
        """Return (start_date, end_date) for this custom filter."""
        self.ensure_one()
        if today is None:
            today = fields.Date.context_today(self)
        start = today + datetime.timedelta(days=self.offset_start)
        end = today + datetime.timedelta(days=self.offset_end)
        if start > end:
            start, end = end, start
        return start, end

    @api.model
    def get_filter_options(self):
        """Options for frontend global date dropdown."""
        options = []
        for rec in self.search([]):
            options.append({'id': rec.id, 'name': rec.name, 'key': f'custom_{rec.id}'})
        return options
