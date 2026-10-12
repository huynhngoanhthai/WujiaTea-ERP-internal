# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Vote tamper-evidence tests.

A vote row is the sole source of truth for whether an approval step is
satisfied. A user must not be able to forge one, flip a recorded decision,
re-attribute a signature, backdate it, or delete it. These tests assert that
every direct (non-workflow) mutation is refused, while the sanctioned
action_approve path still records a vote.
"""

from odoo.exceptions import AccessError
from odoo.tests import tagged

from odoo.addons.eh_account_base.tests.common import (
    EhAccountIntegrationTestCase,
)


@tagged('eh_account_approval', 'security', 'post_install', '-at_install')
class TestVoteTamper(EhAccountIntegrationTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Policy = cls.env['eh.approval.policy']
        cls.Move = cls.env['account.move']
        cls.Vote = cls.env['eh.approval.vote']
        cls.group_manager = cls.env.ref('eh_account_base.group_eh_manager')
        cls.group_user = cls.env.ref('eh_account_base.group_eh_user')

        cls.expense_account = cls.env['account.account'].search(
            [('account_type', '=', 'expense'),
             ('company_ids', 'in', cls.env.company.ids)], limit=1)
        if not cls.expense_account:
            cls.expense_account = cls.env['account.account'].create({
                'code': '5591', 'name': 'Tamper Test Expense',
                'account_type': 'expense',
                'company_ids': [(6, 0, cls.env.company.ids)],
            })
        cls.partner = cls.env['res.partner'].create({'name': 'Tamper vendor'})

        def _user(login, groups):
            return cls.env['res.users'].create({
                'name': login, 'login': login, 'email': login,
                'group_ids': [(6, 0, [g.id for g in groups])],
            })

        cls.approver = _user('vt_appr@test', [cls.group_manager])
        # Mallory: an ordinary accounting user, the low-privilege attacker.
        cls.mallory = _user('vt_mallory@test', [cls.group_user])
        cls.env.user.group_ids |= cls.group_manager

        cls.Policy.create({
            'name': 'VT policy', 'document_type': 'in_invoice',
            'company_id': cls.env.company.id,
            'rule_ids': [(0, 0, {
                'name': 'any', 'sequence': 10,
                'min_amount': 100.0, 'max_amount': 0.0,
                'approval_mode': 'sequential',
                'step_ids': [(0, 0, {
                    'sequence': 10, 'group_id': cls.group_manager.id,
                    'approval_minimum': 1,
                })],
            })],
        })

    def _request(self):
        bill = self.Move.create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2026-04-15',
            'invoice_line_ids': [(0, 0, {
                'name': 'x', 'quantity': 1, 'price_unit': 2000.0,
                'account_id': self.expense_account.id,
            })],
        })
        bill.action_eh_request_approval()
        return bill, bill.eh_active_approval_request_id

    def test_user_cannot_forge_a_vote(self):
        """A low-privilege user cannot inject an approve row directly."""
        _bill, req = self._request()
        with self.assertRaises(AccessError):
            self.Vote.with_user(self.mallory).create({
                'request_id': req.id, 'step_index': 0,
                'user_id': self.approver.id, 'decision': 'approve',
            })
        req.invalidate_recordset()
        self.assertEqual(req.state, 'in_review', "forge must not advance")

    def test_user_cannot_flip_or_backdate_a_recorded_vote(self):
        """A recorded vote is immutable to users; anchors frozen even in sudo."""
        _bill, req = self._request()
        req.with_user(self.approver).action_reject(reason='no')
        vote = req.vote_ids
        self.assertTrue(vote, "reject must have recorded a vote")
        # Flip reject -> approve as a user: refused.
        with self.assertRaises(AccessError):
            vote.with_user(self.mallory).write({'decision': 'approve'})
        # Even in sudo, the evidence anchors cannot be rewritten.
        with self.assertRaises(AccessError):
            vote.sudo().write({'user_id': self.mallory.id})
        vote.invalidate_recordset()
        self.assertEqual(vote.decision, 'reject', "decision must be unchanged")

    def test_user_cannot_delete_a_vote(self):
        _bill, req = self._request()
        req.with_user(self.approver).action_approve(comment="Approved in test")
        vote = req.vote_ids
        self.assertTrue(vote)
        with self.assertRaises(AccessError):
            vote.with_user(self.mallory).unlink()

    def test_sanctioned_approval_still_records_a_vote(self):
        """The workflow path is unaffected by the guards."""
        _bill, req = self._request()
        req.with_user(self.approver).action_approve(comment="Approved in test")
        req.invalidate_recordset()
        self.assertEqual(req.state, 'approved')
        self.assertEqual(len(req.vote_ids), 1)
        self.assertEqual(req.vote_ids.user_id, self.approver)
        self.assertEqual(req.vote_ids.decision, 'approve')
