# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
"""Demo dashboards grouped by Data Calculation Type (depends: base, web, mail, bus)."""
from __future__ import annotations

import base64
import csv
import io
import json
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


# All visual item types supported by the module.
ALL_ITEM_TYPES = [
    'tile', 'kpi', 'scorecard',
    'bar', 'barLine', 'horizontalBar', 'line', 'area', 'stepLine', 'smoothedLine',
    'waterfall', 'pie', 'doughnut', 'polarArea', 'radar', 'flower', 'scatter',
    'radialBar', 'gauge', 'funnel', 'pyramid', 'pictorial', 'bullet',
    'treemap', 'sunburst', 'forceDirected', 'pack', 'tree', 'partition', 'voronoiTreemap',
    'sankey', 'chord', 'chordDirected', 'chordNonRibbon', 'arcDiagram',
    'map', 'mapPoints', 'heatmap', 'matrixHeatmap',
    'wordCloud', 'venn', 'candlestick', 'ohlc', 'timeline', 'serpentine', 'spiral',
    'list', 'todo', 'iframe', 'odoo_view',
]

# Types that need special handling (no model / no SQL rows chart).
EMBED_TYPES = {'todo', 'iframe', 'odoo_view'}
CARD_TYPES = {'tile', 'kpi', 'scorecard'}


