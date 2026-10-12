"""Portal accounts default to Vietnamese (UI-02, cluster B).

Sprint 34 migrated every existing portal user to vi_VN and seeded the portal
template user, so accounts created through the portal wizard inherit it. Accounts
created directly (``res.users.create`` from the backend) do not: they take their
language from the creating user's context, and since Sprint 44 the backend runs in
English. That is why BA kept seeing the US flag in the portal header on freshly
created store accounts.

An explicit ``lang`` in vals still wins, so an English portal account remains
possible on purpose.
"""
from odoo import api, models

PORTAL_DEFAULT_LANG = "vi_VN"


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model_create_multi
    def create(self, vals_list):
        portal_group = self.env.ref("base.group_portal", raise_if_not_found=False)
        if portal_group:
            for vals in vals_list:
                if vals.get("lang"):
                    continue
                if portal_group.id in self._wujia_group_ids(vals):
                    vals["lang"] = PORTAL_DEFAULT_LANG
        return super().create(vals_list)

    @staticmethod
    def _wujia_group_ids(vals):
        """Group ids a create() vals dict would end up with, across command forms."""
        ids = set()
        for command in vals.get("group_ids") or []:
            if isinstance(command, int):
                ids.add(command)
            elif isinstance(command, (list, tuple)) and command:
                if command[0] == 4 and len(command) > 1:
                    ids.add(command[1])
                elif command[0] == 6 and len(command) > 2:
                    ids.update(command[2] or [])
        return ids
