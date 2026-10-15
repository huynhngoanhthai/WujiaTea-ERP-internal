# -*- coding: utf-8 -*-
from odoo import models, _


class ResUsers(models.Model):
    _inherit = 'res.users'

    def action_open_permission_tree(self):
        """Open the wizard displaying the ir.ui.menu permission tree for this user."""
        self.ensure_one()
        wizard = self.env['wujia.user.menu.tree.wizard'].create({
            'user_id': self.id,
        })
        wizard.action_populate_menu_tree()

        return {
            'name': _("Permission Tree"),
            'type': 'ir.actions.act_window',
            'res_model': 'wujia.user.menu.tree.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
