# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MetabaseDashboard(models.Model):
    _name = 'metabase.dashboard'
    _description = 'Metabase BI Dashboard'
    _order = 'sequence, id'

    name = fields.Char(string='Dashboard Name', required=True)
    instance_id = fields.Many2one(
        'metabase.instance',
        string='Metabase Instance',
        required=True,
        ondelete='cascade'
    )
    dashboard_id = fields.Integer(
        string='Metabase Dashboard ID',
        required=True,
        help='Numeric ID of the dashboard in Metabase (e.g., 2)'
    )
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    group_ids = fields.Many2many(
        'res.groups',
        string='Allowed Security Groups',
        help='User groups permitted to view this dashboard menu.'
    )
    company_ids = fields.Many2many(
        'res.company',
        string='Allowed Companies',
        default=lambda self: [(6, 0, [self.env.company.id])],
        help='Companies permitted to view this dashboard.'
    )
    height = fields.Integer(
        string='Iframe Height (px)',
        default=800,
        help='Height of the embedded iframe in pixels'
    )
    allow_download = fields.Boolean(string='Allow Downloads', default=True)
    description = fields.Text(string='Description')

    show_under_menu_id = fields.Many2one(
        'ir.ui.menu',
        string='Show Under Menu',
        ondelete='set null',
        help='Parent Odoo menu under which this dashboard menu will be dynamically created.'
    )
    menu_id = fields.Many2one(
        'ir.ui.menu',
        string='Generated Menu',
        readonly=True,
        ondelete='cascade',
        copy=False,
        help='Automatically generated sub-menu record.'
    )
    action_id = fields.Many2one(
        'ir.actions.client',
        string='Generated Action',
        readonly=True,
        ondelete='cascade',
        copy=False,
        help='Automatically generated Client Action pointing to the Owl iframe renderer.'
    )

    @api.constrains('dashboard_id')
    def _check_dashboard_id(self):
        for rec in self:
            if rec.dashboard_id <= 0:
                raise ValidationError(_("Dashboard ID must be a positive integer."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_dynamic_menu()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ('name', 'show_under_menu_id', 'group_ids', 'sequence', 'active')):
            self._sync_dynamic_menu()
        return res

    def unlink(self):
        menus_to_unlink = self.mapped('menu_id').exists()
        actions_to_unlink = self.mapped('action_id').exists()

        # 1. Clear FK references to avoid restriction errors during delete
        self.sudo().write({'menu_id': False, 'action_id': False})

        # 2. Safely unlink associated menu and action records
        if menus_to_unlink:
            menus_to_unlink.sudo().unlink()
        if actions_to_unlink:
            actions_to_unlink.sudo().unlink()

        # 3. Unlink dashboard records
        return super().unlink()

    def _sync_dynamic_menu(self):
        """Synchronize ir.actions.client and ir.ui.menu records for dashboards."""
        menus_to_unlink = self.env['ir.ui.menu']
        actions_to_unlink = self.env['ir.actions.client']
        records_to_clear = self.env['metabase.dashboard']

        actions_to_create_vals = []
        records_for_new_actions = self.env['metabase.dashboard']

        for rec in self:
            if not rec.show_under_menu_id or not rec.active:
                if rec.menu_id or rec.action_id:
                    records_to_clear |= rec
                    if rec.menu_id:
                        menus_to_unlink |= rec.menu_id
                    if rec.action_id:
                        actions_to_unlink |= rec.action_id
                continue

            # 1. Prepare create or update ir.actions.client
            action_vals = {
                'name': rec.name,
                'tag': 'wujia_metabase_dashboard_client_action',
                'params': {'dashboard_id': rec.id},
                'target': 'current',
                'res_model': 'metabase.dashboard',
            }

            if rec.action_id:
                rec.action_id.sudo().write(action_vals)
            else:
                actions_to_create_vals.append(action_vals)
                records_for_new_actions |= rec

        # Create actions in batch
        if actions_to_create_vals:
            new_actions = self.env['ir.actions.client'].sudo().create(actions_to_create_vals)
            for rec, action in zip(records_for_new_actions, new_actions):
                rec.sudo().write({'action_id': action.id})

        menus_to_create_vals = []
        records_for_new_menus = self.env['metabase.dashboard']

        for rec in self:
            if not rec.show_under_menu_id or not rec.active:
                continue

            # 2. Prepare create or update ir.ui.menu
            groups_cmd = [(6, 0, rec.group_ids.ids)] if rec.group_ids else [(5, 0, 0)]
            menu_vals = {
                'name': rec.name,
                'parent_id': rec.show_under_menu_id.id,
                'action': f"ir.actions.client,{rec.action_id.id}",
                'sequence': rec.sequence,
                'active': rec.active,
                'group_ids': groups_cmd,
            }

            if rec.menu_id:
                rec.menu_id.sudo().write(menu_vals)
            else:
                menus_to_create_vals.append(menu_vals)
                records_for_new_menus |= rec

        # Create menus in batch
        if menus_to_create_vals:
            new_menus = self.env['ir.ui.menu'].sudo().create(menus_to_create_vals)
            for rec, menu in zip(records_for_new_menus, new_menus):
                rec.sudo().write({'menu_id': menu.id})

        if records_to_clear:
            records_to_clear.sudo().write({'menu_id': False, 'action_id': False})
        if menus_to_unlink:
            menus_to_unlink.sudo().unlink()
        if actions_to_unlink:
            actions_to_unlink.sudo().unlink()
