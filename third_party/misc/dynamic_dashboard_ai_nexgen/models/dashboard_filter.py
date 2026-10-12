# Copyright (C) NexGen Solutions
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from .constraints_utils import assert_domain


class DynamicDashboardFilter(models.Model):
    _name = 'dynamic.dashboard.filter'
    _description = 'Dashboard Custom Filters'
    _order = 'sequence, id'
    _check_company_auto = True

    name = fields.Char(string="Filter Label", required=True, translate=True)
    sequence = fields.Integer(default=10)
    dashboard_id = fields.Many2one(
        'dynamic.dashboard', string="Dashboard", required=True, ondelete='cascade',
        check_company=True,
    )
    model_id = fields.Many2one(
        'ir.model',
        string="Model",
        required=True,
        ondelete='cascade',
        domain="[('transient', '=', False)]",
    )
    model_name = fields.Char(string='Model Name', related='model_id.model', readonly=True)
    domain = fields.Char(string="Domain", required=True, default='[]')
    is_active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', related='dashboard_id.company_id', store=True, index=True,
    )

    # Phase 3 — linked / widget filters
    is_linked = fields.Boolean(
        string='Linked Filter',
        default=False,
        help='When enabled, applying this filter pushes its domain to all linked items/analyses.',
    )
    widget_type = fields.Selection([
        ('toggle', 'Toggle Button'),
        ('selection', 'Selection'),
        ('many2one', 'Many2one'),
        ('date', 'Date'),
    ], string='Widget Type', default='toggle')
    filter_field_id = fields.Many2one(
        'ir.model.fields',
        string='Filter Field',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'not in', ['one2many', 'many2many', 'binary', 'html', 'json'])]",
        ondelete='cascade',
        help='Optional field used by selection/many2one widgets.',
    )
    item_ids = fields.Many2many(
        'dynamic.dashboard.item',
        'dynamic_dashboard_ai_nexgen_filter_item_rel',
        'filter_id',
        'item_id',
        string='Target Items',
        help='If set, only these items receive the linked domain.',
    )
    analysis_ids = fields.Many2many(
        'dynamic.dashboard.analysis',
        'dynamic_dashboard_ai_nexgen_filter_analysis_rel',
        'filter_id',
        'analysis_id',
        string='Target Analyses',
    )

    @api.constrains('domain')
    def _check_domain(self):
        for filt in self:
            assert_domain(filt.domain, _('Domain'))

    @api.constrains('widget_type', 'filter_field_id')
    def _check_widget_field(self):
        for filt in self:
            if filt.widget_type in ('selection', 'many2one', 'date') and not filt.filter_field_id:
                raise ValidationError(
                    _('Filter Field is required for widget type "%(widget)s" on filter "%(name)s".',
                      widget=filt.widget_type, name=filt.display_name)
                )
