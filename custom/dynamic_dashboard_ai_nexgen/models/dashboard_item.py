# Copyright (C) NexGen Solutions
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval
import datetime
import json
import re
from dateutil.relativedelta import relativedelta
from .l10n_utils import serialize_currency, resolve_display_currency
from .constraints_utils import assert_hex_color, assert_domain

class DynamicDashboardTodo(models.Model):
    _name = 'dynamic.dashboard.todo'
    _description = 'Dashboard Todo Item'
    _check_company_auto = True

    name = fields.Char(string='Task', required=True, translate=True)
    dashboard_item_id = fields.Many2one(
        'dynamic.dashboard.item', string='Dashboard Item', ondelete='cascade',
        check_company=True,
    )
    is_done = fields.Boolean(string='Done', default=False)
    company_id = fields.Many2one(
        'res.company', string='Company', related='dashboard_item_id.company_id',
        store=True, index=True,
    )

class DynamicDashboardItemColor(models.Model):
    _name = 'dynamic.dashboard.item.color'
    _description = 'Dashboard Item Segment Color'
    _check_company_auto = True

    _segment_uniq = models.Constraint(
        'UNIQUE(item_id, segment_name)',
        'Segment color names must be unique per dashboard item.',
    )

    item_id = fields.Many2one(
        'dynamic.dashboard.item', string='Dashboard Item', ondelete='cascade',
        check_company=True,
    )
    segment_name = fields.Char(string='Segment Name', required=True, help="Exact name of the label/segment (e.g., 'Draft', 'Done')")
    color = fields.Char(string='Color', required=True, default='#4A90E2', help="Hex color code")
    company_id = fields.Many2one(
        'res.company', string='Company', related='item_id.company_id', store=True, index=True,
    )

    @api.constrains('color')
    def _check_color(self):
        for rec in self:
            assert_hex_color(rec.color, _('Segment Color'))

import json

