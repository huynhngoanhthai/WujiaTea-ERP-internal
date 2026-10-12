# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
"""AI Dashboard generator — model / keyword → preview → save."""
import json
import logging
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Pre-defined keywords for Generate with AI
AI_KEYWORD_SELECTION = [
    ('sales', 'Sales'),
    ('revenue', 'Revenue'),
    ('orders', 'Orders'),
    ('quotations', 'Quotations'),
    ('invoices', 'Invoices'),
    ('payments', 'Payments'),
    ('purchase', 'Purchase'),
    ('inventory', 'Inventory'),
    ('deliveries', 'Deliveries'),
    ('customers', 'Customers'),
    ('products', 'Products'),
    ('leads', 'Leads / CRM'),
    ('pipeline', 'Pipeline'),
    ('tasks', 'Tasks'),
    ('employees', 'Employees'),
    ('custom', 'Custom Keyword'),
]

KEYWORD_MODEL_HINTS = {
    'sales': ['sale.order', 'sale.order.line'],
    'revenue': ['sale.order', 'account.move'],
    'orders': ['sale.order'],
    'quotations': ['sale.order'],
    'invoices': ['account.move'],
    'payments': ['account.move', 'account.payment'],
    'purchase': ['purchase.order', 'purchase.order.line'],
    'inventory': ['stock.picking', 'stock.move', 'product.product'],
    'deliveries': ['stock.picking'],
    'customers': ['res.partner'],
    'products': ['product.template', 'product.product'],
    'leads': ['crm.lead'],
    'pipeline': ['crm.lead'],
    'tasks': ['project.task'],
    'employees': ['hr.employee'],
}


