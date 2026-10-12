# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
"""Idempotent demo seeder — only models from module depends (+ this module).

depends: base, web, mail, bus
"""
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


DEMO_PARTNER_PREFIX = 'DD-DEMO-P'


class DynamicDashboardDemoRecord(models.Model):
    """Self-contained metric rows used by the Chart Types Showcase."""
    _name = 'dynamic.dashboard.demo.record'
    _description = 'Dynamic Dashboard Demo Metric'
    _order = 'metric_date desc, id desc'
    _check_company_auto = True

    _quantity_positive = models.Constraint(
        'CHECK(quantity IS NULL OR quantity >= 0)',
        'Quantity cannot be negative.',
    )

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )
    metric_date = fields.Date(required=True, index=True)
    amount = fields.Float(string='Amount', digits=(16, 2))
    quantity = fields.Float(string='Quantity', digits=(16, 2), default=1.0)
    category = fields.Selection([
        ('electronics', 'Electronics'),
        ('furniture', 'Furniture'),
        ('services', 'Services'),
        ('software', 'Software'),
        ('retail', 'Retail'),
        ('industrial', 'Industrial'),
    ], required=True, default='services', index=True)
    stage = fields.Selection([
        ('new', 'New'),
        ('qualified', 'Qualified'),
        ('proposition', 'Proposition'),
        ('won', 'Won'),
        ('lost', 'Lost'),
    ], required=True, default='new', index=True)
    region = fields.Selection([
        ('na', 'North America'),
        ('eu', 'Europe'),
        ('apac', 'APAC'),
        ('latam', 'LATAM'),
        ('mea', 'MEA'),
    ], required=True, default='na', index=True)
    country_id = fields.Many2one('res.country', string='Country', index=True)
    user_id = fields.Many2one('res.users', string='Responsible', index=True)
    partner_id = fields.Many2one('res.partner', string='Partner')
    company_type = fields.Selection([
        ('company', 'Company'),
        ('person', 'Individual'),
    ], default='company')


