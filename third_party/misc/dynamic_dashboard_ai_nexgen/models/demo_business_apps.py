# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
"""Seed complex Sale / Purchase / Stock / Account dashboards.

Runs only when the target app module is installed. Does NOT add those modules
as hard depends of dynamic_dashboard_ai_nexgen (keeps base install lean).
"""
import base64
import csv
import io
import json
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class DynamicDashboardBusinessDemo(models.Model):
    _inherit = 'dynamic.dashboard'

    # ------------------------------------------------------------------
    # Public entry
    # ------------------------------------------------------------------
    @api.model
    def seed_business_app_dashboards(self, force=False):
        """Create Sale/Purchase/Stock/Account dashboards with every Data Calculation Type."""
        num_sys = self._dd_ensure_demo_number_system()
        api_conn = self._dd_ensure_demo_api_connection()
        sheets_conn = self._dd_ensure_demo_sheets_connection()

        created = []
        for cfg in self._dd_business_app_configs():
            if not self._dd_module_installed(cfg['module']):
                continue
            if not self._dd_model(cfg['model']):
                continue
            dash = self._dd_ensure_business_dashboard(cfg, num_sys, api_conn, sheets_conn, force=force)
            if dash:
                created.append(dash.name)
        return created

    @api.model
    def diagnose_data_calculation_types(self):
        """Smoke-test every Data Calculation Type using existing dashboard items.

        Returns a dict report: {calc_type: {status, item, detail}}.
        Prefer Items on Demo business dashboards when present.
        """
        Item = self.env['dynamic.dashboard.item'].sudo().with_context(dd_skip_auto_layout=True)
        types = [
            ('custom', 'Odoo Model'),
            ('sql', 'Custom SQL Query'),
            ('api', 'External API'),
            ('excel', 'Excel File'),
            ('csv', 'CSV File'),
            ('scrape', 'Web Scrape'),
            ('sheets', 'Google Sheets'),
        ]
        demo_names = [
            'Demo - Sales (All Data Sources)',
            'Demo - Purchase (All Data Sources)',
            'Demo - Inventory (All Data Sources)',
            'Demo - Accounting (All Data Sources)',
            'Chart Types Showcase',
            'Partner Insights Gallery',
        ]
        report = []
        for calc, label in types:
            item = Item.search([
                ('data_calculation_type', '=', calc),
                ('dashboard_id.name', 'in', demo_names),
            ], limit=1)
            if not item:
                item = Item.search([('data_calculation_type', '=', calc)], limit=1)
            if not item:
                report.append({
                    'type': calc,
                    'label': label,
                    'status': 'missing',
                    'detail': _('No dashboard item found for this type. Seed demos first.'),
                })
                continue
            try:
                with self.env.cr.savepoint():
                    data = item._get_item_data_dict()
                err = data.get('error')
                warn = data.get('warning')
                ok_shapes = (
                    data.get('labels')
                    or data.get('datasets')
                    or data.get('value') is not None
                    or data.get('records')
                    or data.get('iframe_url')
                    or data.get('odoo_action_id')
                    or data.get('scorecard_values')
                )
                if err and not ok_shapes:
                    report.append({
                        'type': calc,
                        'label': label,
                        'status': 'error',
                        'item': item.display_name,
                        'detail': err,
                    })
                elif err and ok_shapes:
                    report.append({
                        'type': calc,
                        'label': label,
                        'status': 'warning',
                        'item': item.display_name,
                        'detail': err,
                    })
                elif warn:
                    report.append({
                        'type': calc,
                        'label': label,
                        'status': 'ok_demo',
                        'item': item.display_name,
                        'detail': warn,
                    })
                elif ok_shapes:
                    n = len(data.get('labels') or data.get('records') or [])
                    report.append({
                        'type': calc,
                        'label': label,
                        'status': 'ok',
                        'item': item.display_name,
                        'detail': _('OK (%s rows/points)') % (n or 1),
                    })
                else:
                    report.append({
                        'type': calc,
                        'label': label,
                        'status': 'empty',
                        'item': item.display_name,
                        'detail': _('Payload returned with no chart/list values.'),
                    })
            except Exception as e:
                report.append({
                    'type': calc,
                    'label': label,
                    'status': 'error',
                    'item': item.display_name,
                    'detail': str(e),
                })
        return report

    @api.model
    def action_diagnose_data_calculation_types(self):
        """Server-action entry: run diagnose and show a notification."""
        report = self.diagnose_data_calculation_types()
        lines = []
        worst = 'success'
        for row in report:
            st = row.get('status')
            icon = {
                'ok': '✓',
                'ok_demo': '≈',
                'warning': '!',
                'empty': '○',
                'missing': '–',
                'error': '✕',
            }.get(st, '?')
            lines.append(f"{icon} {row['label']}: {row.get('detail') or st}")
            if st == 'error':
                worst = 'danger'
            elif st in ('empty', 'missing', 'warning') and worst == 'success':
                worst = 'warning'
            elif st == 'ok_demo' and worst == 'success':
                worst = 'warning'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Data Calculation Types'),
                'message': '\n'.join(lines),
                'type': worst,
                'sticky': True,
            },
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model
    def _dd_module_installed(self, module_name):
        mod = self.env['ir.module.module'].sudo().search([('name', '=', module_name)], limit=1)
        return bool(mod and mod.state == 'installed')

    @api.model
    def _dd_ensure_demo_number_system(self):
        NS = self.env['dynamic.dashboard.number.system'].sudo()
        ns = NS.search([('name', '=', 'Demo Business Compact')], limit=1)
        if ns:
            return ns
        return NS.create({
            'name': 'Demo Business Compact',
            'line_ids': [
                (0, 0, {'threshold': 1000000000, 'divisor': 1000000000, 'suffix': 'B'}),
                (0, 0, {'threshold': 1000000, 'divisor': 1000000, 'suffix': 'M'}),
                (0, 0, {'threshold': 1000, 'divisor': 1000, 'suffix': 'K'}),
            ],
        })

    @api.model
    def _dd_ensure_demo_api_connection(self):
        Conn = self.env['dynamic.dashboard.connection'].sudo()
        conn = Conn.search([
            ('name', '=', 'Demo Products API (dummyjson)'),
            ('connection_type', '=', 'api'),
        ], limit=1)
        if conn:
            return conn
        return Conn.create({
            'name': 'Demo Products API (dummyjson)',
            'connection_type': 'api',
            'api_endpoint': 'https://dummyjson.com/products?limit=30',
            'api_method': 'GET',
            'api_headers': json.dumps({'Accept': 'application/json'}),
            'api_data_path': 'products',
        })

    @api.model
    def _dd_ensure_demo_sheets_connection(self):
        Conn = self.env['dynamic.dashboard.connection'].sudo()
        conn = Conn.search([
            ('name', '=', 'Demo Google Sheets Connection'),
            ('connection_type', '=', 'sheets'),
        ], limit=1)
        if conn:
            # Keep existing real keys; refresh placeholder metadata when regenerating demos
            return conn
        return Conn.create({
            'name': 'Demo Google Sheets Connection',
            'connection_type': 'sheets',
            # Placeholder — do not call Google with this value (sample data is used until replaced)
            'sheets_api_key': 'DEMO_REPLACE_WITH_REAL_GOOGLE_API_KEY',
            'sheets_spreadsheet_id': '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms',
        })

    @api.model
    def _dd_csv_b64(self, rows, headers):
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        return base64.b64encode(buf.getvalue().encode('utf-8')).decode('ascii')

    @api.model
    def _dd_xlsx_b64(self, rows, headers):
        try:
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = 'Demo'
            ws.append(headers)
            for row in rows:
                ws.append([row.get(h) for h in headers])
            out = io.BytesIO()
            wb.save(out)
            return base64.b64encode(out.getvalue()).decode('ascii')
        except ImportError:
            # Minimal XLSX (OOXML) without openpyxl — Excel reader still needs openpyxl at runtime
            import zipfile
            from xml.sax.saxutils import escape

            def _cell(ref, value):
                if isinstance(value, (int, float)):
                    return f'<c r="{ref}"><v>{value}</v></c>'
                return f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'

            sheet_rows = []
            all_rows = [headers] + [[r.get(h) for h in headers] for r in rows]
            for r_idx, row in enumerate(all_rows, start=1):
                cells = []
                for c_idx, val in enumerate(row):
                    col = ''
                    n = c_idx + 1
                    while n:
                        n, rem = divmod(n - 1, 26)
                        col = chr(65 + rem) + col
                    cells.append(_cell(f'{col}{r_idx}', val if val is not None else ''))
                sheet_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')
            sheet_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
            )
            workbook_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Demo" sheetId="1" r:id="rId1"/></sheets></workbook>'
            )
            rels = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                '</Relationships>'
            )
            wb_rels = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                '</Relationships>'
            )
            content_types = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                '</Types>'
            )
            out = io.BytesIO()
            with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('[Content_Types].xml', content_types)
                zf.writestr('_rels/.rels', rels)
                zf.writestr('xl/workbook.xml', workbook_xml)
                zf.writestr('xl/_rels/workbook.xml.rels', wb_rels)
                zf.writestr('xl/worksheets/sheet1.xml', sheet_xml)
            return base64.b64encode(out.getvalue()).decode('ascii')

    @api.model
    def _dd_business_app_configs(self):
        return [
            {
                'module': 'sale',
                'dashboard_name': 'Demo - Sales (All Data Sources)',
                'category': 'Sales',
                'model': 'sale.order',
                'table': 'sale_order',
                'line_model': 'sale.order.line',
                'measure': 'amount_total',
                'measure_2': 'amount_untaxed',
                'group': 'state',
                'group_partner': 'partner_id',
                'group_user': 'user_id',
                'date_field': 'date_order',
                'list_fields': ['name', 'partner_id', 'user_id', 'date_order', 'amount_total', 'state'],
                'domain': "[('state', '!=', 'cancel')]",
                'tile_color': '#e8f5e9',
                'tile_icon': 'fa-shopping-cart',
                'action_xmlids': ['sale.action_orders', 'sale.action_quotations'],
                'file_rows': [
                    {'Region': 'North', 'Orders': 42, 'Revenue': 125000},
                    {'Region': 'South', 'Orders': 28, 'Revenue': 87000},
                    {'Region': 'East', 'Orders': 35, 'Revenue': 99000},
                    {'Region': 'West', 'Orders': 51, 'Revenue': 143000},
                    {'Region': 'Export', 'Orders': 19, 'Revenue': 210000},
                ],
                'file_headers': ['Region', 'Orders', 'Revenue'],
                'sql_label': 'state',
                'sql_query': (
                    "SELECT state AS label, COALESCE(SUM(amount_total), 0) AS value "
                    "FROM sale_order WHERE company_id = {company_id} AND state != 'cancel' "
                    "GROUP BY state ORDER BY value DESC LIMIT 20"
                ),
            },
            {
                'module': 'purchase',
                'dashboard_name': 'Demo - Purchase (All Data Sources)',
                'category': 'Purchase',
                'model': 'purchase.order',
                'table': 'purchase_order',
                'line_model': 'purchase.order.line',
                'measure': 'amount_total',
                'measure_2': 'amount_untaxed',
                'group': 'state',
                'group_partner': 'partner_id',
                'group_user': 'user_id',
                'date_field': 'date_order',
                'list_fields': ['name', 'partner_id', 'user_id', 'date_order', 'amount_total', 'state'],
                'domain': "[('state', '!=', 'cancel')]",
                'tile_color': '#fff3e0',
                'tile_icon': 'fa-truck',
                'action_xmlids': ['purchase.purchase_rfq', 'purchase.purchase_form_action'],
                'file_rows': [
                    {'Vendor': 'Acme Supplies', 'POs': 12, 'Spend': 45000},
                    {'Vendor': 'Global Parts', 'POs': 9, 'Spend': 32000},
                    {'Vendor': 'Local Tools', 'POs': 15, 'Spend': 18000},
                    {'Vendor': 'Euro Metals', 'POs': 7, 'Spend': 67000},
                    {'Vendor': 'Asia Tech', 'POs': 11, 'Spend': 54000},
                ],
                'file_headers': ['Vendor', 'POs', 'Spend'],
                'sql_label': 'state',
                'sql_query': (
                    "SELECT state AS label, COALESCE(SUM(amount_total), 0) AS value "
                    "FROM purchase_order WHERE company_id = {company_id} AND state != 'cancel' "
                    "GROUP BY state ORDER BY value DESC LIMIT 20"
                ),
            },
            {
                'module': 'stock',
                'dashboard_name': 'Demo - Inventory (All Data Sources)',
                'category': 'Inventory',
                'model': 'stock.picking',
                'table': 'stock_picking',
                'line_model': 'stock.move',
                'measure': False,  # count-based by default
                'measure_line': 'product_uom_qty',
                'group': 'state',
                'group_partner': 'partner_id',
                'group_user': 'user_id',
                'date_field': 'scheduled_date',
                'list_fields': ['name', 'partner_id', 'picking_type_id', 'scheduled_date', 'state'],
                'domain': "[]",
                'tile_color': '#e3f2fd',
                'tile_icon': 'fa-archive',
                'action_xmlids': ['stock.action_picking_tree_all', 'stock.stock_move_action'],
                'file_rows': [
                    {'Warehouse': 'WH/Stock', 'Transfers': 40, 'Qty': 1250},
                    {'Warehouse': 'WH/Input', 'Transfers': 22, 'Qty': 640},
                    {'Warehouse': 'WH/Output', 'Transfers': 31, 'Qty': 980},
                    {'Warehouse': 'WH/QC', 'Transfers': 8, 'Qty': 120},
                    {'Warehouse': 'WH/Pack', 'Transfers': 14, 'Qty': 410},
                ],
                'file_headers': ['Warehouse', 'Transfers', 'Qty'],
                'sql_label': 'state',
                'sql_query': (
                    "SELECT state AS label, COUNT(*) AS value "
                    "FROM stock_picking WHERE company_id = {company_id} "
                    "GROUP BY state ORDER BY value DESC LIMIT 20"
                ),
            },
            {
                'module': 'account',
                'dashboard_name': 'Demo - Accounting (All Data Sources)',
                'category': 'Accounting',
                'model': 'account.move',
                'table': 'account_move',
                'line_model': 'account.move.line',
                'measure': 'amount_total_signed',
                'measure_2': 'amount_residual_signed',
                'group': 'move_type',
                'group_partner': 'partner_id',
                'group_user': 'invoice_user_id',
                'date_field': 'invoice_date',
                'list_fields': ['name', 'partner_id', 'invoice_date', 'move_type', 'amount_total_signed', 'state'],
                'domain': "[('move_type', 'in', ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')), ('state', '!=', 'cancel')]",
                'tile_color': '#f3e5f5',
                'tile_icon': 'fa-calculator',
                'action_xmlids': [
                    'account.action_move_out_invoice_type',
                    'account.action_move_in_invoice_type',
                ],
                'file_rows': [
                    {'Type': 'Customer Invoice', 'Count': 55, 'Amount': 320000},
                    {'Type': 'Vendor Bill', 'Count': 41, 'Amount': 210000},
                    {'Type': 'Credit Note', 'Count': 8, 'Amount': 12000},
                    {'Type': 'Refund', 'Count': 5, 'Amount': 7500},
                    {'Type': 'Other', 'Count': 12, 'Amount': 18000},
                ],
                'file_headers': ['Type', 'Count', 'Amount'],
                'sql_label': 'move_type',
                'sql_query': (
                    "SELECT move_type AS label, COALESCE(SUM(amount_total_signed), 0) AS value "
                    "FROM account_move WHERE company_id = {company_id} "
                    "AND move_type IN ('out_invoice','out_refund','in_invoice','in_refund') "
                    "AND state != 'cancel' "
                    "GROUP BY move_type ORDER BY value DESC LIMIT 20"
                ),
            },
        ]

    @api.model
    def _dd_ensure_business_dashboard(self, cfg, num_sys, api_conn, sheets_conn, force=False):
        Dash = self.env['dynamic.dashboard'].sudo()
        Item = self.env['dynamic.dashboard.item'].sudo().with_context(dd_skip_auto_layout=True)
        Color = self.env['dynamic.dashboard.item.color'].sudo()
        Source = self.env['dynamic.dashboard.item.source'].sudo()
        Todo = self.env['dynamic.dashboard.todo'].sudo()

        model = self._dd_model(cfg['model'])
        if not model:
            return Dash.browse()

        dash = Dash.search([('name', '=', cfg['dashboard_name'])], limit=1)
        if dash and not force:
            return dash
        if dash and force:
            dash.item_ids.unlink()
        else:
            dash = Dash.create({
                'name': cfg['dashboard_name'],
                'category_id': self.env['dynamic.dashboard.category'].sudo().get_or_create(cfg['category']).id,
                'gridstack_config': '{}',
                'default_date_filter': 'this_year',
                'sticky_navbar': True,
                'background_color': '#f4f7fe',
                'layout_direction': 'auto',
            })

        def F(name, model_name=None):
            return self._dd_field(model_name or cfg['model'], name)

        measure = F(cfg['measure']) if cfg.get('measure') else False
        if not measure and cfg['module'] == 'account':
            measure = F('amount_total') or F('amount_total_signed')
        if not measure and cfg['module'] in ('sale', 'purchase'):
            measure = F('amount_total')
        measure_2 = F(cfg['measure_2']) if cfg.get('measure_2') else False
        if not measure_2 and cfg['module'] == 'account':
            measure_2 = F('amount_untaxed') or F('amount_residual') or F('amount_residual_signed')
        if not measure_2 and cfg['module'] in ('sale', 'purchase'):
            measure_2 = F('amount_untaxed')
        group = F(cfg['group'])
        group_partner = F(cfg.get('group_partner'))
        group_user = F(cfg.get('group_user'))
        date_f = F(cfg['date_field'])
        list_fields = [F(n) for n in cfg.get('list_fields') or []]
        list_fields = [f for f in list_fields if f]

        # Prefer stored date field for stock (scheduled_date might be datetime)
        if not date_f and cfg['module'] == 'stock':
            date_f = F('date_done') or F('create_date')
        if not group_user and cfg['module'] == 'account':
            group_user = F('create_uid')

        line_model = self._dd_model(cfg['line_model']) if cfg.get('line_model') else False
        line_measure = False
        line_group = False
        if line_model:
            if cfg.get('measure_line'):
                line_measure = self._dd_field(cfg['line_model'], cfg['measure_line'])
            line_measure = line_measure or self._dd_field(cfg['line_model'], 'price_subtotal') \
                or self._dd_field(cfg['line_model'], 'product_uom_qty')
            line_group = self._dd_field(cfg['line_model'], 'order_id') \
                or self._dd_field(cfg['line_model'], 'picking_id') \
                or self._dd_field(cfg['line_model'], 'move_id')

        # Resolve action for click / odoo_view
        window_action = False
        for xid in cfg.get('action_xmlids') or []:
            window_action = self.env.ref(xid, raise_if_not_found=False)
            if window_action:
                break

        csv_b64 = self._dd_csv_b64(cfg['file_rows'], cfg['file_headers'])
        xlsx_b64 = self._dd_xlsx_b64(cfg['file_rows'], cfg['file_headers'])
        label_col, value_col = cfg['file_headers'][0], cfg['file_headers'][-1]

        company = self.env.company
        currency = company.currency_id

        base_display = {
            'currency_id': currency.id if currency else False,
            'number_system_id': num_sys.id,
            'precision_digits': 2,
            'data_format': 'english',
            'background_color': '#ffffff',
            'font_color': '#212529',
            'unit': '$' if cfg['module'] != 'stock' else 'qty',
            'unit_position': 'prefix' if cfg['module'] != 'stock' else 'suffix',
            'show_records': True,
            'enable_drill_down': True,
            'auto_update_type': 'manual',
            'pagination_limit': 10,
            'export_all_records': True,
            'list_show_grand_total': True,
            'list_column_min_width': 100,
            'visual_config': json.dumps({
                'scrollbar': True,
                'axis_max': False,
                'demo_source': cfg['module'],
            }),
        }

        specs = []
        y = 0

        # ---- CUSTOM (Odoo Model) — rich set ----
        specs.append(dict(
            name=f"{cfg['category']}: Total (Tile)",
            item_type='tile', data_calculation_type='custom',
            grid_x=0, grid_y=y, grid_w=3, grid_h=2,
            data_type='sum' if measure else 'count',
            measure_field_ids=[(6, 0, [measure.id])] if measure else False,
            tile_layout='layout1', tile_color=cfg['tile_color'], tile_icon=cfg['tile_icon'],
            date_filter_field_id=date_f.id if date_f else False,
            date_filter_selection='this_year',
            compare_previous_period=True,
            **{k: v for k, v in base_display.items() if k in (
                'currency_id', 'precision_digits', 'data_format', 'unit', 'unit_position',
                'show_records', 'auto_update_type',
            )},
        ))
        specs.append(dict(
            name=f"{cfg['category']}: Count (Tile)",
            item_type='tile', data_calculation_type='custom',
            grid_x=3, grid_y=y, grid_w=3, grid_h=2,
            data_type='count',
            tile_layout='layout2', tile_color='#eceff1', tile_icon='fa-list',
            date_filter_field_id=date_f.id if date_f else False,
            date_filter_selection='this_month',
        ))
        specs.append(dict(
            name=f"{cfg['category']}: KPI vs Target",
            item_type='kpi', data_calculation_type='custom',
            grid_x=6, grid_y=y, grid_w=3, grid_h=2,
            data_type='sum' if measure else 'count',
            measure_field_ids=[(6, 0, [measure.id])] if measure else False,
            enable_target=True, standard_target_value=100000 if measure else 50,
            target_view='progress_bar',
            date_filter_field_id=date_f.id if date_f else False,
            date_filter_selection='this_year',
            compare_previous_period=True,
            number_system_id=num_sys.id,
            currency_id=currency.id if currency else False,
            unit=base_display['unit'], unit_position=base_display['unit_position'],
            precision_digits=2, data_format='english',
            show_records=True,
        ))
        specs.append(dict(
            name=f"{cfg['category']}: Scorecard",
            item_type='scorecard', data_calculation_type='custom',
            grid_x=9, grid_y=y, grid_w=3, grid_h=2,
            data_type='average' if measure else 'count',
            measure_field_ids=[(6, 0, [measure.id])] if measure else False,
            enable_target=True, standard_target_value=5000 if measure else 10,
            target_view='number',
            currency_id=currency.id if currency else False,
        ))
        y += 2

        specs.append(dict(
            name=f"Custom Bar: by {cfg['group']}",
            item_type='bar', data_calculation_type='custom',
            grid_x=0, grid_y=y, grid_w=6, grid_h=4,
            data_type='sum' if measure else 'count',
            measure_field_ids=[(6, 0, [measure.id])] if measure else False,
            group_by_field_id=group.id if group else False,
            sort_by_field_id=measure.id if measure else (group.id if group else False),
            sort_order='desc', record_limit=12,
            chart_theme='corporate', show_data_value=True, hide_legend=False,
            is_stacked=False, show_records=True, enable_drill_down=True,
            date_filter_field_id=date_f.id if date_f else False,
            date_filter_selection='this_year',
            fill_temporal=False,
            compare_previous_period=True,
            domain_extension='[]',
            multiplier_active=False, multiplier_value=1.0,
            is_cumulative=False, formula_active=False,
            background_color='#ffffff', font_color='#212529',
            currency_id=currency.id if currency else False,
            number_system_id=num_sys.id, precision_digits=2, data_format='english',
            unit=base_display['unit'], unit_position=base_display['unit_position'],
            visual_config=base_display['visual_config'],
            action_type='window' if window_action else 'none',
            action_id=window_action.id if window_action else False,
            auto_update_type='1m',
        ))
        specs.append(dict(
            name="Custom Bar+Line: dual measures",
            item_type='barLine', data_calculation_type='custom',
            grid_x=6, grid_y=y, grid_w=6, grid_h=4,
            data_type='sum' if measure else 'count',
            measure_field_ids=[(6, 0, [measure.id])] if measure else False,
            measure_field_2_ids=[(6, 0, [measure_2.id])] if measure_2 else False,
            group_by_field_id=(group_partner or group).id if (group_partner or group) else False,
            chart_theme='ocean', show_data_value=True, show_records=True,
            enable_drill_down=True,
            date_filter_field_id=date_f.id if date_f else False,
            date_filter_selection='this_year',
            currency_id=currency.id if currency else False,
            number_system_id=num_sys.id,
        ))
        y += 4

        specs.append(dict(
            name="Custom Line: trend (fill temporal)",
            item_type='line', data_calculation_type='custom',
            grid_x=0, grid_y=y, grid_w=6, grid_h=4,
            data_type='sum' if measure else 'count',
            measure_field_ids=[(6, 0, [measure.id])] if measure else False,
            group_by_field_id=date_f.id if date_f else False,
            group_by_date_type='month',
            fill_temporal=True, is_cumulative=False,
            chart_theme='cool', show_data_value=True, show_records=True,
            enable_drill_down=True,
            date_filter_field_id=date_f.id if date_f else False,
            date_filter_selection='this_year',
            compare_previous_period=True,
            currency_id=currency.id if currency else False,
        ))
        specs.append(dict(
            name="Custom Area: cumulative",
            item_type='area', data_calculation_type='custom',
            grid_x=6, grid_y=y, grid_w=6, grid_h=4,
            data_type='sum' if measure else 'count',
            measure_field_ids=[(6, 0, [measure.id])] if measure else False,
            group_by_field_id=date_f.id if date_f else False,
            group_by_date_type='month',
            fill_temporal=True, is_cumulative=True,
            chart_theme='sunset', show_data_value=False, hide_legend=False,
            date_filter_field_id=date_f.id if date_f else False,
            date_filter_selection='this_year',
        ))
        y += 4

        specs.append(dict(
            name="Custom Pie: breakdown",
            item_type='pie', data_calculation_type='custom',
            grid_x=0, grid_y=y, grid_w=4, grid_h=4,
            data_type='sum' if measure else 'count',
            measure_field_ids=[(6, 0, [measure.id])] if measure else False,
            group_by_field_id=group.id if group else False,
            chart_theme='warm', show_data_value=True, hide_legend=False,
            show_records=True, enable_drill_down=True,
        ))
        specs.append(dict(
            name="Custom Doughnut (semi)",
            item_type='doughnut', data_calculation_type='custom',
            grid_x=4, grid_y=y, grid_w=4, grid_h=4,
            data_type='count',
            group_by_field_id=(group_user or group).id if (group_user or group) else False,
            chart_theme='pastel', is_semi_circle=True, show_data_value=True,
        ))
        specs.append(dict(
            name="Custom Horizontal Bar",
            item_type='horizontalBar', data_calculation_type='custom',
            grid_x=8, grid_y=y, grid_w=4, grid_h=4,
            data_type='sum' if measure else 'count',
            measure_field_ids=[(6, 0, [measure.id])] if measure else False,
            group_by_field_id=(group_user or group_partner or group).id if (group_user or group_partner or group) else False,
            chart_theme='vibrant', show_data_value=True, is_stacked=False,
            record_limit=10, sort_order='desc',
        ))
        y += 4

        specs.append(dict(
            name="Custom Stacked Bar (sub-group)",
            item_type='bar', data_calculation_type='custom',
            grid_x=0, grid_y=y, grid_w=6, grid_h=4,
            data_type='sum' if measure else 'count',
            measure_field_ids=[(6, 0, [measure.id])] if measure else False,
            group_by_field_id=group.id if group else False,
            sub_group_by_field_id=(group_user or group_partner).id if (group_user or group_partner) else False,
            is_stacked=True, chart_theme='corporate', show_data_value=False,
            date_filter_field_id=date_f.id if date_f else False,
            date_filter_selection='this_year',
            show_records=True, enable_drill_down=True,
        ))
        specs.append(dict(
            name="Custom List (ungrouped)",
            item_type='list', data_calculation_type='custom',
            grid_x=6, grid_y=y, grid_w=6, grid_h=4,
            list_view_type='ungrouped', list_view_layout='layout1',
            list_view_field_ids=[(6, 0, [f.id for f in list_fields])] if list_fields else False,
            sort_by_field_id=date_f.id if date_f else False,
            sort_order='desc', record_limit=15,
            pagination_limit=10, export_all_records=True,
            list_show_grand_total=True, list_column_min_width=110,
            date_filter_field_id=date_f.id if date_f else False,
            date_filter_selection='this_year',
            show_records=True,
        ))
        y += 4

        specs.append(dict(
            name="Custom Grouped List",
            item_type='list', data_calculation_type='custom',
            grid_x=0, grid_y=y, grid_w=6, grid_h=4,
            list_view_type='grouped', list_view_layout='layout1',
            data_type='sum' if measure else 'count',
            measure_field_ids=[(6, 0, [measure.id])] if measure else False,
            group_by_field_id=group.id if group else False,
            pagination_limit=20, export_all_records=True,
        ))
        specs.append(dict(
            name="Custom Funnel / Bullet",
            item_type='funnel' if cfg['module'] != 'stock' else 'bullet',
            data_calculation_type='custom',
            grid_x=6, grid_y=y, grid_w=6, grid_h=4,
            data_type='sum' if measure else 'count',
            measure_field_ids=[(6, 0, [measure.id])] if measure else False,
            group_by_field_id=group.id if group else False,
            chart_theme='cool', show_data_value=True,
            enable_target=True, standard_target_value=80000 if measure else 20,
            target_view='progress_bar',
            currency_id=currency.id if currency else False,
            number_system_id=num_sys.id,
        ))
        y += 4

        # Extra custom visuals + formula / multiplier
        specs.append(dict(
            name="Custom Polar Area",
            item_type='polarArea', data_calculation_type='custom',
            grid_x=0, grid_y=y, grid_w=4, grid_h=4,
            data_type='sum' if measure else 'count',
            measure_field_ids=[(6, 0, [measure.id])] if measure else False,
            group_by_field_id=group.id if group else False,
            chart_theme='ocean', show_data_value=True, hide_legend=False,
            date_filter_field_id=date_f.id if date_f else False,
            date_filter_selection='this_year',
        ))
        specs.append(dict(
            name="Custom Radar",
            item_type='radar', data_calculation_type='custom',
            grid_x=4, grid_y=y, grid_w=4, grid_h=4,
            data_type='sum' if measure else 'count',
            measure_field_ids=[(6, 0, [measure.id])] if measure else False,
            group_by_field_id=group.id if group else False,
            chart_theme='neon', show_data_value=False, hide_legend=False,
        ))
        specs.append(dict(
            name="Custom Radial / Flower",
            item_type='radialBar' if cfg['module'] in ('sale', 'account') else 'flower',
            data_calculation_type='custom',
            grid_x=8, grid_y=y, grid_w=4, grid_h=4,
            data_type='sum' if measure else 'count',
            measure_field_ids=[(6, 0, [measure.id])] if measure else False,
            group_by_field_id=(group_partner or group).id if (group_partner or group) else False,
            chart_theme='sunset', show_data_value=True, record_limit=8,
        ))
        y += 4

        if measure and measure_2:
            specs.append(dict(
                name="Custom Scatter: dual measures",
                item_type='scatter', data_calculation_type='custom',
                grid_x=0, grid_y=y, grid_w=6, grid_h=4,
                scatter_measure_x_id=measure.id,
                scatter_measure_y_id=measure_2.id,
                is_scatter_group=True,
                group_by_field_id=group.id if group else False,
                chart_theme='corporate', show_records=True,
                date_filter_field_id=date_f.id if date_f else False,
                date_filter_selection='this_year',
            ))
        specs.append(dict(
            name="Custom Tile: formula + multiplier",
            item_type='tile', data_calculation_type='custom',
            grid_x=6 if (measure and measure_2) else 0, grid_y=y, grid_w=6, grid_h=4,
            data_type='sum' if measure else 'count',
            measure_field_ids=[(6, 0, [measure.id])] if measure else False,
            measure_field_2_ids=[(6, 0, [measure_2.id])] if measure_2 else False,
            formula_active=True,
            formula='{m1}/{count}' if measure else '{count}*1',
            multiplier_active=True,
            multiplier_value=1.0,
            tile_layout='layout3', tile_color='#e8eaf6', tile_icon='fa-flask',
            date_filter_field_id=date_f.id if date_f else False,
            date_filter_selection='this_year',
            unit=base_display['unit'], unit_position=base_display['unit_position'],
            currency_id=currency.id if currency else False,
            precision_digits=2, data_format='english',
            number_system_id=num_sys.id,
            compare_previous_period=True,
            show_records=True,
        ))
        y += 4

        # KPI with secondary model (when line model exists)
        if line_model and line_measure:
            specs.append(dict(
                name="Custom KPI: dual-model comparison",
                item_type='kpi', data_calculation_type='custom',
                grid_x=0, grid_y=y, grid_w=6, grid_h=3,
                data_type='sum' if measure else 'count',
                measure_field_ids=[(6, 0, [measure.id])] if measure else False,
                enable_target=True, standard_target_value=50000 if measure else 25,
                target_view='number',
                kpi_model_id=line_model.id,
                kpi_data_type='sum',
                kpi_measure_field_id=line_measure.id,
                kpi_domain='[]',
                kpi_date_filter_field_id=False,
                kpi_date_filter_selection='none',
                kpi_comparison='percentage',
                date_filter_field_id=date_f.id if date_f else False,
                date_filter_selection='this_year',
                currency_id=currency.id if currency else False,
                number_system_id=num_sys.id,
                unit=base_display['unit'], unit_position=base_display['unit_position'],
                precision_digits=2, data_format='english',
                show_records=True, compare_previous_period=True,
            ))
            y += 3

        # ---- SQL ----
        specs.append(dict(
            name="SQL Query: aggregation",
            item_type='bar', data_calculation_type='sql',
            grid_x=0, grid_y=y, grid_w=6, grid_h=4,
            query=cfg['sql_query'],
            sql_label_column=cfg['sql_label'],
            sql_row_limit=50,
            date_filter_selection='this_year',
            chart_theme='ocean', show_data_value=True, hide_legend=False,
            is_stacked=False, show_records=False,
            background_color='#fafafa', font_color='#212529',
            data_format='english', precision_digits=2,
            unit=base_display['unit'], unit_position=base_display['unit_position'],
            currency_id=currency.id if currency else False,
            number_system_id=num_sys.id,
            auto_update_type='5m',
            visual_config=json.dumps({'source': 'sql', 'table': cfg['table']}),
        ))

        vqb_data_1 = json.dumps({
            "baseModel": cfg['model'],
            "fields": [
                {"model": cfg['model'], "name": cfg.get('group') or "name", "alias": "label"},
                {"model": cfg['model'], "name": cfg.get('measure') or "id", "alias": "value", "aggFunc": "sum"}
            ],
            "joins": [],
            "wheres": [{"model": cfg['model'], "field": "company_id", "operator": "=", "value": "{company_id}", "connector": "AND"}],
            "groupBys": [{"model": cfg['model'], "field": cfg.get('group') or "name", "func": ""}],
            "havings": [],
            "orderBys": [{"model": cfg['model'], "field": cfg.get('measure') or "id", "direction": "DESC"}],
            "limit": "15"
        })
        specs.append(dict(
            name="Visual Query Builder: Bar Chart",
            item_type='bar', data_calculation_type='sql',
            use_query_builder=True,
            query_builder_data=vqb_data_1,
            query=cfg['sql_query'],
            sql_label_column='label',
            sql_row_limit=50,
            grid_x=6, grid_y=y, grid_w=6, grid_h=4,
            chart_theme='warm', show_data_value=True,
        ))
        y += 4

        date_field = cfg.get('date_field') or 'create_date'
        vqb_data_2 = json.dumps({
            "baseModel": cfg['model'],
            "fields": [
                {"model": cfg['model'], "name": "name", "alias": "label"},
                {"model": cfg['model'], "name": date_field, "alias": "date_val"}
            ],
            "joins": [],
            "wheres": [{"model": cfg['model'], "field": "company_id", "operator": "=", "value": "{company_id}", "connector": "AND"}],
            "groupBys": [],
            "havings": [],
            "orderBys": [{"model": cfg['model'], "field": date_field, "direction": "DESC"}],
            "limit": "10"
        })
        specs.append(dict(
            name="Visual Query Builder: Recent List",
            item_type='list', data_calculation_type='sql',
            use_query_builder=True,
            query_builder_data=vqb_data_2,
            query=f"SELECT name AS label, {date_field} AS date_val FROM {cfg['table']} WHERE company_id = {{company_id}} ORDER BY {date_field} DESC LIMIT 10",
            grid_x=0, grid_y=y, grid_w=6, grid_h=4,
        ))

        # ---- API ----
        specs.append(dict(
            name="External API: products sample",
            item_type='bar', data_calculation_type='api',
            grid_x=6, grid_y=y, grid_w=6, grid_h=4,
            external_connection_id=api_conn.id,
            api_label_key='title',
            api_value_key='price',
            chart_theme='neon', show_data_value=True, hide_legend=True,
            is_stacked=False, record_limit=15,
            background_color='#ffffff', font_color='#212529',
            unit='$', unit_position='prefix',
            precision_digits=2, data_format='exact',
            number_system_id=num_sys.id,
            currency_id=currency.id if currency else False,
            auto_update_type='5m',
            show_records=False,
            visual_config=json.dumps({'source': 'api', 'endpoint': 'dummyjson/products'}),
        ))
        y += 4

        # ---- CSV ----
        specs.append(dict(
            name="CSV Upload: sample file",
            item_type='bar', data_calculation_type='csv',
            grid_x=0, grid_y=y, grid_w=6, grid_h=4,
            upload_file=csv_b64,
            upload_filename=f"{cfg['module']}_demo.csv",
            file_label_column=label_col,
            file_value_column=value_col,
            data_type='sum',
            chart_theme='warm', show_data_value=True, hide_legend=False,
            show_records=False, is_stacked=False,
            unit=base_display['unit'], unit_position=base_display['unit_position'],
            currency_id=currency.id if currency else False,
            number_system_id=num_sys.id,
            precision_digits=2, data_format='english',
            background_color='#ffffff', font_color='#212529',
            visual_config=json.dumps({'source': 'csv', 'label': label_col, 'value': value_col}),
        ))

        # ---- Excel ----
        specs.append(dict(
            name="Excel Upload: sample workbook",
            item_type='horizontalBar', data_calculation_type='excel',
            grid_x=6, grid_y=y, grid_w=6, grid_h=4,
            upload_file=xlsx_b64,
            upload_filename=f"{cfg['module']}_demo.xlsx",
            file_label_column=label_col,
            file_value_column=value_col,
            data_type='sum',
            chart_theme='vibrant', show_data_value=True, hide_legend=False,
            unit=base_display['unit'], unit_position=base_display['unit_position'],
            currency_id=currency.id if currency else False,
            number_system_id=num_sys.id,
            precision_digits=2, data_format='english',
            background_color='#ffffff', font_color='#212529',
            visual_config=json.dumps({'source': 'excel', 'label': label_col, 'value': value_col}),
        ))
        y += 4

        # ---- Scrape ----
        specs.append(dict(
            name="Web Scrape: JSON feed",
            item_type='pie', data_calculation_type='scrape',
            grid_x=0, grid_y=y, grid_w=6, grid_h=4,
            # select=title,price so first keys are chart-friendly label/value
            # Prefer explicit keys (dummyjson still returns id first even with select=)
            scrape_url='https://dummyjson.com/products?limit=20&select=title,price',
            scrape_json_path='products',
            api_label_key='title',
            api_value_key='price',
            chart_theme='pastel', show_data_value=True, hide_legend=False,
            background_color='#ffffff', font_color='#333333',
            unit='$', unit_position='prefix',
            precision_digits=2, data_format='exact',
            auto_update_type='5m',
            visual_config=json.dumps({'source': 'scrape', 'path': 'products', 'label': 'title', 'value': 'price'}),
        ))

        # ---- Sheets ----
        specs.append(dict(
            name="Google Sheets: connected range",
            item_type='bar', data_calculation_type='sheets',
            grid_x=6, grid_y=y, grid_w=6, grid_h=4,
            external_connection_id=sheets_conn.id,
            sheets_id=sheets_conn.sheets_spreadsheet_id,
            # Include header row so first response row is column names
            sheets_range='Class Data!A1:F',
            chart_theme='corporate', show_data_value=True, hide_legend=False,
            data_format='exact', precision_digits=1,
            background_color='#ffffff', font_color='#212529',
            unit=base_display['unit'], unit_position=base_display['unit_position'],
            auto_update_type='5m',
            visual_config=json.dumps({
                'source': 'sheets',
                'spreadsheet_id': sheets_conn.sheets_spreadsheet_id,
                'range': 'Class Data!A1:F',
            }),
        ))
        y += 4

        # Misc: todo + iframe + odoo view
        specs.append(dict(
            name=f"{cfg['category']} checklist",
            item_type='todo', data_calculation_type='custom',
            grid_x=0, grid_y=y, grid_w=6, grid_h=3,
            background_color='#fffde7', font_color='#212529',
        ))
        specs.append(dict(
            name="Iframe help",
            item_type='iframe', data_calculation_type='custom',
            grid_x=6, grid_y=y, grid_w=6, grid_h=3,
            iframe_url='https://www.odoo.com/documentation/19.0/',
            background_color='#ffffff',
        ))
        y += 3
        if window_action:
            specs.append(dict(
                name=f"Odoo View: {cfg['category']}",
                item_type='odoo_view', data_calculation_type='custom',
                grid_x=0, grid_y=y, grid_w=12, grid_h=5,
                odoo_action_id=window_action.id,
            ))

        # Create items
        created = Item.browse()
        special_types = ('todo', 'iframe', 'odoo_view')
        external_calcs = ('sql', 'api', 'excel', 'csv', 'scrape', 'sheets')
        for seq, spec in enumerate(specs, start=1):
            item_type = spec.get('item_type')
            calc = spec.get('data_calculation_type') or 'custom'
            vals = {
                'dashboard_id': dash.id,
                'sequence': seq,
                'domain': cfg.get('domain') or '[]',
                'model_id': False,
            }
            for key, value in spec.items():
                if value is False or value is None:
                    continue
                vals[key] = value
            for m2m in ('measure_field_ids', 'measure_field_2_ids', 'list_view_field_ids'):
                if vals.get(m2m) is False:
                    vals.pop(m2m, None)

            if item_type in special_types:
                vals['model_id'] = False
                vals['data_calculation_type'] = 'custom'
            elif calc in external_calcs:
                vals['model_id'] = False
            else:
                vals['model_id'] = model.id
                vals['data_calculation_type'] = 'custom'

            try:
                item = Item.create(vals)
            except Exception:
                _logger.exception(
                    "Failed to seed dashboard item %r on %s",
                    vals.get('name'), cfg['dashboard_name'],
                )
                continue
            created |= item

            # Segment colors on first pie
            if item.item_type == 'pie' and group:
                Color.create([
                    {'item_id': item.id, 'segment_name': 'draft', 'color': '#90caf9'},
                    {'item_id': item.id, 'segment_name': 'sale', 'color': '#66bb6a'},
                    {'item_id': item.id, 'segment_name': 'done', 'color': '#43a047'},
                    {'item_id': item.id, 'segment_name': 'posted', 'color': '#7e57c2'},
                    {'item_id': item.id, 'segment_name': 'purchase', 'color': '#ffa726'},
                    {'item_id': item.id, 'segment_name': 'assigned', 'color': '#29b6f6'},
                ])

            # Extra series from line model on Bar+Line
            if item.item_type == 'barLine' and line_model and line_measure:
                Source.create({
                    'name': f"{cfg['line_model']} series",
                    'item_id': item.id,
                    'model_id': line_model.id,
                    'domain': '[]',
                    'data_type': 'sum',
                    'measure_field_id': line_measure.id,
                    'group_by_field_id': False,
                    'series_chart_type': 'line',
                    'sequence': 20,
                })

            # Target lines on KPI
            if item.item_type == 'kpi' and item.enable_target:
                today = fields.Date.context_today(self)
                self.env['dynamic.dashboard.target.line'].sudo().create({
                    'item_id': item.id,
                    'date_start': today.replace(month=1, day=1),
                    'date_end': today.replace(month=12, day=31),
                    'target_value': item.standard_target_value or 100000,
                })

        todo = created.filtered(lambda i: i.item_type == 'todo')[:1]
        if todo:
            Todo.search([('dashboard_item_id', '=', todo.id)]).unlink()
            Todo.create([
                {'name': f'Review {cfg["category"]} KPI targets', 'dashboard_item_id': todo.id, 'is_done': False},
                {'name': 'Replace Google Sheets API key for live Sheets item', 'dashboard_item_id': todo.id, 'is_done': False},
                {'name': 'Validate SQL item against production DB', 'dashboard_item_id': todo.id, 'is_done': True},
                {'name': 'Enable Edit Layout and rearrange widgets', 'dashboard_item_id': todo.id, 'is_done': False},
            ])

        return dash