class DynamicDashboardAIWizardLine(models.TransientModel):
    _name = 'dynamic.dashboard.ai.wizard.line'
    _description = 'AI Dashboard Suggested Item'
    _order = 'sequence, id'

    wizard_id = fields.Many2one('dynamic.dashboard.ai.wizard', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    selected = fields.Boolean(string='Add', default=True)
    name = fields.Char(required=True)
    item_type = fields.Selection([
        ('tile', 'Tile'),
        ('kpi', 'KPI'),
        ('scorecard', 'Scorecard'),
        ('bar', 'Bar'),
        ('barLine', 'Bar + Line'),
        ('horizontalBar', 'Horizontal Bar'),
        ('line', 'Line'),
        ('area', 'Area'),
        ('stepLine', 'Step Line'),
        ('smoothedLine', 'Smoothed Line'),
        ('waterfall', 'Waterfall'),
        ('pie', 'Pie'),
        ('doughnut', 'Doughnut'),
        ('polarArea', 'Polar Area'),
        ('radar', 'Radar'),
        ('flower', 'Flower'),
        ('scatter', 'Scatter'),
        ('radialBar', 'Radial Bar'),
        ('gauge', 'Gauge'),
        ('funnel', 'Funnel'),
        ('pyramid', 'Pyramid'),
        ('treemap', 'Treemap'),
        ('sunburst', 'Sunburst'),
        ('forceDirected', 'Force Directed'),
        ('pack', 'Pack'),
        ('tree', 'Tree'),
        ('partition', 'Partition'),
        ('voronoiTreemap', 'Voronoi Treemap'),
        ('sankey', 'Sankey'),
        ('chord', 'Chord'),
        ('chordDirected', 'Directed Chord'),
        ('chordNonRibbon', 'Chord Non-Ribbon'),
        ('arcDiagram', 'Arc Diagram'),
        ('heatmap', 'Heatmap'),
        ('matrixHeatmap', 'Matrix Heatmap'),
        ('map', 'Map'),
        ('mapPoints', 'Map Points'),
        ('wordCloud', 'Word Cloud'),
        ('venn', 'Venn'),
        ('candlestick', 'Candlestick'),
        ('ohlc', 'OHLC'),
        ('timeline', 'Timeline'),
        ('serpentine', 'Serpentine'),
        ('spiral', 'Spiral'),
        ('pictorial', 'Pictorial'),
        ('bullet', 'Bullet'),
        ('list', 'List'),
    ], required=True, default='bar')
    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        domain="[('transient', '=', False)]",
    )
    model_name = fields.Char(related='model_id.model', readonly=True)
    data_type = fields.Selection([
        ('sum', 'Sum'),
        ('count', 'Count'),
        ('average', 'Average'),
    ], string='Calculation', default='sum')
    measure_field_id = fields.Many2one(
        'ir.model.fields',
        string='Measure',
        ondelete='cascade',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'in', ['integer', 'float', 'monetary']), ('name', '!=', 'id')]",
    )
    group_by_field_id = fields.Many2one(
        'ir.model.fields',
        string='Group By',
        ondelete='cascade',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('name', 'not in', ['id', 'display_name'])]",
    )
    date_filter_field_id = fields.Many2one(
        'ir.model.fields',
        string='Date Field',
        ondelete='cascade',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'in', ['date', 'datetime'])]",
    )
    date_filter_selection = fields.Selection([
        ('none', 'None (All Time)'),
        ('today', 'Today'),
        ('yesterday', 'Yesterday'),
        ('this_week', 'This Week'),
        ('this_month', 'This Month'),
        ('this_quarter', 'This Quarter'),
        ('this_year', 'This Year'),
        ('last_week', 'Last Week'),
        ('last_month', 'Last Month'),
        ('last_quarter', 'Last Quarter'),
        ('last_year', 'Last Year'),
        ('last_7_days', 'Last 7 Days'),
        ('last_30_days', 'Last 30 Days'),
        ('year_to_date', 'Year to Date'),
    ], string='Date Filter', default='this_year')
    group_by_date_type = fields.Selection([
        ('day', 'Day'),
        ('week', 'Week'),
        ('month', 'Month'),
        ('quarter', 'Quarter'),
        ('year', 'Year'),
    ], string='Date Granularity', default='month')
    summary = fields.Char(string='Summary', compute='_compute_summary')

    @api.depends(
        'item_type', 'model_id', 'model_id.model', 'data_type',
        'measure_field_id', 'measure_field_id.name',
        'group_by_field_id', 'group_by_field_id.name',
    )
    def _compute_summary(self):
        for line in self:
            bits = [line.item_type or '', line.model_id.model if line.model_id else '']
            if line.data_type:
                bits.append(line.data_type)
            if line.measure_field_id:
                bits.append(f'measure={line.measure_field_id.name}')
            if line.group_by_field_id:
                bits.append(f'group={line.group_by_field_id.name}')
            line.summary = ' · '.join(filter(None, bits))

    @api.onchange('model_id')
    def _onchange_model_id(self):
        """Clear field picks that no longer belong to the selected model."""
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



