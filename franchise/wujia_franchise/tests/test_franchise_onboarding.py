from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'wujia_franchise_onboarding')
class TestFranchiseOnboarding(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env['wujia.franchise.onboarding.wizard']
        cls.Franchise = cls.env['wujia.franchise.management']
        cls.Member = cls.env['wujia.franchise.member']
        cls.portal_group = cls.env.ref('base.group_portal')
        cls.internal_group = cls.env.ref('base.group_user')

    def _store_vals(self, code='ONB-01', **kw):
        vals = {
            'mode': 'store',
            'code': code,
            'name': 'Onboarding store %s' % code,
            'franchise_end_date': '2030-12-31',
            'partner_mode': 'new',
            'partner_name': 'Store Partner %s' % code,
            'partner_phone': '0900000001',
        }
        vals.update(kw)
        return vals

    def _owner_line(self, login='owner.onb@example.com', **kw):
        vals = {
            'user_mode': 'new',
            'user_name': 'Owner ONB',
            'user_login': login,
            'role': 'owner',
            'is_primary_owner': True,
        }
        vals.update(kw)
        return (0, 0, vals)

    def _run(self, **kw):
        wizard = self.Wizard.create(self._store_vals(**kw))
        wizard.action_confirm()
        return wizard

    # ---------------------------------------------------------------- store
    def test_store_created_in_draft(self):
        self._run(member_line_ids=[self._owner_line()])
        store = self.Franchise.search([('code', '=', 'ONB-01')])
        self.assertEqual(store.status, 'draft')
        self.assertTrue(store.partner_id)

    def test_default_status_is_draft(self):
        store = self.Franchise.create({
            'code': 'ONB-DEF', 'name': 'Default status',
            'franchise_end_date': '2030-12-31',
        })
        self.assertEqual(store.status, 'draft')

    def test_duplicate_store_code_blocked(self):
        self._run(member_line_ids=[self._owner_line()])
        wizard = self.Wizard.create(self._store_vals(
            partner_name='Another partner', partner_phone='0900000099',
            member_line_ids=[self._owner_line(login='other.onb@example.com')],
        ))
        with self.assertRaises(UserError):
            wizard.action_confirm()

    # ---------------------------------------------------------------- partner
    def test_partner_created_once_on_rerun(self):
        self._run(member_line_ids=[self._owner_line()])
        store = self.Franchise.search([('code', '=', 'ONB-01')])
        partner = store.partner_id
        before = self.env['res.partner'].search_count([('name', '=', partner.name)])

        again = self.Wizard.create({
            'mode': 'member',
            'franchise_id': store.id,
            'partner_mode': 'new',
            'partner_name': partner.name,
            'member_line_ids': [self._owner_line(
                login='staff.onb@example.com', role='staff', is_primary_owner=False,
                user_name='Staff ONB',
            )],
        })
        again.action_confirm()
        self.assertEqual(store.partner_id, partner)
        self.assertEqual(
            self.env['res.partner'].search_count([('name', '=', partner.name)]), before,
        )

    def test_duplicate_partner_blocks_until_acknowledged(self):
        self._run(member_line_ids=[self._owner_line()])
        twin = self._store_vals(
            code='ONB-02', member_line_ids=[self._owner_line(login='o2.onb@example.com')],
        )
        wizard = self.Wizard.create(twin)
        self.assertTrue(wizard.duplicate_partner_ids)
        with self.assertRaises(UserError):
            wizard.action_confirm()
        wizard.duplicate_ack = True
        wizard.action_confirm()
        self.assertTrue(self.Franchise.search([('code', '=', 'ONB-02')]).partner_id)

    def test_existing_partner_warning_when_already_store_partner(self):
        self._run(member_line_ids=[self._owner_line()])
        partner = self.Franchise.search([('code', '=', 'ONB-01')]).partner_id
        wizard = self.Wizard.create(self._store_vals(
            code='ONB-03', partner_mode='existing', partner_id=partner.id,
            member_line_ids=[self._owner_line(login='o3.onb@example.com')],
        ))
        self.assertIn('ONB-01', wizard.partner_warning or '')

    # ---------------------------------------------------------------- users
    def test_new_portal_user_shape(self):
        self._run(member_line_ids=[self._owner_line()])
        user = self.env['res.users'].search([('login', '=', 'owner.onb@example.com')])
        self.assertTrue(user.has_group('base.group_portal'))
        self.assertFalse(user.has_group('base.group_user'))
        self.assertFalse(user.partner_id.parent_id)
        self.assertNotEqual(
            user.partner_id, self.Franchise.search([('code', '=', 'ONB-01')]).partner_id,
        )

    def test_duplicate_login_blocked(self):
        self._run(member_line_ids=[self._owner_line()])
        before = self.env['res.users'].search_count(
            [('login', '=', 'owner.onb@example.com')])
        wizard = self.Wizard.create(self._store_vals(
            code='ONB-04', partner_name='Partner 04', partner_phone='0900000004',
            member_line_ids=[self._owner_line()],
        ))
        with self.assertRaises(UserError):
            wizard.action_confirm()
        self.assertEqual(
            self.env['res.users'].search_count([('login', '=', 'owner.onb@example.com')]),
            before,
        )

    def test_duplicate_email_blocked(self):
        self._run(member_line_ids=[self._owner_line(
            user_email='shared.onb@example.com')])
        wizard = self.Wizard.create(self._store_vals(
            code='ONB-14', partner_name='Partner 14', partner_phone='0900000014',
            member_line_ids=[self._owner_line(
                login='other.login.onb@example.com',
                user_email='shared.onb@example.com')],
        ))
        with self.assertRaises(UserError):
            wizard.action_confirm()
        self.assertFalse(
            self.env['res.users'].search([('login', '=', 'other.login.onb@example.com')]))

    def test_internal_user_blocked_without_group_change(self):
        internal = self.env['res.users'].create({
            'name': 'Internal ONB', 'login': 'internal.onb@example.com',
            'group_ids': [(6, 0, [self.internal_group.id])],
        })
        groups_before = internal.group_ids
        wizard = self.Wizard.create(self._store_vals(
            code='ONB-05', partner_name='Partner 05', partner_phone='0900000005',
            member_line_ids=[(0, 0, {
                'user_mode': 'existing', 'user_id': internal.id, 'role': 'owner',
            })],
        ))
        with self.assertRaisesRegex(UserError, 'Internal User'):
            wizard.action_confirm()
        self.assertEqual(internal.group_ids, groups_before)

    def test_archived_user_blocked(self):
        self._run(member_line_ids=[self._owner_line()])
        user = self.env['res.users'].search([('login', '=', 'owner.onb@example.com')])
        user.active = False
        wizard = self.Wizard.create(self._store_vals(
            code='ONB-06', partner_name='Partner 06', partner_phone='0900000006',
            member_line_ids=[(0, 0, {
                'user_mode': 'existing', 'user_id': user.id, 'role': 'owner',
            })],
        ))
        with self.assertRaises(UserError):
            wizard.action_confirm()

    def test_duplicate_membership_blocked(self):
        self._run(member_line_ids=[self._owner_line()])
        store = self.Franchise.search([('code', '=', 'ONB-01')])
        user = self.env['res.users'].search([('login', '=', 'owner.onb@example.com')])
        before = self.Member.search_count([
            ('user_id', '=', user.id), ('franchise_id', '=', store.id)])
        wizard = self.Wizard.create({
            'mode': 'member', 'franchise_id': store.id,
            'member_line_ids': [(0, 0, {
                'user_mode': 'existing', 'user_id': user.id, 'role': 'staff',
            })],
        })
        with self.assertRaises(UserError):
            wizard.action_confirm()
        self.assertEqual(self.Member.search_count([
            ('user_id', '=', user.id), ('franchise_id', '=', store.id)]), before)

    def test_same_login_twice_in_one_form(self):
        wizard = self.Wizard.create(self._store_vals(
            code='ONB-07', partner_name='Partner 07', partner_phone='0900000007',
            member_line_ids=[
                self._owner_line(login='twin.onb@example.com'),
                self._owner_line(login='TWIN.onb@example.com',
                                 role='staff', is_primary_owner=False),
            ],
        ))
        with self.assertRaises(UserError):
            wizard.action_confirm()

    def test_primary_owner_must_have_owner_role(self):
        wizard = self.Wizard.create(self._store_vals(
            code='ONB-08', partner_name='Partner 08', partner_phone='0900000008',
            member_line_ids=[self._owner_line(
                login='po.onb@example.com', role='staff')],
        ))
        with self.assertRaises(UserError):
            wizard.action_confirm()

    def test_failing_line_creates_nothing(self):
        good = self._owner_line(login='half.onb@example.com')
        bad = (0, 0, {
            'user_mode': 'existing', 'user_id': False, 'role': 'staff',
        })
        wizard = self.Wizard.create(self._store_vals(
            code='ONB-09', partner_name='Partner 09', partner_phone='0900000009',
            member_line_ids=[good, bad],
        ))
        with self.assertRaises(UserError):
            wizard.action_confirm()
        self.assertFalse(self.Franchise.search([('code', '=', 'ONB-09')]))
        self.assertFalse(
            self.env['res.users'].search([('login', '=', 'half.onb@example.com')]))

    # ---------------------------------------------------------------- activate
    def test_activate_requires_partner_and_owner(self):
        store = self.Franchise.create({
            'code': 'ONB-10', 'name': 'Gate store',
            'franchise_end_date': '2030-12-31',
        })
        with self.assertRaises(ValidationError):
            store.action_set_active()

        self._run(code='ONB-11', member_line_ids=[
            self._owner_line(login='gate.onb@example.com')])
        ready = self.Franchise.search([('code', '=', 'ONB-11')])
        ready.action_set_active()
        self.assertEqual(ready.status, 'active')

    def test_activate_blocked_when_owner_missing(self):
        self._run(code='ONB-12', member_line_ids=[self._owner_line(
            login='staffonly.onb@example.com', role='staff', is_primary_owner=False)])
        store = self.Franchise.search([('code', '=', 'ONB-12')])
        self.assertTrue(store.partner_id)
        with self.assertRaises(ValidationError):
            store.action_set_active()
        self.assertEqual(store.status, 'draft')

    # ---------------------------------------------------------------- security
    def test_non_hq_user_blocked(self):
        clerk = self.env['res.users'].create({
            'name': 'Clerk ONB', 'login': 'clerk.onb@example.com',
            'group_ids': [(6, 0, [
                self.internal_group.id,
                self.env.ref('wujia_franchise.group_franchise_user').id,
            ])],
        })
        wizard = self.Wizard.create(self._store_vals(
            code='ONB-13', partner_name='Partner 13', partner_phone='0900000013',
            member_line_ids=[self._owner_line(login='sec.onb@example.com')],
        ))
        with self.assertRaises(AccessError):
            wizard.with_user(clerk).action_confirm()
