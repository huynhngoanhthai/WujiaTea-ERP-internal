# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Partner-list approval statistics security and empty-data regressions."""

from unittest.mock import patch

import odoo

from odoo import fields
from odoo.tests import tagged

from odoo.addons.eh_account_base.tests.common import (
    EhAccountIntegrationTestCase,
)
from odoo.addons.eh_account_approval.models import res_partner as partner_model


@tagged('eh_account_approval', 'post_install', '-at_install')
class TestPartnerApprovalStatistics(EhAccountIntegrationTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.company
        cls.company_b = cls.env['res.company'].create({
            'name': 'Approval Statistics Company B',
            'currency_id': cls.company.currency_id.id,
        })
        cls.shared_partner = cls.env['res.partner'].create({
            'name': 'Approval Statistics Shared Partner',
        })
        cls.empty_partner = cls.env['res.partner'].create({
            'name': 'Approval Statistics Empty Partner',
        })

        group_user = cls.env.ref('eh_account_base.group_eh_user')
        base_user = cls.env.ref('base.group_user')
        cls.approval_user = cls.env['res.users'].create({
            'name': 'Approval Statistics User',
            'login': 'approval_statistics_user@test',
            'email': 'approval_statistics_user@test',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, cls.company_a.ids)],
            'group_ids': [(6, 0, (base_user + group_user).ids)],
        })
        cls.unauthorized_user = cls.env['res.users'].create({
            'name': 'Approval Statistics Unauthorized',
            'login': 'approval_statistics_unauthorized@test',
            'email': 'approval_statistics_unauthorized@test',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, cls.company_a.ids)],
            'group_ids': [(6, 0, base_user.ids)],
        })

        allowed_companies = (cls.company_a + cls.company_b).ids
        env_a = cls.env['res.company'].sudo().with_context(
            allowed_company_ids=allowed_companies,
        ).with_company(cls.company_a).env
        env_b = cls.env['res.company'].sudo().with_context(
            allowed_company_ids=allowed_companies,
        ).with_company(cls.company_b).env
        journal_b = cls._ensure_journal(
            env_b, cls.company_b, 'general', 'APSB',
            'Approval Statistics B',
        )
        cls.request_a = cls._create_request(env_a, cls.journal_misc, 'A')
        cls.request_b = cls._create_request(env_b, journal_b, 'B')

    @classmethod
    def _create_request(cls, env, journal, suffix):
        policy = env['eh.approval.policy'].create({
            'name': 'Approval Statistics Policy %s' % suffix,
            'document_type': 'entry',
            'journal_ids': [(6, 0, journal.ids)],
            'company_id': env.company.id,
            'rule_ids': [(0, 0, {
                'name': 'Approval Statistics Rule %s' % suffix,
                'min_amount': 0.0,
                'max_amount': 0.0,
                'step_ids': [(0, 0, {
                    'group_id': env.ref(
                        'eh_account_base.group_eh_manager',
                    ).id,
                    'sequence': 10,
                })],
            })],
        })
        move = env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.today(),
            'journal_id': journal.id,
            'company_id': env.company.id,
            'partner_id': cls.shared_partner.id,
        })
        return env['eh.approval.request'].create({
            'move_id': move.id,
            'policy_id': policy.id,
            'rule_id': policy.rule_ids[0].id,
        })

    @staticmethod
    def _badge(partner):
        partner.invalidate_recordset([
            'application_statistics', 'eh_pending_approval_count',
        ])
        return next((
            item for item in (partner.application_statistics or [])
            if item.get('label') == 'Pending Approvals'
        ), None)

    def test_statistics_respect_allowed_companies(self):
        partner = self.shared_partner.with_user(
            self.approval_user,
        ).with_context(allowed_company_ids=self.company_a.ids)
        self.assertEqual(partner.eh_pending_approval_count, 1)
        self.assertEqual(self._badge(partner)['value'], 1)

        self.approval_user.company_ids = self.company_a + self.company_b
        partner = partner.with_context(
            allowed_company_ids=(self.company_a + self.company_b).ids,
        )
        self.assertEqual(self._badge(partner)['value'], 2)

    def test_badge_click_opens_filtered_list(self):
        expected_list_type = (
            'list' if odoo.release.version_info[0] >= 18 else 'tree'
        )
        partner = self.shared_partner.with_user(
            self.approval_user,
        ).with_context(allowed_company_ids=self.company_a.ids)
        badge = self._badge(partner)
        self.assertEqual(
            badge['actionMethod'], 'action_view_eh_pending_approvals',
        )

        action = getattr(partner, badge['actionMethod'])()
        self.assertEqual(action['res_model'], 'eh.approval.request')
        self.assertEqual(
            action['view_mode'], '%s,form' % expected_list_type,
        )
        self.assertEqual(
            action['views'],
            [(False, expected_list_type), (False, 'form')],
        )
        self.assertNotIn('res_id', action)
        self.assertEqual(action['domain'], [
            ('move_id.partner_id', '=', self.shared_partner.id),
            ('move_id.company_id', 'in', self.company_a.ids),
            ('state', 'in', ('pending', 'in_review')),
        ])
        requests = partner.env['eh.approval.request'].search(action['domain'])
        self.assertEqual(requests.ids, self.request_a.ids)
        self.assertEqual(len(requests), badge['value'])
        self.assertNotIn(self.request_b.id, requests.ids)

    def test_statistics_omit_zero_values(self):
        partner = self.empty_partner.with_user(self.approval_user)
        self.assertIsNone(self._badge(partner))

    def test_statistics_omit_data_for_unauthorized_user(self):
        partner = self.shared_partner.with_user(self.unauthorized_user)
        partner.invalidate_recordset(['application_statistics'])
        statistics = partner.application_statistics or []
        self.assertFalse(any(
            item.get('label') == 'Pending Approvals'
            for item in statistics
        ))

    def test_statistics_grouping_matches_series_capability(self):
        captured = []
        partner = self.shared_partner.with_user(self.approval_user)

        def capture_groupby(model, domain, groupby, aggregates):
            captured.append(groupby)
            return []

        with patch.object(partner_model, 'version_info', (19, 0, 0)), \
                patch.object(
                    partner_model,
                    'read_group_compat',
                    side_effect=capture_groupby,
                ):
            partner.invalidate_recordset(['eh_pending_approval_count'])
            self.assertEqual(partner.eh_pending_approval_count, 0)
        self.assertEqual(captured, [['move_id.partner_id']])

        captured.clear()
        with patch.object(partner_model, 'version_info', (18, 0, 0)), \
                patch.object(
                    partner_model,
                    'read_group_compat',
                    side_effect=capture_groupby,
                ):
            partner.invalidate_recordset(['eh_pending_approval_count'])
            self.assertEqual(partner.eh_pending_approval_count, 0)
        self.assertEqual(captured, [['move_id']])