class DynamicDashboard(models.Model):
    _inherit = 'dynamic.dashboard'

    @api.model
    def seed_chart_demo_data(self, force=False):
        """Create demo data using only depends models + this module's models.

        Allowed sources: res.partner, res.users, res.country, mail.message,
        and dynamic.dashboard.* models.
        """
        partners = self._dd_seed_partners(force=force)
        self._dd_seed_demo_metrics(partners, force=force)
        self._dd_seed_mail_messages(partners, force=force)
        # Drop legacy CRM-based demo dashboards from older versions
        self.env['dynamic.dashboard'].sudo().search([
            ('name', 'in', [
                'Demo - Tiles & KPI',
                'Demo - Charts Gallery',
                'Demo - Lists, Map & To-Do',
                'Sample Sales Dashboard',
            ]),
        ]).unlink()
        self._dd_ensure_all_charts_dashboard()
        self._dd_ensure_partner_gallery_dashboard()
        self.seed_business_app_dashboards(force=force)
        self.seed_data_calculation_type_demos(force=force)
        return True

    # ------------------------------------------------------------------
    # Base / mail seeders
    # ------------------------------------------------------------------
    @api.model
    def _dd_seed_partners(self, force=False):
        Partner = self.env['res.partner'].sudo()
        existing = Partner.search([('ref', 'like', f'{DEMO_PARTNER_PREFIX}-%')])
        if existing and not force:
            return existing
        if force and existing:
            # Best-effort cleanup of leftover demo docs from older seeders
            self._dd_cleanup_legacy_extra_module_demo(existing)
            try:
                existing.unlink()
                existing = Partner.browse()
            except Exception:
                # Keep existing partners if other modules still reference them
                return existing

        country_codes = ['US', 'CA', 'GB', 'DE', 'FR', 'IN', 'AE', 'BR', 'AU', 'JP', 'SG', 'MX']
        countries = {
            c.code: c
            for c in self.env['res.country'].search([('code', 'in', country_codes)])
        }
        all_countries = list(countries.values()) or self.env['res.country'].search([], limit=12)
        users = self.env['res.users'].search([('share', '=', False), ('id', 'not in', [1, 2])], limit=6) or self.env.user

        names = [
            'Acme Robotics', 'Northwind Traders', 'Contoso Retail', 'Fabrikam Labs',
            'Adventure Works', 'Blue Ocean Shipping', 'Sunrise Foods', 'Vertex Soft',
            'Pioneer Furniture', 'Atlas Industrial', 'Nova Healthcare', 'Orbit Media',
            'Cedar Bank', 'Delta Logistics', 'Eclipse Energy', 'Falcon Aviation',
            'Granite Mining', 'Harbor Hotels', 'Ivory Textiles', 'Jade Electronics',
            'Knight Security', 'Lumen Optics', 'Maple Agro', 'Nimbus Cloud',
            'Orchid Pharma', 'Prairie Construction', 'Quartz Materials', 'River Telecom',
            'Summit Sports', 'Titan Automotive', 'Umbra Design', 'Vista Education',
            'Willow Fashion', 'Xenon Chemicals', 'Yellow Cab Fleet', 'Zenith Consulting',
            'Aurora Biotech', 'Beacon Finance', 'Cascade Tools', 'Drift Mobility',
        ]
        partners = Partner.browse()
        today = fields.Date.context_today(self)
        for i, name in enumerate(names):
            country = all_countries[i % len(all_countries)]
            user = users[i % len(users)]
            create_day = today - relativedelta(months=(i % 14), days=(i % 20))
            partner_vals = {
                'name': name,
                'ref': f'{DEMO_PARTNER_PREFIX}-{i + 1:03d}',
                'company_type': 'company' if i % 4 else 'person',
                'country_id': country.id,
                'user_id': user.id,
                'email': f'dd.demo.{i + 1}@example.com',
                'phone': f'+1-555-{1000 + i:04d}',
                'city': f'Demo City {(i % 8) + 1}',
                'is_company': bool(i % 4),
                'comment': f'Dynamic Dashboard demo partner #{i + 1}',
            }
            # credit_limit exists only when accounting apps extend res.partner
            if 'credit_limit' in Partner._fields:
                partner_vals['credit_limit'] = 5000 + (i * 1750) % 90000
            partner = Partner.create(partner_vals)
            self.env.cr.execute(
                "UPDATE res_partner SET create_date = %s WHERE id = %s",
                [datetime.combine(create_day, datetime.min.time()), partner.id],
            )
            partners |= partner
        return partners

    @api.model
    def _dd_cleanup_legacy_extra_module_demo(self, partners):
        """Remove CRM/Sale demo rows created by older seeders (cleanup only)."""
        if 'sale.order' in self.env:
            orders = self.env['sale.order'].sudo().search([
                '|',
                ('client_order_ref', 'like', 'DD-DEMO-SO-%'),
                ('partner_id', 'in', partners.ids),
            ])
            if orders:
                try:
                    orders.filtered(lambda o: o.state not in ('cancel', 'draft'))._action_cancel()
                except Exception:
                    pass
                try:
                    orders.unlink()
                except Exception:
                    pass
        if 'crm.lead' in self.env:
            leads = self.env['crm.lead'].sudo().search([
                '|',
                ('name', 'like', 'DD-DEMO-L %'),
                ('partner_id', 'in', partners.ids),
            ])
            try:
                leads.unlink()
            except Exception:
                pass

    @api.model
    def _dd_seed_demo_metrics(self, partners, force=False):
        Metric = self.env['dynamic.dashboard.demo.record'].sudo()
        existing = Metric.search([])
        if existing and not force:
            return existing
        if force and existing:
            existing.unlink()

        categories = ['electronics', 'furniture', 'services', 'software', 'retail', 'industrial']
        stages = ['new', 'qualified', 'proposition', 'won', 'lost']
        regions = ['na', 'eu', 'apac', 'latam', 'mea']
        users = self.env['res.users'].search([('share', '=', False), ('id', 'not in', [1, 2])], limit=6) or self.env.user
        partner_list = partners or self.env['res.partner'].search([], limit=40)
        today = fields.Date.context_today(self)

        vals_list = []
        for i in range(120):
            p = partner_list[i % len(partner_list)]
            metric_day = today - relativedelta(months=(i % 18), days=(i % 27))
            vals_list.append({
                'name': f'DD Metric {i + 1:03d} — {p.name}',
                'metric_date': metric_day,
                'amount': 1200 + ((i * 137) % 45000) + (i % 7) * 85,
                'quantity': 1 + (i % 15),
                'category': categories[i % len(categories)],
                'stage': stages[i % len(stages)],
                'region': regions[i % len(regions)],
                'country_id': p.country_id.id if p.country_id else False,
                'user_id': users[i % len(users)].id,
                'partner_id': p.id,
                'company_type': 'company' if i % 3 else 'person',
            })
        return Metric.create(vals_list)

    @api.model
    def _dd_seed_mail_messages(self, partners, force=False):
        """Seed chatter notes on demo partners (mail is a declared dependency)."""
        Message = self.env['mail.message'].sudo()
        subtype = self.env.ref('mail.mt_note', raise_if_not_found=False)
        partner_list = list(partners[:20]) if partners else []
        if not partner_list:
            return Message.browse()

        existing = Message.search([
            ('model', '=', 'res.partner'),
            ('res_id', 'in', [p.id for p in partner_list]),
            ('body', 'ilike', 'DD Demo note'),
        ])
        if existing and not force:
            return existing
        if force and existing:
            existing.unlink()

        users = self.env['res.users'].search([('share', '=', False), ('id', 'not in', [1, 2])], limit=4) or self.env.user
        vals_list = []
        for i, partner in enumerate(partner_list):
            author = users[i % len(users)].partner_id
            vals_list.append({
                'model': 'res.partner',
                'res_id': partner.id,
                'body': f'<p>DD Demo note #{i + 1} for {partner.name}</p>',
                'message_type': 'comment',
                'subtype_id': subtype.id if subtype else False,
                'author_id': author.id,
            })
        return Message.create(vals_list)

    # ------------------------------------------------------------------
    # Showcase dashboards
    # ------------------------------------------------------------------
    @api.model
    def _dd_model(self, model_name):
        return self.env['ir.model']._get(model_name)

    @api.model
    def _dd_field(self, model_name, field_name):
        return self.env['ir.model.fields'].search([
            ('model', '=', model_name),
            ('name', '=', field_name),
        ], limit=1)

    @api.model
    def _dd_ensure_all_charts_dashboard(self):
        """Build/refresh a dashboard that covers every visual type (demo.record)."""
        Dash = self.env['dynamic.dashboard'].sudo()
        Item = self.env['dynamic.dashboard.item'].sudo().with_context(dd_skip_auto_layout=True)
        metric_model = self._dd_model('dynamic.dashboard.demo.record')
        if not metric_model:
            return Dash.browse()

        dash = Dash.search([('name', '=', 'Demo - All Chart Types')], limit=1)
        if not dash:
            dash = Dash.create({
                'name': 'Demo - All Chart Types',
                'category_id': self.env['dynamic.dashboard.category'].sudo().get_or_create('Demo').id,
                'gridstack_config': '{}',
            })
        else:
            dash.item_ids.unlink()
            if not dash.category_id:
                dash.category_id = self.env['dynamic.dashboard.category'].sudo().get_or_create('Demo')

        def F(name):
            return self._dd_field('dynamic.dashboard.demo.record', name)

        amount = F('amount')
        quantity = F('quantity')
        category = F('category')
        stage = F('stage')
        region = F('region')
        country = F('country_id')
        user_f = F('user_id')
        metric_date = F('metric_date')
        company_type = F('company_type')
        name_f = F('name')

        specs = [
            dict(name='Tile: Total Amount', item_type='tile', grid_x=0, grid_y=0, grid_w=3, grid_h=2,
                 data_type='sum', measure_field_ids=[(6, 0, [amount.id])] if amount else False,
                 tile_layout='layout1', tile_icon='fa-money', tile_color='#2B9EFF', unit='$', unit_position='prefix',
                 compare_previous_period=True,
                 date_filter_field_id=metric_date.id if metric_date else False, date_filter_selection='this_year'),
            dict(name='Tile: Record Count', item_type='tile', grid_x=3, grid_y=0, grid_w=3, grid_h=2,
                 data_type='count', tile_layout='layout2', tile_icon='fa-database', tile_color='#6366F1',
                 compare_previous_period=True),
            dict(name='KPI: Avg Amount', item_type='kpi', grid_x=6, grid_y=0, grid_w=3, grid_h=2,
                 data_type='average', measure_field_ids=[(6, 0, [amount.id])] if amount else False,
                 unit='$', unit_position='prefix', enable_target=True, standard_target_value=20000,
                 target_view='number', tile_layout='layout1', tile_icon='fa-line-chart', tile_color='#2B9EFF',
                 date_filter_field_id=metric_date.id if metric_date else False,
                 date_filter_selection='this_year', compare_previous_period=True),
            dict(name='KPI: Record Count', item_type='kpi', grid_x=9, grid_y=0, grid_w=3, grid_h=2,
                 data_type='count', enable_target=True, standard_target_value=100,
                 target_view='number', tile_layout='layout3', tile_icon='fa-database', tile_color='#F59E0B',
                 compare_previous_period=True),
            dict(name='KPI: Total Qty', item_type='kpi', grid_x=0, grid_y=22, grid_w=4, grid_h=3,
                 data_type='sum', measure_field_ids=[(6, 0, [quantity.id])] if quantity else False,
                 unit='u', unit_position='suffix', enable_target=True, standard_target_value=500,
                 target_view='progress_bar', tile_layout='layout2', tile_icon='fa-cubes', tile_color='#10B981',
                 date_filter_field_id=metric_date.id if metric_date else False,
                 date_filter_selection='this_year', compare_previous_period=True),
            dict(name='Scorecard: Qty Sum', item_type='scorecard', grid_x=4, grid_y=22, grid_w=8, grid_h=3,
                 data_type='sum', measure_field_ids=[(6, 0, [quantity.id])] if quantity else False,
                 unit='u', unit_position='suffix', tile_layout='layout1', tile_color='#2B9EFF'),
            dict(name='Bar: Amount by Category', item_type='bar', grid_x=0, grid_y=2, grid_w=6, grid_h=4,
                 data_type='sum', measure_field_ids=[(6, 0, [amount.id])] if amount else False,
                 group_by_field_id=category.id if category else False, chart_theme='corporate', show_data_value=True),
            dict(name='Bar+Line: Amount & Qty by Region', item_type='barLine', grid_x=6, grid_y=2, grid_w=6, grid_h=4,
                 data_type='sum',
                 measure_field_ids=[(6, 0, [amount.id])] if amount else False,
                 measure_field_2_ids=[(6, 0, [quantity.id])] if quantity else False,
                 group_by_field_id=region.id if region else False, chart_theme='ocean'),
            dict(name='Horizontal Bar: Amount by User', item_type='horizontalBar', grid_x=0, grid_y=6, grid_w=6, grid_h=4,
                 data_type='sum', measure_field_ids=[(6, 0, [amount.id])] if amount else False,
                 group_by_field_id=user_f.id if user_f else False, chart_theme='vibrant', show_data_value=True),
            dict(name='Line: Amount Trend (Month)', item_type='line', grid_x=6, grid_y=6, grid_w=6, grid_h=4,
                 data_type='sum', measure_field_ids=[(6, 0, [amount.id])] if amount else False,
                 group_by_field_id=metric_date.id if metric_date else False, group_by_date_type='month',
                 chart_theme='cool', fill_temporal=True),
            dict(name='Area: Qty Trend (Month)', item_type='area', grid_x=0, grid_y=10, grid_w=6, grid_h=4,
                 data_type='sum', measure_field_ids=[(6, 0, [quantity.id])] if quantity else False,
                 group_by_field_id=metric_date.id if metric_date else False, group_by_date_type='month',
                 is_cumulative=True, chart_theme='sunset'),
            dict(name='Pie: Amount by Category', item_type='pie', grid_x=6, grid_y=10, grid_w=6, grid_h=4,
                 data_type='sum', measure_field_ids=[(6, 0, [amount.id])] if amount else False,
                 group_by_field_id=category.id if category else False, chart_theme='warm'),
            dict(name='Doughnut: Count by Stage', item_type='doughnut', grid_x=0, grid_y=14, grid_w=6, grid_h=4,
                 data_type='count', group_by_field_id=stage.id if stage else False, chart_theme='pastel'),
            dict(name='Semi Doughnut: by Company Type', item_type='doughnut', grid_x=6, grid_y=14, grid_w=6, grid_h=4,
                 data_type='count', group_by_field_id=company_type.id if company_type else False,
                 is_semi_circle=True, chart_theme='pastel'),
            dict(name='Polar: Amount by Region', item_type='polarArea', grid_x=0, grid_y=18, grid_w=6, grid_h=4,
                 data_type='sum', measure_field_ids=[(6, 0, [amount.id])] if amount else False,
                 group_by_field_id=region.id if region else False, chart_theme='vibrant'),
            dict(name='Radar: Count by Stage', item_type='radar', grid_x=6, grid_y=18, grid_w=6, grid_h=4,
                 data_type='count', group_by_field_id=stage.id if stage else False, chart_theme='neon'),
            dict(name='Flower: Amount by Category', item_type='flower', grid_x=0, grid_y=25, grid_w=6, grid_h=4,
                 data_type='sum', measure_field_ids=[(6, 0, [amount.id])] if amount else False,
                 group_by_field_id=category.id if category else False, chart_theme='sunset', show_data_value=True),
            dict(name='Scatter: Amount by User', item_type='scatter', grid_x=6, grid_y=25, grid_w=6, grid_h=4,
                 data_type='sum', measure_field_ids=[(6, 0, [amount.id])] if amount else False,
                 group_by_field_id=user_f.id if user_f else False, chart_theme='ocean'),
            dict(name='Radial Bar: Count by Region', item_type='radialBar', grid_x=0, grid_y=29, grid_w=6, grid_h=4,
                 data_type='count', group_by_field_id=region.id if region else False,
                 chart_theme='corporate', show_data_value=True),
            dict(name='Funnel: Count by Stage', item_type='funnel', grid_x=6, grid_y=29, grid_w=6, grid_h=4,
                 data_type='count', group_by_field_id=stage.id if stage else False,
                 chart_theme='cool', show_data_value=True),
            dict(name='Bullet: Amount vs Target by Category', item_type='bullet', grid_x=0, grid_y=33, grid_w=6, grid_h=4,
                 data_type='sum', measure_field_ids=[(6, 0, [amount.id])] if amount else False,
                 group_by_field_id=category.id if category else False, enable_target=True,
                 standard_target_value=200000, chart_theme='warm', show_data_value=True),
            dict(name='Map: Amount by Country', item_type='map', grid_x=6, grid_y=33, grid_w=6, grid_h=4,
                 data_type='sum', measure_field_ids=[(6, 0, [amount.id])] if amount else False,
                 group_by_field_id=country.id if country else False),
            dict(name='Heat Map: Count by Country', item_type='heatmap', grid_x=0, grid_y=37, grid_w=6, grid_h=4,
                 data_type='count', group_by_field_id=country.id if country else False),
            dict(name='List: Recent Metrics', item_type='list', grid_x=6, grid_y=37, grid_w=6, grid_h=4,
                 list_view_type='ungrouped', list_view_layout='layout1', record_limit=12,
                 list_view_field_ids=[(6, 0, [f.id for f in (name_f, category, stage, amount, metric_date) if f])],
                 sort_by_field_id=metric_date.id if metric_date else False, sort_order='desc',
                 list_show_grand_total=True),
            dict(name='Grouped List: Amount by Category', item_type='list', grid_x=0, grid_y=41, grid_w=6, grid_h=4,
                 list_view_type='grouped', data_type='sum',
                 measure_field_ids=[(6, 0, [amount.id])] if amount else False,
                 group_by_field_id=category.id if category else False),
            dict(name='Iframe: Odoo Website', item_type='iframe', grid_x=6, grid_y=41, grid_w=6, grid_h=4,
                 iframe_url='https://www.odoo.com'),
            dict(name='To-Do: Demo Checklist', item_type='todo', grid_x=0, grid_y=45, grid_w=6, grid_h=4),
        ]

        partner_action = self.env.ref('base.action_partner_form', raise_if_not_found=False)
        if partner_action:
            specs.append(dict(
                name='Odoo View: Partners', item_type='odoo_view',
                grid_x=6, grid_y=45, grid_w=6, grid_h=4,
                odoo_action_id=partner_action.id,
            ))

        created_items = Item.browse()
        for seq, spec in enumerate(specs, start=1):
            vals = {
                'dashboard_id': dash.id,
                'model_id': metric_model.id if spec['item_type'] not in ('todo', 'iframe', 'odoo_view') else False,
                'data_calculation_type': 'custom',
                'sequence': seq,
                'domain': "[('id', '!=', False)]",
            }
            vals.update({k: v for k, v in spec.items() if v is not False and v is not None})
            for m2m in ('measure_field_ids', 'measure_field_2_ids', 'list_view_field_ids'):
                if vals.get(m2m) is False:
                    vals.pop(m2m, None)
            created_items |= Item.create(vals)

        todo = created_items.filtered(lambda i: i.item_type == 'todo')[:1]
        if todo:
            Todo = self.env['dynamic.dashboard.todo'].sudo()
            Todo.search([('dashboard_item_id', '=', todo.id)]).unlink()
            Todo.create([
                {'name': 'Review All Chart Types dashboard', 'dashboard_item_id': todo.id, 'is_done': False},
                {'name': 'Resize pie/map widgets in edit mode', 'dashboard_item_id': todo.id, 'is_done': False},
                {'name': 'Toggle Compare with This Month filter', 'dashboard_item_id': todo.id, 'is_done': True},
                {'name': 'Export PNG / PDF snapshot', 'dashboard_item_id': todo.id, 'is_done': False},
            ])
        return dash

    @api.model
    def _dd_ensure_partner_gallery_dashboard(self):
        """Extra gallery using only res.partner (base)."""
        Dash = self.env['dynamic.dashboard'].sudo()
        Item = self.env['dynamic.dashboard.item'].sudo().with_context(dd_skip_auto_layout=True)
        partner_model = self._dd_model('res.partner')
        if not partner_model:
            return Dash.browse()

        dash = Dash.search([('name', '=', 'Demo - Partners (Base)')], limit=1)
        if not dash:
            dash = Dash.create({
                'name': 'Demo - Partners (Base)',
                'category_id': self.env['dynamic.dashboard.category'].sudo().get_or_create('Demo').id,
                'gridstack_config': '{}',
            })
        else:
            dash.item_ids.unlink()
            if not dash.category_id:
                dash.category_id = self.env['dynamic.dashboard.category'].sudo().get_or_create('Demo')

        def F(name):
            return self._dd_field('res.partner', name)

        credit = F('credit_limit')
        country = F('country_id')
        user_f = F('user_id')
        create_date = F('create_date')
        is_company = F('is_company')
        name_f = F('name')
        email_f = F('email')
        city_f = F('city')
        demo_domain = f"[('ref', 'like', '{DEMO_PARTNER_PREFIX}-%')]"

        specs = [
            dict(name='Partners Count', item_type='tile', grid_x=0, grid_y=0, grid_w=3, grid_h=2,
                 data_type='count', tile_layout='layout1', tile_icon='fa-users', tile_color='#e3f2fd'),
        ]
        if credit:
            specs.append(dict(
                name='Credit Limit Sum', item_type='tile', grid_x=3, grid_y=0, grid_w=3, grid_h=2,
                data_type='sum', measure_field_ids=[(6, 0, [credit.id])],
                tile_layout='layout2', tile_icon='fa-credit-card', tile_color='#e8f5e9',
                unit='$', unit_position='prefix',
            ))
        else:
            specs.append(dict(
                name='Companies Count', item_type='tile', grid_x=3, grid_y=0, grid_w=3, grid_h=2,
                data_type='count', tile_layout='layout2', tile_icon='fa-building',
                tile_color='#e8f5e9',
                domain=f"[('ref', 'like', '{DEMO_PARTNER_PREFIX}-%'), ('is_company', '=', True)]",
            ))
        specs.append(dict(
            name='Partners by Country', item_type='pie', grid_x=6, grid_y=0, grid_w=6, grid_h=4,
            data_type='count', group_by_field_id=country.id if country else False, chart_theme='warm',
        ))
        if credit and country:
            specs.append(dict(
                name='Credit by Country', item_type='bar', grid_x=0, grid_y=4, grid_w=6, grid_h=4,
                data_type='sum', measure_field_ids=[(6, 0, [credit.id])],
                group_by_field_id=country.id, chart_theme='corporate', show_data_value=True,
            ))
        elif city_f:
            specs.append(dict(
                name='Partners by City', item_type='bar', grid_x=0, grid_y=4, grid_w=6, grid_h=4,
                data_type='count', group_by_field_id=city_f.id,
                chart_theme='corporate', show_data_value=True,
            ))
        specs.extend([
            dict(name='Partners by User', item_type='horizontalBar', grid_x=6, grid_y=4, grid_w=6, grid_h=4,
                 data_type='count', group_by_field_id=user_f.id if user_f else False, chart_theme='vibrant'),
            dict(name='Partners Created (Month)', item_type='line', grid_x=0, grid_y=8, grid_w=6, grid_h=4,
                 data_type='count', group_by_field_id=create_date.id if create_date else False,
                 group_by_date_type='month', chart_theme='cool'),
            dict(name='Company vs Individual', item_type='doughnut', grid_x=6, grid_y=8, grid_w=6, grid_h=4,
                 data_type='count', group_by_field_id=is_company.id if is_company else False, chart_theme='pastel'),
            dict(name='Map: Partners by Country', item_type='map', grid_x=0, grid_y=12, grid_w=6, grid_h=4,
                 data_type='count', group_by_field_id=country.id if country else False),
            dict(name='Partner List', item_type='list', grid_x=0, grid_y=16, grid_w=12, grid_h=4,
                 list_view_type='ungrouped', list_view_layout='layout1', record_limit=15,
                 list_view_field_ids=[(6, 0, [f.id for f in (name_f, email_f, city_f, country, credit) if f])],
                 sort_by_field_id=(credit or name_f).id if (credit or name_f) else False,
                 sort_order='desc' if credit else 'asc'),
        ])

        for seq, spec in enumerate(specs, start=1):
            vals = {
                'dashboard_id': dash.id,
                'model_id': partner_model.id,
                'data_calculation_type': 'custom',
                'sequence': seq,
                'domain': demo_domain,
            }
            vals.update({k: v for k, v in spec.items() if v is not False and v is not None})
            for m2m in ('measure_field_ids', 'measure_field_2_ids', 'list_view_field_ids'):
                if vals.get(m2m) is False:
                    vals.pop(m2m, None)
            Item.create(vals)
        return dash
