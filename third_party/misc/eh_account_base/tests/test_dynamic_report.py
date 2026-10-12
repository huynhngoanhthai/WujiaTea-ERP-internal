# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Tests for the orchestrator (eh.account.dynamic.report).

Covers:

* render() cache miss path: starts execution, calls handler, persists payload,
  marks done.
* render() cache hit path: skips handler invocation, returns stored payload
  with from_cache=True.
* Cache invalidation: bumping the move version counter forces a recompute.
* Error path: handler exceptions mark execution 'error' and re raise.
* Constraint: handler_model must reference an installed model.

The suite's own base handler is always registered with eh_account_base. Tests
patch its compute method so this module validates its orchestration contract
without silently depending on the optional dynamic-reports addon.
"""

import base64
import hashlib
import inspect
from decimal import Decimal
from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo import api
from odoo.exceptions import AccessError, UserError
from odoo.service.model import get_public_method
from odoo.tests import new_test_user, tagged
from odoo.tools import mute_logger

from odoo.addons.eh_account_base.tools.payload_codec import compress_payload
from odoo.addons.eh_account_base.tools.sql_builder import MoveLineQuery
from .common import EhAccountUnitTestCase


# Handler we patch. This abstract base belongs to eh_account_base itself and
# is therefore present even when no concrete report pack is installed.
_REAL_HANDLER = 'eh.account.dynamic.report.handler'


def _fake_compute_payload():
    """The standard payload returned by the patched compute() method."""
    return {
        'columns': [
            {'expression_label': 'value', 'name': "Value",
             'figure_type': 'monetary'},
        ],
        'lines': [
            {
                'id': 'line-1',
                'name': "Test Line",
                'level': 1,
                'columns': [
                    {'expression_label': 'value', 'value': 42.0},
                ],
            },
        ],
        'totals': {'value': 42.0},
        'generated_at': '2026-04-30T00:00:00',
    }


class _CallLog:
    calls = []

    @classmethod
    def reset(cls):
        cls.calls = []

    @classmethod
    def fake_compute(cls, *args, **kwargs):
        # Args: (self, options) on bound method, or (options,) when patched
        # with autospec=False on the class. Capture options shape.
        if args:
            options = args[-1] if not isinstance(args[-1], dict) else args[-1]
        else:
            options = kwargs.get('options') or {}
        try:
            cls.calls.append(dict(options))
        except Exception:
            cls.calls.append({})
        return _fake_compute_payload()

    @classmethod
    def failing_compute(cls, *args, **kwargs):
        raise RuntimeError("synthetic failure for tests")


@tagged('eh_account_base', 'integration', 'post_install', '-at_install')
class TestOrchestratorCacheBehaviour(EhAccountUnitTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env['eh.account.dynamic.report'].create({
            'code': 'orch_cache_test',
            'name': 'Orchestrator Cache Test',
            'handler_model': _REAL_HANDLER,
        })

    def setUp(self):
        super().setUp()
        _CallLog.reset()
        self.options = {
            'date': {'date_from': '2026-01-01', 'date_to': '2026-12-31'},
            'company_ids': [self.env.company.id],
            'posted_only': True,
            'show_zero': False,
        }

    def _patch_compute(self):
        """Return a context manager that swaps the handler's compute()."""
        return patch.object(
            type(self.env[_REAL_HANDLER]),
            'compute',
            _CallLog.fake_compute,
        )

    def test_first_render_miss_invokes_handler(self):
        with self._patch_compute():
            result = self.report.render(self.options)
        self.assertFalse(result['from_cache'])
        self.assertEqual(len(_CallLog.calls), 1)
        self.assertIn('execution_id', result)
        self.assertEqual(len(result['lines']), 1)

    def test_second_render_hit_skips_handler(self):
        with self._patch_compute():
            self.report.render(self.options)
            _CallLog.reset()
            result = self.report.render(self.options)
        self.assertTrue(result['from_cache'])
        self.assertEqual(
            len(_CallLog.calls), 0,
            "Handler should not run on cache hit",
        )
        self.assertEqual(len(result['lines']), 1)

    def test_use_cache_false_forces_recompute(self):
        with self._patch_compute():
            self.report.render(self.options)
            _CallLog.reset()
            result = self.report.render(self.options, use_cache=False)
        self.assertFalse(result['from_cache'])
        self.assertEqual(len(_CallLog.calls), 1)

    def test_move_version_bump_invalidates_cache(self):
        with self._patch_compute():
            self.report.render(self.options)
            _CallLog.reset()
            self.env['res.company']._eh_bump_move_version(
                [self.env.company.id]
            )
            result = self.report.render(self.options)
        self.assertFalse(result['from_cache'])
        self.assertEqual(len(_CallLog.calls), 1)

    def test_report_engine_schema_bump_invalidates_cache(self):
        with self._patch_compute():
            self.report.render(self.options)
            _CallLog.reset()
            with patch(
                'odoo.addons.eh_account_base.models.dynamic_report.'
                '_EH_REPORT_CACHE_SCHEMA_VERSION',
                4,
            ):
                result = self.report.render(self.options)
        self.assertFalse(result['from_cache'])
        self.assertEqual(len(_CallLog.calls), 1)
        self.assertEqual(
            _CallLog.calls[0]['_cache_context']['engine_schema'], 4,
        )

    def test_column_axis_release_uses_cache_schema_three(self):
        with self._patch_compute():
            self.report.render(self.options)
        self.assertEqual(
            _CallLog.calls[0]['_cache_context']['engine_schema'], 3,
        )

    def test_different_options_produce_different_keys(self):
        with self._patch_compute():
            result_a = self.report.render(self.options)
            options_b = dict(self.options)
            options_b['posted_only'] = False
            result_b = self.report.render(options_b)
        self.assertFalse(result_b['from_cache'])
        self.assertNotEqual(
            result_a['execution_id'], result_b['execution_id'],
        )

    def test_inactive_unsupported_axes_share_cache_and_audit_identity(self):
        with self._patch_compute():
            first = self.report.render(self.options)
            _CallLog.reset()
            with_inactive_axis_defaults = dict(
                self.options,
                comparison='none',
                comparison_number=1,
                comparison_custom_date_from='',
                comparison_custom_date_to='',
                comparison_order='descending',
                analytic_column_account_ids=[],
                analytic_column_plan_ids=[],
            )
            second = self.report.render(with_inactive_axis_defaults)
        self.assertTrue(second['from_cache'])
        self.assertFalse(_CallLog.calls)
        first_execution = self.env['eh.account.report.execution'].browse(
            first['execution_id'],
        )
        for key in (
            'comparison', 'comparison_number', 'comparison_order',
            'comparison_custom_date_from', 'comparison_custom_date_to',
            'analytic_column_account_ids', 'analytic_column_plan_ids',
        ):
            self.assertNotIn(key, first_execution.options_snapshot)

    def test_active_unsupported_axis_fails_before_execution_creation(self):
        Execution = self.env['eh.account.report.execution']
        domain = [('report_code', '=', self.report.code)]
        before = Execution.search_count(domain)
        with self._patch_compute(), self.assertRaisesRegex(
                UserError, 'does not support.*comparison columns'):
            self.report.render(dict(
                self.options,
                comparison='previous_year',
                comparison_number=1,
            ))
        self.assertEqual(Execution.search_count(domain), before)
        self.assertFalse(_CallLog.calls)

    def test_canonicalisation_makes_key_order_insensitive(self):
        with self._patch_compute():
            self.report.render(self.options)
            _CallLog.reset()
            reordered = {
                'show_zero': False,
                'company_ids': [self.env.company.id],
                'date': {'date_to': '2026-12-31',
                         'date_from': '2026-01-01'},
                'posted_only': True,
            }
            result = self.report.render(reordered)
        self.assertTrue(result['from_cache'])
        self.assertEqual(len(_CallLog.calls), 0)

    def test_effective_company_order_has_explicit_stable_primary(self):
        company2 = self.env['res.company'].with_context(
            default_group_rfq='default',
        ).create({'name': 'Orchestrator Company B'})
        self.env.user.sudo().write({'company_ids': [(4, company2.id)]})
        report = self.report.with_context(
            allowed_company_ids=[self.env.company.id, company2.id],
        )
        options = dict(self.options, company_ids=[self.env.company.id, company2.id])
        with self._patch_compute():
            report.render(options)
            first_effective = _CallLog.calls[-1]
            _CallLog.reset()
            reversed_options = dict(
                self.options,
                company_ids=[company2.id, self.env.company.id],
            )
            result = report.render(reversed_options)
        self.assertTrue(result['from_cache'])
        self.assertFalse(_CallLog.calls)
        self.assertEqual(
            first_effective['company_ids'],
            sorted([self.env.company.id, company2.id]),
        )
        self.assertEqual(
            first_effective['primary_company_id'],
            self.env.company.id,
        )

    def test_explicit_primary_company_changes_cache_identity(self):
        company2 = self.env['res.company'].with_context(
            default_group_rfq='default',
        ).create({'name': 'Orchestrator Primary Company B'})
        self.env.user.sudo().write({'company_ids': [(4, company2.id)]})
        report = self.report.with_context(
            allowed_company_ids=[self.env.company.id, company2.id],
        )
        common = dict(
            self.options,
            company_ids=[self.env.company.id, company2.id],
        )
        with self._patch_compute():
            report.render(dict(common, primary_company_id=self.env.company.id))
            _CallLog.reset()
            result = report.render(dict(common, primary_company_id=company2.id))
        self.assertFalse(result['from_cache'])
        self.assertEqual(len(_CallLog.calls), 1)
        self.assertEqual(_CallLog.calls[0]['primary_company_id'], company2.id)

    def test_mixed_ledger_currencies_fail_closed_without_handler_conversion(self):
        # Minimal databases archive every currency except company currency.
        # The orchestration guard only needs a distinct ledger currency, not
        # an actively selectable one.
        target = self.env['res.currency'].with_context(
            active_test=False,
        ).search([
            ('id', '!=', self.env.company.currency_id.id),
        ], limit=1)
        self.assertTrue(target)
        company2 = self.env['res.company'].with_context(
            default_group_rfq='default',
        ).create({
            'name': 'Orchestrator Different Currency Company',
            'currency_id': target.id,
        })
        self.env.user.sudo().write({'company_ids': [(4, company2.id)]})
        report = self.report.with_context(allowed_company_ids=[
            self.env.company.id, company2.id,
        ])
        options = dict(
            self.options,
            company_ids=[self.env.company.id, company2.id],
            presentation_currency_id=target.id,
        )
        with self._patch_compute(), self.assertRaisesRegex(
                UserError, "cannot combine companies"):
            report.render(options, use_cache=False)

    def test_presentation_currency_uses_target_precision_and_typed_totals(self):
        target = self.env['res.currency'].create({
            'name': 'ZQP', 'symbol': 'P', 'rounding': 0.001,
        })
        self.assertEqual(target.decimal_places, 3)
        self.env['res.currency.rate'].create({
            'currency_id': target.id,
            'company_id': self.env.company.id,
            'name': '2026-01-01',
            'rate': 0.12345,
        })
        payload = {
            'columns': [{
                'expression_label': 'amount',
                'figure_type': 'monetary',
            }],
            'lines': [{
                'id': 'line-1',
                'columns': [{
                    'expression_label': 'amount',
                    'value': 10.0,
                }],
            }],
            'totals': {
                'disclosures': {'interest_paid': 10.0},
                'ratio': 0.25,
                'untyped_count': 7,
            },
            'meta': {'total_figure_types': {
                'disclosures': 'monetary',
                'ratio': 'percentage',
            }},
        }
        options = dict(
            self.options,
            presentation_currency_id=target.id,
            primary_company_id=self.env.company.id,
        )
        converted = self.report._eh_apply_presentation_currency(
            payload, options, [self.env.company.id],
        )
        self.assertEqual(converted['lines'][0]['columns'][0]['value'], 1.235)
        self.assertEqual(
            converted['totals']['disclosures']['interest_paid'], 1.235,
        )
        self.assertEqual(converted['totals']['ratio'], 0.25)
        self.assertEqual(converted['totals']['untyped_count'], 7)
        self.assertEqual(converted['currency']['decimal_places'], 3)
        self.assertEqual(
            converted['meta']['currency_translation_policy'],
            'closing_spot',
        )
        self.assertEqual(
            converted['meta']['currency_translation_as_of_date'],
            '2026-12-31',
        )
        self.assertEqual(
            converted['meta']['currency_translation_rate_dates'][
                str(self.env.company.id)
            ],
            '2026-01-01',
        )

    def test_central_currency_translation_rejects_absent_or_future_rate(self):
        payload = {
            'columns': [{
                'expression_label': 'amount',
                'figure_type': 'monetary',
            }],
            'lines': [{
                'id': 'line-1',
                'columns': [{
                    'expression_label': 'amount',
                    'value': 10.0,
                }],
            }],
            'totals': {},
            'meta': {},
        }
        targets = []
        for name in ('ZQN', 'ZQF'):
            targets.append(self.env['res.currency'].create({
                'name': name, 'symbol': name[-1], 'rounding': 0.01,
            }))
        self.env['res.currency.rate'].create({
            'currency_id': targets[1].id,
            'company_id': self.env.company.id,
            'name': '2027-01-01',
            'rate': 2.0,
        })
        for target in targets:
            options = dict(
                self.options,
                presentation_currency_id=target.id,
                primary_company_id=self.env.company.id,
            )
            with self.subTest(target=target.name), self.assertRaisesRegex(
                    UserError, "No valid .* exchange rate"):
                self.report._eh_apply_presentation_currency(
                    dict(payload), options, [self.env.company.id],
                )

    def test_handler_monetary_rounding_uses_currency_precision(self):
        target = self.env.ref('base.KWD')
        handler = self.env[_REAL_HANDLER]
        self.assertEqual(
            handler._eh_round_monetary(1.2344, currency=target), 1.234,
        )
        self.assertEqual(
            handler._eh_round_monetary(1.2346, currency=target), 1.235,
        )
        self.assertFalse(
            handler._eh_is_zero_monetary(0.001, currency=target),
        )

    def test_sectioned_helpers_keep_kwd_milliunit(self):
        target = self.env.ref('base.KWD')
        self.assertEqual(target.decimal_places, 3)
        handler = self.env[
            'eh.account.dynamic.report.handler.sectioned'
        ]
        options = dict(
            self.options,
            presentation_currency_id=target.id,
        )

        comparative = handler.merge_comparative_lines(
            [{'id': 'line', 'columns': [{'value': 0.002}]}],
            [{'id': 'line', 'columns': [{'value': 0.001}]}],
            options=options,
            presentation_converted=True,
        )
        comparative_values = {
            column['expression_label']: column['value']
            for column in comparative[0]['columns']
        }
        self.assertEqual(comparative_values['variance'], 0.001)

        horizontal = handler.merge_horizontal_groups(
            [
                [{'id': 'line', 'columns': [{'value': 0.001}]}],
                [{'id': 'line', 'columns': [{'value': 0.002}]}],
            ],
            options=options,
            presentation_converted=True,
        )
        horizontal_values = {
            column['expression_label']: column['value']
            for column in horizontal[0]['columns']
        }
        self.assertEqual(horizontal_values['group_1'], 0.001)
        self.assertEqual(horizontal_values['total'], 0.003)

        rows = [{
            'account_id': 1,
            'account_code': '1000',
            'account_name': 'KWD milliunit',
            'amount': 0.001,
        }]
        rendered = handler._render_account_lines(
            rows,
            options=options,
            presentation_converted=True,
        )
        self.assertEqual(rendered[0]['columns'][0]['value'], 0.001)
        self.assertEqual(
            handler._section_total_line(
                'Total', 0.001, 'kwd', options=options,
                presentation_converted=True,
            )['columns'][0]['value'],
            0.001,
        )
        self.assertEqual(
            handler._computed_line(
                'kwd-computed', 'Computed', 0.001, options=options,
                presentation_converted=True,
            )['columns'][0]['value'],
            0.001,
        )

    def test_group_line_keeps_prefix_structured_not_in_label(self):
        # Upgrade databases retain localization groups from the baseline.
        # Isolate this rendering fixture in its own company so the ordinary
        # ``10`` prefix cannot overlap a legitimate upgraded chart range.
        company = self.env['res.company'].create({
            'name': 'Account group label regression company',
        })
        group = self.env['account.group'].create({
            'name': 'Cash Assets',
            'code_prefix_start': '10',
            'code_prefix_end': '10',
            'company_id': company.id,
        })
        # Odoo 18+ computes account.group_id from the active root company,
        # so keep account creation and rendering in the fixture company.
        Account = self.env['account.account'].with_company(company)
        company_field = (
            'company_ids' if 'company_ids' in Account._fields
            else 'company_id'
        )
        account = Account.create({
            'name': 'Cash label regression',
            'code': '109701',
            'account_type': 'asset_cash',
            company_field: (
                [(6, 0, company.ids)]
                if company_field == 'company_ids'
                else company.id
            ),
            'group_id': group.id,
        })
        handler = self.env[
            'eh.account.dynamic.report.handler.sectioned'
        ].with_company(company)
        lines = handler._render_account_lines_grouped(
            [{
                'account_id': account.id,
                'account_code': account.code,
                'account_name': account.name,
                'amount': 10.0,
            }],
            section_id='assets',
            show_zero=True,
            options={'company_ids': [company.id]},
        )
        group_line = next(
            line for line in lines
            if line.get('meta', {}).get('kind') == 'account_group'
        )
        self.assertEqual(group_line['name'], 'Cash Assets')
        self.assertEqual(group_line['meta']['group_label'], 'Cash Assets')
        self.assertEqual(group_line['meta']['group_key'], {
            'id': group.id,
            'code_prefix': '10',
        })

    def test_language_is_part_of_cache_identity(self):
        self.env['res.lang']._activate_lang('fr_FR')
        with self._patch_compute():
            self.report.with_context(lang='en_US').render(self.options)
            _CallLog.reset()
            result = self.report.with_context(lang='fr_FR').render(self.options)
        self.assertFalse(result['from_cache'])
        self.assertEqual(len(_CallLog.calls), 1)
        self.assertEqual(
            _CallLog.calls[0]['_cache_context']['lang'],
            'fr_FR',
        )

    def test_timezone_is_part_of_cache_identity(self):
        with self._patch_compute():
            self.report.with_context(tz='UTC').render(self.options)
            _CallLog.reset()
            result = self.report.with_context(
                tz='Australia/Melbourne',
            ).render(self.options)
        self.assertFalse(result['from_cache'])
        self.assertEqual(len(_CallLog.calls), 1)
        self.assertEqual(
            _CallLog.calls[0]['_cache_context']['tz'],
            'Australia/Melbourne',
        )

    def test_user_is_part_of_cache_identity(self):
        other_user = new_test_user(
            self.env,
            login='eh_report_cache_other_user',
            groups='eh_account_base.group_eh_user',
        )
        with self._patch_compute():
            self.report.render(self.options)
            _CallLog.reset()
            result = self.report.with_user(other_user).render(self.options)
        self.assertFalse(result['from_cache'])
        self.assertEqual(len(_CallLog.calls), 1)
        self.assertEqual(
            _CallLog.calls[0]['_cache_context']['uid'],
            other_user.id,
        )

    def test_real_xlsx_export_hashes_bytes_and_keeps_json_cache_semantics(self):
        options = dict(self.options, audit_nonce='real-xlsx-result-hash')
        Execution = self.env['eh.account.report.execution']

        with self._patch_compute():
            content = self.report.render_xlsx(options)
            self.assertEqual(content[:2], b'PK')
            self.assertEqual(len(_CallLog.calls), 1)

            first = Execution.search([
                ('report_code', '=', self.report.code),
            ], limit=1, order='id desc')
            self.assertEqual(first.result_format, 'xlsx')
            self.assertEqual(
                first.result_hash,
                hashlib.sha256(content).hexdigest(),
            )
            self.assertTrue(first.cache_trusted)
            self.assertTrue(first.result_payload)

            _CallLog.reset()
            cached_content = self.report.render_xlsx(options)
            self.assertFalse(_CallLog.calls)
            cached_export = Execution.search([
                ('report_code', '=', self.report.code),
            ], limit=1, order='id desc')
            self.assertEqual(cached_export.result_format, 'xlsx')
            self.assertEqual(
                cached_export.result_hash,
                hashlib.sha256(cached_content).hexdigest(),
            )
            self.assertEqual(cached_export.served_from_execution_id, first)

            # XLSX keeps the same compressed JSON cache payload that exports
            # used before this change. A JSON request with the same effective
            # eager options therefore remains a cache hit, but never inherits
            # the XLSX artifact digest.
            _CallLog.reset()
            json_result = self.report.render(dict(
                options,
                eager_expand=True,
            ))
            self.assertTrue(json_result['from_cache'])
            self.assertFalse(_CallLog.calls)
            json_execution = Execution.browse(json_result['execution_id'])
            self.assertEqual(json_execution.result_format, 'json')
            self.assertFalse(json_execution.result_hash)

    def test_direct_xlsx_export_is_private_to_exporting_user(self):
        exporter = new_test_user(
            self.env,
            login='eh_report_xlsx_exporter',
            groups='eh_account_base.group_eh_user',
        )
        other_user = new_test_user(
            self.env,
            login='eh_report_xlsx_other',
            groups='eh_account_base.group_eh_user',
        )
        ReportClass = type(self.report)
        with patch.object(ReportClass, 'render_xlsx', return_value=b'PKxlsx'):
            action = self.report.with_user(exporter).export_xlsx_attachment(
                self.options,
            )
        attachment_id = int(
            action['url'].split('/web/content/')[1].split('?')[0]
        )
        attachment = self.env['ir.attachment'].sudo().browse(attachment_id)
        self.assertEqual(attachment.create_uid, exporter)
        self.assertEqual(
            attachment.res_model, 'eh.account.report.wizard',
        )
        owner = self.env['eh.account.report.wizard'].sudo().browse(
            attachment.res_id,
        )
        self.assertEqual(owner.create_uid, exporter)
        self.assertEqual(owner.report_id, self.report)
        self.assertTrue(self.env['ir.attachment'].with_user(exporter).search([
            ('id', '=', attachment.id),
        ]))
        self.assertFalse(self.env['ir.attachment'].with_user(other_user).search([
            ('id', '=', attachment.id),
        ]))

    def test_read_only_auditor_can_create_private_export_owner(self):
        auditor = new_test_user(
            self.env,
            login='eh_report_xlsx_auditor',
            groups='eh_account_base.group_eh_auditor',
        )
        ReportClass = type(self.report)
        with patch.object(ReportClass, 'render_xlsx', return_value=b'PKxlsx'):
            action = self.report.with_user(auditor).export_xlsx_attachment(
                self.options,
            )
        attachment_id = int(
            action['url'].split('/web/content/')[1].split('?')[0]
        )
        attachment = self.env['ir.attachment'].sudo().browse(attachment_id)
        self.assertEqual(attachment.res_model, 'eh.account.report.wizard')
        owner = self.env[attachment.res_model].sudo().browse(
            attachment.res_id,
        )
        self.assertEqual(owner.create_uid, auditor)
        self.assertTrue(
            self.env['ir.attachment'].with_user(auditor).search([
                ('id', '=', attachment.id),
            ])
        )

    def test_acl_sensitive_handler_never_reuses_persistent_cache(self):
        report = self.env['eh.account.dynamic.report'].create({
            'code': 'orch_acl_sensitive_test',
            'name': 'ACL Sensitive Test',
            'handler_model': _REAL_HANDLER,
        })
        HandlerClass = type(self.env[report.handler_model])
        ReportClass = type(report)
        _CallLog.reset()
        with patch.object(
            ReportClass,
            '_EH_ACL_SENSITIVE_HANDLERS',
            frozenset({_REAL_HANDLER}),
        ), patch.object(HandlerClass, 'compute', _CallLog.fake_compute):
            report.render(self.options)
            result = report.render(self.options)
        self.assertFalse(result['from_cache'])
        self.assertEqual(len(_CallLog.calls), 2)

    def test_expand_and_drilldown_reject_foreign_primary_company(self):
        company2 = self.env['res.company'].with_context(
            default_group_rfq='default',
        ).create({'name': 'Forbidden Drilldown Company'})
        self.env.user.sudo().write({'company_ids': [(3, company2.id)]})
        options = dict(
            self.options,
            primary_company_id=company2.id,
        )
        HandlerClass = type(self.env[_REAL_HANDLER])
        with patch.object(
            HandlerClass,
            'expand_account_line',
            return_value={'child_lines': [{'id': 'leak'}]},
        ) as expand:
            result = self.report.expand_line(options, 'account-1')
        self.assertFalse(expand.called)
        self.assertEqual(result['child_lines'], [])
        with self.assertRaises(AccessError):
            self.report.get_drilldown_for_line(options, 'account-1')

    def test_expand_rpc_clamps_page_size_and_rejects_absurd_offset(self):
        HandlerClass = type(self.env[_REAL_HANDLER])
        with patch.object(
            HandlerClass,
            'expand_account_line',
            return_value={
                'child_lines': [], 'has_more': False,
                'next_offset': 5, 'total_count': 0,
            },
        ) as expand:
            self.report.expand_line(
                self.options, 'account-1', offset=5, limit=10_000_000,
            )
        self.assertEqual(expand.call_args.kwargs['offset'], 5)
        self.assertEqual(expand.call_args.kwargs['limit'], 500)

        with patch.object(HandlerClass, 'expand_account_line') as expand:
            result = self.report.expand_line(
                self.options, 'account-1', offset=100_001, limit=80,
            )
        self.assertFalse(expand.called)
        self.assertEqual(result['child_lines'], [])
        self.assertFalse(result['has_more'])

    def test_report_options_have_resource_budget(self):
        with self.assertRaisesRegex(UserError, 'too many'):
            self.report._eh_effective_options({
                'journal_ids': list(range(20_001)),
            })
        nested = {}
        cursor = nested
        for _index in range(14):
            child = {}
            cursor['child'] = child
            cursor = child
        with self.assertRaisesRegex(UserError, 'deeply'):
            self.report._eh_effective_options(nested)
        with self.assertRaisesRegex(UserError, 'too long'):
            self.report._eh_effective_options({'label': 'x' * 32_769})

    def test_definition_write_invalidates_cached_payload(self):
        with self._patch_compute():
            self.report.render(self.options)
            _CallLog.reset()
            self.report.write({'description': 'Changed report definition'})
            result = self.report.render(self.options)
        self.assertFalse(result['from_cache'])
        self.assertEqual(len(_CallLog.calls), 1)

    def test_fx_rate_write_invalidates_cached_payload(self):
        eur = self.env.ref('base.EUR')
        with self._patch_compute():
            self.report.render(self.options)
            _CallLog.reset()
            rate = self.env['res.currency.rate'].search([
                ('currency_id', '=', eur.id),
                ('company_id', '=', self.env.company.id),
                ('name', '=', '2099-12-31'),
            ], limit=1)
            if rate:
                rate.write({'rate': rate.rate + 0.123})
            else:
                self.env['res.currency.rate'].create({
                    'currency_id': eur.id,
                    'company_id': self.env.company.id,
                    'name': '2099-12-31',
                    'rate': 1.234,
                })
            result = self.report.render(self.options)
        self.assertFalse(result['from_cache'])
        self.assertEqual(len(_CallLog.calls), 1)

    def test_version_bump_between_load_and_complete_recomputes(self):
        ExecutionClass = type(self.env['eh.account.report.execution'])
        original_complete = ExecutionClass.complete_execution

        def racing_complete(execution, **kwargs):
            if kwargs.get('served_from_execution_id'):
                execution.env['res.company']._eh_bump_move_version(
                    execution.company_ids.ids,
                )
            return original_complete(execution, **kwargs)

        with self._patch_compute(), patch.object(
            ExecutionClass,
            'complete_execution',
            racing_complete,
        ):
            self.report.render(self.options)
            _CallLog.reset()
            result = self.report.render(self.options)
        self.assertFalse(result['from_cache'])
        self.assertEqual(len(_CallLog.calls), 1)

    def test_tampered_cache_attachment_forces_recompute(self):
        with self._patch_compute():
            first = self.report.render(self.options)

            execution = self.env['eh.account.report.execution'].browse(
                first['execution_id'],
            )
            attachment = self.env['ir.attachment'].sudo().search([
                ('res_model', '=', 'eh.account.report.execution'),
                ('res_id', '=', execution.id),
                ('res_field', '=', 'result_payload'),
            ], limit=1)
            self.assertTrue(attachment)
            forged = _fake_compute_payload()
            forged['totals']['value'] = 999999.0
            attachment.write({
                'datas': base64.b64encode(compress_payload(forged)),
            })
            execution.invalidate_recordset(['result_payload'])

            _CallLog.reset()
            result = self.report.render(self.options)

        self.assertFalse(result['from_cache'])
        self.assertEqual(len(_CallLog.calls), 1)
        self.assertEqual(result['totals']['value'], 42.0)


