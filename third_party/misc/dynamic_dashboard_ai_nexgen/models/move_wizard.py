# Copyright (C) NexGen Solutions
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DynamicDashboardItemMove(models.TransientModel):
    _name = 'dynamic.dashboard.item.move'
    _description = 'Move or Duplicate Dashboard Item'

    item_id = fields.Many2one(
        'dynamic.dashboard.item',
        string='Item',
        required=True,
        readonly=True,
    )
    action = fields.Selection([
        ('move', 'Move'),
        ('duplicate', 'Duplicate'),
    ], string='Action', default='duplicate', required=True)
    dashboard_id = fields.Many2one(
        'dynamic.dashboard',
        string='Target Dashboard',
        required=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        if active_model == 'dynamic.dashboard.item' and active_id:
            item = self.env['dynamic.dashboard.item'].browse(active_id)
            if item.exists():
                res['item_id'] = item.id
                # Default target to current dashboard (user can change it)
                if 'dashboard_id' not in res or not res.get('dashboard_id'):
                    res['dashboard_id'] = item.dashboard_id.id
        return res

    def action_apply(self):
        self.ensure_one()
        if not self.item_id:
            raise UserError(_('No dashboard item selected. Open Move/Duplicate from an item form.'))
        if not self.dashboard_id:
            raise UserError(_('Please select a target dashboard.'))

        item = self.item_id
        target = self.dashboard_id

        if self.action == 'move':
            item.write({'dashboard_id': target.id})
            result_item = item
            message = _('Item moved to "%s".') % target.name
        else:
            # Place duplicate next to / below original so it is visible on the grid
            max_y = max(target.item_ids.mapped('grid_y') or [0])
            result_item = item.copy({
                'dashboard_id': target.id,
                'name': _('%s (Copy)') % item.name,
                'grid_x': item.grid_x if target.id == item.dashboard_id.id else 0,
                'grid_y': (item.grid_y + (item.grid_h or 4) + 1)
                if target.id == item.dashboard_id.id
                else max_y + (item.grid_h or 4) + 1,
            })
            message = _('Item duplicated on "%s".') % target.name

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Done'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': result_item.name,
                    'res_model': 'dynamic.dashboard.item',
                    'res_id': result_item.id,
                    'view_mode': 'form',
                    'views': [(False, 'form')],
                    'target': 'current',
                },
            },
        }
