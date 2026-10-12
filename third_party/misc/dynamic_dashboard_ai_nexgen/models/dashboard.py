# Copyright (C) NexGen Solutions
import json
from markupsafe import Markup, escape
from odoo import models, fields, api, _

class DynamicDashboard(models.Model):
    _name = 'dynamic.dashboard'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Dynamic Dashboard'
    _order = 'sequence, id'
    _check_company_auto = True

    _tv_interval_positive = models.Constraint(
        'CHECK(tv_interval IS NULL OR tv_interval > 0)',
        'TV Interval must be greater than zero.',
    )

    name = fields.Char(string='Dashboard Name', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    item_ids = fields.One2many('dynamic.dashboard.item', 'dashboard_id', string='Dashboard Items')
    custom_filter_ids = fields.One2many('dynamic.dashboard.filter', 'dashboard_id', string='Custom Filters')
    report_ids = fields.One2many('dynamic.dashboard.report', 'dashboard_id', string='Scheduled Reports')

    item_count = fields.Integer(string='Items', compute='_compute_item_count')

    active = fields.Boolean(default=True)
    
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
    ], string="Chart Theme", default=False, help="If set, this theme will be applied to all charts on the dashboard, overriding their individual settings.")


    @api.depends('item_ids')
    def _compute_item_count(self):
        for dashboard in self:
            dashboard.item_count = self.env['dynamic.dashboard.item'].search_count([('dashboard_id', '=', dashboard.id)])

    def read(self, fields=None, load='_classic_read'):
        """Override read to merge user-specific preferences for dashboard settings."""
        records = super().read(fields, load)
        if self.env.context.get('ignore_user_preferences') or not records:
            return records
            
        import json
        prefs = self.env['dynamic.dashboard.user.preference'].search([
            ('user_id', '=', self.env.user.id),
            ('dashboard_id', 'in', [r['id'] for r in records if 'id' in r]),
            ('item_id', '=', False)
        ])
        if prefs:
            pref_map = {p.dashboard_id.id: json.loads(p.preference_data or '{}') for p in prefs}
            for rec in records:
                rec_id = rec.get('id')
                if rec_id and rec_id in pref_map:
                    for k, v in pref_map[rec_id].items():
                        if not fields or k in fields:
                            rec[k] = v
        return records

    @api.model
    def update_user_preference(self, record_id, values):
        """Allows users to save their dashboard-level overrides (e.g. theme) without modifying the base dashboard."""
        import json
        pref = self.env['dynamic.dashboard.user.preference'].search([
            ('user_id', '=', self.env.user.id),
            ('dashboard_id', '=', record_id),
            ('item_id', '=', False)
        ], limit=1)
        
        if pref:
            data = json.loads(pref.preference_data or '{}')
            data.update(values)
            pref.preference_data = json.dumps(data)
        else:
            self.env['dynamic.dashboard.user.preference'].create({
                'dashboard_id': record_id,
                'preference_data': json.dumps(values)
            })
        return True

    def action_repack_layout(self):
        """Auto-size every item by type/data and pack tightly (no blank gaps)."""
        Item = self.env['dynamic.dashboard.item']
        for dash in self:
            Item._repack_dashboard_items(dash)
        return True

    @api.model
    def action_repack_all_demo_layouts(self):
        """Called from demo.xml — pack every dashboard so demo boards have no blank gaps."""
        dashboards = self.sudo().search([])
        Item = self.env['dynamic.dashboard.item']
        for dash in dashboards:
            if dash.item_ids:
                Item._repack_dashboard_items(dash)
        return True

    def action_view_items(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Dashboard Items'),
            'res_model': 'dynamic.dashboard.item',
            'view_mode': 'list,form',
            'domain': [('dashboard_id', '=', self.id)],
            'context': {'default_dashboard_id': self.id},
        }

    def action_open_dashboard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'dynamic_dashboard_ai_nexgen.dashboard_view',
            'name': self.name,
            'context': {'default_dashboard_id': self.id},
        }
    
    # Phase 3: Bookmarking and Security
    bookmarked_user_ids = fields.Many2many('res.users', 'dynamic_dashboard_ai_nexgen_bookmark_rel', string="Bookmarked By")

    def _default_group_ids(self):
        user_group = self.env.ref('base.group_user', raise_if_not_found=False)
        return [(6, 0, [user_group.id])] if user_group else []

    group_ids = fields.Many2many('res.groups', 'dynamic_dashboard_ai_nexgen_group_rel', string="Allowed Groups", default=_default_group_ids)
    
    def toggle_bookmark(self):
        self.ensure_one()
        if self.env.user in self.bookmarked_user_ids:
            self.bookmarked_user_ids -= self.env.user
            return False
        else:
            self.bookmarked_user_ids += self.env.user
            return True

    def copy(self, default=None):
        if default is None:
            default = {}
        default = dict(default)
        default.setdefault('name', _('%s (Copy)') % (self.name or _('Dashboard')))
        # Never share the original app menu with a duplicate
        default.setdefault('menu_id', False)
        new_dashboard = super().copy(default)
        for item in self.item_ids:
            item.copy({'dashboard_id': new_dashboard.id})
        for filt in self.custom_filter_ids:
            filt.copy({'dashboard_id': new_dashboard.id, 'item_ids': False})
        for report in self.report_ids:
            report.copy({'dashboard_id': new_dashboard.id})
        return new_dashboard

    def action_duplicate_dashboard(self):
        self.ensure_one()
        new_dash = self.copy()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dynamic.dashboard',
            'res_id': new_dash.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }
        
    def action_send_dashboard_email(self, base64_image):
        """Open mail composer with a dashboard snapshot image attached.

        The OWL viewer captures the grid as JPEG (html2canvas); older callers
        may still pass PDF bytes — detect from the payload / magic if needed.
        """
        self.ensure_one()
        if not base64_image:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Email'),
                    'message': _('No dashboard snapshot was generated.'),
                    'type': 'warning',
                },
            }

        # Frontend currently sends image/jpeg from html2canvas
        mimetype = 'image/jpeg'
        ext = 'jpg'
        safe_name = (self.name or 'Dashboard').replace('/', '-').replace('\\', '-')
        attachment = self.env['ir.attachment'].create({
            'name': f'{safe_name}_Dashboard.{ext}',
            'type': 'binary',
            'datas': base64_image,
            'res_model': 'dynamic.dashboard',
            'res_id': self.id,
            'mimetype': mimetype,
        })

        partners = self.email_user_ids.mapped('partner_id').filtered('email')
        body = Markup(
            '<p>Hello,</p>'
            '<p>Please find attached the latest snapshot of the <b>%s</b> dashboard.</p>'
            '<p>Best regards,</p>'
        ) % escape(self.name or '')

        ctx = {
            'default_model': 'dynamic.dashboard',
            'default_res_ids': self.ids,
            'default_composition_mode': 'comment',
            'default_attachment_ids': [(6, 0, [attachment.id])],
            'default_partner_ids': [(6, 0, partners.ids)] if partners else [],
            'default_subject': _('Dashboard Snapshot: %s') % self.name,
            'default_body': body,
        }

        self.message_post(
            body=_('Dashboard snapshot prepared for email.'),
            attachment_ids=[attachment.id],
            subtype_xmlid='mail.mt_note',
            message_type='notification',
        )

        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )
    gridstack_config = fields.Text(string='GridStack Config', default='{}')
    is_rtl = fields.Boolean(
        string='Force RTL',
        default=False,
        help='When enabled, always render this dashboard right-to-left. '
             'Otherwise Layout Direction / user language is used.',
    )
    layout_direction = fields.Selection([
        ('auto', 'Auto (User Language)'),
        ('ltr', 'Left to Right'),
        ('rtl', 'Right to Left'),
    ], string='Layout Direction', default='auto',
        help='Auto follows the signed-in user language (e.g. Arabic → RTL). '
             'All grid layouts respect this direction.',
    )
    background_color = fields.Char(
        string='Background Color',
        default='#f4f5f7',
        help='Viewer background color for this dashboard.',
    )

    @api.constrains('background_color')
    def _check_background_color(self):
        from .constraints_utils import assert_hex_color
        for dash in self:
            assert_hex_color(dash.background_color, _('Background Color'))
    default_date_filter = fields.Selection([
        ('none', 'None (All Time)'),
        ('today', 'Today'),
        ('yesterday', 'Yesterday'),
        ('tomorrow', 'Tomorrow'),
        ('this_week', 'This Week'),
        ('this_month', 'This Month'),
        ('this_quarter', 'This Quarter'),
        ('this_year', 'This Year'),
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
        ('next_week', 'Next Week'),
        ('next_month', 'Next Month'),
        ('next_quarter', 'Next Quarter'),
        ('next_year', 'Next Year'),
    ], string='Default Global Date Filter', default='none')

    # TV Mode
    tv_interval = fields.Integer(
        string='TV Interval (seconds)',
        default=15,
        help='Seconds between dashboard/item rotations in TV Mode.',
    )
    tv_mode_type = fields.Selection([
        ('dashboard', 'Rotate Dashboards'),
        ('item', 'Slideshow Items'),
    ], string='TV Mode Type', default='dashboard')
    tv_hide_chrome = fields.Boolean(
        string='Hide Chrome in TV Mode',
        default=True,
        help='Hide toolbar and bookmarks when TV Mode is active.',
    )

    # Email defaults
    email_user_ids = fields.Many2many(
        'res.users',
        'dynamic_dashboard_ai_nexgen_email_user_rel',
        'dashboard_id',
        'user_id',
        string='Default Email Recipients',
        help='Pre-filled recipients when sending a dashboard snapshot by email.',
    )
    category_id = fields.Many2one(
        'dynamic.dashboard.category',
        string='Category',
        ondelete='set null',
        index=True,
        help='Dashboard category for grouping in menus.',
    )
    category = fields.Char(
        string='Category Label',
        translate=True,
        help='Synced label from Category (kept for filters and the dashboard viewer).',
    )
    sticky_navbar = fields.Boolean(string='Sticky Navbar', default=True)
    present_notes = fields.Text(string='Present Mode Notes', translate=True, help='Optional presenter notes for slides mode.')
    share_ids = fields.One2many('dynamic.dashboard.share', 'dashboard_id', string='Share Links')

    @api.onchange('category_id')
    def _onchange_category_id(self):
        self.category = self.category_id.name if self.category_id else False

    @api.model
    def _prepare_category_vals(self, vals):
        """Keep category_id / category Char in sync (Many2one is the source of truth in the UI)."""
        vals = dict(vals)
        Category = self.env['dynamic.dashboard.category']
        if vals.get('category_id'):
            cat = Category.browse(vals['category_id'])
            vals['category'] = cat.name if cat else False
        elif vals.get('category') and 'category_id' not in vals:
            vals['category_id'] = Category.get_or_create(vals['category']).id
        elif 'category' in vals and not vals.get('category'):
            vals['category_id'] = False
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        prepared = [self._prepare_category_vals(vals) for vals in vals_list]
        return super().create(prepared)

    def write(self, vals):
        return super().write(self._prepare_category_vals(vals))

    def action_create_share_link(self):
        self.ensure_one()
        share = self.env['dynamic.dashboard.share'].create({
            'name': _('%s Share') % self.name,
            'dashboard_id': self.id,
            'expiry_hours': 72,
        })
        return share.action_open_link()

    def action_open_present_mode(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'dynamic_dashboard_ai_nexgen.dashboard_view',
            'name': self.name,
            'context': {
                'default_dashboard_id': self.id,
                'present_mode': True,
            },
        }
    
    # Dynamic Menu
    menu_name = fields.Char(string='Menu Name', translate=True)
    top_menu_id = fields.Many2one('ir.ui.menu', string='Parent Menu', domain="[('parent_id', '=', False)]")
    menu_id = fields.Many2one('ir.ui.menu', string='Created Menu', readonly=True, copy=False)
    
    @api.model
    def save_grid_layout(self, dashboard_id, config):
        dashboard = self.browse(dashboard_id)
        if dashboard.exists():
            dashboard.gridstack_config = json.dumps(config)
            return True
        return False
        
    def action_create_menu(self):
        created = self.env['ir.ui.menu']
        for rec in self:
            if not rec.menu_name or not rec.top_menu_id:
                continue
            if rec.menu_id:
                # Update existing menu label / parent
                rec.menu_id.write({
                    'name': rec.menu_name,
                    'parent_id': rec.top_menu_id.id,
                })
                created |= rec.menu_id
                continue

            custom_action = self.env['ir.actions.client'].create({
                'name': _('%s Action') % rec.name,
                'tag': 'dynamic_dashboard_ai_nexgen.dashboard_view',
                'context': {'default_dashboard_id': rec.id},
            })
            menu = self.env['ir.ui.menu'].create({
                'name': rec.menu_name,
                'parent_id': rec.top_menu_id.id,
                'action': f'ir.actions.client,{custom_action.id}',
            })
            rec.menu_id = menu.id
            created |= menu

        if not created:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Menu'),
                    'message': _('Set Menu Name and Parent Menu first.'),
                    'type': 'warning',
                    'sticky': False,
                },
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Menu'),
                'message': _('Dashboard menu created successfully. Reload the page to see it.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def export_dashboard(self):
        self.ensure_one()
        items_data = []
        for item in self.item_ids:
            items_data.append({
                'name': item.name,
                'item_type': item.item_type,
                'model_id': item.model_id.model,
                'domain': item.domain,
                'tile_color': item.tile_color,
                'tile_icon': item.tile_icon,
                'data_calculation_type': item.data_calculation_type,
                'data_type': item.data_type,
                'measure_field_ids': item.measure_field_ids.mapped('name'),
                'measure_field_2_ids': item.measure_field_2_ids.mapped('name'),
                'list_view_field_ids': item.list_view_field_ids.mapped('name'),
                'group_by_field_id': item.group_by_field_id.name if item.group_by_field_id else False,
                'group_by_date_type': item.group_by_date_type,
                'sub_group_by_field_id': item.sub_group_by_field_id.name if item.sub_group_by_field_id else False,
                'sub_group_by_date_type': item.sub_group_by_date_type,
                'sort_by_field_id': item.sort_by_field_id.name if item.sort_by_field_id else False,
                'sort_order': item.sort_order,
                'record_limit': item.record_limit,
                'enable_target': item.enable_target,
                'standard_target_value': item.standard_target_value,
                'target_view': item.target_view,
                'chart_theme': item.chart_theme,
                'is_stacked': item.is_stacked,
                'show_data_value': item.show_data_value,
                'grid_x': item.grid_x,
                'grid_y': item.grid_y,
                'grid_w': item.grid_w,
                'grid_h': item.grid_h,
            })

        filters_data = []
        for filt in self.custom_filter_ids:
            filters_data.append({
                'name': filt.name,
                'sequence': filt.sequence,
                'model': filt.model_name,
                'domain': filt.domain,
                'widget_type': filt.widget_type,
                'is_linked': filt.is_linked,
                'is_active': filt.is_active,
                'filter_field': filt.filter_field_id.name if filt.filter_field_id else False,
            })

        export_data = {
            'name': self.name,
            'category': self.category,
            'chart_theme': self.chart_theme,
            'background_color': self.background_color,
            'layout_direction': self.layout_direction,
            'is_rtl': self.is_rtl,
            'default_date_filter': self.default_date_filter,
            'sticky_navbar': self.sticky_navbar,
            'tv_interval': self.tv_interval,
            'tv_mode_type': self.tv_mode_type,
            'tv_hide_chrome': self.tv_hide_chrome,
            'present_notes': self.present_notes,
            'items': items_data,
            'filters': filters_data,
        }
        
        json_data = json.dumps(export_data, indent=4)
        
        attachment = self.env['ir.attachment'].create({
            'name': f"{self.name.replace(' ', '_')}.json",
            'type': 'binary',
            'raw': json_data.encode('utf-8'),
            'mimetype': 'application/json',
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    @api.model
    def website_ai_generate(self, dashboard_id, query, mode='add_items'):
        """Called from the website frontend to auto-generate and immediately apply AI dashboard items."""
        vals = {
            'generation_mode': mode,
            'input_mode': 'keyword',
            'keyword': 'custom',
            'custom_keyword': query,
        }
        if mode == 'add_items':
            vals['dashboard_id'] = dashboard_id
            
        wizard = self.env['dynamic.dashboard.ai.wizard'].create(vals)
        wizard.action_generate_suggestions()
        if wizard.line_ids:
            wizard.line_ids.write({'selected': True})
            action = wizard.action_save_selected()
            new_dashboard_id = action.get('context', {}).get('default_dashboard_id', dashboard_id)
            return {'success': True, 'count': len(wizard.line_ids), 'new_dashboard_id': new_dashboard_id}
        return {'success': False, 'error': 'AI could not generate any items for this query.'}
