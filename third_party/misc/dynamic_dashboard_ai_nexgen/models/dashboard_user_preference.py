# Copyright (C) NexGen Solutions
from odoo import models, fields, api, tools
import json

class DashboardUserPreference(models.Model):
    _name = 'dynamic.dashboard.user.preference'
    _description = 'Dashboard User Preference'

    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade', default=lambda self: self.env.user, index=True)
    dashboard_id = fields.Many2one('dynamic.dashboard', string='Dashboard', ondelete='cascade', index=True)
    item_id = fields.Many2one('dynamic.dashboard.item', string='Dashboard Item', ondelete='cascade', index=True)
    preference_data = fields.Text(string='Preference JSON', default='{}')

    _sql_constraints = [
        ('user_dashboard_item_uniq', 'unique(user_id, dashboard_id, item_id)', 'Preferences must be unique per user/dashboard/item!')
    ]

    @api.model
    def get_preferences_dict(self, dashboard_id):
        """Return dash/item preference maps for the active viewer.

        Website item fetches run under ``sudo()`` so ``ir.model.fields`` config
        is readable.  Prefer ``dd_website_fetch_uid`` when present so Chart
        Options saved via ``update_user_preference`` still apply to the real
        website viewer instead of the superuser.
        """
        uid = int(self.env.context.get('dd_website_fetch_uid') or self.env.uid)
        return self._get_preferences_dict_for_uid(uid, int(dashboard_id))

    @api.model
    @tools.ormcache('uid', 'dashboard_id')
    def _get_preferences_dict_for_uid(self, uid, dashboard_id):
        prefs = self.sudo().search([
            ('user_id', '=', uid),
            ('dashboard_id', '=', dashboard_id),
        ])
        dash_pref = {}
        item_prefs = {}
        for p in prefs:
            if not p.item_id:
                dash_pref = json.loads(p.preference_data or '{}')
            else:
                item_prefs[p.item_id.id] = json.loads(p.preference_data or '{}')
        return {'dash': dash_pref, 'items': item_prefs}

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        self.env.registry.clear_cache()
        return res

    def write(self, vals):
        res = super().write(vals)
        self.env.registry.clear_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self.env.registry.clear_cache()
        return res
