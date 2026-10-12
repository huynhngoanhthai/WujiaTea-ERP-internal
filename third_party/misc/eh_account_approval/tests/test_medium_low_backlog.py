# -*- encoding: utf-8 -*-

import ast
import csv
import importlib.util
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.modules.module import get_module_path

from odoo.addons.eh_account_base.tests.common import (
    EhAccountIntegrationTestCase,
)


@tagged('eh_account_approval', 'post_install', '-at_install')
class TestApprovalMediumLowBacklog(EhAccountIntegrationTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Policy = cls.env['eh.approval.policy']
        cls.Request = cls.env['eh.approval.request']
        cls.Move = cls.env['account.move']
        cls.company.email = 'approval-company@test.invalid'
        cls.expense_account = cls.env['account.account'].search([
            ('account_type', '=', 'expense'),
            ('company_ids', 'in', cls.company.ids),
        ], limit=1)
        cls.partner = cls.env['res.partner'].create({
            'name': 'Approval backlog vendor',
        })
        cls.approver_group = cls.env['res.groups'].create({
            'name': 'Approval backlog named group',
        })
        account_group = cls.env.ref('account.group_account_user')
        cls.named_approver = cls.env['res.users'].create({
            'name': 'Named accounting approver',
            'login': 'approval_backlog_named@test.invalid',
            'email': 'approval_backlog_named@test.invalid',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                account_group.id,
                cls.approver_group.id,
            ])],
            'company_ids': [(6, 0, cls.company.ids)],
            'company_id': cls.company.id,
        })
        cls.policy = cls.Policy.create({
            'name': 'Approval backlog policy',
            'company_id': cls.company.id,
            'document_type': 'in_invoice',
            'rule_ids': [(0, 0, {
                'name': 'All governed bills',
                'min_amount': 0.0,
                'max_amount': 0.0,
                'sla_hours': 4,
                'reminder_after_hours': 1,
                'step_ids': [(0, 0, {
                    'approver_ids': [(6, 0, [cls.named_approver.id])],
                    'approval_minimum': 1,
                })],
            })],
        })

    def _bill(self, amount=100.0, company=None, currency=None):
        company = company or self.company
        Move = self.Move.with_context(
            allowed_company_ids=(self.company | company).ids,
        ).with_company(company)
        return Move.create({
            'move_type': 'in_invoice',
            'company_id': company.id,
            'partner_id': self.partner.id,
            'currency_id': (currency or company.currency_id).id,
            'invoice_date': '2026-06-01',
            'invoice_line_ids': [(0, 0, {
                'name': 'Approval evidence line',
                'quantity': 1,
                'price_unit': amount,
                'account_id': self.expense_account.id,
                'tax_ids': [(5, 0, 0)],
            })],
        })

    def _request(self, amount=100.0):
        bill = self._bill(amount)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        request.invalidate_recordset()
        return bill, request

    def test_named_accounting_approver_gets_activity_and_can_approve(self):
        bill, request = self._request()
        self.assertFalse(
            self.named_approver.has_group(
                'eh_account_base.group_eh_user'
            )
        )
        self.assertFalse(request.pending_group_id)
        self.assertIn(self.named_approver, request.pending_group_user_ids)
        self.assertIn(self.named_approver, request.activity_ids.user_id)
        request.with_user(self.named_approver)._eh_check_access('read')
        request.with_user(self.named_approver).action_approve(
            comment='Named approver reviewed evidence',
        )
        self.assertEqual(request.state, 'approved')
        self.assertEqual(bill.state, 'draft')

    def test_cron_sql_failure_isolated_by_savepoint(self):
        _bad_bill, bad = self._request(101.0)
        _good_bill, good = self._request(102.0)
        seen = []
        model_class = type(self.Request)

        def failing_step(record, now):
            if record.id == bad.id:
                record.env.cr.execute('SELECT 1 / 0')
            elif record.id == good.id:
                seen.append(record.id)

        with patch.object(model_class, '_eh_sla_step', failing_step):
            self.Request._cron_sla_sweep()
        self.assertEqual(seen, [good.id])
        self.env.cr.execute('SELECT 1')
        self.assertEqual(self.env.cr.fetchone(), (1,))

    def test_move_with_approval_history_has_controlled_delete_error(self):
        bill, request = self._request()
        self.assertTrue(request.log_ids)
        with self.assertRaisesRegex(UserError, 'has approval history'):
            bill.unlink()
        self.assertTrue(bill.exists())

    def test_approval_amount_uses_company_currency(self):
        foreign = self.env['res.currency'].with_context(
            active_test=False,
        ).search([
            ('id', '!=', self.company.currency_id.id),
        ], limit=1)
        self.assertTrue(foreign)
        foreign.active = True
        bill = self._bill(100.0, currency=foreign)
        bill.action_eh_request_approval()
        request = bill.eh_active_approval_request_id
        self.assertEqual(request.currency_id, self.company.currency_id)
        self.assertNotEqual(request.currency_id, bill.currency_id)

    def test_atomic_compare_and_set_has_asserted_stale_loser(self):
        _bill, request = self._request()
        self.assertTrue(request._eh_advance_step_atomic(expected_step=0))
        self.assertFalse(request._eh_advance_step_atomic(expected_step=0))
        request.invalidate_recordset(['current_step'])
        self.assertEqual(request.current_step, 1)

    def test_policy_gap_edit_invalidates_without_rollback(self):
        bill, request = self._request(200.0)
        request.with_user(self.named_approver).action_approve(
            comment='Approved original amount',
        )
        self.policy.rule_ids.min_amount = 1000.0
        bill.invoice_line_ids.price_unit = 50.0
        request.invalidate_recordset(['state'])
        self.assertEqual(request.state, 'withdrawn')
        self.assertEqual(bill.invoice_line_ids.price_unit, 50.0)
        self.assertTrue(request.log_ids.filtered(
            lambda log: log.action == 'invalidated',
        ))
        with self.assertRaisesRegex(UserError, 'no approval rule covering'):
            bill.action_post()

    def test_corrupt_snapshot_does_not_break_list_computes_but_blocks_action(self):
        _bill, request = self._request()
        self.env.cr.execute(
            "UPDATE eh_approval_request "
            "SET approval_snapshot_hash = 'tampered' WHERE id = %s",
            (request.id,),
        )
        request.invalidate_recordset()
        request._compute_due_at()
        request._compute_sla_state()
        request._compute_pending_group()
        self.assertFalse(request.due_at)
        self.assertEqual(request.sla_state, 'na')
        self.assertFalse(request.pending_group_user_ids)
        with self.assertRaisesRegex(UserError, 'integrity'):
            request.action_approve(comment='Must remain blocked')

    def test_submission_rejects_unattainable_minimum(self):
        step = self.policy.rule_ids.step_ids
        step.approval_minimum = 2
        bill = self._bill()
        amount = bill._eh_amount_for_approval()
        request = self.Request.create({
            'move_id': bill.id,
            'policy_id': self.policy.id,
            'rule_id': self.policy.rule_ids.id,
            'submitted_amount': amount,
        })
        with self.assertRaisesRegex(UserError, 'requires 2 distinct'):
            request.action_submit()

    def test_decision_wizard_requires_and_persists_comment(self):
        _bill, request = self._request()
        action = request.action_open_approve_wizard()
        self.assertEqual(
            action['res_model'], 'eh.approval.decision.wizard',
        )
        wizard = self.env['eh.approval.decision.wizard'].with_user(
            self.named_approver,
        ).create({
            'request_id': request.id,
            'decision': 'approve',
            'comment': 'Checked invoice and supporting contract',
        })
        wizard.action_confirm()
        request.invalidate_recordset()
        self.assertEqual(request.state, 'approved')
        self.assertEqual(
            request.vote_ids.comment,
            'Checked invoice and supporting contract',
        )
        self.assertIn(
            'Checked invoice and supporting contract',
            request.log_ids.mapped('comment'),
        )

    def test_request_view_prevents_drag_and_freezes_payload(self):
        root = Path(get_module_path('eh_account_approval'))
        xml = ElementTree.parse(
            root / 'views/approval_request_views.xml',
        ).getroot()
        kanban = xml.find('.//kanban')
        self.assertEqual(kanban.attrib.get('records_draggable'), 'false')
        for name in (
            'request_reference', 'request_partner_id',
            'request_date', 'request_note',
        ):
            field = xml.find(".//form//field[@name='%s']" % name)
            modifier = field.attrib.get('readonly', '') + field.attrib.get(
                'attrs', '',
            )
            self.assertIn('state', modifier)
        self.assertIsNotNone(
            xml.find(
                ".//button[@name='action_open_approve_wizard']"
            )
        )
        self.assertIsNotNone(
            xml.find(
                ".//button[@name='action_open_reject_wizard']"
            )
        )

    def test_root_policy_is_branch_fallback(self):
        if 'root_id' not in self.env['res.company']._fields:
            return
        branch = self._create_accounting_branch({
            'name': 'Approval policy branch',
            'parent_id': self.company.id,
        })
        bill = self._bill(100.0, company=branch)
        self.assertEqual(self.Policy.find_for_move(bill), self.policy)

    def test_currency_precision_governs_band_and_materiality(self):
        rule = self.policy.rule_ids
        rule.min_amount = 100.004
        self.assertEqual(self.policy.find_matching_rule(100.001), rule)
        _bill, request = self._request(100.001)
        self.assertFalse(request.detect_material_change(100.004))

    def test_deleted_snapshot_escalation_group_is_consumed_once(self):
        target = self.env['res.groups'].create({
            'name': 'Disposable escalation target',
        })
        rule = self.policy.rule_ids
        rule.write({
            'sla_hours': 1,
            'escalate_after_hours': 1,
            'escalate_to_group_id': target.id,
        })
        _bill, request = self._request()
        target.unlink()
        old = fields.Datetime.now() - timedelta(hours=4)
        request.sudo().write({'submitted_at': old})
        request.invalidate_recordset()
        request._compute_due_at()
        request._eh_sla_step(fields.Datetime.now())
        request.invalidate_recordset(['last_escalated_at'])
        self.assertTrue(request.last_escalated_at)

    def test_post_time_rejection_does_not_claim_rolled_back_reset(self):
        bill, request = self._request(200.0)
        request.with_user(self.named_approver).action_approve(
            comment='Approved original rule',
        )
        replacement = self.env['eh.approval.policy.rule'].create({
            'policy_id': self.policy.id,
            'name': 'New higher-priority band',
            'sequence': 0,
            'min_amount': 0.0,
            'max_amount': 0.0,
            'step_ids': [(0, 0, {
                'approver_ids': [(6, 0, [self.named_approver.id])],
            })],
        })
        self.assertEqual(self.policy.find_matching_rule(200.0), replacement)
        with self.assertRaisesRegex(UserError, 'Approval evidence is stale'):
            bill._eh_check_re_approval_after_edit(raise_on_reset=True)
        request.invalidate_recordset(['state'])
        self.assertEqual(request.state, 'approved')
        self.assertFalse(request.log_ids.filtered(
            lambda log: log.action == 'reset'
        ))

    def test_cron_reminder_uses_shipped_email_template(self):
        _bill, request = self._request()
        before = self.env['mail.mail'].search_count([
            ('subject', 'ilike', 'approval awaiting your sign-off'),
        ])
        request._eh_post_reminder(manual=False)
        after = self.env['mail.mail'].search_count([
            ('subject', 'ilike', 'approval awaiting your sign-off'),
        ])
        self.assertGreater(after, before)

    def test_reminder_template_migration_is_targeted_and_idempotent(self):
        root = Path(get_module_path('eh_account_approval'))
        manifest = ast.literal_eval((root / '__manifest__.py').read_text())
        migration_path = (
            root / 'migrations' / manifest['version'] / 'post-migration.py'
        )
        spec = importlib.util.spec_from_file_location(
            'eh_account_approval_128_post_migration', migration_path,
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        template = self.env.ref(
            'eh_account_approval.email_template_eh_approval_reminder',
        ).sudo()
        legacy = "{{ (object.company_id.email or user.email) | safe }}"
        current = "{{ object.company_id.email or user.email }}"

        template.email_from = legacy
        template.flush_recordset(['email_from'])
        migration.migrate(self.env.cr, manifest['version'])
        template.invalidate_recordset(['email_from'])
        self.assertEqual(template.email_from, current)
        migration.migrate(self.env.cr, manifest['version'])
        template.invalidate_recordset(['email_from'])
        self.assertEqual(template.email_from, current)

        customised = "{{ object.company_id.email or 'ap@example.invalid' }}"
        template.email_from = customised
        template.flush_recordset(['email_from'])
        migration.migrate(self.env.cr, manifest['version'])
        migration.migrate(self.env.cr, manifest['version'])
        template.invalidate_recordset(['email_from'])
        self.assertEqual(template.email_from, customised)

    def test_acl_and_metadata_match_immutable_evidence_contract(self):
        root = Path(get_module_path('eh_account_approval'))
        with (root / 'security/ir.model.access.csv').open() as stream:
            rows = {row['id']: row for row in csv.DictReader(stream)}
        self.assertIn('access_eh_approval_policy_rule_auditor', rows)
        self.assertEqual(rows['access_eh_approval_log_user']['perm_write'], '0')
        self.assertEqual(
            rows['access_eh_approval_log_manager']['perm_write'], '0',
        )
        vote_source = (root / 'models/approval_vote.py').read_text()
        self.assertNotIn('_EVIDENCE_FIELDS', vote_source)
        manifest = ast.literal_eval((root / '__manifest__.py').read_text())
        listing = (root / 'static/description/index.html').read_text()
        self.assertIn('v%s' % manifest['version'], listing)
        self.assertNotIn('only the comment is writable', listing.lower())
        self.assertNotIn('ordered single-group steps', listing.lower())
