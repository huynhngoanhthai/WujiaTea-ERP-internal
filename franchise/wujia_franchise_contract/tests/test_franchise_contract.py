from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.wujia_franchise_contract.hooks import post_init_hook


@tagged('post_install', '-at_install', 'wujia_contract')
class TestFranchiseContract(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Franchise = cls.env['wujia.franchise.management']
        cls.Contract = cls.env['wujia.franchise.contract']
        cls.today = fields.Date.context_today(cls.env['wujia.franchise.contract'])
        cls.partner = cls.env['res.partner'].create({'name': 'Test Store Partner'})
        cls.store = cls.Franchise.create({
            'code': 'TCONTRACT01',
            'name': 'Test Contract Store',
            'partner_id': cls.partner.id,
        })

    def _contract(self, start, end, store=None, **extra):
        vals = {
            'franchise_id': (store or self.store).id,
            'start_date': start,
            'end_date': end,
        }
        vals.update(extra)
        return self.Contract.create(vals)

    def _set_legacy_dates(self, store, start, end):
        """Legacy rows are what the columns held BEFORE this module turned them computed."""
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE wujia_franchise_management SET franchise_start_date=%s, franchise_end_date=%s WHERE id=%s",
            (start, end, store.id),
        )
        store.invalidate_recordset(['franchise_start_date', 'franchise_end_date'])

    # ------------------------------------------------------- BA block 1: Store Master
    def test_01_store_master_sees_all_contracts(self):
        self._contract(date(2020, 1, 1), date(2020, 12, 31))
        self._contract(date(2021, 1, 1), date(2021, 12, 31))
        self.assertEqual(self.store.contract_count, 2)
        action = self.store.action_view_contracts()
        self.assertEqual(action['res_model'], 'wujia.franchise.contract')
        self.assertIn(('franchise_id', '=', self.store.id), action['domain'])
        self.assertEqual(action['context']['default_franchise_id'], self.store.id)

    def test_02_contract_number_falls_back_to_sequence(self):
        c = self._contract(date(2020, 1, 1), date(2020, 12, 31))
        self.assertTrue(c.name and c.name != '/')
        self.assertTrue(c.name.startswith('FC/'))

    # ------------------------------------------------------- BA block 2: create rules
    def test_03_end_before_start_rejected(self):
        with self.assertRaisesRegex(ValidationError, "greater than or equal to start date"):
            self._contract(date(2026, 12, 31), date(2026, 1, 1))
            self.env.flush_all()

    def test_04a_overlap_new_encloses_existing(self):
        self._contract(date(2026, 3, 1), date(2026, 6, 30))
        with self.assertRaises(ValidationError):
            self._contract(date(2026, 1, 1), date(2026, 12, 31))

    def test_04b_overlap_new_starts_inside(self):
        self._contract(date(2026, 1, 1), date(2026, 6, 30))
        with self.assertRaises(ValidationError):
            self._contract(date(2026, 5, 1), date(2026, 12, 31))

    def test_04c_overlap_new_inside_existing(self):
        self._contract(date(2026, 1, 1), date(2026, 12, 31))
        with self.assertRaises(ValidationError):
            self._contract(date(2026, 4, 1), date(2026, 5, 31))

    def test_04d_overlap_new_ends_inside(self):
        self._contract(date(2026, 6, 1), date(2026, 12, 31))
        with self.assertRaises(ValidationError):
            self._contract(date(2026, 1, 1), date(2026, 7, 31))

    def test_04e_touching_ranges_share_no_day(self):
        self._contract(date(2026, 1, 1), date(2026, 6, 30))
        with self.assertRaises(ValidationError):
            self._contract(date(2026, 6, 30), date(2026, 12, 31))

    def test_05_history_and_future_contracts_coexist(self):
        past = self._contract(date(2020, 1, 1), date(2020, 12, 31))
        current = self._contract(self.today - timedelta(days=5), self.today + timedelta(days=5))
        future = self._contract(self.today + timedelta(days=100), self.today + timedelta(days=300))
        self.assertEqual(self.store.contract_count, 3)
        self.assertEqual(past.state, 'expired')
        self.assertEqual(current.state, 'effective')
        self.assertEqual(future.state, 'draft')

    def test_06_cancelled_contract_frees_its_range(self):
        first = self._contract(date(2026, 1, 1), date(2026, 12, 31))
        first.action_cancel()
        self.assertEqual(first.state, 'cancelled')
        replacement = self._contract(date(2026, 1, 1), date(2026, 12, 31))
        self.assertTrue(replacement.id)
        # restoring the cancelled one would recreate the clash, so it must be refused
        with self.assertRaises(ValidationError):
            first.action_restore()

    # ------------------------------------------------------- BA block 3: state = dates
    def test_07a_state_future_is_draft(self):
        c = self._contract(self.today + timedelta(days=10), self.today + timedelta(days=20))
        self.assertEqual(c.state, 'draft')

    def test_07b_state_today_inside_range_is_effective(self):
        c = self._contract(self.today - timedelta(days=1), self.today + timedelta(days=1))
        self.assertEqual(c.state, 'effective')

    def test_07c_state_past_is_expired(self):
        c = self._contract(self.today - timedelta(days=20), self.today - timedelta(days=10))
        self.assertEqual(c.state, 'expired')

    def test_07d_state_boundaries_are_inclusive(self):
        self.assertEqual(self._contract(self.today, self.today).state, 'effective')

    def test_08_store_shows_current_contract_and_remaining_days(self):
        self._contract(date(2020, 1, 1), date(2020, 12, 31))
        current = self._contract(self.today - timedelta(days=5), self.today + timedelta(days=30))
        self.assertEqual(self.store.current_contract_id, current)
        self.assertEqual(self.store.franchise_start_date, current.start_date)
        self.assertEqual(self.store.franchise_end_date, current.end_date)
        self.assertEqual(self.store.remaining_days, 30)
        self.assertFalse(self.store.is_expired)

    def test_09_expiry_never_locks_the_store(self):
        """BA: hết hạn chỉ cảnh báo — không đổi status, không bật portal_locked."""
        self.store.write({'status': 'active', 'portal_locked': False})
        self._contract(self.today - timedelta(days=30), self.today - timedelta(days=1))
        self.assertEqual(self.store.current_contract_id.state, 'expired')
        self.assertTrue(self.store.is_expired)

        warned = self.Franchise._cron_check_expired()
        self.assertTrue(warned, "the store whose contract ended yesterday must be warned about")
        self.assertEqual(self.store.status, 'active')
        self.assertFalse(self.store.portal_locked)

    def test_10_cron_flips_state_when_a_boundary_is_crossed(self):
        c = self._contract(self.today + timedelta(days=10), self.today + timedelta(days=20))
        self.assertEqual(c.state, 'draft')
        # simulate time passing: the contract now started, only the cron can notice
        self.env.cr.execute(
            "UPDATE wujia_franchise_contract SET start_date=%s, end_date=%s WHERE id=%s",
            (self.today - timedelta(days=1), self.today + timedelta(days=1), c.id),
        )
        c.invalidate_recordset(['start_date', 'end_date'])
        self.Contract._cron_refresh_state()
        self.assertEqual(c.state, 'effective')

    def test_10b_cancelled_contract_is_never_the_current_one(self):
        live = self._contract(date(2020, 1, 1), date(2020, 12, 31))
        later = self._contract(self.today - timedelta(days=5), self.today + timedelta(days=5))
        later.action_cancel()
        self.assertEqual(later.state, 'cancelled')
        self.assertEqual(self.store.current_contract_id, live)
        self.assertEqual(self.store.franchise_end_date, date(2020, 12, 31))

    # ------------------------------------------------------- BA block 4: migration
    def test_11_migration_creates_at_most_one_contract_and_is_idempotent(self):
        legacy = self.Franchise.create({'code': 'TCONTRACT02', 'name': 'Legacy Store',
                                        'partner_id': self.partner.id})
        blank = self.Franchise.create({'code': 'TCONTRACT03', 'name': 'Blank Store',
                                       'partner_id': self.partner.id})
        self._set_legacy_dates(legacy, date(2025, 1, 1), date(2025, 12, 31))
        self.env['ir.config_parameter'].sudo().set_param('wujia_franchise_contract.legacy_migrated', False)

        self.Franchise._migrate_legacy_franchise_contracts()
        self.assertEqual(legacy.contract_count, 1)
        self.assertEqual(legacy.contract_ids.start_date, date(2025, 1, 1))
        self.assertEqual(legacy.contract_ids.end_date, date(2025, 12, 31))
        self.assertEqual(blank.contract_count, 0)

        total = self.Contract.search_count([])
        self.Franchise._migrate_legacy_franchise_contracts()
        self.assertEqual(self.Contract.search_count([]), total)

    def test_12_post_init_hook_runs_the_migration(self):
        store = self.Franchise.create({'code': 'TCONTRACT04', 'name': 'Hook Store',
                                       'partner_id': self.partner.id})
        self._set_legacy_dates(store, date(2025, 6, 1), date(2026, 5, 31))
        self.env['ir.config_parameter'].sudo().set_param('wujia_franchise_contract.legacy_migrated', False)
        post_init_hook(self.env)
        self.assertEqual(store.contract_count, 1)

    def test_13_migration_re_run_after_flag_reset_still_creates_nothing(self):
        legacy = self.Franchise.create({'code': 'TCONTRACT05', 'name': 'Twice Store',
                                        'partner_id': self.partner.id})
        self._set_legacy_dates(legacy, date(2025, 1, 1), date(2025, 12, 31))
        self.env['ir.config_parameter'].sudo().set_param('wujia_franchise_contract.legacy_migrated', False)
        self.Franchise._migrate_legacy_franchise_contracts()
        self.env['ir.config_parameter'].sudo().set_param('wujia_franchise_contract.legacy_migrated', False)
        self.Franchise._migrate_legacy_franchise_contracts()
        self.assertEqual(legacy.contract_count, 1)

    # ------------------------------------------------------- Q3: edit vs delete
    def test_14_effective_contract_can_be_edited(self):
        c = self._contract(self.today - timedelta(days=5), self.today + timedelta(days=5))
        self.assertEqual(c.state, 'effective')
        c.write({'end_date': self.today + timedelta(days=400), 'note': 'Renewed'})
        self.assertEqual(c.end_date, self.today + timedelta(days=400))
        self.assertEqual(self.store.franchise_end_date, c.end_date)

    def test_15_editing_into_an_overlap_is_still_refused(self):
        self._contract(date(2026, 1, 1), date(2026, 6, 30))
        other = self._contract(date(2027, 1, 1), date(2027, 6, 30))
        with self.assertRaises(ValidationError):
            other.write({'start_date': date(2026, 6, 1)})

    def test_16_effective_and_expired_contracts_cannot_be_deleted(self):
        effective = self._contract(self.today - timedelta(days=5), self.today + timedelta(days=5))
        with self.assertRaises(UserError):
            effective.unlink()
        expired = self._contract(date(2020, 1, 1), date(2020, 12, 31))
        with self.assertRaises(UserError):
            expired.unlink()
        draft = self._contract(self.today + timedelta(days=50), self.today + timedelta(days=60))
        draft.unlink()
        self.assertFalse(draft.exists())

    # ------------------------------------------------------- Q5: onboarding wizard
    def test_17_onboarding_wizard_creates_the_first_contract(self):
        wizard = self.env['wujia.franchise.onboarding.wizard'].create({
            'mode': 'store',
            'code': 'TCONTRACT06',
            'name': 'Wizard Store',
            'franchise_start_date': self.today,
            'franchise_end_date': self.today + timedelta(days=730),
            'partner_mode': 'new',
            'partner_name': 'Wizard Store Partner',
        })
        store = wizard._create_franchise()
        self.assertEqual(store.contract_count, 1, "the wizard must open the first contract")
        self.assertEqual(store.contract_ids.start_date, self.today)
        self.assertEqual(store.contract_ids.end_date, self.today + timedelta(days=730))
        self.assertEqual(store.franchise_start_date, self.today, "store still shows the dates read-only")
