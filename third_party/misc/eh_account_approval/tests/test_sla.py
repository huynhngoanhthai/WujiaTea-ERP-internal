# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
SLA + escalation tests for the approval workflow.

Sets up a policy rule with sla_hours=4, reminder_after_hours=2 and
escalate_after_hours=1, drives an approval request through it, and
asserts the lifecycle:

* due_at computes from rule.sla_hours + submitted_at.
* sla_state walks 'on_track' -> 'at_risk' -> 'breached' as the clock
  is advanced by manipulating submitted_at.
* The hourly cron sends a reminder once per reminder window and
  escalates once per request.
* action_send_reminder posts a chatter note tagging the pending
  approver group.
* action_force_escalate refuses when no escalation group is configured.
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.eh_account_base.tests.common import (
    EhAccountIntegrationTestCase,
)


@tagged('eh_account_approval', 'integration', 'post_install', '-at_install')
class TestApprovalSla(EhAccountIntegrationTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Policy = cls.env['eh.approval.policy']
        cls.Request = cls.env['eh.approval.request']
        cls.Move = cls.env['account.move']

        cls.expense_account = cls.env['account.account'].search(
            [('account_type', '=', 'expense'),
             ('company_ids', 'in', cls.env.company.ids)],
            limit=1,
        )
        if not cls.expense_account:
            cls.expense_account = cls.env['account.account'].create({
                'code': '5510',
                'name': 'SLA Test Expense',
                'account_type': 'expense',
                'company_ids': [(6, 0, cls.env.company.ids)],
            })
        cls.partner = cls.env['res.partner'].create({
            'name': 'SLA test vendor',
        })

        cls.group_manager = cls.env.ref('eh_account_base.group_eh_manager')
        cls.group_escalation = cls.env['res.groups'].create({
            'name': 'EH Test SLA Escalation',
        })

        cls.policy = cls.Policy.create({
            'name': 'SLA test',
            'document_type': 'in_invoice',
            'company_id': cls.env.company.id,
            'rule_ids': [(0, 0, {
                'name': 'Single approver with SLA',
                'sequence': 10,
                'min_amount': 100.0,
                'max_amount': 0.0,
                'step_ids': [(0, 0, {'group_id': cls.group_manager.id,
                                     'sequence': 10})],
                'sla_hours': 4,
                'reminder_after_hours': 2,
                'escalate_after_hours': 1,
                'escalate_to_group_id': cls.group_escalation.id,
            })],
        })
        cls.env.user.group_ids |= cls.group_manager
        # A distinct approver in the manager group: the requester
        # (env.user) cannot sign their own request under segregation of
        # duties, so terminal-state tests approve as this user instead.
        cls.user_approver = cls.env['res.users'].create({
            'name': 'SLA Approver Test',
            'login': 'sla_approver@test', 'email': 'sla_approver@test',
            'group_ids': [(6, 0, [cls.group_manager.id])],
        })
        cls.user_escalation = cls.env['res.users'].create({
            'name': 'SLA Escalation Test',
            'login': 'sla_escalation@test', 'email': 'sla_escalation@test',
            'group_ids': [(6, 0, [
                cls.env.ref('eh_account_base.group_eh_user').id,
                cls.group_escalation.id,
            ])],
        })

    def _make_request(self, amount=2000.0):
        bill = self.Move.create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2026-04-15',
            'invoice_line_ids': [(0, 0, {
                'name': 'SLA test',
                'quantity': 1,
                'price_unit': amount,
                'account_id': self.expense_account.id,
            })],
        })
        rule = self.policy.find_matching_rule(amount)
        request = self.Request.create({
            'move_id': bill.id,
            'policy_id': self.policy.id,
            'rule_id': rule.id,
            'submitted_amount': amount,
        })
        request.action_submit()
        return request

    # ---- due_at + sla_state computation ----

    def test_due_at_set_on_submit(self):
        req = self._make_request()
        self.assertTrue(req.submitted_at)
        self.assertTrue(req.due_at)
        # 4-hour SLA: due_at should be ~4h after submitted_at.
        delta = (req.due_at - req.submitted_at).total_seconds() / 3600.0
        self.assertAlmostEqual(delta, 4.0, places=1)

    def test_sla_state_on_track_initially(self):
        req = self._make_request()
        # Just submitted: 0% consumed -> on_track.
        self.assertEqual(req.sla_state, 'on_track')
        self.assertFalse(req.is_overdue)

    def test_sla_state_at_risk_above_80_pct(self):
        req = self._make_request()
        # Rewind submitted_at by 3.4 hours so 85% of the 4-hour
        # window has elapsed. Fields recompute on read.
        req.submitted_at = fields.Datetime.now() - timedelta(
            hours=3, minutes=24,
        )
        req.invalidate_recordset(['due_at', 'sla_state', 'is_overdue'])
        self.assertEqual(req.sla_state, 'at_risk')
        self.assertFalse(req.is_overdue)

    def test_sla_state_breached_past_due(self):
        req = self._make_request()
        # Push submitted_at far enough back that due_at is in the
        # past.
        req.submitted_at = fields.Datetime.now() - timedelta(hours=10)
        req.invalidate_recordset(['due_at', 'sla_state', 'is_overdue'])
        self.assertEqual(req.sla_state, 'breached')
        self.assertTrue(req.is_overdue)

    def test_sla_state_na_on_terminal_state(self):
        req = self._make_request()
        # Approve immediately so the request is no longer in_review.
        # Use a non-requester approver (segregation of duties).
        req.with_user(self.user_approver).action_approve(comment='ok')
        # Single-step rule -> approved.
        self.assertEqual(req.state, 'approved')
        self.assertEqual(req.sla_state, 'na')
        self.assertFalse(req.is_overdue)

    # ---- cron sweep ----

    def test_cron_sends_reminder_after_reminder_window(self):
        req = self._make_request()
        # Push submitted_at back 3.5 hours; with reminder_after_hours=2
        # we are past the reminder threshold and at 87.5% of the
        # 4-hour SLA window, which crosses the 80% at-risk threshold
        # but is still inside the window so not yet breached.
        req.submitted_at = fields.Datetime.now() - timedelta(hours=3, minutes=30)
        req.invalidate_recordset(['due_at', 'sla_state'])
        self.Request._cron_sla_sweep()
        self.assertTrue(req.last_reminded_at)
        self.assertFalse(req.last_escalated_at)
        self.assertEqual(req.sla_state, 'at_risk')

    def test_cron_escalates_breached_request(self):
        req = self._make_request()
        # Push submitted_at back 6 hours; due_at was 4h after
        # submission, so the request is 2h breached. With
        # escalate_after_hours=1 we should escalate.
        req.submitted_at = fields.Datetime.now() - timedelta(hours=6)
        req.invalidate_recordset(['due_at', 'sla_state'])
        self.Request._cron_sla_sweep()
        self.assertTrue(req.last_escalated_at)
        self.assertEqual(req.escalation_level, 1)
        self.assertEqual(req.sla_state, 'breached')
        self.assertEqual(req.pending_group_id, self.group_escalation)

    def test_escalation_group_can_approve_escalated_step(self):
        req = self._make_request()
        req.submitted_at = fields.Datetime.now() - timedelta(hours=6)
        req.invalidate_recordset(['due_at', 'sla_state'])
        self.Request._cron_sla_sweep()
        req.with_user(self.user_escalation).action_approve(
            comment='SLA intervention',
        )
        req.invalidate_recordset()
        self.assertEqual(req.state, 'approved')

    def test_cron_escalates_only_once(self):
        req = self._make_request()
        req.submitted_at = fields.Datetime.now() - timedelta(hours=6)
        req.invalidate_recordset(['due_at', 'sla_state'])
        self.Request._cron_sla_sweep()
        first_ts = req.last_escalated_at
        # Second pass should not re-escalate.
        self.Request._cron_sla_sweep()
        self.assertEqual(req.last_escalated_at, first_ts)
        self.assertEqual(req.escalation_level, 1)

    def test_escalation_writes_audit_log(self):
        # The escalation must leave an audit row. 'escalated' has to be
        # a valid eh.approval.log action; when it was missing, the log
        # write raised and the cron swallowed it as a warning, so the
        # escalation happened with no trace.
        req = self._make_request()
        req.submitted_at = fields.Datetime.now() - timedelta(hours=6)
        req.invalidate_recordset(['due_at', 'sla_state'])
        self.Request._cron_sla_sweep()
        self.assertEqual(req.escalation_level, 1)
        log = self.env['eh.approval.log'].search([
            ('request_id', '=', req.id),
            ('action', '=', 'escalated'),
        ])
        self.assertEqual(
            len(log), 1,
            "escalation must record exactly one 'escalated' audit row",
        )

    # ---- manual actions ----

    def test_action_send_reminder_posts_chatter(self):
        req = self._make_request()
        before = len(req.message_ids)
        req.action_send_reminder()
        self.assertGreater(len(req.message_ids), before)

    def test_action_force_escalate_without_target_raises(self):
        # Build a rule with no escalation group to confirm the
        # manual escalate action refuses.
        # Submission resolves the active policy from the move rather than
        # trusting caller-supplied policy/rule ids.  Disable the class policy
        # so this purpose-built policy is the authoritative match.
        self.policy.active = False
        bill = self.Move.create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2026-04-15',
            'invoice_line_ids': [(0, 0, {
                'name': 'X', 'quantity': 1, 'price_unit': 200.0,
                'account_id': self.expense_account.id,
            })],
        })
        no_escalation_policy = self.Policy.create({
            'name': 'No escalation policy',
            'document_type': 'in_invoice',
            'company_id': self.env.company.id,
            'rule_ids': [(0, 0, {
                'name': 'No escalation',
                'sequence': 10,
                'min_amount': 100.0,
                'max_amount': 0.0,
                'step_ids': [(0, 0, {'group_id': self.group_manager.id,
                                     'sequence': 10})],
                'sla_hours': 4,
            })],
        })
        rule = no_escalation_policy.find_matching_rule(200.0)
        req = self.Request.create({
            'move_id': bill.id,
            'policy_id': no_escalation_policy.id,
            'rule_id': rule.id,
            'submitted_amount': 200.0,
        })
        req.action_submit()
        with self.assertRaises(UserError):
            req.action_force_escalate()

    # ---- search domain ----

    def test_is_overdue_search_domain(self):
        # Build one overdue request and one on-track request; the
        # is_overdue=True search should pick only the overdue one.
        overdue = self._make_request(amount=2500.0)
        overdue.submitted_at = fields.Datetime.now() - timedelta(hours=10)
        overdue.invalidate_recordset(['due_at', 'is_overdue'])

        on_track = self._make_request(amount=2600.0)

        results = self.Request.search([('is_overdue', '=', True)])
        self.assertIn(overdue, results)
        self.assertNotIn(on_track, results)
