from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


ROLE_OWNER = 'owner'
ROLE_MANAGER = 'manager'
ROLE_STAFF = 'staff'

ROLE_RANK = {ROLE_STAFF: 1, ROLE_MANAGER: 2, ROLE_OWNER: 3}


class WujiaFranchiseMember(models.Model):
    _name = 'wujia.franchise.member'
    _description = 'Wujia Franchise Membership'
    _order = 'franchise_id, is_primary_owner desc, date_from desc, id desc'
    _rec_name = 'user_id'

    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        ondelete='cascade',
        index=True,
    )
    franchise_id = fields.Many2one(
        'wujia.franchise.management',
        string='Franchise store',
        required=True,
        ondelete='cascade',
        index=True,
    )
    role = fields.Selection(
        [
            (ROLE_OWNER, 'Store Owner'),
            (ROLE_MANAGER, 'Manager'),
            (ROLE_STAFF, 'Staff'),
        ],
        string='Role',
        required=True,
        default=ROLE_STAFF,
    )
    is_primary_owner = fields.Boolean(
        string='Primary owner',
        default=False,
        help='Marks the primary owner of the store. Each store has exactly one primary owner.',
    )
    date_from = fields.Date(
        string='Valid from',
        default=fields.Date.context_today,
    )
    date_to = fields.Date(string='Valid until')
    active = fields.Boolean(default=True)
    is_pass = fields.Boolean(
        string='Passed Exam',
        default=False,
        tracking=True,
        help='Staff has passed certification exam.',
    )
    is_working = fields.Boolean(
        string='Is Working',
        default=True,
        tracking=True,
        help='Indicates whether employee is actively working at store.',
    )
    phone = fields.Char(related='user_id.phone', string='Phone', readonly=True)

    is_currently_valid = fields.Boolean(
        compute='_compute_is_currently_valid',
        store=True,
        index=True,
    )

    @api.depends('user_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.user_id.name or _('Unnamed')

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        domain = domain or []
        if name:
            domain = [('user_id.name', operator, name)] + domain
        return super()._name_search(name, domain=domain, operator=operator, limit=limit, order=order)

    @api.depends('active', 'is_working', 'date_from', 'date_to')
    def _compute_is_currently_valid(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_currently_valid = bool(
                rec.active
                and rec.is_working
                and (not rec.date_from or rec.date_from <= today)
                and (not rec.date_to or rec.date_to >= today)
            )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_("End date must be >= start date."))

    @api.constrains('is_primary_owner', 'role', 'franchise_id', 'active')
    def _check_primary_owner(self):
        for rec in self:
            if not rec.is_primary_owner:
                continue
            if rec.role != ROLE_OWNER:
                raise ValidationError(_("Main owner must have role = Owner."))
            duplicate = self.search([
                ('franchise_id', '=', rec.franchise_id.id),
                ('is_primary_owner', '=', True),
                ('active', '=', True),
                ('id', '!=', rec.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    "Store '%s' already has a main owner. Please deactivate previous owner membership first.",
                    rec.franchise_id.display_name,
                ))

    @api.constrains('user_id', 'franchise_id', 'active')
    def _check_unique_active(self):
        for rec in self:
            if not rec.active:
                continue
            duplicate = self.search([
                ('user_id', '=', rec.user_id.id),
                ('franchise_id', '=', rec.franchise_id.id),
                ('active', '=', True),
                ('id', '!=', rec.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    "User '%s' already has an active membership in store '%s'.",
                    rec.user_id.name, rec.franchise_id.display_name,
                ))

    @api.model
    def find_active_membership(self, user_id, franchise_id):
        return self.search([
            ('user_id', '=', user_id),
            ('franchise_id', '=', franchise_id),
            ('is_currently_valid', '=', True),
        ], limit=1)

    def has_role(self, role):
        self.ensure_one()
        return ROLE_RANK.get(self.role, 0) >= ROLE_RANK.get(role, 99)

    # ===========================================================
    # Cache invalidation + cron recompute
    # ===========================================================
    def _invalidate_user_cache(self):
        # Clear ormcache trên _get_accessible_franchise_ids.
        # registry.clear_cache() invalidate cross-worker (Odoo signal qua DB).
        if self:
            self.env.registry.clear_cache()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._invalidate_user_cache()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._invalidate_user_cache()
        return res

    def unlink(self):
        had_records = bool(self)
        res = super().unlink()
        if had_records:
            self.env.registry.clear_cache()
        return res

    @api.model
    def _cron_recompute_validity(self):
        # Re-trigger compute cho membership chuyển trạng thái valid/invalid theo ngày.
        from datetime import timedelta
        today = fields.Date.context_today(self)
        affected = self.search([
            '|',
            ('date_from', '=', today),
            ('date_to', '=', today - timedelta(days=1)),
        ])
        if affected:
            affected._compute_is_currently_valid()
            affected.flush_recordset()
            affected._invalidate_user_cache()