class DynamicDashboardAIWizard(models.TransientModel):
    _name = 'dynamic.dashboard.ai.wizard'
    _description = 'Generative AI Dashboard Wizard'

    state = fields.Selection([
        ('configure', 'Configure'),
        ('preview', 'Preview'),
    ], default='configure')

    generation_mode = fields.Selection([
        ('create_dashboard', 'Create Dashboard with AI'),
        ('add_items', 'Generate Items with AI'),
    ], string='AI Feature', default='create_dashboard', required=True)

    input_mode = fields.Selection([
        ('model', 'By Model'),
        ('keyword', 'By Keyword'),
    ], string='Generate Using', default='model', required=True,
       help='Pick a model, or pick a business keyword.')

    name = fields.Char(string='Dashboard Name')
    dashboard_id = fields.Many2one(
        'dynamic.dashboard',
        string='Target Dashboard',
        help='Required when generating items for an existing dashboard.',
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        domain="[('transient', '=', False)]",
        help='Primary Odoo model used to build the dashboard / items.',
    )
    model_name = fields.Char(related='model_id.model', readonly=True)

    keyword = fields.Selection(AI_KEYWORD_SELECTION, string='Keyword', default='sales')
    custom_keyword = fields.Char(string='Custom Keyword')
    prompt = fields.Text(
        string='Extra Instructions',
        help='Optional — refine what AI should focus on.',
    )
    item_count = fields.Integer(string='Max Items', default=8)

    suggested_name = fields.Char(string='AI Suggested Name', readonly=True)
    line_ids = fields.One2many('dynamic.dashboard.ai.wizard.line', 'wizard_id', string='Suggested Items')
    selected_count = fields.Integer(compute='_compute_selected_count')

    @api.depends('line_ids.selected')
    def _compute_selected_count(self):
        for wiz in self:
            wiz.selected_count = len(wiz.line_ids.filtered('selected'))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        if ctx.get('default_generation_mode'):
            res['generation_mode'] = ctx['default_generation_mode']
        # Opening from an existing dashboard always adds items to that board
        if ctx.get('default_dashboard_id'):
            res['dashboard_id'] = ctx['default_dashboard_id']
            res['generation_mode'] = 'add_items'
        if ctx.get('default_keyword'):
            res['keyword'] = ctx['default_keyword']
            res['input_mode'] = 'keyword'
        if ctx.get('default_ai_keyword'):
            res['custom_keyword'] = ctx['default_ai_keyword']
            res['keyword'] = 'custom'
            res['input_mode'] = 'keyword'
        # Pre-select a sensible installed model
        if not res.get('model_id'):
            for candidate in (
                'sale.order', 'account.move', 'purchase.order', 'stock.picking',
                'res.partner', 'crm.lead', 'dynamic.dashboard.demo.record',
            ):
                if candidate in self.env:
                    model = self.env['ir.model'].sudo().search([('model', '=', candidate)], limit=1)
                    if model:
                        res['model_id'] = model.id
                        break
        return res

    @api.onchange('generation_mode')
    def _onchange_generation_mode(self):
        if self.generation_mode == 'create_dashboard':
            if not self.name:
                self.name = _('AI Dashboard')
        elif self.generation_mode == 'add_items' and not self.dashboard_id:
            # keep UX hint; validation happens on generate/save
            pass

    @api.onchange('input_mode', 'keyword')
    def _onchange_keyword_prefill_model(self):
        if self.input_mode != 'keyword' or self.keyword == 'custom':
            return
        for candidate in KEYWORD_MODEL_HINTS.get(self.keyword) or []:
            if candidate in self.env:
                model = self.env['ir.model'].sudo().search([('model', '=', candidate)], limit=1)
                if model:
                    self.model_id = model
                    break

    # ------------------------------------------------------------------
    # Catalog / prompt helpers
    # ------------------------------------------------------------------
    def _ai_model_catalog_entry(self, model_name):
        if model_name not in self.env:
            return False
        model = self.env['ir.model'].sudo().search([('model', '=', model_name)], limit=1)
        if not model:
            return False
        IrField = self.env['ir.model.fields'].sudo()
        measures = IrField.search([
            ('model_id', '=', model.id), ('store', '=', True),
            ('ttype', 'in', ['integer', 'float', 'monetary']),
            ('name', 'not in', ['id']),
        ], limit=25)
        dimensions = IrField.search([
            ('model_id', '=', model.id), ('store', '=', True),
            ('ttype', 'in', ['many2one', 'selection', 'char', 'boolean']),
            ('name', 'not in', ['id', 'display_name']),
        ], limit=25)
        dates = IrField.search([
            ('model_id', '=', model.id), ('store', '=', True),
            ('ttype', 'in', ['date', 'datetime']),
        ], limit=10)
        return {
            'model': model_name,
            'label': model.name,
            'measures': measures.mapped('name'),
            'dimensions': dimensions.mapped('name'),
            'dates': dates.mapped('name'),
        }

    def _ai_build_catalog(self):
        """Focus on the selected model (+ keyword related models)."""
        names = []
        if self.model_id:
            names.append(self.model_id.model)
        if self.input_mode == 'keyword' and self.keyword != 'custom':
            names.extend(KEYWORD_MODEL_HINTS.get(self.keyword) or [])
        # Always allow partner/demo as soft fallbacks
        for extra in ('res.partner', 'dynamic.dashboard.demo.record'):
            if extra not in names:
                names.append(extra)
        catalog = []
        seen = set()
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            entry = self._ai_model_catalog_entry(name)
            if entry:
                catalog.append(entry)
        return catalog

    def _ai_user_intent(self):
        parts = []
        if self.generation_mode == 'create_dashboard':
            parts.append('Create a FULL dashboard (tiles + charts + optional list).')
        else:
            parts.append('Generate ADDITIONAL dashboard items for an existing dashboard.')
        if self.input_mode == 'model' and self.model_id:
            parts.append(f'Primary model: {self.model_id.model} ({self.model_id.name}).')
        elif self.input_mode == 'keyword':
            kw = self.custom_keyword if self.keyword == 'custom' else dict(AI_KEYWORD_SELECTION).get(self.keyword)
            parts.append(f'Focus keyword: {kw}.')
            if self.model_id:
                parts.append(f'Preferred model: {self.model_id.model}.')
        if self.prompt:
            parts.append(f'Extra instructions: {self.prompt.strip()}')
        if self.name:
            parts.append(f'Dashboard name hint: {self.name}')
        parts.append(f'Max items: {max(2, min(int(self.item_count or 8), 12))}')
        return '\n'.join(parts)

    def _ai_build_system_prompt(self, catalog):
        max_items = max(2, min(int(self.item_count or 8), 12))
        return f"""
You are an Odoo 19 dashboard builder.
Return ONLY valid JSON (no markdown).

Shape:
{{
  "dashboard_name": "Short title",
  "items": [
    {{
      "name": "Widget title",
      "item_type": "bar",
      "model": "sale.order",
      "data_type": "sum",
      "measure": "amount_total",
      "group_by": "state",
      "date_field": "date_order",
      "date_filter": "this_year",
      "group_by_date_type": "month"
    }}
  ]
}}

Rules:
- Generate {max_items} useful items (mix tiles/KPI + several chart types + optionally one list).
- Prefer the FIRST catalog model as the main source; only use other catalog models when relevant.
- Use ONLY exact model/field names from this catalog:
{json.dumps(catalog, indent=2)}
- item_type: tile, kpi, scorecard, bar, barLine, horizontalBar, line, area, stepLine,
  smoothedLine, waterfall, pie, doughnut, polarArea, radar, flower, scatter, radialBar,
  gauge, funnel, pyramid, treemap, sunburst, sankey, heatmap, map, wordCloud, bullet, list
- data_type: sum, count, average
- Charts need group_by; time trends use a date field as group_by with group_by_date_type=month.
- Never invent fields.
""".strip()

    @api.model
    def _ai_extract_json(self, content):
        if content is None:
            raise UserError(_('AI returned an empty response.'))
        text = str(content).strip()
        if not text:
            raise UserError(_('AI returned an empty response.'))
        fence = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text, flags=re.IGNORECASE)
        if fence:
            text = fence.group(1).strip()
        candidates = []
        for opener, closer in (('{', '}'), ('[', ']')):
            start = text.find(opener)
            end = text.rfind(closer)
            if start != -1 and end != -1 and end > start:
                candidates.append(text[start:end + 1])
        for candidate in candidates:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise UserError(
                _('AI response was not valid JSON.\n\n%s\n\nPreview:\n%s') % (e, text[:800])
            ) from e

    def _ai_normalize_items_payload(self, payload):
        dash_name = False
        items = payload
        if isinstance(payload, dict):
            dash_name = payload.get('dashboard_name') or payload.get('name') or False
            items = payload.get('items') or payload.get('widgets') or payload.get('dashboard_items') or []
        if not isinstance(items, list) or not items:
            raise UserError(_('AI returned no dashboard items. Adjust model/keyword and try again.'))
        return dash_name, items

    # ------------------------------------------------------------------
    # Layout / create (shared)
    # ------------------------------------------------------------------
    def _ai_resolve_field(self, model, field_name, ttypes=None):
        if not field_name or not model:
            return self.env['ir.model.fields']
        domain = [('model_id', '=', model.id), ('name', '=', field_name), ('store', '=', True)]
        if ttypes:
            domain.append(('ttype', 'in', list(ttypes)))
        return self.env['ir.model.fields'].sudo().search(domain, limit=1)

    def _ai_layout_for(self, item_type, placed):
        Item = self.env['dynamic.dashboard.item']
        w, h = Item._grid_size_for_type(item_type)
        w, h = Item._tune_grid_size_for_data(item_type, w, h)
        y = 0
        while True:
            for x_try in range(0, 12 - w + 1):
                conflict = False
                for px, py, pw, ph in placed:
                    if not (x_try + w <= px or px + pw <= x_try or y + h <= py or py + ph <= y):
                        conflict = True
                        break
                if not conflict:
                    placed.append((x_try, y, w, h))
                    return x_try, y, w, h
            y += 1

    def _ai_resolve_model(self, model_name):
        if not model_name or model_name not in self.env:
            return self.env['ir.model']
        return self.env['ir.model'].sudo().search([('model', '=', model_name)], limit=1)

    def _ai_line_vals_from_spec(self, spec, primary_model_name, sequence):
        """Convert AI JSON (string field names) into dynamic Many2one/Selection line vals."""
        IrField = self.env['ir.model.fields'].sudo()
        model_name = (spec.get('model') or primary_model_name or '').strip()
        model = self._ai_resolve_model(model_name)
        if not model and primary_model_name:
            model = self._ai_resolve_model(primary_model_name)
        if not model:
            return False

        item_type = spec.get('item_type') or 'bar'
        allowed_types = {k for k, _v in self.env['dynamic.dashboard.ai.wizard.line']._fields['item_type'].selection}
        if item_type not in allowed_types:
            item_type = 'bar'

        data_type = spec.get('data_type') or 'sum'
        if data_type not in ('sum', 'count', 'average'):
            data_type = 'sum'

        measure_name = spec.get('measure') or spec.get('measure_field_id') or False
        group_name = spec.get('group_by') or spec.get('group_by_field_id') or False
        date_name = spec.get('date_field') or spec.get('date_filter_field_id') or False

        measure = self._ai_resolve_field(model, measure_name, ('integer', 'float', 'monetary')) if measure_name else IrField
        group_by = self._ai_resolve_field(model, group_name) if group_name else IrField
        date_field = self._ai_resolve_field(model, date_name, ('date', 'datetime')) if date_name else IrField

        date_filter = spec.get('date_filter') or spec.get('date_filter_selection') or 'this_year'
        date_filter_field = self.env['dynamic.dashboard.ai.wizard.line']._fields['date_filter_selection']
        allowed_filters = {k for k, _v in date_filter_field.selection}
        if date_filter not in allowed_filters:
            date_filter = 'this_year'

        gran = spec.get('group_by_date_type') or 'month'
        if gran not in ('day', 'week', 'month', 'quarter', 'year'):
            gran = 'month'

        return {
            'sequence': sequence,
            'selected': True,
            'name': (spec.get('name') or _('AI Widget'))[:128],
            'item_type': item_type,
            'model_id': model.id,
            'data_type': data_type,
            'measure_field_id': measure.id if measure else False,
            'group_by_field_id': group_by.id if group_by else False,
            'date_filter_field_id': date_field.id if date_field else False,
            'date_filter_selection': date_filter,
            'group_by_date_type': gran,
        }

    def _ai_create_item_from_line(self, dashboard, line, index, placed):
        Item = self.env['dynamic.dashboard.item'].sudo()
        model = line.model_id
        if not model or model.model not in self.env:
            return False

        item_type = line.item_type or 'bar'
        data_type = line.data_type or 'sum'
        measure = line.measure_field_id
        group_by = line.group_by_field_id
        date_field = line.date_filter_field_id

        if not measure and data_type != 'count' and item_type not in ('list',):
            measure = self.env['ir.model.fields'].sudo().search([
                ('model_id', '=', model.id), ('store', '=', True),
                ('ttype', 'in', ['monetary', 'float', 'integer']),
                ('name', 'not in', ['id']),
            ], limit=1)
            if not measure:
                data_type = 'count'

        chart_types = {
            'bar', 'barLine', 'horizontalBar', 'line', 'area', 'stepLine', 'smoothedLine',
            'waterfall', 'pie', 'doughnut', 'polarArea', 'radar', 'flower', 'scatter',
            'radialBar', 'gauge', 'funnel', 'pyramid', 'treemap', 'sunburst', 'sankey',
            'bullet', 'map', 'heatmap', 'wordCloud', 'matrixHeatmap',
        }
        if item_type in chart_types and not group_by:
            group_by = self.env['ir.model.fields'].sudo().search([
                ('model_id', '=', model.id), ('store', '=', True),
                ('ttype', 'in', ['selection', 'many2one']),
                ('name', 'not in', ['id', 'company_id', 'currency_id']),
            ], limit=1)
        if not date_field:
            date_field = self.env['ir.model.fields'].sudo().search([
                ('model_id', '=', model.id), ('store', '=', True),
                ('ttype', 'in', ['date', 'datetime']),
            ], limit=1)

        group_by_date_type = line.group_by_date_type or 'month'
        if group_by and group_by.ttype in ('date', 'datetime'):
            if group_by_date_type not in ('day', 'week', 'month', 'quarter', 'year'):
                group_by_date_type = 'month'
        date_filter = line.date_filter_selection or 'this_year'

        x, y, w, h = self._ai_layout_for(item_type, placed)
        vals = {
            'name': (line.name or _('AI Widget %s') % (index + 1))[:128],
            'dashboard_id': dashboard.id,
            'item_type': item_type,
            'model_id': model.id,
            'data_calculation_type': 'custom',
            'data_type': data_type,
            'domain': '[]',
            'grid_x': x, 'grid_y': y, 'grid_w': w, 'grid_h': h,
            'sequence': (index + 1) * 10,
            'chart_theme': ['corporate', 'ocean', 'warm', 'cool', 'pastel', 'vibrant'][index % 6],
            'show_data_value': item_type in ('pie', 'doughnut', 'funnel', 'tile', 'kpi'),
            'show_records': True,
            'enable_drill_down': True,
            'date_filter_selection': date_filter if date_field else 'none',
            'group_by_date_type': group_by_date_type,
        }
        if measure:
            vals['measure_field_ids'] = [(6, 0, [measure.id])]
        if group_by and item_type in chart_types:
            vals['group_by_field_id'] = group_by.id
        if date_field:
            vals['date_filter_field_id'] = date_field.id
        if item_type == 'list':
            list_fields = self.env['ir.model.fields'].sudo().search([
                ('model_id', '=', model.id), ('store', '=', True),
                ('ttype', 'in', ['char', 'many2one', 'selection', 'monetary', 'date', 'datetime']),
            ], limit=6)
            if list_fields:
                vals.update({
                    'list_view_type': 'ungrouped',
                    'list_view_field_ids': [(6, 0, list_fields.ids)],
                })
        if item_type == 'kpi':
            vals.update({
                'enable_target': True,
                'standard_target_value': 100000 if measure else 50,
                'target_view': 'progress_bar',
            })
        if item_type in ('tile', 'kpi', 'scorecard'):
            vals['tile_icon'] = {'tile': 'fa-bar-chart', 'kpi': 'fa-line-chart', 'scorecard': 'fa-dashboard'}.get(item_type)
            vals['tile_color'] = '#e8f0fe'
        if item_type == 'scatter' and measure:
            measure2 = self.env['ir.model.fields'].sudo().search([
                ('model_id', '=', model.id), ('store', '=', True),
                ('ttype', 'in', ['integer', 'float', 'monetary']),
                ('id', '!=', measure.id),
            ], limit=1)
            vals.update({
                'scatter_measure_x_id': measure.id,
                'scatter_measure_y_id': (measure2 or measure).id,
                'is_scatter_group': bool(group_by),
            })
        try:
            return Item.with_context(dd_skip_auto_layout=True).create(vals)
        except Exception:
            _logger.exception('AI wizard failed creating %r', vals.get('name'))
            return False

    def _ai_heuristic_items(self, catalog):
        """Fallback when LLM is unavailable: build sensible widgets from the model catalog."""
        if not catalog:
            return []
        entry = catalog[0]
        model = entry['model']
        measures = entry.get('measures') or []
        dims = entry.get('dimensions') or []
        dates = entry.get('dates') or []
        measure = measures[0] if measures else False
        dim = dims[0] if dims else False
        date_f = dates[0] if dates else False
        items = [
            {'name': _('%s Count') % entry['label'], 'item_type': 'tile', 'model': model,
             'data_type': 'count', 'date_field': date_f, 'date_filter': 'this_year'},
        ]
        if measure:
            items.append({
                'name': _('%s Total') % (measure.replace('_', ' ').title()),
                'item_type': 'kpi', 'model': model, 'data_type': 'sum', 'measure': measure,
                'date_field': date_f, 'date_filter': 'this_year',
            })
            if dim:
                items.append({
                    'name': _('%s by %s') % (measure.replace('_', ' ').title(), dim),
                    'item_type': 'bar', 'model': model, 'data_type': 'sum',
                    'measure': measure, 'group_by': dim, 'date_field': date_f, 'date_filter': 'this_year',
                })
                items.append({
                    'name': _('%s Mix') % entry['label'],
                    'item_type': 'pie', 'model': model, 'data_type': 'sum',
                    'measure': measure, 'group_by': dim, 'date_field': date_f, 'date_filter': 'this_year',
                })
            if date_f:
                items.append({
                    'name': _('%s Trend') % entry['label'],
                    'item_type': 'line', 'model': model, 'data_type': 'sum',
                    'measure': measure, 'group_by': date_f, 'date_field': date_f,
                    'date_filter': 'this_year', 'group_by_date_type': 'month',
                })
                items.append({
                    'name': _('%s Area') % entry['label'],
                    'item_type': 'area', 'model': model, 'data_type': 'sum',
                    'measure': measure, 'group_by': date_f, 'date_field': date_f,
                    'date_filter': 'this_year', 'group_by_date_type': 'month',
                })
        if dim:
            items.append({
                'name': _('%s by %s') % (entry['label'], dim),
                'item_type': 'horizontalBar', 'model': model, 'data_type': 'count',
                'group_by': dim, 'date_field': date_f, 'date_filter': 'this_year',
            })
        items.append({
            'name': _('%s List') % entry['label'],
            'item_type': 'list', 'model': model, 'data_type': 'count',
            'date_field': date_f, 'date_filter': 'this_year',
        })
        return items[: max(2, min(int(self.item_count or 8), 12))]

    # ------------------------------------------------------------------
    # Wizard actions
    # ------------------------------------------------------------------
    def action_back_configure(self):
        self.ensure_one()
        self.write({'state': 'configure'})
        return self._reopen()

    def action_select_all(self):
        self.ensure_one()
        self.line_ids.write({'selected': True})
        return self._reopen()

    def action_select_none(self):
        self.ensure_one()
        self.line_ids.write({'selected': False})
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dynamic.dashboard.ai.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': dict(self.env.context),
        }

    def action_generate_suggestions(self):
        """Step 1 → call AI (or heuristic) and show selectable preview."""
        self.ensure_one()
        if self.generation_mode == 'add_items' and not self.dashboard_id:
            raise UserError(_('Select a Target Dashboard for “Generate Items with AI”.'))
        if self.input_mode == 'model' and not self.model_id:
            raise UserError(_('Please select a Model.'))
        if self.input_mode == 'keyword' and self.keyword == 'custom' and not (self.custom_keyword or '').strip():
            raise UserError(_('Enter a custom keyword.'))
        if self.input_mode == 'keyword' and not self.model_id:
            # Auto-pick from keyword hints
            self._onchange_keyword_prefill_model()
            if not self.model_id:
                raise UserError(_('No installed model matches that keyword. Select a Model instead.'))

        catalog = self._ai_build_catalog()
        if not catalog:
            raise UserError(_('No usable fields found on the selected model.'))

        suggested_name = self.name or (self.model_id.name if self.model_id else _('AI Dashboard'))
        items_data = []
        used_heuristic = False
        try:
            system_prompt = self._ai_build_system_prompt(catalog)
            content = self.env['dynamic.dashboard.item']._ai_chat(system_prompt, self._ai_user_intent())
            payload = self._ai_extract_json(content)
            suggested_name, items_data = self._ai_normalize_items_payload(payload)
        except UserError as e:
            # If API key / model missing → still offer smart local suggestions
            msg = str(e).lower()
            if 'api key' in msg or 'gemini' in msg or 'openai' in msg or 'provider' in msg:
                used_heuristic = True
                items_data = self._ai_heuristic_items(catalog)
            else:
                raise
        except Exception as e:
            _logger.exception('AI suggestion failed; falling back to heuristic')
            used_heuristic = True
            items_data = self._ai_heuristic_items(catalog)
            if not items_data:
                raise UserError(_('AI generation failed: %s') % e) from e

        # Force primary model onto suggestions when missing
        primary = self.model_id.model if self.model_id else catalog[0]['model']
        line_cmds = [(5, 0, 0)]
        seq = 10
        for spec in items_data:
            if not isinstance(spec, dict):
                continue
            vals = self._ai_line_vals_from_spec(spec, primary, seq)
            if not vals:
                continue
            line_cmds.append((0, 0, vals))
            seq += 10

        if len(line_cmds) == 1:
            raise UserError(_('No suggestions were produced. Try another model or keyword.'))

        self.write({
            'state': 'preview',
            'suggested_name': suggested_name,
            'line_ids': line_cmds,
        })
        action = self._reopen()
        if used_heuristic:
            action['context'] = dict(action.get('context') or {}, dd_ai_heuristic=True)
        return action

    def action_save_selected(self):
        """Step 2 → create dashboard/items from checked suggestions."""
        self.ensure_one()
        selected = self.line_ids.filtered('selected')
        if not selected:
            raise UserError(_('Select at least one suggested item to add.'))

        if self.generation_mode == 'create_dashboard':
            dashboard = self.env['dynamic.dashboard'].create({
                'name': self.name or self.suggested_name or _('AI Generated Dashboard'),
                'category_id': self.env['dynamic.dashboard.category'].get_or_create(_('AI')).id,
                'default_date_filter': 'this_year',
                'background_color': '#f4f7fe',
            })
        else:
            dashboard = self.dashboard_id
            if not dashboard:
                raise UserError(_('Select a Target Dashboard.'))

        created = self.env['dynamic.dashboard.item']
        placed = []
        # Continue layout below existing items when adding
        if self.generation_mode == 'add_items' and dashboard.item_ids:
            max_h = max(
                (i.grid_y + i.grid_h for i in dashboard.item_ids),
                default=0,
            )
            placed.append((0, 0, 12, max_h))  # Block the entire top area so new items start below

        for index, line in enumerate(selected):
            item = self._ai_create_item_from_line(dashboard, line, index, placed)
            if item:
                created |= item

        if not created:
            raise UserError(_('Selected suggestions could not be created. Check model fields.'))

        return {
            'type': 'ir.actions.client',
            'tag': 'dynamic_dashboard_ai_nexgen.dashboard_view',
            'name': dashboard.name,
            'context': {
                'default_dashboard_id': dashboard.id,
                'dd_ai_created_count': len(created),
            },
        }

    # Backwards-compatible entry (old button name)
    def generate_dashboard(self):
        return self.action_generate_suggestions()
