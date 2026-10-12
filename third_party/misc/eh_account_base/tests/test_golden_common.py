# -*- encoding: utf-8 -*-
##############################################################################
# ERP Heritage - Copyright (C) 2026 (https://www.erpheritage.com.au/)
##############################################################################
"""Currency-precision regressions for shared golden assertions."""

from odoo.tests import tagged

from .golden_common import EhGoldenTestCase


@tagged('eh_account_base', 'integration', 'post_install', '-at_install')
class TestGoldenCommonPrecision(EhGoldenTestCase):

    def test_move_line_tolerance_uses_explicit_three_decimal_currency(self):
        move = self.post_balanced_move([
            {'account': self.account_expense, 'debit': 1.0},
            {'account': self.account_cash, 'credit': 1.0},
        ])
        kwd = self.env.ref('base.KWD')
        expected = [
            (self.account_expense, 1.0006, 0.0),
            (self.account_cash, 0.0, 1.0),
        ]

        with self.assertRaises(AssertionError):
            self.assertMoveLines(move, expected, currency=kwd)
        self.assertMoveLines(move, expected, tolerance=0.001)

    def test_move_line_tolerance_rejects_non_positive_override(self):
        move = self.post_balanced_move([
            {'account': self.account_expense, 'debit': 1.0},
            {'account': self.account_cash, 'credit': 1.0},
        ])
        with self.assertRaisesRegex(ValueError, 'must be positive'):
            self.assertMoveLines(move, [], tolerance=0)
