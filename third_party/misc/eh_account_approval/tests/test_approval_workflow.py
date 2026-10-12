# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Approval workflow tests.

Sets up a two-step policy (manager then director) on vendor bills above
1000, posts a bill, and walks the request through both approval steps.
Covers:

* Policy.find_for_move and Policy.find_matching_rule routing.
* Multi-step state machine: pending -> in_review -> approved.
* The post() block until approved.
* Re-approval reset on material amount change after partial approval.
* Atomic step advancement: the same step cannot be advanced twice.
* Reject and withdraw paths.
* Append-only audit log.
"""

from unittest.mock import patch

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools.profiler import Profiler

from odoo.addons.eh_account_base.tests.common import (
    EhAccountIntegrationTestCase,
)


@tagged('eh_account_approval', 'integration', 'post_install', '-at_install')
class TestApprovalWorkflow(EhAccountIntegrationTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Policy = cls.env['eh.approval.policy']
        cls.Request = cls.env['eh.approval.request']
        cls.Log = cls.env['eh.approval.log']
        cls.Move = cls.env['account.move']

        cls.expense_account = cls.env['account.account'].search(
            [('account_type', '=', 'expense'),
             ('company_ids', 'in', cls.env.company.ids)],
            limit=1,
        )
        if not cls.expense_account:
            cls.expense_account = cls.env['account.account'].create({
                'code': '5500',
                'name': 'Approval Test Expense',
                'account_type': 'expense',
                'company_ids': [(6, 0, cls.env.company.ids)],
            })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Approval test vendor',
        })

        # Two-step policy: manager then director.
        cls.group_manager = cls.env.ref('eh_account_base.group_eh_manager')
        cls.group_director = cls.env['res.groups'].create({
            'name': 'EH Test Director',
        })

        cls.policy = cls.Policy.create({
            'name': 'Vendor bills above 1000',
            'document_type': 'in_invoice',
            'company_id': cls.env.company.id,
            're_approval_threshold_pct': 10.0,
            're_approval_threshold_abs': 50.0,
            'rule_ids': [(0, 0, {
                'name': 'Big bills',
                'sequence': 10,
                'min_amount': 1000.0,
                'max_amount': 0.0,
                'step_ids': [
                    (0, 0, {'group_id': cls.group_manager.id,
                            'sequence': 10}),
                    (0, 0, {'group_id': cls.group_director.id,
                            'sequence': 20}),
                ],
            })],
        })

        # Two test users in the appropriate groups.
        cls.user_manager = cls.env['res.users'].create({
            'name': 'Approval Manager Test',
            'login': 'approval_mgr@test', 'email': 'approval_mgr@test',
            'group_ids': [(6, 0, [
                cls.group_manager.id,
            ])],
        })
        cls.user_director = cls.env['res.users'].create({
            'name': 'Approval Director Test',
            'login': 'approval_dir@test', 'email': 'approval_dir@test',
            'group_ids': [(6, 0, [
                cls.group_director.id,
                cls.group_manager.id,
            ])],
        })
        cls.standard_account_user = cls.env['res.users'].create({
            'name': 'Approval Standard Accounting User',
            'login': 'approval_standard_account@test',
            'email': 'approval_standard_account@test',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, cls.company.ids)],
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('account.group_account_invoice').id,
            ])],
        })
        cls.non_account_user = cls.env['res.users'].create({
            'name': 'Approval Non-account User',
            'login': 'approval_non_account@test',
            'email': 'approval_non_account@test',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, cls.company.ids)],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        # The current test user gets manager too so move creation works.
        cls.env.user.group_ids |= cls.group_manager

    def _make_bill(self, amount):
        return self.Move.create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2026-04-15',
            'invoice_line_ids': [(0, 0, {
                'name': 'Big purchase',
                'quantity': 1,
                'price_unit': amount,
                'account_id': self.expense_account.id,
            })],
        })

    def _make_entry(self, journal=None, **extra):
        vals = {
            'move_type': 'entry',
            'date': '2026-04-15',
            'journal_id': (journal or self.journal_misc).id,
            'line_ids': [
                (0, 0, {
                    'name': 'Debit leg',
                    'account_id': self.expense_account.id,
                    'debit': 2000.0,
                }),
                (0, 0, {
                    'name': 'Credit leg',
                    'account_id': self.account_cash.id,
                    'credit': 2000.0,
                }),
            ],
        }
        vals.update(extra)
        return self.Move.create(vals)

    def _make_entry_policy(self, name, journals, origin='manual', sequence=10):
        return self.Policy.create({
            'name': name,
            'document_type': 'entry',
            'entry_origin': origin,
            'journal_ids': [(6, 0, journals.ids)],
            'company_id': self.env.company.id,
            'sequence': sequence,
            'rule_ids': [(0, 0, {
                'name': name,
                'sequence': 10,
                'min_amount': 0.0,
                'max_amount': 0.0,
                'step_ids': [(0, 0, {
                    'group_id': self.group_manager.id,
                    'sequence': 10,
                })],
            })],
        })

    @staticmethod
    def _profile_queries(profiler):
        return [
            entry['full_query']
            for entry in profiler.collectors[0].entries
        ]

    # ---- workflow-guard: RPC bypass is refused ----

    def test_direct_state_write_is_refused(self):
        """The classic exploit - write({'state':'approved'}) over RPC to
        skip the whole chain - must be blocked by eh.workflow.guard. No
        vote, no manager, just a direct ORM/RPC write."""
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        self.assertEqual(request.state, 'in_review')
        # Attempt the bypass as a normal (non-superuser) accounting user;
        # the test env itself runs as SUPERUSER, which is trusted, so the
        # attack must be simulated through an ordinary user.
        attacker = request.with_user(self.user_manager)
        with self.assertRaises(AccessError):
            attacker.write({'state': 'approved'})
        with self.assertRaises(AccessError):
            attacker.write({'current_step': request.total_steps})
        # The record is untouched and the move is still gated.
        request.invalidate_recordset(['state'])
        self.assertEqual(request.state, 'in_review')

    def test_actions_still_drive_state(self):
        """The legitimate action path must still work end to end."""
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        request.with_user(self.user_manager).action_approve(comment="Approved in test")
        request.with_user(self.user_director).action_approve(comment="Approved in test")
        self.assertEqual(request.state, 'approved')

    def test_pending_request_identity_fields_editable(self):
        """A still-'pending' request's own form fields (move/policy/rule)
        must stay editable by a normal (non-superuser) editor. The guard
        only freezes them AFTER submission, so correcting a mis-derived
        policy before submission must succeed - the legitimate path the
        over-restriction fix restores."""
        bill = self._make_bill(2000.0)
        other_bill = self._make_bill(3000.0)
        # A pending request (default state), created directly like the
        # form's own create path.
        request = self.Request.create({
            'move_id': bill.id,
            'policy_id': self.policy.id,
            'rule_id': self.policy.rule_ids[0].id,
            'submitted_amount': 2000.0,
        })
        self.assertEqual(request.state, 'pending')
        # Write as an ordinary (non-superuser) manager, the way the web
        # client saves a corrected form. This must NOT raise.
        editor = request.with_user(self.user_manager)
        editor.write({
            'move_id': other_bill.id,
            'policy_id': self.policy.id,
            'rule_id': self.policy.rule_ids[0].id,
            'submitted_amount': 3000.0,
        })
        request.invalidate_recordset(['move_id', 'submitted_amount'])
        self.assertEqual(request.move_id, other_bill)
        self.assertEqual(request.submitted_amount, 3000.0)

    def test_repoint_submitted_request_is_refused(self):
        """Once a request leaves 'pending', a direct non-superuser write
        must not be able to repoint it onto a different move or restate the
        submitted amount - the original protection stays closed even after
        the guard was scoped to the locked states."""
        bill = self._make_bill(2000.0)
        other_bill = self._make_bill(9000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        self.assertEqual(request.state, 'in_review')
        attacker = request.with_user(self.user_manager)
        with self.assertRaises(AccessError):
            attacker.write({'move_id': other_bill.id})
        with self.assertRaises(AccessError):
            attacker.write({'rule_id': self.policy.rule_ids[0].id})
        with self.assertRaises(AccessError):
            attacker.write({'submitted_amount': 1.0})
        # The record is untouched by the refused writes.
        request.invalidate_recordset(['move_id', 'submitted_amount'])
        self.assertEqual(request.move_id, bill)
        self.assertEqual(request.submitted_amount, 2000.0)

    def test_direct_duplicate_active_request_is_refused(self):
        """The move lock makes the one-active-request check race-safe."""
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        with self.assertRaises(UserError):
            self.Request.create({
                'move_id': bill.id,
                'policy_id': self.policy.id,
                'rule_id': self.policy.rule_ids[0].id,
                'submitted_amount': 1.0,
            })

    def test_submission_snapshot_is_anchored_in_append_only_log(self):
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        submitted = request.log_ids.filtered(
            lambda row: row.action == 'submitted')
        self.assertEqual(len(submitted), 1)
        self.assertEqual(
            submitted.authorization_snapshot_hash,
            request.approval_snapshot_hash,
        )
        self.assertEqual(
            submitted.authorization_snapshot,
            request.approval_snapshot,
        )
        self.assertEqual(
            submitted.authorization_snapshot.get('schema'),
            'eh-approval-authorization-v2',
        )

    # ---- policy routing ----

    def test_pending_group_follows_step_sequence_not_group_id(self):
        # group_director was created after group_eh_manager, so it has
        # the higher primary key. Put it FIRST by sequence and confirm
        # the request walks director-first. Step order must come from
        # the explicit sequence column, never from the group id: the
        # old sorted('id') logic would have put the manager first here
        # and silently reordered the chain.
        rule = self.policy.rule_ids[0]
        rule.step_ids.unlink()
        self.env['eh.approval.policy.rule.step'].create([
            {'rule_id': rule.id, 'group_id': self.group_director.id,
             'sequence': 5},
            {'rule_id': rule.id, 'group_id': self.group_manager.id,
             'sequence': 10},
        ])
        self.assertGreater(self.group_director.id, self.group_manager.id,
                           "test premise: director has the higher id")
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        request.invalidate_recordset()
        self.assertEqual(
            request.pending_group_id, self.group_director,
            "step 0 must be the lowest-sequence group, not lowest id",
        )
        self.assertEqual(request.total_steps, 2)

    def test_find_for_move_returns_policy(self):
        bill = self._make_bill(2000.0)
        policy = self.Policy.find_for_move(bill)
        self.assertEqual(policy, self.policy)

    def test_entry_policy_requires_explicit_journal_scope(self):
        with self.assertRaises(ValidationError):
            self._make_entry_policy(
                'Unsafe unscoped entry policy', self.env['account.journal'],
            )

    def test_entry_policy_matches_explicit_origin_and_journal_only(self):
        manual = self._make_entry_policy(
            'Manual scoped entries', self.journal_misc, sequence=20,
        )
        entry = self._make_entry()
        self.assertEqual(self.Policy.find_for_move(entry), manual)

        other_journal = self.env['account.journal'].create({
            'name': 'Approval Other Journal',
            'code': 'APO2',
            'type': 'general',
            'company_id': self.company.id,
        })
        other_entry = self._make_entry(journal=other_journal)
        self.assertFalse(self.Policy.find_for_move(other_entry))

        source = self._make_entry()
        reversal = self._make_entry(reversed_entry_id=source.id)
        self.assertEqual(reversal._eh_approval_entry_origin(), 'reversal')
        self.assertFalse(self.Policy.find_for_move(reversal))
        reversal_policy = self._make_entry_policy(
            'Scoped reversals', self.journal_misc,
            origin='reversal', sequence=10,
        )
        self.assertEqual(
            self.Policy.find_for_move(reversal), reversal_policy,
        )

        automatic = self._make_entry(auto_post='monthly')
        self.assertEqual(
            automatic._eh_approval_entry_origin(), 'automatic',
        )
        self.assertFalse(self.Policy.find_for_move(automatic))

    def test_payment_and_statement_origins_are_not_manual(self):
        payment_field = (
            'origin_payment_id'
            if 'origin_payment_id' in self.Move._fields else 'payment_id'
        )
        payment = self.Move.new({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            payment_field: 2147483001,
        })
        statement = self.Move.new({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'statement_line_id': 2147483002,
        })
        self.assertEqual(payment._eh_approval_entry_origin(), 'payment')
        self.assertEqual(
            statement._eh_approval_entry_origin(), 'bank_statement',
        )

    def test_ungoverned_basis_mutation_and_post_take_no_approval_locks(self):
        other_account = self.env['account.account'].create({
            'code': '5588',
            'name': 'Ungoverned Lock Test Expense',
            'account_type': 'expense',
            'company_ids': [(6, 0, self.env.company.ids)],
        })
        entry = self._make_entry()
        debit_line = entry.line_ids.filtered('debit')
        lock_calls = []
        move_class = type(entry)
        original_lock = move_class._eh_lock_approval_scope

        def _spy_lock(records, policy_ids=()):
            lock_calls.append((tuple(records.ids), tuple(policy_ids)))
            return original_lock(records, policy_ids=policy_ids)

        with patch.object(move_class, '_eh_lock_approval_scope', _spy_lock):
            with Profiler(db=None, collectors=['sql']) as profiler:
                entry.write({'partner_id': self.partner.id})
                note_line = self.env['account.move.line'].create({
                    'move_id': entry.id,
                    'display_type': 'line_note',
                    'name': 'Ungoverned note',
                })
                note_line.unlink()
                debit_line.write({'account_id': other_account.id})
                entry.action_post()
        self.assertEqual(lock_calls, [])
        approval_locks = [
            query for query in self._profile_queries(profiler)
            if 'FOR UPDATE' in query.upper()
            and (
                'FROM eh_approval_policy WHERE id IN' in query
                or 'FROM eh_approval_request WHERE move_id IN' in query
                or 'FROM res_company WHERE id IN' in query
            )
        ]
        self.assertEqual(approval_locks, [])

    def test_scoped_lock_order_is_move_policy_request_without_company(self):
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        with Profiler(db=None, collectors=['sql']) as profiler:
            bill._eh_lock_approval_scope(policy_ids=self.policy.ids)
        locks = [
            query for query in self._profile_queries(profiler)
            if 'FOR UPDATE' in query.upper()
        ]
        joined = '\n'.join(locks)
        self.assertNotIn('FROM res_company', joined)
        move_index = next(
            index for index, query in enumerate(locks)
            if 'FROM account_move WHERE id IN' in query
        )
        policy_index = next(
            index for index, query in enumerate(locks)
            if 'FROM eh_approval_policy WHERE id IN' in query
        )
        request_index = next(
            index for index, query in enumerate(locks)
            if 'FROM eh_approval_request WHERE move_id IN' in query
        )
        self.assertLess(move_index, policy_index)
        self.assertLess(policy_index, request_index)

    def test_policy_lookup_role_and_company_matrix(self):
        bill = self._make_bill(2000.0)
        policy = self.Policy.with_user(
            self.standard_account_user,
        ).find_for_move(bill)
        self.assertEqual(policy.id, self.policy.id)

        with self.assertRaises(AccessError):
            self.Policy.with_user(self.non_account_user).find_for_move(bill)

        other_company = self.env['res.company'].create({
            'name': 'Approval Policy Hidden Company',
        })
        other_company_user = self.env['res.users'].create({
            'name': 'Approval Other-company Accounting User',
            'login': 'approval_other_company@test',
            'email': 'approval_other_company@test',
            'company_id': other_company.id,
            'company_ids': [(6, 0, [other_company.id])],
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('account.group_account_invoice').id,
            ])],
        })
        with self.assertRaises(AccessError):
            self.Policy.with_user(
                other_company_user,
            ).find_for_move(bill)

    def test_find_matching_rule_above_threshold(self):
        bill = self._make_bill(2000.0)
        rule = self.policy.find_matching_rule(2000.0)
        self.assertTrue(rule)
        self.assertEqual(rule.policy_id, self.policy)

    def test_find_matching_rule_below_threshold_returns_empty(self):
        rule = self.policy.find_matching_rule(500.0)
        self.assertFalse(rule)

    # ---- block posting ----

    def test_post_blocked_when_policy_applies_and_no_request(self):
        bill = self._make_bill(2000.0)
        with self.assertRaises(UserError) as cm:
            bill.action_post()
        self.assertIn('approval', str(cm.exception).lower())

    def test_standard_account_user_gets_business_gate_not_acl_crash(self):
        bill = self._make_bill(2000.0).with_user(
            self.standard_account_user,
        )
        bill.invalidate_recordset(['eh_requires_approval'])
        self.assertTrue(bill.eh_requires_approval)
        with self.assertRaisesRegex(UserError, 'requires approval'):
            bill.action_post()

    def test_post_blocked_when_request_in_review(self):
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        with self.assertRaises(UserError):
            bill.action_post()

    def test_post_succeeds_after_full_approval(self):
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        # Step 1: manager.
        request.with_user(self.user_manager).action_approve(comment="OK")
        request.invalidate_recordset()
        self.assertEqual(request.current_step, 1)
        # Step 2: director.
        request.with_user(self.user_director).action_approve(comment="Final")
        request.invalidate_recordset()
        self.assertEqual(request.state, 'approved')
        # Now post should succeed.
        bill.action_post()
        self.assertEqual(bill.state, 'posted')

    def test_standard_account_user_posts_server_verified_approval(self):
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        request.with_user(self.user_manager).action_approve(comment="OK")
        request.with_user(self.user_director).action_approve(comment="Final")

        bill.with_user(self.standard_account_user).action_post()
        request.invalidate_recordset(['state'])
        self.assertEqual(bill.state, 'posted')
        self.assertEqual(request.state, 'archived')

    def test_post_skipped_when_no_policy(self):
        self.policy.active = False
        bill = self._make_bill(500.0)
        bill.action_post()
        self.assertEqual(bill.state, 'posted')

    def test_post_fails_closed_when_policy_has_band_gap(self):
        bill = self._make_bill(500.0)
        with self.assertRaisesRegex(UserError, 'no approval rule covering'):
            bill.action_post()
        self.assertEqual(bill.state, 'draft')

    # ---- multi-step state machine ----

    def test_first_approve_advances_to_step_one(self):
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        request.with_user(self.user_manager).action_approve(comment="Approved in test")
        request.invalidate_recordset()
        self.assertEqual(request.current_step, 1)
        self.assertEqual(request.state, 'in_review')
        self.assertEqual(request.pending_group_id, self.group_director)

    def test_user_outside_pending_group_cannot_approve(self):
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        # Director cannot sign step 1 (manager step) unless they have
        # the manager group too. Director user has both groups in the
        # fixture so let's create a plain user.
        plain_user = self.env['res.users'].create({
            'name': 'Plain user',
            'login': 'plain@test', 'email': 'plain@test',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        with self.assertRaises(UserError):
            request.with_user(plain_user).action_approve(comment="Approved in test")

    def test_atomic_step_guard_blocks_double_advance(self):
        """Calling _eh_advance_step_atomic twice from the same start
        state must succeed once and refuse the second.
        """
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        first = request._eh_advance_step_atomic(
            expected_step=0,
        )  # noqa: intentional
        self.assertTrue(first)
        second = request._eh_advance_step_atomic(
            expected_step=0,
        )  # stale parallel client
        self.assertFalse(second)
        request.invalidate_recordset(['current_step'])
        self.assertEqual(request.current_step, 1)

    def test_rejection_is_terminal(self):
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        request.with_user(self.user_manager).action_reject(
            reason="Budget exceeded",
        )
        self.assertEqual(request.state, 'rejected')
        self.assertEqual(request.rejection_reason, "Budget exceeded")
        with self.assertRaises(UserError):
            bill.action_post()

    def test_withdraw_then_restart(self):
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        request.action_withdraw(reason="Wrong vendor")
        self.assertEqual(request.state, 'withdrawn')
        request.action_restart()
        self.assertEqual(request.state, 'pending')
        self.assertEqual(request.current_step, 0)

    # ---- re-approval ----

    def test_material_change_resets_request(self):
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        request.with_user(self.user_manager).action_approve(comment="Approved in test")
        request.with_user(self.user_director).action_approve(comment="Approved in test")
        request.invalidate_recordset()
        self.assertEqual(request.state, 'approved')
        # Material change: amount goes from 2000 to 5000 (150% change
        # well above 10% threshold).
        # Trigger the reset via a parent-level write so it commits to
        # the cache before the post-time gate runs (line-level writes
        # now share the same durable reset path as parent writes).
        bill.invoice_line_ids[0].price_unit = 5000.0
        request.invalidate_recordset()
        self.assertEqual(request.state, 'in_review')
        reset_logs = request.log_ids.filtered(lambda l: l.action == 'reset')
        self.assertTrue(reset_logs, "Reset must be recorded in audit log")
        with self.assertRaisesRegex(UserError, 'approv'):
            bill.action_post()

    def test_immaterial_change_does_not_reset(self):
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        request.with_user(self.user_manager).action_approve(comment="Approved in test")
        request.with_user(self.user_director).action_approve(comment="Approved in test")
        # Tiny change (5% of 2000 = 100, well within both thresholds).
        bill.invoice_line_ids[0].price_unit = 2050.0
        bill.action_post()
        self.assertEqual(bill.state, 'posted')

    def test_payee_bank_change_forces_re_approval(self):
        # Redirecting an approved bill to a different payee bank account
        # is a payment-routing / SoD break: it must reset the approval
        # even though the amount is unchanged (below any threshold).
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        request.with_user(self.user_manager).action_approve(comment="Approved in test")
        request.with_user(self.user_director).action_approve(comment="Approved in test")
        request.invalidate_recordset()
        self.assertEqual(request.state, 'approved')
        submitted_log = request.log_ids.filtered(
            lambda row: row.action == 'submitted')
        original_hash = submitted_log.authorization_snapshot_hash
        self.assertFalse(
            submitted_log.authorization_snapshot.get('partner_bank_id'))

        bank_account = self.env['res.partner.bank'].create({
            'acc_number': 'IBAN-EH-RE-APPROVAL-1',
            'partner_id': self.partner.id,
        })
        # Pure routing change: same amount, new payee bank account.
        bill.partner_bank_id = bank_account.id
        request.invalidate_recordset()
        self.assertEqual(
            request.state, 'in_review',
            "Changing the payee bank account must reset the request.",
        )
        self.assertEqual(request.current_step, 0)
        reset_logs = request.log_ids.filtered(
            lambda l: l.action == 'reset',
        )
        self.assertTrue(
            reset_logs, "Routing-change reset must be recorded in the log.",
        )
        reset_log = reset_logs.sorted('id')[-1]
        self.assertEqual(
            reset_log.authorization_snapshot_hash,
            request.approval_snapshot_hash,
        )
        self.assertNotEqual(reset_log.authorization_snapshot_hash,
                            original_hash)
        self.assertEqual(
            reset_log.authorization_snapshot.get('partner_bank_id'),
            bank_account.id,
        )
        # The prior cycle remains a complete immutable evidence row.
        self.assertEqual(submitted_log.authorization_snapshot_hash,
                         original_hash)
        self.assertFalse(
            submitted_log.authorization_snapshot.get('partner_bank_id'))
        # The gate now blocks posting until the request re-approves.
        raised_msg = ''
        try:
            bill.action_post()
        except UserError as exc:
            raised_msg = str(exc)
        self.assertTrue(raised_msg, "Post must block after the reset.")
        self.assertNotEqual(bill.state, 'posted')

    def test_due_date_change_forces_re_approval(self):
        # Shifting the payment due date on an approved bill is a routing
        # change that must reset the approval regardless of amount.
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        request.with_user(self.user_manager).action_approve(comment="Approved in test")
        request.with_user(self.user_director).action_approve(comment="Approved in test")
        request.invalidate_recordset()
        self.assertEqual(request.state, 'approved')

        bill.invoice_date_due = '2027-01-31'
        request.invalidate_recordset()
        self.assertEqual(
            request.state, 'in_review',
            "Changing the due date must reset the request.",
        )
        self.assertEqual(request.current_step, 0)

    def test_in_review_payee_change_starts_a_new_cycle(self):
        """A requester cannot swap the payee while signatures are pending."""
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        prior_cycle = request.approval_cycle
        prior_hash = request.approval_snapshot_hash
        replacement = self.env['res.partner'].create({
            'name': 'Approval replacement vendor',
        })
        bill.partner_id = replacement.id
        request.invalidate_recordset()
        self.assertEqual(request.state, 'in_review')
        self.assertEqual(request.current_step, 0)
        self.assertEqual(request.approval_cycle, prior_cycle + 1)
        self.assertNotEqual(request.approval_snapshot_hash, prior_hash)
        self.assertEqual(
            request.approval_snapshot.get('partner_id'), replacement.id,
        )
        anchored = request.log_ids.filtered(
            lambda row: row.authorization_snapshot_hash in (
                prior_hash, request.approval_snapshot_hash,
            ))
        self.assertEqual(len(anchored), 2)

    def test_line_account_redirection_forces_re_approval(self):
        # Rewriting a posting line to a DIFFERENT account at the same
        # total on an approved journal entry is a payment-routing / SoD
        # break: the value is redirected without touching amount_total,
        # so the amount-based material-change check never fires. The
        # routing re-approval trigger must catch it anyway.
        policy_entry = self.Policy.create({
            'name': 'Journal entries above 1000',
            'document_type': 'entry',
            'journal_ids': [(6, 0, self.journal_misc.ids)],
            'company_id': self.env.company.id,
            're_approval_threshold_pct': 10.0,
            're_approval_threshold_abs': 50.0,
            'rule_ids': [(0, 0, {
                'name': 'Big entries',
                'sequence': 10,
                'min_amount': 1000.0,
                'max_amount': 0.0,
                'step_ids': [
                    (0, 0, {'group_id': self.group_manager.id,
                            'sequence': 10}),
                    (0, 0, {'group_id': self.group_director.id,
                            'sequence': 20}),
                ],
            })],
        })
        self.assertTrue(policy_entry)

        # A second expense account to redirect the debit line to.
        other_account = self.env['account.account'].create({
            'code': '5599',
            'name': 'Approval Test Expense Alt',
            'account_type': 'expense',
            'company_ids': [(6, 0, self.env.company.ids)],
        })
        payable = self.env['account.account'].search(
            [('account_type', '=', 'liability_payable'),
             ('company_ids', 'in', self.env.company.ids)],
            limit=1,
        )
        if not payable:
            payable = self.env['account.account'].create({
                'code': '2100',
                'name': 'Approval Test Payable',
                'account_type': 'liability_payable',
                'company_ids': [(6, 0, self.env.company.ids)],
            })

        entry = self.Move.create({
            'move_type': 'entry',
            'date': '2026-04-15',
            'line_ids': [
                (0, 0, {
                    'name': 'Debit leg',
                    'account_id': self.expense_account.id,
                    'debit': 2000.0, 'credit': 0.0,
                }),
                (0, 0, {
                    'name': 'Credit leg',
                    'account_id': payable.id,
                    'debit': 0.0, 'credit': 2000.0,
                }),
            ],
        })
        entry.action_eh_request_approval()
        request = entry.eh_active_approval_request_id
        request.with_user(self.user_manager).action_approve(comment="Approved in test")
        request.with_user(self.user_director).action_approve(comment="Approved in test")
        request.invalidate_recordset()
        self.assertEqual(request.state, 'approved')

        total_before = entry.amount_total
        debit_line = entry.line_ids.filtered(lambda l: l.debit)
        # Pure account redirection: same debit amount, different account,
        # written through the move via a line_ids command (the vector the
        # routing trigger must cover).
        entry.write({
            'line_ids': [(1, debit_line.id, {
                'account_id': other_account.id,
            })],
        })
        request.invalidate_recordset()

        # The total is unchanged, so this is NOT caught by the amount
        # check; only the routing trigger should reset it.
        self.assertEqual(entry.amount_total, total_before)
        self.assertEqual(
            request.state, 'in_review',
            "Redirecting a line to a different account at the same total "
            "must reset the request.",
        )
        self.assertEqual(request.current_step, 0)
        reset_logs = request.log_ids.filtered(
            lambda l: l.action == 'reset',
        )
        self.assertTrue(
            reset_logs,
            "Account-redirection reset must be recorded in the log.",
        )
        # The gate now blocks posting until the request re-approves.
        raised_msg = ''
        try:
            entry.action_post()
        except UserError as exc:
            raised_msg = str(exc)
        self.assertTrue(raised_msg, "Post must block after the reset.")
        self.assertNotEqual(entry.state, 'posted')

    # ---- self-approval / segregation of duties ----

    def test_requester_cannot_self_approve(self):
        # env.user submits (requested_by_id defaults to env.user) and is
        # also in the manager group that owns step 0. Without the SoD
        # block they could sign their own request; the block must refuse.
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        self.assertEqual(request.requested_by_id, self.env.user)
        with self.assertRaises(UserError) as cm:
            request.action_approve(comment="signing my own")
        self.assertIn('own request', str(cm.exception).lower())
        request.invalidate_recordset(['current_step'])
        self.assertEqual(request.current_step, 0, "step must not advance")

    def test_requester_cannot_self_reject(self):
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        with self.assertRaises(UserError) as cm:
            request.action_reject(reason="killing my own")
        self.assertIn('own request', str(cm.exception).lower())
        self.assertEqual(request.state, 'in_review')

    def test_requester_can_self_approve_when_policy_allows(self):
        # Single-operator escape hatch: allow_self_approval lets the
        # requester sign. Step 0 (manager) is owned by env.user.
        self.policy.allow_self_approval = True
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        self.assertIn(
            self.env.user.id,
            request.approval_snapshot['steps'][0]['eligible_user_ids'],
            "submission must snapshot the requester's effective manager "
            "membership before applying the self-approval policy",
        )
        request.action_approve(comment="self ok by policy")
        request.invalidate_recordset(['current_step'])
        self.assertEqual(request.current_step, 1)

    def test_non_requester_unaffected_by_self_approval_block(self):
        # A different approver in the pending group is never blocked.
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        request.with_user(self.user_manager).action_approve(comment="Approved in test")
        request.invalidate_recordset(['current_step'])
        self.assertEqual(request.current_step, 1)

    # ---- audit log ----

    def test_log_rows_are_append_only(self):
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        log = request.log_ids[:1]
        self.assertTrue(log)
        with self.assertRaises(UserError):
            log.write({'action': 'rejected'})
        with self.assertRaises(UserError):
            log.unlink()

    def test_log_rows_cannot_be_forged_directly(self):
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        with self.assertRaises(AccessError):
            self.Log.with_user(self.user_manager).create({
                'request_id': request.id,
                'action': 'approved',
                'step': request.current_step,
                'user_id': self.env.user.id,
                'comment': 'forged approval evidence',
            })

    def test_log_records_every_transition(self):
        bill = self._make_bill(2000.0)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        request.with_user(self.user_manager).action_approve(comment="Step 1 ok")
        request.with_user(self.user_director).action_approve(comment="Step 2 ok")
        actions = request.log_ids.mapped('action')
        self.assertIn('submitted', actions)
        self.assertIn('approved', actions)
        self.assertIn('completed', actions)
