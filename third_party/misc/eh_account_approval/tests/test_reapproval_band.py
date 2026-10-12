# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Re-approval band-crossing regression tests.

A vendor-bill policy has two amount bands:

* Rule A (0 - 10,000): one step, AP Clerk / manager group.
* Rule B (10,000+):     two steps, manager THEN director.

A bill approved under the weaker Rule A whose amount is later raised into
Rule B's band must NOT stay approved under Rule A. Two independent
protections are exercised:

1. The server-side re-approval reset re-derives rule_id for the new
   amount, so a material increase across the band boundary switches the
   request to the stronger two-step rule (and a single clerk can no
   longer re-approve it).
2. Any amount-band crossing resets immediately even when the value change is
   below the materiality threshold, so the request always has a recoverable
   path through the correct current approval chain.
"""

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.eh_account_base.tests.common import (
    EhAccountIntegrationTestCase,
)


@tagged('eh_account_approval', 'integration', 'post_install', '-at_install')
class TestReApprovalBand(EhAccountIntegrationTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Policy = cls.env['eh.approval.policy']
        cls.Move = cls.env['account.move']

        cls.expense_account = cls.env['account.account'].search(
            [('account_type', '=', 'expense'),
             ('company_ids', 'in', cls.env.company.ids)],
            limit=1,
        )
        if not cls.expense_account:
            cls.expense_account = cls.env['account.account'].create({
                'code': '5501',
                'name': 'Band Test Expense',
                'account_type': 'expense',
                'company_ids': [(6, 0, cls.env.company.ids)],
            })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Band test vendor',
        })

        cls.group_manager = cls.env.ref('eh_account_base.group_eh_manager')
        cls.group_director = cls.env['res.groups'].create({
            'name': 'EH Band Test Director',
        })

        # Two-band policy. Rule A is weaker (one step); Rule B is the
        # stronger chain (two steps) that any amount at or above 10,000
        # must reach. threshold_pct is deliberately high (50%) so a small
        # band crossing (9,500 -> 10,400) stays UNDER the material-change
        # floor - that is the case the post-time gate has to catch.
        cls.policy = cls.Policy.create({
            'name': 'Band vendor bills',
            'document_type': 'in_invoice',
            'company_id': cls.env.company.id,
            'sequence': 5,
            're_approval_threshold_pct': 50.0,
            're_approval_threshold_abs': 0.0,
            'rule_ids': [
                (0, 0, {
                    'name': 'Rule A - low band',
                    'sequence': 10,
                    'min_amount': 0.0,
                    'max_amount': 10000.0,
                    'step_ids': [
                        (0, 0, {'group_id': cls.group_manager.id,
                                'sequence': 10}),
                    ],
                }),
                (0, 0, {
                    'name': 'Rule B - high band',
                    'sequence': 20,
                    'min_amount': 10000.0,
                    'max_amount': 0.0,
                    'step_ids': [
                        (0, 0, {'group_id': cls.group_manager.id,
                                'sequence': 10}),
                        (0, 0, {'group_id': cls.group_director.id,
                                'sequence': 20}),
                    ],
                }),
            ],
        })
        cls.rule_a = cls.policy.rule_ids.filtered(
            lambda r: r.sequence == 10)
        cls.rule_b = cls.policy.rule_ids.filtered(
            lambda r: r.sequence == 20)

        cls.user_manager = cls.env['res.users'].create({
            'name': 'Band Manager Test',
            'login': 'band_mgr@test', 'email': 'band_mgr@test',
            'group_ids': [(6, 0, [cls.group_manager.id])],
        })
        cls.user_director = cls.env['res.users'].create({
            'name': 'Band Director Test',
            'login': 'band_dir@test', 'email': 'band_dir@test',
            'group_ids': [(6, 0, [
                cls.group_director.id,
                cls.group_manager.id,
            ])],
        })
        # The current test user needs the manager group to create bills.
        cls.env.user.group_ids |= cls.group_manager

    def _make_bill(self, amount):
        return self.Move.create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2026-04-15',
            'invoice_line_ids': [(0, 0, {
                'name': 'Band purchase',
                'quantity': 1,
                'price_unit': amount,
                'account_id': self.expense_account.id,
            })],
        })

    def _raise_amount(self, bill, amount):
        """Raise the bill's amount through a move-level write so the
        write-path re-approval guard fires durably (a line-level price
        edit only surfaces at post time and rolls back when the post
        raises)."""
        bill.write({
            'invoice_line_ids': [
                (1, bill.invoice_line_ids[0].id, {'price_unit': amount}),
            ],
        })

    def _approve_rule_a(self, bill):
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        self.assertEqual(request.rule_id, self.rule_a)
        self.assertEqual(request.total_steps, 1)
        request.with_user(self.user_manager).action_approve(comment="A ok")
        request.invalidate_recordset()
        self.assertEqual(request.state, 'approved')
        return request

    # ---- Fix 1: reset re-selects the stronger rule ----

    def test_material_band_crossing_reset_reselects_stronger_rule(self):
        """A material increase across the band boundary must switch the
        reset request to the higher band's (two-step) rule; the stale
        one-step rule must not survive the reset."""
        bill = self._make_bill(9000.0)
        request = self._approve_rule_a(bill)

        # 9,000 -> 50,000 is a 455% jump, well above the 50% threshold,
        # so the write-path guard resets the approval.
        self._raise_amount(bill, 50000.0)
        request.invalidate_recordset()

        self.assertEqual(
            request.state, 'in_review',
            "Material change must reset the approval to in_review.")
        self.assertEqual(request.current_step, 0)
        self.assertEqual(
            request.rule_id, self.rule_b,
            "Reset must re-derive the rule for the NEW amount (Rule B), "
            "not keep the stale lower-band Rule A.")
        self.assertEqual(
            request.total_steps, 2,
            "total_steps must follow the re-selected Rule B (two steps).")

    def test_single_clerk_cannot_re_approve_higher_band_after_reset(self):
        """The exploit: after raising the bill into the two-step band, a
        single manager sign-off must NOT be enough - the director step is
        now required and posting stays blocked until it is signed."""
        bill = self._make_bill(9000.0)
        request = self._approve_rule_a(bill)
        self._raise_amount(bill, 50000.0)
        request.invalidate_recordset()
        self.assertEqual(request.rule_id, self.rule_b)

        # A single manager approval clears step 0 only.
        request.with_user(self.user_manager).action_approve(comment="mgr")
        request.invalidate_recordset()
        self.assertEqual(
            request.state, 'in_review',
            "One manager sign-off must not approve the two-step request.")
        self.assertEqual(request.current_step, 1)
        with self.assertRaises(UserError):
            bill.action_post()

        # The director completes the stronger chain; only then may it post.
        request.with_user(self.user_director).action_approve(comment="dir")
        request.invalidate_recordset()
        self.assertEqual(request.state, 'approved')
        bill.action_post()
        self.assertEqual(bill.state, 'posted')

    # ---- Fix 2: subthreshold band crossing remains recoverable ----

    def test_subthreshold_band_crossing_resets_to_current_rule(self):
        """A band crossing that stays below the material-change threshold
        must still reset to the current rule; blocking without a reset leaves
        an approved request with no sanctioned recovery path."""
        bill = self._make_bill(9500.0)
        request = self._approve_rule_a(bill)

        # 9,500 -> 10,400 is a 9.47% change, under the 50% materiality
        # threshold, but it crosses from Rule A to stronger Rule B.
        self._raise_amount(bill, 10400.0)
        request.invalidate_recordset()
        self.assertEqual(
            request.state, 'in_review',
            "Every band crossing must reset the request.")
        self.assertEqual(
            request.rule_id, self.rule_b,
            "Reset must point at current Rule B.")
        self.assertEqual(request.current_step, 0)
        self.assertEqual(request.total_steps, 2)
        with self.assertRaises(UserError):
            bill.action_post()
        self.assertNotEqual(bill.state, 'posted')

    def test_same_band_change_still_posts(self):
        """A change that stays within the SAME band must not be blocked by
        the new rule-equality gate: the approved rule still matches."""
        bill = self._make_bill(3000.0)
        request = self._approve_rule_a(bill)
        # 3,000 -> 3,100: same Rule A band, sub-threshold, no reset.
        self._raise_amount(bill, 3100.0)
        request.invalidate_recordset()
        self.assertEqual(request.state, 'approved')
        self.assertEqual(request.rule_id, self.rule_a)
        bill.action_post()
        self.assertEqual(bill.state, 'posted')