class DynamicDashboard(models.Model):
    _inherit = 'dynamic.dashboard'

    @api.model
    def seed_data_calculation_type_demos(self, force=False):
        """Create one dashboard per Data Calculation Type with rich items.

        Uses only depends models + this module:
        res.partner, res.users, res.country, ir.module.module, mail.message,
        dynamic.dashboard.demo.record
        """
        self = self.sudo()
        # Ensure demo operator can manage filters/items (ACL: manager write).
        manager = self.env.ref('dynamic_dashboard_ai_nexgen.group_dashboard_manager', raise_if_not_found=False)
        if manager and manager not in self.env.user.group_ids:
            self.env.user.sudo().write({'group_ids': [(4, manager.id)]})
        Category = self.env['dynamic.dashboard.category'].sudo()
        cat = Category.get_or_create('Data Sources Demo')
        num = self._dd_ds_ensure_number_system()
        date_filt = self._dd_ds_ensure_date_filter()
        api_conn = self._dd_ds_ensure_api_connection()
        sheets_conn = self._dd_ds_ensure_sheets_connection()

        builders = [
            ('Demo - Odoo Model (Custom)', 'custom', self._dd_ds_build_custom),
            ('Demo - Custom SQL (Visual Query Builder)', 'sql', self._dd_ds_build_sql),
            ('Demo - External API', 'api', self._dd_ds_build_api),
            ('Demo - Excel File', 'excel', self._dd_ds_build_excel),
            ('Demo - CSV File', 'csv', self._dd_ds_build_csv),
            ('Demo - Web Scrape', 'scrape', self._dd_ds_build_scrape),
            ('Demo - Google Sheets', 'sheets', self._dd_ds_build_sheets),
        ]

        created = self.browse()
        for seq, (name, calc, builder) in enumerate(builders, start=1):
            dash = self.search([('name', '=', name)], limit=1)
            if dash and force:
                dash.item_ids.unlink()
                dash.custom_filter_ids.unlink()
            if not dash:
                dash = self.create(self._dd_ds_dashboard_vals(
                    name=name, sequence=100 + seq, category=cat, num=num,
                    date_filt=date_filt, theme={
                        'custom': 'corporate', 'sql': 'ocean', 'api': 'cool',
                        'excel': 'warm', 'csv': 'pastel', 'scrape': 'vibrant',
                        'sheets': 'sunset',
                    }.get(calc, 'default'),
                ))
            else:
                write_vals = {
                    'category_id': cat.id,
                    'default_date_filter': 'this_year' if calc in ('custom', 'sql') else 'none',
                    'chart_theme': {
                        'custom': 'corporate', 'sql': 'ocean', 'api': 'cool',
                        'excel': 'warm', 'csv': 'pastel', 'scrape': 'vibrant',
                        'sheets': 'sunset',
                    }.get(calc, 'default'),
                    'present_notes': (
                        f'Demo dashboard for Data Calculation Type = {calc}. '
                        'Use global date filter and custom filters in the navbar.'
                    ),
                    'sticky_navbar': True,
                    'tv_interval': 12,
                    'tv_mode_type': 'item',
                    'background_color': '#F1F5F9',
                }
                if 'website_published' in self._fields:
                    write_vals['website_published'] = True
                dash.write(write_vals)
            if force or not dash.item_ids:
                builder(dash, api_conn=api_conn, sheets_conn=sheets_conn, num=num)
            self._dd_ds_ensure_global_filters(dash, calc)
            created |= dash
        return created

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @api.model
    def _dd_ds_dashboard_vals(self, name, sequence, category, num, date_filt, theme):
        # num / date_filt are created globally for the demo suite (items + date picker).
        _ = (num, date_filt)
        group_ids = []
        for xmlid in (
            'dynamic_dashboard_ai_nexgen.group_dashboard_user',
            'dynamic_dashboard_ai_nexgen.group_dashboard_manager',
            'base.group_user',
            'base.group_system',
        ):
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                group_ids.append(group.id)
        vals = {
            'name': name,
            'sequence': sequence,
            'active': True,
            'category_id': category.id,
            'chart_theme': theme,
            'default_date_filter': 'this_year' if 'SQL' in name or 'Odoo Model' in name else 'none',
            'sticky_navbar': True,
            'tv_interval': 12,
            'tv_mode_type': 'item',
            'tv_hide_chrome': True,
            'background_color': '#F1F5F9',
            'layout_direction': 'ltr',
            'is_rtl': False,
            'present_notes': (
                f'Presenter notes for {name}. Walk through tiles first, then charts, '
                'then lists. Toggle global filters to show interactive filtering.'
            ),
            'email_user_ids': [(6, 0, [self.env.user.id])],
            'group_ids': [(6, 0, group_ids or self.env.user.group_ids.ids)],
            'menu_name': name.replace('Demo - ', ''),
            'gridstack_config': '{}',
        }
        # dynamic_dashboard_ai_website record rule requires website_published for filters
        if 'website_published' in self._fields:
            vals['website_published'] = True
        return vals

    @api.model
    def _dd_ds_ensure_number_system(self):
        NS = self.env['dynamic.dashboard.number.system'].sudo()
        ns = NS.search([('name', '=', 'Demo Compact')], limit=1)
        if ns:
            return ns
        ns = NS.create({'name': 'Demo Compact'})
        Line = self.env['dynamic.dashboard.number.system.line'].sudo()
        Line.create([
            {'system_id': ns.id, 'threshold': 1000, 'divisor': 1000, 'suffix': 'K'},
            {'system_id': ns.id, 'threshold': 1000000, 'divisor': 1000000, 'suffix': 'M'},
            {'system_id': ns.id, 'threshold': 1000000000, 'divisor': 1000000000, 'suffix': 'B'},
        ])
        return ns

    @api.model
    def _dd_ds_ensure_date_filter(self):
        DF = self.env['dynamic.dashboard.date.filter'].sudo()
        rec = DF.search([('name', '=', 'Demo Last 45 Days')], limit=1)
        if rec:
            return rec
        return DF.create({
            'name': 'Demo Last 45 Days',
            'sequence': 5,
            'offset_start': -45,
            'offset_end': 0,
        })

    @api.model
    def _dd_ds_ensure_api_connection(self):
        Conn = self.env['dynamic.dashboard.connection'].sudo()
        rec = Conn.search([('name', '=', 'Demo DummyJSON Products')], limit=1)
        if rec:
            return rec
        return Conn.create({
            'name': 'Demo DummyJSON Products',
            'connection_type': 'api',
            'api_endpoint': 'https://dummyjson.com/products?limit=15',
            'api_method': 'GET',
            'api_data_path': 'products',
        })

    @api.model
    def _dd_ds_ensure_sheets_connection(self):
        Conn = self.env['dynamic.dashboard.connection'].sudo()
        rec = Conn.search([('name', '=', 'Demo Google Sheets')], limit=1)
        if rec:
            return rec
        return Conn.create({
            'name': 'Demo Google Sheets',
            'connection_type': 'sheets',
            'sheets_api_key': 'AIzaSyDemoDummyKeyReplaceMe',
        })

    @api.model
    def _dd_ds_field(self, model_name, field_name):
        return self.env['ir.model.fields'].sudo().search([
            ('model', '=', model_name), ('name', '=', field_name),
        ], limit=1)

    @api.model
    def _dd_ds_model(self, model_name):
        return self.env['ir.model'].sudo().search([('model', '=', model_name)], limit=1)

    @api.model
    def _dd_ds_size_for_type(self, item_type):
        """Recommended GridStack size (w, h) on a 12-column board per item type."""
        sizes = {
            # Metric cards — compact KPI strip
            'tile': (3, 2),
            'kpi': (3, 2),
            'scorecard': (6, 3),
            # Compact radial / single-value charts
            'gauge': (3, 3),
            'radialBar': (3, 3),
            'bullet': (6, 3),
            # Round / polar family — square-ish
            'pie': (4, 4),
            'doughnut': (4, 4),
            'polarArea': (4, 4),
            'radar': (4, 4),
            'flower': (4, 4),
            'venn': (4, 4),
            'pictorial': (4, 4),
            'spiral': (4, 4),
            # Core XY charts — half width, readable height
            'bar': (6, 4),
            'barLine': (6, 4),
            'horizontalBar': (6, 4),
            'line': (6, 4),
            'area': (6, 4),
            'stepLine': (6, 4),
            'smoothedLine': (6, 4),
            'waterfall': (6, 4),
            'scatter': (6, 4),
            'candlestick': (6, 4),
            'ohlc': (6, 4),
            'wordCloud': (6, 4),
            # Tall funnel / pyramid
            'funnel': (4, 5),
            'pyramid': (4, 5),
            # Hierarchy / network — needs breathing room
            'treemap': (6, 5),
            'sunburst': (6, 5),
            'forceDirected': (6, 5),
            'pack': (6, 5),
            'tree': (6, 5),
            'partition': (6, 5),
            'voronoiTreemap': (6, 5),
            # Flow — wide
            'sankey': (12, 5),
            'chord': (6, 5),
            'chordDirected': (6, 5),
            'chordNonRibbon': (6, 5),
            'arcDiagram': (12, 4),
            # Maps / heat
            'map': (6, 5),
            'mapPoints': (6, 5),
            'heatmap': (6, 5),
            'matrixHeatmap': (6, 5),
            # Time / narrative
            'timeline': (12, 4),
            'serpentine': (12, 4),
            # Tables & embeds
            'list': (6, 5),
            'todo': (6, 4),
            'iframe': (6, 5),
            'odoo_view': (12, 6),
        }
        return sizes.get(item_type, (6, 4))

    @api.model
    def _dd_ds_layout_priority(self, item_type):
        """Lower = higher on the dashboard (hero metrics first)."""
        order = {
            'tile': 10, 'kpi': 20, 'scorecard': 30,
            'bar': 100, 'barLine': 110, 'horizontalBar': 120,
            'line': 130, 'area': 140, 'stepLine': 150, 'smoothedLine': 160,
            'waterfall': 170, 'pie': 180, 'doughnut': 190,
            'polarArea': 200, 'radar': 210, 'flower': 220,
            'gauge': 230, 'radialBar': 240, 'bullet': 250,
            'funnel': 260, 'pyramid': 270, 'pictorial': 280,
            'scatter': 290, 'candlestick': 300, 'ohlc': 310,
            'treemap': 400, 'sunburst': 410, 'pack': 420, 'tree': 430,
            'partition': 440, 'voronoiTreemap': 450, 'forceDirected': 460,
            'sankey': 500, 'chord': 510, 'chordDirected': 520,
            'chordNonRibbon': 530, 'arcDiagram': 540,
            'map': 600, 'mapPoints': 610, 'heatmap': 620, 'matrixHeatmap': 630,
            'wordCloud': 700, 'venn': 710, 'spiral': 720,
            'timeline': 730, 'serpentine': 740,
            'list': 800, 'todo': 900, 'iframe': 910, 'odoo_view': 920,
        }
        return order.get(item_type, 550)

    @api.model
    def _dd_ds_pack_specs(self, specs, cols=12):
        """Assign non-overlapping grid positions sized per item_type (skyline pack)."""
        ordered = sorted(
            specs,
            key=lambda s: (self._dd_ds_layout_priority(s.get('item_type')), s.get('name') or ''),
        )
        heights = [0] * cols
        packed = []
        for seq, spec in enumerate(ordered, start=1):
            w, h = self._dd_ds_size_for_type(spec.get('item_type'))
            w = max(1, min(int(w), cols))
            h = max(1, int(h))
            best_x, best_y = 0, max(heights) if heights else 0
            found = False
            for x in range(0, cols - w + 1):
                y = max(heights[x:x + w]) if w else 0
                if not found or y < best_y or (y == best_y and x < best_x):
                    best_x, best_y = x, y
                    found = True
            # Stretch into leftover stub columns so demo boards have no thin blank strips
            leftover = cols - (best_x + w)
            if 0 < leftover <= 5 and all(heights[x] <= best_y for x in range(best_x + w, cols)):
                w = cols - best_x
            for x in range(best_x, best_x + w):
                heights[x] = best_y + h
            spec = dict(spec)
            spec.update({
                'grid_x': best_x,
                'grid_y': best_y,
                'grid_w': w,
                'grid_h': h,
                'sequence': seq,
            })
            packed.append(spec)
        return packed

    @api.model
    def _dd_ds_clear_item_prefs(self, dash):
        """Drop per-user layout overrides so seeded grid_* is what My Dashboard shows."""
        Pref = self.env['dynamic.dashboard.user.preference'].sudo()
        Pref.search([
            ('dashboard_id', '=', dash.id),
            ('item_id', '!=', False),
        ]).unlink()

    @api.model
    def _dd_ds_grid(self, index, w=4, h=3, cols=12):
        """Legacy helper — prefer _dd_ds_pack_specs for new layouts."""
        per_row = max(1, cols // w)
        row = index // per_row
        col = index % per_row
        return {'grid_x': col * w, 'grid_y': row * h, 'grid_w': w, 'grid_h': h}

    @api.model
    def _dd_ds_create_items(self, dash, specs):
        self._dd_ds_clear_item_prefs(dash)
        specs = self._dd_ds_pack_specs(specs)
        Item = self.env['dynamic.dashboard.item'].sudo().with_context(
            dd_skip_auto_layout=True,
            dd_file_columns=['Category', 'Amount', 'Quantity', 'Region', 'Label', 'Value'],
            dd_sql_columns=['label', 'value', 'band', 'name', 'state', 'date_val'],
            dd_api_keys=[
                'title', 'price', 'name', 'label', 'category', 'amount', 'value',
                'Student Name', 'Home State', 'Class Level', 'Major',
            ],
        )
        created = Item.browse()
        for spec in specs:
            vals = {'dashboard_id': dash.id, 'domain': '[]'}
            vals.update({k: v for k, v in spec.items() if v is not False and v is not None})
            for m2m in ('measure_field_ids', 'measure_field_2_ids', 'list_view_field_ids'):
                if vals.get(m2m) is False:
                    vals.pop(m2m, None)
            try:
                created |= Item.create(vals)
            except Exception as exc:
                _logger.warning(
                    'Demo item skipped (%s / %s): %s',
                    spec.get('item_type'), spec.get('name'), exc,
                )
                continue
        # Persist a clean gridstack snapshot for the dashboard shell
        config = [
            {
                'id': item.id,
                'x': item.grid_x,
                'y': item.grid_y,
                'w': item.grid_w,
                'h': item.grid_h,
            }
            for item in created
        ]
        dash.sudo().write({'gridstack_config': json.dumps(config)})
        return created

    @api.model
    def _dd_ds_ensure_global_filters(self, dash, calc):
        Filter = self.env['dynamic.dashboard.filter'].sudo()
        if Filter.search_count([('dashboard_id', '=', dash.id)]):
            return
        partner = self._dd_ds_model('res.partner')
        if not partner:
            return
        is_company = self._dd_ds_field('res.partner', 'is_company')
        country = self._dd_ds_field('res.partner', 'country_id')
        active = self._dd_ds_field('res.partner', 'active')
        create_date = self._dd_ds_field('res.partner', 'create_date')
        filters = [
            {
                'name': 'Companies only',
                'dashboard_id': dash.id,
                'model_id': partner.id,
                'domain': "[('is_company', '=', True)]",
                'is_active': True,
                'is_linked': True,
                'widget_type': 'toggle',
                'sequence': 10,
                'filter_field_id': is_company.id if is_company else False,
            },
            {
                'name': 'Active partners',
                'dashboard_id': dash.id,
                'model_id': partner.id,
                'domain': "[('active', '=', True)]",
                'is_active': True,
                'is_linked': True,
                'widget_type': 'toggle',
                'sequence': 20,
                'filter_field_id': active.id if active else False,
            },
        ]
        if country:
            filters.append({
                'name': 'Country',
                'dashboard_id': dash.id,
                'model_id': partner.id,
                'domain': '[]',
                'is_active': True,
                'is_linked': True,
                'widget_type': 'many2one',
                'sequence': 30,
                'filter_field_id': country.id,
            })
        if create_date and calc in ('custom', 'sql'):
            filters.append({
                'name': 'Created on',
                'dashboard_id': dash.id,
                'model_id': partner.id,
                'domain': '[]',
                'is_active': True,
                'is_linked': True,
                'widget_type': 'date',
                'sequence': 40,
                'filter_field_id': create_date.id,
            })
        for fvals in filters:
            if not fvals.get('filter_field_id') and fvals['widget_type'] in ('selection', 'many2one', 'date'):
                fvals['widget_type'] = 'toggle'
            Filter.create({k: v for k, v in fvals.items() if v is not False})

    # ------------------------------------------------------------------
    # Complex Visual Query Builder payloads (SQL)
    # ------------------------------------------------------------------

    @api.model
    def _dd_ds_vqb_partner_by_country(self):
        """Complex partner × country aggregate with joins, having, order, limit, CTE."""
        data = {
            'baseModel': 'res.partner',
            'fields': [
                {'model': 'res.partner', 'name': 'country_id', 'alias': 'label', 'agg': '', 'func': ''},
                {'model': 'res.partner', 'name': 'id', 'alias': 'value', 'agg': 'COUNT', 'func': ''},
            ],
            'joins': [{
                'type': 'LEFT JOIN',
                'model': 'res.country',
                'alias': 'country',
                'conditions': [{
                    'leftModel': 'res.partner',
                    'leftField': 'country_id',
                    'operator': '=',
                    'rightField': 'id',
                    'connector': 'AND',
                }],
            }],
            'wheres': [
                {'model': 'res.partner', 'field': 'active', 'operator': '=', 'value': 'true',
                 'connector': '', 'valueType': 'value', 'cast': ''},
                {'model': 'res.partner', 'field': 'country_id', 'operator': 'IS NOT NULL', 'value': '',
                 'connector': 'AND', 'valueType': 'value', 'cast': ''},
            ],
            'groupBys': [{'model': 'res.partner', 'field': 'country_id', 'func': ''}],
            'havings': [
                {'model': 'res.partner', 'field': 'id', 'agg': 'COUNT', 'operator': '>', 'value': '0', 'connector': ''},
            ],
            'orderBys': [
                {'model': 'res.partner', 'field': 'id', 'agg': 'COUNT', 'direction': 'DESC', 'nulls': 'LAST'},
            ],
            'distinct': False,
            'limit': '20',
            'offset': '',
            'customExpressions': [
                {'expression': "CASE WHEN COUNT(res_partner.\"id\") > 5 THEN 'High' ELSE 'Low' END", 'alias': 'band'},
            ],
            'windowFuncs': [
                {
                    'func': 'RANK',
                    'alias': 'rk',
                    'partitionBy': [],
                    'orderBy': [{'model': 'res.partner', 'field': 'id', 'agg': 'COUNT', 'direction': 'DESC'}],
                },
            ],
            'ctes': [
                {
                    'name': 'active_partners',
                    'sql': 'SELECT id, country_id FROM res_partner WHERE active IS TRUE AND country_id IS NOT NULL',
                },
            ],
        }
        sql = (
            'WITH active_partners AS (\n'
            '    SELECT id, country_id FROM res_partner\n'
            '    WHERE active IS TRUE AND country_id IS NOT NULL\n'
            ')\n'
            'SELECT\n'
            '    res_partner."country_id" AS "label",\n'
            '    COUNT(res_partner."id") AS "value",\n'
            '    CASE WHEN COUNT(res_partner."id") > 5 THEN \'High\' ELSE \'Low\' END AS "band",\n'
            '    RANK() OVER (ORDER BY COUNT(res_partner."id") DESC) AS "rk"\n'
            'FROM res_partner AS res_partner\n'
            'LEFT JOIN res_country AS country ON res_partner."country_id" = country."id"\n'
            'WHERE res_partner."active" = true\n'
            'AND res_partner."country_id" IS NOT NULL\n'
            'GROUP BY res_partner."country_id"\n'
            'HAVING COUNT(res_partner."id") > 0\n'
            'ORDER BY COUNT(res_partner."id") DESC NULLS LAST\n'
            'LIMIT 20'
        )
        return data, sql

    @api.model
    def _dd_ds_vqb_modules_by_state(self):
        data = {
            'baseModel': 'ir.module.module',
            'fields': [
                {'model': 'ir.module.module', 'name': 'state', 'alias': 'label', 'agg': '', 'func': 'UPPER'},
                {'model': 'ir.module.module', 'name': 'id', 'alias': 'value', 'agg': 'COUNT', 'func': ''},
            ],
            'joins': [],
            'wheres': [
                {'model': 'ir.module.module', 'field': 'state', 'operator': 'IN',
                 'value': "('installed','uninstalled','to upgrade','to install')",
                 'connector': '', 'valueType': 'expression', 'cast': ''},
            ],
            'groupBys': [{'model': 'ir.module.module', 'field': 'state', 'func': 'UPPER'}],
            'havings': [],
            'orderBys': [
                {'model': 'ir.module.module', 'field': 'id', 'agg': 'COUNT', 'direction': 'DESC', 'nulls': ''},
            ],
            'distinct': False,
            'limit': '15',
            'offset': '',
            'customExpressions': [],
            'windowFuncs': [],
            'ctes': [],
        }
        sql = (
            'SELECT\n'
            '    UPPER(ir_module_module."state") AS "label",\n'
            '    COUNT(ir_module_module."id") AS "value"\n'
            'FROM ir_module_module AS ir_module_module\n'
            "WHERE ir_module_module.\"state\" IN ('installed','uninstalled','to upgrade','to install')\n"
            'GROUP BY UPPER(ir_module_module."state")\n'
            'ORDER BY COUNT(ir_module_module."id") DESC\n'
            'LIMIT 15'
        )
        return data, sql

    @api.model
    def _dd_ds_vqb_for_type(self, item_type, index):
        """Alternate between two complex VQB queries for variety across item types."""
        if item_type in CARD_TYPES or index % 2 == 0:
            return self._dd_ds_vqb_partner_by_country()
        return self._dd_ds_vqb_modules_by_state()

    # ------------------------------------------------------------------
    # Per calculation-type builders
    # ------------------------------------------------------------------

    @api.model
    def _dd_ds_build_custom(self, dash, **kwargs):
        """Odoo Model dashboard — rich coverage using demo.record + partner."""
        metric = self._dd_ds_model('dynamic.dashboard.demo.record')
        partner = self._dd_ds_model('res.partner')
        model = metric or partner
        model_name = model.model
        amount = self._dd_ds_field(model_name, 'amount') or self._dd_ds_field(model_name, 'credit')
        category = self._dd_ds_field(model_name, 'category') or self._dd_ds_field(model_name, 'company_type')
        region = self._dd_ds_field(model_name, 'region') or self._dd_ds_field(model_name, 'country_id')
        stage = self._dd_ds_field(model_name, 'stage') or self._dd_ds_field(model_name, 'is_company')
        date_f = self._dd_ds_field(model_name, 'metric_date') or self._dd_ds_field(model_name, 'create_date')
        name_f = self._dd_ds_field(model_name, 'name')
        country = self._dd_ds_field(model_name, 'country_id')

        chart_types = [t for t in ALL_ITEM_TYPES if t not in EMBED_TYPES]
        card_icons = {
            'tile': 'fa-tachometer', 'kpi': 'fa-line-chart', 'scorecard': 'fa-th-large',
        }
        specs = []
        for idx, itype in enumerate(chart_types):
            spec = {
                'name': f'{itype.title()}: {model_name}',
                'item_type': itype,
                'data_calculation_type': 'custom',
                'model_id': model.id,
                'data_type': 'sum' if amount and itype not in ('list',) else 'count',
                'chart_theme': ['corporate', 'ocean', 'cool', 'warm', 'pastel', 'vibrant'][idx % 6],
                'show_data_value': True,
                'show_records': True,
                'enable_drill_down': True,
                'precision_digits': 2,
                'background_color': '#FFFFFF',
                'font_color': '#0F172A',
                'tile_layout': f'layout{(idx % 8) + 1}',
                'tile_theme': ['ocean', 'forest', 'coral', 'midnight', 'amber', 'slate', 'mint', 'berry'][idx % 8],
                'tile_color': ['#2563EB', '#0EA5E9', '#059669', '#EA580C', '#7C3AED'][idx % 5],
                'tile_icon': card_icons.get(itype, 'fa-chart-bar'),
                'unit': '$' if amount else '',
                'unit_position': 'prefix',
                'record_limit': 40,
                'sort_order': 'desc',
                'date_filter_selection': 'this_year' if date_f else 'none',
                'date_filter_field_id': date_f.id if date_f else False,
                'compare_previous_period': bool(date_f and itype in CARD_TYPES),
                'legend_position': 'bottom',
                'hide_legend': False,
            }
            num = kwargs.get('num')
            if num:
                spec['number_system_id'] = num.id

            if amount and itype not in ('list', 'wordCloud'):
                spec['measure_field_ids'] = [(6, 0, [amount.id])]
            gb = category or region or stage or country
            if gb and itype not in CARD_TYPES | {'list'}:
                spec['group_by_field_id'] = gb.id
            if itype == 'list':
                fields_list = [f for f in (name_f, category, stage, amount, date_f) if f]
                spec.update({
                    'list_view_type': 'ungrouped',
                    'list_view_layout': 'layout1',
                    'list_show_grand_total': True,
                    'list_view_field_ids': [(6, 0, [f.id for f in fields_list])] if fields_list else False,
                    'sort_by_field_id': (date_f or name_f).id if (date_f or name_f) else False,
                })
            if itype in ('line', 'area', 'stepLine', 'smoothedLine', 'timeline') and date_f:
                spec['group_by_field_id'] = date_f.id
                spec['group_by_date_type'] = 'month'
                spec['fill_temporal'] = True
            if itype in ('map', 'mapPoints', 'heatmap') and country:
                spec['group_by_field_id'] = country.id
            if itype in CARD_TYPES:
                spec['enable_target'] = True
                spec['standard_target_value'] = 1000
                spec['target_view'] = 'number' if itype != 'kpi' else 'progress_bar'
            if itype == 'scorecard' and (category or region):
                spec['group_by_field_id'] = (category or region).id
                spec['scorecard_columns'] = '3'
            if itype == 'barLine' and amount:
                qty = self._dd_ds_field(model_name, 'quantity')
                if qty:
                    spec['measure_field_2_ids'] = [(6, 0, [qty.id])]
            specs.append(spec)

        # Embeds (placed last by layout priority)
        partner_action = self.env.ref('base.action_partner_form', raise_if_not_found=False)
        specs.append({
            'name': 'To-Do: Data Sources Checklist', 'item_type': 'todo',
            'data_calculation_type': 'custom',
        })
        specs.append({
            'name': 'Iframe: Odoo.com', 'item_type': 'iframe',
            'data_calculation_type': 'custom', 'iframe_url': 'https://www.odoo.com',
        })
        if partner_action:
            specs.append({
                'name': 'Odoo View: Partners', 'item_type': 'odoo_view',
                'data_calculation_type': 'custom', 'odoo_action_id': partner_action.id,
            })

        items = self._dd_ds_create_items(dash, specs)
        todo = items.filtered(lambda i: i.item_type == 'todo')[:1]
        if todo:
            Todo = self.env['dynamic.dashboard.todo'].sudo()
            Todo.search([('dashboard_item_id', '=', todo.id)]).unlink()
            Todo.create([
                {'dashboard_item_id': todo.id, 'name': 'Explore Odoo Model dashboard tiles', 'is_done': True},
                {'dashboard_item_id': todo.id, 'name': 'Toggle Companies-only global filter', 'is_done': False},
                {'dashboard_item_id': todo.id, 'name': 'Change global date to Last 30 Days', 'is_done': False},
                {'dashboard_item_id': todo.id, 'name': 'Open chart options on a bar chart', 'is_done': False},
            ])

    @api.model
    def _dd_ds_build_sql(self, dash, **kwargs):
        """Custom SQL + Visual Query Builder — one complex item per item_type."""
        specs = []
        partner_action = self.env.ref('base.action_partner_form', raise_if_not_found=False)
        for idx, itype in enumerate(ALL_ITEM_TYPES):
            if itype in EMBED_TYPES:
                spec = {
                    'name': f'SQL board · {itype}',
                    'item_type': itype,
                    'data_calculation_type': 'sql',
                }
                if itype == 'iframe':
                    spec['iframe_url'] = 'https://www.odoo.com/page/docs'
                if itype == 'odoo_view' and partner_action:
                    spec['odoo_action_id'] = partner_action.id
                specs.append(spec)
                continue

            vqb, sql = self._dd_ds_vqb_for_type(itype, idx)
            # Cards: simplify to scalar aggregate SQL
            if itype in CARD_TYPES:
                sql = (
                    'SELECT COUNT(*) AS "value"\n'
                    'FROM res_partner AS res_partner\n'
                    'WHERE res_partner."active" = true'
                )
                vqb = {
                    'baseModel': 'res.partner',
                    'fields': [
                        {'model': 'res.partner', 'name': 'id', 'alias': 'value', 'agg': 'COUNT', 'func': ''},
                    ],
                    'joins': [], 'wheres': [
                        {'model': 'res.partner', 'field': 'active', 'operator': '=', 'value': 'true',
                         'connector': '', 'valueType': 'value', 'cast': ''},
                    ],
                    'groupBys': [], 'havings': [], 'orderBys': [],
                    'distinct': False, 'limit': '1', 'offset': '',
                    'customExpressions': [], 'windowFuncs': [], 'ctes': [],
                }
            spec = {
                'name': f'VQB {itype}: complex SQL',
                'item_type': itype,
                'data_calculation_type': 'sql',
                'use_query_builder': True,
                'query_builder_data': json.dumps(vqb),
                'query': sql,
                'sql_row_limit': 500,
                'sql_label_column': False if itype in CARD_TYPES else 'label',
                'data_type': 'count',
                'chart_theme': ['ocean', 'corporate', 'cool', 'warm'][idx % 4],
                'show_data_value': True,
                'hide_legend': False,
                'legend_position': 'bottom',
                'enable_drill_down': False,
                'precision_digits': 0,
                'tile_color': '#0EA5E9',
                'tile_icon': 'fa-database',
                'tile_layout': 'layout1',
                'tile_theme': 'ocean',
                'unit': '',
                'background_color': '#FFFFFF',
                'font_color': '#0F172A',
                'record_limit': 50,
                'date_filter_selection': 'none',
                'enable_target': itype in CARD_TYPES,
                'standard_target_value': 50 if itype in CARD_TYPES else 0,
                'target_view': 'number',
                'list_view_type': 'ungrouped',
                'list_view_layout': 'layout1',
                'list_show_grand_total': True,
            }
            if num := kwargs.get('num'):
                if itype in CARD_TYPES:
                    spec['number_system_id'] = num.id
            specs.append(spec)

        items = self._dd_ds_create_items(dash, specs)
        todo = items.filtered(lambda i: i.item_type == 'todo')[:1]
        if todo:
            Todo = self.env['dynamic.dashboard.todo'].sudo()
            Todo.search([('dashboard_item_id', '=', todo.id)]).unlink()
            Todo.create([
                {'dashboard_item_id': todo.id, 'name': 'Open any chart → Data → Visual Query Builder', 'is_done': False},
                {'dashboard_item_id': todo.id, 'name': 'Click Test Query on a VQB item', 'is_done': False},
                {'dashboard_item_id': todo.id, 'name': 'Compare partner vs module SQL variants', 'is_done': False},
            ])

    @api.model
    def _dd_ds_common_external_specs(self, calc, connection=None, extra=None):
        """Shared chart gallery for api/excel/csv/scrape/sheets."""
        # Prefer chart-friendly types + cards + list
        types = [
            'tile', 'kpi', 'scorecard',
            'bar', 'barLine', 'horizontalBar', 'line', 'area', 'pie', 'doughnut',
            'polarArea', 'radar', 'funnel', 'gauge', 'treemap', 'heatmap', 'map',
            'list',
        ]
        specs = []
        for idx, itype in enumerate(types):
            spec = {
                'name': f'{calc.upper()} · {itype}',
                'item_type': itype,
                'data_calculation_type': calc,
                'chart_theme': ['cool', 'warm', 'ocean', 'pastel'][idx % 4],
                'show_data_value': True,
                'precision_digits': 2,
                'tile_color': '#2563EB',
                'tile_icon': 'fa-cloud',
                'tile_layout': 'layout2',
                'tile_theme': ['ocean', 'coral', 'forest', 'amber'][idx % 4],
                'unit': '$' if itype in CARD_TYPES else '',
                'unit_position': 'prefix',
                'enable_target': itype in CARD_TYPES,
                'standard_target_value': 100,
                'target_view': 'number',
                'background_color': '#FFFFFF',
                'font_color': '#111827',
                'record_limit': 30,
                'list_view_layout': 'layout1',
                'list_view_type': 'ungrouped',
                'list_show_grand_total': True,
                'date_filter_selection': 'none',
                'legend_position': 'bottom',
                'hide_legend': False,
            }
            if itype == 'scorecard':
                spec['scorecard_columns'] = '3'
            if connection:
                spec['external_connection_id'] = connection.id
            if extra:
                spec.update(extra)
            specs.append(spec)
        return specs

    @api.model
    def _dd_ds_build_api(self, dash, api_conn=None, **kwargs):
        extra = {
            'api_label_key': 'title',
            'api_value_key': 'price',
            'action_type': 'url',
            'action_url': 'https://dummyjson.com',
        }
        specs = self._dd_ds_common_external_specs('api', connection=api_conn, extra=extra)
        self._dd_ds_create_items(dash, specs)

    @api.model
    def _dd_ds_file_payload(self):
        rows = [
            ['Category', 'Amount', 'Quantity', 'Region'],
            ['Electronics', '12500', '42', 'NA'],
            ['Furniture', '8200', '18', 'EU'],
            ['Services', '15600', '55', 'APAC'],
            ['Software', '22100', '33', 'NA'],
            ['Retail', '9800', '70', 'LATAM'],
            ['Industrial', '17400', '25', 'MEA'],
        ]
        # CSV
        buf = io.StringIO()
        csv.writer(buf).writerows(rows)
        csv_b64 = base64.b64encode(buf.getvalue().encode('utf-8'))
        # Minimal XLSX-like CSV fallback if openpyxl missing — still set as excel bytes of CSV
        # Prefer real xlsx when possible
        xlsx_b64 = csv_b64
        try:
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            for r in rows:
                ws.append(list(r))
            out = io.BytesIO()
            wb.save(out)
            xlsx_b64 = base64.b64encode(out.getvalue())
        except Exception:
            pass
        return csv_b64, xlsx_b64

    @api.model
    def _dd_ds_build_excel(self, dash, **kwargs):
        _csv, xlsx = self._dd_ds_file_payload()
        extra = {
            'upload_file': xlsx,
            'upload_filename': 'demo_metrics.xlsx',
            'file_label_column': 'Category',
            'file_value_column': 'Amount',
            'data_type': 'sum',
        }
        specs = self._dd_ds_common_external_specs('excel', extra=extra)
        self._dd_ds_create_items(dash, specs)

    @api.model
    def _dd_ds_build_csv(self, dash, **kwargs):
        csv_b64, _xlsx = self._dd_ds_file_payload()
        extra = {
            'upload_file': csv_b64,
            'upload_filename': 'demo_metrics.csv',
            'file_label_column': 'Category',
            'file_value_column': 'Amount',
            'data_type': 'sum',
        }
        specs = self._dd_ds_common_external_specs('csv', extra=extra)
        self._dd_ds_create_items(dash, specs)

    @api.model
    def _dd_ds_build_scrape(self, dash, **kwargs):
        extra = {
            'scrape_url': 'https://dummyjson.com/products?limit=12',
            'scrape_json_path': 'products',
            'api_label_key': 'title',
            'api_value_key': 'price',
        }
        specs = self._dd_ds_common_external_specs('scrape', extra=extra)
        self._dd_ds_create_items(dash, specs)

    @api.model
    def _dd_ds_build_sheets(self, dash, sheets_conn=None, **kwargs):
        extra = {
            'sheets_id': '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms',
            'sheets_range': 'Class Data!A2:E10',
            'api_label_key': 'Student Name',
            'api_value_key': 'Class Level',
        }
        specs = self._dd_ds_common_external_specs('sheets', connection=sheets_conn, extra=extra)
        self._dd_ds_create_items(dash, specs)
