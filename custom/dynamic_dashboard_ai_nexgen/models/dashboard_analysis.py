# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval
from .constraints_utils import assert_domain, assert_json_object


class DynamicDashboardAnalysis(models.Model):
    _name = 'dynamic.dashboard.analysis'
    _description = 'Reusable Dashboard Analysis'
    _order = 'name, id'
    _check_company_auto = True

    _sql_row_limit_positive = models.Constraint(
        'CHECK(sql_row_limit IS NULL OR sql_row_limit >= 0)',
        'SQL row limit cannot be negative.',
    )

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company, index=True,
    )
    visual_type = fields.Selection([
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
        ('pictorial', 'Pictorial'),
        ('bullet', 'Bullet'),
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
        ('map', 'Map'),
        ('mapPoints', 'Map Points'),
        ('heatmap', 'Matrix Heat Map'),
        ('matrixHeatmap', 'Matrix Heat Map'),
        ('wordCloud', 'Word Cloud'),
        ('venn', 'Venn'),
        ('candlestick', 'Candlestick'),
        ('ohlc', 'OHLC'),
        ('timeline', 'Timeline'),
        ('serpentine', 'Serpentine'),
        ('spiral', 'Spiral'),
        ('list', 'Table / List'),
        ('iframe', 'Iframe'),
        ('odoo_view', 'Odoo View'),
    ], string='Default Visual', default='bar', required=True)

    source_type = fields.Selection([
        ('model', 'Odoo Model'),
        ('sql', 'SQL Query'),
        ('api', 'API'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
        ('mart', 'Data Mart'),
        ('scrape', 'Web Scrape'),
        ('sheets', 'Google Sheets'),
    ], string='Source Type', default='model', required=True)

    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        ondelete='cascade',
        domain="[('transient', '=', False)]",
    )
    model_name = fields.Char(string='Model Technical Name', related='model_id.model', readonly=True)
    domain = fields.Char(default='[]')
    date_filter_field_id = fields.Many2one(
        'ir.model.fields',
        string='Date Field',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'in', ['date', 'datetime'])]",
        ondelete='cascade',
    )
    external_connection_id = fields.Many2one(
        'dynamic.dashboard.connection', string='Connection', check_company=True,
    )
    query = fields.Text(string='SQL Query')
    sql_row_limit = fields.Integer(default=5000)
    mart_id = fields.Many2one(
        'dynamic.dashboard.mart', string='Data Mart', check_company=True,
    )
    api_endpoint = fields.Char()
    scrape_url = fields.Char(string='Scrape URL')
    scrape_json_path = fields.Char(string='JSON Path', help="Dot path to list in JSON response")
    sheets_id = fields.Char(string='Google Sheet ID')
    sheets_range = fields.Char(string='Sheet Range', default='A:Z')
    upload_file = fields.Binary(attachment=True)
    upload_filename = fields.Char()
    visual_config = fields.Text(
        string='Visual Config JSON',
        default='{}',
        help='legend_position, pie_radius, axis_max, scrollbar, show_values, label_bullet, column_min_width, grand_total',
    )
    iframe_url = fields.Char(string='Iframe URL')
    odoo_action_id = fields.Many2one('ir.actions.act_window', string='Odoo Window Action')

    metric_ids = fields.One2many('dynamic.dashboard.analysis.metric', 'analysis_id', string='Metrics', copy=True)
    dimension_ids = fields.One2many('dynamic.dashboard.analysis.dimension', 'analysis_id', string='Dimensions', copy=True)
    filter_ids = fields.One2many('dynamic.dashboard.analysis.filter', 'analysis_id', string='Filters', copy=True)
    item_ids = fields.One2many('dynamic.dashboard.item', 'analysis_id', string='Used On Items')

    @api.constrains('domain', 'visual_config')
    def _check_json_and_domain(self):
        for analysis in self:
            assert_domain(analysis.domain, _('Domain'))
            assert_json_object(analysis.visual_config, _('Visual Config JSON'))

    @api.constrains(
        'source_type', 'model_id', 'query', 'mart_id', 'external_connection_id',
        'iframe_url', 'odoo_action_id', 'visual_type',
    )
    def _check_source_config(self):
        for analysis in self:
            st = analysis.source_type
            if st == 'model' and not analysis.model_id:
                raise ValidationError(
                    _('Model is required for model-based analyses (%s).') % analysis.display_name
                )
            if st == 'sql' and not (analysis.query or '').strip():
                raise ValidationError(
                    _('SQL Query is required for SQL analyses (%s).') % analysis.display_name
                )
            if st == 'mart' and not analysis.mart_id:
                raise ValidationError(
                    _('Data Mart is required for mart analyses (%s).') % analysis.display_name
                )
            if st in ('api', 'sheets') and not analysis.external_connection_id:
                raise ValidationError(
                    _('Connection is required for %s analyses (%s).')
                    % (st, analysis.display_name)
                )
            if analysis.visual_type == 'iframe' and not (analysis.iframe_url or '').strip():
                raise ValidationError(
                    _('Iframe URL is required for iframe visuals (%s).') % analysis.display_name
                )
            if analysis.visual_type == 'odoo_view' and not analysis.odoo_action_id:
                raise ValidationError(
                    _('Odoo Window Action is required for Odoo View visuals (%s).')
                    % analysis.display_name
                )

    def action_open_editor(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'dynamic_dashboard_ai_nexgen.analysis_editor',
            'name': _('Analysis Editor'),
            'context': {'default_analysis_id': self.id},
        }

    @api.model
    def get_field_catalog(self, analysis_id):
        analysis = self.browse(analysis_id)
        if not analysis.exists() or not analysis.model_id:
            return []
        fields_recs = self.env['ir.model.fields'].search([
            ('model_id', '=', analysis.model_id.id),
            ('store', '=', True),
            ('ttype', 'not in', ['binary', 'html']),
        ], order='field_description')
        result = []
        for f in fields_recs:
            result.append({
                'id': f.id,
                'name': f.name,
                'label': f.field_description or f.name,
                'ttype': f.ttype,
                'is_metric': f.ttype in ('integer', 'float', 'monetary'),
                'is_dimension': f.ttype in (
                    'char', 'text', 'selection', 'many2one', 'boolean', 'date', 'datetime',
                ),
            })
        return result

    def get_visual_config_dict(self):
        self.ensure_one()
        try:
            return json.loads(self.visual_config or '{}')
        except Exception:
            return {}

    def fetch_analysis_data(self, **kwargs):
        self.ensure_one()
        visual = kwargs.get('visual_type') or self.visual_type
        result = {
            'id': self.id,
            'name': self.name,
            'type': visual,
            'item_type': visual,
            'theme': 'default',
            'visual_config': self.get_visual_config_dict(),
            'analysis_id': self.id,
        }
        if visual == 'iframe':
            result['iframe_url'] = self.iframe_url or ''
            return result
        if visual == 'odoo_view':
            result['odoo_action_id'] = self.odoo_action_id.id if self.odoo_action_id else False
            result['odoo_action_xml'] = self.odoo_action_id.xml_id if self.odoo_action_id else False
            return result

        if self.source_type == 'model':
            return self._fetch_from_model(result, visual, **kwargs)
        if self.source_type == 'sql':
            return self._fetch_from_sql(result, visual, **kwargs)
        if self.source_type == 'mart' and self.mart_id:
            return self.mart_id.fetch_as_analysis(result, visual, **kwargs)
        if self.source_type in ('excel', 'csv'):
            result['error'] = _('File source on Analysis: attach file on a dashboard item or use mart ETL.')
            return result
        if self.source_type == 'scrape':
            return self._fetch_from_scrape(result, visual)
        if self.source_type == 'sheets':
            return self._fetch_from_sheets(result, visual)
        if self.source_type == 'api':
            result['error'] = _('Use an External Connection on a dashboard item for API, or configure scrape/sheets.')
            return result
        result['error'] = _('Unsupported analysis source.')
        return result

    def _build_domain(self, **kwargs):
        domain = list(safe_eval(self.domain or '[]'))
        for af in self.filter_ids:
            if af.field_id and af.value:
                domain.append((af.field_id.name, af.operator or '=', af.value))
        extra = kwargs.get('extra_domain') or []
        if isinstance(extra, list):
            domain.extend([tuple(x) if isinstance(x, list) else x for x in extra if x])
        custom_filters = kwargs.get('custom_filter_domains', [])
        for cf in custom_filters:
            try:
                domain.extend(safe_eval(cf))
            except Exception:
                pass
        date_filter = kwargs.get('global_date_filter', 'none')
        if self.date_filter_field_id and date_filter and date_filter != 'none':
            Item = self.env['dynamic.dashboard.item']
            today = fields.Date.context_today(self)
            start_date, end_date, _, _ = Item._resolve_date_range(date_filter, today=today, item=None)
            if start_date and end_date:
                fname = self.date_filter_field_id.name
                domain += [(fname, '>=', start_date), (fname, '<=', end_date)]
        return domain

    def _fetch_from_model(self, result, visual, **kwargs):
        if not self.model_id:
            result['error'] = _('Model is required.')
            return result
        Model = self.env['dynamic.dashboard.item']._dd_scoped_model(self.model_id.model)
        domain = self._build_domain(**kwargs)
        metrics = self.metric_ids.sorted('sequence')
        dimensions = self.dimension_ids.sorted('sequence')

        if visual in ('tile', 'kpi', 'scorecard'):
            values = []
            for m in metrics:
                agg = m.aggregation or 'sum'
                if agg == 'count' or not m.field_id:
                    val = Model.search_count(domain)
                    label = m.name or _('Count')
                else:
                    fname = m.field_id.name
                    orm_agg = 'avg' if agg == 'average' else agg
                    grouped = Model.read_group(domain, [f'{fname}:{orm_agg}'], [])
                    val = grouped[0].get(fname) if grouped else 0
                    label = m.name or m.field_id.field_description
                values.append({'label': label, 'value': val or 0})
            if not values:
                values = [{'label': self.name, 'value': Model.search_count(domain)}]
            result.update({
                'value': values[0]['value'],
                'scorecard_values': values,
                'color': '#FFFFFF',
                'icon': 'fa-bar-chart',
            })
            return result

        if visual == 'list' or not dimensions:
            # Table: read fields from dimensions + metrics
            field_names = []
            columns = []
            for d in dimensions:
                if d.field_id:
                    field_names.append(d.field_id.name)
                    columns.append(d.name or d.field_id.field_description)
            for m in metrics:
                if m.field_id and m.field_id.name not in field_names:
                    field_names.append(m.field_id.name)
                    columns.append(m.name or m.field_id.field_description)
            if not field_names:
                field_names = ['display_name']
                columns = ['Name']
            recs = Model.search_read(domain, field_names + ['id'], limit=500)
            result.update({
                'list_view_type': 'list',
                'list_view_layout': 'layout1',
                'columns': columns,
                'column_keys': field_names,
                'records': recs,
                'list_total': len(recs),
                'grand_total': self._compute_grand_total(recs, field_names, metrics),
            })
            return result

        # Chart: first dimension + metrics via read_group
        dim = dimensions[0]
        groupby = dim.field_id.name
        date_grain = dim.date_grain
        if dim.field_id.ttype in ('date', 'datetime') and date_grain:
            groupby = f'{dim.field_id.name}:{date_grain}'

        fields_list = []
        for m in metrics:
            if not m.field_id or m.aggregation == 'count':
                continue
            agg = 'avg' if m.aggregation == 'average' else (m.aggregation or 'sum')
            fields_list.append(f'{m.field_id.name}:{agg}')
        if not fields_list:
            fields_list = ['__count']

        order = False
        if metrics and metrics[0].sort_order:
            m0 = metrics[0]
            if m0.field_id:
                order = f'{m0.field_id.name} {m0.sort_order}'
            else:
                order = f'__count {m0.sort_order}'

        grouped = Model.read_group(domain, fields_list, [groupby], orderby=order or None, lazy=False)
        labels = []
        datasets = []
        metric_keys = []
        for m in metrics:
            if m.aggregation == 'count' or not m.field_id:
                metric_keys.append(('__count', m.name or _('Count')))
            else:
                metric_keys.append((m.field_id.name, m.name or m.field_id.field_description))
        if not metric_keys:
            metric_keys = [('__count', _('Count'))]

        series_data = {key: [] for key, _ in metric_keys}
        for row in grouped:
            lab = row.get(groupby)
            if isinstance(lab, (list, tuple)):
                lab = lab[1]
            labels.append(str(lab if lab is not None else ''))
            for key, _lbl in metric_keys:
                series_data[key].append(row.get(key) or 0)

        for key, lbl in metric_keys:
            datasets.append({'label': lbl, 'data': series_data[key]})

        result.update({
            'labels': labels,
            'datasets': datasets,
            'is_stacked': False,
            'show_data_value': True,
        })
        return result

    def _compute_grand_total(self, records, field_names, metrics):
        totals = {}
        metric_names = {m.field_id.name for m in metrics if m.field_id}
        for fname in field_names:
            if fname not in metric_names and fname not in ('amount_total', 'amount_untaxed', 'price_subtotal'):
                continue
            s = 0.0
            for r in records:
                v = r.get(fname) or 0
                if isinstance(v, (int, float)):
                    s += v
            totals[fname] = s
        return totals

    def _fetch_from_sql(self, result, visual, **kwargs):
        Item = self.env['dynamic.dashboard.item']
        # Temporary helper using item SQL helpers via a new recordset pattern
        helper = Item.new({
            'query': self.query,
            'sql_row_limit': self.sql_row_limit or 5000,
            'data_calculation_type': 'sql',
            'external_connection_id': self.external_connection_id.id,
            'item_type': visual if visual != 'scorecard' else 'tile',
            'date_filter_selection': 'none',
        })
        try:
            prepared, limit, params = helper._prepare_sql_query(self.query or '', kwargs)
            rows = helper._execute_sql_query(prepared, self.external_connection_id, params=params) or []
            if len(rows) > limit:
                rows = rows[:limit]
        except Exception as e:
            result['error'] = str(e)
            return result
        if not rows:
            result.update({'labels': [], 'datasets': [], 'columns': [], 'records': []})
            return result
        keys = list(rows[0].keys())
        if visual == 'list':
            result.update({
                'list_view_type': 'list',
                'list_view_layout': 'layout1',
                'columns': keys,
                'column_keys': keys,
                'records': rows,
            })
            return result
        if visual in ('tile', 'kpi', 'scorecard'):
            val = list(rows[0].values())[0] if rows else 0
            result.update({'value': val, 'scorecard_values': [{'label': keys[0], 'value': val}]})
            return result
        label_key = keys[0]
        measure_keys = keys[1:] or [keys[0]]
        result.update({
            'labels': [str(r.get(label_key, '')) for r in rows],
            'datasets': [{'label': mk, 'data': [r.get(mk, 0) for r in rows]} for mk in measure_keys],
        })
        return result

    def _scrape_to_float(self, value):
        if isinstance(value, bool):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if value is None:
            return None
        text = str(value).strip().replace(',', '')
        if not text:
            return None
        try:
            return float(text)
        except Exception:
            return None

    def _scrape_pick_keys(self, sample_row, label_key=None, value_key=None):
        """Choose label/value keys from a JSON object row."""
        if not isinstance(sample_row, dict) or not sample_row:
            return 'label', 'value'
        keys = list(sample_row.keys())
        label_key = (label_key or '').strip() or None
        value_key = (value_key or '').strip() or None

        label_prefs = ('title', 'name', 'label', 'category', 'product', 'sku', 'code')
        value_prefs = ('price', 'value', 'amount', 'total', 'qty', 'quantity', 'count', 'score', 'rating')

        if label_key and label_key not in sample_row:
            label_key = None
        if value_key and value_key not in sample_row:
            value_key = None

        if not label_key:
            for pref in label_prefs:
                for k in keys:
                    if k.lower() == pref:
                        label_key = k
                        break
                if label_key:
                    break
        if not value_key:
            for pref in value_prefs:
                for k in keys:
                    if k.lower() == pref:
                        value_key = k
                        break
                if value_key:
                    break

        # Prefer first non-numeric-looking key as label, first numeric as value
        if not value_key:
            for k in keys:
                if self._scrape_to_float(sample_row.get(k)) is not None and k != label_key:
                    value_key = k
                    break
        if not label_key:
            for k in keys:
                if k == value_key:
                    continue
                if self._scrape_to_float(sample_row.get(k)) is None:
                    label_key = k
                    break
        if not label_key:
            label_key = keys[0]
        if not value_key:
            value_key = keys[1] if len(keys) > 1 else keys[0]
        return label_key, value_key

    def _scrape_demo_products(self):
        """Offline sample when the remote scrape URL is unreachable."""
        return [
            {'title': 'Essence Mascara', 'price': 9.99},
            {'title': 'Eyeshadow Palette', 'price': 19.99},
            {'title': 'Powder Canister', 'price': 14.99},
            {'title': 'Red Lipstick', 'price': 12.49},
            {'title': 'Nail Polish', 'price': 8.99},
            {'title': 'Perfume Oil', 'price': 29.99},
            {'title': 'Skin Beauty Serum', 'price': 24.5},
            {'title': 'Tree Oil', 'price': 11.0},
        ]

    def _fetch_from_scrape(self, result, visual):
        import requests
        if not self.scrape_url:
            result['error'] = _('Scrape URL is required.')
            return result

        allow_demo = self.env.context.get('dd_scrape_allow_demo', True)
        label_key = self.env.context.get('dd_scrape_label_key')
        value_key = self.env.context.get('dd_scrape_value_key')
        rows = None
        warning = False

        try:
            resp = requests.get(
                self.scrape_url,
                timeout=20,
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; DynamicDashboard/1.0)',
                    'Accept': 'application/json, text/plain, */*',
                },
            )
            resp.raise_for_status()
            data = resp.json()
            path = (self.scrape_json_path or '').strip()
            if path:
                cursor = data
                for part in path.split('.'):
                    if not part:
                        continue
                    if isinstance(cursor, dict) and part in cursor:
                        cursor = cursor[part]
                    elif isinstance(cursor, list) and part.isdigit() and int(part) < len(cursor):
                        cursor = cursor[int(part)]
                    else:
                        raise KeyError(part)
                data = cursor
            if isinstance(data, dict):
                # Common envelopes: {data: [...]}, {items: [...]}, {results: [...]}
                for envelope in ('products', 'data', 'items', 'results', 'records', 'rows'):
                    if isinstance(data.get(envelope), list):
                        data = data[envelope]
                        break
            if not isinstance(data, list):
                data = [data]
            rows = [r for r in data if isinstance(r, dict)]
            if not rows and data:
                # Scalar list → synthesize rows
                rows = [{'label': str(i), 'value': self._scrape_to_float(v) or 0} for i, v in enumerate(data)]
        except Exception as e:
            if allow_demo:
                rows = self._scrape_demo_products()
                warning = _(
                    'Scrape unavailable (%s). Showing sample product data. '
                    'Check URL / JSON path / server outbound HTTPS.'
                ) % e
            else:
                result['error'] = _('Scrape failed: %s') % e
                return result

        if not rows:
            if allow_demo:
                rows = self._scrape_demo_products()
                warning = _('Scrape returned no rows. Showing sample product data.')
            else:
                result.update({'labels': [], 'datasets': [], 'columns': [], 'records': []})
                return result

        label_key, value_key = self._scrape_pick_keys(rows[0], label_key, value_key)

        if visual == 'list':
            # Prefer a compact column set for list views
            preferred = [label_key, value_key] + [
                k for k in rows[0].keys() if k not in (label_key, value_key)
            ]
            keys = []
            for k in preferred:
                if k and k not in keys:
                    keys.append(k)
            result.update({
                'columns': keys,
                'column_keys': keys,
                'records': rows,
                'list_view_layout': 'layout1',
            })
        else:
            labels, values = [], []
            for row in rows:
                labels.append(str(row.get(label_key, '') or ''))
                num = self._scrape_to_float(row.get(value_key))
                values.append(0.0 if num is None else num)
            # Drop empty labels / all-zero-only noise only if nothing usable
            if labels and all(v == 0 for v in values):
                # Retry: pick another numeric column
                for k in rows[0].keys():
                    if k == label_key:
                        continue
                    trial = [self._scrape_to_float(r.get(k)) for r in rows]
                    if any(v is not None and v != 0 for v in trial):
                        value_key = k
                        values = [0.0 if v is None else v for v in trial]
                        break
            result.update({
                'labels': labels,
                'datasets': [{'label': value_key or self.name or 'Value', 'data': values}],
                'scrape_label_key': label_key,
                'scrape_value_key': value_key,
            })

        if warning:
            result['warning'] = warning
        return result

    def _is_placeholder_sheets_api_key(self, api_key):
        """True when the key is missing/demo and must not be sent to Google."""
        key = (api_key or '').strip()
        if not key:
            return True
        upper = key.upper()
        markers = (
            'DEMO_', 'REPLACE_WITH', 'YOUR_API', 'YOUR_GOOGLE', 'CHANGEME',
            'XXX', 'TODO', 'PLACEHOLDER', 'EXAMPLE',
        )
        return any(m in upper for m in markers)

    def _sheets_demo_table(self):
        """Offline sample matching Google's public Class Data sheet (for demos)."""
        return [
            ['Student Name', 'Gender', 'Class Level', 'Home State', 'Major', 'Extracurricular Activity'],
            ['Alexandra', 'Female', '4. Senior', 'CA', 'English', 'Drama Club'],
            ['Andrew', 'Male', '1. Freshman', 'SD', 'Math', 'Lacrosse'],
            ['Anna', 'Female', '1. Freshman', 'NC', 'English', 'Basketball'],
            ['Becky', 'Female', '2. Sophomore', 'SD', 'Art', 'Baseball'],
            ['Benjamin', 'Male', '4. Senior', 'WI', 'English', 'Basketball'],
            ['Carl', 'Male', '3. Junior', 'MD', 'Art', 'Debate'],
            ['Carrie', 'Female', '3. Junior', 'NE', 'English', 'Track & Field'],
            ['Dorothy', 'Female', '4. Senior', 'MD', 'Math', 'Lacrosse'],
            ['Dylan', 'Male', '1. Freshman', 'CA', 'Math', 'Baseball'],
            ['Edward', 'Male', '3. Junior', 'FL', 'English', 'Drama Club'],
        ]

    def _sheets_table_to_result(self, values, result, visual, demo=False):
        """Map a 2D sheet table (header + rows) into chart/list payload."""
        if not values:
            result.update({'labels': [], 'datasets': [], 'columns': [], 'records': []})
            if demo:
                result['warning'] = _(
                    'Demo Sheets data (no live Google API key). '
                    'Set a real API key on the connection or in Settings.'
                )
            return result
        headers = [str(h) if h is not None else '' for h in values[0]]
        rows = []
        for raw in values[1:]:
            padded = list(raw) + [''] * (len(headers) - len(raw))
            rows.append(dict(zip(headers, padded)))
        if visual == 'list':
            result.update({
                'columns': headers,
                'column_keys': headers,
                'records': rows,
                'list_view_layout': 'layout1',
            })
        else:
            label_key = headers[0] if headers else 'Label'
            labels = [str(r.get(label_key, '')) for r in rows]

            def _num(val):
                if isinstance(val, (int, float)):
                    return float(val)
                s = str(val or '').replace(',', '').strip()
                try:
                    return float(s)
                except Exception:
                    return 0.0

            datasets = []
            for h in headers[1:]:
                nums = [_num(r.get(h)) for r in rows]
                # Prefer numeric-looking columns; still include if any value parsed
                if any(n != 0 for n in nums) or all(
                    str(r.get(h) or '').replace(',', '').replace('.', '', 1).replace('-', '', 1).isdigit()
                    for r in rows if r.get(h) not in (None, '')
                ):
                    datasets.append({'label': h, 'data': nums})
            # Class Data sample has mostly text columns — aggregate counts by Major (col 5) or Class Level
            if not datasets and labels:
                from collections import Counter
                # Prefer a categorical column with few unique values
                cat_idx = None
                for candidate in ('Major', 'Class Level', 'Home State', 'Gender'):
                    if candidate in headers:
                        cat_idx = candidate
                        break
                if cat_idx:
                    counts = Counter(str(r.get(cat_idx, '') or 'Unknown') for r in rows)
                    labels = list(counts.keys())
                    datasets = [{'label': cat_idx, 'data': [counts[k] for k in labels]}]
                else:
                    datasets = [{'label': 'count', 'data': [1] * len(labels)}]
            result.update({
                'labels': labels,
                'datasets': datasets or [{'label': 'count', 'data': [1] * len(labels)}],
            })
        if demo:
            result['warning'] = _(
                'Showing sample Sheets data — replace the demo Google API key on the '
                'connection (or Dynamic Dashboard settings) to load live spreadsheet values.'
            )
            result['is_demo_sheets'] = True
        return result

    def _fetch_from_sheets(self, result, visual):
        import requests
        from urllib.parse import quote

        api_key = (
            self.env.context.get('dd_sheets_api_key')
            or self.env['ir.config_parameter'].sudo().get_param('dynamic_dashboard_ai_nexgen.google_sheets_api_key')
        )
        allow_demo = self.env.context.get('dd_sheets_allow_demo', True)
        if not self.sheets_id:
            result['error'] = _('Google Sheet ID is required.')
            return result
        if self._is_placeholder_sheets_api_key(api_key):
            if allow_demo:
                return self._sheets_table_to_result(self._sheets_demo_table(), result, visual, demo=True)
            result['error'] = _(
                'Configure a real Google Sheets API key on the External Connection '
                'or in Settings → Dynamic Dashboard.'
            )
            return result

        rng = (self.sheets_range or 'A:Z').strip()
        # Encode sheet name / range for the URL path (spaces, !, etc.)
        encoded_id = quote(str(self.sheets_id).strip(), safe='')
        encoded_range = quote(rng, safe='')
        url = (
            f'https://sheets.googleapis.com/v4/spreadsheets/{encoded_id}/values/{encoded_range}'
            f'?key={api_key}'
        )
        try:
            resp = requests.get(url, timeout=20)
            if resp.status_code >= 400:
                # Never echo the API key back to the UI
                body = ''
                try:
                    body = (resp.json() or {}).get('error', {}).get('message') or ''
                except Exception:
                    body = ''
                hint = body or resp.reason or _('Bad Request')
                result['error'] = _(
                    'Google Sheets HTTP %(code)s: %(hint)s. '
                    'Check API key, Sheet ID, range, and that the Sheets API is enabled.'
                ) % {'code': resp.status_code, 'hint': hint}
                if allow_demo:
                    # Keep dashboard layout usable while config is incomplete
                    self._sheets_table_to_result(self._sheets_demo_table(), result, visual, demo=True)
                    result.pop('error', None)
                return result
            values = resp.json().get('values') or []
            return self._sheets_table_to_result(values, result, visual, demo=False)
        except Exception as e:
            msg = str(e)
            # Strip query string / key if present in exception text
            if 'key=' in msg:
                msg = msg.split('?')[0] + '?key=***'
            if allow_demo:
                self._sheets_table_to_result(self._sheets_demo_table(), result, visual, demo=True)
                result['warning'] = _('Google Sheets unavailable (%s). Showing sample data.') % msg
            else:
                result['error'] = _('Google Sheets error: %s') % msg
        return result

    def explain_with_ai(self):
        self.ensure_one()
        data = self.fetch_analysis_data()
        text = self.env['dynamic.dashboard.item']._ai_chat(
            system=(
                "You are a business analyst. Explain this dashboard analysis in 3-5 sentences "
                "and give 2 actionable recommendations. Do not invent numbers."
            ),
            user=json.dumps({
                'name': self.name,
                'labels': data.get('labels'),
                'datasets': data.get('datasets'),
                'value': data.get('value'),
            }, default=str)[:8000],
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('AI Explanation'),
                'message': text,
                'type': 'info',
                'sticky': True,
            },
        }

    @api.model
    def generate_from_keyword(self, prompt, model_name=None, dashboard_id=False):
        """Create an analysis (and optionally a dashboard item) from a natural-language keyword."""
        catalog_hint = model_name or 'res.partner'
        system = f"""
You generate one Odoo analysis config as JSON only:
{{
  "name": "...",
  "visual_type": "bar|line|pie|list|tile|kpi",
  "model": "{catalog_hint}",
  "metrics": [{{"field": "field_name_or_null", "aggregation": "sum|count|average", "name": "..."}}],
  "dimensions": [{{"field": "field_name", "date_grain": "month|day|year|false", "name": "..."}}]
}}
Use real Odoo field names for model {catalog_hint}. JSON only.
"""
        content = self.env['dynamic.dashboard.item']._ai_chat(system=system, user=prompt)
        if content.startswith('```'):
            content = content.strip('`')
            if content.startswith('json'):
                content = content[4:]
            content = content.strip()
        try:
            cfg = json.loads(content)
        except Exception as e:
            raise UserError(_('AI returned invalid JSON: %s') % e) from e

        model = self.env['ir.model'].search([('model', '=', cfg.get('model') or catalog_hint)], limit=1)
        if not model:
            raise UserError(_('Model not found: %s') % cfg.get('model'))

        analysis = self.create({
            'name': cfg.get('name') or prompt[:60],
            'visual_type': cfg.get('visual_type') or 'bar',
            'source_type': 'model',
            'model_id': model.id,
        })
        for i, m in enumerate(cfg.get('metrics') or []):
            field = False
            if m.get('field'):
                field = self.env['ir.model.fields'].search([
                    ('model_id', '=', model.id), ('name', '=', m['field'])
                ], limit=1)
            self.env['dynamic.dashboard.analysis.metric'].create({
                'analysis_id': analysis.id,
                'name': m.get('name') or (field.field_description if field else 'Count'),
                'field_id': field.id if field else False,
                'aggregation': m.get('aggregation') or 'count',
                'sequence': i * 10,
            })
        for i, d in enumerate(cfg.get('dimensions') or []):
            field = self.env['ir.model.fields'].search([
                ('model_id', '=', model.id), ('name', '=', d.get('field'))
            ], limit=1) if d.get('field') else False
            if not field:
                continue
            self.env['dynamic.dashboard.analysis.dimension'].create({
                'analysis_id': analysis.id,
                'name': d.get('name') or field.field_description,
                'field_id': field.id,
                'date_grain': d.get('date_grain') if d.get('date_grain') not in (False, 'false', None) else False,
                'sequence': i * 10,
            })
        item = False
        if dashboard_id:
            item = self.env['dynamic.dashboard.item'].create({
                'name': analysis.name,
                'dashboard_id': dashboard_id,
                'item_type': analysis.visual_type if analysis.visual_type in dict(
                    self.env['dynamic.dashboard.item']._fields['item_type'].selection
                ) else 'bar',
                'analysis_id': analysis.id,
                'data_calculation_type': 'custom',
            })
        return {'analysis_id': analysis.id, 'item_id': item.id if item else False}


