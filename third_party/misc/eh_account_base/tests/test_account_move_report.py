# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Render regression test for the branded Journal Entry PDF report.

The report (action ``eh_account_base.action_report_eh_account_move``,
template ``eh_account_base.report_eh_account_move``, model
``account.move``) has shipped rendering bugs twice, both caused by the
absence of a render test. This test drives the QWeb HTML render path
(no wkhtmltopdf dependency) against a real POSTED journal entry and
proves the template renders to non-empty HTML: a missing field, bad
attribute access, or template KeyError would surface here as a render
failure rather than as a broken print button in production.

There is no reliably stable title string in the rendered output across
Odoo series and localisations, so this asserts only on the render
mechanics: a non-empty ``html`` body and a ``ftype`` of ``'html'``.
"""

from odoo.tests import tagged

from .common import EhAccountIntegrationTestCase


@tagged('eh_account_base', 'integration', 'post_install', '-at_install')
class TestAccountMoveReportRender(EhAccountIntegrationTestCase):
    """Prove the Journal Entry report renders for a posted move."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A minimal, balanced, POSTED entry: one debit line and one credit
        # line, with a partner on the receivable leg so the template's
        # partner-facing branches are exercised.
        cls.move = cls.post_balanced_move([
            {
                'account': cls.account_receivable,
                'debit': 150.0,
                'partner': cls.partner_a,
                'name': 'Journal entry render test line',
            },
            {
                'account': cls.account_revenue,
                'credit': 150.0,
                'name': 'Journal entry render test counter-leg',
            },
        ])

    def test_journal_entry_report_renders(self):
        """The report renders to non-empty HTML for a posted move."""
        self.assertEqual(
            self.move.state, 'posted',
            'Fixture move must be posted before rendering the report.',
        )
        report = self.env.ref(
            'eh_account_base.action_report_eh_account_move')
        html, ftype = report._render_qweb_html(
            report.report_name, self.move.ids)
        self.assertEqual(ftype, 'html')
        # Non-empty HTML proves the template compiled and rendered without a
        # KeyError / attribute error / missing-field failure.
        self.assertTrue(html)
        template = self.env.ref('eh_account_base.report_eh_account_move')
        self.assertNotIn('%0.2f', template.arch_db)
        self.assertGreaterEqual(
            template.arch_db.count("'widget': 'monetary'"), 4,
        )
        self.assertIn('move.company_currency_id', template.arch_db)
        self.assertIn('Ledger', template.arch_db)
        self.assertIn('Document', template.arch_db)
        self.assertIn(
            'move.currency_id != move.company_currency_id',
            template.arch_db,
        )
        self.assertNotIn("strftime('%Y-%m-%d')", template.arch_db)
        self.assertIn("move._eh_selection_label('move_type')", template.arch_db)
        self.assertIn('move.inalterable_hash', template.arch_db)
        self.assertEqual(
            report.paperformat_id,
            self.env.ref('eh_account_base.paperformat_eh_portrait'),
        )

    def test_footer_sums_same_rounded_values_as_visible_rows(self):
        """Legacy half-minor data cannot make printed rows miss footer."""
        self.company.currency_id.write({'rounding': 0.01})
        move = self.post_balanced_move([
            {
                'account': self.account_receivable,
                'debit': 1.0,
                'partner': self.partner_a,
            },
            {'account': self.account_expense, 'debit': 1.0},
            {'account': self.account_revenue, 'credit': 2.0},
        ])
        debit_lines = move.line_ids.filtered('debit')
        credit_line = move.line_ids.filtered('credit').ensure_one()
        # Simulate legacy/direct-SQL values predating Monetary-field
        # normalisation. Each debit visibly rounds to 0.01, so footer must be
        # 0.02 rather than round(raw sum 0.01) to 0.01.
        self.env.cr.execute(
            "UPDATE account_move_line SET debit = %s, credit = 0, "
            "balance = %s WHERE id IN %s",
            (0.005, 0.005, tuple(debit_lines.ids)),
        )
        self.env.cr.execute(
            "UPDATE account_move_line SET debit = 0, credit = %s, "
            "balance = %s WHERE id = %s",
            (0.01, -0.01, credit_line.id),
        )
        move.line_ids.invalidate_recordset(['debit', 'credit', 'balance'])

        report = self.env.ref(
            'eh_account_base.action_report_eh_account_move',
        )
        html, ftype = report._render_qweb_html(
            report.report_name, move.ids,
        )

        self.assertEqual(ftype, 'html')
        rendered = html.decode() if isinstance(html, bytes) else html
        self.assertIn('0.02', rendered)
        template = self.env.ref('eh_account_base.report_eh_account_move')
        self.assertIn('total_debit + line_debit', template.arch_db)
        self.assertIn('total_credit + line_credit', template.arch_db)

    def test_analytic_names_percentages_and_seal_render_as_evidence(self):
        plan = self.env['account.analytic.plan'].create({
            'name': 'Journal Print Plan',
        })
        analytic = self.env['account.analytic.account'].create({
            'name': 'Journal Print Department',
            'plan_id': plan.id,
        })
        target = self.move.line_ids.filtered(
            lambda line: line.account_id == self.account_revenue,
        )
        target.write({
            'analytic_distribution': {str(analytic.id): 60.0},
        })
        self.move._eh_stamp_verified_seal()

        report = self.env.ref('eh_account_base.action_report_eh_account_move')
        html, ftype = report._render_qweb_html(
            report.report_name, self.move.ids,
        )
        rendered = html.decode() if isinstance(html, bytes) else html

        self.assertEqual(ftype, 'html')
        self.assertIn('Journal Print Department', rendered)
        self.assertIn('60%', rendered)
        self.assertIn('Verified EH seal', rendered)
        self.assertNotIn(
            '&gt;%s&lt;' % analytic.id,
            rendered,
        )

    def test_statutory_footer_has_company_identity_without_vendor_copy(self):
        footer = self.env.ref('eh_account_base.eh_report_footer')
        clean_layout = self.env.ref('eh_account_base.eh_clean_layout')
        combined = footer.arch_db + clean_layout.arch_db

        self.assertIn('company.display_name', combined)
        self.assertNotIn('Made with', combined)
        self.assertNotIn('Melbourne', combined)