@tagged('eh_account_base', 'unit')
class TestColumnAxisFoundation(EhAccountUnitTestCase):

    def setUp(self):
        super().setUp()
        self.handler = self.env[_REAL_HANDLER]
        self.company = self.env.company

    def _period_options(self, **overrides):
        options = {
            'date': {
                'date_from': '2026-01-01',
                'date_to': '2026-01-31',
            },
            'company_ids': [self.company.id],
            'comparison': 'previous_period',
            'comparison_number': 2,
            'comparison_order': 'descending',
        }
        options.update(overrides)
        return options

    def _normalize_axis_options(self, options):
        """Exercise canonicalisation as an explicitly axis-capable handler."""
        with patch.object(
            type(self.handler),
            '_EH_COLUMN_AXIS_CAPABILITIES',
            frozenset({'comparison', 'analytic_columns'}),
        ):
            return self.handler.normalize_options(options)

    def test_unsupported_axes_fail_closed_but_global_analytics_survive(self):
        normalized = self.handler.normalize_options({
            'comparison': 'none',
            'comparison_number': 1,
            'comparison_custom_date_from': '',
            'comparison_custom_date_to': '',
            'comparison_order': 'descending',
            'analytic_column_account_ids': [],
            'analytic_column_plan_ids': [],
            'analytic_account_ids': [987654],
            'analytic_plan_ids': [456789],
        })
        for key in (
            'comparison', 'comparison_number', 'comparison_order',
            'comparison_custom_date_from', 'comparison_custom_date_to',
            'analytic_column_account_ids', 'analytic_column_plan_ids',
        ):
            self.assertNotIn(key, normalized)
        self.assertEqual(normalized['analytic_account_ids'], [987654])
        self.assertEqual(normalized['analytic_plan_ids'], [456789])

        with self.assertRaisesRegex(
                UserError, 'does not support.*comparison columns'):
            self.handler.normalize_options({
                'comparison': 'previous_period',
            })
        with self.assertRaisesRegex(
                UserError, 'does not support.*analytic columns'):
            self.handler.normalize_options({
                'analytic_column_account_ids': [1],
            })

    def test_period_scopes_have_stable_keys_and_requested_order(self):
        descending = self.handler._eh_resolve_period_scopes(
            self._period_options(), '2026-01-01', '2026-01-31',
        )
        self.assertEqual(
            [scope['key'] for scope in descending],
            [
                'period_current',
                'period_comparison_1',
                'period_comparison_2',
            ],
        )
        self.assertEqual(descending[1]['date_from'], '2025-12-01')
        self.assertEqual(descending[2]['date_to'], '2025-11-30')

        ascending = self.handler._eh_resolve_period_scopes(
            self._period_options(comparison_order='ascending'),
            '2026-01-01', '2026-01-31',
        )
        self.assertEqual(
            [scope['key'] for scope in ascending],
            [
                'period_comparison_2',
                'period_comparison_1',
                'period_current',
            ],
        )
        self.assertEqual(
            {scope['key']: scope['date_to'] for scope in descending},
            {scope['key']: scope['date_to'] for scope in ascending},
        )

    def test_custom_comparison_forces_one_range(self):
        options = self._normalize_axis_options(self._period_options(
            comparison='custom',
            comparison_number=99,
            comparison_custom_date_from='2024-02-01',
            comparison_custom_date_to='2024-02-29',
        ))
        self.assertEqual(options['comparison_number'], 1)
        scopes = self.handler._eh_resolve_period_scopes(
            options, '2026-01-01', '2026-01-31',
        )
        self.assertEqual(len(scopes), 2)
        self.assertEqual(scopes[1]['date_from'], '2024-02-01')
        self.assertEqual(scopes[1]['date_to'], '2024-02-29')

    def test_snapshot_value_scope_is_cumulative_but_keeps_period_shift(self):
        periods = self.handler._eh_resolve_period_scopes(
            self._period_options(
                comparison='previous_year', comparison_number=1,
            ),
            '2026-01-01', '2026-01-31', snapshot=True,
        )
        self.assertEqual(periods[1]['date_from'], '2025-01-01')
        values = self.handler._eh_build_value_scopes(periods, [])
        self.assertEqual(values[1]['scope']['date_from'], '0001-01-01')
        self.assertEqual(values[1]['scope']['date_to'], '2025-01-31')

    def test_column_axis_limits_fail_before_compute(self):
        with self.assertRaisesRegex(UserError, 'at most 12'):
            self._normalize_axis_options(self._period_options(
                comparison_number=13,
            ))
        periods = [
            {
                'key': 'period_%d' % index,
                'label': str(index),
                'date_from': '2026-01-01',
                'date_to': '2026-01-31',
                'company_ids': [self.company.id],
                'comparison_index': index,
            }
            for index in range(6)
        ]
        analytics = [
            {
                'key': 'analytic_account_%d' % index,
                'label': str(index),
                'analytic_account_ids': [index + 1],
                'analytic_plan_ids': [],
            }
            for index in range(8)
        ]
        with self.assertRaisesRegex(UserError, '54 value columns'):
            self.handler._eh_build_value_scopes(periods, analytics)

    def test_invalid_comparison_inputs_fail_closed(self):
        with self.assertRaisesRegex(UserError, 'Unsupported comparison mode'):
            self._normalize_axis_options(self._period_options(
                comparison='sideways',
            ))
        with self.assertRaisesRegex(UserError, 'ascending or descending'):
            self._normalize_axis_options(self._period_options(
                comparison_order='sideways',
            ))
        with self.assertRaisesRegex(UserError, 'at least one'):
            self._normalize_axis_options(self._period_options(
                comparison_number=0,
            ))
        for invalid in (3.7, Decimal('3.7'), True, None, [], {}):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                    UserError, 'whole number'):
                self._normalize_axis_options(self._period_options(
                    comparison_number=invalid,
                ))

    def test_comparison_number_integrality_applies_to_scope_resolver(self):
        for invalid in (3.7, Decimal('3.7'), True, None, [], {}):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                    UserError, 'whole number'):
                self.handler._eh_resolve_period_scopes(
                    self._period_options(comparison_number=invalid),
                    '2026-01-01', '2026-01-31',
                )
        for valid in ('3', 3.0, Decimal('3')):
            with self.subTest(valid=valid):
                scopes = self.handler._eh_resolve_period_scopes(
                    self._period_options(comparison_number=valid),
                    '2026-01-01', '2026-01-31',
                )
                self.assertEqual(len(scopes), 4)

    def test_inactive_comparison_controls_canonicalize_to_defaults(self):
        options = self._normalize_axis_options(self._period_options(
            comparison='none', comparison_number=9,
            comparison_order='ascending',
        ))
        self.assertEqual(options['comparison_number'], 1)
        self.assertEqual(options['comparison_order'], 'descending')
        self.assertFalse(self.handler._eh_column_axis_requested(options))

    def test_column_selector_id_sets_are_canonical(self):
        self.assertEqual(
            self.handler._eh_normalize_id_set(
                [11, '7', 11], 'analytic_column_account_ids',
            ),
            [7, 11],
        )
        self.assertEqual(
            self.handler._eh_normalize_id_set(
                ('11', 7, 11), 'analytic_column_account_ids',
            ),
            [7, 11],
        )
        self.assertEqual(
            self.handler._eh_normalize_id_set(
                {11, 7}, 'analytic_column_account_ids',
            ),
            [7, 11],
        )
        for invalid in (
            7, '7', {'7': True}, True, [True], [7.5],
        ):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                    UserError, 'record IDs'):
                self.handler._eh_normalize_id_set(
                    invalid, 'analytic_column_account_ids',
                )
        with self.assertRaisesRegex(UserError, 'positive record IDs'):
            self.handler._eh_normalize_id_set(
                [0], 'analytic_column_account_ids',
            )

    def test_analytic_acl_guard_uses_cross_version_suite_api(self):
        source = inspect.getsource(
            type(self.handler)._eh_resolve_analytic_column_scopes,
        )
        self.assertIn("records._eh_check_access('read')", source)
        self.assertNotIn("records.check_access('read')", source)

    def test_analytic_plan_scope_expands_descendants_stably(self):
        parent = self.env['account.analytic.plan'].create({
            'name': 'Axis Parent Plan',
        })
        child = self.env['account.analytic.plan'].create({
            'name': 'Axis Child Plan',
            'parent_id': parent.id,
        })
        account = self.env['account.analytic.account'].create({
            'name': 'Axis Child Account',
            'plan_id': child.id,
            'company_id': self.company.id,
        })
        options = {
            'analytic_column_plan_ids': [parent.id],
            'analytic_column_account_ids': [],
        }
        scopes = self.handler._eh_resolve_analytic_column_scopes(
            options, [self.company.id],
        )
        self.assertEqual(len(scopes), 1)
        self.assertEqual(scopes[0]['key'], 'analytic_plan_%d' % parent.id)
        self.assertIn(account.id, scopes[0]['analytic_account_ids'])
        self.assertEqual(scopes[0]['analytic_plan_ids'], [parent.id])

    def test_analytic_column_selection_obeys_caller_acl(self):
        plan = self.env['account.analytic.plan'].create({
            'name': 'Axis ACL Plan',
        })
        account = self.env['account.analytic.account'].create({
            'name': 'Axis ACL Account',
            'plan_id': plan.id,
            'company_id': self.company.id,
        })
        user = new_test_user(
            self.env,
            login='axis_without_analytic_acl',
            groups='base.group_public',
            company_id=self.company.id,
            company_ids=[(6, 0, [self.company.id])],
        )
        with self.assertRaises(AccessError):
            self.handler.with_user(user)._eh_resolve_analytic_column_scopes(
                {'analytic_column_account_ids': [account.id]},
                [self.company.id],
            )

    def test_analytic_account_must_match_selected_company(self):
        other_company = self.env['res.company'].create({
            'name': 'Axis Other Company',
        })
        plan = self.env['account.analytic.plan'].create({
            'name': 'Axis Company Plan',
        })
        account = self.env['account.analytic.account'].create({
            'name': 'Axis Other Company Account',
            'plan_id': plan.id,
            'company_id': other_company.id,
        })
        with self.assertRaisesRegex(UserError, 'outside selected company'):
            self.handler._eh_resolve_analytic_column_scopes(
                {'analytic_column_account_ids': [account.id]},
                [self.company.id],
            )

    def test_scope_overlay_preserves_global_analytic_filters(self):
        options = self._period_options(
            analytic_account_ids=[91],
            analytic_plan_ids=[92],
            analytic_column_account_ids=[93],
        )
        value_scope = {
            'key': 'amount__period_current__analytic_account_93',
            'scope': {
                'date_from': '2025-01-01',
                'date_to': '2025-01-31',
                'company_ids': [self.company.id],
                'analytic_account_ids': [93],
                'analytic_plan_ids': [],
                'comparison_index': 1,
                'is_total': False,
            },
        }
        scoped = self.handler._eh_scope_options(options, value_scope)
        self.assertEqual(scoped['analytic_account_ids'], [91])
        self.assertEqual(scoped['analytic_plan_ids'], [92])
        self.assertEqual(scoped['_eh_analytic_column_account_ids'], [93])
        self.assertEqual(scoped['analytic_column_account_ids'], [])
        self.assertEqual(scoped['date']['date_from'], '2025-01-01')
        self.assertFalse(scoped['lazy_expand'])

    def test_analytic_drilldown_fails_closed_not_gross(self):
        base = self._period_options(comparison='none')
        self.assertIsNone(self.handler.get_drilldown_action(
            dict(base, analytic_account_ids=[7]),
            'account-1',
        ))
        self.assertIsNone(self.handler.get_drilldown_action(
            dict(base, _eh_analytic_column_account_ids=[7]),
            'account-1',
        ))
        # Independent Total clears only column allocation.  With no global
        # analytic row filter, native AML rows still reconcile to baseline.
        total_options = dict(
            base,
            _eh_analytic_column_account_ids=[],
            _eh_analytic_column_plan_ids=[],
            _eh_analytic_column_is_total=True,
        )
        self.assertIsNotNone(self.handler.get_drilldown_action(
            total_options, 'account-1',
        ))

    def test_value_scope_keys_and_baseline_are_deterministic(self):
        periods = self.handler._eh_resolve_period_scopes(
            self._period_options(comparison='none'),
            '2026-01-01', '2026-01-31',
        )
        analytics = [
            {
                'key': 'analytic_account_7',
                'label': 'Seven',
                'analytic_account_ids': [7],
                'analytic_plan_ids': [],
            },
            {
                'key': 'analytic_account_11',
                'label': 'Eleven',
                'analytic_account_ids': [11],
                'analytic_plan_ids': [],
            },
        ]
        scopes = self.handler._eh_build_value_scopes(periods, analytics)
        self.assertEqual(
            [scope['key'] for scope in scopes],
            [
                'amount__period_current__analytic_account_7',
                'amount__period_current__analytic_account_11',
                'amount__period_current__analytic_total',
            ],
        )
        self.assertEqual(scopes[-1]['analytic_key'], 'analytic_total')
        self.assertTrue(scopes[-1]['scope']['is_total'])
        self.assertEqual(scopes[-1]['scope']['analytic_account_ids'], [])
        self.assertEqual(scopes[-1]['scope']['analytic_plan_ids'], [])

    def test_merge_uses_independent_total_for_overlap_and_unallocated(self):
        period = self.handler._eh_resolve_period_scopes(
            self._period_options(comparison='none'),
            '2026-01-01', '2026-01-31',
        )
        scopes = self.handler._eh_build_value_scopes(period, [
            {
                'key': 'analytic_account_7',
                'label': 'Seven',
                'analytic_account_ids': [7],
                'analytic_plan_ids': [],
            },
            {
                'key': 'analytic_plan_3',
                'label': 'Plan Three',
                'analytic_account_ids': [7, 11],
                'analytic_plan_ids': [3],
            },
        ])
        scoped_results = [
            {
                'scope': scopes[0],
                'lines': [{
                    'id': 'line', 'name': 'Line', 'level': 1,
                    'columns': [{'value': 60.0}],
                }],
                'totals': {'amount': 60.0},
            },
            {
                'scope': scopes[1],
                'lines': [{
                    'id': 'line', 'name': 'Line', 'level': 1,
                    'columns': [{'value': 100.0}],
                }],
                'totals': {'amount': 100.0},
            },
            {
                'scope': scopes[2],
                'lines': [{
                    'id': 'line', 'name': 'Line', 'level': 1,
                    'columns': [{'value': 150.0}],
                }],
                'totals': {'amount': 150.0},
            },
        ]
        merged = self.handler.merge_scoped_results(scoped_results)
        values = [cell['value'] for cell in merged['lines'][0]['columns']]
        # Visible groups overlap (60 is contained by Plan Three) and 50 is
        # unallocated.  Baseline must remain its independently queried 150.
        self.assertEqual(values, [60.0, 100.0, 150.0])
        self.assertEqual(merged['totals'][scopes[-1]['key']], 150.0)

    def test_merge_keeps_later_only_leaf_inside_section(self):
        periods = self.handler._eh_resolve_period_scopes(
            self._period_options(comparison_number=1),
            '2026-01-01', '2026-01-31',
        )
        scopes = self.handler._eh_build_value_scopes(periods, [])
        merged = self.handler.merge_scoped_results([
            {
                'scope': scopes[0],
                'lines': [
                    {'id': 'section', 'columns': [{'value': 0.0}]},
                    {'id': 'section-total', 'columns': [{'value': 0.0}]},
                    {'id': 'grand-total', 'columns': [{'value': 0.0}]},
                ],
                'totals': 0.0,
            },
            {
                'scope': scopes[1],
                'lines': [
                    {'id': 'section', 'columns': [{'value': 0.0}]},
                    {
                        'id': 'prior-only', 'parent_id': 'section',
                        'unfoldable': False,
                        'columns': [{'value': 7.0}],
                    },
                    {'id': 'section-total', 'columns': [{'value': 7.0}]},
                    {'id': 'grand-total', 'columns': [{'value': 7.0}]},
                ],
                'totals': 7.0,
            },
        ])
        self.assertEqual(
            [line['id'] for line in merged['lines']],
            ['section', 'prior-only', 'section-total', 'grand-total'],
        )
        leaf = next(
            line for line in merged['lines']
            if line['id'] == 'prior-only'
        )
        self.assertEqual(leaf['parent_id'], 'section')
        self.assertFalse(leaf['unfoldable'])

    def test_legacy_single_comparison_does_not_request_new_axis(self):
        self.assertFalse(self.handler._eh_column_axis_requested(
            self._period_options(comparison_number=1),
            allow_analytic=True,
        ))
        self.assertTrue(self.handler._eh_column_axis_requested(
            self._period_options(comparison_number=1,
                                 comparison_order='ascending'),
        ))


