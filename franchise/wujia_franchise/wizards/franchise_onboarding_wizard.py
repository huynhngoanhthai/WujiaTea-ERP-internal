import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..models.wujia_franchise_member import ROLE_OWNER, ROLE_SELECTION, ROLE_STAFF

HQ_GROUP = 'wujia_franchise.group_franchise_manager'
PORTAL_GROUP = 'base.group_portal'
INTERNAL_GROUP = 'base.group_user'


def _digits(value):
    return re.sub(r'\D', '', value or '')


class WujiaFranchiseOnboardingWizard(models.TransientModel):
    _name = 'wujia.franchise.onboarding.wizard'
    _description = 'Franchise store onboarding'

    mode = fields.Selection(
        [('store', 'New store'), ('member', 'Add store users')],
        string='Mode', default='store', required=True,
    )
    franchise_id = fields.Many2one(
        'wujia.franchise.management',
        string='Franchise store',
    )

    code = fields.Char(string='Store code')
    name = fields.Char(string='Store name')
    area_id = fields.Many2one('res.area', string='Area')
    state_id = fields.Many2one('res.country.state', string='Province')
    address = fields.Text(string='Address')
    opening_date = fields.Date(string='Opening date')
    franchise_start_date = fields.Date(
        string='Franchise start date',
        default=fields.Date.context_today,
    )
    franchise_end_date = fields.Date(string='Franchise end date')
    phone = fields.Char(string='Store phone')
    email = fields.Char(string='Store email')

    partner_mode = fields.Selection(
        [('new', 'Create a new Store Partner'), ('existing', 'Link an existing Partner')],
        string='Store Partner', default='new', required=True,
    )
    partner_id = fields.Many2one('res.partner', string='Existing Partner')
    partner_name = fields.Char(string='Partner name')
    partner_phone = fields.Char(string='Partner phone')
    partner_email = fields.Char(string='Partner email')
    partner_vat = fields.Char(string='Tax ID')
    partner_street = fields.Char(string='Partner address')

    duplicate_partner_ids = fields.Many2many(
        'res.partner',
        string='Possible duplicates',
        compute='_compute_duplicate_partner_ids',
    )
    duplicate_ack = fields.Boolean(
        string='I checked the list above, create a new Partner anyway',
    )
    partner_warning = fields.Text(
        string='Partner warning',
        compute='_compute_partner_warning',
    )

    member_line_ids = fields.One2many(
        'wujia.franchise.onboarding.member.line', 'wizard_id',
        string='Store users',
    )

    # ------------------------------------------------------------------ compute
    @api.depends('partner_mode', 'partner_name', 'partner_phone', 'partner_email', 'partner_vat')
    def _compute_duplicate_partner_ids(self):
        for wiz in self:
            wiz.duplicate_partner_ids = (
                wiz._find_duplicate_partners() if wiz.partner_mode == 'new'
                else self.env['res.partner']
            )

    @api.depends('partner_mode', 'partner_id', 'franchise_id')
    def _compute_partner_warning(self):
        for wiz in self:
            wiz.partner_warning = wiz._partner_link_warning()

    # ------------------------------------------------------------------ helpers
    def _find_duplicate_partners(self):
        self.ensure_one()
        domain = []
        if self.partner_name:
            domain.append(('name', '=ilike', self.partner_name.strip()))
        if self.partner_email:
            domain.append(('email', '=ilike', self.partner_email.strip()))
        if self.partner_vat:
            domain.append(('vat', '=ilike', self.partner_vat.strip()))
        tail = _digits(self.partner_phone)[-8:]
        if len(tail) == 8:
            domain.append(('phone', 'ilike', tail))
        if not domain:
            return self.env['res.partner']
        return self.env['res.partner'].sudo().search(
            ['|'] * (len(domain) - 1) + domain, limit=10,
        )

    def _partner_link_warning(self):
        """Cảnh báo khi Partner đã gắn store khác / map không rõ — không chặn."""
        self.ensure_one()
        if self.partner_mode != 'existing' or not self.partner_id:
            return False
        partner = self.partner_id.sudo()
        state, franchises = partner._wujia_franchise_mapping()
        others = franchises - self.franchise_id
        if not others:
            return False
        if state == 'multi':
            return _(
                "Partner '%(partner)s' is already linked to %(count)s stores: %(stores)s.",
                partner=partner.display_name, count=len(franchises),
                stores=', '.join(franchises.mapped('display_name')),
            )
        return _(
            "Partner '%(partner)s' is already the Store Partner of '%(store)s'.",
            partner=partner.display_name, store=others[0].display_name,
        )

    def _assert_hq(self):
        if self.env.su:
            return
        if not self.env.user.has_group(HQ_GROUP):
            raise AccessError(_(
                "Only HQ (Wujia Franchise / Administrator) may run store onboarding."
            ))

    # ------------------------------------------------------------------ validation
    def _validate(self):
        self.ensure_one()
        if self.mode == 'store' and not self.franchise_id:
            if not self.code or not self.name:
                raise UserError(_("Store code and store name are required."))
            if not self.franchise_end_date:
                raise UserError(_("Franchise end date is required."))
            twin = self.env['wujia.franchise.management'].sudo().search(
                [('code', '=', self.code.strip())], limit=1,
            )
            if twin:
                raise UserError(_(
                    "Store code '%(code)s' already exists (%(store)s).",
                    code=self.code.strip(), store=twin.display_name,
                ))
        elif not self.franchise_id:
            raise UserError(_("Please select the store to add users to."))

        self._validate_partner()
        self._validate_members()

    def _validate_partner(self):
        self.ensure_one()
        if self.franchise_id and self.franchise_id.partner_id:
            return
        if self.partner_mode == 'existing':
            if not self.partner_id:
                raise UserError(_("Please select the Partner to link."))
            if not self.partner_id.sudo().active:
                raise UserError(_("Partner '%s' is archived.", self.partner_id.display_name))
            return
        if not self.partner_name:
            raise UserError(_("Please enter the name of the new Store Partner."))
        duplicates = self._find_duplicate_partners()
        if duplicates and not self.duplicate_ack:
            raise UserError(_(
                "These partners look like duplicates of '%(name)s':\n%(list)s\n\n"
                "Link one of them instead, or tick the confirmation box to create a new one anyway.",
                name=self.partner_name,
                list='\n'.join('- %s' % p.display_name for p in duplicates),
            ))

    def _validate_members(self):
        self.ensure_one()
        if self.mode == 'member' and not self.member_line_ids:
            raise UserError(_("Please add at least one store user."))

        logins = []
        for line in self.member_line_ids:
            line._validate(self.franchise_id)
            if line.user_mode == 'new':
                logins.append(line.user_login.strip().lower())
        duplicated = {login for login in logins if logins.count(login) > 1}
        if duplicated:
            raise UserError(_(
                "The same login is used twice in this form: %s", ', '.join(sorted(duplicated)),
            ))

        owners = self.member_line_ids.filtered(lambda l: l.is_primary_owner)
        if len(owners) > 1:
            raise UserError(_("A store may only have one primary owner."))

    # ------------------------------------------------------------------ action
    def action_confirm(self):
        self.ensure_one()
        self._assert_hq()
        self._validate()

        franchise = self.franchise_id or self._create_franchise()
        if not franchise.partner_id:
            franchise.partner_id = self._resolve_store_partner()
        for line in self.member_line_ids:
            line._apply(franchise)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wujia.franchise.management',
            'res_id': franchise.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _create_franchise(self):
        self.ensure_one()
        vals = {
            'code': self.code.strip(),
            'name': self.name.strip(),
            'status': 'draft',
            'area_id': self.area_id.id,
            'state_id': self.state_id.id,
            'address': self.address,
            'opening_date': self.opening_date,
            'phone': self.phone,
            'email': self.email,
        }
        if not self._wj_contracts_enabled():
            vals['franchise_start_date'] = self.franchise_start_date
            vals['franchise_end_date'] = self.franchise_end_date
        franchise = self.env['wujia.franchise.management'].sudo().create(vals)
        if self._wj_contracts_enabled():
            franchise._wj_ensure_contract(self.franchise_start_date, self.franchise_end_date)
        return franchise

    def _wj_contracts_enabled(self):
        """wujia_franchise_contract is an optional add-on; it owns the dates once installed."""
        return 'wujia.franchise.contract' in self.env

    def _resolve_store_partner(self):
        self.ensure_one()
        if self.partner_mode == 'existing':
            return self.partner_id
        return self.env['res.partner'].sudo().create({
            'name': self.partner_name.strip(),
            'company_type': 'company',
            'phone': self.partner_phone,
            'email': self.partner_email,
            'vat': self.partner_vat,
            'street': self.partner_street,
            'state_id': self.state_id.id,
        })