class DynamicDashboardAnalysisMetric(models.Model):
    _name = 'dynamic.dashboard.analysis.metric'
    _description = 'Analysis Metric'
    _order = 'sequence, id'
    _check_company_auto = True

    analysis_id = fields.Many2one('dynamic.dashboard.analysis', required=True, ondelete='cascade', check_company=True)
    company_id = fields.Many2one(
        'res.company', related='analysis_id.company_id', store=True, index=True,
    )
    name = fields.Char()
    sequence = fields.Integer(default=10)
    field_id = fields.Many2one(
        'ir.model.fields',
        domain="[('model_id', '=', parent.model_id), ('store', '=', True), ('ttype', 'in', ['integer', 'float', 'monetary']), ('name', '!=', 'id')]",
        ondelete='cascade',
    )
    aggregation = fields.Selection([
        ('sum', 'Sum'),
        ('count', 'Count'),
        ('average', 'Average'),
        ('min', 'Min'),
        ('max', 'Max'),
    ], default='sum')
    sort_order = fields.Selection([('asc', 'Ascending'), ('desc', 'Descending')])
    format_type = fields.Selection([
        ('number', 'Number'),
        ('currency', 'Currency'),
        ('percent', 'Percent'),
    ], default='number')

    @api.constrains('aggregation', 'field_id')
    def _check_measure_field(self):
        for metric in self:
            if metric.aggregation in ('sum', 'average', 'min', 'max') and not metric.field_id:
                raise ValidationError(
                    _('A measure field is required for %(agg)s metrics (%(name)s).',
                      agg=metric.aggregation, name=metric.display_name)
                )