@tagged('eh_account_base', 'integration', 'post_install', '-at_install')
class TestOrchestratorErrorPath(EhAccountUnitTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env['eh.account.dynamic.report'].create({
            'code': 'orch_error_test',
            'name': 'Orchestrator Error Test',
            'handler_model': _REAL_HANDLER,
        })

    def test_handler_exception_marks_execution_error(self):
        # Manually catch the exception rather than using assertRaises,
        # because Odoo 19's _assertRaises wraps the block in a savepoint
        # that rolls back on exception. That rollback would also undo
        # the fail_execution() write we want to inspect.
        Execution = self.env['eh.account.report.execution']
        raised = False
        with patch.object(
            type(self.env[_REAL_HANDLER]),
            'compute',
            _CallLog.failing_compute,
        ):
            try:
                self.report.render({
                    'date': {'date_from': '2026-01-01',
                             'date_to': '2026-12-31'},
                    'company_ids': [self.env.company.id],
                })
            except RuntimeError as exc:
                raised = True
                self.assertIn('synthetic failure', str(exc))
        self.assertTrue(raised, "render should have re raised RuntimeError")
        self.env.flush_all()
        Execution.invalidate_model()
        last = Execution.search(
            [('report_code', '=', 'orch_error_test')],
            limit=1, order='executed_at desc',
        )
        self.assertTrue(last)
        self.assertEqual(last.state, 'error')
        self.assertIn('synthetic failure', last.error_message)

    def test_failure_audit_survives_request_transaction_rollback(self):
        """Exercise a committed Base report through an RPC-like cursor."""
        registry = self.env.registry
        report_code = 'orch_error_durable_base_test'
        report_id = False
        # The durable audit deliberately uses an independent transaction.
        # Commit a Base-owned report definition first, while suppressing only
        # the cache epoch bump so this setup cannot wait on the TransactionCase
        # cursor's uncommitted singleton epoch row.
        with registry.cursor() as setup_cr:
            setup_env = api.Environment(
                setup_cr,
                self.env.uid,
                {'allowed_company_ids': [self.env.company.id]},
            )
            ReportClass = type(setup_env['eh.account.dynamic.report'])
            with patch.object(
                ReportClass,
                '_eh_invalidate_definition_cache',
                lambda reports: None,
            ):
                setup_env['eh.account.dynamic.report'].search([
                    ('code', '=', report_code),
                ]).unlink()
                committed_report = setup_env[
                    'eh.account.dynamic.report'
                ].create({
                    'code': report_code,
                    'name': 'Base Durable Failure Test',
                    'handler_model': _REAL_HANDLER,
                })
                report_id = committed_report.id
            setup_cr.commit()
        with registry.cursor() as check_cr:
            check_cr.execute(
                "SELECT COALESCE(MAX(id), 0) "
                "FROM eh_account_report_execution",
            )
            previous_id = check_cr.fetchone()[0]

        try:
            raised = False
            with registry.cursor() as request_cr:
                request_env = api.Environment(
                    request_cr,
                    self.env.uid,
                    {'allowed_company_ids': [self.env.company.id]},
                )
                committed_report = request_env[
                    'eh.account.dynamic.report'
                ].browse(report_id)
                with patch.object(
                    type(request_env[_REAL_HANDLER]),
                    'compute',
                    _CallLog.failing_compute,
                ):
                    try:
                        committed_report.render({
                            'date': {
                                'date_from': '2026-01-01',
                                'date_to': '2026-12-31',
                            },
                            'company_ids': [self.env.company.id],
                        })
                    except RuntimeError:
                        raised = True
                request_cr.rollback()
            self.assertTrue(raised)

            with registry.cursor() as verify_cr:
                verify_cr.execute(
                    "SELECT state, error_message "
                    "FROM eh_account_report_execution "
                    "WHERE id > %s AND report_code = %s "
                    "ORDER BY id DESC LIMIT 1",
                    [previous_id, report_code],
                )
                row = verify_cr.fetchone()
            self.assertTrue(row)
            self.assertEqual(row[0], 'error')
            self.assertIn('synthetic failure', row[1])
        finally:
            with registry.cursor() as cleanup_cr:
                cleanup_env = api.Environment(
                    cleanup_cr,
                    self.env.uid,
                    {'allowed_company_ids': [self.env.company.id]},
                )
                ReportClass = type(cleanup_env['eh.account.dynamic.report'])
                with patch.object(
                    ReportClass,
                    '_eh_invalidate_definition_cache',
                    lambda reports: None,
                ):
                    cleanup_env['eh.account.dynamic.report'].browse(
                        report_id,
                    ).unlink()
                cleanup_cr.commit()


@tagged('eh_account_base', 'integration', 'post_install', '-at_install')
class TestOrchestratorConstraints(EhAccountUnitTestCase):

    def test_unknown_handler_model_rejected(self):
        with self.assertRaises(UserError):
            self.env['eh.account.dynamic.report'].create({
                'code': 'bad_test',
                'name': 'Bad',
                'handler_model': 'eh.does.not.exist',
            })

    def test_duplicate_code_rejected(self):
        first = self.env['eh.account.dynamic.report'].create({
            'code': 'unique_test',
            'name': 'First',
            'handler_model': _REAL_HANDLER,
        })
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), \
                self.env.cr.savepoint():
            self.env['eh.account.dynamic.report'].create({
                'code': 'unique_test',
                'name': 'Second',
                'handler_model': _REAL_HANDLER,
            })
        self.assertTrue(first.exists())

    def test_get_default_options_returns_dict(self):
        report = self.env['eh.account.dynamic.report'].create({
            'code': 'defaults_test',
            'name': 'Defaults',
            'handler_model': _REAL_HANDLER,
        })
        opts = report.get_default_options()
        self.assertIn('date', opts)
        self.assertIn('company_ids', opts)
        self.assertEqual(opts['posted_only'], True)

    def test_handler_engine_methods_are_not_rpc_public(self):
        """Raw-SQL handlers must run only behind scoped orchestrator."""
        handler = self.env[_REAL_HANDLER]
        for method_name in (
            'compute',
            'build_default_options',
            'resolve_currency_info',
            'apply_common_filters',
            'get_drilldown_action',
            'expand_account_line',
        ):
            with self.subTest(method=method_name), self.assertRaises(
                    AccessError):
                get_public_method(handler, method_name)

    def test_binary_render_lifecycle_is_not_rpc_public(self):
        report_model = self.env['eh.account.dynamic.report']
        for method_name in (
            '_eh_render_result',
            '_eh_finalize_rendered_result',
            '_eh_private_download_action',
        ):
            with self.subTest(method=method_name), self.assertRaises(
                    AccessError):
                get_public_method(report_model, method_name)

    def test_common_account_type_filter_reaches_sql(self):
        """Visible account-type option must constrain report computation."""
        handler = self.env[_REAL_HANDLER]
        query = MoveLineQuery(
            self.env,
            company_ids=[self.env.company.id],
        ).select_balance_sum()
        handler.apply_common_filters(query, {
            'account_type_ids': ['liability_payable'],
        })
        sql = query.build()
        self.assertIn('acc.account_type IN', sql.code)
        self.assertIn(('liability_payable',), sql.params)

    def test_common_account_type_filter_reaches_drilldown_domain(self):
        handler = self.env[_REAL_HANDLER]
        domain = handler._eh_drilldown_filter_domain({
            'account_type_ids': ['income', 'income_other'],
        })
        self.assertIn(
            ('account_id.account_type', 'in', ['income', 'income_other']),
            domain,
        )


