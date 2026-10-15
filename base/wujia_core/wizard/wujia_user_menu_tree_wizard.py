# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class WujiaUserMenuTreeWizard(models.TransientModel):
    _name = 'wujia.user.menu.tree.wizard'
    _description = 'User Menu Permission Tree Wizard'

    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        readonly=True,
    )
    user_name = fields.Char(
        related='user_id.name',
        string='User Name',
        readonly=True,
    )
    user_login = fields.Char(
        related='user_id.login',
        string='Login ID',
        readonly=True,
    )
    total_menu_count = fields.Integer(
        string='Total Menus',
        readonly=True,
    )
    accessible_menu_count = fields.Integer(
        string='Accessible Menus',
        readonly=True,
    )
    tree_html = fields.Html(
        string='Menu Permission Tree',
        readonly=True,
        sanitize=False,
    )

    def action_populate_menu_tree(self):
        """Build interactive hierarchical HTML tree of ir.ui.menu with direct edit links."""
        self.ensure_one()
        target_user = self.user_id

        # Retrieve all visible menu IDs for the target user in debug mode (pure ORM)
        visible_menu_ids = self.env['ir.ui.menu'].with_user(target_user)._visible_menu_ids(debug=True)

        # Retrieve all active menus in system
        all_menus = self.env['ir.ui.menu'].search([], order='sequence asc, id asc')

        total_count = len(all_menus)
        accessible_count = sum(1 for m in all_menus if m.id in visible_menu_ids)

        # Group menus by parent_id
        menus_by_parent = {}
        for m in all_menus:
            parent_key = m.parent_id.id if m.parent_id else 0
            menus_by_parent.setdefault(parent_key, []).append(m)

        def render_tree(parent_id=0):
            children = menus_by_parent.get(parent_id, [])
            if not children:
                return ""

            html = ['<ul class="wj_menu_tree" style="list-style-type: none; margin: 0; padding-left: 20px;">']
            for child in children:
                has_access = child.id in visible_menu_ids
                sub_children = menus_by_parent.get(child.id, [])

                # Checkbox status
                checked_attr = 'checked="checked"' if has_access else ''
                status_color = '#dc3545' if has_access else '#6c757d'
                text_weight = 'font-weight: 600;' if (not child.parent_id or sub_children) else 'font-weight: 400;'
                
                # Link to open ir.ui.menu directly inside current Odoo single-page web client
                menu_url = f"/web#id={child.id}&amp;model=ir.ui.menu&amp;view_type=form"
                link_title = _("Click to view/edit ir.ui.menu (%s)", child.name)

                link_html = (
                    f'<a href="{menu_url}" title="{link_title}" '
                    f'style="{text_weight} color: #0d6efd; text-decoration: none; font-size: 14px; margin-right: 6px;" '
                    f'onmouseover="this.style.textDecoration=\'underline\'" onmouseout="this.style.textDecoration=\'none\'">'
                    f'{child.name}'
                    f'</a>'
                    f'<span style="font-size: 11px; color: #6c757d; background: #e9ecef; padding: 1px 6px; border-radius: 4px; font-family: monospace;">id: {child.id}</span>'
                )

                html.append('<li style="margin: 6px 0; line-height: 1.6;">')
                
                if sub_children:
                    html.append(
                        '<details open style="display: block;">'
                        '<summary style="cursor: pointer; outline: none; list-style: none; display: flex; align-items: center; gap: 8px;">'
                        '<span style="font-size: 11px; color: #495057; display: inline-block; width: 14px; text-align: center;">▼</span>'
                        f'<input type="checkbox" {checked_attr} disabled="disabled" style="cursor: default; width: 17px; height: 17px; accent-color: {status_color}; margin: 0; pointer-events: none;"/>'
                        f'{link_html}'
                        '</summary>'
                    )
                    html.append(render_tree(child.id))
                    html.append('</details>')
                else:
                    html.append(
                        '<div style="display: flex; align-items: center; gap: 8px; padding-left: 22px;">'
                        f'<input type="checkbox" {checked_attr} disabled="disabled" style="cursor: default; width: 17px; height: 17px; accent-color: {status_color}; margin: 0; pointer-events: none;"/>'
                        f'{link_html}'
                        '</div>'
                    )

                html.append('</li>')

            html.append('</ul>')
            return "".join(html)

        full_html = (
            '<div class="wj_menu_permission_container" style="max-height: 68vh; overflow-y: auto; padding: 12px 18px; background: #ffffff; border: 1px solid #dee2e6; border-radius: 8px; font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;">'
            + render_tree(0)
            + '</div>'
        )

        self.write({
            'total_menu_count': total_count,
            'accessible_menu_count': accessible_count,
            'tree_html': full_html,
        })