class DynamicDashboardAnalysisDimension(models.Model):
    _name = 'dynamic.dashboard.analysis.dimension'
    _description = 'Analysis Dimension'
    _order = 'sequence, id'
    _check_company_auto = True

    analysis_id = fields.Many2one('dynamic.dashboard.analysis', required=True, ondelete='cascade', check_company=True)
    company_id = fields.Many2one(
        'res.company', related='analysis_id.company_id', store=True, index=True,
    )
    name = fields.Char()
    sequence = fields.Integer(default=10)
    field_id = fields.Many2one(
        'ir.model.fields',
        required=True,
        domain="[('model_id', '=', parent.model_id), ('store', '=', True), ('ttype', 'not in', ['one2many', 'many2many', 'binary', 'html', 'json', 'properties'])]",
        ondelete='cascade',
    )
    date_grain = fields.Selection([
        ('day', 'Day'),
        ('week', 'Week'),
        ('month', 'Month'),
        ('quarter', 'Quarter'),
        ('year', 'Year'),
    ])
    sort_order = fields.Selection([('asc', 'Ascending'), ('desc', 'Descending')])
    format_type = fields.Char()


class DynamicDashboardAnalysisFilter(models.Model):
    _name = 'dynamic.dashboard.analysis.filter'
    _description = 'Analysis Default Filter'
    _order = 'sequence, id'
    _check_company_auto = True

    analysis_id = fields.Many2one('dynamic.dashboard.analysis', required=True, ondelete='cascade', check_company=True)
    company_id = fields.Many2one(
        'res.company', related='analysis_id.company_id', store=True, index=True,
    )
    name = fields.Char()
    sequence = fields.Integer(default=10)
    field_id = fields.Many2one(
        'ir.model.fields',
        domain="[('model_id', '=', parent.model_id), ('store', '=', True), ('ttype', 'not in', ['one2many', 'many2many', 'binary', 'html', 'json'])]",
        ondelete='cascade',
    )
    operator = fields.Selection([
        ('=', '='), ('!=', '!='), ('ilike', 'ilike'),
        ('>', '>'), ('>=', '>='), ('<', '<'), ('<=', '<='),
        ('in', 'in'),
    ], default='=')
    value = fields.Char(string='Default Value')
