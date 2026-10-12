from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class WujiaExamTimeSlot(models.Model):
    """Ca thi (khung giờ) — config dùng chung cho khóa thi / kỳ thi."""

    _name = 'wujia.exam.time.slot'
    _description = 'Wujia Exam Time Slot'
    _order = 'time_from, id'

    name = fields.Char(string='Time slot name', required=True)
    code = fields.Char(string='Slot code', required=True)
    time_from = fields.Float(string='Start time', required=True)
    time_to = fields.Float(string='End time', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _uniq_code = models.Constraint(
        'unique(code)', 'Time slot code must be unique.',
    )

    @api.constrains('time_from', 'time_to')
    def _check_time_range(self):
        for rec in self:
            if not (0.0 <= rec.time_from < rec.time_to <= 24.0):
                raise ValidationError(_(
                    "Time slot '%s': hours must satisfy 0 ≤ start < end ≤ 24.",
                    rec.name))
