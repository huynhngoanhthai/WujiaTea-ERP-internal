# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Ownership and append-only security regressions for report UI metadata."""

import json

from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase


@tagged('eh_account_base', 'integration', 'post_install', '-at_install')
class TestSavedViewSecurity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner = new_test_user(
            cls.env,
            login='base_saved_view_owner',
            groups='eh_account_base.group_eh_user',
        )
        cls.reader = new_test_user(
            cls.env,
            login='base_saved_view_reader',
            groups='eh_account_base.group_eh_user',
        )
        cls.SavedView = cls.env['eh.account.report.saved_view']

    def _make_view(self, **overrides):
        vals = {
            'name': 'Owner baseline',
            'report_code': 'trial_balance',
            'options_json': json.dumps({'posted_only': True}),
            'shared': True,
        }
        vals.update(overrides)
        return self.SavedView.with_user(self.owner).create(vals)

    def test_shared_view_is_readable_but_not_mutable_by_non_owner(self):
        view = self._make_view()
        reader_view = self.SavedView.with_user(self.reader).browse(view.id)

        self.assertEqual(reader_view.name, 'Owner baseline')
        with self.assertRaises(AccessError):
            reader_view.write({'name': 'Hijacked'})
        with self.assertRaises(AccessError):
            reader_view.unlink()

        self.assertEqual(view.sudo().name, 'Owner baseline')

    def test_owner_and_company_identity_cannot_be_forged_or_rekeyed(self):
        with self.assertRaises(AccessError):
            self.SavedView.with_user(self.owner).create({
                'name': 'Forged owner',
                'report_code': 'trial_balance',
                'options_json': '{}',
                'user_id': self.reader.id,
            })
        with self.assertRaises(AccessError):
            self.SavedView.with_user(self.owner).create({
                'name': 'Forged company',
                'report_code': 'trial_balance',
                'options_json': '{}',
                'company_id': False,
            })

        view = self._make_view(name='Immutable identity')
        owner_view = view.with_user(self.owner)
        with self.assertRaises(AccessError):
            owner_view.write({'user_id': self.reader.id})
        with self.assertRaises(AccessError):
            owner_view.write({'company_id': False})

    def test_load_fails_closed_for_malformed_or_non_object_json(self):
        view = self._make_view(name='Legacy corrupt options')
        owner_view = view.with_user(self.owner)
        for raw_options in (
            '{bad', '[]', 'null', '"text"', '1', '{"value": NaN}',
        ):
            self.env.cr.execute(
                "UPDATE eh_account_report_saved_view "
                "SET options_json = %s WHERE id = %s",
                (raw_options, view.id),
            )
            owner_view.invalidate_recordset(['options_json'])
            with self.subTest(raw_options=raw_options):
                with self.assertRaises(UserError):
                    owner_view.load_options()

        self.env.cr.execute(
            "UPDATE eh_account_report_saved_view "
            "SET options_json = '{}' WHERE id = %s",
            (view.id,),
        )
        owner_view.invalidate_recordset(['options_json'])

    def test_framework_load_api_is_not_shadowed(self):
        result = self.SavedView.with_user(self.owner).load(
            ['name', 'report_code', 'options_json', 'shared'],
            [[
                'Imported through BaseModel.load',
                'trial_balance',
                '{"posted_only": false}',
                'False',
            ]],
        )

        self.assertFalse(result['messages'])
        self.assertEqual(len(result['ids']), 1)
        imported = self.SavedView.with_user(self.owner).browse(
            result['ids'][0],
        )
        self.assertEqual(
            imported.load_options(),
            {'posted_only': False},
        )

    def test_shared_view_survives_owner_removal_without_new_mutator(self):
        view = self._make_view(name='Surviving shared definition')

        self.owner.sudo().unlink()
        view.invalidate_recordset(['user_id'])

        self.assertTrue(view.sudo().exists())
        self.assertFalse(view.sudo().user_id)
        self.assertEqual(
            view.with_user(self.reader).name,
            'Surviving shared definition',
        )
        with self.assertRaises(AccessError):
            view.with_user(self.reader).write({'name': 'Claimed orphan'})


@tagged('eh_account_base', 'integration', 'post_install', '-at_install')
class TestAnnotationSecurity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.author = new_test_user(
            cls.env,
            login='annotation_author',
            groups='eh_account_base.group_eh_user',
        )
        cls.manager = new_test_user(
            cls.env,
            login='annotation_manager',
            groups='eh_account_base.group_eh_manager',
        )
        cls.Annotation = cls.env['eh.account.report.annotation']

    def _make_note(self, text='Original note'):
        return self.Annotation.with_user(self.author).create({
            'report_code': 'trial_balance',
            'line_id': 'account-1',
            'text': text,
        })

    def test_user_acl_and_orm_keep_annotations_append_only(self):
        user_acl = self.env.ref(
            'eh_account_base.access_eh_account_report_annotation_user'
        )
        self.assertFalse(user_acl.perm_write)

        note = self._make_note()
        with self.assertRaises(AccessError):
            note.with_user(self.author).write({'text': 'Rewritten'})
        with self.assertRaises(AccessError):
            note.with_user(self.author).unlink()
        self.assertEqual(note.sudo().text, 'Original note')

    def test_manager_can_correct_text_without_changing_author(self):
        note = self._make_note()
        original_author = note.sudo().create_uid

        note.with_user(self.manager).write({'text': 'Manager correction'})

        self.assertEqual(note.sudo().text, 'Manager correction')
        self.assertEqual(note.sudo().create_uid, original_author)
        with self.assertRaises(AccessError):
            note.with_user(self.manager).write({
                'create_uid': self.manager.id,
            })

    def test_create_cannot_spoof_annotation_author(self):
        with self.assertRaises(AccessError):
            self.Annotation.with_user(self.author).create({
                'report_code': 'trial_balance',
                'line_id': 'account-2',
                'text': 'Forged note',
                'create_uid': self.manager.id,
            })

    def test_manager_may_delete_annotation(self):
        note = self._make_note(text='Manager-removable note')
        note.with_user(self.manager).unlink()
        self.assertFalse(note.sudo().exists())