class WujiaFranchiseOnboardingMemberLine(models.TransientModel):
    _name = 'wujia.franchise.onboarding.member.line'
    _description = 'Franchise onboarding — store user'

    wizard_id = fields.Many2one(
        'wujia.franchise.onboarding.wizard',
        required=True, ondelete='cascade',
    )
    user_mode = fields.Selection(
        [('new', 'Create a new Portal User'), ('existing', 'Use an existing Portal User')],
        string='Portal user', default='new', required=True,
    )
    user_id = fields.Many2one('res.users', string='Existing user')
    user_name = fields.Char(string='Full name')
    user_login = fields.Char(string='Login (email)')
    user_email = fields.Char(string='Email')
    user_phone = fields.Char(string='Phone')
    role = fields.Selection(
        ROLE_SELECTION, string='Role', required=True, default=ROLE_STAFF,
    )
    is_primary_owner = fields.Boolean(string='Primary owner')
    date_from = fields.Date(string='Valid from', default=fields.Date.context_today)

    # ------------------------------------------------------------------ helpers
    def _login_value(self):
        self.ensure_one()
        return (self.user_login or '').strip().lower()

    def _find_existing_account(self):
        """User trùng login hoặc trùng email — kể cả user đã archive."""
        self.ensure_one()
        login = self._login_value()
        email = (self.user_email or '').strip()
        domain = [('login', '=ilike', login)]
        if email and email.lower() != login:
            domain = ['|', '|', domain[0],
                      ('login', '=ilike', email), ('email', '=ilike', email)]
        return self.env['res.users'].sudo().with_context(active_test=False).search(
            domain, limit=1,
        )

    def _validate(self, franchise):
        self.ensure_one()
        if self.is_primary_owner and self.role != ROLE_OWNER:
            raise UserError(_("The primary owner must have the Owner role."))

        if self.user_mode == 'existing':
            user = self.user_id.sudo()
            if not user:
                raise UserError(_("Please select the existing portal user."))
            if not user.active:
                raise UserError(_(
                    "User '%s' is archived. Restore it first, or create a new portal user.",
                    user.login,
                ))
            if user.has_group(INTERNAL_GROUP):
                raise UserError(_(
                    "Login '%s' belongs to an Internal User. Onboarding never changes user "
                    "types — please use a portal account instead.", user.login,
                ))
            if not user.has_group(PORTAL_GROUP):
                raise UserError(_(
                    "User '%s' is not a Portal User. Onboarding never changes user types.",
                    user.login,
                ))
            if franchise and self.env['wujia.franchise.member'].sudo().search_count([
                ('user_id', '=', user.id),
                ('franchise_id', '=', franchise.id),
                ('active', '=', True),
            ]):
                raise UserError(_(
                    "User '%(login)s' already has an active membership in store '%(store)s'.",
                    login=user.login, store=franchise.display_name,
                ))
            return

        if not self.user_name or not self._login_value():
            raise UserError(_("Full name and login are required for a new portal user."))
        twin = self._find_existing_account()
        if twin:
            raise UserError(_(
                "An account already uses this login or email: %(login)s (%(name)s). "
                "Switch this line to 'Use an existing Portal User' — onboarding never "
                "creates a second account.",
                login=twin.login, name=twin.name,
            ))

    def _apply(self, franchise):
        self.ensure_one()
        user = self.user_id.sudo() if self.user_mode == 'existing' else self._create_portal_user()
        self.env['wujia.franchise.member'].sudo().create({
            'user_id': user.id,
            'franchise_id': franchise.id,
            'role': self.role,
            'is_primary_owner': self.is_primary_owner,
            'date_from': self.date_from,
        })

    def _create_portal_user(self):
        self.ensure_one()
        email = (self.user_email or self._login_value()).strip()
        partner = self.env['res.partner'].sudo().create({
            'name': self.user_name.strip(),
            'company_type': 'person',
            'email': email,
            'phone': self.user_phone,
        })
        return self.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name': self.user_name.strip(),
            'login': self._login_value(),
            'email': email,
            'phone': self.user_phone,
            'partner_id': partner.id,
            'group_ids': [(6, 0, [self.env.ref(PORTAL_GROUP).id])],
        })
