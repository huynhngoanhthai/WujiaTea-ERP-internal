# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Per-user fold-state model tests.
"""

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


@tagged('eh_account_base', 'unit')
class TestReportFoldState(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Model = self.env['eh.account.report.fold.state']
        self.user = self.env.user

    def test_set_then_get_round_trip(self):
        self.Model.set_for_user(
            'balance_sheet', 'section-assets-group-12', True,
        )
        result = self.Model.get_for_user('balance_sheet')
        self.assertEqual(
            result.get('section-assets-group-12'), True,
        )

    def test_set_overwrites_existing(self):
        self.Model.set_for_user('balance_sheet', 'l1', True)
        self.Model.set_for_user('balance_sheet', 'l1', False)
        result = self.Model.get_for_user('balance_sheet')
        self.assertEqual(result.get('l1'), False)

    def test_get_returns_empty_when_no_state(self):
        result = self.Model.get_for_user('not_a_real_report')
        self.assertEqual(result, {})

    def test_reset_clears_for_report_only(self):
        self.Model.set_for_user('balance_sheet', 'l1', True)
        self.Model.set_for_user('profit_and_loss', 'l2', True)
        self.Model.reset_for_user('balance_sheet')
        bs = self.Model.get_for_user('balance_sheet')
        pl = self.Model.get_for_user('profit_and_loss')
        self.assertEqual(bs, {})
        self.assertEqual(pl.get('l2'), True)

    def test_unique_per_user_report_line(self):
        # Two creates with the same key should violate the constraint;
        # assert the exact storage error so an unrelated regression cannot
        # satisfy this test.
        self.Model.create({
            'user_id': self.user.id,
            'report_code': 'balance_sheet',
            'line_id': 'unique-line',
            'is_unfolded': True,
        })
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), \
                self.env.cr.savepoint():
            self.Model.create({
                'user_id': self.user.id,
                'report_code': 'balance_sheet',
                'line_id': 'unique-line',
                'is_unfolded': False,
            })

    def test_per_user_isolation(self):
        other = new_test_user(
            self.env,
            login='fold_test_other',
            groups='eh_account_base.group_eh_user',
        )
        self.Model.set_for_user('balance_sheet', 'l1', True)
        mine_row = self.Model.sudo().search([
            ('user_id', '=', self.user.id),
            ('report_code', '=', 'balance_sheet'),
        ])
        self.Model.with_user(other).set_for_user(
            'balance_sheet', 'l2', True,
        )
        mine = self.Model.get_for_user('balance_sheet')
        theirs = self.Model.with_user(other).get_for_user('balance_sheet')
        self.assertEqual(mine, {'l1': True})
        self.assertEqual(theirs, {'l2': True})

        self.assertFalse(
            self.Model.with_user(other).search([
                ('id', 'in', mine_row.ids),
            ])
        )

    def test_rpc_helpers_do_not_bypass_model_acl(self):
        outsider = new_test_user(
            self.env,
            login='fold_test_outsider',
            groups='base.group_user',
        )
        Model = self.Model.with_user(outsider)
        with self.assertRaises(AccessError):
            Model.get_for_user('balance_sheet')
        with self.assertRaises(AccessError):
            Model.set_for_user('balance_sheet', 'l1', True)
        with self.assertRaises(AccessError):
            Model.reset_for_user('balance_sheet')

    def test_read_only_auditor_can_mount_but_cannot_persist_fold_state(self):
        auditor = new_test_user(
            self.env,
            login='fold_test_auditor',
            groups='eh_account_base.group_eh_auditor',
        )
        Model = self.Model.with_user(auditor)

        self.assertEqual(Model.get_for_user('balance_sheet'), {})
        with self.assertRaises(AccessError):
            Model.set_for_user('balance_sheet', 'l1', True)
        with self.assertRaises(AccessError):
            Model.reset_for_user('balance_sheet')
