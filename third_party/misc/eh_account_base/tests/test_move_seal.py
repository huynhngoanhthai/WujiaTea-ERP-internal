# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Inalterability seal on posted sub-ledger GL entries.

A move stamped eh_sealed by an ERP Heritage sub-ledger cannot, once posted, be
reset to draft or cancelled, nor can its figures be edited / added / removed in
place; sanctioned reversal paths carry an unforgeable in-process capability.
A move that is NOT sealed (a normal journal entry / invoice) is unaffected.
"""

import base64
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch

from odoo import Command, fields, SUPERUSER_ID
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged

from odoo.addons.eh_account_base.tests.common import (
    EhAccountIntegrationTestCase,
)


@tagged('eh_account_base', 'integration', 'post_install', '-at_install')
class TestMoveSeal(EhAccountIntegrationTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account_user = new_test_user(
            cls.env,
            login='eh_move_seal_security_user',
            groups='eh_account_base.group_eh_user',
        )
        cls.account_manager = new_test_user(
            cls.env,
            login='eh_move_seal_manager_user',
            groups='eh_account_base.group_eh_manager',
        )
        cls.account_manager.email = 'eh-move-seal-manager@example.com'
        cls.readonly_auditor = new_test_user(
            cls.env,
            login='eh_move_seal_readonly_auditor',
            groups='eh_account_base.group_eh_auditor',
        )
        migration_path = (
            Path(__file__).parents[1]
            / 'migrations' / '19.0.1.7.4' / 'post-migration.py'
        )
        spec = spec_from_file_location(
            'eh_account_base_post_migration_174', migration_path,
        )
        cls.migration_174 = module_from_spec(spec)
        spec.loader.exec_module(cls.migration_174)
        migration_path = (
            Path(__file__).parents[1]
            / 'migrations' / '19.0.1.7.5' / 'post-migration.py'
        )
        spec = spec_from_file_location(
            'eh_account_base_post_migration_175', migration_path,
        )
        cls.migration_175 = module_from_spec(spec)
        spec.loader.exec_module(cls.migration_175)
        migration_path = (
            Path(__file__).parents[1]
            / 'migrations' / '19.0.1.7.6' / 'post-migration.py'
        )
        spec = spec_from_file_location(
            'eh_account_base_post_migration_176', migration_path,
        )
        cls.migration_176 = module_from_spec(spec)
        spec.loader.exec_module(cls.migration_176)
        migration_path = (
            Path(__file__).parents[1]
            / 'migrations' / '19.0.1.7.8' / 'post-migration.py'
        )
        spec = spec_from_file_location(
            'eh_account_base_post_migration_178', migration_path,
        )
        cls.migration_178 = module_from_spec(spec)
        spec.loader.exec_module(cls.migration_178)

    def _posted_move(self):
        return self.post_balanced_move([
            {'account': self.account_expense, 'debit': 100.0},
            {'account': self.account_cash, 'credit': 100.0},
        ])

    def _generate_test_invoice_pdf(self, move):
        if 'account.move.send' not in self.env:
            self.skipTest('core invoice-send model is unavailable')
        SendClass = type(self.env['account.move.send'])

        def _fake_prepare_pdf(send_model, invoices_data, invoice_data=None):
            if invoice_data is not None:
                invoices_data = {invoices_data: invoice_data}
            for invoice, invoice_data in invoices_data.items():
                invoice_data['pdf_attachment_values'] = {
                    'name': invoice._get_invoice_report_filename(),
                    'raw': b'%PDF-1.4\nsealed invoice test\n%%EOF',
                    'mimetype': 'application/pdf',
                    'res_model': invoice._name,
                    'res_id': invoice.id,
                    'res_field': 'invoice_pdf_report_file',
                }

        # Keep PDF/security regressions independent of a local wkhtmltopdf
        # process. The unmocked core linking/sending path still creates the
        # legal attachment and writes every server-owned move field.
        with patch.object(
            SendClass,
            '_prepare_invoice_pdf_report',
            _fake_prepare_pdf,
        ):
            send_model = self.env['account.move.send']
            if hasattr(send_model, '_generate_and_send_invoices'):
                return send_model._generate_and_send_invoices(
                    move,
                    sending_methods=['manual'],
                )
            if hasattr(send_model, '_process_send_and_print'):
                wizard = send_model.with_context(
                    active_model='account.move',
                    active_ids=move.ids,
                ).create({
                    'move_ids': [Command.set(move.ids)],
                })
                return wizard.action_send_and_print(force_synchronous=True)
            self.skipTest('core invoice-send PDF corridor is unavailable')

    def test_unsealed_move_is_unaffected(self):
        move = self._posted_move()
        self.assertFalse(move.eh_sealed)
        move.button_draft()
        self.assertEqual(move.state, 'draft')

    def test_draft_line_parent_projection_is_server_owned(self):
        move = self._posted_move()
        move.button_draft()
        line = move.line_ids[0]
        self.assertEqual(line.parent_state, 'draft')
        with self.assertRaises(AccessError):
            line.sudo().write({'parent_state': 'posted'})
        line.invalidate_recordset(['parent_state'])
        self.assertEqual(line.parent_state, 'draft')

        with self.assertRaises(AccessError):
            self.env['account.move.line'].sudo().create({
                'move_id': move.id,
                'name': 'Forged parent projection',
                'account_id': self.account_expense.id,
                'debit': 0.0,
                'credit': 0.0,
                'parent_state': 'posted',
            })

    def test_exact_core_line_projections_are_sanitised_on_create(self):
        move = self._posted_move()
        move.button_draft()
        line = self.env['account.move.line'].create({
            'move_id': move.id,
            'name': 'Exact redundant core projections',
            'account_id': self.account_expense.id,
            'debit': 0.0,
            'credit': 0.0,
            'company_id': move.company_id.id,
            'company_currency_id': move.company_currency_id.id,
            'journal_id': move.journal_id.id,
            'date': move.date,
            'parent_state': move.state,
        })
        self.assertEqual(line.company_id, move.company_id)
        self.assertEqual(line.company_currency_id, move.company_currency_id)
        self.assertEqual(line.journal_id, move.journal_id)
        self.assertEqual(line.date, move.date)
        self.assertEqual(line.parent_state, 'draft')
        line.write({
            'name': 'Exact redundant projections on update',
            'company_id': move.company_id.id,
            'company_currency_id': move.company_currency_id.id,
            'parent_state': move.state,
        })
        self.assertEqual(line.name, 'Exact redundant projections on update')
        self.assertEqual(line.company_id, move.company_id)
        self.assertEqual(line.parent_state, 'draft')

        context_line = self.env['account.move.line'].with_context(
            default_move_id=move.id,
            default_parent_state='posted',
            default_company_id=move.company_id.id,
        ).create({
            'name': 'Context-default projections are discarded',
            'account_id': self.account_expense.id,
            'debit': 0.0,
            'credit': 0.0,
        })
        self.assertEqual(context_line.move_id, move)
        self.assertEqual(context_line.parent_state, 'draft')
        self.assertEqual(context_line.company_id, move.company_id)

        with self.assertRaises(AccessError):
            self.env['account.move.line'].with_user(
                self.readonly_auditor,
            ).with_context(default_move_id=move.id).create({
                'name': 'Denied default destination',
                'account_id': self.account_expense.id,
                'debit': 0.0,
                'credit': 0.0,
            })

    def test_server_owned_create_defaults_cannot_preseed_evidence(self):
        parent = self.env['res.partner'].create({
            'name': 'Context-default commercial parent',
            'is_company': True,
        })
        forged_root = self.env['res.partner'].create({
            'name': 'Context-default forged root',
            'is_company': True,
        })
        child = self.env['res.partner'].with_context(
            default_parent_id=parent.id,
            default_commercial_partner_id=forged_root.id,
            default_commercial_company_name='Forged company name',
        ).create({'name': 'Context-default child'})
        self.assertEqual(child.commercial_partner_id, parent)
        self.assertEqual(child.commercial_company_name, parent.name)

        IrDefault = self.env['ir.default']
        IrDefault.set(
            'res.partner', 'commercial_partner_id', forged_root.id,
            user_id=True,
        )
        ir_child = self.env['res.partner'].create({
            'name': 'ir.default commercial child',
            'parent_id': parent.id,
        })
        self.assertEqual(ir_child.commercial_partner_id, parent)

        IrDefault.set(
            'res.company', 'eh_move_version', 99, user_id=True,
        )
        safe_company = self.env['res.company'].create({
            'name': 'Safe default report version company',
        })
        self.env.cr.execute(
            "SELECT version FROM eh_account_report_company_version "
            "WHERE company_id = %s",
            (safe_company.id,),
        )
        local_version = self.env.cr.fetchone()[0]
        self.env.cr.execute(
            "SELECT COALESCE(version, 0) "
            "FROM eh_account_report_global_version WHERE id = 1"
        )
        global_version = self.env.cr.fetchone()[0]
        self.assertEqual(local_version, 1)
        self.assertEqual(
            safe_company.eh_move_version,
            local_version + global_version,
        )

        IrDefault.set('account.move', 'eh_sealed', True, user_id=True)
        safe_move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'date': '2026-01-01',
        })
        self.assertFalse(safe_move.eh_sealed)

        IrDefault.set(
            'account.move.line', 'parent_state', 'posted', user_id=True,
        )
        safe_line = self.env['account.move.line'].create({
            'move_id': safe_move.id,
            'name': 'Safe ir.default line projection',
            'account_id': self.account_expense.id,
            'debit': 0.0,
            'credit': 0.0,
        })
        self.assertEqual(safe_line.parent_state, 'draft')

        with self.assertRaises(AccessError):
            self.env['res.company'].with_context(
                default_eh_move_version=99,
            ).create({'name': 'Forged report version company'})

        with self.assertRaises(AccessError):
            self.env['account.move'].with_context(
                default_eh_sealed=True,
            ).create({
                'move_type': 'entry',
                'journal_id': self.journal_misc.id,
                'date': '2026-01-01',
            })

    def test_move_commercial_partner_projection_is_server_owned(self):
        parent = self.env['res.partner'].create({
            'name': 'Move commercial parent',
            'is_company': True,
        })
        child = self.env['res.partner'].create({
            'name': 'Move commercial child',
            'parent_id': parent.id,
        })
        forged = self.env['res.partner'].create({
            'name': 'Forged move commercial parent',
            'is_company': True,
        })
        exact = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'date': '2026-01-01',
            'partner_id': child.id,
            'commercial_partner_id': parent.id,
        })
        self.assertEqual(exact.commercial_partner_id, parent)
        with self.assertRaises(AccessError):
            self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': self.journal_misc.id,
                'date': '2026-01-01',
                'partner_id': child.id,
                'commercial_partner_id': forged.id,
            })
        move = self._posted_move()
        move.button_draft()
        move.partner_id = child
        self.assertEqual(move.commercial_partner_id, parent)
        with self.assertRaises(AccessError):
            move.write({'commercial_partner_id': forged.id})
        self.assertEqual(move.commercial_partner_id, parent)

    def test_partner_reparent_refreshes_posted_move_projections(self):
        old_parent = self.env['res.partner'].create({
            'name': 'Old commercial parent', 'is_company': True,
        })
        new_parent = self.env['res.partner'].create({
            'name': 'New commercial parent', 'is_company': True,
        })
        child = self.env['res.partner'].create({
            'name': 'Reparented accounting contact',
            'parent_id': old_parent.id,
        })
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'date': '2026-01-01',
            'partner_id': child.id,
            'line_ids': [
                (0, 0, {
                    'name': 'Partner reparent debit',
                    'account_id': self.account_expense.id,
                    'partner_id': child.id,
                    'debit': 100.0,
                }),
                (0, 0, {
                    'name': 'Partner reparent credit',
                    'account_id': self.account_cash.id,
                    'partner_id': child.id,
                    'credit': 100.0,
                }),
            ],
        })
        move.action_post()

        child.write({'parent_id': new_parent.id})

        move.invalidate_recordset(['commercial_partner_id'])
        move.line_ids.invalidate_recordset(['partner_id'])
        self.assertEqual(move.commercial_partner_id, new_parent)
        self.assertEqual(set(move.line_ids.mapped('partner_id')), {new_parent})

    def test_partner_hierarchy_refreshes_header_only_move_projection(self):
        old_parent = self.env['res.partner'].create({
            'name': 'Header-only old root', 'is_company': True,
        })
        new_parent = self.env['res.partner'].create({
            'name': 'Header-only new root', 'is_company': True,
        })
        child = self.env['res.partner'].create({
            'name': 'Header-only move contact', 'parent_id': old_parent.id,
        })
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'date': '2026-01-01',
            'partner_id': child.id,
        })

        child.write({'parent_id': new_parent.id})
        move.invalidate_recordset(['commercial_partner_id'])
        self.assertEqual(move.commercial_partner_id, new_parent)

        child.write({'is_company': True})
        move.invalidate_recordset(['commercial_partner_id'])
        self.assertEqual(move.commercial_partner_id, child)

    def test_archived_partner_reparent_refreshes_header_projection(self):
        old_parent = self.env['res.partner'].create({
            'name': 'Archived contact old root', 'is_company': True,
        })
        new_parent = self.env['res.partner'].create({
            'name': 'Archived contact new root', 'is_company': True,
        })
        child = self.env['res.partner'].create({
            'name': 'Archived move contact', 'parent_id': old_parent.id,
        })
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'date': '2026-01-01',
            'partner_id': child.id,
        })
        child.active = False

        child.write({'parent_id': new_parent.id})

        move.invalidate_recordset(['commercial_partner_id'])
        self.assertEqual(move.commercial_partner_id, new_parent)

    def test_expense_authority_changes_refresh_move_commercial_projection(self):
        if 'hr.expense' not in self.env.registry:
            self.skipTest('hr_expense is not installed')
        employee_partner = self.env['res.partner'].create({
            'name': 'Expense commercial projection employee',
            'parent_id': self.company.partner_id.id,
        })
        employee = self.env['hr.employee'].sudo().create({
            'name': 'Expense commercial projection employee',
            'company_id': self.company.id,
            'work_contact_id': employee_partner.id,
        })
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'date': '2026-01-01',
            'partner_id': employee_partner.id,
        })
        Expense = self.env['hr.expense'].sudo()
        expense_vals = {
            'name': 'Commercial projection dependency expense',
            'employee_id': employee.id,
            'company_id': self.company.id,
            'currency_id': self.company.currency_id.id,
            'payment_mode': 'own_account',
        }
        amount_field = (
            'total_amount_currency'
            if 'total_amount_currency' in Expense._fields else
            'total_amount'
        )
        expense_vals[amount_field] = 100.0
        if 'account_move_id' in Expense._fields:
            # Odoo 19 links expenses directly to their journal entry.
            expense_vals['account_move_id'] = move.id
            expense = Expense.create(expense_vals)
        else:
            # Odoo 16--18 route the authority through an expense sheet.
            expense = Expense.create(expense_vals)
            sheet = self.env['hr.expense.sheet'].sudo().create({
                'name': 'Commercial projection dependency sheet',
                'employee_id': employee.id,
                'company_id': self.company.id,
                'expense_line_ids': [Command.link(expense.id)],
            })
            expense_sheet_field = move._fields['expense_sheet_id']
            if expense_sheet_field.type == 'many2one':
                move.with_context(skip_is_manually_modified=True).write({
                    'expense_sheet_id': sheet.id,
                })
            else:
                sheet.write({'account_move_id': move.id})
        move.invalidate_recordset(['commercial_partner_id'])
        self.assertEqual(move.commercial_partner_id, employee_partner)

        expense.write({'payment_mode': 'company_account'})
        move.invalidate_recordset(['commercial_partner_id'])
        self.assertEqual(
            move.commercial_partner_id, self.company.partner_id,
        )

        expense.write({'payment_mode': 'own_account'})
        move.invalidate_recordset(['commercial_partner_id'])
        self.assertEqual(move.commercial_partner_id, employee_partner)
        replacement_identity = self.env['res.partner'].create({
            'name': 'Replacement expense company identity',
            'is_company': True,
        })
        original_identity = self.company.partner_id
        self.company.write({'partner_id': replacement_identity.id})
        move.invalidate_recordset(['commercial_partner_id'])
        self.assertEqual(move.commercial_partner_id, original_identity)
        if 'is_manually_modified' in move._fields:
            move.invalidate_recordset(['is_manually_modified'])
            self.assertFalse(move.is_manually_modified)

    def test_partner_reparent_cannot_rewrite_verified_sealed_lines(self):
        old_parent = self.env['res.partner'].create({
            'name': 'Sealed old commercial parent', 'is_company': True,
        })
        new_parent = self.env['res.partner'].create({
            'name': 'Sealed new commercial parent', 'is_company': True,
        })
        child = self.env['res.partner'].create({
            'name': 'Sealed accounting contact',
            'parent_id': old_parent.id,
        })
        move = self.env['account.move']._eh_create_sealed({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'date': '2026-01-01',
            'partner_id': child.id,
            'eh_sealed': True,
            'line_ids': [
                (0, 0, {
                    'name': 'Sealed partner debit',
                    'account_id': self.account_expense.id,
                    'partner_id': child.id,
                    'debit': 100.0,
                }),
                (0, 0, {
                    'name': 'Sealed partner credit',
                    'account_id': self.account_cash.id,
                    'partner_id': child.id,
                    'credit': 100.0,
                }),
            ],
        })
        move.action_post()
        original_line_partners = move.line_ids.mapped('partner_id')

        with self.assertRaises(UserError), self.env.cr.savepoint():
            child.write({'parent_id': new_parent.id})

        child.invalidate_recordset(['parent_id'])
        move.line_ids.invalidate_recordset(['partner_id'])
        self.assertEqual(child.parent_id, old_parent)
        self.assertEqual(
            move.line_ids.mapped('partner_id'), original_line_partners,
        )

    def test_commercial_partner_projection_is_server_owned(self):
        parent = self.env['res.partner'].create({
            'name': 'Authoritative commercial parent',
            'is_company': True,
        })
        child = self.env['res.partner'].create({
            'name': 'Authoritative child contact',
            'parent_id': parent.id,
        })
        attacker_root = self.env['res.partner'].create({
            'name': 'Unrelated forged commercial parent',
            'is_company': True,
        })
        self.assertEqual(child.commercial_partner_id, parent)
        with self.assertRaises(AccessError):
            child.sudo().write({
                'commercial_partner_id': attacker_root.id,
            })
        child.invalidate_recordset(['commercial_partner_id'])
        self.assertEqual(child.commercial_partner_id, parent)

    def test_178_migration_repairs_stored_source_projections(self):
        move = self._posted_move()
        move.button_draft()
        line = move.line_ids[0]
        parent = self.env['res.partner'].create({
            'name': 'Migration commercial parent',
            'is_company': True,
        })
        child = self.env['res.partner'].create({
            'name': 'Migration commercial child',
            'parent_id': parent.id,
        })
        forged_root = self.env['res.partner'].create({
            'name': 'Migration forged root',
            'is_company': True,
        })
        move.partner_id = child
        self.assertEqual(move.commercial_partner_id, parent)
        self.env.flush_all()
        self.company.invalidate_recordset(['eh_move_version'])
        version_before = self.company.eh_move_version
        self.env.cr.execute(
            "UPDATE account_move_line SET parent_state = 'posted' "
            "WHERE id = %s",
            (line.id,),
        )
        self.env.cr.execute(
            "UPDATE res_partner SET commercial_partner_id = %s "
            "WHERE id = %s",
            (forged_root.id, child.id),
        )
        self.env.cr.execute(
            "UPDATE account_move SET commercial_partner_id = %s "
            "WHERE id = %s",
            (forged_root.id, move.id),
        )

        self.migration_178.migrate(self.env.cr, '19.0.1.7.7')
        self.env.invalidate_all()

        self.assertEqual(line.parent_state, 'draft')
        self.assertEqual(child.commercial_partner_id, parent)
        self.assertEqual(move.commercial_partner_id, parent)
        self.assertGreater(self.company.eh_move_version, version_before)

    def test_main_attachment_hook_accepts_old_and_new_keywords(self):
        move = self._posted_move()
        empty_attachments = self.env['ir.attachment']
        move._message_set_main_attachment_id(
            attachment_ids=empty_attachments,
        )
        move._message_set_main_attachment_id(
            attachments=empty_attachments,
        )
        self.assertFalse(move.message_main_attachment_id)

    def test_source_can_create_sealed_draft_then_post(self):
        move = self.env['account.move']._eh_create_sealed({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'date': '2026-01-01',
            'eh_sealed': True,
            'line_ids': [
                (0, 0, {
                    'account_id': self.account_expense.id,
                    'debit': 25.0,
                    'name': 'sealed debit',
                }),
                (0, 0, {
                    'account_id': self.account_cash.id,
                    'credit': 25.0,
                    'name': 'sealed credit',
                }),
            ],
        })
        self.assertEqual(move.state, 'draft')
        self.assertTrue(move.eh_sealed)
        self.assertFalse(move.eh_legacy_unverified_seal)
        with self.assertRaises(UserError):
            move.write({'ref': 'raw draft mutation'})
        with self.assertRaises(UserError):
            move.line_ids[0].write({'name': 'raw line mutation'})
        with self.assertRaises(UserError):
            move.with_context(force_delete=True).unlink()
        move.action_post()
        self.assertEqual(move.state, 'posted')
        self.assertTrue(move.eh_sealed)

    def test_caught_sealed_create_stamp_failure_leaves_no_draft(self):
        MoveClass = type(self.env['account.move'])
        reference = 'CAUGHT SEALED CREATE FAILURE'
        caught = None
        try:
            with patch.object(
                MoveClass,
                '_eh_stamp_verified_seal',
                side_effect=UserError('injected stamp failure'),
            ):
                self.env['account.move']._eh_create_sealed({
                    'move_type': 'entry',
                    'journal_id': self.journal_misc.id,
                    'date': '2026-01-01',
                    'ref': reference,
                    'line_ids': [
                        (0, 0, {
                            'account_id': self.account_expense.id,
                            'debit': 25.0,
                        }),
                        (0, 0, {
                            'account_id': self.account_cash.id,
                            'credit': 25.0,
                        }),
                    ],
                })
        except UserError as error:
            caught = error
        self.assertIsNotNone(caught)
        self.assertFalse(self.env['account.move'].search([
            ('ref', '=', reference),
        ]))

    def test_legacy_rpc_writable_seal_is_frozen_but_never_trusted(self):
        move = self._posted_move()
        original_name = move.name
        self.env.flush_all()
        # Reproduce a pre-1.7.4 row whose seal could have been forged through
        # RPC. A valid-looking posted shape must not be blessed by migration.
        self.env.cr.execute(
            "UPDATE account_move SET eh_sealed = TRUE, "
            "eh_legacy_unverified_seal = FALSE WHERE id = %s",
            (move.id,),
        )
        self.migration_174.migrate(self.env.cr, '19.0.1.7.3')
        self.env.invalidate_all()

        self.assertFalse(move.eh_sealed)
        self.assertTrue(move.eh_legacy_unverified_seal)
        self.assertEqual(move.name, original_name)
        self.assertEqual(move.state, 'posted')
        with self.assertRaises(UserError):
            move.write({'ref': 'forged legacy rewrite'})
        with self.assertRaises(UserError):
            move.line_ids[0].write({'debit': 1.0})
        with self.assertRaises(UserError):
            move.with_context(force_delete=True).unlink()
        with self.assertRaises(UserError):
            move._eh_stamp_verified_seal()
        with self.assertRaises(UserError):
            move._reverse_moves()
        with self.assertRaises(UserError):
            move._eh_reverse_with_verified_capability()
        with self.assertRaises(UserError):
            move.sudo().with_context(eh_seal_internal=True).write({
                'eh_sealed': True,
            })
        self.assertFalse(move.eh_sealed)
        self.assertTrue(move.eh_legacy_unverified_seal)

    def test_manager_posts_exact_sealed_counterentry_for_legacy_quarantine(self):
        source = self._posted_move()
        original_name = source.name
        original_lines = {
            line.id: (
                line.account_id.id,
                line.debit,
                line.credit,
                line.balance,
            )
            for line in source.line_ids
        }
        self.env.flush_all()
        # Reproduce the historical condition through its real migration: the
        # original is preserved but can never be promoted as trusted evidence.
        self.env.cr.execute(
            "UPDATE account_move SET eh_sealed = TRUE, "
            "eh_legacy_unverified_seal = FALSE WHERE id = %s",
            (source.id,),
        )
        self.migration_174.migrate(self.env.cr, '19.0.1.7.3')
        self.env.invalidate_all()
        self.assertFalse(source.eh_sealed)
        self.assertTrue(source.eh_legacy_unverified_seal)

        manager_source = source.with_user(self.account_manager)
        action = manager_source.action_eh_reverse_legacy_quarantine()
        self.assertEqual(
            action['res_model'], 'eh.account.legacy.seal.reversal',
        )
        wizard = self.env[
            'eh.account.legacy.seal.reversal'
        ].with_user(self.account_manager).create({
            'move_id': source.id,
            'date': '2026-01-02',
            'reason': 'Reviewed pre-provenance import and corrected in full',
        })
        result = wizard.action_reverse()
        reversal = self.env['account.move'].browse(result['res_id'])

        self.assertEqual(source.name, original_name)
        self.assertEqual(source.state, 'posted')
        self.assertFalse(source.eh_sealed)
        self.assertTrue(source.eh_legacy_unverified_seal)
        self.assertEqual({
            line.id: (
                line.account_id.id,
                line.debit,
                line.credit,
                line.balance,
            )
            for line in source.line_ids
        }, original_lines)
        self.assertEqual(reversal.state, 'posted')
        self.assertTrue(reversal.eh_sealed)
        self.assertFalse(reversal.eh_legacy_unverified_seal)
        self.assertEqual(reversal.reversed_entry_id, source)
        reversal._eh_validate_verified_reversal(
            source, allow_legacy_original=True,
        )
        self.assertIn(
            'Reviewed pre-provenance import',
            ' '.join(str(body) for body in source.message_ids.mapped('body')),
        )

        with self.assertRaises(UserError):
            manager_source.action_eh_reverse_legacy_quarantine()
        with self.assertRaises(UserError):
            manager_source._reverse_moves()
        with self.assertRaises(AccessError):
            source.with_user(
                self.account_user,
            ).action_eh_reverse_legacy_quarantine()

    def test_core_and_wizard_cannot_reverse_a_sealed_move(self):
        move = self._posted_move()
        move._eh_stamp_verified_seal()
        reversal_count = self.env['account.move'].search_count([
            ('reversed_entry_id', '=', move.id),
        ])

        with self.assertRaises(UserError):
            move._reverse_moves()
        # A forgeable context value is not the object capability.
        with self.assertRaises(UserError):
            move.with_context(
                eh_reverse_sealed_internal=True,
            )._reverse_moves()
        with self.assertRaises(UserError):
            move.line_ids.with_context(
                eh_reverse_sealed_internal=True,
            ).write({'name': 'forged reversal line edit'})

        wizard = self.env['account.move.reversal'].with_context(
            active_model='account.move',
            active_ids=move.ids,
        ).create({
            'move_ids': [(6, 0, move.ids)],
            'date': '2026-01-02',
            'journal_id': self.journal_misc.id,
            'company_id': self.company.id,
        })
        with self.assertRaises(UserError):
            wizard.reverse_moves()
        self.assertEqual(self.env['account.move'].search_count([
            ('reversed_entry_id', '=', move.id),
        ]), reversal_count)

    def test_sanctioned_reversal_is_linked_validated_and_sealed(self):
        move = self._posted_move()
        move._eh_stamp_verified_seal()

        reversal = move._eh_reverse_with_verified_capability([{
            'date': '2026-01-02',
            'ref': 'Controlled sealed reversal',
        }], cancel=False)

        self.assertEqual(reversal.state, 'draft')
        self.assertEqual(reversal.reversed_entry_id, move)
        self.assertTrue(reversal.eh_sealed)
        self.assertFalse(reversal.eh_legacy_unverified_seal)
        reversal._eh_validate_verified_reversal(move)
        with self.assertRaises(UserError):
            move._eh_reverse_with_verified_capability()
        with self.assertRaises(AccessError):
            reversal.write({'reversed_entry_id': False})
        with self.assertRaises(UserError):
            reversal.write({'ref': 'editable reversal escape'})

        reversal._eh_post_verified_reversal()
        self.assertEqual(reversal.state, 'posted')
        self.assertEqual(reversal.reversed_entry_id, move)
        self.assertTrue(reversal.eh_sealed)

    def test_caught_reversal_validation_failure_leaves_no_counter_entry(self):
        source = self._posted_move()
        source._eh_stamp_verified_seal()
        before = self.env['account.move'].search_count([
            ('reversed_entry_id', '=', source.id),
        ])
        MoveClass = type(self.env['account.move'])
        caught = None
        try:
            with patch.object(
                MoveClass,
                '_eh_validate_verified_reversal',
                side_effect=UserError('injected reversal-shape failure'),
            ):
                source._eh_reverse_with_verified_capability([{
                    'date': '2026-01-02',
                }], cancel=False)
        except UserError as error:
            caught = error
        self.assertIsNotNone(caught)
        self.assertEqual(self.env['account.move'].search_count([
            ('reversed_entry_id', '=', source.id),
        ]), before)

    def test_verified_reversal_rejects_reporting_dimension_drift(self):
        source_partner = self.env['res.partner'].create({
            'name': 'Verified reversal source partner',
        })
        forged_partner = self.env['res.partner'].create({
            'name': 'Forged reversal reporting partner',
        })
        source = self.post_balanced_move([
            {
                'account': self.account_expense,
                'debit': 100.0,
                'partner': source_partner,
            },
            {
                'account': self.account_cash,
                'credit': 100.0,
                'partner': source_partner,
            },
        ])
        source._eh_stamp_verified_seal()
        reversal = source._eh_reverse_with_verified_capability([{
            'date': '2026-01-02',
        }], cancel=False)
        reversal._eh_validate_verified_reversal(source)

        forged_line = reversal.line_ids.filtered(
            lambda line: line.account_id == self.account_expense
        )
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE account_move_line SET partner_id = %s WHERE id = %s",
            (forged_partner.id, forged_line.id),
        )
        forged_line.invalidate_recordset(['partner_id'])

        with self.assertRaises(UserError):
            reversal._eh_validate_verified_reversal(source)

    def test_verified_reversal_rejects_tax_tag_drift(self):
        source_tag = self.env['account.account.tag'].create({
            'name': 'Verified reversal source grid',
            'applicability': 'taxes',
        })
        forged_tag = self.env['account.account.tag'].create({
            'name': 'Verified reversal forged grid',
            'applicability': 'taxes',
        })
        source = self._posted_move()
        tagged_line = source.line_ids.filtered(
            lambda line: line.account_id == self.account_expense
        )
        tagged_line.write({'tax_tag_ids': [(6, 0, source_tag.ids)]})
        source._eh_stamp_verified_seal()
        reversal = source._eh_reverse_with_verified_capability([{
            'date': '2026-01-02',
        }], cancel=False)
        reversal._eh_validate_verified_reversal(source)
        forged_line = reversal.line_ids.filtered(
            lambda line: line.account_id == self.account_expense
        )

        self.env.flush_all()
        self.env.cr.execute(
            "INSERT INTO account_account_tag_account_move_line_rel "
            "(account_move_line_id, account_account_tag_id) VALUES (%s, %s)",
            (forged_line.id, forged_tag.id),
        )
        forged_line.invalidate_recordset(['tax_tag_ids'])

        with self.assertRaises(UserError):
            reversal._eh_validate_verified_reversal(source)

    def test_verified_tax_invoice_reversal_keeps_reporting_dimensions(self):
        partner = self.env['res.partner'].create({
            'name': 'Verified tax-invoice reversal partner',
        })
        tax_vals = {
            'name': 'Verified reversal 10 percent tax',
            'amount': 10.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'company_id': self.company.id,
        }
        if 'country_id' in self.env['account.tax']._fields:
            fiscal_country = getattr(
                self.company, 'account_fiscal_country_id', False,
            )
            if not fiscal_country:
                fiscal_country = (
                    self.company.country_id or self.env.ref('base.us')
                )
                self.company.account_fiscal_country_id = fiscal_country
            tax_vals['country_id'] = fiscal_country.id
        tax = self.env['account.tax'].create(tax_vals)
        source = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'journal_id': self.journal_sale.id,
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [(0, 0, {
                'name': 'Taxed verified-reversal line',
                'account_id': self.account_revenue.id,
                'quantity': 1.0,
                'price_unit': 100.0,
                'tax_ids': [(6, 0, tax.ids)],
            })],
        })
        source.action_post()
        source._eh_stamp_verified_seal()

        reversal = source._eh_reverse_with_verified_capability([{
            'date': '2026-01-02',
        }], cancel=False)

        self.assertEqual(reversal.move_type, 'out_refund')
        self.assertTrue(reversal.eh_sealed)
        reversal._eh_validate_verified_reversal(source)

    def test_verified_reversal_preserves_fx_and_discount_dimensions(self):
        eur = self.env.ref('base.EUR')
        if not eur.active:
            eur.sudo().active = True
        rate = self.env['res.currency.rate'].search([
            ('currency_id', '=', eur.id),
            ('company_id', '=', self.company.id),
            ('name', '=', '2026-01-01'),
        ], limit=1)
        if rate:
            rate.rate = 0.8
        else:
            self.env['res.currency.rate'].create({
                'currency_id': eur.id,
                'company_id': self.company.id,
                'name': '2026-01-01',
                'rate': 0.8,
            })
        source = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'journal_id': self.journal_sale.id,
            'invoice_date': '2026-01-01',
            'currency_id': eur.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Discounted foreign-currency line',
                'account_id': self.account_revenue.id,
                'quantity': 2.0,
                'price_unit': 62.75,
                'discount': 20.0,
                'tax_ids': [(6, 0, [])],
            })],
        })
        source.action_post()
        source._eh_stamp_verified_seal()

        reversal = source._eh_reverse_with_verified_capability([{
            'date': '2026-01-02',
        }], cancel=False)

        self.assertEqual(reversal.currency_id, eur)
        self.assertEqual(reversal.move_type, 'out_refund')
        self.assertTrue(reversal.line_ids.filtered(
            lambda line: line.discount == 20.0
        ))
        reversal._eh_validate_verified_reversal(source)

    def test_verified_reversal_preserves_cash_rounding_line(self):
        rounding = self.env['account.cash.rounding'].create({
            'name': 'Verified reversal cash rounding',
            'rounding': 0.05,
            'rounding_method': 'HALF-UP',
            'strategy': 'add_invoice_line',
            'profit_account_id': self.account_revenue.id,
            'loss_account_id': self.account_expense.id,
        })
        source = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'journal_id': self.journal_sale.id,
            'invoice_date': '2026-01-01',
            'invoice_cash_rounding_id': rounding.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Cash-rounded source line',
                'account_id': self.account_revenue.id,
                'quantity': 1.0,
                'price_unit': 100.03,
                'tax_ids': [(6, 0, [])],
            })],
        })
        source.action_post()
        source._eh_stamp_verified_seal()

        reversal = source._eh_reverse_with_verified_capability([{
            'date': '2026-01-02',
        }], cancel=False)

        self.assertTrue(source.line_ids.filtered(
            lambda line: line.display_type == 'rounding'
        ))
        self.assertTrue(reversal.line_ids.filtered(
            lambda line: line.display_type == 'rounding'
        ))
        self.assertEqual(
            reversal.line_ids.filtered(
                lambda line: line.display_type == 'rounding'
            ).account_id,
            source.line_ids.filtered(
                lambda line: line.display_type == 'rounding'
            ).account_id,
        )
        reversal._eh_validate_verified_reversal(source)

    def test_verified_reversal_preserves_storno_dimension(self):
        if 'account_storno' not in self.company._fields:
            self.skipTest('storno accounting is unavailable')
        self.company.account_storno = True
        source = self._posted_move()
        source._eh_stamp_verified_seal()

        reversal = source._eh_reverse_with_verified_capability([{
            'date': '2026-01-02',
        }], cancel=False)

        reversal._eh_validate_verified_reversal(source)
        self.assertEqual(
            {line.is_storno for line in reversal.line_ids},
            {not line.is_storno for line in source.line_ids},
        )

    def test_verified_reversal_posts_after_source_period_lock(self):
        source = self.post_balanced_move([
            {'account': self.account_expense, 'debit': 100.0},
            {'account': self.account_cash, 'credit': 100.0},
        ], date=fields.Date.from_string('2026-01-01'))
        source._eh_stamp_verified_seal()
        lock_field = (
            'hard_lock_date'
            if 'hard_lock_date' in self.company._fields
            else 'fiscalyear_lock_date'
        )
        self.company[lock_field] = fields.Date.from_string('2026-01-01')

        reversal = source._eh_reverse_with_verified_capability([{
            'date': '2026-01-02',
        }], cancel=False)
        reversal._eh_post_verified_reversal()

        self.assertEqual(reversal.state, 'posted')
        self.assertEqual(reversal.date, fields.Date.from_string('2026-01-02'))
        reversal._eh_validate_verified_reversal(source)

    def test_verified_reversal_keeps_secure_hash_journal_chain(self):
        journal = self._ensure_journal(
            self.env,
            self.company,
            'general',
            'VHRV',
            'Verified Hash Reversal',
        )
        if 'restrict_mode_hash_table' not in journal._fields:
            self.skipTest('secure-entry journal mode is unavailable')
        journal.restrict_mode_hash_table = True
        source = self.post_balanced_move([
            {'account': self.account_expense, 'debit': 100.0},
            {'account': self.account_cash, 'credit': 100.0},
        ], journal=journal, date=fields.Date.from_string('2026-01-01'))
        source._eh_stamp_verified_seal()

        reversal = source._eh_reverse_with_verified_capability([{
            'date': '2026-01-02',
        }], cancel=False)
        reversal._eh_post_verified_reversal()

        self.assertTrue(source.inalterable_hash)
        self.assertTrue(reversal.inalterable_hash)
        if source.secure_sequence_number:
            # Hash versions before v4 used a dedicated no-gap sequence.
            self.assertGreater(
                reversal.secure_sequence_number,
                source.secure_sequence_number,
            )
        else:
            # Odoo 19 hash v4 retired that sequence and chains entries by
            # their ordinary journal sequence instead.
            self.assertEqual(reversal.sequence_prefix, source.sequence_prefix)
            self.assertGreater(reversal.sequence_number, source.sequence_number)
        reversal._eh_validate_verified_reversal(source)

    def test_controlled_post_rejects_duplicate_reversal_graph(self):
        source = self._posted_move()
        first = source._reverse_moves([{
            'date': '2026-01-02',
            'ref': 'First historical reversal',
        }], cancel=False)
        second = source._reverse_moves([{
            'date': '2026-01-03',
            'ref': 'Second historical reversal',
        }], cancel=False)
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE account_move SET eh_sealed = TRUE "
            "WHERE id IN %s",
            (tuple(source.ids + first.ids + second.ids),),
        )
        (source | first | second).invalidate_recordset(['eh_sealed'])

        with self.assertRaises(UserError):
            first._eh_post_verified_reversal()
        self.assertEqual(first.state, 'draft')
        self.assertEqual(first.reversed_entry_id, source)
        self.assertEqual(second.reversed_entry_id, source)

    def test_raw_reversal_link_to_sealed_move_is_server_owned(self):
        move = self._posted_move()
        move._eh_stamp_verified_seal()
        with self.assertRaises(AccessError):
            self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': self.journal_misc.id,
                'date': '2026-01-02',
                'reversed_entry_id': move.id,
            })

        candidate = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'date': '2026-01-02',
        })
        with self.assertRaises(AccessError):
            candidate.write({'reversed_entry_id': move.id})
        self.assertFalse(candidate.reversed_entry_id)

    def test_175_upgrade_quarantines_old_unsealed_reversal_graph(self):
        # Reproduce the exact intermediate-1.7.4 gap: core creates the linked
        # reversal while the source is still ordinary, then the now-trusted
        # 1.7.4 helper seals only the original. The upgrade must not infer
        # trust for the plausible linked reversal.
        source = self._posted_move()
        reversal = source._reverse_moves([{
            'date': '2026-01-02',
            'ref': 'Old core unsealed reversal',
        }], cancel=False)
        with self.assertRaises(UserError):
            source._eh_stamp_verified_seal()
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE account_move SET eh_sealed = TRUE WHERE id = %s",
            (source.id,),
        )
        source.invalidate_recordset(['eh_sealed'])
        source_line_count = len(source.line_ids)
        reversal_line_count = len(reversal.line_ids)
        self.assertTrue(source.eh_sealed)
        self.assertFalse(reversal.eh_sealed)
        self.assertEqual(reversal.reversed_entry_id, source)

        self.env.flush_all()
        self.migration_175.migrate(self.env.cr, '19.0.1.7.4')
        self.env.invalidate_all()

        self.assertFalse(source.eh_sealed)
        self.assertTrue(source.eh_legacy_unverified_seal)
        self.assertFalse(reversal.eh_sealed)
        self.assertTrue(reversal.eh_legacy_unverified_seal)
        self.assertEqual(reversal.reversed_entry_id, source)
        self.assertEqual(len(source.line_ids), source_line_count)
        self.assertEqual(len(reversal.line_ids), reversal_line_count)
        with self.assertRaises(UserError):
            source.write({'ref': 'rewrite quarantined source'})
        with self.assertRaises(UserError):
            reversal.write({'ref': 'rewrite quarantined reversal'})
        with self.assertRaises(UserError):
            source._eh_reverse_with_verified_capability()

    def test_175_upgrade_keeps_complete_current_reversal_graph_verified(self):
        source = self._posted_move()
        source._eh_stamp_verified_seal()
        reversal = source._eh_reverse_with_verified_capability([{
            'date': '2026-01-02',
            'ref': 'Current exact reversal',
        }], cancel=False)
        reversal._eh_post_verified_reversal()

        self.env.flush_all()
        self.migration_175.migrate(self.env.cr, '19.0.1.7.4')
        self.env.invalidate_all()

        self.assertTrue(source.eh_sealed)
        self.assertFalse(source.eh_legacy_unverified_seal)
        self.assertTrue(reversal.eh_sealed)
        self.assertFalse(reversal.eh_legacy_unverified_seal)
        self.assertEqual(reversal.reversed_entry_id, source)

    def test_175_upgrade_quarantines_dimension_drift(self):
        source_partner = self.env['res.partner'].create({
            'name': 'Historical exact reversal partner',
        })
        forged_partner = self.env['res.partner'].create({
            'name': 'Historical forged line partner',
        })
        source = self.post_balanced_move([
            {
                'account': self.account_expense,
                'debit': 100.0,
                'partner': source_partner,
            },
            {
                'account': self.account_cash,
                'credit': 100.0,
                'partner': source_partner,
            },
        ])
        source._eh_stamp_verified_seal()
        reversal = source._eh_reverse_with_verified_capability([{
            'date': '2026-01-02',
        }], cancel=False)
        reversal._eh_post_verified_reversal()
        forged_line = reversal.line_ids.filtered(
            lambda line: line.account_id == self.account_expense
        )

        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE account_move_line SET partner_id = %s WHERE id = %s",
            (forged_partner.id, forged_line.id),
        )
        self.migration_175.migrate(self.env.cr, '19.0.1.7.4')
        self.env.invalidate_all()

        self.assertFalse(source.eh_sealed)
        self.assertTrue(source.eh_legacy_unverified_seal)
        self.assertFalse(reversal.eh_sealed)
        self.assertTrue(reversal.eh_legacy_unverified_seal)
        self.assertEqual(reversal.reversed_entry_id, source)

    def test_175_upgrade_quarantines_tax_tag_drift(self):
        source_tag = self.env['account.account.tag'].create({
            'name': 'Historical reversal source grid',
            'applicability': 'taxes',
        })
        forged_tag = self.env['account.account.tag'].create({
            'name': 'Historical reversal forged grid',
            'applicability': 'taxes',
        })
        source = self._posted_move()
        source_line = source.line_ids.filtered(
            lambda line: line.account_id == self.account_expense
        )
        source_line.write({'tax_tag_ids': [(6, 0, source_tag.ids)]})
        source._eh_stamp_verified_seal()
        reversal = source._eh_reverse_with_verified_capability([{
            'date': '2026-01-02',
        }], cancel=False)
        reversal._eh_post_verified_reversal()
        forged_line = reversal.line_ids.filtered(
            lambda line: line.account_id == self.account_expense
        )

        self.env.flush_all()
        self.env.cr.execute(
            "INSERT INTO account_account_tag_account_move_line_rel "
            "(account_move_line_id, account_account_tag_id) VALUES (%s, %s)",
            (forged_line.id, forged_tag.id),
        )
        self.migration_175.migrate(self.env.cr, '19.0.1.7.4')
        self.env.invalidate_all()

        self.assertFalse(source.eh_sealed)
        self.assertTrue(source.eh_legacy_unverified_seal)
        self.assertFalse(reversal.eh_sealed)
        self.assertTrue(reversal.eh_legacy_unverified_seal)
        self.assertEqual(reversal.reversed_entry_id, source)

    def test_176_upgrade_quarantines_legacy_portal_send_and_pdf_evidence(self):
        required = {'invoice_pdf_report_id', 'sending_data'}
        if not required.issubset(self.env['account.move']._fields):
            self.skipTest('core legal-PDF/send fields are unavailable')
        partner = self.env['res.partner'].create({
            'name': 'Legacy delivery evidence customer',
        })
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'journal_id': self.journal_sale.id,
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [(0, 0, {
                'name': 'Legacy delivery evidence line',
                'account_id': self.account_revenue.id,
                'quantity': 1.0,
                'price_unit': 100.0,
            })],
        })
        invoice.action_post()
        self._generate_test_invoice_pdf(invoice)
        legal_pdf = invoice.invoice_pdf_report_id
        original_bytes = legal_pdf.raw
        ordinary_main = self.env['ir.attachment'].create({
            'name': 'legacy-readonly-selected-main.txt',
            'raw': b'legacy ordinary main attachment bytes',
            'mimetype': 'text/plain',
            'res_model': invoice._name,
            'res_id': invoice.id,
        })
        ordinary_main_bytes = ordinary_main.raw

        ordinary_invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'journal_id': self.journal_sale.id,
            'invoice_date': '2026-01-02',
            'invoice_line_ids': [(0, 0, {
                'name': 'Ordinary retained delivery evidence line',
                'account_id': self.account_revenue.id,
                'quantity': 1.0,
                'price_unit': 50.0,
            })],
        })
        ordinary_invoice.action_post()
        ordinary_token = ordinary_invoice._portal_ensure_token()
        self._generate_test_invoice_pdf(ordinary_invoice)
        ordinary_pdf = ordinary_invoice.invoice_pdf_report_id
        ordinary_pdf_bytes = ordinary_pdf.raw
        ordinary_invoice.write({'sending_data': {'queued': True}})

        self.env.flush_all()
        self.env.cr.execute(
            """
            UPDATE account_move
               SET eh_sealed = FALSE,
                   eh_legacy_unverified_seal = TRUE,
                   access_token = %s,
                   is_move_sent = TRUE,
                   sending_data = %s::jsonb,
                   message_main_attachment_id = %s
             WHERE id = %s
            """,
            (
                'legacy-forged-token',
                '{"forged": true}',
                ordinary_main.id,
                invoice.id,
            ),
        )

        self.migration_176.migrate(self.env.cr, '19.0.1.7.5')
        self.env.invalidate_all()

        self.assertFalse(invoice.access_token)
        self.assertFalse(invoice.is_move_sent)
        self.assertFalse(invoice.sending_data)
        self.assertFalse(invoice.invoice_pdf_report_id)
        self.assertFalse(invoice.message_main_attachment_id)
        self.assertTrue(legal_pdf.exists())
        self.assertEqual(legal_pdf.raw, original_bytes)
        self.assertEqual(legal_pdf.res_model, invoice._name)
        self.assertEqual(legal_pdf.res_id, invoice.id)
        self.assertFalse(legal_pdf.res_field)
        self.assertTrue(legal_pdf.eh_legacy_unverified_legal_pdf)
        self.assertIn('detached', legal_pdf.description or '')
        self.assertTrue(ordinary_main.exists())
        self.assertEqual(ordinary_main.raw, ordinary_main_bytes)
        self.assertEqual(ordinary_main.res_model, invoice._name)
        self.assertEqual(ordinary_main.res_id, invoice.id)
        self.assertFalse(ordinary_main.eh_legacy_unverified_legal_pdf)
        self.assertEqual(ordinary_invoice.access_token, ordinary_token)
        self.assertTrue(ordinary_invoice.is_move_sent)
        self.assertEqual(ordinary_invoice.sending_data, {'queued': True})
        self.assertEqual(ordinary_invoice.invoice_pdf_report_id, ordinary_pdf)
        self.assertEqual(ordinary_pdf.raw, ordinary_pdf_bytes)
        self.assertEqual(
            ordinary_pdf.res_field, 'invoice_pdf_report_file',
        )
        self.assertFalse(ordinary_pdf.eh_legacy_unverified_legal_pdf)
        with self.assertRaises(AccessError):
            legal_pdf.write({'name': 'forged quarantined evidence.pdf'})
        with self.assertRaises(AccessError):
            legal_pdf.unlink()
        with self.assertRaises(UserError):
            invoice._portal_ensure_token()
        if 'account.move.send' in self.env:
            send_model = self.env['account.move.send']
            if (
                hasattr(send_model, '_generate_and_send_invoices')
                or hasattr(send_model, '_process_send_and_print')
            ):
                with self.assertRaises(UserError):
                    self._generate_test_invoice_pdf(invoice)

    def test_elevated_source_restores_actor_company_rules(self):
        foreign_company = self.env['res.company'].create({
            'name': 'Foreign sealed-move company',
            'currency_id': self.company.currency_id.id,
        })
        foreign_env = self.env['account.account'].sudo().with_company(
            foreign_company,
        ).env
        foreign_expense = self._ensure_account(
            foreign_env, '950001', 'Foreign expense', 'expense',
        )
        foreign_cash = self._ensure_account(
            foreign_env, '950002', 'Foreign cash', 'asset_cash',
        )
        foreign_journal = self._ensure_journal(
            foreign_env,
            foreign_company,
            'general',
            'FSEAL',
            'Foreign sealed entries',
        )
        elevated_actor_model = self.env['account.move'].with_user(
            self.account_user,
        ).sudo()
        self.assertTrue(elevated_actor_model.env.su)
        foreign_move_count = self.env['account.move'].sudo().search_count([
            ('journal_id', '=', foreign_journal.id),
        ])
        with self.assertRaises(Exception) as denied:
            elevated_actor_model._eh_create_sealed({
                'move_type': 'entry',
                'journal_id': foreign_journal.id,
                'date': '2026-01-01',
                'line_ids': [
                    (0, 0, {
                        'account_id': foreign_expense.id,
                        'debit': 25.0,
                        'name': 'foreign sealed debit',
                    }),
                    (0, 0, {
                        'account_id': foreign_cash.id,
                        'credit': 25.0,
                        'name': 'foreign sealed credit',
                    }),
                ],
            })
        self.assertIsInstance(denied.exception, (AccessError, UserError))
        self.assertEqual(self.env['account.move'].sudo().search_count([
            ('journal_id', '=', foreign_journal.id),
        ]), foreign_move_count)

    def test_client_cannot_supply_seal_on_create(self):
        vals = {
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'date': '2026-01-01',
            'eh_sealed': True,
        }
        with self.assertRaises(AccessError):
            self.env['account.move'].sudo().create(vals)

    def test_sealed_stored_outputs_reject_raw_rpc_writes(self):
        partner = self.env['res.partner'].create({
            'name': 'Stored output guard customer',
        })
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'journal_id': self.journal_sale.id,
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [(0, 0, {
                'name': 'Stored output guard line',
                'account_id': self.account_revenue.id,
                'quantity': 1.0,
                'price_unit': 100.0,
            })],
        })
        move.action_post()
        move._eh_stamp_verified_seal()
        fake_pdf = self.env['ir.attachment'].create({
            'name': 'forged-legal-invoice.pdf',
            'type': 'binary',
            'datas': base64.b64encode(b'not the legal invoice'),
            'mimetype': 'application/pdf',
            'res_model': move._name,
            'res_id': move.id,
        })
        move_fields = {
            'narration': 'arbitrary stored-field overwrite',
            'access_token': 'attacker-chosen-portal-bearer',
            'message_main_attachment_id': fake_pdf.id,
            'sending_data': {'forged': True},
            'is_move_sent': True,
            'invoice_pdf_report_id': fake_pdf.id,
            'invoice_pdf_report_file': base64.b64encode(b'forged pdf'),
            'amount_untaxed': 999.0,
            'amount_tax': 999.0,
            'amount_total': 999.0,
            'amount_residual': 999.0,
            'amount_untaxed_signed': 999.0,
            'amount_untaxed_in_currency_signed': 999.0,
            'amount_tax_signed': 999.0,
            'amount_total_signed': 999.0,
            'amount_total_in_currency_signed': 999.0,
            'amount_residual_signed': 999.0,
            'payment_state': 'paid',
        }
        move_fields = {
            field_name: value
            for field_name, value in move_fields.items()
            if field_name in move._fields
        }
        for field_name, forged_value in move_fields.items():
            with self.assertRaises(UserError, msg=field_name):
                move.with_context(
                    eh_account_engine_internal=True,
                ).write({field_name: forged_value})

        line = move.invoice_line_ids
        line_fields = {
            'sequence': 987,
            'parent_state': 'draft',
            'invoice_date': '2026-02-01',
            'full_reconcile_id': False,
            'matching_number': 'FORGED',
            'tax_base_amount': 999.0,
            'amount_residual': 999.0,
            'amount_residual_currency': 999.0,
            'reconciled': True,
            'price_subtotal': 999.0,
            'price_total': 999.0,
            'product_uom_id': self.env.ref('uom.product_uom_unit').id,
            'is_storno': not getattr(line, 'is_storno', False),
            'deductible_amount': 1.0,
            'extra_tax_data': {'forged': True},
            'tax_tag_ids': [(6, 0, self.env['account.account.tag'].create({
                'name': 'Forged sealed line tax grid',
                'applicability': 'taxes',
            }).ids)],
        }
        line_fields = {
            field_name: value
            for field_name, value in line_fields.items()
            if field_name in line._fields and line._fields[field_name].store
        }
        for field_name, forged_value in line_fields.items():
            with self.assertRaises(UserError, msg=field_name):
                line.with_context(
                    eh_account_engine_internal=True,
                ).write({field_name: forged_value})

    def test_unsealed_delivery_fields_keep_core_lifecycle_but_dirty_move_cannot_seal(self):
        partner = self.env['res.partner'].create({
            'name': 'Draft evidence preseed customer',
        })
        base_vals = {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'journal_id': self.journal_sale.id,
            'invoice_date': '2026-01-01',
            'ref': 'DRAFT EVIDENCE PRESEED',
            'invoice_line_ids': [(0, 0, {
                'name': 'Draft evidence preseed line',
                'account_id': self.account_revenue.id,
                'quantity': 1.0,
                'price_unit': 100.0,
            })],
        }
        core_create = {
            'is_move_sent': True,
            'sending_data': {'core_queue': True},
        }
        core_create = {
            name: value for name, value in core_create.items()
            if name in self.env['account.move']._fields
        }
        queued_invoice = self.env['account.move'].create({
            **base_vals, **core_create,
        })
        self.assertTrue(queued_invoice.is_move_sent)
        if 'sending_data' in queued_invoice._fields:
            self.assertEqual(
                queued_invoice.sending_data, {'core_queue': True},
            )
        queued_invoice.action_post()
        with self.assertRaises(UserError):
            queued_invoice._eh_stamp_verified_seal()

        clean_vals = dict(base_vals, ref='UNSEALED CORE FIELD WRITES')
        invoice = self.env['account.move'].create(clean_vals)
        core_fields = {
            'is_move_sent': True,
            'sending_data': {'core_queue': 'cancel-me'},
        }
        core_fields = {
            name: value for name, value in core_fields.items()
            if name in invoice._fields
        }
        invoice.write(core_fields)
        self.assertTrue(invoice.is_move_sent)
        if 'sending_data' in invoice._fields:
            self.assertEqual(
                invoice.sending_data, {'core_queue': 'cancel-me'},
            )
            # Mirrors account_peppol.action_cancel_peppol_documents on core
            # series which expose its JSON queue field.
            invoice.write({'sending_data': False})
            self.assertFalse(invoice.sending_data)
        with self.assertRaises(AccessError):
            invoice.write({'access_token': 'caller-chosen-bearer'})
        with self.assertRaises(AccessError):
            self.env['account.move'].create({
                **dict(base_vals, ref='FORGED DRAFT BEARER'),
                'access_token': 'caller-chosen-bearer',
            })
        with self.assertRaises(AccessError):
            self.env['ir.attachment'].create({
                'name': 'draft-forged-legal.pdf',
                'raw': b'%PDF-1.4\ndraft forged legal bytes\n%%EOF',
                'mimetype': 'application/pdf',
                'res_model': invoice._name,
                'res_id': invoice.id,
                'res_field': 'invoice_pdf_report_file',
            })

        invoice.action_post()
        invoice.write({'is_move_sent': False})
        invoice._eh_stamp_verified_seal()
        token = invoice._portal_ensure_token()
        if 'invoice_pdf_report_id' in invoice._fields:
            attachments = self._generate_test_invoice_pdf(invoice)
            self.assertTrue(attachments)
            self.assertTrue(invoice.invoice_pdf_report_id)
            self.assertEqual(
                invoice.invoice_pdf_report_id.raw,
                b'%PDF-1.4\nsealed invoice test\n%%EOF',
            )
            self.assertTrue(invoice.is_move_sent)
        self.assertTrue(token)

    def test_sealed_portal_token_and_pdf_generation_are_sanctioned(self):
        partner = self.env['res.partner'].create({
            'name': 'Sealed portal and PDF customer',
            'email': 'sealed.portal@example.com',
        })
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'journal_id': self.journal_sale.id,
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [(0, 0, {
                'name': 'Sealed portal and PDF line',
                'account_id': self.account_revenue.id,
                'quantity': 1.0,
                'price_unit': 100.0,
            })],
        })
        move.action_post()
        move._eh_stamp_verified_seal()

        token = move._portal_ensure_token()
        self.assertTrue(token)
        self.assertEqual(move.access_token, token)
        self.assertTrue(move.eh_sealed)
        if 'invoice_pdf_report_id' in move._fields:
            attachments = self._generate_test_invoice_pdf(move)
            self.assertTrue(attachments)
            self.assertTrue(move.invoice_pdf_report_id)
            self.assertEqual(
                move.message_main_attachment_id,
                move.invoice_pdf_report_id,
            )

    def test_legacy_send_async_queue_keeps_wizard_context_clean(self):
        if 'account.move.send' not in self.env:
            self.skipTest('core invoice-send model is unavailable')
        SendModel = self.env['account.move.send']
        if not hasattr(SendModel, '_process_send_and_print'):
            self.skipTest('legacy asynchronous send corridor is unavailable')
        if 'send_and_print_values' not in self.env['account.move']._fields:
            self.skipTest('legacy send queue field is unavailable')

        if 'invoice_is_email' in self.company._fields:
            self.company.invoice_is_email = True
        partner = self.env['res.partner'].create({
            'name': 'Sealed async-send customer without email',
        })
        moves = self.env['account.move']
        for sequence in range(2):
            move = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'journal_id': self.journal_sale.id,
                'invoice_date': '2026-01-01',
                'invoice_line_ids': [(0, 0, {
                    'name': 'Sealed async-send line %s' % sequence,
                    'account_id': self.account_revenue.id,
                    'quantity': 1.0,
                    'price_unit': 100.0,
                })],
            })
            move.action_post()
            move._eh_stamp_verified_seal()
            moves |= move

        with self.assertRaises(AccessError):
            moves.write({
                'send_and_print_values': {'download': False},
            })

        wizard = SendModel.with_context(
            active_model='account.move',
            active_ids=moves.ids,
        ).create({
            'move_ids': [Command.set(moves.ids)],
            'checkbox_download': False,
        })
        wizard.checkbox_download = False

        observed_wizard_contexts = []
        SendClass = type(SendModel)
        original_get_wizard_values = SendClass._get_wizard_values

        def _capture_clean_wizard_context(wizard_self):
            observed_wizard_contexts.append(dict(wizard_self.env.context))
            return original_get_wizard_values(wizard_self)

        triggered_crons = []
        cron = self.env.ref('account.ir_cron_account_move_send')

        def _capture_trigger(cron_self, *args, **kwargs):
            triggered_crons.append(cron_self.ids)

        with patch.object(
            SendClass,
            '_get_wizard_values',
            _capture_clean_wizard_context,
        ), patch.object(type(cron), '_trigger', _capture_trigger):
            action = wizard.action_send_and_print(
                force_synchronous=False,
            )

        self.assertTrue(observed_wizard_contexts)
        for context in observed_wizard_contexts:
            self.assertNotIn('eh_sealed_metadata_internal', context)
            self.assertNotIn('eh_account_engine_internal', context)
        self.assertEqual(triggered_crons, [cron.ids])
        self.assertEqual(action['type'], 'ir.actions.client')
        self.assertEqual(action['tag'], 'display_notification')
        self.assertEqual(
            action['params']['next'],
            {'type': 'ir.actions.act_window_close'},
        )
        moves.invalidate_recordset(['send_and_print_values'])
        for move in moves:
            self.assertIsInstance(move.send_and_print_values, dict)
            self.assertFalse(move.send_and_print_values.get('download'))
            self.assertFalse(move.send_and_print_values.get('send_mail'))
            self.assertTrue(move.eh_sealed)

    def test_sealed_invoice_followup_control_uses_sanctioned_inverse(self):
        modern_followup = (
            'no_followup' in self.env['account.move']._fields
            and 'no_followup' in self.env['account.move.line']._fields
        )
        legacy_followup = 'blocked' in self.env['account.move.line']._fields
        if not modern_followup and not legacy_followup:
            self.skipTest('core follow-up exclusion field is unavailable')
        partner = self.env['res.partner'].create({
            'name': 'Sealed follow-up customer',
        })
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'journal_id': self.journal_sale.id,
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [(0, 0, {
                'name': 'Sealed follow-up line',
                'account_id': self.account_revenue.id,
                'quantity': 1.0,
                'price_unit': 100.0,
            })],
        })
        invoice.action_post()
        invoice._eh_stamp_verified_seal()
        receivable = invoice.line_ids.filtered(
            lambda line: line.account_type == 'asset_receivable'
        )

        if modern_followup:
            invoice.write({'no_followup': True})
            self.assertTrue(receivable.no_followup)
            with self.assertRaises(UserError):
                receivable.with_context(
                    eh_account_engine_internal=True,
                ).write({'no_followup': False})
            invoice.write({'no_followup': False})
            self.assertFalse(receivable.no_followup)
        else:
            receivable.write({'blocked': True})
            self.assertTrue(receivable.blocked)
            receivable.write({'blocked': False})
            self.assertFalse(receivable.blocked)

    def test_sealed_move_chatter_attachment_sets_main_attachment(self):
        move = self._posted_move()
        move._eh_stamp_verified_seal()

        message = move.message_post(
            body='Sealed evidence attachment',
            attachments=[(
                'sealed-evidence.pdf',
                b'%PDF-1.4\nsealed chatter test\n%%EOF',
            )],
        )

        self.assertTrue(message.attachment_ids)
        self.assertEqual(
            move.message_main_attachment_id,
            message.attachment_ids,
        )
        self.assertTrue(move.eh_sealed)
        with self.assertRaises(AccessError):
            message.attachment_ids.write({
                'datas': base64.b64encode(b'forged chatter evidence'),
            })
        with self.assertRaises(AccessError):
            message.attachment_ids.unlink()

    def test_sealed_legal_pdf_attachment_is_owner_protected(self):
        if 'invoice_pdf_report_id' not in self.env['account.move']._fields:
            self.skipTest('core legal-PDF fields are unavailable')
        partner = self.env['res.partner'].create({
            'name': 'Sealed legal PDF customer',
        })
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'journal_id': self.journal_sale.id,
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [(0, 0, {
                'name': 'Sealed legal PDF line',
                'account_id': self.account_revenue.id,
                'quantity': 1.0,
                'price_unit': 100.0,
            })],
        })
        invoice.action_post()
        invoice._eh_stamp_verified_seal()
        self._generate_test_invoice_pdf(invoice)
        legal_pdf = invoice.invoice_pdf_report_id
        self.assertTrue(legal_pdf)

        attacker_attachment = self.env['ir.attachment'].create({
            'name': 'attacker.pdf',
            'raw': b'%PDF-1.4\nattacker replacement\n%%EOF',
            'mimetype': 'application/pdf',
            'res_model': invoice._name,
            'res_id': invoice.id,
        })
        with self.assertRaises(UserError):
            attacker_attachment.with_user(
                self.account_user,
            ).register_as_main_attachment(force=False)
        with self.assertRaises(UserError):
            attacker_attachment.with_user(
                self.account_user,
            ).register_as_main_attachment(force=True)
        self.assertEqual(invoice.message_main_attachment_id, legal_pdf)

        pending_legal_pdf = self.env['ir.attachment'].create({
            'name': 'pending-forged-legal.pdf',
            'raw': b'%PDF-1.4\npending forged legal PDF\n%%EOF',
            'mimetype': 'application/pdf',
            'res_model': 'mail.compose.message',
            'res_id': 0,
            'res_field': 'invoice_pdf_report_file',
        })
        with self.assertRaises(AccessError):
            invoice.message_post(
                body='Attempted legal PDF smuggling',
                attachment_ids=pending_legal_pdf.ids,
            )
        self.assertEqual(
            pending_legal_pdf.res_model,
            'mail.compose.message',
        )
        self.assertEqual(invoice.message_main_attachment_id, legal_pdf)

        with self.assertRaises(AccessError):
            self.env['ir.attachment'].create({
                'name': 'forged-invoice.pdf',
                'raw': b'%PDF-1.4\nforged invoice\n%%EOF',
                'mimetype': 'application/pdf',
                'res_model': invoice._name,
                'res_id': invoice.id,
                'res_field': 'invoice_pdf_report_file',
            })
        with self.assertRaises(AccessError):
            legal_pdf.write({
                'datas': base64.b64encode(b'forged legal PDF bytes'),
            })
        with self.assertRaises(AccessError):
            legal_pdf.write({'res_id': self._posted_move().id})
        with self.assertRaises(AccessError):
            attacker_attachment.write({
                'res_field': 'invoice_pdf_report_file',
            })
        with self.assertRaises(AccessError):
            legal_pdf.unlink()
        self.assertTrue(legal_pdf.exists())
        self.assertEqual(invoice.message_main_attachment_id, legal_pdf)

    def test_legal_pdf_attachment_target_has_no_move_existence_oracle(self):
        foreign_company = self.env['res.company'].create({
            'name': 'Hidden legal PDF target company',
            'currency_id': self.company.currency_id.id,
        })
        foreign_env = self.env['account.journal'].sudo().with_company(
            foreign_company,
        ).env
        foreign_journal = self._ensure_journal(
            foreign_env,
            foreign_company,
            'general',
            'HPDF',
            'Hidden legal PDF journal',
        )
        hidden_move = foreign_env['account.move'].create({
            'move_type': 'entry',
            'journal_id': foreign_journal.id,
            'date': '2026-01-01',
        })

        errors = []
        for target_id in (hidden_move.id, hidden_move.id + 1_000_000_000):
            with self.assertRaises(AccessError) as denied:
                self.env['ir.attachment'].with_user(
                    self.account_user,
                ).create({
                    'name': 'oracle-probe.pdf',
                    'raw': b'%PDF-1.4\noracle probe\n%%EOF',
                    'mimetype': 'application/pdf',
                    'res_model': 'account.move',
                    'res_id': target_id,
                    'res_field': 'invoice_pdf_report_file',
                })
            errors.append(str(denied.exception))
        self.assertEqual(errors[0], errors[1])

    def test_sealed_move_mail_controller_upload_can_set_initial_main(self):
        move = self._posted_move()
        move._eh_stamp_verified_seal()
        self.assertFalse(move.message_main_attachment_id)
        upload = self.env['ir.attachment'].sudo().create({
            'name': 'controller-upload.pdf',
            'raw': b'%PDF-1.4\ncontroller upload\n%%EOF',
            'mimetype': 'application/pdf',
            'res_model': move._name,
            'res_id': move.id,
        })

        # Mirrors /mail/attachment/upload: sudo creation followed by the
        # core post-add hook, whose force=False registration is intentionally
        # narrower than the public force=True replacement action.
        upload._post_add_create()

        move.invalidate_recordset(['message_main_attachment_id'])
        self.assertEqual(move.message_main_attachment_id, upload)
        with self.assertRaises(AccessError):
            upload.write({'name': 'forged controller upload.pdf'})

    def test_readonly_chatter_and_upload_cannot_choose_main_attachment(self):
        move = self._posted_move()
        move._eh_stamp_verified_seal()

        message = move.with_user(self.readonly_auditor).message_post(
            body='Read-only audit observation',
            attachments=[(
                'readonly-observation.txt',
                b'read-only observation',
            )],
        )
        move.invalidate_recordset(['message_main_attachment_id'])
        self.assertTrue(message.attachment_ids)
        self.assertFalse(move.message_main_attachment_id)

        controller_upload = self.env['ir.attachment'].with_user(
            self.readonly_auditor,
        ).sudo().create({
            'name': 'readonly-controller-upload.txt',
            'raw': b'read-only controller upload',
            'mimetype': 'text/plain',
            'res_model': move._name,
            'res_id': move.id,
        })
        controller_upload._post_add_create()
        move.invalidate_recordset(['message_main_attachment_id'])
        self.assertFalse(move.message_main_attachment_id)

    def test_sealed_invoice_can_be_paid_and_unreconciled_by_core(self):
        partner = self.env['res.partner'].create({
            'name': 'Sealed invoice payment customer',
        })
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'journal_id': self.journal_sale.id,
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [(0, 0, {
                'name': 'Sealed invoice payment line',
                'account_id': self.account_revenue.id,
                'quantity': 1.0,
                'price_unit': 100.0,
            })],
        })
        invoice.action_post()
        invoice._eh_stamp_verified_seal()
        bank = self._ensure_journal(
            self.env,
            self.company,
            'bank',
            'SBPG',
            'Sealed bill payment bank',
            default_account=self.account_cash,
        )
        outstanding = self._ensure_account(
            self.env, '1096', 'Sealed payment outstanding', 'asset_current',
        )
        if not outstanding.reconcile:
            outstanding.reconcile = True
        method_line = bank.inbound_payment_method_line_ids[:1]
        if not method_line.payment_account_id:
            method_line.payment_account_id = outstanding.id
        self.company.invalidate_recordset(['eh_move_version'])
        version_before = self.company.eh_move_version
        payment = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({
            'payment_date': '2026-01-02',
            'journal_id': bank.id,
            'payment_method_line_id': method_line.id,
        })._create_payments()
        invoice.invalidate_recordset([
            'amount_residual', 'amount_residual_signed', 'payment_state',
        ])
        self.assertEqual(invoice.amount_residual, 0.0)
        self.assertEqual(invoice.payment_state, 'paid')
        self.assertTrue(invoice.eh_sealed)
        self.company.invalidate_recordset(['eh_move_version'])
        self.assertGreater(self.company.eh_move_version, version_before)

        receivable_lines = (
            invoice.line_ids | payment.move_id.line_ids
        ).filtered(lambda line: line.account_type == 'asset_receivable')
        receivable_lines.remove_move_reconcile()
        invoice.invalidate_recordset([
            'amount_residual', 'amount_residual_signed', 'payment_state',
        ])
        self.assertEqual(invoice.amount_residual, 100.0)
        self.assertEqual(invoice.payment_state, 'not_paid')
        self.assertTrue(invoice.eh_sealed)

    def test_low_level_reconcile_crud_cannot_mutate_sealed_lines(self):
        partner = self.env['res.partner'].create({
            'name': 'Sealed low-level reconcile customer',
        })
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'journal_id': self.journal_sale.id,
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [(0, 0, {
                'name': 'Sealed low-level reconcile invoice line',
                'account_id': self.account_revenue.id,
                'quantity': 1.0,
                'price_unit': 100.0,
            })],
        })
        invoice.action_post()
        invoice._eh_stamp_verified_seal()
        receivable = invoice.line_ids.filtered(
            lambda line: line.account_type == 'asset_receivable'
        )
        counterpart_move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'date': '2026-01-02',
            'line_ids': [
                (0, 0, {
                    'name': 'Sealed reconcile counterpart',
                    'account_id': receivable.account_id.id,
                    'partner_id': partner.id,
                    'credit': 100.0,
                }),
                (0, 0, {
                    'name': 'Sealed reconcile cash',
                    'account_id': self.account_cash.id,
                    'debit': 100.0,
                }),
            ],
        })
        counterpart_move.action_post()
        counterpart = counterpart_move.line_ids.filtered(
            lambda line: line.account_id == receivable.account_id
        )
        partial_values = {
            'debit_move_id': receivable.id,
            'credit_move_id': counterpart.id,
            'amount': 100.0,
            'debit_amount_currency': 100.0,
            'credit_amount_currency': 100.0,
        }

        with self.assertRaises(UserError):
            self.env['account.partial.reconcile'].create(partial_values)
        with self.assertRaises(UserError):
            self.env['account.full.reconcile'].create({
                'partial_reconcile_ids': [],
                'reconciled_line_ids': [
                    Command.link(receivable.id),
                    Command.link(counterpart.id),
                ],
            })
        invoice.invalidate_recordset(['amount_residual', 'payment_state'])
        self.assertEqual(invoice.amount_residual, 100.0)
        self.assertEqual(invoice.payment_state, 'not_paid')

        reconcile_result = (receivable | counterpart).reconcile()

        def assert_clean_reconcile_result(item):
            if getattr(item, '_name', False):
                self.assertNotIn(
                    'eh_account_engine_internal', item.env.context,
                )
            elif isinstance(item, dict):
                for key, value in item.items():
                    assert_clean_reconcile_result(key)
                    assert_clean_reconcile_result(value)
            elif isinstance(item, (list, tuple, set)):
                for child in item:
                    assert_clean_reconcile_result(child)

        assert_clean_reconcile_result(reconcile_result)
        partial = receivable.matched_credit_ids | receivable.matched_debit_ids
        full = receivable.full_reconcile_id
        self.assertTrue(partial)
        self.assertTrue(full)
        with self.assertRaises(UserError):
            partial.write({'amount': 50.0})
        with self.assertRaises(UserError):
            partial.unlink()
        with self.assertRaises(UserError):
            full.unlink()

        (receivable | counterpart).remove_move_reconcile()
        invoice.invalidate_recordset(['amount_residual', 'payment_state'])
        self.assertEqual(invoice.amount_residual, 100.0)
        self.assertEqual(invoice.payment_state, 'not_paid')
        self.assertTrue(invoice.eh_sealed)

    def test_sealed_vendor_bill_can_be_paid_by_register_payment(self):
        partner = self.env['res.partner'].create({
            'name': 'Sealed vendor bill payment supplier',
        })
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': partner.id,
            'journal_id': self.journal_purchase.id,
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [(0, 0, {
                'name': 'Sealed vendor bill payment line',
                'account_id': self.account_expense.id,
                'quantity': 1.0,
                'price_unit': 75.0,
            })],
        })
        bill.action_post()
        bill._eh_stamp_verified_seal()
        bank = self._ensure_journal(
            self.env,
            self.company,
            'bank',
            'SBPO',
            'Sealed outbound bill payment bank',
            default_account=self.account_cash,
        )
        outstanding = self._ensure_account(
            self.env, '2096', 'Sealed outbound payment', 'liability_current',
        )
        if not outstanding.reconcile:
            outstanding.reconcile = True
        method_line = bank.outbound_payment_method_line_ids[:1]
        if not method_line.payment_account_id:
            method_line.payment_account_id = outstanding.id

        payment = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=bill.ids,
        ).create({
            'payment_date': '2026-01-02',
            'journal_id': bank.id,
            'payment_method_line_id': method_line.id,
        })._create_payments()

        bill.invalidate_recordset([
            'amount_residual', 'amount_residual_signed', 'payment_state',
        ])
        self.assertTrue(payment)
        self.assertEqual(bill.amount_residual, 0.0)
        self.assertEqual(bill.payment_state, 'paid')
        self.assertTrue(bill.eh_sealed)

    def test_sealed_move_cannot_be_reset_or_edited(self):
        move = self._posted_move()
        move._eh_stamp_verified_seal()
        self.assertEqual(move.state, 'posted')
        with self.assertRaises(UserError):
            move.button_draft()
        with self.assertRaises(UserError):
            move.button_cancel()
        with self.assertRaises(UserError):
            move.write({'state': 'draft'})
        with self.assertRaises(UserError):
            move.write({'date': '2026-01-02'})
        with self.assertRaises(UserError):
            move.with_context(force_delete=True).unlink()
        # A material figure edit on a line is refused.
        with self.assertRaises(UserError):
            move.line_ids[0].debit = 5.0
        # Adding / removing a line is refused.
        with self.assertRaises(UserError):
            move.line_ids[0].unlink()
        line_count = len(move.line_ids)
        with self.assertRaises(UserError):
            self.env['account.move.line'].with_context(
                check_move_validity=False,
            ).create({
                'move_id': move.id,
                'account_id': self.account_expense.id,
                'debit': 1.0,
                'name': 'forged sealed line',
            })
        self.assertEqual(len(move.line_ids), line_count)
        source = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'date': '2026-01-01',
            'line_ids': [
                (0, 0, {
                    'account_id': self.account_expense.id,
                    'debit': 2.0,
                    'name': 'source debit',
                }),
                (0, 0, {
                    'account_id': self.account_cash.id,
                    'credit': 2.0,
                    'name': 'source credit',
                }),
            ],
        })
        source_line = source.line_ids[0]
        with self.assertRaises(UserError):
            source_line.write({'move_id': move.id})
        self.assertEqual(source_line.move_id, source)
        self.assertEqual(move.state, 'posted')

    def test_uid1_cannot_forge_legacy_unpost_context(self):
        move = self._posted_move()
        move._eh_stamp_verified_seal()
        forged = move.with_user(SUPERUSER_ID).with_context(
            eh_allow_unpost=True,
        )
        with self.assertRaises(UserError):
            forged.button_draft()
        with self.assertRaises(AccessError):
            forged.write({'eh_sealed': False})
        with self.assertRaises(UserError):
            forged.line_ids[:1].write({'debit': 1.0})
        move.invalidate_recordset(['state', 'eh_sealed'])
        self.assertEqual(move.state, 'posted')
        self.assertTrue(move.eh_sealed)

    def test_interactive_user_cannot_change_seal(self):
        move = self._posted_move()
        actor_move = move.with_user(self.account_user)
        with self.assertRaises(AccessError):
            actor_move.write({'eh_sealed': True})

        move._eh_stamp_verified_seal()
        for context in ({}, {'eh_allow_unpost': True}):
            with self.assertRaises(AccessError):
                actor_move.with_context(**context).write({
                    'eh_sealed': False,
                })
        self.assertTrue(move.eh_sealed)
