# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Golden-example test base for the IFRS 10/10 program.

A golden test encodes a worked example derived from the standard's own
illustrative material (numbers only, hand-recomputed) and asserts the exact
journal entry the engine posts. Passing the golden suite is the evidence line
behind any "IFRS-aligned" claim, so:

* every expected amount in a golden test must be derivable by hand from the
  inputs stated in the test, with the derivation in a comment;
* assertions are exact to the tested currency's rounding, never a fixed
  two-decimal tolerance and never assertGreater / assertTrue on magnitudes;
* no golden test may read an expected value back from the engine under test.

Property-style tests (seeded randomized trials with invariants) share this
base: use ``self.seeded_rng(n)`` so a failure reproduces from the case seed.
"""

import random

from odoo.addons.eh_account_base.tests.common import (
    EhAccountIntegrationTestCase,
)


class EhGoldenTestCase(EhAccountIntegrationTestCase):
    """Base for golden IFRS worked-example tests and property tests."""

    # ------------------------------------------------------------------
    # journal entry assertions
    # ------------------------------------------------------------------
    def assertMoveLines(
        self, move, expected, msg=None, currency=None, tolerance=None,
    ):
        """Assert a move's lines match exactly (account, debit, credit).

        ``expected`` is an iterable of (account_record_or_code, debit,
        credit). Order-insensitive; every expected line must match a distinct
        move line and no unexpected line may remain.
        """
        self.assertTrue(move, msg or 'expected a journal entry, got none')
        currency = currency or move.company_currency_id
        if tolerance is None:
            tolerance = float(currency.rounding) / 2.0
        tolerance = float(tolerance)
        if tolerance <= 0:
            raise ValueError('journal-line assertion tolerance must be positive')
        epsilon = max(tolerance * 1e-9, 1e-12)
        remaining = list(move.line_ids)
        misses = []
        for account, debit, credit in expected:
            code = account if isinstance(account, str) else account.code
            hit = None
            for line in remaining:
                if (line.account_id.code == code
                        and abs(line.debit - debit) <= tolerance + epsilon
                        and abs(line.credit - credit) <= tolerance + epsilon):
                    hit = line
                    break
            if hit is None:
                misses.append((code, debit, credit))
            else:
                remaining.remove(hit)
        detail = []
        if misses:
            detail.append('missing lines: %s' % misses)
        if remaining:
            detail.append('unexpected lines: %s' % [
                (l.account_id.code, l.debit, l.credit) for l in remaining])
        if detail:
            got = [(l.account_id.code, l.debit, l.credit)
                   for l in move.line_ids]
            self.fail('%s\nmove %s lines %s\n%s' % (
                msg or 'journal entry mismatch', move.display_name, got,
                '; '.join(detail)))

    def assertBalanced(self, move):
        self.assertAlmostEqual(
            sum(move.line_ids.mapped('debit')),
            sum(move.line_ids.mapped('credit')), places=2,
            msg='unbalanced entry %s' % move.display_name)

    def posted_balance(self, account, company=None):
        """Posted debit-minus-credit balance of an account."""
        domain = [('account_id', '=', account.id),
                  ('move_id.state', '=', 'posted')]
        if company is not None:
            domain.append(('company_id', '=', company.id))
        lines = self.env['account.move.line'].search(domain)
        return sum(lines.mapped('debit')) - sum(lines.mapped('credit'))

    # ------------------------------------------------------------------
    # fixtures
    # ------------------------------------------------------------------
    @classmethod
    def _set_rate(cls, currency, day, rate, company=None):
        """Pin an exchange rate (units of currency per 1 company currency)."""
        cls.env['res.currency.rate'].create({
            'currency_id': currency.id,
            'name': day,
            'rate': rate,
            'company_id': (company or cls.company).id,
        })
        if not currency.active:
            currency.sudo().active = True

    # ------------------------------------------------------------------
    # property-test support
    # ------------------------------------------------------------------
    def seeded_rng(self, seed):
        """Deterministic RNG per case so failures replay exactly."""
        return random.Random(seed)
