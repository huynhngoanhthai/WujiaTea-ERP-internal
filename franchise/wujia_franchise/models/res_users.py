from odoo import _, fields, models
from odoo.tools import ormcache


class ResUsers(models.Model):
    _inherit = 'res.users'

    member_ids = fields.One2many(
        'wujia.franchise.member',
        'user_id',
        string='Franchise Memberships',
    )
    member_count = fields.Integer(
        string='Membership count',
        compute='_compute_member_count',
    )

    def _compute_member_count(self):
        for user in self:
            user.member_count = len(user.member_ids.filtered('is_currently_valid'))

    def _get_active_franchise_memberships(self):
        self.ensure_one()
        return self.member_ids.filtered('is_currently_valid')

    @ormcache('self.id')
    def _get_accessible_franchise_ids(self):
        # Per-worker cache. Invalidated qua wujia.franchise.member CRUD hooks.
        # Trả về tuple (immutable, hashable) các id của wujia.franchise.management
        # mà user đang có active membership.
        self.ensure_one()
        return tuple(self._get_active_franchise_memberships()
                     .mapped('franchise_id').ids)

    def _get_accessible_franchises(self):
        self.ensure_one()
        return self.env['wujia.franchise.management'].browse(
            self._get_accessible_franchise_ids()
        )

    def _get_franchise_role(self, franchise_id):
        self.ensure_one()
        membership = self.env['wujia.franchise.member'].find_active_membership(
            self.id, franchise_id
        )
        return membership.role if membership else False

    def action_view_franchise_members(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Franchise Memberships of %s', self.name),
            'res_model': 'wujia.franchise.member',
            'view_mode': 'list,form',
            'domain': [('user_id', '=', self.id)],
            'context': {'default_user_id': self.id},
        }
