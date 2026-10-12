# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Performance scaffolding for MoveLineQuery.

These are NOT functional tests. They run as part of the perf suite and gate
on regression thresholds. The thresholds are intentionally generous for
Phase 1 week 1; we tighten them as the engine matures.

To run only the perf suite:

    odoo --test-tags eh_account_base,perf -i eh_account_base

To run the heavy variants (post_install required to ensure demo data is loaded):

    odoo --test-tags eh_account_base,perf,heavy -i eh_account_base

Heavy tests are gated on env var EH_RUN_HEAVY_PERF=1 to keep CI fast by
default.
"""

import os
import time

from odoo.tests import tagged

from odoo.addons.eh_account_base.tools.sql_builder import MoveLineQuery
from .common import EhAccountIntegrationTestCase


# Thresholds (milliseconds). Tune as the engine matures.
THRESHOLD_BUILD_MS = 5
THRESHOLD_EXECUTE_TRIVIAL_MS = 100
THRESHOLD_EXECUTE_GROUPED_MS = 500


@tagged('eh_account_base', 'perf', 'post_install', '-at_install')
class TestSqlBuilderPerfBaseline(EhAccountIntegrationTestCase):
    """Perf baselines on the small seed fixture.

    These exist to:

    1. Confirm the build path is microseconds even for moderately complex
       queries (compose 5 filters, 3 selects, group by 2 fields).
    2. Establish a CI gate at the "trivial small fixture" level so the engine
       does not silently regress into ORM bound paths.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Seed enough lines for a meaningful aggregate without slowing CI.
        for n in range(50):
            cls.post_balanced_move([
                {'account': cls.account_revenue, 'credit': 1.0,
                 'partner': cls.partner_a if n % 2 == 0 else cls.partner_b},
                {'account': cls.account_cash, 'debit': 1.0},
            ])

    def _measure_ms(self, fn):
        start = time.perf_counter()
        result = fn()
        elapsed_ms = (time.perf_counter() - start) * 1000
        return elapsed_ms, result

    def test_build_is_fast(self):
        def build_complex_query():
            return (
                MoveLineQuery(self.env, company_ids=[self.company.id])
                .select_field('account_id')
                .select_field('partner_id')
                .select_balance_sum()
                .select_count()
                .where_date_range('2026-01-01', '2026-12-31')
                .where_account_types(['income', 'expense'])
                .where_account_codes(['1', '4', '5'])
                .where_posted_only()
                .group_by('account_id', 'partner_id')
                .order_by('account_id', 'ASC')
                .limit(100)
                .build()
            )

        # Warm up.
        build_complex_query()
        elapsed, _ = self._measure_ms(build_complex_query)
        self.assertLess(
            elapsed, THRESHOLD_BUILD_MS,
            f"build() took {elapsed:.2f}ms; threshold {THRESHOLD_BUILD_MS}ms",
        )

    def test_execute_trivial_aggregation_under_threshold(self):
        def run():
            return (
                MoveLineQuery(self.env, company_ids=[self.company.id])
                .select_balance_sum()
                .where_account_types(['income'])
                .execute()
            )

        # Warm up the cursor.
        run()
        elapsed, rows = self._measure_ms(run)
        self.assertEqual(len(rows), 1)
        self.assertLess(
            elapsed, THRESHOLD_EXECUTE_TRIVIAL_MS,
            f"trivial execute() took {elapsed:.2f}ms; "
            f"threshold {THRESHOLD_EXECUTE_TRIVIAL_MS}ms",
        )

    def test_execute_grouped_aggregation_under_threshold(self):
        def run():
            return (
                MoveLineQuery(self.env, company_ids=[self.company.id])
                .select_field('account_id')
                .select_field('partner_id')
                .select_balance_sum()
                .where_account_types(['income', 'expense'])
                .group_by('account_id', 'partner_id')
                .execute()
            )

        run()
        elapsed, _ = self._measure_ms(run)
        self.assertLess(
            elapsed, THRESHOLD_EXECUTE_GROUPED_MS,
            f"grouped execute() took {elapsed:.2f}ms; "
            f"threshold {THRESHOLD_EXECUTE_GROUPED_MS}ms",
        )


@tagged('eh_account_base', 'perf', 'heavy', 'post_install', '-at_install')
class TestSqlBuilderPerfHeavy(EhAccountIntegrationTestCase):
    """Heavy perf tests. Skipped unless EH_RUN_HEAVY_PERF=1.

    Phase 1 commitment: these exercise 100k journal lines and assert the
    grouped P&L style aggregation completes under 2 seconds. Tighter thresholds
    arrive in Phase 2 once the snapshot manager is wired in.
    """

    THRESHOLD_100K_PL_MS = 2000

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if os.environ.get('EH_RUN_HEAVY_PERF') != '1':
            cls.skipTest(cls, "Heavy perf disabled. Set EH_RUN_HEAVY_PERF=1 to run.")

        # Seed 100k lines via batched create. Pre validate batch size to keep
        # transaction memory bounded.
        BATCH = 1000
        for batch in range(100):  # 100 * BATCH * 2 lines = 200k aml rows
            move_vals = []
            for n in range(BATCH):
                move_vals.append({
                    'move_type': 'entry',
                    'journal_id': cls.journal_misc.id,
                    'date': '2026-01-15',
                    'line_ids': [
                        (0, 0, {
                            'account_id': cls.account_revenue.id,
                            'credit': 1.0,
                            'partner_id': cls.partner_a.id if n % 2 == 0 else cls.partner_b.id,
                        }),
                        (0, 0, {
                            'account_id': cls.account_cash.id,
                            'debit': 1.0,
                        }),
                    ],
                })
            moves = cls.env['account.move'].create(move_vals)
            moves.action_post()

    def test_pl_style_aggregation_100k_under_threshold(self):
        import time
        query = (
            MoveLineQuery(self.env, company_ids=[self.company.id])
            .select_field('account_id')
            .select_balance_sum()
            .where_account_types(['income', 'expense'])
            .where_posted_only()
            .group_by('account_id')
        )
        # Warm up.
        query.execute()
        start = time.perf_counter()
        rows = query.execute()
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertGreater(len(rows), 0)
        self.assertLess(
            elapsed_ms, self.THRESHOLD_100K_PL_MS,
            f"100k aggregation took {elapsed_ms:.2f}ms; "
            f"threshold {self.THRESHOLD_100K_PL_MS}ms",
        )