class DynamicDashboardItem(models.Model):
    _name = 'dynamic.dashboard.item'
    _description = 'Dynamic Dashboard Item'
    _check_company_auto = True

    _grid_x_positive = models.Constraint(
        'CHECK(grid_x >= 0)',
        'Grid X must be greater than or equal to 0.',
    )
    _grid_y_positive = models.Constraint(
        'CHECK(grid_y >= 0)',
        'Grid Y must be greater than or equal to 0.',
    )
    _grid_w_positive = models.Constraint(
        'CHECK(grid_w >= 1)',
        'Grid Width must be at least 1.',
    )
    _grid_h_positive = models.Constraint(
        'CHECK(grid_h >= 1)',
        'Grid Height must be at least 1.',
    )
    _grid_w_max = models.Constraint(
        'CHECK(grid_w <= 24)',
        'Grid Width cannot exceed 24 columns.',
    )
    _record_limit_positive = models.Constraint(
        'CHECK(record_limit IS NULL OR record_limit >= 0)',
        'Record Limit cannot be negative.',
    )
    _pagination_limit_positive = models.Constraint(
        'CHECK(pagination_limit IS NULL OR pagination_limit >= 0)',
        'Pagination Limit cannot be negative.',
    )
    _precision_digits_range = models.Constraint(
        'CHECK(precision_digits IS NULL OR (precision_digits >= 0 AND precision_digits <= 10))',
        'Decimal Precision must be between 0 and 10.',
    )
    _sql_row_limit_positive = models.Constraint(
        'CHECK(sql_row_limit IS NULL OR sql_row_limit >= 0)',
        'SQL Row Limit cannot be negative.',
    )
    _list_col_min_width_positive = models.Constraint(
        'CHECK(list_column_min_width IS NULL OR list_column_min_width >= 0)',
        'Column Min Width cannot be negative.',
    )

    def read(self, fields=None, load='_classic_read'):
        """Override read to merge user-specific preferences for item settings."""
        records = super().read(fields, load)
        return self._apply_preferences_to_records(records, fields)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None, **read_kwargs):
        """Override search_read to merge user-specific preferences, since Odoo 19 bypasses read()."""
        records = super().search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order, **read_kwargs)
        return self._apply_preferences_to_records(records, fields)

    def _apply_preferences_to_records(self, records, fields):
        if self.env.context.get('ignore_user_preferences') or not records:
            return records
            
        import json
        prefs = self.env['dynamic.dashboard.user.preference'].search([
            ('user_id', '=', self.env.user.id),
            ('item_id', 'in', [r['id'] for r in records if 'id' in r])
        ])
        if prefs:
            pref_map = {p.item_id.id: json.loads(p.preference_data or '{}') for p in prefs}
            for rec in records:
                rec_id = rec.get('id')
                if rec_id and rec_id in pref_map:
                    for k, v in pref_map[rec_id].items():
                        if not fields or k in fields:
                            rec[k] = v
        return records

    name = fields.Char(string='Item Name', required=True, translate=True)
    item_preview = fields.Char(string='Preview', compute='_compute_item_preview')

    @api.depends(
        'name', 'item_type', 'model_id', 'domain', 'measure_field_ids', 'group_by_field_id', 'kpi_id', 'analysis_id',
        'data_calculation_type', 'query', 'query_builder_data', 'date_filter_field_id', 'date_filter_selection',
        'tile_layout', 'tile_theme', 'tile_color', 'tile_icon', 'scorecard_columns', 'unit', 'unit_position', 'data_type', 'data_format',
        'list_view_layout', 'list_view_field_ids', 'list_view_type', 'record_limit', 'sort_by_field_id', 'sort_order',
        'chart_theme', 'is_stacked', 'is_stacked_100', 'hide_legend', 'legend_position',
        'show_data_value', 'show_records', 'sub_group_by_field_id',
        'show_tooltip', 'enable_animation', 'chart_animation_duration',
        'enable_zoom', 'enable_pan', 'show_scrollbar_x', 'show_scrollbar_y',
        'show_cursor', 'show_grid', 'show_export_menu', 'enable_slice_grouper',
        'enable_heat_rules', 'map_projection', 'show_map_labels', 'show_map_zoom_control',
        'map_exclude_antarctica', 'show_heat_legend', 'cursor_snap',
        'show_line_bullets', 'bullet_radius', 'line_stroke_width', 'area_fill_opacity',
        'column_corner_radius', 'column_width_percent', 'pie_radius', 'pie_inner_radius',
        'label_position', 'amcharts_ui_theme', 'force_many_body_strength',
        'force_center_strength', 'hierarchy_initial_depth', 'serpentine_level_count',
        'funnel_orientation', 'funnel_bottom_ratio', 'word_cloud_randomness',
        'slice_group_threshold',
        'show_axis_labels', 'rotate_category_labels', 'category_label_max_width',
        'axis_min', 'axis_max', 'logarithmic_scale', 'min_grid_distance',
        'chart_padding_top', 'chart_padding_right', 'chart_padding_bottom', 'chart_padding_left',
        'legend_clickable', 'legend_scrollable', 'legend_marker_size',
        'series_fill_opacity', 'column_stroke_width', 'column_stroke_opacity',
        'mask_bullets', 'connect_nulls', 'line_tension', 'step_to',
        'pie_start_angle', 'pie_end_angle', 'slice_stroke_width', 'show_slice_ticks',
        'slice_hover_scale', 'tooltip_pointer_orientation',
        'gauge_min', 'gauge_max', 'gauge_start_angle', 'gauge_end_angle',
        'hierarchy_top_depth', 'show_node_labels', 'force_link_strength', 'node_padding',
        'sankey_node_align', 'sankey_node_width', 'sankey_node_padding', 'chord_pad_angle',
        'show_flow_labels', 'word_min_font_size', 'word_max_font_size', 'word_min_length',
        'word_angles_mode', 'map_home_zoom_level', 'map_pan_x_mode', 'map_fill_opacity',
        'timeline_orientation', 'curve_distance', 'heat_min_color', 'heat_max_color',
        'show_cursor_line_x', 'show_cursor_line_y', 'chart_number_format',
        'show_category_axis', 'show_value_axis', 'scatter_fill_opacity',
        'flow_source_field_id', 'flow_target_field_id', 'word_cloud_field_id',
        'measure_open_field_id', 'measure_high_field_id', 'measure_low_field_id',
        'measure_close_field_id',
        'group_by_date_type', 'sub_group_by_date_type', 'multiplier_active', 'multiplier_value',
        'is_cumulative', 'enable_target', 'standard_target_value', 'target_view', 'measure_field_2_ids', 'todo_ids',
        'is_semi_circle', 'upload_file', 'file_label_column', 'file_value_column',
        'kpi_model_id', 'kpi_measure_field_id', 'kpi_data_type', 'kpi_domain', 'kpi_comparison',
        'formula_active', 'formula', 'background_color', 'font_color', 'currency_id',
        'number_system_id', 'precision_digits', 'api_label_key', 'api_value_key', 'sql_label_column',
        # Display tab — must invalidate form preview when these change
        'enable_drill_down', 'fill_temporal', 'pagination_limit', 'export_all_records',
        'segment_color_ids', 'segment_color_ids.segment_name', 'segment_color_ids.color',
    )
    def _compute_item_preview(self):
        for rec in self:
            if not rec.analysis_id and not rec.kpi_id and not rec.model_id and rec.data_calculation_type not in ('sql', 'api', 'excel', 'csv', 'scrape', 'sheets') and rec.item_type not in ('todo', 'iframe', 'odoo_view'):
                rec.item_preview = json.dumps({"error": "Please select a Model."})
                continue
            try:
                # Isolate preview fetches (SQL / read_group / HTTP) so errors never
                # poison the current save/write transaction.
                with rec.env.cr.savepoint(flush=False):
                    data = rec._get_item_data_dict()
                    rec.item_preview = json.dumps(data, default=str)  # default=str to handle NewId
            except Exception as e:
                rec.item_preview = json.dumps({"error": str(e)})

    dashboard_id = fields.Many2one(
        'dynamic.dashboard', string='Dashboard', required=True, ondelete='cascade',
    )
    company_id = fields.Many2one(
        'res.company', string='Company', related='dashboard_id.company_id',
        store=True, index=True,
    )
    sequence = fields.Integer(default=10)
    item_type = fields.Selection([
        ('tile', 'Tile'),
        ('kpi', 'KPI'),
        ('scorecard', 'Scorecard'),
        ('bar', 'Bar Chart'),
        ('barLine', 'Bar + Line Chart'),
        ('horizontalBar', 'Horizontal Bar Chart'),
        ('line', 'Line Chart'),
        ('area', 'Area Chart'),
        ('stepLine', 'Step Line Chart'),
        ('smoothedLine', 'Smoothed Line Chart'),
        ('waterfall', 'Waterfall Chart'),
        ('pie', 'Pie Chart'),
        ('doughnut', 'Doughnut Chart'),
        ('polarArea', 'Polar Area Chart'),
        ('radar', 'Radar Chart'),
        ('flower', 'Flower Chart'),
        ('scatter', 'Scatter Chart'),
        ('radialBar', 'Radial Bar Chart'),
        ('gauge', 'Gauge Chart'),
        ('funnel', 'Funnel Chart'),
        ('pyramid', 'Pyramid Chart'),
        ('pictorial', 'Pictorial Chart'),
        ('bullet', 'Bullet Chart'),
        ('treemap', 'Treemap'),
        ('sunburst', 'Sunburst'),
        ('forceDirected', 'Force Directed'),
        ('pack', 'Pack Chart'),
        ('tree', 'Tree Chart'),
        ('partition', 'Partition Chart'),
        ('voronoiTreemap', 'Voronoi Treemap'),
        ('sankey', 'Sankey Diagram'),
        ('chord', 'Chord Diagram'),
        ('chordDirected', 'Directed Chord'),
        ('chordNonRibbon', 'Chord (Non-Ribbon)'),
        ('arcDiagram', 'Arc Diagram'),
        ('map', 'Map View'),
        ('mapPoints', 'Map Points'),
        ('heatmap', 'Matrix Heat Map'),
        ('matrixHeatmap', 'Matrix Heat Map'),
        ('wordCloud', 'Word Cloud'),
        ('venn', 'Venn Diagram'),
        ('candlestick', 'Candlestick Chart'),
        ('ohlc', 'OHLC Chart'),
        ('timeline', 'Timeline Chart'),
        ('serpentine', 'Serpentine Timeline'),
        ('spiral', 'Spiral Timeline'),
        ('list', 'List View'),
        ('todo', 'To-Do List'),
        ('iframe', 'Iframe'),
        ('odoo_view', 'Odoo View'),
    ], string="Item Type", required=True, default='tile')

    # Form UX helpers (dynamic visibility — not stored)
    is_card_item = fields.Boolean(compute='_compute_form_ux_flags')
    is_chart_item = fields.Boolean(compute='_compute_form_ux_flags')
    is_xy_chart = fields.Boolean(compute='_compute_form_ux_flags')
    is_pie_like = fields.Boolean(compute='_compute_form_ux_flags')
    show_model_data = fields.Boolean(compute='_compute_form_ux_flags')
    show_sql_data = fields.Boolean(compute='_compute_form_ux_flags')
    show_api_data = fields.Boolean(compute='_compute_form_ux_flags')
    show_file_data = fields.Boolean(compute='_compute_form_ux_flags')
    show_scrape_data = fields.Boolean(compute='_compute_form_ux_flags')
    show_sheets_data = fields.Boolean(compute='_compute_form_ux_flags')

    @api.depends('item_type', 'data_calculation_type', 'analysis_id', 'kpi_id')
    def _compute_form_ux_flags(self):
        card = {'tile', 'kpi', 'scorecard'}
        embed = {'todo', 'iframe', 'odoo_view'}
        pie_like = {'pie', 'doughnut', 'funnel', 'pyramid', 'pictorial'}
        xy = {
            'bar', 'barLine', 'horizontalBar', 'line', 'area', 'stepLine', 'smoothedLine',
            'waterfall', 'scatter', 'bullet', 'candlestick', 'ohlc', 'heatmap', 'matrixHeatmap',
            'timeline', 'serpentine', 'spiral', 'radar', 'flower', 'polarArea', 'radialBar',
        }
        charts = xy | pie_like | {
            'gauge', 'treemap', 'sunburst', 'forceDirected', 'pack', 'tree', 'partition',
            'voronoiTreemap', 'sankey', 'chord', 'chordDirected', 'chordNonRibbon', 'arcDiagram',
            'map', 'mapPoints', 'wordCloud', 'venn',
        }
        for rec in self:
            itype = rec.item_type or ''
            calc = rec.data_calculation_type or 'custom'
            rec.is_card_item = itype in card
            rec.is_chart_item = itype in charts
            rec.is_xy_chart = itype in xy
            rec.is_pie_like = itype in pie_like
            linked = bool(rec.analysis_id or rec.kpi_id)
            rec.show_model_data = calc == 'custom' and not linked and itype not in embed
            rec.show_sql_data = calc == 'sql'
            rec.show_api_data = calc == 'api'
            rec.show_file_data = calc in ('excel', 'csv')
            rec.show_scrape_data = calc == 'scrape'
            rec.show_sheets_data = calc == 'sheets'

    analysis_id = fields.Many2one(
        'dynamic.dashboard.analysis',
        string='Analysis',
        ondelete='set null',
        check_company=True,
        help='When set, data and visual defaults come from the reusable Analysis.',
    )
    kpi_id = fields.Many2one(
        'dynamic.dashboard.kpi',
        string='KPI Definition',
        ondelete='set null',
        check_company=True,
        help='Bind this item to a hierarchical KPI definition.',
    )
    visual_config = fields.Text(string='Visual Config JSON', default='{}')
    iframe_url = fields.Char(string='Iframe URL')
    odoo_action_id = fields.Many2one('ir.actions.act_window', string='Embedded Odoo Action')
    scrape_url = fields.Char(string='Scrape URL')
    scrape_json_path = fields.Char(string='Scrape JSON Path')
    sheets_id = fields.Char(string='Google Sheet ID')
    sheets_range = fields.Char(string='Sheet Range', default='A:Z')
    list_show_grand_total = fields.Boolean(string='Show Grand Total', default=False)
    list_column_min_width = fields.Integer(string='Column Min Width (px)', default=80)
    
    auto_update_type = fields.Selection([
        ('none', 'None'),
        ('realtime', 'Realtime (5 Seconds + Bus)'),
        ('15s', 'Every 15 Seconds'),
        ('30s', 'Every 30 Seconds'),
        ('1m', 'Every 1 Minute'),
        ('5m', 'Every 5 Minutes')
    ], string="Auto Update", default='none')

    # Common fields
    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        ondelete='cascade',
        domain="[('transient', '=', False)]",
    )
    model_name = fields.Char(string='Model Name', related='model_id.model', readonly=True)
    domain = fields.Char(string='Domain', default='[]')
    allowed_group_ids = fields.Many2many(
        'res.groups',
        string='Allowed Groups',
        help='If specified, only users in these groups can see this item.'
    )
    enable_drill_down = fields.Boolean(
        string='Enable Drill Down',
        default=True,
        help='Click chart segments to filter/drill; use breadcrumb to drill up.',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        help='Display currency for monetary values. Defaults to the company currency. '
             'Supports multi-company / multi-currency formatting in all layouts.',
    )
    number_system_id = fields.Many2one(
        'dynamic.dashboard.number.system',
        string='Custom Number System',
        check_company=True,
        help='Overrides Data Format when set.',
    )
    precision_digits = fields.Integer(
        string='Decimal Precision',
        default=2,
        help='Number of decimal places when not using a currency or compact format.',
    )
    fill_temporal = fields.Boolean(
        string='Fill Temporal Gaps',
        default=False,
        help='For date-grouped charts, insert missing periods with zero values.',
    )
    pagination_limit = fields.Integer(
        string='Pagination Limit',
        default=10,
        help='Rows per page for list views (0 = show all loaded rows).',
    )
    export_all_records = fields.Boolean(
        string='Export All Records',
        default=False,
        help='When exporting list/CSV, ignore record limit and export all matching rows.',
    )
    custom_date_filter_id = fields.Many2one(
        'dynamic.dashboard.date.filter',
        string='Custom Date Filter',
        check_company=True,
        help='Used when Item Date Filter is set to Custom Defined.',
    )
    domain_extension = fields.Char(
        string='Domain Extension',
        default='[]',
        help='Extra domain AND-ed with the main domain (supports %UID and %MYCOMPANY).',
    )
    source_ids = fields.One2many(
        'dynamic.dashboard.item.source',
        'item_id',
        string='Additional Data Sources',
        help='Extra series from other models, merged onto the same chart.',
        copy=True,
    )
    # Scatter chart axes
    is_scatter_group = fields.Boolean(
        string='Scatter Group By',
        default=True,
        help='If enabled, aggregate X/Y by Group By; otherwise each record is a point.',
    )
    scatter_measure_x_id = fields.Many2one(
        'ir.model.fields',
        string='Scatter Measure X',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'in', ['integer', 'float', 'monetary']), ('name', '!=', 'id')]",
    )
    scatter_measure_y_id = fields.Many2one(
        'ir.model.fields',
        string='Scatter Measure Y',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'in', ['integer', 'float', 'monetary']), ('name', '!=', 'id')]",
    )
    
    # Todo fields
    todo_ids = fields.One2many('dynamic.dashboard.todo', 'dashboard_item_id', string='To Do Items')
    
    # Tile settings
    tile_color = fields.Char(string='Tile Background Color', default='#FFFFFF')
    tile_icon = fields.Selection(
        selection='_selection_tile_icons',
        string='Icon',
        default='fa-bar-chart',
        required=True,
    )
    tile_layout = fields.Selection([
        ('layout1', 'Accent Left'),
        ('layout2', 'Icon Left'),
        ('layout3', 'Centered'),
        ('layout4', 'Gradient Hero'),
        ('layout5', 'Split Band'),
        ('layout6', 'Soft Float'),
        ('layout7', 'Value First'),
        ('layout8', 'Pill Header'),
    ], string="Card Layout", default='layout1',
       help="Visual layout for Tile, KPI, and Scorecard cards.")
    tile_theme = fields.Selection([
        ('custom', 'Custom Color'),
        ('ocean', 'Ocean Blue'),
        ('sky', 'Sky'),
        ('indigo', 'Indigo'),
        ('violet', 'Violet'),
        ('plum', 'Plum'),
        ('berry', 'Berry Rose'),
        ('rose', 'Rose'),
        ('coral', 'Warm Coral'),
        ('tangerine', 'Tangerine'),
        ('amber', 'Amber Glow'),
        ('sunflower', 'Sunflower'),
        ('forest', 'Forest Green'),
        ('emerald', 'Emerald'),
        ('mint', 'Fresh Mint'),
        ('teal', 'Teal'),
        ('slate', 'Cool Slate'),
        ('graphite', 'Graphite'),
        ('navy', 'Navy'),
        ('midnight', 'Midnight'),
    ], string="Card Theme", default='ocean',
       help="Preset color theme for Tile / KPI / Scorecard. Custom uses Tile Color.")
    scorecard_columns = fields.Selection([
        ('auto', 'Auto'),
        ('2', '2 Columns'),
        ('3', '3 Columns'),
        ('4', '4 Columns'),
    ], string="Scorecard Columns", default='auto')
    
    unit = fields.Selection(
        selection='_selection_units',
        string='Data Unit',
        help='Display unit shown next to tile/KPI values.',
    )
    unit_position = fields.Selection([('prefix', 'Prefix'), ('suffix', 'Suffix')], string="Unit Position", default='suffix')
    
    # Data Fields
    data_calculation_type = fields.Selection([
        ('custom', 'Odoo Model'),
        ('sql', 'Custom SQL Query'),
        ('api', 'External API'),
        ('excel', 'Excel File'),
        ('csv', 'CSV File'),
        ('scrape', 'Web Scrape'),
        ('sheets', 'Google Sheets'),
    ], string="Data Calculation Type", default='custom')
    external_connection_id = fields.Many2one(
        'dynamic.dashboard.connection',
        string='External Connection',
        check_company=True,
    )
    use_query_builder = fields.Boolean(
        string='Use Visual Query Builder',
        help='Build the SQL Query visually instead of typing manual SQL.'
    )
    query_builder_data = fields.Text(
        string='Query Builder State',
        help='Stores the JSON state of the visual query builder.'
    )
    query = fields.Text(
        string='Custom SQL Query',
        help="SELECT-only. Placeholders: {start_date}, {end_date}, {uid}, {company_id} "
             "(also %START_DATE%, %END_DATE%, %UID%, %COMPANY_ID%).",
    )
    use_materialized_view = fields.Boolean(
        string='Use Materialized View',
        default=False,
        help="If checked, this query will be cached in PostgreSQL as a Materialized View and refreshed on a schedule. Drastically improves dashboard load times for complex queries. Warning: dynamic user/company variables will be cached as-is.",
    )
    mview_status = fields.Selection(
        [('none', 'Not Created'), ('active', 'Active'), ('error', 'Error')],
        string="MView Status",
        default='none',
        readonly=True,
    )
    sql_row_limit = fields.Integer(
        string='SQL Row Limit',
        default=5000,
        help='Maximum rows returned. Applied as LIMIT when the query has none.',
    )
    sql_label_column = fields.Selection(
        selection='_selection_sql_label_columns',
        string='SQL Label Column',
        help='Optional column name used as chart labels / first list key. Defaults to the first column.',
    )
    api_label_key = fields.Selection(
        selection='_selection_api_keys',
        string='API Label Key',
        help="Key in the JSON array objects to use for chart labels.",
    )
    api_value_key = fields.Selection(
        selection='_selection_api_keys',
        string='API Value Key',
        help="Key in the JSON array objects to use for chart values.",
    )

    # Excel / CSV upload
    upload_file = fields.Binary(string='Upload File', attachment=True)
    upload_filename = fields.Char(string='Filename')
    file_label_column = fields.Selection(
        selection='_selection_file_columns',
        string='Label Column',
        help="Column header used for labels/categories (charts).",
    )
    file_value_column = fields.Selection(
        selection='_selection_file_columns',
        string='Value Column',
        help="Column header used for numeric values.",
    )
    file_columns_preview = fields.Char(
        string='Detected Columns',
        compute='_compute_file_columns_preview',
        help="Columns detected in the uploaded file.",
    )

    list_view_layout = fields.Selection([
        ('layout1', 'Table'),
        ('layout2', 'Card Grid'),
        ('layout3', 'Compact Rows'),
    ], string="List View Layout", default='layout1')
    list_view_type = fields.Selection([
        ('ungrouped', 'Ungrouped'),
        ('grouped', 'Grouped'),
    ], string="List View Type", default='ungrouped',
       help="Ungrouped shows raw records. Grouped aggregates measures by the Group By field.")

    data_type = fields.Selection([('sum', 'Sum'), ('count', 'Count'), ('average', 'Average')], string='Data Type', default='sum')
    data_format = fields.Selection([('exact', 'Exact'), ('english', 'English (K, M, B)'), ('indian', 'Indian (L, Cr)')], string="Data Format", default="exact")
    
    measure_field_ids = fields.Many2many(
        'ir.model.fields', 'dynamic_item_measure_rel', 'item_id', 'field_id',
        string="Measure Fields",
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'in', ['integer', 'float', 'monetary']), ('name', '!=', 'id')]",
    )
    measure_field_2_ids = fields.Many2many(
        'ir.model.fields', 'dynamic_item_measure_2_rel', 'item_id', 'field_id',
        string="Secondary Measure Fields",
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'in', ['integer', 'float', 'monetary']), ('name', '!=', 'id')]",
    )
    group_by_field_id = fields.Many2one(
        'ir.model.fields',
        string='Group By Field',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'not in', ['one2many', 'many2many', 'binary', 'html', 'json', 'properties'])]",
    )
    list_view_field_ids = fields.Many2many(
        'ir.model.fields', 'dynamic_item_list_fields_rel', 'item_id', 'field_id',
        string="List View Fields",
        domain="[('model_id', '=', model_id), ('ttype', 'not in', ['one2many', 'many2many', 'binary', 'html', 'json'])]",
    )
    
    # Multiplier, Cumulative, Formula
    multiplier_active = fields.Boolean(string="Enable Multiplier", default=False)
    multiplier_value = fields.Float(string="Multiplier Value", default=1.0)
    is_cumulative = fields.Boolean(string="Cumulative Data", default=False)
    is_semi_circle = fields.Boolean(
        string="Semi Circle Chart",
        default=False,
        help="Render pie/doughnut charts as a semi-circle (half gauge).",
    )
    formula_active = fields.Boolean(
        string="Enable Formula",
        default=False,
        help="Compute the result from a formula using {m1}, {m2}, and {count}.",
    )
    formula = fields.Char(
        string="Formula",
        help="Example: {m1}/{m2}*100  — m1 = first measure, m2 = second measure (or KPI model 2 value), count = record count.",
    )

    # KPI second model comparison
    kpi_model_id = fields.Many2one('ir.model', string='KPI Comparison Model', ondelete='cascade')
    kpi_model_name = fields.Char(string='KPI Model Name', related='kpi_model_id.model', readonly=True)
    kpi_data_type = fields.Selection(
        [('sum', 'Sum'), ('count', 'Count'), ('average', 'Average')],
        string='KPI Model 2 Data Type',
        default='sum',
    )
    kpi_measure_field_id = fields.Many2one(
        'ir.model.fields',
        string='KPI Model 2 Measure',
        domain="[('model_id', '=', kpi_model_id), ('store', '=', True), ('ttype', 'in', ['integer', 'float', 'monetary']), ('name', '!=', 'id')]",
    )
    kpi_domain = fields.Char(string='KPI Model 2 Domain', default='[]')
    kpi_date_filter_field_id = fields.Many2one(
        'ir.model.fields',
        string='KPI Model 2 Date Field',
        domain="[('model_id', '=', kpi_model_id), ('store', '=', True), ('ttype', 'in', ['date', 'datetime'])]",
    )
    kpi_date_filter_selection = fields.Selection([
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
        ('custom', 'Custom Date Range'),
    ], string='KPI Model 2 Date Filter', default='none')
    kpi_item_start_date = fields.Datetime(string="KPI Model 2 Start Date")
    kpi_item_end_date = fields.Datetime(string="KPI Model 2 End Date")
    kpi_comparison = fields.Selection([
        ('none', 'Show Both Values'),
        ('percentage', 'Percentage (A/B * 100)'),
        ('ratio', 'Ratio (A/B)'),
        ('sum', 'Sum (A+B)'),
        ('difference', 'Difference (A-B)'),
    ], string="KPI Comparison Mode", default='percentage',
       help="How to combine primary KPI value (A) with secondary model value (B).")
    
    # Advanced Data
    group_by_date_type = fields.Selection([
        ('minute', 'Minute'), ('hour', 'Hour'), ('day', 'Day'), ('week', 'Week'),
        ('month', 'Month'), ('quarter', 'Quarter'), ('year', 'Year')
    ], string="Group By Date Type", default="month")
    sub_group_by_field_id = fields.Many2one(
        'ir.model.fields',
        string='Sub Group By Field',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'not in', ['one2many', 'many2many', 'binary', 'html', 'json', 'properties'])]",
    )
    sub_group_by_date_type = fields.Selection([
        ('minute', 'Minute'), ('hour', 'Hour'), ('day', 'Day'), ('week', 'Week'),
        ('month', 'Month'), ('quarter', 'Quarter'), ('year', 'Year')
    ], string="Sub Group By Date Type", default="month")
    
    sort_by_field_id = fields.Many2one(
        'ir.model.fields',
        string='Sort By Field',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'not in', ['one2many', 'many2many', 'binary', 'html', 'json'])]",
    )
    sort_order = fields.Selection([('asc', 'Ascending'), ('desc', 'Descending')], string="Sort Order", default="desc")
    record_limit = fields.Integer(string="Record Limit", default=0)
    
    # Target
    enable_target = fields.Boolean(string="Enable Target")
    standard_target_value = fields.Float(string="Standard Target Value")
    target_line_ids = fields.One2many('dynamic.dashboard.target.line', 'item_id', string='Dynamic Target Lines')
    target_view = fields.Selection([('number', 'Number'), ('progress_bar', 'Progress Bar')], string="Target View", default='number')
    # Custom Actions
    action_type = fields.Selection([
        ('none', 'No Action (Default List)'),
        ('window', 'Window Action'),
        ('client', 'Client Action'),
        ('url', 'URL')
    ], string='Click Action Type', default='none')
    action_id = fields.Many2one('ir.actions.act_window', string='Window Action')
    client_action_id = fields.Many2one('ir.actions.client', string='Client Action')
    action_url = fields.Char(string='Action URL')

    # Display Options
    chart_theme = fields.Selection([
        ('default', 'Default'),
        ('cool', 'Cool'),
        ('warm', 'Warm'),
        ('neon', 'Neon'),
        ('pastel', 'Pastel'),
        ('corporate', 'Corporate'),
        ('vibrant', 'Vibrant'),
        ('ocean', 'Ocean'),
        ('sunset', 'Sunset'),
    ], string="Chart Theme", default="default")
    is_stacked = fields.Boolean(string="Stacked Bar Chart", default=False)
    is_stacked_100 = fields.Boolean(
        string="100% Stacked",
        default=False,
        help="Stack series to 100% of each category (relative composition).",
    )
    hide_legend = fields.Boolean(string="Hide Chart Legend", default=False)
    legend_position = fields.Selection([
        ('bottom', 'Bottom'),
        ('top', 'Top'),
        ('left', 'Left'),
        ('right', 'Right'),
        ('none', 'Hidden'),
    ], string="Legend Position", default='bottom')
    show_data_value = fields.Boolean(string="Show Data Value", default=True)
    show_records = fields.Boolean(string="Show Records", default=False)
    show_tooltip = fields.Boolean(string="Show Tooltip", default=True)
    enable_animation = fields.Boolean(string="Enable Animation", default=True)
    chart_animation_duration = fields.Integer(string="Animation Duration (ms)", default=800)
    enable_zoom = fields.Boolean(string="Enable Zoom", default=True)
    enable_pan = fields.Boolean(string="Enable Pan", default=True)
    show_scrollbar_x = fields.Boolean(
        string="Horizontal Zoom Bar",
        default=False,
        help="Show the horizontal zoom/scrollbar under the chart for zoom in and zoom out.",
    )
    show_scrollbar_y = fields.Boolean(string="Show Y Scrollbar", default=False)
    show_cursor = fields.Boolean(string="Show Cursor", default=True)
    show_grid = fields.Boolean(string="Show Grid Lines", default=True)
    show_export_menu = fields.Boolean(
        string="Show Chart Export Menu",
        default=False,
        help="Show amCharts export menu (PNG/CSV/…) on the chart.",
    )
    enable_slice_grouper = fields.Boolean(
        string="Group Small Slices",
        default=False,
        help="Group tiny pie slices into an Other slice.",
    )
    enable_heat_rules = fields.Boolean(
        string="Heat Coloring",
        default=False,
        help="Color columns/polygons by value intensity.",
    )
    map_projection = fields.Selection([
        ('mercator', 'Mercator'),
        ('orthographic', 'Orthographic'),
        ('equirectangular', 'Equirectangular'),
        ('naturalEarth1', 'Natural Earth'),
    ], string="Map Projection", default='mercator')
    show_map_labels = fields.Boolean(string="Show Map Labels", default=False)
    show_map_zoom_control = fields.Boolean(string="Show Map Zoom Control", default=True)
    map_exclude_antarctica = fields.Boolean(string="Exclude Antarctica", default=True)
    show_heat_legend = fields.Boolean(string="Show Heat Legend", default=True)
    cursor_snap = fields.Boolean(string="Cursor Snap to Series", default=False)
    show_line_bullets = fields.Boolean(string="Show Line Bullets", default=True)
    bullet_radius = fields.Integer(string="Bullet Radius", default=5)
    line_stroke_width = fields.Float(string="Line Stroke Width", default=2.75)
    area_fill_opacity = fields.Float(string="Area Fill Opacity", default=0.22)
    column_corner_radius = fields.Integer(string="Column Corner Radius", default=6)
    column_width_percent = fields.Integer(string="Column Width %", default=68)
    pie_radius = fields.Integer(string="Pie Radius %", default=70)
    pie_inner_radius = fields.Integer(
        string="Inner Radius %",
        default=50,
        help="Used for doughnut / radial / flower charts.",
    )
    label_position = fields.Selection([
        ('auto', 'Auto'),
        ('inside', 'Inside'),
        ('outside', 'Outside'),
        ('none', 'Hidden'),
    ], string="Slice / Label Position", default='auto')
    amcharts_ui_theme = fields.Selection([
        ('animated', 'Animated'),
        ('dark', 'Dark'),
        ('material', 'Material'),
        ('none', 'None'),
    ], string="amCharts UI Theme", default='animated')
    force_many_body_strength = fields.Float(string="Force Many-Body Strength", default=-15.0)
    force_center_strength = fields.Float(string="Force Center Strength", default=0.5)
    hierarchy_initial_depth = fields.Integer(string="Hierarchy Initial Depth", default=2)
    serpentine_level_count = fields.Integer(string="Serpentine Levels", default=3)
    funnel_orientation = fields.Selection([
        ('vertical', 'Vertical'),
        ('horizontal', 'Horizontal'),
    ], string="Funnel Orientation", default='vertical')
    funnel_bottom_ratio = fields.Float(string="Funnel Bottom Ratio", default=0.1)
    word_cloud_randomness = fields.Float(string="Word Cloud Randomness", default=0.1)
    slice_group_threshold = fields.Float(
        string="Slice Group Threshold %",
        default=5.0,
        help="When Group Small Slices is on, slices below this %% of total become Other.",
    )

    # ---- Extended amCharts 5 dynamic options ----
    show_axis_labels = fields.Boolean(string="Show Axis Labels", default=True)
    rotate_category_labels = fields.Boolean(string="Rotate Category Labels", default=False)
    category_label_max_width = fields.Integer(string="Category Label Max Width", default=110)
    axis_min = fields.Float(string="Axis Min (blank=auto)", default=False)
    axis_max = fields.Float(string="Axis Max (blank=auto)", default=False)
    logarithmic_scale = fields.Boolean(string="Logarithmic Scale", default=False)
    min_grid_distance = fields.Integer(string="Min Grid Distance", default=30)
    chart_padding_top = fields.Integer(string="Padding Top", default=12)
    chart_padding_right = fields.Integer(string="Padding Right", default=16)
    chart_padding_bottom = fields.Integer(string="Padding Bottom", default=8)
    chart_padding_left = fields.Integer(string="Padding Left", default=8)
    legend_clickable = fields.Boolean(string="Legend Clickable", default=True)
    legend_scrollable = fields.Boolean(string="Scrollable Legend", default=True)
    legend_marker_size = fields.Integer(string="Legend Marker Size", default=11)
    series_fill_opacity = fields.Float(string="Series Fill Opacity", default=1.0)
    column_stroke_width = fields.Float(string="Column Stroke Width", default=0.0)
    column_stroke_opacity = fields.Float(string="Column Stroke Opacity", default=0.0)
    mask_bullets = fields.Boolean(string="Mask Bullets Outside Plot", default=True)
    connect_nulls = fields.Boolean(string="Connect Null Values", default=True)
    line_tension = fields.Float(
        string="Line Tension",
        default=0.5,
        help="Smoothing tension for smoothed line charts (0=straight, 1=max curve).",
    )
    step_to = fields.Selection([
        ('left', 'Left / Start'),
        ('center', 'Center / Middle'),
        ('right', 'Right / End'),
    ], string="Step Position", default='left')
    pie_start_angle = fields.Integer(string="Pie Start Angle", default=-90)
    pie_end_angle = fields.Integer(string="Pie End Angle", default=270)
    slice_stroke_width = fields.Float(string="Slice Stroke Width", default=2.0)
    show_slice_ticks = fields.Boolean(string="Show Slice Ticks", default=True)
    slice_hover_scale = fields.Float(string="Slice Hover Scale", default=1.04)
    tooltip_pointer_orientation = fields.Selection([
        ('vertical', 'Vertical'),
        ('horizontal', 'Horizontal'),
        ('left', 'Left'),
        ('right', 'Right'),
        ('up', 'Up'),
        ('down', 'Down'),
    ], string="Tooltip Pointer", default='vertical')
    gauge_min = fields.Float(string="Gauge Min", default=0.0)
    gauge_max = fields.Float(
        string="Gauge Max (0=auto)",
        default=0.0,
        help="Leave 0 to auto-scale from data / target.",
    )
    gauge_start_angle = fields.Integer(string="Gauge Start Angle", default=-210)
    gauge_end_angle = fields.Integer(string="Gauge End Angle", default=30)
    hierarchy_top_depth = fields.Integer(string="Hierarchy Top Depth", default=1)
    show_node_labels = fields.Boolean(string="Show Node Labels", default=True)
    force_link_strength = fields.Float(string="Force Link Strength", default=0.5)
    node_padding = fields.Integer(string="Node Padding", default=4)
    sankey_node_align = fields.Selection([
        ('justify', 'Justify'),
        ('left', 'Left'),
        ('right', 'Right'),
        ('center', 'Center'),
    ], string="Sankey Node Align", default='justify')
    sankey_node_width = fields.Integer(string="Sankey Node Width", default=10)
    sankey_node_padding = fields.Integer(string="Sankey Node Padding", default=8)
    chord_pad_angle = fields.Float(string="Chord Pad Angle", default=0.02)
    show_flow_labels = fields.Boolean(string="Show Flow Labels", default=True)
    word_min_font_size = fields.Integer(string="Word Min Font Size", default=8)
    word_max_font_size = fields.Integer(string="Word Max Font Size", default=48)
    word_min_length = fields.Integer(string="Word Min Length", default=2)
    word_angles_mode = fields.Selection([
        ('horizontal', 'Horizontal'),
        ('mixed', 'Mixed 0/-90'),
        ('vertical', 'Vertical'),
    ], string="Word Angles", default='mixed')
    map_home_zoom_level = fields.Float(string="Map Home Zoom", default=1.0)
    map_pan_x_mode = fields.Selection([
        ('rotateX', 'Rotate X'),
        ('translateX', 'Translate X'),
        ('none', 'None'),
    ], string="Map Pan X Mode", default='rotateX')
    map_fill_opacity = fields.Float(string="Map Fill Opacity", default=1.0)
    timeline_orientation = fields.Selection([
        ('horizontal', 'Horizontal'),
        ('vertical', 'Vertical'),
    ], string="Timeline Orientation", default='horizontal')
    curve_distance = fields.Integer(string="Curve Distance", default=40)
    heat_min_color = fields.Char(string="Heat Min Color", default='#eff6ff')
    heat_max_color = fields.Char(string="Heat Max Color", default='#1d4ed8')
    show_cursor_line_x = fields.Boolean(string="Show Cursor X Line", default=True)
    show_cursor_line_y = fields.Boolean(string="Show Cursor Y Line", default=False)
    chart_number_format = fields.Char(
        string="Chart Number Format",
        default='#,###.##',
        help="amCharts number format pattern, e.g. #,###.## or #.0a",
    )
    show_category_axis = fields.Boolean(string="Show Category Axis", default=True)
    show_value_axis = fields.Boolean(string="Show Value Axis", default=True)
    scatter_fill_opacity = fields.Float(string="Scatter Fill Opacity", default=0.85)

    flow_source_field_id = fields.Many2one(
        'ir.model.fields',
        string='Flow Source Field',
        domain="[('model_id', '=', model_id), ('store', '=', True), "
               "('ttype', 'in', ['many2one', 'selection', 'char', 'many2many'])]",
        help='Source node field for Sankey / Chord / Arc diagrams.',
    )
    flow_target_field_id = fields.Many2one(
        'ir.model.fields',
        string='Flow Target Field',
        domain="[('model_id', '=', model_id), ('store', '=', True), "
               "('ttype', 'in', ['many2one', 'selection', 'char', 'many2many'])]",
        help='Target node field for Sankey / Chord / Arc diagrams.',
    )
    word_cloud_field_id = fields.Many2one(
        'ir.model.fields',
        string='Word Cloud Text Field',
        domain="[('model_id', '=', model_id), ('store', '=', True), "
               "('ttype', 'in', ['char', 'text', 'html'])]",
    )
    measure_open_field_id = fields.Many2one(
        'ir.model.fields',
        string='OHLC Open',
        domain="[('model_id', '=', model_id), ('store', '=', True), "
               "('ttype', 'in', ['integer', 'float', 'monetary'])]",
    )
    measure_high_field_id = fields.Many2one(
        'ir.model.fields',
        string='OHLC High',
        domain="[('model_id', '=', model_id), ('store', '=', True), "
               "('ttype', 'in', ['integer', 'float', 'monetary'])]",
    )
    measure_low_field_id = fields.Many2one(
        'ir.model.fields',
        string='OHLC Low',
        domain="[('model_id', '=', model_id), ('store', '=', True), "
               "('ttype', 'in', ['integer', 'float', 'monetary'])]",
    )
    measure_close_field_id = fields.Many2one(
        'ir.model.fields',
        string='OHLC Close',
        domain="[('model_id', '=', model_id), ('store', '=', True), "
               "('ttype', 'in', ['integer', 'float', 'monetary'])]",
    )
    segment_color_ids = fields.One2many('dynamic.dashboard.item.color', 'item_id', string='Custom Segment Colors')
    
    # Card Styling
    background_color = fields.Char(string='Card Background Color', default='#ffffff')
    font_color = fields.Char(string='Font Color', default='#212529')
    
    # Grid Positioning
    grid_x = fields.Integer(string="Grid X", default=0)
    grid_y = fields.Integer(string="Grid Y", default=0)
    grid_w = fields.Integer(string='Grid Width', default=6, required=True)
    grid_h = fields.Integer(string='Grid Height', default=4, required=True)

    @api.model
    def _grid_size_for_type(self, item_type):
        """Recommended GridStack size (w, h) on a 12-column My Dashboard board."""
        sizes = {
            'tile': (3, 2),
            'kpi': (3, 2),
            'scorecard': (6, 3),
            'gauge': (3, 3),
            'radialBar': (3, 3),
            'bullet': (6, 3),
            'pie': (4, 4),
            'doughnut': (4, 4),
            'polarArea': (4, 4),
            'radar': (4, 4),
            'flower': (4, 4),
            'venn': (4, 4),
            'pictorial': (4, 4),
            'spiral': (4, 4),
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
            'funnel': (4, 5),
            'pyramid': (4, 5),
            'treemap': (6, 5),
            'sunburst': (6, 5),
            'forceDirected': (6, 5),
            'pack': (6, 5),
            'tree': (6, 5),
            'partition': (6, 5),
            'voronoiTreemap': (6, 5),
            'sankey': (12, 5),
            'chord': (6, 5),
            'chordDirected': (6, 5),
            'chordNonRibbon': (6, 5),
            'arcDiagram': (12, 4),
            'map': (6, 5),
            'mapPoints': (6, 5),
            'heatmap': (6, 5),
            'matrixHeatmap': (6, 5),
            'timeline': (12, 4),
            'serpentine': (12, 4),
            'list': (6, 5),
            'todo': (6, 4),
            'iframe': (6, 5),
            'odoo_view': (12, 6),
        }
        return sizes.get(item_type or 'bar', (6, 4))

    @api.model
    def _layout_priority_for_type(self, item_type):
        """Lower = higher on the dashboard (metrics first, embeds last)."""
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
    def _find_free_grid_slot(self, w, h, occupied=None, cols=12, fill_row=True):
        """Skyline packer: place (w,h) in the first free slot (top-most, then left-most).

        If ``fill_row`` and leftover columns in the chosen row are smaller than a
        minimal tile (3), stretch width to fill the row and avoid orphan blank space.
        """
        cols = max(1, int(cols))
        w = max(1, min(int(w), cols))
        h = max(1, int(h))
        occupied = list(occupied or [])

        heights = [0] * cols
        for ox, oy, ow, oh in occupied:
            for x in range(max(0, ox), min(cols, ox + ow)):
                heights[x] = max(heights[x], oy + oh)

        best_x, best_y = 0, max(heights) if heights else 0
        found = False
        for x in range(0, cols - w + 1):
            y = max(heights[x:x + w]) if w else 0
            if not found or y < best_y or (y == best_y and x < best_x):
                best_x, best_y = x, y
                found = True

        # Stretch into a leftover stub on the same row (prevents thin blank columns)
        if fill_row:
            leftover = cols - (best_x + w)
            if 0 < leftover <= 5:
                if all(heights[x] <= best_y for x in range(best_x + w, cols)):
                    w = cols - best_x

        return best_x, best_y, w, h

    @api.model
    def _occupied_rects_for_dashboard(self, dashboard_id, exclude_ids=None, extra_rects=None):
        """Return list of (x, y, w, h) for items already on the dashboard."""
        exclude_ids = set(exclude_ids or [])
        rects = list(extra_rects or [])
        if not dashboard_id:
            return rects
        items = self.search([('dashboard_id', '=', dashboard_id)])
        for item in items:
            if item.id in exclude_ids:
                continue
            rects.append((item.grid_x or 0, item.grid_y or 0, item.grid_w or 1, item.grid_h or 1))
        return rects

    def _repack_dashboard_items(self, dashboard, items=None):
        """Tightly repack items on a dashboard using type/data-based sizes."""
        dashboard.ensure_one()
        Item = self.env['dynamic.dashboard.item']
        items = items if items is not None else dashboard.item_ids
        if not items:
            dashboard.sudo().write({'gridstack_config': '[]'})
            return Item.browse()

        specs = []
        for item in items:
            w, h = Item._grid_size_for_type(item.item_type)
            w, h = Item._tune_grid_size_for_data(item.item_type, w, h, record=item)
            specs.append({
                'item': item,
                'item_type': item.item_type,
                'name': item.name or '',
                'sequence': item.sequence or 0,
                'w': w,
                'h': h,
            })
        specs.sort(key=lambda s: (
            Item._layout_priority_for_type(s['item_type']),
            s['sequence'],
            s['name'],
            s['item'].id,
        ))

        cols = 12
        heights = [0] * cols
        packed = []
        for seq, spec in enumerate(specs, start=1):
            w = max(1, min(int(spec['w']), cols))
            h = max(1, int(spec['h']))
            best_x, best_y = 0, max(heights) if heights else 0
            found = False
            for x in range(0, cols - w + 1):
                y = max(heights[x:x + w]) if w else 0
                if not found or y < best_y or (y == best_y and x < best_x):
                    best_x, best_y = x, y
                    found = True
            # Fill stub leftover columns on this row (≤5 cols would look like wasted blank space)
            leftover = cols - (best_x + w)
            if 0 < leftover <= 5 and all(heights[x] <= best_y for x in range(best_x + w, cols)):
                w = cols - best_x
            for x in range(best_x, best_x + w):
                heights[x] = best_y + h
            packed.append({
                'item': spec['item'],
                'grid_x': best_x,
                'grid_y': best_y,
                'grid_w': w,
                'grid_h': h,
                'sequence': seq * 10,
            })

        # Grow items downward into empty cells so short tiles don't leave holes
        # beside taller neighbors (e.g. 3×2 tile next to 9×4 chart).
        packed = self._grow_packed_into_gaps(packed, cols=cols)

        writes = []
        config = []
        for row in packed:
            item = row['item']
            vals = {
                'grid_x': row['grid_x'],
                'grid_y': row['grid_y'],
                'grid_w': row['grid_w'],
                'grid_h': row['grid_h'],
                'sequence': row['sequence'],
            }
            writes.append((item, vals))
            config.append({
                'id': item.id,
                'x': row['grid_x'],
                'y': row['grid_y'],
                'w': row['grid_w'],
                'h': row['grid_h'],
            })

        for item, vals in writes:
            item.with_context(dd_skip_auto_layout=True).write(vals)

        # Drop stale per-user layout overrides so My Dashboard shows the packed grid
        Pref = self.env['dynamic.dashboard.user.preference'].sudo()
        Pref.search([
            ('dashboard_id', '=', dashboard.id),
            ('item_id', 'in', items.ids),
        ]).unlink()
        dashboard.sudo().write({'gridstack_config': json.dumps(config)})
        return items

    @api.model
    def _grow_packed_into_gaps(self, packed, cols=12, max_extra=6):
        """Expand item heights into empty cells below to remove vertical blank holes."""
        if not packed:
            return packed

        def build_occ(rows):
            max_y = max((r['grid_y'] + r['grid_h'] for r in rows), default=0)
            occ = [[None] * cols for _ in range(max_y)]
            for idx, r in enumerate(rows):
                for y in range(r['grid_y'], r['grid_y'] + r['grid_h']):
                    for x in range(r['grid_x'], r['grid_x'] + r['grid_w']):
                        if 0 <= y < max_y and 0 <= x < cols:
                            occ[y][x] = idx
            return occ

        changed = True
        guard = 0
        while changed and guard < max_extra * max(len(packed), 1):
            changed = False
            guard += 1
            occ = build_occ(packed)
            max_y = len(occ)
            for idx, r in enumerate(packed):
                x, y, w, h = r['grid_x'], r['grid_y'], r['grid_w'], r['grid_h']
                below = y + h
                if below >= max_y + max_extra:
                    continue
                # Need a full free strip under this item
                free = True
                # Ensure occupancy grid is tall enough to inspect
                while len(occ) <= below:
                    occ.append([None] * cols)
                for xx in range(x, x + w):
                    if xx >= cols or occ[below][xx] is not None:
                        free = False
                        break
                if not free:
                    continue
                # Only grow if at least one neighboring column beside us is taller
                # (otherwise we'd just create empty padding at the board bottom)
                neighbor_taller = False
                for xx in range(cols):
                    if x <= xx < x + w:
                        continue
                    col_h = 0
                    for yy in range(len(occ) - 1, -1, -1):
                        if occ[yy][xx] is not None:
                            col_h = yy + 1
                            break
                    if col_h > below:
                        neighbor_taller = True
                        break
                if not neighbor_taller:
                    continue
                r['grid_h'] = h + 1
                changed = True
                break  # rebuild occupancy
        return packed

    def action_repack_layout(self):
        """Public button/RPC: auto-size and compact all items on each item's dashboard."""
        dashboards = self.mapped('dashboard_id')
        for dash in dashboards:
            if dash:
                self._repack_dashboard_items(dash)
        return True


    @api.model
    def _tune_grid_size_for_data(self, item_type, w, h, vals=None, record=None):
        """Bump size when data config needs more space (scorecard cells, dense lists, etc.)."""
        vals = vals or {}
        w, h = int(w), int(h)
        itype = item_type or (record.item_type if record else 'bar')

        def _has_group_by():
            if 'group_by_field_id' in vals:
                return bool(vals.get('group_by_field_id'))
            return bool(record and record.group_by_field_id)

        def _list_field_count():
            cmds = vals.get('list_view_field_ids')
            if cmds:
                # Approximate from M2M commands: (6, 0, ids) or list of (4, id)
                ids = set()
                for cmd in cmds:
                    if not cmd:
                        continue
                    if cmd[0] == 6 and len(cmd) > 2:
                        ids.update(cmd[2] or [])
                    elif cmd[0] in (4, 1) and len(cmd) > 1:
                        ids.add(cmd[1])
                if ids:
                    return len(ids)
            if record:
                return len(record.list_view_field_ids)
            return 0

        if itype == 'scorecard' and _has_group_by():
            w, h = max(w, 6), max(h, 3)
            cols = vals.get('scorecard_columns') or (record.scorecard_columns if record else 'auto')
            if cols in ('3', '4'):
                w, h = max(w, 8 if cols == '3' else 12), max(h, 3)
        if itype == 'list':
            n = _list_field_count()
            if n >= 8:
                w, h = max(w, 12), max(h, 6)
            elif n >= 5:
                w, h = max(w, 6), max(h, 5)
        if itype in ('map', 'mapPoints', 'heatmap', 'matrixHeatmap'):
            w, h = max(w, 6), max(h, 5)
        if itype in ('sankey', 'arcDiagram', 'timeline', 'serpentine', 'odoo_view'):
            w = max(w, 12)
        return max(1, min(w, 12)), max(1, h)

    def _apply_auto_grid_size(self, vals, record=None):
        """Mutate vals with type/data-based grid_w/grid_h."""
        itype = vals.get('item_type') or (record.item_type if record else 'bar')
        w, h = self._grid_size_for_type(itype)
        w, h = self._tune_grid_size_for_data(itype, w, h, vals=vals, record=record)
        vals['grid_w'] = w
        vals['grid_h'] = h
        return w, h

    @api.onchange('item_type', 'group_by_field_id', 'list_view_field_ids', 'scorecard_columns')
    def _onchange_item_type_auto_grid_size(self):
        """Keep form defaults readable so users do not need to resize manually."""
        if not self.item_type:
            return
        w, h = self._grid_size_for_type(self.item_type)
        w, h = self._tune_grid_size_for_data(
            self.item_type, w, h,
            vals={
                'group_by_field_id': self.group_by_field_id.id if self.group_by_field_id else False,
                'list_view_field_ids': [(6, 0, self.list_view_field_ids.ids)],
                'scorecard_columns': self.scorecard_columns,
            },
            record=self,
        )
        self.grid_w = w
        self.grid_h = h

    def read(self, fields=None, load='_classic_read'):
        """Override read to merge user-specific preferences for layout and display settings."""
        records = super().read(fields, load)
        if self.env.context.get('ignore_user_preferences') or not records:
            return records
            
        import json
        prefs = self.env['dynamic.dashboard.user.preference'].search([
            ('user_id', '=', self.env.user.id),
            ('item_id', 'in', [r['id'] for r in records if 'id' in r])
        ])
        if prefs:
            pref_map = {p.item_id.id: json.loads(p.preference_data or '{}') for p in prefs}
            for rec in records:
                rec_id = rec.get('id')
                if rec_id and rec_id in pref_map:
                    for k, v in pref_map[rec_id].items():
                        if not fields or k in fields:
                            rec[k] = v
        return records

    # =========================================================================
    # RELATIONAL FIELDS
    
    # Date Filter
    date_filter_field_id = fields.Many2one(
        'ir.model.fields',
        string='Date Filter Field',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'in', ['date', 'datetime'])]",
    )
    date_filter_selection = fields.Selection([
        ('none', 'None (All Time)'),
        ('today', 'Today'),
        ('yesterday', 'Yesterday'),
        ('tomorrow', 'Tomorrow'),
        ('this_week', 'This Week'),
        ('this_month', 'This Month'),
        ('this_quarter', 'This Quarter'),
        ('this_year', 'This Year'),
        ('next_week', 'Next Week'),
        ('next_month', 'Next Month'),
        ('next_quarter', 'Next Quarter'),
        ('next_year', 'Next Year'),
        ('week_to_date', 'Week to Date'),
        ('month_to_date', 'Month to Date'),
        ('year_to_date', 'Year to Date'),
        ('last_7_days', 'Last 7 Days'),
        ('last_30_days', 'Last 30 Days'),
        ('last_90_days', 'Last 90 Days'),
        ('last_week', 'Last Week'),
        ('last_month', 'Last Month'),
        ('last_quarter', 'Last Quarter'),
        ('last_year', 'Last Year'),
        ('past_until_now', 'Past Until Now'),
        ('future_starting_now', 'Future Starting Now'),
        ('custom', 'Custom Date Range'),
        ('user_defined', 'Custom Defined Filter'),
    ], string='Item Date Filter', default='none')
    item_start_date = fields.Datetime(string="Start Date")
    item_end_date = fields.Datetime(string="End Date")
    compare_previous_period = fields.Boolean(string="Compare with Previous Period")

    @api.constrains('domain', 'kpi_domain')
    def _check_domains(self):
        for item in self:
            assert_domain(item.domain, _('Domain'))
            assert_domain(item.kpi_domain, _('KPI Model 2 Domain'))

    @api.constrains('item_start_date', 'item_end_date', 'date_filter_selection')
    def _check_custom_date_range(self):
        for item in self:
            if item.date_filter_selection == 'custom':
                if not item.item_start_date or not item.item_end_date:
                    raise ValidationError(
                        _('Custom date filter on "%s" requires both Start Date and End Date.')
                        % item.display_name
                    )
            if item.item_start_date and item.item_end_date and item.item_start_date > item.item_end_date:
                raise ValidationError(
                    _('Start Date must be before End Date on item "%s".') % item.display_name
                )

    @api.constrains('tile_color', 'background_color', 'font_color')
    def _check_item_colors(self):
        for item in self:
            assert_hex_color(item.tile_color, _('Tile Background Color'))
            assert_hex_color(item.background_color, _('Card Background Color'))
            assert_hex_color(item.font_color, _('Font Color'))

    @api.constrains('formula_active', 'formula')
    def _check_formula(self):
        for item in self:
            if item.formula_active and not (item.formula or '').strip():
                raise ValidationError(
                    _('Formula is required when "Enable Formula" is set on item "%s".')
                    % item.display_name
                )

    @api.constrains('item_type', 'iframe_url', 'odoo_action_id')
    def _check_embed_config(self):
        for item in self:
            if item.item_type == 'iframe' and not (item.iframe_url or '').strip():
                raise ValidationError(
                    _('Iframe URL is required for iframe items (%s).') % item.display_name
                )
            if item.item_type == 'odoo_view' and not item.odoo_action_id:
                raise ValidationError(
                    _('Embedded Odoo Action is required for Odoo View items (%s).')
                    % item.display_name
                )

    @api.constrains(
        'data_calculation_type', 'item_type', 'model_id', 'analysis_id', 'kpi_id',
        'external_connection_id', 'query',
    )
    def _check_data_source(self):
        for item in self:
            special = item.item_type in ('todo', 'iframe', 'odoo_view')
            if special or item.analysis_id or item.kpi_id:
                continue
            calc = item.data_calculation_type or 'custom'
            if calc == 'custom' and not item.model_id:
                raise ValidationError(
                    _('Please select a Model for item "%s".') % item.display_name
                )
            if calc == 'sql' and not (item.query or '').strip():
                raise ValidationError(
                    _('SQL Query is required for item "%s".') % item.display_name
                )
            if calc in ('api', 'sheets') and not item.external_connection_id:
                raise ValidationError(
                    _('External Connection is required for item "%s".') % item.display_name
                )
            if calc == 'scrape' and not (item.scrape_url or '').strip():
                raise ValidationError(
                    _('Scrape URL is required for item "%s".') % item.display_name
                )

    @api.depends('upload_file', 'upload_filename', 'data_calculation_type')
    def _compute_file_columns_preview(self):
        for rec in self:
            if rec.data_calculation_type not in ('excel', 'csv') or not rec.upload_file:
                rec.file_columns_preview = False
                continue
            try:
                rows = rec._parse_uploaded_rows()
                if rows:
                    rec.file_columns_preview = ', '.join(str(k) for k in rows[0].keys())
                else:
                    rec.file_columns_preview = _('(empty file)')
            except Exception as e:
                rec.file_columns_preview = _('Error: %s') % e

    @api.model
    def _selection_tile_icons(self):
        icons = [
            ('fa-bar-chart', 'Bar Chart'),
            ('fa-line-chart', 'Line Chart'),
            ('fa-area-chart', 'Area Chart'),
            ('fa-pie-chart', 'Pie Chart'),
            ('fa-dashboard', 'Dashboard'),
            ('fa-tachometer', 'Tachometer'),
            ('fa-money', 'Money'),
            ('fa-usd', 'USD'),
            ('fa-eur', 'Euro'),
            ('fa-shopping-cart', 'Shopping Cart'),
            ('fa-credit-card', 'Credit Card'),
            ('fa-truck', 'Truck'),
            ('fa-archive', 'Archive'),
            ('fa-calculator', 'Calculator'),
            ('fa-users', 'Users'),
            ('fa-user', 'User'),
            ('fa-building', 'Building'),
            ('fa-briefcase', 'Briefcase'),
            ('fa-database', 'Database'),
            ('fa-flask', 'Flask'),
            ('fa-list', 'List'),
            ('fa-check', 'Check'),
            ('fa-star', 'Star'),
            ('fa-heart', 'Heart'),
            ('fa-globe', 'Globe'),
            ('fa-calendar', 'Calendar'),
            ('fa-clock-o', 'Clock'),
            ('fa-envelope', 'Envelope'),
            ('fa-phone', 'Phone'),
            ('fa-tag', 'Tag'),
            ('fa-tags', 'Tags'),
            ('fa-cubes', 'Cubes'),
            ('fa-cube', 'Cube'),
            ('fa-percent', 'Percent'),
            ('fa-signal', 'Signal'),
            ('fa-trophy', 'Trophy'),
            ('fa-bolt', 'Bolt'),
            ('fa-fire', 'Fire'),
            ('fa-leaf', 'Leaf'),
            ('fa-home', 'Home'),
        ]
        known = {k for k, _v in icons}
        try:
            for row in self.sudo().search_read([('tile_icon', '!=', False)], ['tile_icon'], limit=500):
                icon = row.get('tile_icon')
                if icon and icon not in known:
                    icons.append((icon, icon))
                    known.add(icon)
        except Exception:
            pass
        return icons

    @api.model
    def _selection_units(self):
        units = [
            ('$', '$'),
            ('€', '€'),
            ('£', '£'),
            ('¥', '¥'),
            ('%', '%'),
            ('kg', 'kg'),
            ('g', 'g'),
            ('lb', 'lb'),
            ('m', 'm'),
            ('cm', 'cm'),
            ('km', 'km'),
            ('hrs', 'hrs'),
            ('days', 'days'),
            ('pcs', 'pcs'),
            ('u', 'u'),
            ('units', 'units'),
        ]
        known = {k for k, _v in units}
        try:
            for row in self.sudo().search_read([('unit', '!=', False)], ['unit'], limit=500):
                unit = row.get('unit')
                if unit and unit not in known:
                    units.append((unit, unit))
                    known.add(unit)
        except Exception:
            pass
        return units

    @api.model
    def _selection_file_columns(self):
        """Column picker options — only use stored fields (preview is non-stored)."""
        cols = set()
        Item = self.env['dynamic.dashboard.item'].sudo()
        for row in Item.search_read(
            ['|', ('file_label_column', '!=', False), ('file_value_column', '!=', False)],
            ['file_label_column', 'file_value_column'],
            limit=500,
        ):
            for key in ('file_label_column', 'file_value_column'):
                if row.get(key):
                    cols.add(row[key])
        # Current form records (NewId / open form) may expose computed preview
        for rec in self:
            preview = getattr(rec, 'file_columns_preview', False) or ''
            if preview and not str(preview).startswith(('Error:', '(')):
                for part in str(preview).split(','):
                    name = part.strip()
                    if name:
                        cols.add(name)
            for key in ('file_label_column', 'file_value_column'):
                val = getattr(rec, key, False)
                if val:
                    cols.add(val)
        for name in self.env.context.get('dd_file_columns') or []:
            if name:
                cols.add(str(name))
        # Common demo / generator headers
        for name in (
            'Region', 'Orders', 'Revenue', 'Category', 'Amount', 'Qty', 'Quantity',
            'Label', 'Value', 'Product', 'Partner', 'Month', 'Year', 'State',
            'Warehouse', 'Vendor', 'Customer', 'Spend', 'Stock', 'POs', 'Transfers',
            'Type', 'Count',
        ):
            cols.add(name)
        return [(c, c) for c in sorted(cols)]

    @api.model
    def _selection_sql_label_columns(self):
        cols = set()
        for row in self.env['dynamic.dashboard.item'].sudo().search_read(
            [('sql_label_column', '!=', False)],
            ['sql_label_column'],
            limit=500,
        ):
            if row.get('sql_label_column'):
                cols.add(row['sql_label_column'])
        for name in self.env.context.get('dd_sql_columns') or []:
            if name:
                cols.add(str(name))
        # Common SQL aliases used by demos / generators
        for name in ('label', 'name', 'state', 'category', 'partner', 'product', 'month', 'year', 'move_type'):
            cols.add(name)
        return [(c, c) for c in sorted(cols)]

    @api.model
    def _selection_api_keys(self):
        cols = {
            'title', 'name', 'label', 'category', 'product', 'sku', 'code',
            'price', 'amount', 'value', 'total', 'qty', 'quantity', 'count', 'id',
        }
        for row in self.env['dynamic.dashboard.item'].sudo().search_read(
            ['|', ('api_label_key', '!=', False), ('api_value_key', '!=', False)],
            ['api_label_key', 'api_value_key'],
            limit=500,
        ):
            if row.get('api_label_key'):
                cols.add(row['api_label_key'])
            if row.get('api_value_key'):
                cols.add(row['api_value_key'])
        for name in self.env.context.get('dd_api_keys') or []:
            if name:
                cols.add(str(name))
        return [(c, c) for c in sorted(cols)]

    @api.onchange('model_id')
    def _onchange_model_id_clear_related_fields(self):
        """Clear dynamic field picks that no longer belong to the selected model."""
        mid = self.model_id.id if self.model_id else False
        if not mid:
            self.measure_field_ids = [(5, 0, 0)]
            self.measure_field_2_ids = [(5, 0, 0)]
            self.list_view_field_ids = [(5, 0, 0)]
            self.group_by_field_id = False
            self.sub_group_by_field_id = False
            self.sort_by_field_id = False
            self.date_filter_field_id = False
            self.scatter_measure_x_id = False
            self.scatter_measure_y_id = False
            return
        def _ok(field):
            return field and field.model_id.id == mid
        if self.measure_field_ids:
            self.measure_field_ids = self.measure_field_ids.filtered(lambda f: f.model_id.id == mid)
        if self.measure_field_2_ids:
            self.measure_field_2_ids = self.measure_field_2_ids.filtered(lambda f: f.model_id.id == mid)
        if self.list_view_field_ids:
            self.list_view_field_ids = self.list_view_field_ids.filtered(lambda f: f.model_id.id == mid)
        if not _ok(self.group_by_field_id):
            self.group_by_field_id = False
        if not _ok(self.sub_group_by_field_id):
            self.sub_group_by_field_id = False
        if not _ok(self.sort_by_field_id):
            self.sort_by_field_id = False
        if not _ok(self.date_filter_field_id):
            self.date_filter_field_id = False
        if not _ok(self.scatter_measure_x_id):
            self.scatter_measure_x_id = False
        if not _ok(self.scatter_measure_y_id):
            self.scatter_measure_y_id = False

    @api.onchange('upload_file', 'upload_filename', 'data_calculation_type')
    def _onchange_upload_file_columns(self):
        if self.data_calculation_type not in ('excel', 'csv') or not self.upload_file:
            return
        try:
            rows = self._parse_uploaded_rows()
        except Exception:
            return
        if not rows:
            return
        headers = [str(k) for k in rows[0].keys()]
        if not headers:
            return
        if not self.file_label_column or self.file_label_column not in headers:
            self.file_label_column = headers[0]
        if not self.file_value_column or self.file_value_column not in headers:
            # Prefer a numeric-looking column after the first
            self.file_value_column = headers[1] if len(headers) > 1 else headers[0]
        return {'context': {'dd_file_columns': headers}}

    def _get_upload_file_bytes(self):
        """Return raw file bytes for upload_file (CSV/Excel).

        Binary fields often arrive under ``bin_size=True`` as human size strings
        (e.g. ``\"12 Kb\"``), which must not be base64-decoded.
        """
        self.ensure_one()
        import base64
        import re

        def _from_attachment():
            att = self.env['ir.attachment'].sudo().search([
                ('res_model', '=', self._name),
                ('res_id', '=', self.id),
                ('res_field', '=', 'upload_file'),
            ], limit=1)
            if not att:
                return False
            return att.with_context(bin_size=False).datas

        data = self.with_context(bin_size=False).upload_file
        if not data and self.id:
            data = _from_attachment()
        if not data:
            return b''

        # bin_size leftovers that sometimes leak into caches / RPC payloads
        if isinstance(data, str) and re.match(r'^\d+(\.\d+)?\s*[KMGT]?[Bb]$', data.strip()):
            data = _from_attachment()
            if not data:
                raise UserError(_('Uploaded file content is unavailable. Please re-upload the file.'))

        if isinstance(data, bytes):
            # Raw XLSX/ZIP, or already-decoded binary
            if data[:2] == b'PK' or data[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
                return data
            try:
                return base64.b64decode(data, validate=False)
            except Exception:
                return data

        if isinstance(data, str):
            text = data.strip()
            # Pad if ORM/truncation dropped '=' padding
            missing = (-len(text)) % 4
            if missing:
                text += '=' * missing
            try:
                return base64.b64decode(text, validate=False)
            except Exception:
                # Last resort: attachment store
                data = _from_attachment()
                if not data:
                    raise
                if isinstance(data, bytes) and data[:2] == b'PK':
                    return data
                return base64.b64decode(data)

        raise UserError(_('Unsupported upload file payload type: %s') % type(data).__name__)

    def _parse_uploaded_rows(self):
        """Parse uploaded Excel/CSV into a list of dicts (header → value)."""
        self.ensure_one()
        if not self.upload_file and not self.id:
            return []
        import csv
        import io

        raw = self._get_upload_file_bytes()
        if not raw:
            return []
        filename = (self.upload_filename or '').lower()

        if self.data_calculation_type == 'csv' or filename.endswith('.csv'):
            text = raw.decode('utf-8-sig', errors='replace')
            reader = csv.DictReader(io.StringIO(text))
            return [dict(row) for row in reader]

        # Excel (.xlsx / .xls)
        if filename.endswith('.xls') and not filename.endswith('.xlsx'):
            import xlrd
            book = xlrd.open_workbook(file_contents=raw)
            sheet = book.sheet_by_index(0)
            if sheet.nrows < 1:
                return []
            headers = [str(sheet.cell_value(0, c)).strip() for c in range(sheet.ncols)]
            rows = []
            for r in range(1, sheet.nrows):
                row = {}
                for c, h in enumerate(headers):
                    if not h:
                        continue
                    row[h] = sheet.cell_value(r, c)
                rows.append(row)
            return rows

        from openpyxl import load_workbook
        wb = load_workbook(filename=io.BytesIO(raw), read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        try:
            headers = [str(h).strip() if h is not None else '' for h in next(rows_iter)]
        except StopIteration:
            return []
        rows = []
        for values in rows_iter:
            row = {}
            for i, h in enumerate(headers):
                if not h:
                    continue
                row[h] = values[i] if i < len(values) else None
            if any(v not in (None, '') for v in row.values()):
                rows.append(row)
        return rows

    def _to_float(self, value):
        if value is None or value == '':
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace(',', '').strip())
        except Exception:
            return 0.0

    def _eval_measure_formula(self, m1=0, m2=0, count=0):
        """Safely evaluate formula with {m1}, {m2}, {count} placeholders."""
        self.ensure_one()
        if not self.formula_active or not self.formula:
            return None
        import re
        expr = self.formula
        replacements = {
            'm1': float(m1 or 0),
            'm2': float(m2 or 0),
            'count': float(count or 0),
        }
        for key, val in replacements.items():
            expr = expr.replace('{%s}' % key, str(val))
        expr = expr.strip()
        if not re.fullmatch(r'[\d\.\+\-\*/\(\)\s]+', expr):
            raise UserError(_("Invalid formula. Only {m1}, {m2}, {count} and + - * / ( ) are allowed."))
        try:
            return float(safe_eval(expr))
        except Exception as e:
            raise UserError(_("Formula evaluation error: %s") % e)

    def _resolve_file_columns(self, rows):
        """Pick label/value columns from uploaded rows."""
        if not rows:
            return None, None
        headers = list(rows[0].keys())
        label_col = self.file_label_column if self.file_label_column in headers else headers[0]
        value_col = None
        if self.file_value_column and self.file_value_column in headers:
            value_col = self.file_value_column
        else:
            for h in headers:
                if h == label_col:
                    continue
                # Prefer a column that looks numeric
                sample = next((r.get(h) for r in rows if r.get(h) not in (None, '')), None)
                if sample is not None:
                    try:
                        float(str(sample).replace(',', '').strip())
                        value_col = h
                        break
                    except Exception:
                        continue
            if not value_col and len(headers) > 1:
                value_col = headers[1]
        return label_col, value_col

    def _get_item_data_from_file(self, result, item=None):
        """Build tile/chart/list payloads from uploaded Excel/CSV."""
        self.ensure_one()
        item = item or self
        try:
            rows = self._parse_uploaded_rows()
        except Exception as e:
            result['error'] = _('File parse error: %s') % e
            return result
        if not rows:
            result['error'] = _('Uploaded file is empty or has no data rows.')
            return result

        label_col, value_col = self._resolve_file_columns(rows)
        agg = 'avg' if item.data_type == 'average' else item.data_type

        if item.item_type in ('tile', 'kpi', 'scorecard'):
            values = [self._to_float(r.get(value_col)) for r in rows] if value_col else []
            if agg == 'count' or not value_col:
                val = float(len(rows))
            elif agg == 'avg':
                val = sum(values) / len(values) if values else 0.0
            else:
                val = sum(values)
            if item.multiplier_active:
                val = val * item.multiplier_value
            if item.formula_active:
                try:
                    val = self._eval_measure_formula(m1=val, m2=0, count=len(rows))
                except UserError as e:
                    result['error'] = str(e)
                    return result
            result.update({
                'value': val,
                'color': item.tile_color,
                'icon': item.tile_icon,
                'compare_previous_period': False,
                'previous_value': 0,
                'scorecard_values': [
                    {'label': item.name or _('Total'), 'value': val},
                ],
            })
            self._apply_item_display_options(result, item)
            return result

        if item.item_type == 'list':
            columns = list(rows[0].keys())
            limit = item.record_limit or len(rows)
            result.update({
                'records': rows[:limit],
                'columns': columns,
                'column_keys': columns,
                'list_view_layout': item.list_view_layout,
                'list_view_type': 'ungrouped',
            })
            self._apply_item_display_options(result, item)
            return result

        # Charts: aggregate by label column
        buckets = {}
        counts = {}
        for r in rows:
            lbl = str(r.get(label_col) if label_col else 'Data')
            if lbl not in buckets:
                buckets[lbl] = 0.0
                counts[lbl] = 0
            buckets[lbl] += self._to_float(r.get(value_col)) if value_col else 1.0
            counts[lbl] += 1

        labels = list(buckets.keys())
        if agg == 'count' or not value_col:
            data_vals = [counts[l] for l in labels]
        elif agg == 'avg':
            data_vals = [(buckets[l] / counts[l]) if counts[l] else 0 for l in labels]
        else:
            data_vals = [buckets[l] for l in labels]

        if item.multiplier_active:
            data_vals = [v * item.multiplier_value for v in data_vals]

        if item.is_cumulative:
            running = 0
            cum = []
            for v in data_vals:
                running += v or 0
                cum.append(running)
            data_vals = cum

        if item.record_limit:
            labels = labels[:item.record_limit]
            data_vals = data_vals[:item.record_limit]

        result.update({
            'labels': labels,
            'datasets': [{'label': value_col or 'Value', 'data': data_vals, 'yAxisID': 'y'}],
        })
        self._apply_item_display_options(result, item)
        return result

    def _get_item_data_from_api(self, result, item=None):
        """Fetch External API calculation type into a chart/tile/list payload."""
        self.ensure_one()
        item = item or self
        if not item.external_connection_id or item.external_connection_id.connection_type != 'api':
            result['error'] = _('Invalid API Connection — select an External Connection of type API.')
            return result

        Analysis = self.env['dynamic.dashboard.analysis']
        try:
            import requests
            import json as pyjson
            conn_info = item.external_connection_id

            headers = {}
            if conn_info.api_headers:
                try:
                    headers = pyjson.loads(conn_info.api_headers)
                except Exception:
                    headers = {}
            headers.setdefault('Accept', 'application/json')
            headers.setdefault('User-Agent', 'Mozilla/5.0 (compatible; DynamicDashboard/1.0)')

            body = None
            if conn_info.api_method == 'POST' and conn_info.api_body:
                try:
                    body = pyjson.loads(conn_info.api_body)
                except Exception:
                    body = None

            kwargs_req = {'headers': headers, 'timeout': 30}
            if body is not None:
                kwargs_req['json'] = body

            if conn_info.api_method == 'POST':
                response = requests.post(conn_info.api_endpoint, **kwargs_req)
            else:
                response = requests.get(conn_info.api_endpoint, **kwargs_req)
            response.raise_for_status()
            data = response.json()

            if conn_info.api_data_path:
                for key in conn_info.api_data_path.split('.'):
                    if not key:
                        continue
                    if isinstance(data, dict):
                        data = data.get(key, {})
                    elif isinstance(data, list) and key.isdigit():
                        try:
                            data = data[int(key)]
                        except Exception:
                            data = {}

            if isinstance(data, dict):
                for envelope in ('products', 'data', 'items', 'results', 'records', 'rows'):
                    if isinstance(data.get(envelope), list):
                        data = data[envelope]
                        break

            if not isinstance(data, list):
                data = [data]
            rows = [r for r in data if isinstance(r, dict)]
            if not rows and data:
                rows = [{'label': str(i), 'value': item._to_float(v)} for i, v in enumerate(data)]

            if item.record_limit and item.record_limit > 0:
                rows = rows[:item.record_limit]

            if not rows:
                result['error'] = _('API returned no usable rows.')
                self._apply_item_display_options(result, item)
                return result

            label_key, value_key = Analysis._scrape_pick_keys(
                rows[0], item.api_label_key, item.api_value_key,
            )

            if item.item_type in ('tile', 'kpi', 'scorecard'):
                val = item._to_float(rows[0].get(value_key))
                if item.data_type == 'count':
                    val = float(len(rows))
                elif item.data_type == 'average':
                    nums = [item._to_float(r.get(value_key)) for r in rows]
                    val = sum(nums) / len(nums) if nums else 0.0
                elif item.data_type == 'sum':
                    val = sum(item._to_float(r.get(value_key)) for r in rows)
                if item.multiplier_active:
                    val = val * item.multiplier_value
                target = item.standard_target_value or 0
                if item.enable_target and item.target_line_ids:
                    today = fields.Date.today()
                    valid_line = item.target_line_ids.filtered(lambda l: l.date_start <= today <= l.date_end)
                    if valid_line:
                        target = valid_line[0].target_value
                result.update({
                    'value': val,
                    'target': target,
                    'target_value': target,
                    'color': item.tile_color,
                    'icon': item.tile_icon,
                    'scorecard_values': [{'label': item.name or label_key, 'value': val}],
                })
                self._apply_item_display_options(result, item)
                return result

            labels = [str(r.get(label_key, '') or '') for r in rows]
            values = [item._to_float(r.get(value_key)) for r in rows]
            if item.multiplier_active:
                values = [v * item.multiplier_value for v in values]

            result.update({
                'labels': labels,
                'datasets': [{'label': value_key or 'API Data', 'data': values}],
                'list_view_type': 'list',
                'list_view_layout': item.list_view_layout,
                'columns': [label_key, value_key],
                'column_keys': [label_key, value_key],
                'records': [{label_key: labels[i], value_key: values[i]} for i in range(len(labels))],
                'api_label_key': label_key,
                'api_value_key': value_key,
            })
            self._apply_item_display_options(result, item)
            return result
        except Exception as e:
            result['error'] = _('API error: %s') % e
            self._apply_item_display_options(result, item)
            return result

    def _get_item_data_from_sql(self, result, kwargs=None, item=None):
        """Fetch Custom SQL calculation type into a chart/tile/list payload."""
        self.ensure_one()
        item = item or self
        kwargs = kwargs or {}
        if not item.query:
            result['error'] = _('SQL Query is empty')
            return result
        try:
            if item.use_materialized_view:
                try:
                    row_limit = item.sql_row_limit or 5000
                    res = self._execute_sql_query(f"SELECT * FROM mview_dyn_dashboard_{self.id}", item.external_connection_id) or []
                except Exception as e:
                    # If materialized view fails (maybe not created yet), fallback to raw query
                    prepared, row_limit, params = self._prepare_sql_query(item.query, kwargs)
                    res = self._execute_sql_query(prepared, item.external_connection_id, params=params) or []
            else:
                prepared, row_limit, params = self._prepare_sql_query(item.query, kwargs)
                res = self._execute_sql_query(prepared, item.external_connection_id, params=params) or []
            if len(res) > row_limit:
                res = res[:row_limit]

            if item.item_type in ('tile', 'kpi', 'scorecard'):
                if res:
                    keys = list(res[0].keys())
                    # Prefer a numeric column named value/amount/total, else last/first
                    value_key = None
                    for pref in ('value', 'amount', 'total', 'sum', 'count'):
                        for k in keys:
                            if k.lower() == pref:
                                value_key = k
                                break
                        if value_key:
                            break
                    if not value_key:
                        value_key = keys[-1] if len(keys) > 1 else keys[0]
                    val = self._to_float(res[0].get(value_key))
                    if item.multiplier_active:
                        val = val * item.multiplier_value
                else:
                    val = 0.0
                result.update({
                    'value': val,
                    'color': item.tile_color,
                    'icon': item.tile_icon,
                    'compare_previous_period': False,
                    'previous_value': 0,
                    'scorecard_values': [{'label': item.name or _('SQL'), 'value': val}],
                })
            elif item.item_type == 'list':
                if res:
                    columns = list(res[0].keys())
                    result.update({
                        'list_view_type': 'list',
                        'list_view_layout': item.list_view_layout,
                        'columns': columns,
                        'column_keys': columns,
                        'records': res,
                    })
                else:
                    result.update({
                        'list_view_type': 'list',
                        'list_view_layout': item.list_view_layout,
                        'columns': [],
                        'column_keys': [],
                        'records': [],
                    })
            else:
                # Charts (bar, barLine, pie, …)
                if res:
                    keys = list(res[0].keys())
                    label_key = (
                        item.sql_label_column
                        if item.sql_label_column and item.sql_label_column in keys
                        else keys[0]
                    )
                    measure_keys = [k for k in keys if k != label_key]
                    if not measure_keys:
                        # Single-column result → count 1 per label
                        measure_keys = ['value']
                        for r in res:
                            r['value'] = 1
                    labels = [str(r.get(label_key, '') or '') for r in res]
                    datasets = []
                    for mk in measure_keys:
                        series = [self._to_float(r.get(mk)) for r in res]
                        if item.is_cumulative:
                            running = 0.0
                            cum = []
                            for val in series:
                                running += val or 0.0
                                cum.append(running)
                            series = cum
                        datasets.append({'label': mk, 'data': series})
                    result.update({
                        'labels': labels,
                        'datasets': datasets,
                        'theme': item.chart_theme or item.dashboard_id.chart_theme or 'default',
                        'is_stacked': item.is_stacked,
                    })
                else:
                    result.update({'labels': [], 'datasets': []})
            self._apply_item_display_options(result, item)
            return result
        except UserError as e:
            result['error'] = str(e)
            self._apply_item_display_options(result, item)
            return result
        except Exception as e:
            result['error'] = _('SQL Execution Error: %s') % e
            self._apply_item_display_options(result, item)
            return result

    def _compute_kpi_secondary_value(self, kwargs, use_previous_period=False):
        """Compute value from KPI comparison model (model 2)."""
        self.ensure_one()
        if not self.kpi_model_id:
            return 0.0
        model2 = self._dd_scoped_model(self.sudo().kpi_model_id.model)
        domain2 = safe_eval(self.kpi_domain or '[]')

        # Apply date filter on model 2 if configured
        date_filter = kwargs.get('global_date_filter', 'none')
        if date_filter == 'none':
            date_filter = self.kpi_date_filter_selection
        if self.kpi_date_filter_field_id and date_filter and date_filter != 'none':
            today = fields.Date.context_today(self)
            start_date, end_date, prev_start, prev_end = self._resolve_date_range(
                date_filter, today=today, item=self
            )
            if use_previous_period:
                start_date, end_date = prev_start, prev_end
            if start_date and end_date:
                fname = self.kpi_date_filter_field_id.name
                if self.kpi_date_filter_field_id.ttype == 'datetime':
                    if isinstance(start_date, datetime.date) and not isinstance(start_date, datetime.datetime):
                        start_date = datetime.datetime.combine(start_date, datetime.time.min)
                    if isinstance(end_date, datetime.date) and not isinstance(end_date, datetime.datetime):
                        end_date = datetime.datetime.combine(end_date, datetime.time.max)
                domain2 += [(fname, '>=', start_date), (fname, '<=', end_date)]

        agg2 = 'avg' if self.kpi_data_type == 'average' else self.kpi_data_type
        if self.kpi_measure_field_id and agg2 != 'count':
            fname = self.kpi_measure_field_id.name
            res = model2.formatted_read_group(domain2, groupby=[], aggregates=[f"{fname}:{agg2}"])
            return res[0].get(f"{fname}:{agg2}", 0) if res else 0
        return model2.search_count(domain2)

    @api.model
    def _resolve_date_range(self, date_filter, today=None, item=None, custom_filter=None):
        """Resolve a date filter key into (start, end, prev_start, prev_end)."""
        if today is None:
            today = fields.Date.context_today(self)
        start_date = end_date = prev_start = prev_end = False

        if date_filter and str(date_filter).startswith('custom_'):
            try:
                cf_id = int(str(date_filter).split('_', 1)[1])
                custom_filter = self.env['dynamic.dashboard.date.filter'].browse(cf_id)
            except (ValueError, IndexError):
                custom_filter = self.env['dynamic.dashboard.date.filter']
            if custom_filter and custom_filter.exists():
                start_date, end_date = custom_filter.resolve_range(today)
                delta = end_date - start_date
                prev_end = start_date - datetime.timedelta(days=1)
                prev_start = prev_end - delta
                return start_date, end_date, prev_start, prev_end

        if date_filter == 'user_defined' and item and item.custom_date_filter_id:
            start_date, end_date = item.custom_date_filter_id.resolve_range(today)
            delta = end_date - start_date
            prev_end = start_date - datetime.timedelta(days=1)
            prev_start = prev_end - delta
            return start_date, end_date, prev_start, prev_end

        if date_filter == 'today':
            start_date = end_date = today
            prev_start = prev_end = today - datetime.timedelta(days=1)
        elif date_filter == 'yesterday':
            start_date = end_date = today - datetime.timedelta(days=1)
            prev_start = prev_end = start_date - datetime.timedelta(days=1)
        elif date_filter == 'tomorrow':
            start_date = end_date = today + datetime.timedelta(days=1)
            prev_start = prev_end = today
        elif date_filter == 'this_week':
            start_date = today - datetime.timedelta(days=today.weekday())
            end_date = start_date + datetime.timedelta(days=6)
            prev_start = start_date - datetime.timedelta(days=7)
            prev_end = end_date - datetime.timedelta(days=7)
        elif date_filter == 'this_month':
            start_date = today.replace(day=1)
            end_date = start_date + relativedelta(months=1, days=-1)
            prev_start = start_date - relativedelta(months=1)
            prev_end = end_date - relativedelta(months=1)
        elif date_filter == 'this_quarter':
            quarter = (today.month - 1) // 3 + 1
            start_date = today.replace(month=3 * quarter - 2, day=1)
            end_date = start_date + relativedelta(months=3, days=-1)
            prev_start = start_date - relativedelta(months=3)
            prev_end = end_date - relativedelta(months=3)
        elif date_filter == 'this_year':
            start_date = today.replace(month=1, day=1)
            end_date = today.replace(month=12, day=31)
            prev_start = start_date - relativedelta(years=1)
            prev_end = end_date - relativedelta(years=1)
        elif date_filter == 'next_week':
            start_date = today - datetime.timedelta(days=today.weekday()) + datetime.timedelta(days=7)
            end_date = start_date + datetime.timedelta(days=6)
            prev_start = start_date - datetime.timedelta(days=7)
            prev_end = end_date - datetime.timedelta(days=7)
        elif date_filter == 'next_month':
            start_date = today.replace(day=1) + relativedelta(months=1)
            end_date = start_date + relativedelta(months=1, days=-1)
            prev_start = start_date - relativedelta(months=1)
            prev_end = end_date - relativedelta(months=1)
        elif date_filter == 'next_quarter':
            quarter = (today.month - 1) // 3 + 1
            start_date = today.replace(month=3 * quarter - 2, day=1) + relativedelta(months=3)
            end_date = start_date + relativedelta(months=3, days=-1)
            prev_start = start_date - relativedelta(months=3)
            prev_end = end_date - relativedelta(months=3)
        elif date_filter == 'next_year':
            start_date = today.replace(year=today.year + 1, month=1, day=1)
            end_date = today.replace(year=today.year + 1, month=12, day=31)
            prev_start = start_date - relativedelta(years=1)
            prev_end = end_date - relativedelta(years=1)
        elif date_filter == 'week_to_date':
            start_date = today - datetime.timedelta(days=today.weekday())
            end_date = today
            prev_start = start_date - datetime.timedelta(days=7)
            prev_end = today - datetime.timedelta(days=7)
        elif date_filter == 'month_to_date':
            start_date = today.replace(day=1)
            end_date = today
            prev_start = start_date - relativedelta(months=1)
            prev_end = today - relativedelta(months=1)
        elif date_filter == 'year_to_date':
            start_date = today.replace(month=1, day=1)
            end_date = today
            prev_start = start_date - relativedelta(years=1)
            prev_end = today - relativedelta(years=1)
        elif date_filter == 'last_7_days':
            start_date = today - datetime.timedelta(days=6)
            end_date = today
            prev_start = start_date - datetime.timedelta(days=7)
            prev_end = end_date - datetime.timedelta(days=7)
        elif date_filter == 'last_30_days':
            start_date = today - datetime.timedelta(days=29)
            end_date = today
            prev_start = start_date - datetime.timedelta(days=30)
            prev_end = end_date - datetime.timedelta(days=30)
        elif date_filter == 'last_90_days':
            start_date = today - datetime.timedelta(days=89)
            end_date = today
            prev_start = start_date - datetime.timedelta(days=90)
            prev_end = end_date - datetime.timedelta(days=90)
        elif date_filter == 'last_week':
            start_date = today - datetime.timedelta(days=today.weekday() + 7)
            end_date = start_date + datetime.timedelta(days=6)
            prev_start = start_date - datetime.timedelta(days=7)
            prev_end = end_date - datetime.timedelta(days=7)
        elif date_filter == 'last_month':
            start_date = (today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
            end_date = start_date + relativedelta(months=1, days=-1)
            prev_start = start_date - relativedelta(months=1)
            prev_end = end_date - relativedelta(months=1)
        elif date_filter == 'last_quarter':
            quarter = (today.month - 1) // 3 + 1
            start_date = today.replace(month=3 * quarter - 2, day=1) - relativedelta(months=3)
            end_date = start_date + relativedelta(months=3, days=-1)
            prev_start = start_date - relativedelta(months=3)
            prev_end = end_date - relativedelta(months=3)
        elif date_filter == 'last_year':
            start_date = today.replace(year=today.year - 1, month=1, day=1)
            end_date = today.replace(year=today.year - 1, month=12, day=31)
            prev_start = start_date - relativedelta(years=1)
            prev_end = end_date - relativedelta(years=1)
        elif date_filter == 'past_until_now':
            start_date = datetime.date(1970, 1, 1)
            end_date = today
            prev_start = datetime.date(1970, 1, 1)
            prev_end = today - datetime.timedelta(days=1)
        elif date_filter == 'future_starting_now':
            start_date = today
            end_date = today + relativedelta(years=50)
            prev_start = today - relativedelta(years=50)
            prev_end = today - datetime.timedelta(days=1)
        elif date_filter == 'custom' and item:
            start_date = item.item_start_date
            end_date = item.item_end_date
            if start_date and end_date:
                # Normalize datetimes to dates for delta if needed
                s = start_date.date() if isinstance(start_date, datetime.datetime) else start_date
                e = end_date.date() if isinstance(end_date, datetime.datetime) else end_date
                delta = e - s
                prev_start = s - delta
                prev_end = e - delta

        return start_date, end_date, prev_start, prev_end

    def _fill_temporal_series(self, labels, datasets, label_domain_map, date_type, range_start, range_end):
        """Insert missing date buckets between range_start and range_end with zeros."""
        if not date_type or not range_start or not range_end:
            return labels, datasets, label_domain_map

        def to_date(val):
            if isinstance(val, datetime.datetime):
                return val.date()
            if isinstance(val, datetime.date):
                return val
            if isinstance(val, str) and len(val) >= 10:
                try:
                    return fields.Date.to_date(val[:10])
                except Exception:
                    return False
            return False

        start = to_date(range_start)
        end = to_date(range_end)
        if not start or not end or start > end:
            return labels, datasets, label_domain_map

        # Index existing points by normalized period key from domain values
        existing_by_key = {}
        for i, lab in enumerate(labels):
            dval = label_domain_map.get(lab)
            key = self._temporal_period_key(dval if dval is not False else lab, date_type)
            if key:
                existing_by_key[key] = i

        expected = []
        cursor = start
        max_steps = 500
        steps = 0
        while cursor <= end and steps < max_steps:
            steps += 1
            key, label, domain_val = self._temporal_period_meta(cursor, date_type)
            expected.append((key, label, domain_val))
            if date_type == 'year':
                cursor = cursor.replace(year=cursor.year + 1, month=1, day=1)
            elif date_type == 'quarter':
                q = (cursor.month - 1) // 3 + 1
                cursor = cursor.replace(month=3 * q - 2, day=1) + relativedelta(months=3)
            elif date_type == 'month':
                cursor = cursor.replace(day=1) + relativedelta(months=1)
            elif date_type == 'week':
                cursor = cursor + datetime.timedelta(days=7)
            else:
                cursor = cursor + datetime.timedelta(days=1)

        new_labels = []
        new_map = {}
        new_data_indexes = []  # parallel list of source indexes or None for zero
        seen_keys = set()
        for key, label, domain_val in expected:
            if key in seen_keys:
                continue
            seen_keys.add(key)
            if key in existing_by_key:
                idx = existing_by_key[key]
                lab = labels[idx]
                new_labels.append(lab)
                new_map[lab] = label_domain_map.get(lab, domain_val)
                new_data_indexes.append(idx)
            else:
                new_labels.append(label)
                new_map[label] = domain_val
                new_data_indexes.append(None)

        new_datasets = []
        for ds in datasets:
            data = ds.get('data') or []
            new_data = []
            for idx in new_data_indexes:
                if idx is None:
                    new_data.append(0)
                else:
                    new_data.append(data[idx] if idx < len(data) else 0)
            new_ds = dict(ds)
            new_ds['data'] = new_data
            new_datasets.append(new_ds)
        return new_labels, new_datasets, new_map

    def _temporal_period_key(self, value, date_type):
        d = value
        if isinstance(value, str):
            # Accept ISO date or year/month fragments
            try:
                if len(value) >= 19 and value[4] == '-':
                    # Datetime string from read_group — convert to user TZ first
                    dt = fields.Datetime.to_datetime(value)
                    local = fields.Datetime.context_timestamp(self, dt)
                    d = local.date()
                elif len(value) >= 10 and value[4] == '-':
                    d = fields.Date.to_date(value[:10])
                elif date_type == 'year' and value.isdigit():
                    return value
                elif date_type == 'month' and len(value) >= 7 and value[4] == '-':
                    return value[:7]
                elif date_type == 'quarter' and '-Q' in value.upper():
                    return value.upper().replace(' ', '')
                elif date_type == 'week' and 'W' in value.upper():
                    return value.upper().replace(' ', '')
            except Exception:
                return str(value)
        if isinstance(d, datetime.datetime):
            local = fields.Datetime.context_timestamp(self, d)
            d = local.date()
        if not isinstance(d, datetime.date):
            return str(value) if value not in (None, False) else False
        if date_type == 'year':
            return str(d.year)
        if date_type == 'quarter':
            return f"{d.year}-Q{(d.month - 1) // 3 + 1}"
        if date_type == 'month':
            return f"{d.year}-{d.month:02d}"
        if date_type == 'week':
            iso = d.isocalendar()
            return f"{iso[0]}-W{iso[1]:02d}"
        return d.isoformat()

    def _temporal_period_meta(self, cursor, date_type):
        """Return (key, display_label, domain_val) for a period starting at cursor."""
        if date_type == 'year':
            key = str(cursor.year)
            return key, key, f"{cursor.year}-01-01"
        if date_type == 'quarter':
            q = (cursor.month - 1) // 3 + 1
            key = f"{cursor.year}-Q{q}"
            return key, f"Q{q} {cursor.year}", f"{cursor.year}-{3 * q - 2:02d}-01"
        if date_type == 'month':
            key = f"{cursor.year}-{cursor.month:02d}"
            label = cursor.strftime('%B %Y')
            return key, label, f"{cursor.year}-{cursor.month:02d}-01"
        if date_type == 'week':
            iso = cursor.isocalendar()
            key = f"{iso[0]}-W{iso[1]:02d}"
            return key, f"W{iso[1]:02d} {iso[0]}", cursor.isoformat()
        key = cursor.isoformat()
        return key, cursor.strftime('%d %b %Y'), cursor.isoformat()

    def _merge_additional_sources(self, item, labels, datasets, date_range=None, drill_date_type=None):
        """Append extra source series, aligning labels across models."""
        labels = list(labels or [])
        datasets = [dict(ds) for ds in (datasets or [])]
        for src in item.source_ids.sorted(key=lambda s: (s.sequence, s.id)):
            values_map, src_labels, meta = src._get_source_series(
                item,
                date_range=date_range,
                drill_date_type=drill_date_type,
            )
            if meta.get('error'):
                continue
            for lab in src_labels:
                if lab not in labels:
                    labels.append(lab)
            # Pad existing datasets for new labels
            for ds in datasets:
                while len(ds['data']) < len(labels):
                    ds['data'].append(0)
            data_arr = [values_map.get(lab, 0) for lab in labels]
            datasets.append({
                'label': meta.get('name') or src.name,
                'data': data_arr,
                'yAxisID': 'y',
                'series_chart_type': meta.get('series_chart_type') or 'column',
            })
            # Pad this new series if labels grew earlier (already aligned)
        # Ensure every dataset length matches labels
        for ds in datasets:
            if len(ds['data']) < len(labels):
                ds['data'].extend([0] * (len(labels) - len(ds['data'])))
            elif len(ds['data']) > len(labels):
                ds['data'] = ds['data'][:len(labels)]
        return labels, datasets

    def _get_scatter_xy_data(self, item, model, domain, agg, date_type=None):
        """Build true XY scatter points from measure X / measure Y."""
        x_field = item.scatter_measure_x_id.name
        y_field = item.scatter_measure_y_id.name
        points = []
        labels = []

        if item.is_scatter_group and item.group_by_field_id:
            groupby_main = item.group_by_field_id.name
            if item.group_by_field_id.ttype in ('date', 'datetime'):
                groupby_main = f"{groupby_main}:{date_type or item.group_by_date_type or 'month'}"
            rows = model.formatted_read_group(
                domain,
                groupby=[groupby_main],
                aggregates=[f"{x_field}:{agg}", f"{y_field}:{agg}", '__count'],
                limit=item.record_limit or None,
            )
            for res in rows:
                raw = res.get(groupby_main)
                if isinstance(raw, tuple):
                    label = str(raw[1] or 'Undefined')
                else:
                    label = str(raw or 'Undefined')
                xv = res.get(f"{x_field}:{agg}", 0) or 0
                yv = res.get(f"{y_field}:{agg}", 0) or 0
                if item.multiplier_active:
                    xv *= item.multiplier_value
                    yv *= item.multiplier_value
                labels.append(label)
                points.append({'x': xv, 'y': yv, 'category': label})
        else:
            fields_read = [x_field, y_field, 'display_name']
            records = model.search_read(
                domain,
                fields_read,
                limit=item.record_limit or 200,
            )
            for rec in records:
                xv = rec.get(x_field) or 0
                yv = rec.get(y_field) or 0
                if isinstance(xv, (list, tuple)):
                    xv = xv[0] or 0
                if isinstance(yv, (list, tuple)):
                    yv = yv[0] or 0
                if item.multiplier_active:
                    xv *= item.multiplier_value
                    yv *= item.multiplier_value
                label = rec.get('display_name') or str(rec.get('id'))
                labels.append(label)
                points.append({'x': xv, 'y': yv, 'category': label})

        return {
            'labels': labels,
            'scatter_points': points,
            'datasets': [{
                'label': f"{item.scatter_measure_x_id.field_description} × {item.scatter_measure_y_id.field_description}",
                'data': [p['y'] for p in points],
                'yAxisID': 'y',
            }],
            'group_by_field': item.group_by_field_id.name if item.group_by_field_id else False,
            'scatter_xy': True,
            'enable_drill_down': False,
            'label_domain_map': {},
            'custom_segment_colors': {},
            'has_sub_group': False,
            'next_drill_date_type': False,
        }

    _SQL_FORBIDDEN = re.compile(
        r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|COPY|'
        r'EXECUTE|EXEC|CALL|MERGE|REPLACE|ATTACH|DETACH|VACUUM|REINDEX|CLUSTER|'
        r'COMMENT|LISTEN|NOTIFY|LOAD|INTO\s+OUTFILE|INTO\s+DUMPFILE|'
        r'SET\s+ROLE|SET\s+SESSION|SECURITY\s+DEFINER)\b',
        re.IGNORECASE,
    )

    def _validate_sql_query(self, query):
        """Allow only a single SELECT / WITH … SELECT statement."""
        if not query or not str(query).strip():
            raise UserError(_('SQL Query is empty.'))
        cleaned = re.sub(r'/\*.*?\*/', '', str(query), flags=re.DOTALL)
        cleaned = re.sub(r'--.*?$', '', cleaned, flags=re.MULTILINE).strip()
        if not cleaned:
            raise UserError(_('SQL Query is empty.'))
        body = cleaned.rstrip(';').strip()
        if ';' in body:
            raise UserError(_('Multiple SQL statements are not allowed.'))
        first = body.lstrip('(').strip()
        if not re.match(r'^(WITH|SELECT)\b', first, re.IGNORECASE):
            raise UserError(_('Only SELECT queries are allowed (WITH … SELECT is supported).'))
        if self._SQL_FORBIDDEN.search(body):
            raise UserError(_('Forbidden SQL keyword detected. Only read-only SELECT queries are allowed.'))
        return body

    def _prepare_sql_query(self, query, kwargs=None):
        """Validate, substitute date/user placeholders, and enforce row limit."""
        kwargs = kwargs or {}
        prepared = self._validate_sql_query(query)

        date_filter = kwargs.get('global_date_filter', 'none')
        if date_filter == 'none':
            date_filter = self.date_filter_selection or 'none'
        today = fields.Date.context_today(self)
        start_date, end_date, _, _ = self._resolve_date_range(
            date_filter, today=today, item=self
        )

        def _fmt(val):
            if not val:
                return ''
            if isinstance(val, datetime.datetime):
                return fields.Datetime.to_string(val)
            if isinstance(val, datetime.date):
                return fields.Date.to_string(val)
            return str(val)

        start_s = _fmt(start_date) or '1900-01-01'
        end_s = _fmt(end_date) or '2099-12-31'
        uid = str(self.env.uid)
        company_id = str(self.env.company.id)

        prepared = prepared.replace('%', '%%')

        params = {
            'start_date': start_s,
            'end_date': end_s,
            'uid': int(uid) if uid.isdigit() else uid,
            'company_id': int(company_id) if company_id.isdigit() else company_id,
        }

        replacements_map = {
            '{start_date}': 'start_date', '{end_date}': 'end_date',
            '{uid}': 'uid', '{user_id}': 'uid', '{company_id}': 'company_id',
            '%%START_DATE%%': 'start_date', '%%END_DATE%%': 'end_date',
            '%%UID%%': 'uid', '%%USER_ID%%': 'uid', '%%COMPANY_ID%%': 'company_id',
        }
        for key, param_name in replacements_map.items():
            pattern_with_quotes = r"['\"]" + re.escape(key) + r"['\"]"
            prepared = re.sub(pattern_with_quotes, f"%({param_name})s", prepared, flags=re.IGNORECASE)
            pattern_without = re.escape(key)
            prepared = re.sub(pattern_without, f"%({param_name})s", prepared, flags=re.IGNORECASE)

        limit = max(1, int(self.sql_row_limit or 5000))
        if not re.search(r'\bLIMIT\s+\d+', prepared, re.IGNORECASE):
            prepared = f"{prepared} LIMIT {limit}"
        return prepared, limit, params

    def _execute_sql_query(self, query, connection=None, params=None):
        """Run a prepared SELECT against local DB or an external connection."""
        if params is None:
            params = {}

        if connection:
            if connection.connection_type == 'postgres':
                import psycopg2
                conn_kwargs = {
                    'host': connection.host,
                    'port': connection.port,
                    'user': connection.user,
                    'password': connection.password,
                    'database': connection.database,
                }
                if connection.use_ssl:
                    conn_kwargs['sslmode'] = 'require'
                conn = psycopg2.connect(**conn_kwargs)
                try:
                    cur = conn.cursor()
                    cur.execute(query, params)
                    columns = [desc[0] for desc in cur.description] if cur.description else []
                    return [dict(zip(columns, row)) for row in cur.fetchall()]
                finally:
                    conn.close()
            if connection.connection_type == 'mysql':
                import mysql.connector
                conn_kwargs = {
                    'host': connection.host,
                    'port': connection.port,
                    'user': connection.user,
                    'password': connection.password,
                    'database': connection.database,
                }
                if connection.use_ssl:
                    conn_kwargs['ssl_disabled'] = False
                conn = mysql.connector.connect(**conn_kwargs)
                try:
                    cur = conn.cursor(dictionary=True)
                    cur.execute(query, params)
                    return list(cur.fetchall() or [])
                finally:
                    conn.close()
            if connection.connection_type == 'mssql':
                import pymssql
                conn = pymssql.connect(
                    server=connection.host,
                    port=str(connection.port or 1433),
                    user=connection.user,
                    password=connection.password,
                    database=connection.database,
                )
                try:
                    cur = conn.cursor(as_dict=True)
                    cur.execute(query, params)
                    return list(cur.fetchall() or [])
                finally:
                    conn.close()
            raise UserError(_('Unsupported connection type for SQL: %s') % connection.connection_type)

        # Protect the ambient ORM transaction: a failed user SELECT would otherwise
        # abort the whole PostgreSQL transaction (InFailedSqlTransaction on save).
        with self.env.cr.savepoint(flush=False):
            self.env.cr.execute(query, params)
            return self.env.cr.dictfetchall()

    def action_validate_sql(self):
        self.ensure_one()
        prepared, _limit, params = self._prepare_sql_query(self.query or '', {})
        try:
            rows = self._execute_sql_query(prepared, self.external_connection_id, params=params)
            cols = list(rows[0].keys()) if rows else []
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('SQL Valid'),
                    'message': _('Query OK. %s row(s), columns: %s') % (
                        len(rows), ', '.join(cols) or '(none)'
                    ),
                    'type': 'success',
                    'sticky': False,
                },
            }
        except Exception as e:
            raise UserError(_('SQL validation failed: %s') % e) from e

    @api.model
    def vqb_test_sql(self, query, connection_id=False):
        """Dry-run a SELECT from the Visual Query Builder (no record required)."""
        connection = False
        if connection_id:
            connection = self.env['dynamic.dashboard.connection'].browse(connection_id)
            if not connection.exists():
                connection = False
        # Temporary shell record so placeholder helpers work
        shell = self.new({
            'query': query or '',
            'external_connection_id': connection.id if connection else False,
            'date_filter_selection': 'none',
            'sql_row_limit': 20,
        })
        try:
            prepared, _limit, params = shell._prepare_sql_query(query or '', {})
            rows = shell._execute_sql_query(prepared, connection, params=params)
            cols = list(rows[0].keys()) if rows else []
            return {
                'ok': True,
                'rows': len(rows),
                'columns': cols,
                'sample': rows[:3],
                'message': _('Query OK — %s row(s). Columns: %s') % (
                    len(rows), ', '.join(cols) or '(none)',
                ),
            }
        except Exception as e:
            tip = self._vqb_error_tip(str(e))
            return {
                'ok': False,
                'error': str(e),
                'tip': tip,
                'message': _('SQL failed: %s') % e,
            }

    @api.model
    def _vqb_error_tip(self, err):
        """Map common PostgreSQL / Odoo errors to actionable guidance."""
        e = (err or '').lower()
        if 'does not exist' in e and 'relation' in e:
            return _(
                'The table was not found. Use Odoo model technical names '
                '(e.g. sale.order → sale_order). Check spelling and that the module is installed.'
            )
        if 'does not exist' in e and 'column' in e:
            return _(
                'A column was not found. Open the Field dropdown again and pick a listed field, '
                'or remove fields that belong to a different joined table.'
            )
        if 'must appear in the group by' in e or 'not in aggregate' in e:
            return _(
                'You mixed aggregates (SUM/COUNT/…) with plain columns. '
                'Either add those columns to GROUP BY, or wrap them in an aggregate too.'
            )
        if 'having' in e and 'group' in e:
            return _('HAVING needs a GROUP BY. Add grouping columns first, then filter aggregates.')
        if 'syntax error' in e:
            return _(
                'SQL syntax error. Check operators, quotes around text values '
                "(e.g. 'draft'), and that BETWEEN uses: 1 AND 10."
            )
        if 'permission' in e or 'access' in e:
            return _('Database permission denied. Use an allowed connection or ask an admin.')
        if 'ambiguous' in e:
            return _(
                'A column name exists on multiple joined tables. '
                'Pick the table explicitly for each field, or set a JOIN alias.'
            )
        if 'forbidden' in e or 'only select' in e:
            return _('Only read-only SELECT / WITH…SELECT queries are allowed.')
        return _(
            'Review the Generated SQL Preview, fix the highlighted builder warnings, '
            'then click Test Query again.'
        )

    @api.model
    def _dd_scoped_model(self, model_name):
        """Return ``env[model_name]``, optionally scoped to a website viewer.

        Website published boards fetch item payloads under ``sudo()`` so that
        ``ir.model`` / ``ir.model.fields`` config remains readable for users
        outside Dynamic Dashboard groups.  When ``dd_website_fetch_uid`` is set
        in the context, source-model queries still run as that user so ACLs and
        record rules stay intact.
        """
        if not model_name:
            return None
        Model = self.env[model_name]
        uid = self.env.context.get('dd_website_fetch_uid')
        if uid and int(uid) != self.env.uid:
            Model = Model.with_user(int(uid))
        return Model

    def fetch_item_data(self, item_id, **kwargs):
        item = self.browse(item_id)
        if not item.exists():
            return {}
        return item._get_item_data_dict(**kwargs)

    @api.model
    def fetch_items_data(self, item_ids, shared_kwargs=None, per_item_kwargs=None):
        """Batch-fetch dashboard item payloads in one RPC (avoids N round-trips on load).

        :param item_ids: list of item ids
        :param shared_kwargs: kwargs applied to every item (global_date_filter, …)
        :param per_item_kwargs: optional {item_id: kwargs} overrides (e.g. custom_filter_domains)
        :return: dict {item_id: payload}
        """
        if not item_ids:
            return {}
        shared = dict(shared_kwargs or {})
        per_item = per_item_kwargs or {}
        result = {}
        items = self.browse([int(i) for i in item_ids]).exists()
        for item in items:
            kw = dict(shared)
            extra = per_item.get(str(item.id)) or per_item.get(item.id) or {}
            if isinstance(extra, dict):
                kw.update(extra)
            try:
                result[item.id] = item._get_item_data_dict(**kw)
            except Exception as err:
                _logger = __import__('logging').getLogger(__name__)
                _logger.exception("fetch_items_data failed for item %s", item.id)
                result[item.id] = {
                    'id': item.id,
                    'name': item.name,
                    'item_type': item.item_type,
                    'error': str(err),
                }
        return result

    @api.model
    def update_user_preference(self, record_id, values):
        """Allows users to save their layout overrides (e.g. grid positioning, chart type) without modifying the base item."""
        import json
        item = self.browse(record_id)
        if not item.exists():
            return False
            
        pref = self.env['dynamic.dashboard.user.preference'].search([
            ('user_id', '=', self.env.user.id),
            ('dashboard_id', '=', item.dashboard_id.id),
            ('item_id', '=', record_id)
        ], limit=1)
        
        if pref:
            data = json.loads(pref.preference_data or '{}')
            data.update(values)
            pref.preference_data = json.dumps(data)
        else:
            self.env['dynamic.dashboard.user.preference'].create({
                'dashboard_id': item.dashboard_id.id,
                'item_id': record_id,
                'preference_data': json.dumps(values)
            })
        return True

    def _serialize_item_currency(self, item=None):
        """Company / item / KPI currency for multi-currency display."""
        item = item or self
        explicit = item.currency_id
        if not explicit and item.kpi_id and item.kpi_id.currency_id:
            explicit = item.kpi_id.currency_id
        currency = resolve_display_currency(
            self.env, item=item, company=item.company_id, explicit=explicit or None,
        )
        return serialize_currency(currency)

    def _serialize_number_system(self, item):
        if not item.number_system_id:
            return False
        return [{
            'threshold': line.threshold,
            'divisor': line.divisor,
            'suffix': line.suffix,
        } for line in item.number_system_id.line_ids.sorted(
            key=lambda l: l.threshold, reverse=True
        )]

    def _serialize_segment_colors(self, item):
        colors = {}
        for sc in item.segment_color_ids:
            if sc.segment_name and sc.color:
                colors[sc.segment_name] = sc.color
        return colors

    HIERARCHY_TYPES = frozenset({
        'treemap', 'sunburst', 'forceDirected', 'pack',
        'tree', 'partition', 'voronoiTreemap',
    })
    FLOW_TYPES = frozenset({
        'sankey', 'chord', 'chordDirected', 'chordNonRibbon', 'arcDiagram',
    })
    MATRIX_TYPES = frozenset({'heatmap', 'matrixHeatmap'})
    MAP_TYPES = frozenset({'map', 'mapPoints'})

    def _enrich_chart_payload(self, result, item=None, model=None, domain=None):
        """Attach hierarchy / flow / OHLC / word-cloud / matrix structures when needed."""
        item = item or self
        domain = domain if domain is not None else []
        itype = item.item_type

        # Hierarchy tree from labels + datasets (subgroup) or flat categories
        if itype in self.HIERARCHY_TYPES:
            result['hierarchy_data'] = self._build_hierarchy_data(result)

        # Matrix cells from subgroup datasets
        if itype in self.MATRIX_TYPES:
            result['matrix_data'] = self._build_matrix_data(result)

        # Flow links
        if itype in self.FLOW_TYPES and model is not None:
            flow = self._build_flow_data(item, model, domain)
            if flow:
                result['flow_data'] = flow

        # Word cloud terms
        if itype == 'wordCloud' and model is not None:
            words = self._build_word_cloud_data(item, model, domain)
            if words:
                result['word_cloud_data'] = words

        # OHLC candlestick / OHLC stick points
        if itype in ('candlestick', 'ohlc'):
            ohlc = []
            if model is not None:
                ohlc = self._build_ohlc_data(item, model, domain, result)
            if not ohlc:
                ohlc = self._synthesize_ohlc_from_series(result)
            if ohlc:
                result['ohlc_data'] = ohlc

        # Waterfall open/step values derived from sequential categories
        if itype == 'waterfall':
            result['waterfall_data'] = self._build_waterfall_data(result)

        return result

    def _build_hierarchy_data(self, result):
        labels = result.get('labels') or []
        datasets = result.get('datasets') or []
        if not labels:
            return [{'name': 'Root', 'children': []}]
        if len(datasets) > 1:
            # Parent = label, children = each dataset series value
            children = []
            for i, lab in enumerate(labels):
                kids = []
                for ds in datasets:
                    vals = ds.get('data') or []
                    kids.append({
                        'name': str(ds.get('label') or ''),
                        'value': float(vals[i] or 0) if i < len(vals) else 0.0,
                    })
                children.append({
                    'name': str(lab),
                    'children': kids,
                    'value': sum(k['value'] for k in kids),
                })
            return [{'name': 'Root', 'children': children}]
        data = (datasets[0].get('data') if datasets else result.get('data')) or []
        children = []
        for i, lab in enumerate(labels):
            children.append({
                'name': str(lab),
                'value': float(data[i] or 0) if i < len(data) else 0.0,
            })
        return [{'name': 'Root', 'children': children}]

    def _build_matrix_data(self, result):
        """Build {x, y, value} cells from labels × datasets."""
        labels = result.get('labels') or []
        datasets = result.get('datasets') or []
        cells = []
        if not labels:
            return cells
        if len(datasets) > 1:
            for ds in datasets:
                y = str(ds.get('label') or '')
                vals = ds.get('data') or []
                for i, lab in enumerate(labels):
                    cells.append({
                        'x': str(lab),
                        'y': y,
                        'value': float(vals[i] or 0) if i < len(vals) else 0.0,
                    })
        else:
            data = (datasets[0].get('data') if datasets else result.get('data')) or []
            for i, lab in enumerate(labels):
                cells.append({
                    'x': str(lab),
                    'y': 'Value',
                    'value': float(data[i] or 0) if i < len(data) else 0.0,
                })
        return cells

    def _build_flow_data(self, item, model, domain):
        src_f = item.flow_source_field_id
        tgt_f = item.flow_target_field_id
        if not src_f or not tgt_f:
            # Fallback: group_by + sub_group_by as source/target
            if item.group_by_field_id and item.sub_group_by_field_id:
                src_name = item.group_by_field_id.name
                tgt_name = item.sub_group_by_field_id.name
            else:
                return []
        else:
            src_name = src_f.name
            tgt_name = tgt_f.name
        measure = item.measure_field_ids[:1]
        agg = 'avg' if item.data_type == 'average' else (item.data_type or 'sum')
        if agg == 'count' or not measure:
            aggregates = ['__count']
            measure_key = '__count'
        else:
            mname = measure.name
            aggregates = [f'{mname}:{agg}', '__count']
            measure_key = f'{mname}:{agg}'
        try:
            rows = model.formatted_read_group(
                domain,
                groupby=[src_name, tgt_name],
                aggregates=aggregates,
                limit=item.record_limit or 5000,
            )
        except Exception:
            return []
        links = []
        for row in rows:
            s = row.get(src_name)
            t = row.get(tgt_name)
            if isinstance(s, tuple):
                s = s[1]
            if isinstance(t, tuple):
                t = t[1]
            s = str(s or 'Undefined')
            t = str(t or 'Undefined')
            val = row.get(measure_key, 0) or 0
            if item.multiplier_active:
                val = val * item.multiplier_value
            links.append({'source': s, 'target': t, 'value': float(val)})
        return links

    def _build_word_cloud_data(self, item, model, domain):
        field = item.word_cloud_field_id or item.group_by_field_id
        if not field:
            return []
        fname = field.name
        try:
            rows = model.formatted_read_group(
                domain,
                groupby=[fname],
                aggregates=['__count'],
                limit=item.record_limit or 200,
                order='__count DESC',
            )
        except Exception:
            return []
        words = []
        for row in rows:
            raw = row.get(fname)
            if isinstance(raw, tuple):
                raw = raw[1]
            text = str(raw or '').strip()
            if not text:
                continue
            words.append({'category': text, 'value': float(row.get('__count') or 0)})
        return words

    def _build_ohlc_data(self, item, model, domain, result):
        open_f = item.measure_open_field_id
        high_f = item.measure_high_field_id
        low_f = item.measure_low_field_id
        close_f = item.measure_close_field_id
        # Prefer real OHLC measures when all four are configured
        if all([open_f, high_f, low_f, close_f]) and item.group_by_field_id:
            gname = item.group_by_field_id.name
            if item.group_by_field_id.ttype in ('date', 'datetime'):
                gname = f"{gname}:{item.group_by_date_type or 'day'}"
            aggregates = [
                f'{open_f.name}:avg',
                f'{high_f.name}:max',
                f'{low_f.name}:min',
                f'{close_f.name}:avg',
                '__count',
            ]
            try:
                rows = model.formatted_read_group(
                    domain,
                    groupby=[gname],
                    aggregates=aggregates,
                    limit=item.record_limit or 500,
                    order=gname,
                )
            except Exception:
                rows = []
            points = []
            for row in rows:
                raw = row.get(gname)
                domain_val = raw
                if isinstance(raw, tuple):
                    domain_val = raw[0]
                    label = str(raw[1])
                else:
                    label = str(raw or '')
                o_val = float(row.get(f'{open_f.name}:avg') or 0)
                h_val = float(row.get(f'{high_f.name}:max') or 0)
                l_val = float(row.get(f'{low_f.name}:min') or 0)
                c_val = float(row.get(f'{close_f.name}:avg') or 0)
                # Keep high/low valid relative to open/close
                h_val = max(h_val, o_val, c_val)
                l_val = min(l_val, o_val, c_val)
                points.append({
                    'category': label,
                    'open': o_val,
                    'high': h_val,
                    'low': l_val,
                    'close': c_val,
                    'date': domain_val if isinstance(domain_val, str) else label,
                })
            if points:
                return points
        # Fallback: synthesize OHLC from the standard category/value series so
        # Switch Layout → Candlestick still renders without dedicated OHLC fields.
        return self._synthesize_ohlc_from_series(result)

    def _synthesize_ohlc_from_series(self, result):
        """Build plausible OHLC candles from a single measure series."""
        labels = result.get('labels') or []
        datasets = result.get('datasets') or []
        values = (datasets[0].get('data') if datasets else result.get('data')) or []
        points = []
        prev_close = None
        for i, lab in enumerate(labels):
            close = float(values[i] or 0) if i < len(values) else 0.0
            open_v = float(prev_close) if prev_close is not None else close
            high = max(open_v, close)
            low = min(open_v, close)
            span = abs(close - open_v)
            if span <= 0:
                span = abs(close) * 0.05 or 1.0
            high = high + span * 0.25
            low = low - span * 0.25
            points.append({
                'category': str(lab),
                'open': open_v,
                'high': high,
                'low': low,
                'close': close,
                'date': str(lab),
            })
            prev_close = close
        return points

    def _build_waterfall_data(self, result):
        labels = result.get('labels') or []
        datasets = result.get('datasets') or []
        data = (datasets[0].get('data') if datasets else result.get('data')) or []
        points = []
        running = 0.0
        for i, lab in enumerate(labels):
            val = float(data[i] or 0) if i < len(data) else 0.0
            open_v = running
            running += val
            points.append({
                'category': str(lab),
                'value': running,
                'openValue': open_v,
                'stepValue': val,
            })
        return points

    def _apply_item_display_options(self, result, item=None):
        """Ensure Display-tab settings always win over linked Analysis/KPI payloads."""
        item = item or self
        pref_uid = int(self.env.context.get('dd_website_fetch_uid') or self.env.uid)

        # Resolve dashboard theme from user preference if available
        dashboard_theme = item.dashboard_id.chart_theme
        Pref = self.env['dynamic.dashboard.user.preference'].sudo()
        dash_pref = Pref.search([
            ('user_id', '=', pref_uid),
            ('dashboard_id', '=', item.dashboard_id.id),
            ('item_id', '=', False)
        ], limit=1)
        if dash_pref and dash_pref.preference_data:
            import json
            try:
                data = json.loads(dash_pref.preference_data)
                if 'chart_theme' in data:
                    dashboard_theme = data['chart_theme']
            except Exception:
                pass

        # Item-level preference (viewer overrides) wins over DB field / dashboard theme
        item_theme = getattr(item, 'chart_theme', False) or False
        item_pref = Pref.search([
            ('user_id', '=', pref_uid),
            ('dashboard_id', '=', item.dashboard_id.id),
            ('item_id', '=', item.id),
        ], limit=1)
        if item_pref and item_pref.preference_data:
            import json
            try:
                pdata = json.loads(item_pref.preference_data)
                if 'chart_theme' in pdata and pdata['chart_theme']:
                    item_theme = pdata['chart_theme']
            except Exception:
                pass

        effective_theme = item_theme or dashboard_theme or 'default'

        result.update({
            'theme': effective_theme,
            'chart_theme': effective_theme,
            'is_stacked': item.is_stacked,
            'is_stacked_100': item.is_stacked_100,
            'show_records': item.show_records,
            'tile_layout': item.tile_layout or 'layout1',
            'tile_theme': item.tile_theme or 'ocean',
            'scorecard_columns': item.scorecard_columns or 'auto',
            'tile_color': item.tile_color,
            'tile_icon': item.tile_icon,
            'color': item.tile_color or result.get('color'),
            'icon': item.tile_icon or result.get('icon') or 'fa-bar-chart',
            'unit': item.unit,
            'unit_position': item.unit_position,
            'enable_target': item.enable_target,
            'target_view': item.target_view,
            'hide_legend': item.hide_legend or item.legend_position == 'none',
            'legend_position': item.legend_position or 'bottom',
            'show_data_value': item.show_data_value,
            'show_tooltip': item.show_tooltip,
            'enable_animation': item.enable_animation,
            'chart_animation_duration': item.chart_animation_duration or 800,
            'enable_zoom': item.enable_zoom,
            'enable_pan': item.enable_pan,
            'show_scrollbar_x': item.show_scrollbar_x,
            'show_scrollbar_y': item.show_scrollbar_y,
            'show_cursor': item.show_cursor,
            'show_grid': item.show_grid,
            'show_export_menu': item.show_export_menu,
            'enable_slice_grouper': item.enable_slice_grouper,
            'enable_heat_rules': item.enable_heat_rules,
            'map_projection': item.map_projection or 'mercator',
            'show_map_labels': item.show_map_labels,
            'show_map_zoom_control': item.show_map_zoom_control,
            'map_exclude_antarctica': item.map_exclude_antarctica,
            'show_heat_legend': item.show_heat_legend,
            'cursor_snap': item.cursor_snap,
            'show_line_bullets': item.show_line_bullets,
            'bullet_radius': item.bullet_radius if item.bullet_radius is not False else 5,
            'line_stroke_width': item.line_stroke_width if item.line_stroke_width is not False else 2.75,
            'area_fill_opacity': item.area_fill_opacity if item.area_fill_opacity is not False else 0.22,
            'column_corner_radius': item.column_corner_radius if item.column_corner_radius is not False else 6,
            'column_width_percent': item.column_width_percent if item.column_width_percent is not False else 68,
            'pie_radius': item.pie_radius if item.pie_radius is not False else 70,
            'pie_inner_radius': item.pie_inner_radius if item.pie_inner_radius is not False else 50,
            'label_position': item.label_position or 'auto',
            'amcharts_ui_theme': item.amcharts_ui_theme or 'animated',
            'force_many_body_strength': item.force_many_body_strength if item.force_many_body_strength is not False else -15.0,
            'force_center_strength': item.force_center_strength if item.force_center_strength is not False else 0.5,
            'hierarchy_initial_depth': item.hierarchy_initial_depth or 2,
            'serpentine_level_count': item.serpentine_level_count or 3,
            'funnel_orientation': item.funnel_orientation or 'vertical',
            'funnel_bottom_ratio': item.funnel_bottom_ratio if item.funnel_bottom_ratio is not False else 0.1,
            'word_cloud_randomness': item.word_cloud_randomness if item.word_cloud_randomness is not False else 0.1,
            'slice_group_threshold': item.slice_group_threshold if item.slice_group_threshold is not False else 5.0,
            'show_axis_labels': item.show_axis_labels,
            'rotate_category_labels': item.rotate_category_labels,
            'category_label_max_width': item.category_label_max_width or 110,
            'axis_min': item.axis_min if item.axis_min is not False else None,
            'axis_max': item.axis_max if item.axis_max is not False else None,
            'logarithmic_scale': item.logarithmic_scale,
            'min_grid_distance': item.min_grid_distance or 30,
            'chart_padding_top': item.chart_padding_top if item.chart_padding_top is not False else 12,
            'chart_padding_right': item.chart_padding_right if item.chart_padding_right is not False else 16,
            'chart_padding_bottom': item.chart_padding_bottom if item.chart_padding_bottom is not False else 8,
            'chart_padding_left': item.chart_padding_left if item.chart_padding_left is not False else 8,
            'legend_clickable': item.legend_clickable,
            'legend_scrollable': item.legend_scrollable,
            'legend_marker_size': item.legend_marker_size or 11,
            'series_fill_opacity': item.series_fill_opacity if item.series_fill_opacity is not False else 1.0,
            'column_stroke_width': item.column_stroke_width if item.column_stroke_width is not False else 0.0,
            'column_stroke_opacity': item.column_stroke_opacity if item.column_stroke_opacity is not False else 0.0,
            'mask_bullets': item.mask_bullets,
            'connect_nulls': item.connect_nulls,
            'line_tension': item.line_tension if item.line_tension is not False else 0.5,
            'step_to': item.step_to or 'left',
            'pie_start_angle': item.pie_start_angle if item.pie_start_angle is not False else -90,
            'pie_end_angle': item.pie_end_angle if item.pie_end_angle is not False else 270,
            'slice_stroke_width': item.slice_stroke_width if item.slice_stroke_width is not False else 2.0,
            'show_slice_ticks': item.show_slice_ticks,
            'slice_hover_scale': item.slice_hover_scale if item.slice_hover_scale is not False else 1.04,
            'tooltip_pointer_orientation': item.tooltip_pointer_orientation or 'vertical',
            'gauge_min': item.gauge_min if item.gauge_min is not False else 0.0,
            'gauge_max': item.gauge_max if item.gauge_max is not False else 0.0,
            'gauge_start_angle': item.gauge_start_angle if item.gauge_start_angle is not False else -210,
            'gauge_end_angle': item.gauge_end_angle if item.gauge_end_angle is not False else 30,
            'hierarchy_top_depth': item.hierarchy_top_depth if item.hierarchy_top_depth is not False else 1,
            'show_node_labels': item.show_node_labels,
            'force_link_strength': item.force_link_strength if item.force_link_strength is not False else 0.5,
            'node_padding': item.node_padding if item.node_padding is not False else 4,
            'sankey_node_align': item.sankey_node_align or 'justify',
            'sankey_node_width': item.sankey_node_width or 10,
            'sankey_node_padding': item.sankey_node_padding or 8,
            'chord_pad_angle': item.chord_pad_angle if item.chord_pad_angle is not False else 0.02,
            'show_flow_labels': item.show_flow_labels,
            'word_min_font_size': item.word_min_font_size or 8,
            'word_max_font_size': item.word_max_font_size or 48,
            'word_min_length': item.word_min_length or 2,
            'word_angles_mode': item.word_angles_mode or 'mixed',
            'map_home_zoom_level': item.map_home_zoom_level if item.map_home_zoom_level is not False else 1.0,
            'map_pan_x_mode': item.map_pan_x_mode or 'rotateX',
            'map_fill_opacity': item.map_fill_opacity if item.map_fill_opacity is not False else 1.0,
            'timeline_orientation': item.timeline_orientation or 'horizontal',
            'curve_distance': item.curve_distance or 40,
            'heat_min_color': item.heat_min_color or '#eff6ff',
            'heat_max_color': item.heat_max_color or '#1d4ed8',
            'show_cursor_line_x': item.show_cursor_line_x,
            'show_cursor_line_y': item.show_cursor_line_y,
            'chart_number_format': item.chart_number_format or '#,###.##',
            'show_category_axis': item.show_category_axis,
            'show_value_axis': item.show_value_axis,
            'scatter_fill_opacity': item.scatter_fill_opacity if item.scatter_fill_opacity is not False else 0.85,
            'data_format': item.data_format,
            'background_color': item.background_color,
            'font_color': item.font_color,
            'is_semi_circle': item.is_semi_circle,
            'enable_drill_down': item.enable_drill_down,
            'precision_digits': item.precision_digits if item.precision_digits is not False else 2,
            'pagination_limit': item.pagination_limit or 0,
            'export_all_records': item.export_all_records,
            'fill_temporal': item.fill_temporal,
            'number_system': self._serialize_number_system(item),
            'custom_segment_colors': self._serialize_segment_colors(item),
            'currency': self._serialize_item_currency(item),
            'lang': self.env.lang,
            'locale': (self.env.lang or 'en_US').replace('_', '-'),
        })
        return result

    def _base_item_result(self, item=None):
        item = item or self
        try:
            visual_config = json.loads(item.visual_config or '{}')
        except Exception:
            visual_config = {}
        result = {
            'id': item.id,
            'name': item.name,
            'type': item.item_type,
            'item_type': item.item_type,
            'model': item.sudo().model_id.model if item.sudo().model_id else False,
            'domain': safe_eval(item.domain or '[]'),
            'action_type': item.action_type,
            'action_id': item.action_id.id if item.action_id else False,
            'client_action_tag': item.client_action_id.tag if item.client_action_id else False,
            'action_url': item.action_url or False,
            'list_view_type': item.list_view_type,
            'list_view_layout': item.list_view_layout,
            'visual_config': visual_config,
            'list_show_grand_total': item.list_show_grand_total,
            'list_column_min_width': item.list_column_min_width or 80,
            'analysis_id': item.analysis_id.id if item.analysis_id else False,
            'kpi_id': item.kpi_id.id if item.kpi_id else False,
        }
        return self._apply_item_display_options(result, item)

    @api.model
    def _ai_gemini_model_candidates(self, preferred=None):
        """Ordered Gemini model ids to try."""
        built_in = [
            'gemini-2.0-flash',
            'gemini-1.5-flash',
            'gemini-2.5-flash',
            'gemini-3.5-flash',
            'gemini-pro',
        ]
        ordered = []
        for name in (preferred, *built_in):
            if not name:
                continue
            name = str(name).strip().removeprefix('models/')
            if not name or name in ordered:
                continue
            ordered.append(name)
        return ordered or ['gemini-1.5-flash']

    @api.model
    def _ai_list_gemini_models(self, api_key):
        """Return model ids that support generateContent (best-effort)."""
        import requests
        try:
            res = requests.get(
                f'https://generativelanguage.googleapis.com/v1beta/models?key={api_key}',
                timeout=20,
            )
            if res.status_code >= 400:
                return []
            models = []
            for m in (res.json() or {}).get('models') or []:
                methods = m.get('supportedGenerationMethods') or []
                if 'generateContent' not in methods:
                    continue
                mid = (m.get('name') or '').removeprefix('models/')
                if mid:
                    models.append(mid)
            # Prefer flash / lite names first
            models.sort(key=lambda n: (0 if 'flash' in n else 1, 0 if 'lite' in n else 1, n))
            return models
        except Exception:
            return []

    @api.model
    def _ai_parse_cursor_model(self, model_slug):
        """Parse 'composer-2.5' or 'composer-2.5[fast=true,effort=high]' into Cloud Agents model object."""
        slug = (model_slug or '').strip()
        if not slug or slug == 'auto':
            return None
        params = []
        mid = slug
        if '[' in slug and slug.endswith(']'):
            mid, raw = slug[:-1].split('[', 1)
            mid = mid.strip()
            for part in raw.split(','):
                part = part.strip()
                if not part or '=' not in part:
                    continue
                pid, pval = part.split('=', 1)
                params.append({'id': pid.strip(), 'value': pval.strip()})
        # Convenience aliases for -fast suffix
        if mid.endswith('-fast') and not params:
            base = mid[:-5]
            return {'id': base, 'params': [{'id': 'fast', 'value': 'true'}]}
        selection = {'id': mid}
        if params:
            selection['params'] = params
        return selection

    @api.model
    def _ai_cursor_chat(self, system, user, api_key, model_slug, max_tokens=1200):
        """Call Cursor Cloud Agents (no-repo) and return the final assistant text."""
        import time
        import requests

        key = (api_key or '').strip()
        if not key:
            raise UserError(_("Please configure your Cursor API Key in Settings → Dynamic Dashboard."))

        prompt_text = (
            f"{system}\n\n"
            f"---\n\n"
            f"{user}\n\n"
            f"---\n"
            f"Respond with the final answer only. Do not modify repositories or run shell tools. "
            f"Prefer concise JSON or plain text as requested. Soft length budget ~{max_tokens} tokens."
        )
        payload = {
            'prompt': {'text': prompt_text},
            'name': 'Dynamic Dashboard AI',
        }
        model_obj = self._ai_parse_cursor_model(model_slug)
        if model_obj:
            payload['model'] = model_obj

        headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        auth = (key, '')

        try:
            create = requests.post(
                'https://api.cursor.com/v1/agents',
                auth=auth,
                headers=headers,
                json=payload,
                timeout=60,
            )
        except Exception as e:
            raise UserError(_("Cursor API connection failed: %s") % e) from e

        if create.status_code == 401:
            raise UserError(_("Invalid Cursor API Key. Create one in Cursor Dashboard → Integrations."))
        if create.status_code >= 400:
            raise UserError(_("Cursor API error (%s): %s") % (create.status_code, (create.text or '')[:400]))

        data = create.json() or {}
        agent = data.get('agent') or {}
        run = data.get('run') or {}
        agent_id = agent.get('id')
        run_id = run.get('id')
        if not agent_id or not run_id:
            raise UserError(_("Cursor API returned no agent/run id: %s") % (data,))

        terminal = {'FINISHED', 'ERROR', 'CANCELLED', 'EXPIRED'}
        last = run
        try:
            for _ in range(90):  # ~3 minutes
                status = (last.get('status') or '').upper()
                if status in terminal:
                    break
                time.sleep(2)
                poll = requests.get(
                    f'https://api.cursor.com/v1/agents/{agent_id}/runs/{run_id}',
                    auth=auth,
                    headers={'Accept': 'application/json'},
                    timeout=30,
                )
                if poll.status_code >= 400:
                    raise UserError(_("Cursor run poll failed (%s): %s") % (
                        poll.status_code, (poll.text or '')[:300],
                    ))
                last = poll.json() or {}
            else:
                raise UserError(_("Cursor agent timed out waiting for a response."))

            status = (last.get('status') or '').upper()
            if status != 'FINISHED':
                raise UserError(_("Cursor run ended with status %s: %s") % (
                    status, (last.get('result') or last.get('error') or '')[:400],
                ))
            text = (last.get('result') or '').strip()
            if not text:
                raise UserError(_("Cursor returned an empty response."))
            return text
        finally:
            # Best-effort cleanup so dashboard chats don't litter the agent list
            try:
                requests.delete(
                    f'https://api.cursor.com/v1/agents/{agent_id}',
                    auth=auth,
                    timeout=15,
                )
            except Exception:
                try:
                    requests.post(
                        f'https://api.cursor.com/v1/agents/{agent_id}/archive',
                        auth=auth,
                        timeout=15,
                    )
                except Exception:
                    pass

    @api.model
    def _ai_chat(self, system, user):
        """Shared OpenAI/Gemini/Claude/Cursor chat helper. Returns text content."""
        import requests
        ICP = self.env['ir.config_parameter'].sudo()
        provider = ICP.get_param('dynamic_dashboard_ai_nexgen.ai_provider', 'openai') or 'openai'
        openai_key = ICP.get_param('dynamic_dashboard_ai_nexgen.openai_api_key')
        gemini_key = ICP.get_param('dynamic_dashboard_ai_nexgen.gemini_api_key')
        claude_key = ICP.get_param('dynamic_dashboard_ai_nexgen.claude_api_key')
        cursor_key = ICP.get_param('dynamic_dashboard_ai_nexgen.cursor_api_key')
        max_tokens = int(ICP.get_param('dynamic_dashboard_ai_nexgen.ai_max_tokens', '1200') or 1200)
        openai_model = ICP.get_param('dynamic_dashboard_ai_nexgen.openai_model', 'gpt-4o-mini') or 'gpt-4o-mini'
        gemini_model = ICP.get_param('dynamic_dashboard_ai_nexgen.gemini_model') or 'gemini-3.5-flash'
        gemini_model = str(gemini_model).strip().removeprefix('models/')
        claude_model = ICP.get_param('dynamic_dashboard_ai_nexgen.claude_model') or 'claude-sonnet-5'
        cursor_model = ICP.get_param('dynamic_dashboard_ai_nexgen.cursor_model') or 'composer-2.5'
        if provider == 'openai' and not openai_key:
            raise UserError(_("Please configure your OpenAI API Key in Settings → Dynamic Dashboard."))
        if provider == 'gemini' and not gemini_key:
            raise UserError(_("Please configure your Gemini API Key in Settings → Dynamic Dashboard."))
        if provider == 'claude' and not claude_key:
            raise UserError(_("Please configure your Claude API Key in Settings → Dynamic Dashboard."))
        if provider == 'cursor' and not cursor_key:
            raise UserError(_("Please configure your Cursor API Key in Settings → Dynamic Dashboard."))

        try:
            if provider == 'openai':
                res = requests.post(
                    'https://api.openai.com/v1/chat/completions',
                    headers={
                        'Authorization': f'Bearer {openai_key}',
                        'Content-Type': 'application/json',
                    },
                    json={
                        'model': openai_model,
                        'messages': [
                            {'role': 'system', 'content': system},
                            {'role': 'user', 'content': user},
                        ],
                        'temperature': 0.2,
                        'max_tokens': max_tokens,
                    },
                    timeout=90,
                )
                res.raise_for_status()
                data = res.json()
                return (data.get('choices') or [{}])[0].get('message', {}).get('content') or ''

            if provider == 'claude':
                res = requests.post(
                    'https://api.anthropic.com/v1/messages',
                    headers={
                        'x-api-key': claude_key,
                        'anthropic-version': '2023-06-01',
                        'Content-Type': 'application/json',
                    },
                    json={
                        'model': claude_model,
                        'max_tokens': max_tokens,
                        'system': system,
                        'messages': [{'role': 'user', 'content': user}],
                    },
                    timeout=90,
                )
                res.raise_for_status()
                data = res.json()
                parts = data.get('content') or []
                texts = [p.get('text') for p in parts if isinstance(p, dict) and p.get('type') == 'text']
                return '\n'.join(t for t in texts if t) or ''

            if provider == 'cursor':
                return self._ai_cursor_chat(system, user, cursor_key, cursor_model, max_tokens)

            # Gemini — try preferred + modern fallbacks, then ListModels discovery
            candidates = self._ai_gemini_model_candidates(gemini_model)
            errors = []
            for model_name in candidates:
                url = (
                    f'https://generativelanguage.googleapis.com/v1beta/models/'
                    f'{model_name}:generateContent?key={gemini_key}'
                )
                try:
                    payload = {
                        'system_instruction': {'parts': [{'text': system}]},
                        'contents': [{'parts': [{'text': user}]}],
                        'generationConfig': {
                            'temperature': 0.2,
                            'maxOutputTokens': max_tokens,
                        },
                    }
                    # Structured JSON output when supported (ignore if API rejects)
                    payload_json = dict(payload)
                    payload_json['generationConfig'] = dict(payload['generationConfig'])
                    payload_json['generationConfig']['responseMimeType'] = 'application/json'
                    res = requests.post(url, headers={'Content-Type': 'application/json'}, json=payload_json, timeout=90)
                    if res.status_code >= 400:
                        # Retry without responseMimeType for older-compatible models
                        res = requests.post(url, headers={'Content-Type': 'application/json'}, json=payload, timeout=90)
                    if res.status_code >= 400:
                        errors.append(f'{model_name}: HTTP {res.status_code} {(res.text or "")[:220]}')
                        continue
                    data = res.json()
                    candidates_resp = data.get('candidates') or []
                    if not candidates_resp:
                        errors.append(f'{model_name}: empty candidates ({(data.get("promptFeedback") or {})})')
                        continue
                    parts = (((candidates_resp[0] or {}).get('content') or {}).get('parts') or [])
                    text = (parts[0] or {}).get('text') if parts else ''
                    if text:
                        # Persist a working model so next calls skip deprecated settings
                        if gemini_model != model_name:
                            ICP.set_param('dynamic_dashboard_ai_nexgen.gemini_model', model_name)
                        return text
                    errors.append(f'{model_name}: empty text')
                except Exception as e:
                    errors.append(f'{model_name}: {e}')
                    continue

            # Discover live models and try those supporting generateContent
            discovered = [
                m for m in self._ai_list_gemini_models(gemini_key)
                if m not in candidates
            ][:8]
            for model_name in discovered:
                url = (
                    f'https://generativelanguage.googleapis.com/v1beta/models/'
                    f'{model_name}:generateContent?key={gemini_key}'
                )
                try:
                    res = requests.post(
                        url,
                        headers={'Content-Type': 'application/json'},
                        json={
                            'system_instruction': {'parts': [{'text': system}]},
                            'contents': [{'parts': [{'text': user}]}],
                            'generationConfig': {'temperature': 0.2, 'maxOutputTokens': max_tokens},
                        },
                        timeout=90,
                    )
                    if res.status_code >= 400:
                        errors.append(f'{model_name}: HTTP {res.status_code}')
                        continue
                    data = res.json()
                    parts = ((((data.get('candidates') or [{}])[0]).get('content') or {}).get('parts') or [])
                    text = (parts[0] or {}).get('text') if parts else ''
                    if text:
                        ICP.set_param('dynamic_dashboard_ai_nexgen.gemini_model', model_name)
                        return text
                except Exception as e:
                    errors.append(f'{model_name}: {e}')
                    continue

            hint = ', '.join(discovered[:5]) if discovered else 'gemini-2.0-flash / gemini-1.5-flash'
            raise UserError(_(
                'Gemini API failed for all tried models.\n\n'
                'Set a current model in Settings → Dynamic Dashboard (e.g. %(hint)s),\n'
                'or leave it blank to auto-pick.\n\n'
                'Details:\n%(details)s'
            ) % {
                'hint': hint,
                'details': '\n'.join(errors[-6:]) or _('unknown error'),
            })
        except UserError:
            raise
        except Exception as e:
            raise UserError(_('AI provider error (%s): %s') % (provider, e)) from e

    @api.model
    def suggest_fields_for_model(self, model_name):
        model = self.env['ir.model'].search([('model', '=', model_name)], limit=1)
        if not model:
            return []
        fields_recs = self.env['ir.model.fields'].search([
            ('model_id', '=', model.id),
            ('store', '=', True),
            ('ttype', 'in', ['integer', 'float', 'monetary', 'char', 'selection', 'many2one', 'date', 'datetime']),
        ], limit=40)
        catalog = [{'name': f.name, 'label': f.field_description, 'ttype': f.ttype} for f in fields_recs]
        try:
            text = self._ai_chat(
                system='Suggest the best 3 metrics and 2 dimensions for dashboards. Reply JSON: {"metrics":[],"dimensions":[]}',
                user=json.dumps({'model': model_name, 'fields': catalog}),
            )
            if text.startswith('```'):
                text = text.strip('`')
                if text.startswith('json'):
                    text = text[4:]
            return json.loads(text.strip())
        except Exception as e:
            return {'error': str(e), 'fields': catalog}

    def _get_item_data_dict(self, **kwargs):
        self.ensure_one()
        
        # Merge user preferences dynamically for this request
        import json
        cached_prefs = self.env['dynamic.dashboard.user.preference'].get_preferences_dict(self.dashboard_id.id)
        
        class PreferenceProxy:
            def __init__(self, record, overrides):
                self._record = record
                self._overrides = overrides
            def __getattr__(self, name):
                if name in self._overrides:
                    return self._overrides[name]
                return getattr(self._record, name)
                
        dash_pref = cached_prefs.get('dash', {})
        item_pref = cached_prefs.get('items', {}).get(self.id, {})
                
        eff_dash = PreferenceProxy(self.dashboard_id, dash_pref) if dash_pref else self.dashboard_id
        
        eff_item_overrides = dict(item_pref)
        eff_item_overrides['dashboard_id'] = eff_dash
        item = PreferenceProxy(self, eff_item_overrides)

        # Hierarchical KPI binding
        if item.kpi_id and item.item_type in ('kpi', 'tile', 'scorecard'):
            payload = item.kpi_id.get_dashboard_payload(
                date_filter=kwargs.get('global_date_filter', 'none')
            )
            result = self._base_item_result(item)
            result.update(payload)
            result['item_type'] = item.item_type
            result['type'] = item.item_type
            result['enable_target'] = True
            result['target_value'] = payload.get('target_value') or 0
            # Item Display-tab options always win over linked KPI defaults
            self._apply_item_display_options(result, item)
            result['enable_target'] = True
            result['target_value'] = payload.get('target_value') or item.standard_target_value or 0
            return result

        # Reusable Analysis binding
        if item.analysis_id:
            visual = item.item_type if item.item_type not in ('todo',) else item.analysis_id.visual_type
            data = item.analysis_id.fetch_analysis_data(visual_type=visual, **kwargs)
            result = self._base_item_result(item)
            result.update(data)
            result['name'] = item.name or data.get('name')
            result['item_type'] = item.item_type
            result['type'] = item.item_type
            # Item Display-tab options always win over Analysis payload
            self._apply_item_display_options(result, item)
            try:
                vc = json.loads(item.visual_config or '{}')
                if vc:
                    merged = dict(result.get('visual_config') or {})
                    merged.update(vc)
                    result['visual_config'] = merged
            except Exception:
                pass
            if item.item_type == 'iframe':
                result['iframe_url'] = item.iframe_url or item.analysis_id.iframe_url
            if item.item_type == 'odoo_view':
                action = item.odoo_action_id or item.analysis_id.odoo_action_id
                result['odoo_action_id'] = action.id if action else False
            result['list_show_grand_total'] = item.list_show_grand_total
            result['list_column_min_width'] = item.list_column_min_width
            return result

        if item.item_type == 'iframe':
            result = self._base_item_result(item)
            result.update({'iframe_url': item.iframe_url or '', 'item_type': 'iframe', 'type': 'iframe'})
            return result
        if item.item_type == 'odoo_view':
            result = self._base_item_result(item)
            result.update({
                'odoo_action_id': item.odoo_action_id.id if item.odoo_action_id else False,
                'item_type': 'odoo_view',
                'type': 'odoo_view',
            })
            return result

        # Map the UI data type to a valid ORM aggregate method ('average' -> 'avg')
        agg = 'avg' if item.data_type == 'average' else item.data_type

        base_domain = safe_eval(item.domain or '[]')
        domain = list(base_domain)
        prev_domain = list(base_domain)
        model = self._dd_scoped_model(item.sudo().model_id.model if item.sudo().model_id else False)

        # Domain extension (AND)
        try:
            ext = safe_eval(item.domain_extension or '[]')
            if isinstance(ext, list) and ext:
                domain.extend(ext)
                prev_domain.extend(ext)
        except Exception:
            pass
        
        # Apply Date Filter
        date_filter = kwargs.get('global_date_filter', 'none')
        if date_filter == 'none':
            date_filter = item.date_filter_selection

        # Header Compare toggle OR item-level "Compare with Previous Period"
        do_compare = bool(kwargs.get('global_compare') or item.compare_previous_period)
        compare_active = False

        range_start = range_end = False
        if item.date_filter_field_id and date_filter != 'none':
            today = fields.Date.context_today(self)
            start_date, end_date, prev_start, prev_end = self._resolve_date_range(
                date_filter, today=today, item=item
            )
            range_start, range_end = start_date, end_date

            if start_date and end_date:
                field_name = item.date_filter_field_id.name
                # Adjust bounds if field is datetime
                if item.date_filter_field_id.ttype == 'datetime':
                    if isinstance(start_date, datetime.date) and not isinstance(start_date, datetime.datetime):
                        start_date = datetime.datetime.combine(start_date, datetime.time.min)
                    if isinstance(end_date, datetime.date) and not isinstance(end_date, datetime.datetime):
                        end_date = datetime.datetime.combine(end_date, datetime.time.max)
                    if isinstance(prev_start, datetime.date) and not isinstance(prev_start, datetime.datetime):
                        prev_start = datetime.datetime.combine(prev_start, datetime.time.min)
                    if isinstance(prev_end, datetime.date) and not isinstance(prev_end, datetime.datetime):
                        prev_end = datetime.datetime.combine(prev_end, datetime.time.max)

                domain += [(field_name, '>=', start_date), (field_name, '<=', end_date)]

            if do_compare and prev_start and prev_end:
                prev_domain.extend([
                    (item.date_filter_field_id.name, '>=', prev_start),
                    (item.date_filter_field_id.name, '<=', prev_end),
                ])
                compare_active = True

        # Apply Custom Filters
        custom_filters = kwargs.get('custom_filter_domains', [])
        for cf in custom_filters:
            try:
                cf_dom = safe_eval(cf)
                domain.extend(cf_dom)
                prev_domain.extend(cf_dom)
            except Exception:
                pass

        # Apply drill-down domain leaves from the client
        drill_domain = kwargs.get('drill_domain') or []
        if isinstance(drill_domain, list):
            for leaf in drill_domain:
                if isinstance(leaf, (list, tuple)) and len(leaf) == 3:
                    domain.append(tuple(leaf))
                    prev_domain.append(tuple(leaf))

        # Optional date granularity override while drilling date fields
        # (consumed later via kwargs.get('drill_date_type'))

        # Replace %UID and %MYCOMPANY logic (Section 4.7)
        user_id = self.env.user.id
        company_id = self.env.company.id
        
        def replace_env_vars(d_list):
            final_d = []
            for dom in d_list:
                if isinstance(dom, (tuple, list)) and len(dom) == 3:
                    val = dom[2]
                    if isinstance(val, str):
                        if '%UID' in val:
                            val = val.replace('%UID', str(user_id))
                            try: val = int(val)
                            except: pass
                        elif '%MYCOMPANY' in val:
                            val = val.replace('%MYCOMPANY', str(company_id))
                            try: val = int(val)
                            except: pass
                    final_d.append((dom[0], dom[1], val))
                else:
                    final_d.append(dom)
            return final_d

        domain = replace_env_vars(domain)
        prev_domain = replace_env_vars(prev_domain)
        model = self._dd_scoped_model(item.sudo().model_id.model if item.sudo().model_id else False)

        result = self._base_item_result(item)
        result['domain'] = domain
        result['is_scatter_group'] = item.is_scatter_group

        # Date type used for this request (supports drill-down override)
        effective_date_type = kwargs.get('drill_date_type') or item.group_by_date_type
        DATE_DRILL_NEXT = {
            'year': 'quarter', 'quarter': 'month', 'month': 'week', 'week': 'day', 'day': False,
            'hour': 'minute', 'minute': False,
        }
        
        # Resolve Target Value
        target_val = item.standard_target_value
        if item.enable_target and item.target_line_ids:
            today = fields.Date.today()
            valid_line = item.target_line_ids.filtered(lambda l: l.date_start <= today <= l.date_end)
            if valid_line:
                target_val = valid_line[0].target_value
        result['target_value'] = target_val
        
        if item.data_calculation_type == 'api':
            result = self._get_item_data_from_api(result, item=item)
            self._apply_item_display_options(result, item)
            return result

        if item.data_calculation_type == 'sql':
            result = self._get_item_data_from_sql(result, kwargs, item=item)
            self._apply_item_display_options(result, item)
            return result

        if item.data_calculation_type in ('excel', 'csv'):
            result = self._get_item_data_from_file(result, item=item)
            self._apply_item_display_options(result, item)
            return result

        if item.data_calculation_type in ('scrape', 'sheets'):
            sheets_id = item.sheets_id
            sheets_range = item.sheets_range or 'A:Z'
            scrape_url = item.scrape_url
            scrape_path = item.scrape_json_path
            sheets_api_key = False
            conn = item.external_connection_id
            if conn and conn.connection_type == 'sheets':
                sheets_id = sheets_id or conn.sheets_spreadsheet_id
                sheets_api_key = (conn.sheets_api_key or '').strip() or False
            analysis_like = self.env['dynamic.dashboard.analysis'].with_context(
                dd_sheets_api_key=sheets_api_key,
                dd_sheets_allow_demo=True,
                dd_scrape_allow_demo=True,
                dd_scrape_label_key=item.api_label_key or False,
                dd_scrape_value_key=item.api_value_key or False,
            ).new({
                'name': item.name,
                'source_type': item.data_calculation_type,
                'scrape_url': scrape_url,
                'scrape_json_path': scrape_path,
                'sheets_id': sheets_id,
                'sheets_range': sheets_range,
                'visual_type': item.item_type,
            })
            data = analysis_like.fetch_analysis_data(visual_type=item.item_type, **kwargs)
            result.update(data)
            self._apply_item_display_options(result, item)
            return result

        if item.item_type != 'todo' and model is None:
            result['error'] = 'Target model is not defined.'
            return result

        if item.item_type in ('tile', 'kpi', 'scorecard'):
            value = 0
            prev_value = 0
            
            # Combine measure fields
            all_measures = item.measure_field_ids | item.measure_field_2_ids
            measure_names = all_measures.mapped('name')
            m1 = m2 = 0.0
            count_val = 0
            
            if measure_names:
                query_fields = [f"{m}:{agg}" for m in measure_names]
                res = model.formatted_read_group(domain, groupby=[], aggregates=query_fields + ['__count'])
                first_measure = item.measure_field_ids[0].name if item.measure_field_ids else measure_names[0]
                value = res[0].get(f"{first_measure}:{agg}", 0) if res else 0
                m1 = value or 0
                if len(item.measure_field_ids) > 1:
                    m2 = res[0].get(f"{item.measure_field_ids[1].name}:{agg}", 0) if res else 0
                elif item.measure_field_2_ids:
                    m2 = res[0].get(f"{item.measure_field_2_ids[0].name}:{agg}", 0) if res else 0
                count_val = res[0].get('__count', 0) if res else 0
                
                if compare_active:
                    prev_res = model.formatted_read_group(prev_domain, groupby=[], aggregates=query_fields)
                    prev_value = prev_res[0].get(f"{first_measure}:{agg}", 0) if prev_res else 0
            else:
                value = model.search_count(domain)
                count_val = value
                m1 = value
                if compare_active:
                    prev_value = model.search_count(prev_domain)

            # KPI second model
            value_2 = 0
            if item.item_type == 'kpi' and item.kpi_model_id:
                value_2 = item._compute_kpi_secondary_value(kwargs)
                m2 = value_2
                comparison = item.kpi_comparison or 'none'

                def _apply_kpi_cmp(v1, v2):
                    if comparison == 'percentage':
                        return (float(v1) / float(v2) * 100) if v2 else 0
                    if comparison == 'ratio':
                        return (float(v1) / float(v2)) if v2 else 0
                    if comparison == 'sum':
                        return float(v1) + float(v2)
                    if comparison == 'difference':
                        return float(v1) - float(v2)
                    return float(v1)

                if compare_active:
                    prev_v2 = item._compute_kpi_secondary_value(kwargs, use_previous_period=True)
                    prev_value = _apply_kpi_cmp(prev_value, prev_v2)
                value = _apply_kpi_cmp(m1, value_2)

            if item.multiplier_active:
                value = value * item.multiplier_value
                prev_value = prev_value * item.multiplier_value
                value_2 = value_2 * item.multiplier_value if value_2 else value_2

            if item.formula_active:
                try:
                    value = item._eval_measure_formula(m1=m1, m2=m2, count=count_val)
                except UserError as e:
                    result['error'] = str(e)
                    return result

            result.update({
                'value': value,
                'value_2': value_2,
                'value_1': m1,
                'kpi_comparison': item.kpi_comparison if item.kpi_model_id else False,
                'color': item.tile_color,
                'icon': item.tile_icon,
                'compare_previous_period': bool(compare_active),
                'previous_value': prev_value if compare_active else 0,
            })
            if item.item_type == 'scorecard':
                scorecard_values = [{'label': item.name or _('Total'), 'value': value}]
                if item.group_by_field_id and item.group_by_field_id.store:
                    groupby = item.group_by_field_id.name
                    if item.group_by_field_id.ttype in ('date', 'datetime'):
                        groupby = f"{groupby}:{item.group_by_date_type or 'month'}"
                    measure = item.measure_field_ids[:1]
                    aggregates = (
                        [f"{measure.name}:{agg}", '__count'] if measure else ['__count']
                    )
                    try:
                        groups = model.formatted_read_group(
                            domain, groupby=[groupby], aggregates=aggregates,
                        )
                        cells = []
                        for row in groups:
                            raw = row.get(groupby)
                            if isinstance(raw, tuple):
                                label = str(raw[1] or _('Undefined'))
                            else:
                                label = str(raw or _('Undefined'))
                            if measure:
                                cell_val = row.get(f"{measure.name}:{agg}", 0) or 0
                            else:
                                cell_val = row.get('__count', 0) or 0
                            if item.multiplier_active:
                                cell_val = cell_val * item.multiplier_value
                            cells.append({'label': label, 'value': cell_val})
                        if cells:
                            scorecard_values = cells
                    except Exception:
                        # Fall back to single total cell if grouping fails
                        pass
                result['scorecard_values'] = scorecard_values
        elif item.item_type == 'scatter' and item.scatter_measure_x_id and item.scatter_measure_y_id:
            result.update(self._get_scatter_xy_data(
                item, model, domain, agg,
                date_type=kwargs.get('drill_date_type') or item.group_by_date_type,
            ))
        elif item.item_type in (
            'bar', 'barLine', 'horizontalBar', 'line', 'area', 'stepLine', 'smoothedLine',
            'waterfall', 'pie', 'doughnut', 'polarArea', 'radar', 'flower', 'scatter',
            'radialBar', 'gauge', 'funnel', 'pyramid', 'pictorial', 'bullet',
            'treemap', 'sunburst', 'forceDirected', 'pack', 'tree', 'partition', 'voronoiTreemap',
            'sankey', 'chord', 'chordDirected', 'chordNonRibbon', 'arcDiagram',
            'map', 'mapPoints', 'heatmap', 'matrixHeatmap',
            'wordCloud', 'venn', 'candlestick', 'ohlc', 'timeline', 'serpentine', 'spiral',
        ):
            if item.item_type == 'wordCloud' and item.word_cloud_field_id and not item.group_by_field_id:
                words = self._build_word_cloud_data(item, model, domain)
                result.update({
                    'labels': [w['category'] for w in words],
                    'datasets': [{'label': 'Count', 'data': [w['value'] for w in words]}],
                    'word_cloud_data': words,
                })
                self._apply_item_display_options(result, item)
                return result
            if item.item_type in self.FLOW_TYPES and item.flow_source_field_id and item.flow_target_field_id and not item.group_by_field_id:
                flow = self._build_flow_data(item, model, domain)
                result.update({'labels': [], 'datasets': [], 'flow_data': flow})
                self._apply_item_display_options(result, item)
                return result
            if not item.group_by_field_id:
                result['error'] = 'Group By field is required for charts.'
                return result
            # Non-stored fields (e.g. res.partner.company_type) cannot be used in read_group
            if not item.group_by_field_id.store:
                result['error'] = (
                    f"Group By field '{item.group_by_field_id.field_description}' "
                    f"({item.group_by_field_id.name}) is not stored and cannot be used for charts. "
                    f"Choose a stored field instead (e.g. Is a Company)."
                )
                return result
            if item.sub_group_by_field_id and not item.sub_group_by_field_id.store:
                result['error'] = (
                    f"Sub Group By field '{item.sub_group_by_field_id.field_description}' "
                    f"is not stored and cannot be used for charts."
                )
                return result
            
            all_measures = item.measure_field_ids | item.measure_field_2_ids
            measure_names = all_measures.mapped('name')
            
            query_fields = [f"{m}:{agg}" for m in measure_names] if measure_names else []
            
            # After a drill into the main group, chart by sub-group (if any).
            # Otherwise optionally stack main + sub in one chart.
            use_sub_as_main = bool(drill_domain and item.sub_group_by_field_id)
            if use_sub_as_main:
                groupby_main = item.sub_group_by_field_id.name
                if item.sub_group_by_field_id.ttype in ('date', 'datetime'):
                    groupby_main = f"{groupby_main}:{item.sub_group_by_date_type}"
                groupby_list = [groupby_main]
                groupby_sub = ""
                active_group_field = item.sub_group_by_field_id
            else:
                groupby_main = item.group_by_field_id.name
                if item.group_by_field_id.ttype in ('date', 'datetime'):
                    groupby_main = f"{groupby_main}:{effective_date_type}"
                groupby_list = [groupby_main]
                groupby_sub = ""
                active_group_field = item.group_by_field_id
                if item.sub_group_by_field_id:
                    groupby_sub = item.sub_group_by_field_id.name
                    if item.sub_group_by_field_id.ttype in ('date', 'datetime'):
                        groupby_sub = f"{groupby_sub}:{item.sub_group_by_date_type}"
                    groupby_list.append(groupby_sub)
                
            orderby = ""
            if item.sort_by_field_id:
                sort_f = item.sort_by_field_id.name
                if sort_f == 'id':
                    sort_term = '__count'
                elif sort_f == item.group_by_field_id.name:
                    sort_term = groupby_main
                elif item.sub_group_by_field_id and sort_f == item.sub_group_by_field_id.name:
                    sort_term = groupby_sub
                else:
                    sort_term = f"{sort_f}:{agg}"
                    if sort_term not in query_fields:
                        query_fields.append(sort_term)
                orderby = f"{sort_term} {'ASC' if item.sort_order == 'asc' else 'DESC'}"
            
            if '__count' not in query_fields:
                query_fields.append('__count')

            # Enforce a hard maximum to prevent browser crashes and DB timeouts
            applied_limit = item.record_limit or 10000
            
            read_group_res = model.formatted_read_group(
                domain,
                groupby=groupby_list,
                aggregates=query_fields,
                limit=applied_limit,
                order=orderby or None
            )
            
            labels_set = []
            datasets_array = []
            label_domain_map = {}
            
            if len(groupby_list) > 1:
                # Sub-group logic (Multi-dataset by subgroup)
                # Currently we only chart the first measure if sub-grouping
                measure = measure_names[0] if measure_names else '__count'
                datasets_dict = {}
                
                for res in read_group_res:
                    main_val = res.get(groupby_main)
                    sub_val = res.get(groupby_list[1])
                    domain_val = main_val
                    if isinstance(main_val, tuple):
                        domain_val = main_val[0]
                        main_val = main_val[1]
                    if isinstance(sub_val, tuple): sub_val = sub_val[1]
                    
                    l_main = str(main_val or 'Undefined')
                    l_sub = str(sub_val or 'Undefined')
                    
                    if l_main not in labels_set:
                        labels_set.append(l_main)
                        label_domain_map[l_main] = False if main_val in (None, False) or l_main == 'Undefined' else domain_val
                        
                    if l_sub not in datasets_dict:
                        datasets_dict[l_sub] = {}
                        
                    val = res.get(f"{measure}:{agg}") if measure != '__count' else res.get('__count')
                    if item.multiplier_active and val is not None:
                        val = val * item.multiplier_value
                    datasets_dict[l_sub][l_main] = val
                    
                for sub_label, data_map in datasets_dict.items():
                    data_arr = [data_map.get(l, 0) for l in labels_set]
                    datasets_array.append({
                        'label': sub_label,
                        'data': data_arr,
                        'yAxisID': 'y'
                    })
            else:
                # Single grouping logic
                is_map_country = False
                country_map = {}
                if item.item_type in ('map', 'mapPoints') and item.group_by_field_id.relation == 'res.country':
                    is_map_country = True
                    country_ids = [res.get(groupby_main)[0] for res in read_group_res if isinstance(res.get(groupby_main), tuple)]
                    if country_ids:
                        for c in self.env['res.country'].browse(country_ids):
                            country_map[c.id] = c.code or c.name

                for res in read_group_res:
                    raw_val = res.get(groupby_main)
                    domain_val = raw_val
                    if isinstance(raw_val, tuple):
                        domain_val = raw_val[0]
                        if is_map_country:
                            group_val = country_map.get(raw_val[0], raw_val[1])
                        else:
                            group_val = raw_val[1]
                    else:
                        group_val = raw_val
                    label = str(group_val or 'Undefined')
                    labels_set.append(label)
                    label_domain_map[label] = False if group_val in (None, False) or label == 'Undefined' else domain_val
                
                if not measure_names:
                    # Count fallback
                    data = [res.get('__count', 0) * (item.multiplier_value if item.multiplier_active else 1) for res in read_group_res]
                    datasets_array.append({
                        'label': 'Count',
                        'data': data,
                        'yAxisID': 'y'
                    })
                else:
                    # Multi-measure logic
                    for measure in item.measure_field_ids:
                        data = [(res.get(f"{measure.name}:{agg}", 0) * (item.multiplier_value if item.multiplier_active else 1)) for res in read_group_res]
                        datasets_array.append({
                            'label': measure.field_description,
                            'data': data,
                            'yAxisID': 'y'
                        })
                    for measure in item.measure_field_2_ids:
                        data = [(res.get(f"{measure.name}:{agg}", 0) * (item.multiplier_value if item.multiplier_active else 1)) for res in read_group_res]
                        datasets_array.append({
                            'label': measure.field_description,
                            'data': data,
                            'yAxisID': 'y1' # Secondary axis
                        })
                    
            if item.is_cumulative:
                for ds in datasets_array:
                    cum_data = []
                    running_total = 0
                    for val in ds['data']:
                        running_total += (val or 0)
                        cum_data.append(running_total)
                    ds['data'] = cum_data

            custom_colors = {}
            for sc in item.segment_color_ids:
                if sc.segment_name and sc.color:
                    custom_colors[sc.segment_name] = sc.color

            next_date_type = False
            if active_group_field.ttype in ('date', 'datetime'):
                next_date_type = DATE_DRILL_NEXT.get(effective_date_type, False)
            # Further drill available via sub-group (only before switching to it)
            can_drill_sub = bool(item.sub_group_by_field_id) and not use_sub_as_main

            if (
                item.fill_temporal
                and active_group_field.ttype in ('date', 'datetime')
                and len(groupby_list) == 1
            ):
                fill_start, fill_end = range_start, range_end
                # When no date filter range, derive bounds from returned buckets
                if not fill_start or not fill_end:
                    dates = []
                    for lab in labels_set:
                        dval = label_domain_map.get(lab)
                        parsed = False
                        if isinstance(dval, (datetime.date, datetime.datetime)):
                            parsed = dval.date() if isinstance(dval, datetime.datetime) else dval
                        elif isinstance(dval, str) and len(dval) >= 10:
                            try:
                                parsed = fields.Date.to_date(dval[:10])
                            except Exception:
                                parsed = False
                        if parsed:
                            dates.append(parsed)
                    if dates:
                        fill_start = fill_start or min(dates)
                        fill_end = fill_end or max(dates)
                if fill_start and fill_end:
                    labels_set, datasets_array, label_domain_map = self._fill_temporal_series(
                        labels_set, datasets_array, label_domain_map,
                        effective_date_type, fill_start, fill_end,
                    )

            result.update({
                'labels': labels_set,
                'datasets': datasets_array,
                'custom_segment_colors': custom_colors,
                'measure_2_active': len(item.measure_field_2_ids) > 0,
                'label_domain_map': label_domain_map,
                'group_by_ttype': active_group_field.ttype,
                'group_by_date_type': effective_date_type if active_group_field.ttype in ('date', 'datetime') else False,
                'next_drill_date_type': next_date_type,
                'has_sub_group': can_drill_sub,
                'group_by_field': active_group_field.name,
            })

            # Previous-period comparison (header Compare or item flag)
            if compare_active and len(groupby_list) == 1:
                try:
                    prev_rg = model.formatted_read_group(
                        prev_domain,
                        groupby=groupby_list,
                        aggregates=query_fields,
                        limit=item.record_limit or None,
                        order=orderby or None,
                    )
                    prev_map = {}
                    prev_total = 0.0
                    measure_key = (
                        f"{measure_names[0]}:{agg}" if measure_names else '__count'
                    )
                    for res in prev_rg:
                        raw_val = res.get(groupby_main)
                        if isinstance(raw_val, tuple):
                            group_val = raw_val[1]
                        else:
                            group_val = raw_val
                        label = str(group_val or 'Undefined')
                        val = res.get(measure_key, 0) or 0
                        if item.multiplier_active:
                            val = val * item.multiplier_value
                        prev_map[label] = val
                        prev_total += float(val or 0)

                    # Align previous values to current labels (category match)
                    if datasets_array:
                        primary = datasets_array[0]
                        prev_data = [prev_map.get(lbl, 0) for lbl in labels_set]
                        datasets_array.append({
                            'label': f"{primary.get('label') or 'Value'} (Prev)",
                            'data': prev_data,
                            'yAxisID': primary.get('yAxisID') or 'y',
                            'is_previous_period': True,
                        })
                        result['datasets'] = datasets_array
                    result['compare_previous_period'] = True
                    result['previous_value'] = prev_total
                except Exception:
                    result['compare_previous_period'] = True
                    result['previous_value'] = 0
            elif compare_active:
                result['compare_previous_period'] = True
                try:
                    if measure_names:
                        prev_tot = model.formatted_read_group(
                            prev_domain, groupby=[], aggregates=[f"{measure_names[0]}:{agg}"]
                        )
                        result['previous_value'] = (
                            prev_tot[0].get(f"{measure_names[0]}:{agg}", 0) if prev_tot else 0
                        )
                    else:
                        result['previous_value'] = model.search_count(prev_domain)
                    if item.multiplier_active and result.get('previous_value'):
                        result['previous_value'] = result['previous_value'] * item.multiplier_value
                except Exception:
                    result['previous_value'] = 0

            # Optional formula across first two measure series (per category)
            if item.formula_active and item.formula and len(datasets_array) >= 1:
                try:
                    m1_data = datasets_array[0]['data']
                    m2_data = datasets_array[1]['data'] if len(datasets_array) > 1 else [0] * len(m1_data)
                    counts = [1] * len(m1_data)
                    formula_data = []
                    for i in range(len(m1_data)):
                        formula_data.append(item._eval_measure_formula(
                            m1=m1_data[i], m2=m2_data[i] if i < len(m2_data) else 0, count=counts[i]
                        ))
                    result['datasets'] = [{'label': item.formula, 'data': formula_data, 'yAxisID': 'y'}]
                    datasets_array = result['datasets']
                except UserError as e:
                    result['error'] = str(e)
                    return result

            # Merge additional multi-model data sources as extra series
            if item.source_ids and item.item_type in (
                'bar', 'horizontalBar', 'line', 'area', 'stepLine', 'smoothedLine',
                'waterfall', 'pie', 'doughnut', 'polarArea', 'radar', 'flower',
                'radialBar', 'funnel', 'pyramid', 'pictorial', 'bullet', 'gauge',
            ):
                labels_set, datasets_array = self._merge_additional_sources(
                    item,
                    result.get('labels') or [],
                    result.get('datasets') or [],
                    date_range=(range_start, range_end),
                    drill_date_type=effective_date_type,
                )
                result['labels'] = labels_set
                result['datasets'] = datasets_array
                result['multi_source'] = True
            self._enrich_chart_payload(result, item, model=model, domain=domain)
        elif item.item_type == 'list':
            if item.list_view_type == 'grouped':
                if not item.group_by_field_id:
                    result['error'] = 'Group By field is required for grouped list views.'
                    return result
                all_measures = item.measure_field_ids | item.measure_field_2_ids
                measure_names = all_measures.mapped('name')
                query_fields = [f"{m}:{agg}" for m in measure_names] if measure_names else []
                if '__count' not in query_fields:
                    query_fields.append('__count')

                groupby_main = item.group_by_field_id.name
                if item.group_by_field_id.ttype in ('date', 'datetime'):
                    groupby_main = f"{groupby_main}:{item.group_by_date_type}"

                orderby = ""
                if item.sort_by_field_id:
                    sort_f = item.sort_by_field_id.name
                    if sort_f == 'id':
                        sort_term = '__count'
                    elif sort_f == item.group_by_field_id.name:
                        sort_term = groupby_main
                    else:
                        sort_term = f"{sort_f}:{agg}"
                        if sort_term not in query_fields:
                            query_fields.append(sort_term)
                    orderby = f"{sort_term} {'ASC' if item.sort_order == 'asc' else 'DESC'}"

                read_group_res = model.formatted_read_group(
                    domain,
                    groupby=[groupby_main],
                    aggregates=query_fields,
                    limit=item.record_limit or None,
                    order=orderby or None,
                )

                columns = [item.group_by_field_id.field_description]
                measure_cols = []
                if measure_names:
                    for m in item.measure_field_ids:
                        columns.append(m.field_description)
                        measure_cols.append((m.name, m.field_description))
                    for m in item.measure_field_2_ids:
                        columns.append(m.field_description)
                        measure_cols.append((m.name, m.field_description))
                else:
                    columns.append('Count')
                    measure_cols.append(('__count', 'Count'))

                records = []
                for res in read_group_res:
                    group_val = res.get(groupby_main)
                    if isinstance(group_val, tuple):
                        group_val = group_val[1]
                    row = {item.group_by_field_id.field_description: group_val or 'Undefined'}
                    for mname, mlabel in measure_cols:
                        if mname == '__count':
                            val = res.get('__count', 0)
                        else:
                            val = res.get(f"{mname}:{agg}", 0)
                        if item.multiplier_active and val is not None:
                            val = val * item.multiplier_value
                        row[mlabel] = val
                    records.append(row)

                result.update({
                    'records': records,
                    'columns': columns,
                    'column_keys': columns,
                    'list_view_layout': item.list_view_layout,
                    'list_view_type': 'grouped',
                })
            else:
                orderby = f"{item.sort_by_field_id.name} {'ASC' if item.sort_order == 'asc' else 'DESC'}" if item.sort_by_field_id else ""
                fields_to_read = item.list_view_field_ids.mapped('name') if item.list_view_field_ids else ['display_name']
                # export_all kwarg forces full dump; field only opts into that behavior for export actions
                export_all = bool(kwargs.get('export_all'))
                total_count = model.search_count(domain)
                offset = int(kwargs.get('list_offset') or 0)
                page_size = item.pagination_limit or 0
                if export_all:
                    limit = None
                    offset = 0
                elif page_size:
                    limit = page_size
                else:
                    limit = item.record_limit or 80
                    offset = 0
                records = model.search_read(
                    domain,
                    fields_to_read,
                    limit=limit,
                    offset=offset,
                    order=orderby
                )
                result['records'] = records
                result['columns'] = item.list_view_field_ids.mapped('field_description') if item.list_view_field_ids else ['Name']
                result['column_keys'] = fields_to_read
                result['list_view_layout'] = item.list_view_layout
                result['list_view_type'] = 'ungrouped'
                result['list_total'] = total_count
                result['list_offset'] = offset
                result['pagination_limit'] = page_size
                result['export_all_records'] = item.export_all_records
                if item.list_show_grand_total:
                    totals = {}
                    for key in fields_to_read:
                        s = 0.0
                        numeric = False
                        for r in records:
                            v = r.get(key)
                            if isinstance(v, (int, float)):
                                s += v
                                numeric = True
                        if numeric:
                            totals[key] = s
                    result['grand_total'] = totals
                result['list_show_grand_total'] = item.list_show_grand_total
                result['list_column_min_width'] = item.list_column_min_width or 80
        elif item.item_type == 'todo':
            todos = item.todo_ids.search_read([('dashboard_item_id', '=', item.id)], ['id', 'name', 'is_done'])
            result['todos'] = todos
            
        # Action details
        result['action_type'] = item.action_type
        if item.action_type == 'window' and item.action_id:
            result['action_id'] = item.action_id.id
            result['action_name'] = item.action_id.name
        elif item.action_type == 'client' and item.client_action_id:
            result['client_action_tag'] = item.client_action_id.tag
            result['client_action_name'] = item.client_action_id.name
        elif item.action_type == 'url' and item.action_url:
            result['action_url'] = item.action_url

        if item.group_by_field_id and 'group_by_field' not in result:
            result['group_by_field'] = item.group_by_field_id.name

        # Final pass: Display-tab settings must not be overwritten by branch logic
        self._apply_item_display_options(result, item)
        # Keep resolved target if a branch already computed it
        if 'target_value' not in result and item.enable_target:
            result['target_value'] = item.standard_target_value

        return result

    def generate_ai_insight(self, chart_data):
        self.ensure_one()
        try:
            return self._ai_chat(
                system=(
                    "You are a professional business analyst. Analyze the following chart data "
                    "and provide a concise, insightful 2-3 sentence summary of the key trends or outliers."
                ),
                user=f"Chart Name: {chart_data.get('name')}\nData: {json.dumps(chart_data, default=str)[:6000]}",
            )
        except Exception as e:
            return f"Error analyzing data: {str(e)}"

    def action_internal_chat(self):
        self.ensure_one()
        channel_name = f"Dashboard: {self.dashboard_id.name} - {self.name}"
        
        channel = self.env['discuss.channel'].search([('name', '=', channel_name)], limit=1)
        if not channel:
            channel = self.env['discuss.channel'].create({
                'name': channel_name,
                'channel_type': 'channel',
            })
        
        # Ensure user is in channel
        if self.env.user.partner_id not in channel.channel_member_ids.partner_id:
            channel.add_members(self.env.user.partner_id.ids)
            
        return {
            'type': 'ir.actions.client',
            'tag': 'mail.action_discuss',
            'context': {
                'active_id': channel.id,
            },
        }

    def _bus_notify_refresh(self):
        """Notify connected clients to refresh this item/dashboard."""
        for item in self:
            payload = {
                'item_id': item.id,
                'dashboard_id': item.dashboard_id.id,
            }
            try:
                self.env['bus.bus']._sendone(
                    'dynamic_dashboard_ai_nexgen',
                    'dynamic_dashboard_ai_nexgen_refresh',
                    payload,
                )
            except Exception:
                pass

    def write(self, vals):
        vals = dict(vals or {})
        auto = not self.env.context.get('dd_skip_auto_layout')
        # When Item Type / data config changes, auto-resize so My Dashboard stays readable
        data_keys = {
            'item_type', 'group_by_field_id', 'list_view_field_ids', 'scorecard_columns',
            'flow_source_field_id', 'flow_target_field_id',
        }
        resize = auto and bool(data_keys & set(vals.keys())) and not (
            'grid_w' in vals or 'grid_h' in vals
        )
        dashboards_to_repack = self.env['dynamic.dashboard']
        if resize and len(self) == 1:
            self._apply_auto_grid_size(vals, record=self)
            if self.dashboard_id:
                dashboards_to_repack |= self.dashboard_id
        elif resize and len(self) > 1:
            # Per-record sizes may differ — write size in a second pass, then repack
            resize_map = {}
            for rec in self:
                v = dict(vals)
                self._apply_auto_grid_size(v, record=rec)
                resize_map[rec.id] = (v['grid_w'], v['grid_h'])
            res = super().write(vals)
            for rec in self:
                gw, gh = resize_map[rec.id]
                if rec.grid_w != gw or rec.grid_h != gh:
                    super(DynamicDashboardItem, rec).write({'grid_w': gw, 'grid_h': gh})
            for dash in self.mapped('dashboard_id'):
                if dash:
                    self._repack_dashboard_items(dash)
            layout_only = {'grid_x', 'grid_y', 'grid_w', 'grid_h', 'sequence'}
            if vals and not set(vals.keys()) <= layout_only:
                self._bus_notify_refresh()
            if 'query' in vals or 'use_materialized_view' in vals:
                self._sync_materialized_views_after_write(vals)
            return res

        res = super().write(vals)
        if dashboards_to_repack:
            for dash in dashboards_to_repack:
                self._repack_dashboard_items(dash)
        # Layout-only moves should not force every open viewer to refetch data
        layout_only = {'grid_x', 'grid_y', 'grid_w', 'grid_h', 'sequence'}
        if vals and not set(vals.keys()) <= layout_only:
            self._bus_notify_refresh()
        if 'query' in vals or 'use_materialized_view' in vals:
            self._sync_materialized_views_after_write(vals)
        return res

    def _sync_materialized_views_after_write(self, vals):
        if 'query' not in vals and 'use_materialized_view' not in vals:
            return
        for item in self:
            if item.use_materialized_view:
                try:
                    item.action_create_mview()
                except Exception:
                    pass
            else:
                try:
                    item.action_drop_mview()
                except Exception:
                    pass

    @api.model_create_multi
    def create(self, vals_list):
        """New items get a type/data-based size and land in the first free slot (no blank holes)."""
        auto = not self.env.context.get('dd_skip_auto_layout')
        prepared = []
        batch_rects = {}
        for vals in vals_list:
            vals = dict(vals)
            dashboard_id = vals.get('dashboard_id')
            if auto:
                self._apply_auto_grid_size(vals)
                if dashboard_id:
                    if dashboard_id not in batch_rects:
                        batch_rects[dashboard_id] = self._occupied_rects_for_dashboard(dashboard_id)
                        existing = self.search([('dashboard_id', '=', dashboard_id)])
                        if 'sequence' not in vals:
                            vals['sequence'] = (max(existing.mapped('sequence') or [0]) + 10) if existing else 10
                    w = int(vals.get('grid_w') or 6)
                    h = int(vals.get('grid_h') or 4)
                    x, y, w, h = self._find_free_grid_slot(
                        w, h, occupied=batch_rects[dashboard_id], cols=12, fill_row=True,
                    )
                    vals.update({'grid_x': x, 'grid_y': y, 'grid_w': w, 'grid_h': h})
                    batch_rects[dashboard_id].append((x, y, w, h))
            prepared.append(vals)

        records = super().create(prepared)
        records._bus_notify_refresh()
        return records

    
    # ---------------------------------------------------------
    # Materialized View Management
    # ---------------------------------------------------------

    def action_create_mview(self):
        for item in self:
            if not item.use_materialized_view or not item.query:
                continue
            view_name = f"mview_dyn_dashboard_{item.id}"
            
            # Drop if exists
            self.env.cr.execute(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}")
            
            # Prepare without kwargs to test if it relies on dynamic kwargs
            try:
                prepared, row_limit, params = item._prepare_sql_query(item.query, {})

                # We can't pass params to CREATE MATERIALIZED VIEW via standard driver execute binding.
                # However, since the parameters returned by _prepare_sql_query are only uid, company_id,
                # start_date, and end_date (which are safe primitives), we can substitute them manually here,
                # or use mogrify if applicable. Since mviews are Postgres only, we can use mogrify.
                # But to avoid dependency on mogrify availability across all driver versions easily,
                # we format the string safely since params only contains controlled primitives.
                for k, v in params.items():
                    val_str = str(v).replace("'", "''")
                    prepared = prepared.replace(f"%({k})s", f"'{val_str}'")
                # Also restore the pyformat %% back to % since we're no longer using execute with params
                prepared = prepared.replace("%%", "%")

                # Execute create statement
                self.env.cr.execute(f"CREATE MATERIALIZED VIEW {view_name} AS {prepared}")
                item.write({'mview_status': 'active'})
            except Exception as e:
                item.write({'mview_status': 'error'})
                raise

    def action_drop_mview(self):
        for item in self:
            view_name = f"mview_dyn_dashboard_{item.id}"
            self.env.cr.execute(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}")
            item.write({'mview_status': 'none', 'use_materialized_view': False})

    def _refresh_materialized_view(self):
        for item in self:
            if item.mview_status == 'active':
                view_name = f"mview_dyn_dashboard_{item.id}"
                try:
                    self.env.cr.execute(f"REFRESH MATERIALIZED VIEW {view_name}")
                except Exception as e:
                    # Might not exist
                    item.action_create_mview()

    @api.model
    def cron_refresh_all_materialized_views(self):
        items = self.search([('use_materialized_view', '=', True)])
        for item in items:
            item._refresh_materialized_view()

