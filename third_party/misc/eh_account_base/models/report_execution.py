# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
eh.account.report.execution: durable audit log for every report render.

Why this exists:

* Compliance. Auditors need to reproduce the exact report a user printed on a
  given day. We persist the full options dict and the result hash so any prior
  execution can be replayed deterministically.
* Cache key. The (report_code, options_hash, sum(eh_move_version)) tuple is
  the freshness key used by the persisted cache layer. The monotonic company
  counter covers posted-ledger changes plus report-visible master data,
  configuration, exchange rates, and suite sub-ledger inputs.
* Performance telemetry. duration_ms and row_count let us track regressions
  over time and flag reports drifting outside their service level objective.
"""

import base64
import hashlib
import hmac
import json
import logging
from datetime import timedelta

from psycopg2.errors import LockNotAvailable

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import Query
from odoo.tools import SQL

try:  # Python Domain/custom SQL arrived in Odoo 19.
    from odoo.fields import Domain
except ImportError:  # pragma: no cover - exercised on 16/17/18 backports
    Domain = None

from odoo.addons.eh_account_base.tools.payload_codec import decompress_payload

_logger = logging.getLogger(__name__)


# Public RPC callers control context values and UID 1 always runs with
# ``env.su=True``.  Audit provenance therefore needs process-local identity,
# not a boolean/context/sudo convention.  Only start_execution mints this
# object and keeps it on the short-lived lifecycle recordset.
_EH_REPORT_EXECUTION_ENGINE_CONTEXT = (
    'eh_report_execution_engine_capability'
)
_EH_REPORT_EXECUTION_ENGINE_CAPABILITY = object()


class EhAccountReportExecution(models.Model):
    _name = 'eh.account.report.execution'
    _description = "Accounting report execution audit log"
    _order = 'executed_at desc'
    _rec_name = 'display_name'

    display_name = fields.Char(
        compute='_compute_display_name',
        store=True,
    )
    report_code = fields.Char(
        required=True,
        index=True,
        help="Stable identifier for the report definition (for example 'profit_loss').",
    )
    name = fields.Char(required=True)

    executed_by = fields.Many2one(
        'res.users',
        required=True,
        default=lambda self: self.env.user,
        index=True,
    )
    executed_at = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        index=True,
    )

    company_ids = fields.Many2many('res.company', required=True)
    company_ids_key = fields.Char(
        compute='_compute_company_ids_key',
        store=True,
        index=True,
        help=(
            "Sorted comma separated representation of company_ids. Used "
            "for strict equality in the cache lookup; an m2m IN filter "
            "would match overlapping sets and return wrong scoped rows."
        ),
    )
    scope_accessible = fields.Boolean(
        compute='_compute_scope_accessible',
        search='_search_scope_accessible',
        help=(
            "True only when every company on this execution belongs to the "
            "caller's active allowed-company scope."
        ),
    )

    options_snapshot = fields.Text(
        required=True,
        help="JSON serialised options dict at execution time.",
    )
    options_hash = fields.Char(
        size=64,
        required=True,
        index=True,
        help="SHA-256 of the canonicalised options dict.",
    )

    result_format = fields.Selection(
        [
            ('json', "JSON"),
            ('xlsx', "XLSX"),
            ('pdf', "PDF"),
        ],
        required=True,
        default='json',
    )

    state = fields.Selection(
        [
            ('running', "Running"),
            ('done', "Done"),
            ('error', "Error"),
        ],
        required=True,
        default='running',
        index=True,
    )

    duration_ms = fields.Integer(default=0)
    row_count = fields.Integer(default=0)
    result_hash = fields.Char(
        size=64,
        help="SHA-256 of the rendered output for xlsx and pdf formats.",
    )
    error_message = fields.Text()

    move_version_at_start = fields.Integer(
        help=(
            "Sum of res_company.eh_move_version at execution start across the "
            "company_ids. This is the report-input version despite the "
            "legacy field name, and is a component of the cache key."
        ),
    )

    result_payload = fields.Binary(
        attachment=True,
        help=(
            "Compressed serialised report result. Used to serve cache hits "
            "without recomputation. See eh_account_base.tools.payload_codec."
        ),
    )
    payload_hash = fields.Char(
        size=64,
        readonly=True,
        copy=False,
        help=(
            "SHA-256 of the compressed cache payload. Cache reads verify this "
            "digest before deserialising so replacing the backing attachment "
            "cannot substitute a different financial report."
        ),
    )
    cache_trusted = fields.Boolean(
        default=False,
        readonly=True,
        copy=False,
        index=True,
        help=(
            "Set only by the server-owned completion path. Rows created "
            "directly, including rows predating this trust marker, are never "
            "eligible to serve a shared cache payload."
        ),
    )
    served_from_execution_id = fields.Many2one(
        'eh.account.report.execution',
        index=True, ondelete='set null',
        help=(
            "When this execution served a result from a prior cached "
            "execution, this is a pointer to that prior execution. The "
            "audit log keeps one row per actual user request even when "
            "the underlying compute was reused, so compliance reporting "
            "lists every render."
        ),
    )

    @api.depends('company_ids')
    def _compute_company_ids_key(self):
        for rec in self:
            ids = sorted(rec.company_ids.ids)
            rec.company_ids_key = ','.join(str(i) for i in ids)

    @api.depends('company_ids_key')
    @api.depends_context('allowed_company_ids')
    def _compute_scope_accessible(self):
        allowed = set(self.env.companies.ids)
        for rec in self:
            scoped = {
                int(company_id)
                for company_id in (rec.company_ids_key or '').split(',')
                if company_id
            }
            rec.scope_accessible = bool(scoped) and scoped.issubset(allowed)

    @api.model
    def _search_scope_accessible(self, operator, value):
        """Translate scope checks to a set-containment SQL predicate.

        A normal M2M ``in`` domain means overlap, not containment. For an
        A+B execution it would therefore let an A-only user read B's payload.
        This predicate requires at least one scoped company and rejects the
        row when any relation points outside the active allowed companies.
        """
        if operator not in ('=', '!=') or not isinstance(value, bool):
            return NotImplemented
        allowed = tuple(self.env.companies.ids)
        field = self._fields['company_ids']

        if Domain is None:
            # 16/17/18 search methods cannot return a custom SQL domain, but
            # ``id in Query`` is supported by every legacy expression engine.
            # Keep the exact containment check as a lazy SQL subquery so list
            # limits/pagination remain database-side and Python never
            # materialises every accessible execution id.
            relation = field.relation
            execution_column = field.column1
            company_column = field.column2
            query_owner = (
                self.env
                if hasattr(self.env, 'execute_query')
                else self.env.cr
            )
            accessible = Query(query_owner, self._table)
            accessible.add_where(
                'EXISTS ('
                f' SELECT 1 FROM "{relation}" scope'
                f' WHERE scope."{execution_column}" = '
                f'"{self._table}"."id"'
                ') AND NOT EXISTS ('
                f' SELECT 1 FROM "{relation}" outside_scope'
                f' WHERE outside_scope."{execution_column}" = '
                f'"{self._table}"."id"'
                f' AND outside_scope."{company_column}" NOT IN %s'
                ')',
                [allowed or (0,)],
            )
            positive = (
                (operator == '=' and value)
                or (operator == '!=' and not value)
            )
            return [
                ('id', 'in' if positive else 'not in', accessible),
            ]

        def to_sql(model, alias, query):
            record_id = SQL.identifier(alias, 'id')
            relation = SQL.identifier(field.relation)
            execution_column = SQL.identifier(field.column1)
            company_column = SQL.identifier(field.column2)
            return SQL(
                "EXISTS (SELECT 1 FROM %s scope "
                "WHERE scope.%s = %s) "
                "AND NOT EXISTS (SELECT 1 FROM %s outside_scope "
                "WHERE outside_scope.%s = %s "
                "AND outside_scope.%s NOT IN %s)",
                relation, execution_column, record_id,
                relation, execution_column, record_id,
                company_column, allowed,
            )

        def predicate(record):
            scoped = {
                int(company_id)
                for company_id in (record.company_ids_key or '').split(',')
                if company_id
            }
            return bool(scoped) and scoped.issubset(set(allowed))

        accessible = Domain.custom(to_sql=to_sql, predicate=predicate)
        positive = (operator == '=' and value) or (operator == '!=' and not value)
        return accessible if positive else ~accessible

    @api.depends('report_code', 'name', 'executed_at')
    def _compute_display_name(self):
        for rec in self:
            ts = rec.executed_at and fields.Datetime.to_string(rec.executed_at) or ''
            base = rec.name or rec.report_code or 'Report'
            rec.display_name = f"{base} ({ts})" if ts else base

    @staticmethod
    def _company_ids_key_for(company_ids):
        ids = sorted(set(int(c) for c in company_ids))
        return ','.join(str(i) for i in ids)

    # ----------- audit-log ownership -----------

    @api.model_create_multi
    def create(self, vals_list):
        """Allow row creation only through the server-owned lifecycle.

        ``readonly`` fields and a context sentinel are not security
        boundaries in Odoo: both can be supplied over RPC. The reporting
        engine calls :meth:`start_execution`, which creates under ``env.su``
        plus a process-local identity capability and returns that short-lived
        recordset to the remaining Python lifecycle. An RPC caller receives
        only serialised ids, never that in-memory capability.
        """
        if not self._eh_has_execution_engine_capability():
            raise AccessError(_(
                "Report execution rows are created by the reporting engine "
                "and cannot be created directly."
            ))
        protected_vals = []
        for incoming in vals_list:
            vals = dict(incoming or {})
            # A row is untrusted until complete_execution validates and hashes
            # its payload. Ignore even a sudo caller's create-time marker so
            # trusted cache status has exactly one transition point.
            vals['cache_trusted'] = False
            vals['payload_hash'] = False
            protected_vals.append(vals)
        return super().create(protected_vals)

    @api.model
    def _eh_has_execution_engine_capability(self):
        return bool(
            self.env.su
            and self.env.context.get(_EH_REPORT_EXECUTION_ENGINE_CONTEXT)
            is _EH_REPORT_EXECUTION_ENGINE_CAPABILITY
        )

    def _eh_assert_execution_engine_capability(self):
        """Require exact lifecycle authority bound to the original actor."""
        if not self._eh_has_execution_engine_capability():
            raise AccessError(_(
                "Report execution audit rows are append-only and may only be "
                "written by the reporting engine."
            ))
        wrong_actor = self.filtered(
            lambda rec: rec.executed_by.id != self.env.uid
        )
        if wrong_actor:
            raise AccessError(_(
                "Report execution lifecycle authority belongs to the user "
                "who started the report."
            ))

    @api.model
    @api.private
    def start_execution(self, report_code, name, options, company_ids,
                        result_format='json', move_version_at_start=None):
        """Begin a report execution and return the audit row.

        :param report_code: short stable identifier, for example 'profit_loss'.
        :param name: human readable report name.
        :param options: dict of all parameters used to render the report.
        :param company_ids: iterable of company ids in scope.
        :param result_format: 'json', 'xlsx', or 'pdf'.
        :return: created eh.account.report.execution record.
        """
        canonical = self._canonicalise_options(options)
        canonical_json = json.dumps(canonical, sort_keys=True, default=str)
        options_hash = self._hash_string(canonical_json)
        company_ids_list = sorted(set(int(c) for c in company_ids))
        if not company_ids_list:
            raise ValueError("start_execution requires at least one company id")
        company_recs = self.env['res.company'].sudo().browse(company_ids_list)
        move_version_total = (
            sum(company_recs.mapped('eh_move_version'))
            if move_version_at_start is None
            else int(move_version_at_start)
        )
        # Capture the real actor before elevating. sudo() bypasses the now
        # read-only ACL solely to create the engine-owned audit row; the
        # returned sudo recordset is the unforgeable capability used by the
        # subsequent complete/fail call in this same Python request.
        actor_id = self.env.user.id
        lifecycle = self.sudo().with_context({
            _EH_REPORT_EXECUTION_ENGINE_CONTEXT:
                _EH_REPORT_EXECUTION_ENGINE_CAPABILITY,
        })
        return lifecycle.create({
            'report_code': report_code,
            'name': name,
            'executed_by': actor_id,
            'company_ids': [(6, 0, company_ids_list)],
            'options_snapshot': json.dumps(options, sort_keys=True, default=str, indent=2),
            'options_hash': options_hash,
            'result_format': result_format,
            'state': 'running',
            'move_version_at_start': move_version_total,
        })

    def write(self, vals):
        # Neither sudo nor a context string is authority. The exact object
        # minted by start_execution exists only inside this Python process.
        self._eh_assert_execution_engine_capability()
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_immutable_audit(self):
        # No context bypass: RPC callers control context. The decorator skips
        # this guard automatically during module uninstall.
        raise UserError(_(
            "Report execution audit rows cannot be deleted. "
            "Reason: durable compliance trail."
        ))

    @api.private
    def complete_execution(self, row_count=0, result_hash=None,
                           result_payload=None,
                           served_from_execution_id=None,
                           cache_eligible=True):
        """Mark this execution as done and record duration based on executed_at.

        :param row_count: number of rows in the rendered report.
        :param result_hash: optional SHA-256 of the rendered output.
        :param result_payload: optional compressed bytes blob produced by
            eh_account_base.tools.payload_codec.compress_payload(). When
            provided, the next find_cached() call with a matching cache key
            can skip recomputation entirely and return this stored payload.
        :param served_from_execution_id: optional trusted source execution
            used for a cache hit. Cache-hit audit rows intentionally do not
            duplicate the source payload.
        """
        self._eh_assert_execution_engine_capability()
        raw_payload = None
        payload_hash = False
        if result_payload is not None:
            if not isinstance(result_payload, (bytes, bytearray)):
                raise UserError(_(
                    "A report cache payload must be raw compressed bytes."
                ))
            raw_payload = bytes(result_payload)
            try:
                decoded = decompress_payload(raw_payload)
            except Exception as exc:  # noqa: BLE001 - convert to user error
                raise UserError(_(
                    "The report cache payload is not valid: %s",
                    str(exc),
                )) from exc
            if not isinstance(decoded, dict):
                raise UserError(_(
                    "A report cache payload must decode to a JSON object."
                ))
            payload_hash = hashlib.sha256(raw_payload).hexdigest()

        invalid = self.filtered(lambda rec: rec.state != 'running')
        if invalid:
            raise UserError(_(
                "Only a running report execution can be completed."
            ))
        served_from_id = int(served_from_execution_id or 0)
        for rec in self:
            current_version = rec._current_move_version()
            source = self.browse(served_from_id).exists() if served_from_id else self.browse()
            if served_from_id and (
                    not cache_eligible
                    or not rec._cache_source_matches(source, current_version)):
                # A post/configuration write raced the payload load, or the
                # source did not match this exact request. Keep this row
                # running so the orchestrator can refresh and recompute.
                return False
            cache_fresh = bool(
                cache_eligible
                and current_version == rec.move_version_at_start
            )
            duration_ms = self._compute_elapsed_ms(rec)
            vals = {
                'state': 'done',
                'duration_ms': duration_ms,
                'row_count': int(row_count or 0),
                'result_hash': result_hash or False,
                'payload_hash': payload_hash if cache_fresh else False,
                'cache_trusted': raw_payload is not None and cache_fresh,
                'served_from_execution_id': served_from_id or False,
                # Discard any untrusted create-time blob when this completion
                # does not persist a freshly validated payload.
                'result_payload': False,
            }
            if raw_payload is not None and cache_fresh:
                # Odoo 19 Binary fields require base64-encoded bytes on write.
                vals['result_payload'] = base64.b64encode(raw_payload)
            rec.write(vals)
        return True

    def _current_move_version(self):
        self.ensure_one()
        companies = self.env['res.company'].sudo().browse(self.company_ids.ids)
        companies.invalidate_recordset(['eh_move_version'])
        return sum(companies.mapped('eh_move_version'))

    def _cache_source_matches(self, source, current_version=None):
        self.ensure_one()
        source.ensure_one() if source else None
        if not source or source._load_trusted_payload() is None:
            return False
        current_version = (
            self._current_move_version()
            if current_version is None
            else int(current_version)
        )
        return bool(
            source.state == 'done'
            and source.report_code == self.report_code
            and source.options_hash == self.options_hash
            and source.company_ids_key == self.company_ids_key
            and source.move_version_at_start == self.move_version_at_start
            and self.move_version_at_start == current_version
        )

    @api.private
    def refresh_execution_snapshot(self, move_version_at_start=None):
        self._eh_assert_execution_engine_capability()
        self.ensure_one()
        if self.state != 'running':
            raise UserError(_(
                "Only a running report execution can refresh its snapshot."
            ))
        version = (
            self._current_move_version()
            if move_version_at_start is None
            else int(move_version_at_start)
        )
        self.write({'move_version_at_start': version})
        return self.move_version_at_start

    @api.private
    def fail_execution(self, error_message):
        """Mark this execution as failed and log the error."""
        self._eh_assert_execution_engine_capability()
        invalid = self.filtered(lambda rec: rec.state != 'running')
        if invalid:
            raise UserError(_(
                "Only a running report execution can be marked failed."
            ))
        msg = str(error_message)[:8000]
        for rec in self:
            duration_ms = self._compute_elapsed_ms(rec)
            rec.write({
                'state': 'error',
                'duration_ms': duration_ms,
                'error_message': msg,
                'cache_trusted': False,
                'payload_hash': False,
                'result_payload': False,
                'served_from_execution_id': False,
            })
            _logger.warning(
                "Report execution failed: report_code=%s execution_id=%s error=%s",
                rec.report_code, rec.id, msg,
            )
        return True

    @api.model
    @api.private
    def record_failure_durable(self, report_code, name, options, company_ids,
                               result_format, error_message,
                               move_version_at_start=None,
                               definition_id=None):
        """Commit failure evidence outside the doomed request transaction.

        The normal execution row lives in the report request transaction and
        is rolled back when the exception crosses the RPC boundary. This
        method creates a second, complete error row on an independent cursor.
        It fails closed to the local lifecycle when a test-only user, company,
        or report definition has not been committed yet.
        """
        company_ids_list = sorted(set(int(c) for c in company_ids))
        actor_id = self.env.user.id
        durable_id = False
        try:
            with self.env.registry.cursor() as cr:
                # Prove every FK parent is both committed and currently
                # stable before creating the independent audit row. A plain
                # visibility SELECT can see the parent's older committed
                # tuple while this request holds an uncommitted update. The
                # later FK check would then wait on this same request forever.
                # NOWAIT makes durable evidence best-effort without masking
                # or delaying the original report failure.
                cr.execute(
                    "SELECT id FROM res_users WHERE id = %s "
                    "FOR NO KEY UPDATE NOWAIT",
                    [actor_id],
                )
                actor_visible = bool(cr.fetchone())
                cr.execute(
                    "SELECT id FROM res_company WHERE id IN %s "
                    "ORDER BY id FOR NO KEY UPDATE NOWAIT",
                    [tuple(company_ids_list) or (0,)],
                )
                companies_visible = {
                    row[0] for row in cr.fetchall()
                } == set(company_ids_list)
                definition_visible = True
                if definition_id:
                    cr.execute(
                        "SELECT id FROM eh_account_dynamic_report "
                        "WHERE id = %s FOR NO KEY UPDATE NOWAIT",
                        [int(definition_id)],
                    )
                    definition_visible = bool(cr.fetchone())
                if actor_visible and companies_visible and definition_visible:
                    isolated_env = api.Environment(
                        cr,
                        actor_id,
                        {
                            'allowed_company_ids': company_ids_list,
                            'lang': self.env.lang,
                        },
                    )
                    durable = isolated_env[self._name].start_execution(
                        report_code=report_code,
                        name=name,
                        options=options,
                        company_ids=company_ids_list,
                        result_format=result_format,
                        move_version_at_start=move_version_at_start,
                    )
                    durable.fail_execution(error_message)
                    durable_id = durable.id
                    cr.commit()
        except LockNotAvailable:
            _logger.info(
                "Skipped durable report failure audit because an FK parent "
                "is locked by the failing request: report_code=%s actor_id=%s "
                "company_ids=%s definition_id=%s",
                report_code, actor_id, company_ids_list, definition_id,
            )
        return durable_id

    @staticmethod
    def _compute_elapsed_ms(record):
        if not record.executed_at:
            return 0
        delta = fields.Datetime.now() - record.executed_at
        return int(delta.total_seconds() * 1000)

    @api.model
    @api.private
    def find_cached(self, report_code, options_hash, company_ids,
                    move_version_at_start=None):
        """Look up a recent successful execution that matches the cache key.

        Strict equality on company scope: an m2m 'in' would match
        overlapping sets, so a render for [1, 2] could pick up a cached
        row computed for [1] alone (and vice versa). Using the canonical
        sorted-comma key forces exact set equality. Combined with the
        move-version freshness check this guarantees the cached payload
        was computed on the same ledger snapshot for the same company
        scope as the current request.
        """
        company_ids_list = sorted(set(int(c) for c in company_ids))
        if not company_ids_list:
            return self.browse()
        company_recs = self.env['res.company'].sudo().browse(company_ids_list)
        current_version = (
            sum(company_recs.mapped('eh_move_version'))
            if move_version_at_start is None
            else int(move_version_at_start)
        )
        scope_key = self._company_ids_key_for(company_ids_list)
        return self.search(
            [
                ('report_code', '=', report_code),
                ('options_hash', '=', options_hash),
                ('state', '=', 'done'),
                ('cache_trusted', '=', True),
                ('result_payload', '!=', False),
                ('payload_hash', '!=', False),
                ('move_version_at_start', '=', current_version),
                ('company_ids_key', '=', scope_key),
            ],
            limit=1,
            order='executed_at desc',
        )

    def _load_trusted_payload(self):
        """Return the verified cached JSON object, or ``None`` on tampering.

        ``result_payload`` is attachment-backed. Protecting this model's
        ``write`` is therefore necessary but insufficient: a separate write
        to the backing ``ir.attachment`` could otherwise replace the bytes.
        Read the blob once, compare its digest with the server-stamped hash,
        then deserialize those same verified bytes.
        """
        self.ensure_one()
        rec = self.sudo()
        if not (rec.cache_trusted and rec.result_payload and rec.payload_hash):
            return None
        try:
            raw_payload = self._binary_field_bytes(rec.result_payload)
            actual_hash = hashlib.sha256(raw_payload).hexdigest()
            if not hmac.compare_digest(actual_hash, rec.payload_hash):
                _logger.warning(
                    "Rejected tampered report cache payload: execution_id=%s",
                    rec.id,
                )
                return None
            payload = decompress_payload(raw_payload)
        except Exception as exc:  # noqa: BLE001 - corrupt cache is a miss
            _logger.warning(
                "Rejected invalid report cache payload: execution_id=%s "
                "error=%s",
                rec.id, exc,
            )
            return None
        if not isinstance(payload, dict):
            _logger.warning(
                "Rejected non-object report cache payload: execution_id=%s",
                rec.id,
            )
            return None
        return payload

    @api.private
    def _eh_load_bound_json_snapshot(
        self, report_code, options_hash, company_ids,
    ):
        """Return the exact readable JSON snapshot behind this execution.

        A browser-supplied execution id is authority for neither an audit row
        nor its attachment-backed payload.  Bind it to the current actor,
        report, canonical options and exact company set before following the
        cache-source pointer.  Cache-hit audit rows intentionally carry no
        duplicate payload, so the trusted source is the only reproducible
        result snapshot for those executions.
        """
        self.ensure_one()
        self._eh_check_access('read')
        company_key = self._company_ids_key_for(company_ids)
        if (
            self.executed_by.id != self.env.uid
            or self.state != 'done'
            or self.result_format != 'json'
            or self.report_code != report_code
            or self.options_hash != options_hash
            or self.company_ids_key != company_key
        ):
            raise AccessError(_(
                "The report execution does not belong to this displayed "
                "report. Refresh the report and try again."
            ))

        source = self.served_from_execution_id or self
        source = source.exists()
        if not source:
            raise UserError(_(
                "The displayed report snapshot is no longer available. "
                "Refresh the report and try again."
            ))
        source._eh_check_access('read')
        if (
            source.state != 'done'
            or source.result_format != 'json'
            or source.report_code != self.report_code
            or source.options_hash != self.options_hash
            or source.company_ids_key != self.company_ids_key
            or source.move_version_at_start != self.move_version_at_start
        ):
            raise AccessError(_(
                "The report execution source does not match this displayed "
                "report. Refresh the report and try again."
            ))
        payload = source._load_trusted_payload()
        if payload is None:
            raise UserError(_(
                "The displayed report snapshot is no longer available. "
                "Refresh the report and try again."
            ))
        return payload

    @api.autovacuum
    def _gc_expired_cache_payloads(self):
        """Expire cache bytes after 30 days; preserve audit evidence forever.

        Execution rows, options, actor, timing and binary result hashes remain
        append-only. Only recomputable compressed JSON cache blobs lose trust
        and storage. Batching bounds autovacuum transaction size; later daily
        runs continue until backlog is gone.
        """
        cutoff = fields.Datetime.now() - timedelta(days=30)
        expired = self.sudo().search([
            ('state', '=', 'done'),
            ('result_payload', '!=', False),
            ('executed_at', '<', cutoff),
        ], order='executed_at, id', limit=5000)
        if not expired:
            return 0
        # Deliberately bypass this model's public append-only write guard:
        # autovacuum owns only these recomputable cache fields. Binary field
        # machinery removes matching attachment-backed blobs.
        super(EhAccountReportExecution, expired).write({
            'result_payload': False,
            'payload_hash': False,
            'cache_trusted': False,
        })
        return len(expired)

    @staticmethod
    def _binary_field_bytes(blob):
        """Normalise an Odoo Binary value to its raw compressed bytes."""
        if isinstance(blob, str):
            blob = blob.encode('ascii')
        if isinstance(blob, bytearray):
            blob = bytes(blob)
        if not isinstance(blob, bytes):
            raise ValueError("report cache payload is not bytes")
        # Raw payloads start with the current codec's version byte. Binary
        # fields normally return base64 bytes, but tests/internal callers may
        # already hold the raw representation.
        if blob[:1] == b'\x01':
            return blob
        return base64.b64decode(blob, validate=True)

    # Option keys that are conceptually SETS of ids: their order carries no
    # meaning, so they MUST be canonicalised order-insensitively or the
    # cache fragments (the same unfold set expanded in a different order
    # would hash differently) or, worse, an un-normalised key serves a
    # stale no-children payload. unfolded_lines is the load-bearing case
    # (different unfold sets are different payloads); the id-list filters
    # are peers whose order never changes the figures.
    _ORDER_INSENSITIVE_OPTION_KEYS = frozenset({
        'unfolded_lines',
        'company_ids',
        'journal_ids',
        'partner_ids',
        'account_ids',
        'account_type_ids',
        'analytic_account_ids',
        'analytic_plan_ids',
        'analytic_column_account_ids',
        'analytic_column_plan_ids',
        '_eh_analytic_column_account_ids',
        '_eh_analytic_column_plan_ids',
    })

    @staticmethod
    def _canonicalise_options(options, _key=None):
        """Produce a deterministic representation of options for hashing.

        Dicts are sorted by key. Sets and frozensets are sorted. Lists and
        tuples keep order EXCEPT for the order-insensitive id-list keys
        (unfolded_lines and peer filters), which are sorted so the same set
        of ids hashes identically regardless of selection order. Scalar
        types pass through; non-JSON values become str() downstream.
        """
        cls = EhAccountReportExecution
        if isinstance(options, dict):
            return {
                k: cls._canonicalise_options(v, _key=k)
                for k, v in sorted(options.items(), key=lambda kv: str(kv[0]))
            }
        if isinstance(options, (list, tuple)):
            items = [cls._canonicalise_options(v) for v in options]
            if _key in cls._ORDER_INSENSITIVE_OPTION_KEYS:
                # Sort by a stable string projection so heterogeneous /
                # unorderable members never raise during canonicalisation.
                try:
                    return sorted(items, key=lambda v: (str(type(v)), str(v)))
                except Exception:  # pragma: no cover - defensive
                    return items
            return items
        if isinstance(options, (set, frozenset)):
            return sorted(
                cls._canonicalise_options(v) for v in options
            )
        return options

    @staticmethod
    def _hash_string(s):
        return hashlib.sha256(s.encode('utf-8')).hexdigest()
