# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Integration tests for MoveLineQuery: actual execution against seeded data.

Validates that the SQL the builder produces is not only syntactically valid
but also semantically correct, by comparing aggregated results against ORM
read_group results on the same fixture data.
"""

import odoo

from odoo.tests import tagged
from odoo.tools import SQL

from odoo.addons.eh_account_base.tools.sql_builder import MoveLineQuery
from .common import EhAccountIntegrationTestCase


@tagged('eh_account_base', 'integration', 'post_install', '-at_install')
class TestMoveLineQueryExecution(EhAccountIntegrationTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Seed three balanced entries with different account / partner mixes.
        cls.move_a = cls.post_balanced_move([
            {'account': cls.account_revenue, 'credit': 100.0, 'partner': cls.partner_a},
            {'account': cls.account_cash, 'debit': 100.0},
        ])
        cls.move_b = cls.post_balanced_move([
            {'account': cls.account_revenue, 'credit': 200.0, 'partner': cls.partner_b},
            {'account': cls.account_cash, 'debit': 200.0},
        ])
        cls.move_c = cls.post_balanced_move([
            {'account': cls.account_expense, 'debit': 50.0, 'partner': cls.partner_a},
            {'account': cls.account_cash, 'credit': 50.0},
        ])

    def test_sum_balance_revenue_only(self):
        rows = (
            MoveLineQuery(self.env, company_ids=[self.company.id])
            .select_balance_sum()
            .where_accounts([self.account_revenue.id])
            .execute()
        )
        self.assertEqual(len(rows), 1)
        # Revenue lines are credits, so balance is negative (-100 + -200).
        self.assertAlmostEqual(rows[0]['balance'], -300.0, places=2)

    def test_group_by_account_returns_per_account_totals(self):
        rows = (
            MoveLineQuery(self.env, company_ids=[self.company.id])
            .select_field('account_id')
            .select_balance_sum()
            .where_account_types(['income', 'expense'])
            .group_by('account_id')
            .execute()
        )
        by_account = {r['account_id']: r['balance'] for r in rows}
        self.assertAlmostEqual(by_account[self.account_revenue.id], -300.0, places=2)
        self.assertAlmostEqual(by_account[self.account_expense.id], 50.0, places=2)

    def test_partner_filter(self):
        rows = (
            MoveLineQuery(self.env, company_ids=[self.company.id])
            .select_balance_sum()
            .where_partners([self.partner_a.id])
            .execute()
        )
        self.assertEqual(len(rows), 1)
        # Partner A: revenue -100 + expense 50 = -50.
        self.assertAlmostEqual(rows[0]['balance'], -50.0, places=2)

    def test_analytic_filter_matches_cross_plan_composite_key(self):
        plan_a = self.env['account.analytic.plan'].create({
            'name': 'SQL Builder Plan A',
        })
        plan_b = self.env['account.analytic.plan'].create({
            'name': 'SQL Builder Plan B',
        })
        analytic_a = self.env['account.analytic.account'].create({
            'name': 'SQL Builder Analytic A',
            'plan_id': plan_a.id,
        })
        analytic_b = self.env['account.analytic.account'].create({
            'name': 'SQL Builder Analytic B',
            'plan_id': plan_b.id,
        })
        composite_key = f'{analytic_a.id},{analytic_b.id}'
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'date': '2026-08-01',
            'line_ids': [
                (0, 0, {
                    'name': 'Composite analytic expense',
                    'account_id': self.account_expense.id,
                    'debit': 80.0,
                    'analytic_distribution': {
                        (
                            composite_key
                            if odoo.release.version_info[0] >= 17
                            else str(analytic_a.id)
                        ): 25.0,
                    },
                }),
                (0, 0, {
                    'name': 'Composite analytic cash',
                    'account_id': self.account_cash.id,
                    'credit': 80.0,
                }),
            ],
        })
        move.action_post()
        if odoo.release.version_info[0] == 16:
            analytic_line = move.line_ids.filtered(
                lambda line: line.account_id == self.account_expense,
            )
            self.env.cr.execute(
                "UPDATE account_move_line "
                "SET analytic_distribution = jsonb_build_object(%s, %s) "
                "WHERE id = %s",
                [composite_key, 25.0, analytic_line.id],
            )

        for analytic in (analytic_a, analytic_b):
            rows = (
                MoveLineQuery(self.env, company_ids=[self.company.id])
                .select_balance_sum()
                .where_date_range('2026-08-01', '2026-08-01')
                .where_accounts([self.account_expense.id])
                .where_analytic_accounts([analytic.id])
                .execute()
            )
            self.assertEqual(len(rows), 1)
            # The line allocates 25% to this cross-plan combination.  A
            # filtered report must show its allocated 20, not gross 80.
            self.assertAlmostEqual(rows[0]['balance'], 20.0, places=2)

        composite_intersection = (
            MoveLineQuery(self.env, company_ids=[self.company.id])
            .select_balance_sum()
            .where_date_range('2026-08-01', '2026-08-01')
            .where_accounts([self.account_expense.id])
            .where_analytic_accounts([analytic_a.id])
            .where_analytic_column_accounts([analytic_b.id])
            .execute()
        )
        # Composite A+B key matches both predicates but contributes its 25%
        # allocation once, never once per matching account token.
        self.assertAlmostEqual(
            composite_intersection[0]['balance'], 20.0, places=2,
        )

    def test_analytic_filter_applies_split_distribution_percentage(self):
        plan = self.env['account.analytic.plan'].create({
            'name': 'SQL Builder Split Plan',
        })
        analytic_a = self.env['account.analytic.account'].create({
            'name': 'SQL Builder Split A',
            'plan_id': plan.id,
        })
        analytic_b = self.env['account.analytic.account'].create({
            'name': 'SQL Builder Split B',
            'plan_id': plan.id,
        })
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'date': '2026-08-02',
            'line_ids': [
                (0, 0, {
                    'name': 'Split analytic expense',
                    'account_id': self.account_expense.id,
                    'debit': 100.0,
                    'analytic_distribution': {
                        str(analytic_a.id): 60.0,
                        str(analytic_b.id): 40.0,
                    },
                }),
                (0, 0, {
                    'name': 'Split analytic cash',
                    'account_id': self.account_cash.id,
                    'credit': 100.0,
                }),
            ],
        })
        move.action_post()

        def allocated(analytic):
            rows = (
                MoveLineQuery(self.env, company_ids=[self.company.id])
                .select_balance_sum()
                .where_date_range('2026-08-02', '2026-08-02')
                .where_accounts([self.account_expense.id])
                .where_analytic_accounts([analytic.id])
                .execute()
            )
            return rows[0]['balance']

        self.assertAlmostEqual(allocated(analytic_a), 60.0, places=2)
        self.assertAlmostEqual(allocated(analytic_b), 40.0, places=2)
        both = (
            MoveLineQuery(self.env, company_ids=[self.company.id])
            .select_balance_sum()
            .where_date_range('2026-08-02', '2026-08-02')
            .where_accounts([self.account_expense.id])
            .where_analytic_accounts([analytic_a.id, analytic_b.id])
            .execute()
        )
        self.assertAlmostEqual(both[0]['balance'], 100.0, places=2)

        intersection = (
            MoveLineQuery(self.env, company_ids=[self.company.id])
            .select_balance_sum()
            .where_date_range('2026-08-02', '2026-08-02')
            .where_accounts([self.account_expense.id])
            .where_analytic_accounts([analytic_a.id, analytic_b.id])
            .where_analytic_column_accounts([analytic_a.id])
            .execute()
        )
        self.assertAlmostEqual(
            intersection[0]['balance'], 60.0, places=2,
        )

        # Unallocated activity belongs to independently queried Total but not
        # any analytic slice.  This proves Total cannot be sum(group columns).
        unallocated = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'date': '2026-08-02',
            'line_ids': [
                (0, 0, {
                    'name': 'Unallocated expense',
                    'account_id': self.account_expense.id,
                    'debit': 50.0,
                }),
                (0, 0, {
                    'name': 'Unallocated cash',
                    'account_id': self.account_cash.id,
                    'credit': 50.0,
                }),
            ],
        })
        unallocated.action_post()
        analytic_slice = (
            MoveLineQuery(self.env, company_ids=[self.company.id])
            .select_balance_sum()
            .where_date_range('2026-08-02', '2026-08-02')
            .where_accounts([self.account_expense.id])
            .where_analytic_column_accounts([analytic_a.id])
            .execute()
        )
        independent_total = (
            MoveLineQuery(self.env, company_ids=[self.company.id])
            .select_balance_sum()
            .where_date_range('2026-08-02', '2026-08-02')
            .where_accounts([self.account_expense.id])
            .execute()
        )
        self.assertAlmostEqual(
            analytic_slice[0]['balance'], 60.0, places=2,
        )
        self.assertAlmostEqual(
            independent_total[0]['balance'], 150.0, places=2,
        )

    def test_cash_basis_groups_multiline_invoice_in_sql_with_analytics(self):
        plan = self.env['account.analytic.plan'].create({
            'name': 'Cash Basis SQL Plan',
        })
        analytic_a = self.env['account.analytic.account'].create({
            'name': 'Cash Basis SQL A',
            'plan_id': plan.id,
        })
        analytic_b = self.env['account.analytic.account'].create({
            'name': 'Cash Basis SQL B',
            'plan_id': plan.id,
        })
        invoice = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'date': '2026-01-10',
            'line_ids': [
                (0, 0, {
                    'name': 'Cash-basis receivable',
                    'account_id': self.account_receivable.id,
                    'partner_id': self.partner_a.id,
                    'debit': 200.0,
                }),
                (0, 0, {
                    'name': 'Cash-basis split revenue',
                    'account_id': self.account_revenue.id,
                    'credit': 100.0,
                    'analytic_distribution': {
                        str(analytic_a.id): 60.0,
                        str(analytic_b.id): 40.0,
                    },
                }),
                (0, 0, {
                    'name': 'Cash-basis full revenue',
                    'account_id': self.account_revenue.id,
                    'credit': 100.0,
                    'analytic_distribution': {str(analytic_a.id): 100.0},
                }),
            ],
        })
        invoice.action_post()
        payment = self.post_balanced_move([
            {'account': self.account_cash, 'debit': 80.0},
            {
                'account': self.account_receivable,
                'partner': self.partner_a,
                'credit': 80.0,
            },
        ], date=odoo.fields.Date.from_string('2026-02-10'))
        (invoice.line_ids | payment.line_ids).filtered(
            lambda line: line.account_id == self.account_receivable
        ).reconcile()

        handler = self.env['eh.account.dynamic.report.handler.sectioned']
        rows = handler._cash_basis_grouped_totals(
            account_types=['income'],
            company_ids=[self.company.id],
            date_from=odoo.fields.Date.from_string('2026-02-01'),
            date_to=odoo.fields.Date.from_string('2026-02-28'),
            posted_only=True,
            options={'analytic_account_ids': [analytic_a.id]},
            sign=-1,
        )

        self.assertEqual(len(rows), 1)
        # Paid fraction 80/200.  Analytic A owns 60 + 100 of revenue.
        self.assertAlmostEqual(rows[0]['amount'], 64.0, places=2)

    def test_analytic_filter_ignores_legacy_non_object_json(self):
        plan = self.env['account.analytic.plan'].create({
            'name': 'Malformed Distribution Plan',
        })
        analytic = self.env['account.analytic.account'].create({
            'name': 'Malformed Distribution Analytic',
            'plan_id': plan.id,
        })
        query = (
            MoveLineQuery(self.env, company_ids=[self.company.id])
            .select_count()
            .where_analytic_accounts([analytic.id])
            .build()
        )
        # Supported Odoo series reject new non-object distributions through
        # a core SQL constraint.  A narrow CTE shadows account_move_line so
        # the generated production query can still prove it safely ignores a
        # legacy array without weakening that authoritative constraint.
        wrapped = SQL(
            "WITH account_move_line(id, move_id, company_id, balance, "
            "analytic_distribution) AS ("
            "VALUES (%s, %s, %s, %s, jsonb_build_array(%s::text))"
            ") %s",
            -1,
            self.move_c.id,
            self.company.id,
            50.0,
            str(analytic.id),
            query,
        )
        # Odoo 16 cursors predate direct SQL-object execution.
        self.env.cr.execute(wrapped.code, wrapped.params)
        rows = self.env.cr.dictfetchall()

        self.assertEqual(rows, [{'line_count': 0}])

    def test_account_codes_prefix_filter(self):
        rows = (
            MoveLineQuery(self.env, company_ids=[self.company.id])
            .select_balance_sum()
            .where_account_codes(['1'])  # cash account 1000 only
            .execute()
        )
        self.assertEqual(len(rows), 1)
        # Cash: 100 + 200 - 50 = 250.
        self.assertAlmostEqual(rows[0]['balance'], 250.0, places=2)

    def test_branch_account_code_uses_root_company_storage_key(self):
        if 'code_store' not in self.env['account.account']._fields:
            self.skipTest("Account code is not root-keyed on this series.")
        branch = self.env['res.company'].create({
            'name': 'SQL Builder Branch',
            'parent_id': self.company.id,
        })
        accounts = self.account_expense | self.account_revenue
        accounts.write({'company_ids': [(4, branch.id)]})
        branch_env = self.env['account.move'].with_context(
            allowed_company_ids=[self.company.id, branch.id],
        ).with_company(branch).env
        journal = self._ensure_journal(
            branch_env, branch, 'general', 'SQLB', 'SQL Branch Journal',
        )
        move = branch_env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': '2026-01-15',
            'line_ids': [
                (0, 0, {
                    'name': 'Branch expense',
                    'account_id': self.account_expense.id,
                    'debit': 25.0,
                }),
                (0, 0, {
                    'name': 'Branch revenue',
                    'account_id': self.account_revenue.id,
                    'credit': 25.0,
                }),
            ],
        })
        move.action_post()
        rows = (
            MoveLineQuery(branch_env, company_ids=[branch.id])
            .select_balance_sum()
            .where_account_codes([
                self.account_expense.with_company(branch).code,
            ])
            .execute()
        )
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]['balance'], 25.0, places=2)

    def test_cancelled_moves_excluded_by_default(self):
        # Cancel one move and ensure it disappears from the aggregation.
        self.move_b.button_cancel()
        rows = (
            MoveLineQuery(self.env, company_ids=[self.company.id])
            .select_balance_sum()
            .where_accounts([self.account_revenue.id])
            .execute()
        )
        # Only move A's revenue should remain: -100.
        self.assertAlmostEqual(rows[0]['balance'], -100.0, places=2)

    def test_count_lines(self):
        rows = (
            MoveLineQuery(self.env, company_ids=[self.company.id])
            .select_count()
            .where_account_types(['income'])
            .execute()
        )
        self.assertEqual(rows[0]['line_count'], 2)

    def test_shared_fixture_populates_only_missing_journal_default(self):
        self.journal_purchase.default_account_id = False

        journal = self._ensure_journal(
            self.env,
            self.company,
            'purchase',
            'BILL',
            'Vendor Bills',
            default_account=self.account_expense,
        )

        self.assertEqual(journal, self.journal_purchase)
        self.assertEqual(journal.default_account_id, self.account_expense)

        configured_account = self._ensure_account(
            self.env, '5001', 'Configured Purchase Default', 'expense',
        )
        journal.default_account_id = configured_account
        self._ensure_journal(
            self.env,
            self.company,
            'purchase',
            'BILL',
            'Vendor Bills',
            default_account=self.account_expense,
        )
        self.assertEqual(journal.default_account_id, configured_account)

    def test_shared_fixture_removes_ambient_account_groups(self):
        root_company = (
            self.company.root_id
            if 'root_id' in self.company._fields
            else self.company
        )
        ambient_group = self.env['account.group'].create({
            'name': 'Ambient Upgrade Group',
            'code_prefix_start': '98',
            'code_prefix_end': '98',
            'company_id': root_company.id,
        })

        self._isolate_account_groups(self.env, self.company)

        self.assertFalse(ambient_group.exists())
