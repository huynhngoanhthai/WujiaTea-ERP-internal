# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Integration tests for the cache invalidation hook on account.move.

Covers:

* Posting a draft entry bumps the version counter.
* Cancelling a posted entry bumps the counter.
* Drafting a posted entry bumps the counter.
* An unrelated field write does not bump the counter.
* Multi company posts bump only the affected company's counter.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from odoo import Command
from odoo.exceptions import AccessError
from odoo.release import version_info
from odoo.tests import new_test_user, tagged

from .common import EhAccountIntegrationTestCase


@tagged('eh_account_base', 'integration', 'post_install', '-at_install')
class TestCacheInvalidationHook(EhAccountIntegrationTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        migration_path = (
            Path(__file__).parents[1]
            / 'migrations' / '19.0.1.7.16' / 'post-migration.py'
        )
        spec = spec_from_file_location(
            'eh_account_base_post_migration_1716', migration_path,
        )
        cls.migration_1716 = module_from_spec(spec)
        spec.loader.exec_module(cls.migration_1716)

    def _local_report_versions(self, companies):
        self.env.cr.execute(
            "SELECT company_id, version "
            "FROM eh_account_report_company_version "
            "WHERE company_id IN %s",
            (tuple(companies.ids),),
        )
        return dict(self.env.cr.fetchall())

    def test_company_counter_bump_uses_isolated_row_not_res_company(self):
        self.env.cr.execute(
            "SELECT ctid::text FROM res_company WHERE id = %s",
            (self.company.id,),
        )
        company_tuple_before = self.env.cr.fetchone()[0]
        local_before = self._local_report_versions(self.company).get(
            self.company.id, 0,
        )

        self.env['res.company']._eh_bump_move_version([self.company.id])

        self.env.cr.execute(
            "SELECT ctid::text FROM res_company WHERE id = %s",
            (self.company.id,),
        )
        self.assertEqual(self.env.cr.fetchone()[0], company_tuple_before)
        self.assertEqual(
            self._local_report_versions(self.company)[self.company.id],
            local_before + 1,
        )

    def test_global_epoch_leaves_every_company_counter_row_untouched(self):
        other = self.env['res.company'].create({
            'name': 'Global epoch isolation company',
            'currency_id': self.company.currency_id.id,
        })
        companies = self.company | other
        local_before = self._local_report_versions(companies)
        companies.invalidate_recordset(['eh_move_version'])
        visible_before = {
            company.id: company.eh_move_version for company in companies
        }
        self.env.cr.execute(
            "SELECT COALESCE(version, 0) "
            "FROM eh_account_report_global_version WHERE id = 1"
        )
        row = self.env.cr.fetchone()
        global_before = int(row[0]) if row else 0

        self.env['res.company']._eh_bump_global_report_version()

        self.assertEqual(
            self._local_report_versions(companies), local_before,
        )
        self.env.cr.execute(
            "SELECT version FROM eh_account_report_global_version WHERE id = 1"
        )
        self.assertEqual(self.env.cr.fetchone()[0], global_before + 1)
        companies.invalidate_recordset(['eh_move_version'])
        for company in companies:
            self.assertEqual(
                company.eh_move_version,
                visible_before[company.id] + 1,
            )

    def test_1716_migration_seeds_epoch_above_every_legacy_counter(self):
        self.env.cr.execute(
            "SELECT COALESCE(MAX(version), 0) "
            "FROM eh_account_report_global_version"
        )
        global_before = int(self.env.cr.fetchone()[0])
        self.env.cr.execute(
            "SELECT EXISTS ("
            "SELECT 1 FROM pg_attribute "
            "WHERE attrelid = 'res_company'::regclass "
            "AND attname = 'eh_move_version' AND attnum > 0 "
            "AND NOT attisdropped)"
        )
        if not self.env.cr.fetchone()[0]:
            self.env.cr.execute(
                "ALTER TABLE res_company ADD COLUMN "
                "eh_move_version INTEGER NOT NULL DEFAULT 0"
            )
        legacy_high = global_before + 100
        self.env.cr.execute(
            "UPDATE res_company SET eh_move_version = %s WHERE id = %s",
            (legacy_high, self.company.id),
        )

        self.migration_1716.migrate(self.env.cr, '19.0.1.7.15')

        self.env.cr.execute(
            "SELECT version FROM eh_account_report_global_version WHERE id = 1"
        )
        self.assertGreaterEqual(
            self.env.cr.fetchone()[0], legacy_high + 1,
        )

    def test_version_counter_rejects_direct_write_even_with_sudo(self):
        original = self.company.eh_move_version
        with self.assertRaises(AccessError):
            self.company.write({'eh_move_version': original + 1000})
        with self.assertRaises(AccessError):
            self.company.sudo().write({'eh_move_version': original + 1000})
        self.company.invalidate_recordset(['eh_move_version'])
        self.assertEqual(self.company.eh_move_version, original)

    def test_version_counter_rejects_create_time_injection(self):
        with self.assertRaises(AccessError):
            self.env['res.company'].sudo().create({
                'name': 'Counter Injection',
                'currency_id': self.company.currency_id.id,
                'eh_move_version': 999999,
            })

    def test_post_bumps_version(self):
        before = self.company.eh_move_version
        self.post_balanced_move([
            {'account': self.account_revenue, 'credit': 100.0},
            {'account': self.account_cash, 'debit': 100.0},
        ])
        self.company.invalidate_recordset(['eh_move_version'])
        self.assertGreater(
            self.company.eh_move_version,
            before,
            "Posting a balanced entry should bump eh_move_version",
        )

    def test_cancel_bumps_version(self):
        move = self.post_balanced_move([
            {'account': self.account_revenue, 'credit': 50.0},
            {'account': self.account_cash, 'debit': 50.0},
        ])
        self.company.invalidate_recordset(['eh_move_version'])
        post_version = self.company.eh_move_version

        move.button_cancel()
        self.company.invalidate_recordset(['eh_move_version'])
        self.assertGreater(
            self.company.eh_move_version,
            post_version,
            "Cancelling a posted entry should bump eh_move_version",
        )

    def test_draft_bumps_version(self):
        move = self.post_balanced_move([
            {'account': self.account_revenue, 'credit': 75.0},
            {'account': self.account_cash, 'debit': 75.0},
        ])
        self.company.invalidate_recordset(['eh_move_version'])
        post_version = self.company.eh_move_version

        move.button_draft()
        self.company.invalidate_recordset(['eh_move_version'])
        self.assertGreater(
            self.company.eh_move_version,
            post_version,
            "Returning a posted entry to draft should bump eh_move_version",
        )

    def test_unrelated_write_does_not_bump(self):
        move = self.post_balanced_move([
            {'account': self.account_revenue, 'credit': 60.0},
            {'account': self.account_cash, 'debit': 60.0},
        ])
        self.company.invalidate_recordset(['eh_move_version'])
        baseline = self.company.eh_move_version

        # Narration is not selected by any cached report payload.
        move.write({'narration': 'Internal note outside report output'})
        self.company.invalidate_recordset(['eh_move_version'])
        self.assertEqual(
            self.company.eh_move_version,
            baseline,
            "Writing a non-report field must not bump eh_move_version",
        )

    def test_report_visible_reference_write_bumps(self):
        move = self.post_balanced_move([
            {'account': self.account_revenue, 'credit': 60.0},
            {'account': self.account_cash, 'debit': 60.0},
        ])
        self.company.invalidate_recordset(['eh_move_version'])
        baseline = self.company.eh_move_version
        move.write({'ref': 'NEW REPORT REFERENCE'})
        self.company.invalidate_recordset(['eh_move_version'])
        self.assertGreater(self.company.eh_move_version, baseline)

    def test_partial_reconcile_amount_write_bumps(self):
        if 'eh.batch.payment' in self.env.registry:
            self.skipTest(
                "Batch Payment makes partial financial fields core-owned; "
                "standalone Base coverage exercises the write hook."
            )
        # Keep this fixture valid in a mixed install: Batch Payment correctly
        # rejects low-level partials unless both posted journal items use the
        # same company, account, and a genuinely reconcilable account.
        if not self.account_cash.reconcile:
            self.account_cash.reconcile = True
        debit_move = self.post_balanced_move([
            {'account': self.account_cash, 'debit': 100.0},
            {'account': self.account_revenue, 'credit': 100.0},
        ])
        credit_move = self.post_balanced_move([
            {'account': self.account_expense, 'debit': 100.0},
            {'account': self.account_cash, 'credit': 100.0},
        ])
        debit_line = debit_move.line_ids.filtered(
            lambda line: line.account_id == self.account_cash
        )
        credit_line = credit_move.line_ids.filtered(
            lambda line: line.account_id == self.account_cash
        )
        self.assertEqual(debit_move.state, 'posted')
        self.assertEqual(credit_move.state, 'posted')
        self.assertEqual(debit_line.company_id, credit_line.company_id)
        self.assertEqual(debit_line.account_id, credit_line.account_id)
        self.assertTrue(debit_line.account_id.reconcile)
        partial = self.env['account.partial.reconcile'].create({
            'debit_move_id': debit_line.id,
            'credit_move_id': credit_line.id,
            'amount': 50.0,
            'debit_amount_currency': 50.0,
            'credit_amount_currency': 50.0,
        })
        self.company.invalidate_recordset(['eh_move_version'])
        baseline = self.company.eh_move_version
        partial.write({
            'amount': 40.0,
            'debit_amount_currency': 40.0,
            'credit_amount_currency': 40.0,
        })
        self.company.invalidate_recordset(['eh_move_version'])
        self.assertGreater(self.company.eh_move_version, baseline)

    def test_payment_method_outstanding_account_write_bumps(self):
        journal = self.env['account.journal'].search([
            ('company_id', '=', self.company.id),
            ('type', 'in', ('bank', 'cash')),
        ], limit=1)
        if not journal:
            journal = self.env['account.journal'].create({
                'name': 'Cache Invalidation Bank',
                'code': 'CIBK',
                'type': 'bank',
                'company_id': self.company.id,
                'default_account_id': self.account_cash.id,
            })
        method_line = self.env['account.payment.method.line'].search([
            ('journal_id', '=', journal.id),
        ], limit=1)
        if not method_line:
            method = self.env['account.payment.method'].search([], limit=1)
            method_line = self.env['account.payment.method.line'].create({
                'payment_method_id': method.id,
                'journal_id': journal.id,
            })
        outstanding = self._ensure_account(
            self.env, '1097', 'Cache Outstanding', 'asset_current',
        )
        self.company.invalidate_recordset(['eh_move_version'])
        baseline = self.company.eh_move_version
        method_line.write({'payment_account_id': outstanding.id})
        self.company.invalidate_recordset(['eh_move_version'])
        self.assertGreater(self.company.eh_move_version, baseline)

    def test_standard_fx_configuration_write_bumps(self):
        self.company.invalidate_recordset(['eh_move_version'])
        baseline = self.company.eh_move_version
        self.company.write({
            'income_currency_exchange_account_id': self.account_revenue.id,
        })
        self.company.invalidate_recordset(['eh_move_version'])
        self.assertGreater(self.company.eh_move_version, baseline)

    def test_raw_account_code_store_write_bumps(self):
        account = self.account_revenue.with_company(self.company)
        self.company.invalidate_recordset(['eh_move_version'])
        baseline = self.company.eh_move_version
        code_field = 'code_store' if 'code_store' in account._fields else 'code'
        account.write({code_field: '499998'})
        self.company.invalidate_recordset(['eh_move_version'])
        self.assertGreater(self.company.eh_move_version, baseline)

    def test_account_company_scope_write_bumps(self):
        branch = self.env['res.company'].create({
            'name': 'Account ownership invalidation branch',
            'parent_id': self.company.id,
        })
        account = self.account_revenue
        self.company.invalidate_recordset(['eh_move_version'])
        baseline = self.company.eh_move_version
        if 'company_ids' in account._fields:
            account.write({'company_ids': [Command.link(branch.id)]})
        else:
            self.env.user.write({'company_ids': [Command.link(branch.id)]})
            account.with_context(allowed_company_ids=(
                self.company | branch
            ).ids).write({'company_id': branch.id})
        self.company.invalidate_recordset(['eh_move_version'])
        self.assertGreater(self.company.eh_move_version, baseline)

    def test_root_account_metadata_write_bumps_descendant_branch(self):
        branch = self.env['res.company'].create({
            'name': 'Shared-chart cache branch',
            'parent_id': self.company.id,
        })
        self.env.user.write({'company_ids': [Command.link(branch.id)]})
        branch.invalidate_recordset(['eh_move_version'])
        baseline = branch.eh_move_version
        account = self.account_revenue.with_company(self.company)
        account.write({'name': 'Revenue renamed for shared chart'})
        branch.invalidate_recordset(['eh_move_version'])
        self.assertGreater(branch.eh_move_version, baseline)

    def test_branch_manager_metadata_bumps_hidden_root_owner_scope(self):
        if 'company_ids' not in self.env['account.account']._fields:
            self.skipTest('shared root-owned accounts start in Odoo 18')
        branch = self.env['res.company'].create({
            'name': 'Branch-scoped chart manager company',
            'parent_id': self.company.id,
        })
        manager = new_test_user(
            self.env,
            login='eh_branch_scoped_chart_manager',
            groups='account.group_account_manager',
            company_id=branch.id,
        )
        branch.invalidate_recordset(['eh_move_version'])
        baseline = branch.eh_move_version

        self.account_revenue.with_user(manager).with_company(branch).write({
            'name': 'Revenue renamed by branch-scoped manager',
        })

        branch.invalidate_recordset(['eh_move_version'])
        self.assertGreater(branch.eh_move_version, baseline)

    def test_root_metadata_and_reactivation_bump_archived_branch(self):
        branch = self.env['res.company'].create({
            'name': 'Archived shared-chart cache branch',
            'parent_id': self.company.id,
        })
        branch.active = False
        branch.invalidate_recordset(['eh_move_version'])
        archived_version = branch.eh_move_version

        self.account_revenue.with_company(self.company).write({
            'name': 'Revenue renamed while branch archived',
        })
        branch.invalidate_recordset(['eh_move_version'])
        self.assertGreater(branch.eh_move_version, archived_version)

        renamed_version = branch.eh_move_version
        branch.active = True
        branch.invalidate_recordset(['eh_move_version'])
        self.assertGreater(branch.eh_move_version, renamed_version)

    def test_company_reparent_bumps_every_descendant_version(self):
        if version_info[0] >= 17:
            self.skipTest('core forbids changing company hierarchy on 17+')
        ancestor = self.env['res.company'].create({
            'name': 'Moved accounting branch',
            'parent_id': self.company.id,
        })
        descendant = self.env['res.company'].create({
            'name': 'Moved accounting sub-branch',
            'parent_id': ancestor.id,
        })
        new_root = self.env['res.company'].create({
            'name': 'Replacement accounting root',
        })
        self.env.user.write({'company_ids': [
            Command.link(ancestor.id),
            Command.link(descendant.id),
            Command.link(new_root.id),
        ]})
        descendant.invalidate_recordset(['eh_move_version'])
        baseline = descendant.eh_move_version
        ancestor.write({'parent_id': new_root.id})
        descendant.invalidate_recordset(['eh_move_version'])
        self.assertGreater(descendant.eh_move_version, baseline)

    def test_company_partner_identity_write_bumps(self):
        replacement = self.env['res.partner'].create({
            'name': 'Replacement company accounting identity',
            'is_company': True,
        })
        self.company.invalidate_recordset(['eh_move_version'])
        baseline = self.company.eh_move_version
        self.company.write({'partner_id': replacement.id})
        self.company.invalidate_recordset(['eh_move_version'])
        self.assertGreater(self.company.eh_move_version, baseline)

    def test_force_delete_of_posted_move_bumps_version(self):
        move = self.post_balanced_move([
            {'account': self.account_revenue, 'credit': 15.0},
            {'account': self.account_cash, 'debit': 15.0},
        ])
        self.company.invalidate_recordset(['eh_move_version'])
        baseline = self.company.eh_move_version

        move.sudo().with_context(force_delete=True).unlink()

        self.company.invalidate_recordset(['eh_move_version'])
        self.assertGreater(self.company.eh_move_version, baseline)

    def test_post_bumps_each_company_independently(self):
        other_company = self.env['res.company'].create({
            'name': 'Second Company',
            'currency_id': self.company.currency_id.id,
        })
        other_company.invalidate_recordset(['eh_move_version'])
        other_before = other_company.eh_move_version

        # Post in our default company.
        self.post_balanced_move([
            {'account': self.account_revenue, 'credit': 10.0},
            {'account': self.account_cash, 'debit': 10.0},
        ])
        self.env['res.company'].invalidate_model(['eh_move_version'])
        v_self = self.company.eh_move_version
        v_other = other_company.eh_move_version
        self.assertGreater(v_self, 0)
        self.assertEqual(v_other, other_before,
                         "Other company's counter must not be bumped")
