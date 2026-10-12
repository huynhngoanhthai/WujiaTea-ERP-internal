# Copyright (C) NexGen Solutions
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval


class DynamicDashboardItemSource(models.Model):
    _name = 'dynamic.dashboard.item.source'
    _description = 'Dashboard Item Extra Data Source'
    _order = 'sequence, id'
    _check_company_auto = True

    name = fields.Char(string='Series Name', required=True)
    sequence = fields.Integer(default=10)
    item_id = fields.Many2one(
        'dynamic.dashboard.item',
        string='Dashboard Item',
        required=True,
        ondelete='cascade',
        index=True,
        check_company=True,
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        domain="[('transient', '=', False)]",
    )
    model_name = fields.Char(string='Model Technical Name', related='model_id.model', readonly=True)
    domain = fields.Char(string='Domain', default='[]')
    data_type = fields.Selection(
        [('sum', 'Sum'), ('count', 'Count'), ('average', 'Average')],
        string='Aggregation',
        default='sum',
        required=True,
    )
    measure_field_id = fields.Many2one(
        'ir.model.fields',
        string='Measure',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'in', ['integer', 'float', 'monetary']), ('name', '!=', 'id')]",
    )
    group_by_field_id = fields.Many2one(
        'ir.model.fields',
        string='Group By',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'not in', ['one2many', 'many2many', 'binary', 'html', 'json', 'properties'])]",
        help='Defaults to the parent item Group By when empty (same field name must exist on this model).',
    )
    group_by_date_type = fields.Selection([
        ('day', 'Day'),
        ('week', 'Week'),
        ('month', 'Month'),
        ('quarter', 'Quarter'),
        ('year', 'Year'),
    ], string='Group By Date', default='month')
    date_filter_field_id = fields.Many2one(
        'ir.model.fields',
        string='Date Filter Field',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'in', ['date', 'datetime'])]",
    )
    series_chart_type = fields.Selection(
        [('column', 'Column / Bar'), ('line', 'Line')],
        string='Series Style',
        default='column',
        help='Used on bar/line/area charts to mix column and line series.',
    )
    company_id = fields.Many2one(
        'res.company',
        related='item_id.company_id',
        store=True,
        index=True,
    )

    @api.constrains('domain')
    def _check_domain(self):
        from .constraints_utils import assert_domain
        for src in self:
            assert_domain(src.domain, _('Domain'))

    @api.constrains('data_type', 'measure_field_id')
    def _check_measure(self):
        for src in self:
            if src.data_type in ('sum', 'average') and not src.measure_field_id:
                raise ValidationError(
                    _('Measure field is required for Sum/Average data sources (%s).')
                    % src.display_name
                )

    @api.onchange('model_id')
    def _onchange_model_id(self):
        if not self.model_id:
            self.measure_field_id = False
            self.group_by_field_id = False
            self.date_filter_field_id = False
            return
        mid = self.model_id.id
        if self.measure_field_id and self.measure_field_id.model_id.id != mid:
            self.measure_field_id = False
        if self.group_by_field_id and self.group_by_field_id.model_id.id != mid:
            self.group_by_field_id = False
        if self.date_filter_field_id and self.date_filter_field_id.model_id.id != mid:
            self.date_filter_field_id = False

    def _get_source_series(self, parent_item, shared_domain_extra=None, date_range=None, drill_date_type=None):
        """Return (label -> value dict, ordered labels, series meta)."""
        self.ensure_one()
        if not self.model_id:
            return {}, [], {}
        model = self.env['dynamic.dashboard.item']._dd_scoped_model(self.sudo().model_id.model)
        domain = list(safe_eval(self.domain or '[]'))
        if shared_domain_extra:
            domain.extend(shared_domain_extra)

        # Optional date range on this source's date field
        date_field = self.date_filter_field_id or (
            parent_item.date_filter_field_id
            if parent_item.date_filter_field_id
            and parent_item.date_filter_field_id.model == self.sudo().model_id.model
            else False
        )
        if date_field and date_range and date_range[0] and date_range[1]:
            start, end = date_range
            domain += [(date_field.name, '>=', start), (date_field.name, '<=', end)]

        group_field = self.group_by_field_id or (
            parent_item.group_by_field_id
            if parent_item.group_by_field_id
            and parent_item.group_by_field_id.model == self.sudo().model_id.model
            else False
        )
        if not group_field:
            return {}, [], {'error': 'Group By is required for multi-source series "%s".' % self.name}

        agg = 'avg' if self.data_type == 'average' else self.data_type
        groupby_main = group_field.name
        if group_field.ttype in ('date', 'datetime'):
            dtype = drill_date_type or self.group_by_date_type or parent_item.group_by_date_type or 'month'
            groupby_main = f"{groupby_main}:{dtype}"

        measure_name = self.measure_field_id.name if self.measure_field_id and agg != 'count' else None
        aggregates = [f"{measure_name}:{agg}", '__count'] if measure_name else ['__count']

        rows = model.formatted_read_group(
            domain,
            groupby=[groupby_main],
            aggregates=aggregates,
            limit=parent_item.record_limit or None,
        )

        label_values = {}
        labels = []
        for res in rows:
            raw = res.get(groupby_main)
            if isinstance(raw, tuple):
                label = str(raw[1] or 'Undefined')
            else:
                label = str(raw or 'Undefined')
            if measure_name:
                val = res.get(f"{measure_name}:{agg}", 0) or 0
            else:
                val = res.get('__count', 0) or 0
            if parent_item.multiplier_active:
                val = val * parent_item.multiplier_value
            labels.append(label)
            label_values[label] = val

        meta = {
            'name': self.name,
            'series_chart_type': self.series_chart_type or 'column',
            'yAxisID': 'y',
        }
        return label_values, labels, meta
