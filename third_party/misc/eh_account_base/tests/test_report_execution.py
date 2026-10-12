# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Unit tests for eh.account.report.execution.

Covers:

* Lifecycle: start_execution -> complete_execution / fail_execution.
* Options canonicalisation: deterministic across input orderings.
* Hash stability: same canonical form yields same hash.
* find_cached: matches by (report_code, options_hash, version) and misses
  when any component drifts.
* Move version snapshotting: the audit row records version at start.
"""

import base64
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError
from odoo.service.model import get_public_method
from odoo.tests import new_test_user, tagged
from odoo.tools import Query

from odoo.addons.eh_account_base.models import report_execution as execution_model
from odoo.addons.eh_account_base.models.report_execution import (
    EhAccountReportExecution,
)
from odoo.addons.eh_account_base.tools.payload_codec import compress_payload
from .common import EhAccountUnitTestCase


@tagged('eh_account_base', 'unit')
class TestOptionsCanonicalisation(EhAccountUnitTestCase):

    def test_dict_keys_sorted(self):
        a = EhAccountReportExecution._canonicalise_options({'b': 1, 'a': 2})
        b = EhAccountReportExecution._canonicalise_options({'a': 2, 'b': 1})
        self.assertEqual(json.dumps(a, sort_keys=True),
                         json.dumps(b, sort_keys=True))

    def test_nested_dict_canonicalised(self):
        a = EhAccountReportExecution._canonicalise_options({
            'filters': {'b': 1, 'a': 2},
            'meta': {'y': 'z', 'x': 'w'},
        })
        b = EhAccountReportExecution._canonicalise_options({
            'meta': {'x': 'w', 'y': 'z'},
            'filters': {'a': 2, 'b': 1},
        })
        self.assertEqual(json.dumps(a, sort_keys=True),
                         json.dumps(b, sort_keys=True))

    def test_list_order_preserved(self):
        # Lists may carry meaningful order; do not sort them.
        result = EhAccountReportExecution._canonicalise_options([3, 1, 2])
        self.assertEqual(result, [3, 1, 2])

    def test_semantically_unordered_option_lists_hash_identically(self):
        left = {
            'unfolded_lines': ['section-b', 'section-a'],
            'company_ids': [8, 3],
            'journal_ids': [5, 2],
            'partner_ids': [13, 11],
            'account_ids': [23, 17],
            'analytic_account_ids': [31, 29],
            'analytic_plan_ids': [41, 37],
            'analytic_column_account_ids': [47, 43],
            'analytic_column_plan_ids': [59, 53],
        }
        right = {
            key: list(reversed(value)) for key, value in left.items()
        }
        canonical_left = EhAccountReportExecution._canonicalise_options(left)
        canonical_right = EhAccountReportExecution._canonicalise_options(right)
        self.assertEqual(canonical_left, canonical_right)
        self.assertEqual(
            EhAccountReportExecution._hash_string(json.dumps(
                canonical_left, sort_keys=True,
            )),
            EhAccountReportExecution._hash_string(json.dumps(
                canonical_right, sort_keys=True,
            )),
        )

    def test_set_is_sorted(self):
        result = EhAccountReportExecution._canonicalise_options({3, 1, 2})
        self.assertEqual(result, [1, 2, 3])

    def test_scalar_passthrough(self):
        for value in (1, 1.5, 'hello', True, False, None):
            self.assertEqual(
                EhAccountReportExecution._canonicalise_options(value), value,
            )

    def test_hash_is_stable_across_dict_orderings(self):
        h1 = EhAccountReportExecution._hash_string(
            json.dumps(
                EhAccountReportExecution._canonicalise_options({'b': 1, 'a': 2}),
                sort_keys=True,
            )
        )
        h2 = EhAccountReportExecution._hash_string(
            json.dumps(
                EhAccountReportExecution._canonicalise_options({'a': 2, 'b': 1}),
                sort_keys=True,
            )
        )
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_hash_differs_on_value_change(self):
        h1 = EhAccountReportExecution._hash_string(json.dumps({'a': 1}, sort_keys=True))
        h2 = EhAccountReportExecution._hash_string(json.dumps({'a': 2}, sort_keys=True))
        self.assertNotEqual(h1, h2)


@tagged('eh_account_base', 'integration')
class TestReportExecutionLifecycle(EhAccountUnitTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.eh_user = new_test_user(
            cls.env,
            login='eh_report_execution_security_user',
            groups='eh_account_base.group_eh_user',
        )

    def setUp(self):
        super().setUp()
        self.Execution = self.env['eh.account.report.execution']
        self.company = self.env.company

    @staticmethod
    def _payload(marker='trusted'):
        return compress_payload({
            'lines': [{'id': 'line-1', 'value': 42}],
            'marker': marker,
        })

    def test_start_execution_creates_running_record(self):
        execution = self.Execution.start_execution(
            report_code='profit_loss',
            name='Profit and Loss',
            options={'date': {'from': '2026-01-01', 'to': '2026-12-31'}},
            company_ids=[self.company.id],
            result_format='json',
        )
        self.assertEqual(execution.state, 'running')
        self.assertEqual(execution.report_code, 'profit_loss')
        self.assertEqual(execution.executed_by, self.env.user)
        self.assertEqual(len(execution.options_hash), 64)
        self.assertIn('2026-01-01', execution.options_snapshot)

    def test_start_execution_requires_companies(self):
        with self.assertRaises(ValueError):
            self.Execution.start_execution(
                report_code='profit_loss',
                name='PL',
                options={},
                company_ids=[],
            )

    def test_start_execution_records_move_version_snapshot(self):
        # Bump the company version directly.
        self.env['res.company']._eh_bump_move_version([self.company.id])
        version_before = self.company.eh_move_version
        execution = self.Execution.start_execution(
            report_code='profit_loss',
            name='PL',
            options={},
            company_ids=[self.company.id],
        )
        self.assertEqual(execution.move_version_at_start, version_before)

    def test_complete_execution_marks_done(self):
        payload = self._payload()
        execution = self.Execution.start_execution(
            report_code='profit_loss',
            name='PL',
            options={},
            company_ids=[self.company.id],
        )
        execution.complete_execution(
            row_count=42,
            result_hash='abc' * 21 + 'd',
            result_payload=payload,
        )
        self.assertEqual(execution.state, 'done')
        self.assertEqual(execution.row_count, 42)
        self.assertGreaterEqual(execution.duration_ms, 0)
        self.assertTrue(execution.cache_trusted)
        self.assertEqual(len(execution.payload_hash), 64)
        self.assertEqual(
            execution._load_trusted_payload()['marker'],
            'trusted',
        )

    def test_bound_json_snapshot_requires_owner_and_exact_identity(self):
        options = {'date': '2026-04-30'}
        execution = self.Execution.start_execution(
            report_code='trial_balance',
            name='TB bound snapshot',
            options=options,
            company_ids=[self.company.id],
        )
        execution.complete_execution(result_payload=self._payload('bound'))
        actor_execution = self.Execution.browse(execution.id)
        self.assertEqual(
            actor_execution._eh_load_bound_json_snapshot(
                'trial_balance', execution.options_hash, [self.company.id],
            )['marker'],
            'bound',
        )
        with self.assertRaises(AccessError):
            actor_execution._eh_load_bound_json_snapshot(
                'balance_sheet', execution.options_hash, [self.company.id],
            )
        with self.assertRaises(AccessError):
            actor_execution.with_user(
                self.eh_user,
            )._eh_load_bound_json_snapshot(
                'trial_balance', execution.options_hash, [self.company.id],
            )

    def test_bound_json_snapshot_follows_matching_cache_source(self):
        options = {'date': '2026-04-30'}
        source = self.Execution.start_execution(
            report_code='trial_balance', name='TB source', options=options,
            company_ids=[self.company.id],
        )
        source.complete_execution(result_payload=self._payload('source'))
        audit = self.Execution.start_execution(
            report_code='trial_balance', name='TB cache hit', options=options,
            company_ids=[self.company.id],
        )
        self.assertTrue(audit.complete_execution(
            served_from_execution_id=source.id,
        ))
        actor_audit = self.Execution.browse(audit.id)
        self.assertEqual(
            actor_audit._eh_load_bound_json_snapshot(
                'trial_balance', audit.options_hash, [self.company.id],
            )['marker'],
            'source',
        )

    def test_autovacuum_expires_cache_bytes_but_preserves_audit_row(self):
        old = self.Execution.start_execution(
            report_code='profit_loss',
            name='PL retained audit',
            options={'date': '2026-01-31'},
            company_ids=[self.company.id],
        )
        result_hash = 'a' * 64
        old.complete_execution(
            row_count=7,
            result_hash=result_hash,
            result_payload=self._payload('expired'),
        )
        old.write({
            'executed_at': fields.Datetime.now() - timedelta(days=31),
        })
        fresh = self.Execution.start_execution(
            report_code='profit_loss',
            name='PL fresh cache',
            options={'date': '2026-02-28'},
            company_ids=[self.company.id],
        )
        fresh.complete_execution(result_payload=self._payload('fresh'))

        self.assertEqual(self.Execution._gc_expired_cache_payloads(), 1)
        (old | fresh).invalidate_recordset([
            'result_payload', 'payload_hash', 'cache_trusted',
        ])
        self.assertTrue(old.exists())
        self.assertEqual(old.options_snapshot, '{\n  "date": "2026-01-31"\n}')
        self.assertEqual(old.result_hash, result_hash)
        self.assertFalse(old.result_payload)
        self.assertFalse(old.payload_hash)
        self.assertFalse(old.cache_trusted)
        self.assertTrue(fresh.result_payload)
        self.assertTrue(fresh.cache_trusted)

    def test_fail_execution_marks_error(self):
        execution = self.Execution.start_execution(
            report_code='profit_loss',
            name='PL',
            options={},
            company_ids=[self.company.id],
        )
        execution.fail_execution("boom: SQL syntax error at line 42")
        self.assertEqual(execution.state, 'error')
        self.assertIn('SQL syntax error', execution.error_message)

    def test_fail_execution_truncates_long_error_message(self):
        execution = self.Execution.start_execution(
            report_code='pl',
            name='pl',
            options={},
            company_ids=[self.company.id],
        )
        long_msg = 'x' * 20000
        execution.fail_execution(long_msg)
        self.assertEqual(len(execution.error_message), 8000)

    def test_find_cached_matches_recent_done_execution(self):
        options = {'date': '2026-04-30'}
        execution = self.Execution.start_execution(
            report_code='trial_balance',
            name='TB',
            options=options,
            company_ids=[self.company.id],
        )
        execution.complete_execution(
            row_count=10,
            result_payload=self._payload(),
        )

        found = self.Execution.find_cached(
            report_code='trial_balance',
            options_hash=execution.options_hash,
            company_ids=[self.company.id],
        )
        self.assertEqual(found, execution)

    def test_find_cached_misses_when_version_changed(self):
        options = {'date': '2026-04-30'}
        execution = self.Execution.start_execution(
            report_code='trial_balance',
            name='TB',
            options=options,
            company_ids=[self.company.id],
        )
        execution.complete_execution(
            row_count=10,
            result_payload=self._payload(),
        )

        # Bump the version so the cached version no longer matches.
        self.env['res.company']._eh_bump_move_version([self.company.id])

        found = self.Execution.find_cached(
            report_code='trial_balance',
            options_hash=execution.options_hash,
            company_ids=[self.company.id],
        )
        self.assertFalse(found)

    def test_cache_hit_completion_rechecks_version_and_source_identity(self):
        options = {'date': '2026-04-30'}
        source = self.Execution.start_execution(
            report_code='trial_balance',
            name='TB',
            options=options,
            company_ids=[self.company.id],
        )
        source.complete_execution(result_payload=self._payload())
        audit = self.Execution.start_execution(
            report_code='trial_balance',
            name='TB',
            options=options,
            company_ids=[self.company.id],
        )

        self.env['res.company']._eh_bump_move_version([self.company.id])
        self.assertFalse(audit.complete_execution(
            served_from_execution_id=source.id,
        ))
        self.assertEqual(audit.state, 'running')

        audit.refresh_execution_snapshot()
        audit.complete_execution(result_payload=self._payload('recomputed'))
        self.assertEqual(audit.state, 'done')
        self.assertEqual(
            audit._load_trusted_payload()['marker'],
            'recomputed',
        )

    def test_cache_hit_rejects_different_options_source(self):
        source = self.Execution.start_execution(
            report_code='trial_balance',
            name='TB',
            options={'date': '2026-04-30'},
            company_ids=[self.company.id],
        )
        source.complete_execution(result_payload=self._payload())
        audit = self.Execution.start_execution(
            report_code='trial_balance',
            name='TB',
            options={'date': '2026-05-31'},
            company_ids=[self.company.id],
        )
        self.assertFalse(audit.complete_execution(
            served_from_execution_id=source.id,
        ))
        self.assertEqual(audit.state, 'running')

    def test_completion_does_not_cache_payload_from_stale_snapshot(self):
        execution = self.Execution.start_execution(
            report_code='trial_balance',
            name='TB',
            options={},
            company_ids=[self.company.id],
        )
        self.env['res.company']._eh_bump_move_version([self.company.id])
        execution.complete_execution(result_payload=self._payload())
        self.assertEqual(execution.state, 'done')
        self.assertFalse(execution.cache_trusted)
        self.assertFalse(execution.result_payload)
        self.assertFalse(execution.payload_hash)

    def test_find_cached_misses_when_options_differ(self):
        execution = self.Execution.start_execution(
            report_code='trial_balance',
            name='TB',
            options={'date': '2026-04-30'},
            company_ids=[self.company.id],
        )
        execution.complete_execution(
            row_count=10,
            result_payload=self._payload(),
        )

        found = self.Execution.find_cached(
            report_code='trial_balance',
            options_hash='deadbeef' * 8,
            company_ids=[self.company.id],
        )
        self.assertFalse(found)

    def test_find_cached_skips_running_executions(self):
        execution = self.Execution.start_execution(
            report_code='trial_balance',
            name='TB',
            options={'date': '2026-04-30'},
            company_ids=[self.company.id],
        )
        # Do NOT call complete_execution: state stays 'running'.
        found = self.Execution.find_cached(
            report_code='trial_balance',
            options_hash=execution.options_hash,
            company_ids=[self.company.id],
        )
        self.assertFalse(found)

    def test_find_cached_strict_company_scope(self):
        """Cache lookup must require an exact match on company_ids.

        Regression: the previous implementation used ('company_ids',
        'in', X) which matches overlapping sets, so a render against
        [c1, c2] could pick up a cached row computed for [c1] alone.
        With company_ids_key the lookup is strict equality on the
        sorted-comma representation.
        """
        company2 = self.env['res.company'].with_context(
            default_group_rfq='default',
        ).create({
            'name': 'Cache Scope Test Co 2',
        })
        options = {'date': '2026-05-31'}
        # Cache an execution scoped to a single company.
        single = self.Execution.start_execution(
            report_code='trial_balance',
            name='TB',
            options=options,
            company_ids=[self.company.id],
        )
        single.complete_execution(
            row_count=42,
            result_payload=self._payload(),
        )

        # A render request for a wider scope must not pick up the
        # narrow-scope cache, even though the overlap is non empty.
        found = self.Execution.find_cached(
            report_code='trial_balance',
            options_hash=single.options_hash,
            company_ids=[self.company.id, company2.id],
        )
        self.assertFalse(found, "wide scope must not match narrow cache")

        # Original scope still hits.
        found_same = self.Execution.find_cached(
            report_code='trial_balance',
            options_hash=single.options_hash,
            company_ids=[self.company.id],
        )
        self.assertEqual(found_same, single)

    def test_company_ids_key_canonical(self):
        """The key is the sorted-comma representation regardless of input
        order; the strict cache match relies on this canonicalisation.
        """
        self.assertEqual(
            self.Execution._company_ids_key_for([3, 1, 2]),
            "1,2,3",
        )
        self.assertEqual(
            self.Execution._company_ids_key_for([1, 1, 2]),
            "1,2",
        )
        self.assertEqual(self.Execution._company_ids_key_for([]), "")

    def test_lifecycle_methods_are_not_rpc_callable(self):
        """RPC cannot obtain the sudo recordset used by the engine."""
        model = self.Execution.with_user(self.eh_user)
        model._eh_check_access('read')
        for operation in ('create', 'write', 'unlink'):
            with self.assertRaises(AccessError, msg=operation):
                model._eh_check_access(operation)
        for method_name in (
            'start_execution',
            'complete_execution',
            'refresh_execution_snapshot',
            'fail_execution',
            'record_failure_durable',
            'find_cached',
        ):
            with self.subTest(method_name=method_name):
                with self.assertRaises(AccessError):
                    get_public_method(model, method_name)

    def test_durable_failure_skips_locked_fk_parent_without_waiting(self):
        """Independent failure audit must never wait on its own request.

        Report computation can update a company-scoped input while its outer
        transaction remains open.  A second cursor can still see the older
        committed company tuple, but inserting the execution-company M2M then
        waits for the outer transaction.  The durable path must fail closed
        before that FK check and preserve the original report exception.
        """
        report_code = 'locked_parent_failure'
        before = self.Execution.search_count([
            ('report_code', '=', report_code),
        ])
        self.env.cr.execute(
            "SELECT id FROM res_company WHERE id = %s FOR NO KEY UPDATE",
            [self.company.id],
        )
        self.assertFalse(self.Execution.record_failure_durable(
            report_code=report_code,
            name='Locked parent failure',
            options={'date': '2026-05-31'},
            company_ids=[self.company.id],
            result_format='json',
            error_message='synthetic original failure',
            move_version_at_start=0,
        ))
        self.assertEqual(
            self.Execution.search_count([('report_code', '=', report_code)]),
            before,
        )

    def test_company_rule_requires_full_scope_not_m2m_overlap(self):
        company2 = self.env['res.company'].with_context(
            default_group_rfq='default',
        ).create({'name': 'Execution Secret Company'})
        self.eh_user.sudo().write({
            'company_ids': [(4, company2.id)],
        })
        execution = self.Execution.start_execution(
            report_code='consolidated_secret',
            name='A+B Secret',
            options={'secret_total': 999999},
            company_ids=[self.company.id, company2.id],
        )
        execution.complete_execution(result_payload=self._payload('secret'))

        a_only = self.Execution.with_user(self.eh_user).with_context(
            allowed_company_ids=[self.company.id],
        )
        self.assertFalse(a_only.search([('id', '=', execution.id)]))
        with self.assertRaises(AccessError):
            a_only.browse(execution.id).read([
                'options_snapshot', 'result_payload',
            ])

        full_scope = self.Execution.with_user(self.eh_user).with_context(
            allowed_company_ids=[self.company.id, company2.id],
        )
        self.assertEqual(
            full_scope.search([('id', '=', execution.id)]).id,
            execution.id,
        )

    def test_legacy_scope_search_is_lazy_and_keeps_exact_containment(self):
        """Legacy record rules must not expand matching audit rows to ids."""
        company2 = self.env['res.company'].with_context(
            default_group_rfq='default',
        ).create({'name': 'Legacy Execution Scope Company'})
        self.eh_user.sudo().write({'company_ids': [(4, company2.id)]})
        single = self.Execution.start_execution(
            report_code='legacy_scope_allowed',
            name='Allowed execution',
            options={'marker': 'allowed'},
            company_ids=[self.company.id],
        )
        mixed = self.Execution.start_execution(
            report_code='legacy_scope_secret',
            name='Mixed-scope execution',
            options={'secret_total': 999999},
            company_ids=[self.company.id, company2.id],
        )
        scoped = self.Execution.with_user(self.eh_user).with_context(
            allowed_company_ids=[self.company.id],
        )

        # Exercise 16/17/18 compatibility path on 19 too. Query RHS proves
        # result size cannot turn into a Python list of execution ids.
        with patch.object(execution_model, 'Domain', None):
            lazy_domain = scoped._search_scope_accessible('=', True)
            self.assertIsInstance(lazy_domain[0][2], Query)
            self.assertNotIsInstance(lazy_domain[0][2], (list, tuple))
            visible = scoped.search([
                ('id', 'in', [single.id, mixed.id]),
            ])
            self.assertEqual(visible, single)
            with self.assertRaises(AccessError):
                scoped.browse(mixed.id).read([
                    'options_snapshot', 'result_payload',
                ])

    def test_ordinary_user_cannot_create_with_forged_context(self):
        raw_payload = self._payload('forged')
        values = {
            'report_code': 'forged_report',
            'name': 'Forged report',
            'company_ids': [(6, 0, [self.company.id])],
            'options_snapshot': '{}',
            'options_hash': 'a' * 64,
            'state': 'done',
            'cache_trusted': True,
            'payload_hash': 'b' * 64,
            'result_payload': base64.b64encode(raw_payload),
            'move_version_at_start': self.company.eh_move_version,
        }
        attacker = self.Execution.with_user(self.eh_user).with_context(
            eh_internal_audit_write=True,
        )
        with self.assertRaises(AccessError):
            attacker.create(values)

    def test_ordinary_user_cannot_write_or_complete_with_forged_context(self):
        execution = self.Execution.start_execution(
            report_code='protected_report',
            name='Protected report',
            options={},
            company_ids=[self.company.id],
        )
        attacker = execution.with_user(self.eh_user).with_context(
            eh_internal_audit_write=True,
        )
        with self.assertRaises(AccessError):
            attacker.write({
                'state': 'done',
                'cache_trusted': True,
                'payload_hash': 'c' * 64,
            })
        with self.assertRaises(AccessError):
            attacker.complete_execution(
                row_count=1,
                result_payload=self._payload('forged'),
            )

        # The in-process server-owned lifecycle still completes normally.
        execution.complete_execution(
            row_count=1,
            result_payload=self._payload('server'),
        )
        self.assertTrue(execution.cache_trusted)
        self.assertEqual(
            execution._load_trusted_payload()['marker'],
            'server',
        )

    def test_sudo_and_uid1_cannot_create_cache_candidate(self):
        """Sudo/UID1 are not report-engine provenance."""
        raw_payload = self._payload('poison')
        options = {'date': '2026-06-30'}
        options_hash = self.Execution._hash_string(json.dumps(options))
        values = {
            'report_code': 'poisoned_report',
            'name': 'Poisoned report',
            'company_ids': [(6, 0, [self.company.id])],
            'options_snapshot': json.dumps(options),
            'options_hash': options_hash,
            'state': 'done',
            'cache_trusted': True,
            'payload_hash': 'd' * 64,
            'result_payload': base64.b64encode(raw_payload),
            'move_version_at_start': self.company.eh_move_version,
        }
        attackers = (
            self.Execution.sudo(),
            self.Execution.with_user(1),
            self.Execution.with_user(1).with_context(
                eh_report_execution_engine_capability=True,
            ),
        )
        for attacker in attackers:
            with self.subTest(uid=attacker.env.uid, context=attacker.env.context):
                self.assertTrue(attacker.env.su)
                with self.assertRaises(AccessError):
                    attacker.create(values)
        self.assertFalse(self.Execution.find_cached(
            report_code='poisoned_report',
            options_hash=options_hash,
            company_ids=[self.company.id],
        ))

    def test_uid1_cannot_rewrite_execution_or_forge_trusted_payload(self):
        execution = self.Execution.start_execution(
            report_code='uid1_protected_report',
            name='UID1 protected report',
            options={'date': '2026-06-30'},
            company_ids=[self.company.id],
        )
        attacker = self.env['eh.account.report.execution'].with_user(1).browse(
            execution.id,
        ).with_context(eh_report_execution_engine_capability=True)
        self.assertTrue(attacker.env.su)
        with self.assertRaises(AccessError):
            attacker.write({
                'state': 'done',
                'cache_trusted': True,
                'payload_hash': 'f' * 64,
                'result_payload': base64.b64encode(self._payload('uid1')),
            })
        execution.invalidate_recordset()
        self.assertEqual(execution.state, 'running')
        self.assertFalse(execution.cache_trusted)
        self.assertFalse(execution.payload_hash)

    def test_backing_attachment_replacement_is_rejected(self):
        execution = self.Execution.start_execution(
            report_code='tampered_report',
            name='Tampered report',
            options={},
            company_ids=[self.company.id],
        )
        execution.complete_execution(
            row_count=1,
            result_payload=self._payload('original'),
        )
        self.assertEqual(
            execution._load_trusted_payload()['marker'],
            'original',
        )

        attachment = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'eh.account.report.execution'),
            ('res_id', '=', execution.id),
            ('res_field', '=', 'result_payload'),
        ], limit=1)
        self.assertTrue(attachment)
        attachment.write({
            'datas': base64.b64encode(self._payload('substituted')),
        })
        execution.invalidate_recordset(['result_payload'])
        self.assertIsNone(execution._load_trusted_payload())
