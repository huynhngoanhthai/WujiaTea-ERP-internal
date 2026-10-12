# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class WujiaFranchiseShiftTemplate(models.Model):
    _name = 'wujia.franchise.shift.template'
    _description = 'Franchise Shift Template'
    _order = 'sequence asc, id desc'

    name = fields.Char(
        string='Shift Name',
        required=True,
        help='Shift template name (e.g. Morning Shift 06:30 - 14:30).',
    )
    code = fields.Char(
        string='Shift Code',
        required=True,
        index=True,
        help='Shift code (e.g. MORNING, EVENING).',
    )
    sequence = fields.Integer(default=10)
    franchise_id = fields.Many2one(
        'wujia.franchise.management',
        string='Store Specific',
        ondelete='cascade',
        help='If empty, this shift template is global and available for all stores.',
    )
    start_time = fields.Float(
        string='Start Hour',
        required=True,
        help='Shift start hour in float (e.g. 6.5 = 06:30). Must be between 0 and 24.',
    )
    end_time = fields.Float(
        string='End Hour',
        required=True,
        help='Shift end hour in float (e.g. 14.5 = 14:30). If end_time <= start_time, shift spans overnight.',
    )
    break_minutes = fields.Integer(
        string='Break (Minutes)',
        default=0,
        help='Rest/Break time during shift in minutes.',
    )
    planned_hours = fields.Float(
        string='Planned Hours',
        compute='_compute_planned_hours',
        store=True,
        digits=(16, 2),
        help='Net planned working hours = (end - start) - break.',
    )
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)

    @api.constrains('start_time', 'end_time', 'break_minutes')
    def _check_shift_hours(self):
        for rec in self:
            if not (0 <= rec.start_time < 24):
                raise ValidationError(_("Start time (%s) must be between 0.0 and 24.0.", rec.start_time))
            if not (0 <= rec.end_time < 24):
                raise ValidationError(_("End time (%s) must be between 0.0 and 24.0.", rec.end_time))
            if rec.break_minutes < 0:
                raise ValidationError(_("Break duration (%s mins) cannot be negative.", rec.break_minutes))
            if rec.planned_hours <= 0:
                raise ValidationError(_("Planned working hours (%s hours) must be greater than zero.", rec.planned_hours))

    @api.depends('start_time', 'end_time', 'break_minutes')
    def _compute_planned_hours(self):
        for rec in self:
            if rec.end_time > rec.start_time:
                gross = rec.end_time - rec.start_time
            else:
                # Overnight shift (e.g. 22.0 to 06.0 -> 24 - 22 + 6 = 8)
                gross = (24.0 - rec.start_time) + rec.end_time
            net = gross - (rec.break_minutes / 60.0)
            rec.planned_hours = round(net, 2)
