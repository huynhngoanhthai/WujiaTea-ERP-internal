# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Multi-approver depth tests: named approvers, N-of-M minimums, required
approvers, parallel mode, and force-approve.
"""

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.eh_account_base.tests.common import (
    EhAccountIntegrationTestCase,
)


@tagged('eh_account_approval', 'integration', 'post_install', '-at_install')
class TestMultiApprover(EhAccountIntegrationTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Policy = cls.env['eh.approval.policy']
        cls.Move = cls.env['account.move']
        cls.group_manager = cls.env.ref('eh_account_base.group_eh_manager')
        cls.group_eh_user = cls.env.ref('eh_account_base.group_eh_user')

        cls.expense_account = cls.env['account.account'].search(
            [('account_type', '=', 'expense'),
             ('company_ids', 'in', cls.env.company.ids)], limit=1)
        if not cls.expense_account:
            cls.expense_account = cls.env['account.account'].create({
                'code': '5599', 'name': 'MA Test Expense',
                'account_type': 'expense',
                'company_ids': [(6, 0, cls.env.company.ids)],
            })
        cls.partner = cls.env['res.partner'].create({'name': 'MA vendor'})

        def _user(login, groups):
            return cls.env['res.users'].create({
                'name': login, 'login': login, 'email': login,
                'group_ids': [(6, 0, [g.id for g in groups])],
            })

        # Two distinct approvers in the manager group, plus two named
        # approvers carrying only the base accounting-user access.
        cls.appr_a = _user('ma_a@test', [cls.group_manager])
        cls.appr_b = _user('ma_b@test', [cls.group_manager])
        cls.named_one = _user('ma_named1@test', [cls.group_eh_user])
        cls.named_two = _user('ma_named2@test', [cls.group_eh_user])
        # Requester is the current user; give it manager access for move
        # creation, and it must NOT count as an approver (self-approval).
        cls.env.user.group_ids |= cls.group_manager

    def _bill(self, amount=2000.0):
        return self.Move.create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2026-04-15',
            'invoice_line_ids': [(0, 0, {
                'name': 'x', 'quantity': 1, 'price_unit': amount,
                'account_id': self.expense_account.id,
            })],
        })

    def _policy(self, steps, mode='sequential'):
        return self.Policy.create({
            'name': 'MA policy', 'document_type': 'in_invoice',
            'company_id': self.env.company.id,
            'rule_ids': [(0, 0, {
                'name': 'any', 'sequence': 10,
                'min_amount': 100.0, 'max_amount': 0.0,
                'approval_mode': mode,
                'step_ids': steps,
            })],
        })

    def _request(self, policy):
        bill = self._bill()
        bill.action_eh_request_approval()
        return bill, bill.eh_active_approval_request_id

    # ---- N-of-M ----

    def test_n_of_m_needs_two_distinct_approvers(self):
        self._policy([(0, 0, {
            'sequence': 10, 'group_id': self.group_manager.id,
            'approval_minimum': 2,
        })])
        bill, req = self._request(self.Policy.search([], limit=1))
        req.with_user(self.appr_a).action_approve(comment="Approved in test")
        req.invalidate_recordset()
        self.assertEqual(req.state, 'in_review', "one of two: not yet")
        self.assertEqual(req.current_step, 0)
        req.with_user(self.appr_b).action_approve(comment="Approved in test")
        req.invalidate_recordset()
        self.assertEqual(req.state, 'approved')

    def test_same_user_twice_does_not_satisfy_minimum(self):
        self._policy([(0, 0, {
            'sequence': 10, 'group_id': self.group_manager.id,
            'approval_minimum': 2,
        })])
        bill, req = self._request(self.Policy.search([], limit=1))
        req.with_user(self.appr_a).action_approve(comment="Approved in test")
        req.with_user(self.appr_a).action_approve(comment="Approved in test")
        req.invalidate_recordset()
        self.assertEqual(req.state, 'in_review',
                         "the same approver cannot count twice")

    # ---- named approvers ----

    def test_named_approver_only(self):
        self._policy([(0, 0, {
            'sequence': 10,
            'approver_ids': [(6, 0, [self.named_one.id])],
        })])
        bill, req = self._request(self.Policy.search([], limit=1))
        # An accounting manager who is not the named approver cannot sign.
        with self.assertRaises(UserError):
            req.with_user(self.appr_a).action_approve(comment="Approved in test")
        req.with_user(self.named_one).action_approve(comment="Approved in test")
        req.invalidate_recordset()
        self.assertEqual(req.state, 'approved')

    # ---- required approver ----

    def test_required_approver_must_sign(self):
        self._policy([(0, 0, {
            'sequence': 10, 'group_id': self.group_manager.id,
            'approval_minimum': 1,
            'required_approver_ids': [(6, 0, [self.appr_b.id])],
        })])
        bill, req = self._request(self.Policy.search([], limit=1))
        # appr_a meets the count but the required appr_b has not signed.
        req.with_user(self.appr_a).action_approve(comment="Approved in test")
        req.invalidate_recordset()
        self.assertEqual(req.state, 'in_review')
        req.with_user(self.appr_b).action_approve(comment="Approved in test")
        req.invalidate_recordset()
        self.assertEqual(req.state, 'approved')

    # ---- parallel ----

    def test_parallel_all_steps_any_order(self):
        self._policy([
            (0, 0, {'sequence': 10,
                    'approver_ids': [(6, 0, [self.named_one.id])]}),
            (0, 0, {'sequence': 20,
                    'approver_ids': [(6, 0, [self.named_two.id])]}),
        ], mode='parallel')
        bill, req = self._request(self.Policy.search([], limit=1))
        # Approve the second step first: still pending the first.
        req.with_user(self.named_two).action_approve(comment="Approved in test")
        req.invalidate_recordset()
        self.assertEqual(req.state, 'in_review')
        req.with_user(self.named_one).action_approve(comment="Approved in test")
        req.invalidate_recordset()
        self.assertEqual(req.state, 'approved')

    # ---- cross-step segregation of duties ----

    def test_single_user_cannot_clear_two_step_rule_alone(self):
        # One user who belongs to every step group must not be able to
        # walk a two-step rule single-handedly: signing step 0 spends
        # them, so they are not an eligible approver for step 1.
        self._policy([
            (0, 0, {'sequence': 10, 'group_id': self.group_manager.id}),
            (0, 0, {'sequence': 20, 'group_id': self.group_manager.id}),
        ])
        bill, req = self._request(self.Policy.search([], limit=1))
        req.with_user(self.appr_a).action_approve(comment="Approved in test")
        req.invalidate_recordset()
        self.assertEqual(req.state, 'in_review',
                         "first signature advances only the first step")
        self.assertEqual(req.current_step, 1)
        # appr_a is in the manager group for step 1 too, but already
        # signed step 0, so cross-step SoD must refuse the second signature.
        with self.assertRaises(UserError):
            req.with_user(self.appr_a).action_approve(comment="Approved in test")
        req.invalidate_recordset()
        self.assertEqual(req.state, 'in_review')
        self.assertEqual(req.current_step, 1)

    def test_two_distinct_approvers_clear_two_step_rule(self):
        # The same two-step rule is cleared when a second, distinct
        # approver signs the later step.
        self._policy([
            (0, 0, {'sequence': 10, 'group_id': self.group_manager.id}),
            (0, 0, {'sequence': 20, 'group_id': self.group_manager.id}),
        ])
        bill, req = self._request(self.Policy.search([], limit=1))
        req.with_user(self.appr_a).action_approve(comment="Approved in test")
        req.invalidate_recordset()
        self.assertEqual(req.current_step, 1)
        req.with_user(self.appr_b).action_approve(comment="Approved in test")
        req.invalidate_recordset()
        self.assertEqual(req.state, 'approved')

    # ---- force approve ----

    def test_force_approve_by_manager(self):
        self._policy([(0, 0, {
            'sequence': 10, 'group_id': self.group_manager.id,
            'approval_minimum': 2,
        })])
        bill, req = self._request(self.Policy.search([], limit=1))
        req.with_user(self.appr_a).action_force_approve(
            reason="exec override",
        )
        self.assertEqual(req.state, 'approved')

    def test_requester_manager_cannot_force_approve_own_request(self):
        self._policy([(0, 0, {
            'sequence': 10, 'group_id': self.group_manager.id,
        })])
        _bill, req = self._request(self.Policy.search([], limit=1))
        self.assertEqual(req.requested_by_id, self.env.user)
        with self.assertRaises(UserError):
            req.action_force_approve(reason="self override")
        self.assertEqual(req.state, 'in_review')

    def test_force_approve_denied_for_non_manager(self):
        self._policy([(0, 0, {
            'sequence': 10, 'group_id': self.group_manager.id,
        })])
        bill, req = self._request(self.Policy.search([], limit=1))
        with self.assertRaises(UserError):
            req.with_user(self.named_one).action_force_approve()
