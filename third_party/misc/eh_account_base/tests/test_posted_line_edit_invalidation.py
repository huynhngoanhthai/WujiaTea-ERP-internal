# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Integration tests for reporting cache invalidation when a POSTED move has a
financially-material line edited in an unlocked period.

A posted move can still have its lines edited while the period is unlocked.
Such an edit changes report figures but performs no state transition, so the
state-only version hook would leave the reporting cache serving a stale
payload. These tests assert the line write() hook bumps eh_move_version (and
thus the report freshness key) when, and only when, a material field
(account, amount, or date) changes on a posted move's line.
"""

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import EhAccountIntegrationTestCase


@tagged('eh_account_base', 'integration', 'post_install', '-at_install')
class TestPostedLineEditInvalidation(EhAccountIntegrationTestCase):

    def _post_move(self):
        return self.post_balanced_move([
            {'account': self.account_revenue, 'credit': 100.0},
            {'account': self.account_cash, 'debit': 100.0},
        ])

    def _current_version(self):
        self.company.invalidate_recordset(['eh_move_version'])
        return self.company.eh_move_version

    def test_account_change_bumps_version(self):
        move = self._post_move()
        baseline = self._current_version()

        # Re-point the credit line to a different account. This is a
        # balance-preserving, financially-material edit on a posted move.
        credit_line = move.line_ids.filtered(lambda l: l.credit > 0)
        credit_line.write({'account_id': self.account_equity.id})

        self.assertGreater(
            self._current_version(),
            baseline,
            "Changing the account of a posted move line must bump "
            "eh_move_version so the report cache invalidates",
        )

    def test_amount_fields_are_material(self):
        # The framework blocks direct amount edits on the lines of a posted
        # move (line_ids is readonly, and a lone leg write unbalances the
        # entry), so an amount change reaches the suite only through the same
        # account.move.line.write() hook that the account/date tests exercise
        # end to end. Assert the amount fields are in the material set that
        # the hook keys on, so an amount edit that does land (for example a
        # balanced two-leg swap) invalidates the cache.
        from odoo.addons.eh_account_base.models.account_move import (
            _EH_MATERIAL_LINE_FIELDS,
        )
        for fname in (
            'debit', 'credit', 'balance', 'amount_currency',
            'tax_base_amount', 'amount_residual',
            'amount_residual_currency', 'reconciled',
            'price_subtotal', 'price_total', 'product_uom_id',
            'is_storno', 'deductible_amount', 'tax_tag_ids',
            'tax_line_id', 'group_tax_id', 'tax_group_id',
            'extra_tax_data',
        ):
            self.assertIn(
                fname, _EH_MATERIAL_LINE_FIELDS,
                "Amount field %s must be treated as cache-material" % fname,
            )

    def test_move_stored_outputs_are_cache_material(self):
        from odoo.addons.eh_account_base.models.account_move import (
            _EH_MATERIAL_MOVE_FIELDS,
        )
        for fname in (
            'amount_untaxed', 'amount_tax', 'amount_total',
            'amount_residual', 'amount_untaxed_signed',
            'amount_untaxed_in_currency_signed', 'amount_tax_signed',
            'amount_total_signed', 'amount_total_in_currency_signed',
            'amount_residual_signed', 'payment_state',
            'origin_payment_id', 'payment_id', 'statement_line_id',
        ):
            self.assertIn(
                fname, _EH_MATERIAL_MOVE_FIELDS,
                "Stored move output %s must invalidate report caches" % fname,
            )

    def test_date_change_bumps_version(self):
        move = self._post_move()
        baseline = self._current_version()

        line = move.line_ids[0]
        with self.assertRaises(AccessError):
            line.write({'date': fields.Date.to_date('2020-01-15')})
        with self.assertRaises(UserError):
            move.write({'date': fields.Date.to_date('2020-01-15')})
        alternate_day = 1 if move.date.day != 1 else 2
        move.with_context(skip_readonly_check=True).write({
            'date': move.date.replace(day=alternate_day),
        })

        self.assertGreater(
            self._current_version(),
            baseline,
            "Changing a posted move's authoritative date must bump "
            "eh_move_version",
        )

    def test_freshness_key_changes_for_report_cache(self):
        # The reporting cache uses sum(eh_move_version) across the reported
        # companies as its freshness key. Assert an in-place posted line edit
        # actually moves that key, which is what invalidates find_cached().
        move = self._post_move()
        company_recs = self.company
        company_recs.invalidate_recordset(['eh_move_version'])
        key_before = sum(company_recs.mapped('eh_move_version'))

        credit_line = move.line_ids.filtered(lambda l: l.credit > 0)
        credit_line.write({'account_id': self.account_equity.id})

        company_recs.invalidate_recordset(['eh_move_version'])
        key_after = sum(company_recs.mapped('eh_move_version'))
        self.assertNotEqual(
            key_before, key_after,
            "The report freshness key must change after a posted line edit",
        )

    def test_add_line_to_posted_move_bumps_version(self):
        # Adding a line to an already-posted move (unlocked period) changes
        # report figures with no state transition. The create() hook must bump
        # the version. The move.line_ids one2many is readonly on a posted
        # move, so real code paths that add lines create them directly against
        # the model (with move_id set); exercise that path here. Add a
        # balanced pair of legs so the entry stays balanced by construction
        # (10 debit + 10 credit == 0 net).
        move = self._post_move()
        baseline = self._current_version()

        self.env['account.move.line'].create([
            {'move_id': move.id, 'account_id': self.account_revenue.id,
             'credit': 10.0, 'name': 'extra-credit'},
            {'move_id': move.id, 'account_id': self.account_cash.id,
             'debit': 10.0, 'name': 'extra-debit'},
        ])

        self.assertGreater(
            self._current_version(),
            baseline,
            "Adding a line to a posted move must bump eh_move_version so "
            "the report cache invalidates",
        )

    def test_remove_line_from_posted_move_bumps_version(self):
        # Removing a line from an already-posted move changes report figures
        # with no state transition. The unlink() hook must bump the version.
        # First add a balanced pair directly against the model so the move
        # stays balanced after we drop that same pair back out.
        move = self._post_move()
        extra = self.env['account.move.line'].create([
            {'move_id': move.id, 'account_id': self.account_revenue.id,
             'credit': 10.0, 'name': 'extra-credit'},
            {'move_id': move.id, 'account_id': self.account_cash.id,
             'debit': 10.0, 'name': 'extra-debit'},
        ])
        baseline = self._current_version()

        # The base account model guards a bare unlink of a posted line; the
        # internal recompute paths that regenerate a posted move's lines reach
        # the real delete via the force_delete context flag, which is the path
        # a line removal on a posted move takes in practice. Exercise that same
        # path so the unlink() hook fires.
        extra.with_context(force_delete=True, dynamic_unlink=True).unlink()

        self.assertGreater(
            self._current_version(),
            baseline,
            "Removing a line from a posted move must bump eh_move_version so "
            "the report cache invalidates",
        )

    def test_add_line_to_draft_move_does_not_bump(self):
        # Building up a draft entry before action_post must not bump the
        # counter: draft moves are excluded from published reports.
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'date': fields.Date.today(),
            'line_ids': [
                (0, 0, {'account_id': self.account_revenue.id,
                        'credit': 20.0, 'name': '/'}),
                (0, 0, {'account_id': self.account_cash.id,
                        'debit': 20.0, 'name': '/'}),
            ],
        })
        self.assertEqual(move.state, 'draft')
        baseline = self._current_version()

        move.write({'line_ids': [
            (0, 0, {'account_id': self.account_revenue.id,
                    'credit': 5.0, 'name': '/'}),
            (0, 0, {'account_id': self.account_cash.id,
                    'debit': 5.0, 'name': '/'}),
        ]})

        self.assertEqual(
            self._current_version(),
            baseline,
            "Adding a line to a draft move must not bump eh_move_version",
        )

    def test_report_visible_line_label_write_bumps(self):
        move = self._post_move()
        baseline = self._current_version()

        # General Ledger/Partner Ledger render the line label.
        move.line_ids[0].write({'name': 'Reworded label'})

        self.assertGreater(
            self._current_version(),
            baseline,
            "A report-visible line label must invalidate cached payloads",
        )

    def test_unrelated_line_write_does_not_bump(self):
        move = self._post_move()
        baseline = self._current_version()
        move.line_ids[0].write({'sequence': 999})
        self.assertEqual(self._current_version(), baseline)

    def test_draft_move_line_write_does_not_bump(self):
        # Draft moves are excluded from published reports, so editing a draft
        # move's lines must not bump the counter.
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'date': fields.Date.today(),
            'line_ids': [
                (0, 0, {'account_id': self.account_revenue.id,
                        'credit': 20.0, 'name': '/'}),
                (0, 0, {'account_id': self.account_cash.id,
                        'debit': 20.0, 'name': '/'}),
            ],
        })
        self.assertEqual(move.state, 'draft')
        baseline = self._current_version()

        # Draft moves allow line_ids edits; change both legs so the entry
        # stays balanced (30 == 30). The move is draft, so no bump.
        credit_line = move.line_ids.filtered(lambda l: l.credit > 0)
        debit_line = move.line_ids.filtered(lambda l: l.debit > 0)
        move.write({'line_ids': [
            (1, credit_line.id, {'credit': 30.0}),
            (1, debit_line.id, {'debit': 30.0}),
        ]})

        self.assertEqual(
            self._current_version(),
            baseline,
            "Editing a draft move line must not bump eh_move_version",
        )