@tagged('eh_account_base', 'unit')
class TestAnalyticDetailPageSnapshot(EhAccountUnitTestCase):

    def setUp(self):
        super().setUp()
        self.handler = self.env[
            'eh.account.dynamic.report.handler.sectioned'
        ]
        self.currency = self.env.company.currency_id
        self.scope = {
            'scope': {
                'date_from': '2026-01-01',
                'date_to': '2026-12-31',
                'analytic_account_ids': [51],
                'analytic_plan_ids': [],
                'comparison_index': 0,
                'is_total': False,
            },
        }
        self.binding = {
            'execution_id': 91,
            'options_hash': 'a' * 64,
            'displayed_amount': 100.0,
        }

    def _token(self, rows, amounts, limit=1):
        return self.handler._eh_analytic_drilldown_page_token(
            rows, amounts, 100.0, self.currency, self.scope,
            'account-4000', 'amount__aa51', limit, self.binding,
        )

    def test_candidate_digest_detects_equal_count_and_total_replacement(self):
        original = self._token([
            {'move_line_id': 11, 'move_id': 21},
            {'move_line_id': 12, 'move_id': 22},
        ], [40.0, 60.0])
        replaced = self._token([
            {'move_line_id': 11, 'move_id': 21},
            {'move_line_id': 99, 'move_id': 88},
        ], [40.0, 60.0])
        redistributed = self._token([
            {'move_line_id': 11, 'move_id': 21},
            {'move_line_id': 12, 'move_id': 22},
        ], [30.0, 70.0])
        self.assertNotEqual(original, replaced)
        self.assertNotEqual(original, redistributed)

    def test_page_token_binds_page_size_and_sequence(self):
        rows = [{'move_line_id': 11, 'move_id': 21}]
        token = self._token(rows, [100.0], limit=1)
        self.assertNotEqual(token, self._token(rows, [100.0], limit=2))
        self.handler._eh_assert_analytic_drilldown_page_token(
            1, token, token,
        )
        with self.assertRaisesRegex(UserError, 'opened in sequence'):
            self.handler._eh_assert_analytic_drilldown_page_token(
                1, None, token,
            )
        with self.assertRaisesRegex(UserError, 'changed while paging'):
            self.handler._eh_assert_analytic_drilldown_page_token(
                1, 'b' * 64, token,
            )
