# Copyright (C) NexGen Solutions
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class DynamicDashboardNumberSystem(models.Model):
    _name = 'dynamic.dashboard.number.system'
    _description = 'Dashboard Custom Number System'
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(string='Name', required=True, translate=True)
    active = fields.Boolean(default=True)
    line_ids = fields.One2many(
        'dynamic.dashboard.number.system.line',
        'system_id',
        string='Thresholds',
        copy=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )

    def format_value(self, value):
        """Format a number using this system's thresholds (largest matching first)."""
        self.ensure_one()
        if value is None:
            return ''
        try:
            num = float(value)
        except (TypeError, ValueError):
            return str(value)
        sign = '-' if num < 0 else ''
        abs_num = abs(num)
        for line in self.line_ids.sorted(key=lambda l: l.threshold, reverse=True):
            if abs_num >= line.threshold and line.divisor:
                formatted = abs_num / line.divisor
                text = f'{formatted:.1f}'.rstrip('0').rstrip('.')
                return f'{sign}{text}{line.suffix or ""}'
        return f'{sign}{abs_num:g}'


class DynamicDashboardNumberSystemLine(models.Model):
    _name = 'dynamic.dashboard.number.system.line'
    _description = 'Number System Threshold Line'
    _order = 'threshold desc'
    _check_company_auto = True

    _divisor_nonzero = models.Constraint(
        'CHECK(divisor <> 0)',
        'Divisor cannot be zero.',
    )
    _threshold_positive = models.Constraint(
        'CHECK(threshold >= 0)',
        'Threshold cannot be negative.',
    )

    system_id = fields.Many2one(
        'dynamic.dashboard.number.system',
        required=True,
        ondelete='cascade',
        check_company=True,
    )
    threshold = fields.Float(
        string='Threshold',
        required=True,
        help='Apply this rule when |value| >= threshold.',
    )
    divisor = fields.Float(
        string='Divisor',
        required=True,
        default=1000.0,
        help='Value is divided by this before appending the suffix.',
    )
    suffix = fields.Char(string='Suffix', required=True, default='K')
    company_id = fields.Many2one(
        'res.company',
        related='system_id.company_id',
        store=True,
        index=True,
    )
