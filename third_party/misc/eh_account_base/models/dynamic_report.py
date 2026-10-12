# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
eh.account.dynamic.report: the orchestrator model.

One record per concrete report (Trial Balance, P&L, Balance Sheet, ...).
The handler_model field references the AbstractModel that knows how to
compute that report. The render() method:

1. Computes the cache key from the options dict.
2. Looks up a prior successful execution with the same key. If the move
   version counter is unchanged since that execution, the cached payload
   is fresh and is returned directly.
3. On cache miss, instantiates the handler, runs compute(), persists the
   payload on a fresh execution row, and returns it.

Both paths return the same shape so callers cannot tell hit from miss
unless they inspect the from_cache flag.
"""

import copy
import hashlib
import json
import logging
import math

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.eh_account_base.tools.currency_table import CurrencyTable
from odoo.addons.eh_account_base.tools.payload_codec import compress_payload
from odoo.addons.eh_account_base.tools.xlsx_writer import XlsxReportWriter

_logger = logging.getLogger(__name__)

_MAX_OPTIONS_DEPTH = 12
_MAX_OPTIONS_ITEMS = 20_000
_MAX_OPTION_TEXT = 32_768
_MAX_EXPAND_LINE_ID = 512
_MAX_EXPAND_PAGE_SIZE = 500
_MAX_EXPAND_OFFSET = 100_000
_MAX_ANALYTIC_DRILLDOWN_EXPRESSION = 512
# Bump whenever report-engine code can change a cached payload without an
# accounting/configuration write.  Keeping this in canonical options makes a
# code upgrade reject every payload produced by the previous engine schema;
# no destructive cache migration is required.
_EH_REPORT_CACHE_SCHEMA_VERSION = 3


class EhAccountDynamicReport(models.Model):
    _name = 'eh.account.dynamic.report'
    _description = "Dynamic accounting report"
    _order = 'sequence, name'

    code = fields.Char(required=True, copy=False, index=True)
    name = fields.Char(required=True, translate=True)
    handler_model = fields.Char(
        required=True,
        help="Odoo abstract model name implementing the report handler.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(translate=True)

    _unique_code = models.Constraint(
        'unique(code)',
        'Report code must be unique.',
    )

    _EH_CACHE_DEFINITION_FIELDS = frozenset({
        'code', 'name', 'handler_model', 'description', 'active',
    })
    _EH_ACL_SENSITIVE_HANDLERS = frozenset({
        'eh.account.dynamic.report.handler.analytic_balance',
    })

    def _eh_invalidate_definition_cache(self):
        self.env['res.company'].sudo()._eh_bump_global_report_version()

    @api.model_create_multi
    def create(self, vals_list):
        reports = super().create(vals_list)
        reports._eh_invalidate_definition_cache()
        return reports

    def write(self, vals):
        result = super().write(vals)
        if self._EH_CACHE_DEFINITION_FIELDS.intersection(vals):
            self._eh_invalidate_definition_cache()
        return result

    def unlink(self):
        invalidate = bool(self)
        result = super().unlink()
        if invalidate:
            self._eh_invalidate_definition_cache()
        return result

    @api.constrains('handler_model')
    def _check_handler_model(self):
        for rec in self:
            if not rec.handler_model:
                raise ValidationError(_(
                    "Handler model is required for report %(code)r.",
                    code=rec.code,
                ))
            if rec.handler_model not in self.env.registry.models:
                raise ValidationError(_(
                    "Unknown handler model %(model)r for report %(code)r. "
                    "Did you forget to install the addon that provides "
                    "the handler?",
                    model=rec.handler_model,
                    code=rec.code,
                ))

    @api.model
    def get_by_code(self, code):
        report = self.search([('code', '=', code)], limit=1)
        if not report:
            raise UserError(_("Unknown report code: %s") % code)
        return report

    def get_default_options(self):
        self.ensure_one()
        self._eh_check_access('read')
        return self.env[self.handler_model].build_default_options()

    def action_open_run_wizard(self):
        """Open executable report parameters for this definition."""
        self.ensure_one()
        self._eh_check_access('read')
        action = self.env.ref(
            'eh_account_base.action_eh_account_report_wizard',
        ).read()[0]
        action['context'] = {
            'default_report_id': self.id,
            'allowed_company_ids': self.env.companies.ids,
        }
        return action

    def _eh_apply_presentation_currency(self, payload, options, company_ids):
        """Restate every monetary cell of a computed payload into the
        currency named by options['presentation_currency_id'].

        Only cells whose column is figure_type 'monetary' are converted,
        so day counts, percentages and labels are left intact. Conversion
        uses closing-spot translation at period end (date_to), or today when
        the report carries no end date. It is deliberately not transaction-
        date or period-average translation. No-op when no currency is chosen
        or it equals the company currency.
        """
        target_id = options.get('presentation_currency_id')
        if not target_id:
            return payload
        target = self.env['res.currency'].browse(int(target_id)).exists()
        if not target:
            return payload
        if (payload.get('meta') or {}).get(
                'presentation_currency_converted'):
            payload['currency'] = {
                'id': target.id, 'name': target.name,
                'symbol': target.symbol, 'position': target.position,
                'decimal_places': target.decimal_places,
            }
            payload.setdefault('meta', {})[
                'presentation_currency_id'] = target.id
            return payload
        primary_company_id = options.get('primary_company_id')
        fallback_company_id = company_ids[0] if company_ids else self.env.company.id
        company = self.env['res.company'].browse(
            int(primary_company_id or fallback_company_id)
        )
        source = company.currency_id
        if not source or target == source:
            return payload

        date_block = options.get('date') or {}
        date_to = date_block.get('date_to')
        if isinstance(date_to, str):
            date_to = fields.Date.from_string(date_to)
        date_to = date_to or fields.Date.context_today(self)
        currency_table = CurrencyTable(
            self.env,
            company_ids=[company.id],
            presentation_currency_id=target.id,
            as_of_date=date_to,
        )
        rate = currency_table.rate_map[company.id]

        def convert(value):
            return target.round(value * rate)

        def convert_monetary(value):
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return convert(value)
            if isinstance(value, dict):
                return {
                    key: convert_monetary(item)
                    for key, item in value.items()
                }
            if isinstance(value, list):
                return [convert_monetary(item) for item in value]
            return value

        column_figure_types = {
            col.get('expression_label'): col.get('figure_type', 'string')
            for col in payload.get('columns', [])
            if col.get('expression_label')
        }
        for line in payload.get('lines', []):
            for col in line.get('columns', []):
                figure_type = (
                    col.get('figure_type')
                    or column_figure_types.get(
                        col.get('expression_label'), 'string',
                    )
                )
                if figure_type == 'monetary' and isinstance(
                        col.get('value'), (int, float)):
                    col['value'] = convert(col['value'])
        total_figure_types = dict(column_figure_types)
        total_figure_types.update(
            (payload.get('meta') or {}).get('total_figure_types') or {},
        )
        for line in payload.get('lines', []):
            line_types = {
                col.get('figure_type')
                or column_figure_types.get(
                    col.get('expression_label'), 'string',
                )
                for col in line.get('columns', [])
                if isinstance(col, dict)
                and isinstance(col.get('value'), (int, float))
                and not isinstance(col.get('value'), bool)
            }
            if 'monetary' in line_types:
                line_type = 'monetary'
            elif len(line_types) == 1:
                line_type = next(iter(line_types))
            else:
                continue
            for semantic_key in (
                line.get('id'),
                (line.get('meta') or {}).get('metric'),
                (line.get('meta') or {}).get('builder_line_code'),
            ):
                if semantic_key:
                    total_figure_types.setdefault(semantic_key, line_type)
        totals = payload.get('totals', {})
        for key, value in list(totals.items()):
            if total_figure_types.get(key) == 'monetary':
                totals[key] = convert_monetary(value)
        payload['currency'] = {
            'id': target.id, 'name': target.name, 'symbol': target.symbol,
            'position': target.position,
            'decimal_places': target.decimal_places,
        }
        meta = payload.setdefault('meta', {})
        meta['presentation_currency_id'] = target.id
        meta['presentation_currency_converted'] = True
        meta.update(currency_table.translation_metadata())
        return payload

    def _eh_assert_currency_scope_supported(self, payload, company_ids):
        """Reject unlike company currencies unless handler converted first.

        Summing already-aggregated company-currency numbers and converting the
        total with one primary-company rate is mathematically invalid.  SQL
        currency-aware handlers declare ``presentation_currency_converted``;
        every other handler may consolidate only companies sharing one ledger
        currency.  Fail closed instead of publishing a mislabeled total.
        """
        companies = self.env['res.company'].sudo().browse(company_ids)
        currency_ids = set(companies.mapped('currency_id').ids)
        if len(currency_ids) <= 1:
            return
        if (payload.get('meta') or {}).get(
                'presentation_currency_converted'):
            return
        raise UserError(_(
            "Report %(report)s cannot combine companies with different "
            "ledger currencies without handler-level conversion. Select "
            "one currency scope, or choose a report that supports "
            "consolidated presentation currency.",
            report=self.name,
        ))

    def _eh_normalize_fold(self, payload, options):
        """Enforce one fold invariant across every report, in place.

        With options['lazy_expand'] (and NOT eager_expand), apply uniformly
        to every line so a caret appears IFF the row has something to expand:

          * lazy leaf (line['lazy'] is True): left as-is. It carries no
            in-payload children but expands on demand, so it stays
            unfoldable and collapsed.
          * structural group (the line's id is some other line's parent_id):
            unfoldable=True, and unfolded defaults to True (open) when the
            handler did not already set it. A row with real children always
            gets a caret and starts open.
          * everything else: unfoldable=False. Strips stray carets from flat
            rows (cash-flow / executive-summary / bank-reconciliation section
            headers, an empty bank-rec section line, partner/opening/total
            rows) that have nothing to expand.

        Backward compatible on two axes, so the eager / export / non-lazy
        callers and the existing suite see byte-identical lines:

          1. No-op unless options['lazy_expand'] is truthy and eager_expand
             is falsy (the OWL screen path only).
          2. Best-effort: any malformed payload degrades to leaving the lines
             untouched rather than raising (a normalization failure must
             never break a render).
        """
        self.ensure_one()
        options = options or {}
        if not options.get('lazy_expand') or options.get('eager_expand'):
            return payload
        try:
            lines = payload.get('lines')
            if not isinstance(lines, list):
                return payload
            # The set of ids that are some line's parent_id, i.e. ids that
            # actually have >= 1 child line materialised in this payload.
            parents_with_children = set()
            for line in lines:
                if not isinstance(line, dict):
                    continue
                parent_id = line.get('parent_id')
                if parent_id:
                    parents_with_children.add(parent_id)
            for line in lines:
                if not isinstance(line, dict):
                    continue
                if line.get('lazy') is True:
                    # Lazy leaf: expands on demand; leave its flags as the
                    # handler stamped them (unfoldable True, collapsed).
                    continue
                if line.get('id') in parents_with_children:
                    line['unfoldable'] = True
                    if 'unfolded' not in line:
                        line['unfolded'] = True
                else:
                    line['unfoldable'] = False
        except Exception:  # pragma: no cover - normalization is best-effort
            _logger.exception(
                "fold normalization failed for report %s; lines unchanged",
                self.code,
            )
        return payload

    def _eh_clamp_company_ids(self, company_ids):
        """Restrict a report's company scope to companies the acting user
        may access.

        The reporting engine reads ledgers through the raw-SQL builder and
        sudo()'d searches, which bypass the multi-company ``ir.rule``. That
        makes this the ONLY place multi-company isolation is enforced for
        reports, so a caller-supplied ``options['company_ids']`` must never
        be trusted verbatim: any requested company outside the acting
        user's own ``company_ids`` is refused. Scheduled or background
        renders must switch to the owning user (``with_user``) so this
        clamp applies to that user rather than the cron's root context.
        """
        allowed = set(self.env.user.company_ids.ids)
        seen = set()
        requested = []
        for c in company_ids or ():
            cid = int(c)
            if cid not in seen:
                seen.add(cid)
                requested.append(cid)
        forbidden = [c for c in requested if c not in allowed]
        if forbidden:
            raise AccessError(_(
                "Report %(code)s was requested for companies you are not "
                "allowed to access (%(ids)s).",
                code=self.code,
                ids=', '.join(str(c) for c in forbidden),
            ))
        return requested or [self.env.company.id]

    def _eh_effective_options(self, options):
        """Return one normalized input used by audit, cache, and handler.

        Company order is not financial meaning. Primary-company policy is,
        so it is represented explicitly instead of being inferred from the
        first caller-supplied id. Language is part of cache identity because
        handlers resolve translated labels while computing the payload.
        """
        self.ensure_one()
        if not isinstance(options, dict):
            raise UserError(_("Report options must be a dictionary."))
        self._eh_validate_options_budget(options)
        effective = copy.deepcopy(options)
        requested = (
            effective.get('company_ids')
            or list(self.env.context.get(
                'allowed_company_ids', [self.env.company.id],
            ))
        )
        company_ids = sorted(set(self._eh_clamp_company_ids(requested)))
        raw_primary = effective.get('primary_company_id')
        primary_company_id = (
            int(raw_primary)
            if raw_primary
            else (
                self.env.company.id
                if self.env.company.id in company_ids
                else company_ids[0]
            )
        )
        if primary_company_id not in company_ids:
            raise AccessError(_(
                "Primary company %(primary)s is outside report company "
                "scope %(scope)s.",
                primary=primary_company_id,
                scope=', '.join(str(company_id) for company_id in company_ids),
            ))
        effective['company_ids'] = company_ids
        effective['primary_company_id'] = primary_company_id
        effective['_cache_context'] = {
            # Some handlers apply record rules after ledger aggregation (for
            # example analytic-account visibility). Never share their payload
            # across users with potentially different record-rule domains.
            'uid': self.env.uid,
            'lang': self.env.lang or 'en_US',
            # Date defaults and currency conversion use context_today(); a
            # render around midnight can differ by user timezone even when
            # every explicit option is identical.
            'tz': (
                self.env.context.get('tz')
                or self.env.user.tz
                or 'UTC'
            ),
            'engine_schema': _EH_REPORT_CACHE_SCHEMA_VERSION,
        }
        return effective, company_ids

    @api.model
    @api.private
    def _eh_validate_options_budget(self, options):
        """Reject pathological RPC option trees before deepcopy/hash/SQL.

        Normal report options are shallow and contain tens of ids. These
        generous ceilings only stop deliberately huge/deep payloads that can
        consume worker CPU or memory before normal report limits apply.
        """
        seen = set()
        item_count = 0
        stack = [(options, 0)]
        while stack:
            value, depth = stack.pop()
            if depth > _MAX_OPTIONS_DEPTH:
                raise UserError(_("Report options are nested too deeply."))
            if isinstance(value, str):
                if len(value) > _MAX_OPTION_TEXT:
                    raise UserError(_("A report option text value is too long."))
                continue
            if not isinstance(value, (dict, list, tuple, set)):
                continue
            marker = id(value)
            if marker in seen:
                continue
            seen.add(marker)
            if isinstance(value, dict):
                item_count += len(value)
                children = list(value.items())
                for key, child in children:
                    stack.append((key, depth + 1))
                    stack.append((child, depth + 1))
            else:
                item_count += len(value)
                stack.extend((child, depth + 1) for child in value)
            if item_count > _MAX_OPTIONS_ITEMS:
                raise UserError(_("Report options contain too many values."))

    def _eh_outer_move_version(self, company_ids):
        companies = self.env['res.company'].sudo().browse(company_ids)
        companies.invalidate_recordset(['eh_move_version'])
        return sum(companies.mapped('eh_move_version'))

    def render(self, options, result_format='json', use_cache=True):
        """Render the interactive JSON payload.

        Binary formats must use their dedicated renderers so the immutable
        execution row is completed only after the exact returned bytes exist.
        Keeping that finalizer on a private method also prevents an RPC caller
        from supplying a process-local callable.
        """
        if result_format != 'json':
            raise UserError(_(
                "Use the dedicated XLSX or PDF renderer for binary output."
            ))
        return self._eh_render_result(
            options,
            result_format='json',
            use_cache=use_cache,
        )

    @api.private
    def _eh_finalize_rendered_result(self, payload, result_builder=None):
        """Return the caller result and its truthful artifact digest."""
        if result_builder is None:
            return payload, False
        content = result_builder(payload)
        if not isinstance(content, (bytes, bytearray)):
            raise UserError(_(
                "A report export renderer must return binary content."
            ))
        content = bytes(content)
        return content, hashlib.sha256(content).hexdigest()

    @api.private
    def _eh_render_result(self, options, result_format='json', use_cache=True,
                          result_builder=None, persist_payload=True):
        """Run the report. Returns the same shape on hit and miss.

        Result dict keys:

        * columns, lines, totals, generated_at: from handler.compute().
        * execution_id: id of the eh.account.report.execution row.
        * from_cache: True when served from a prior execution payload.

        On error, the execution row is marked 'error' with the exception
        message, and the exception is re raised so the caller can surface it.
        """
        if result_format == 'json':
            if result_builder is not None:
                raise ValueError(
                    "JSON report rendering cannot use a binary builder"
                )
        elif (
            result_format not in ('xlsx', 'pdf')
            or not callable(result_builder)
        ):
            raise ValueError("Binary report rendering requires a format builder")
        self.ensure_one()
        self._eh_check_access('read')
        Execution = self.env['eh.account.report.execution']

        effective_options, company_ids = self._eh_effective_options(options)
        # Resolve and normalize handler-owned capabilities before audit/cache
        # identity.  This also prevents unsupported dimensions from reaching
        # central post-processors after the handler has computed its payload.
        handler = self.env[self.handler_model].with_context(
            eh_report_code=self.code,
        )
        effective_options = handler.normalize_options(effective_options)

        canonical = Execution._canonicalise_options(effective_options)
        options_hash = Execution._hash_string(
            json.dumps(canonical, sort_keys=True, default=str)
        )

        # Start before lookup. The cache source must match this exact version
        # snapshot, then completion rechecks it after payload load to close the
        # post-between-lookup-and-audit race.
        outer_version = self._eh_outer_move_version(company_ids)
        execution = Execution.start_execution(
            report_code=self.code,
            name=self.name,
            options=effective_options,
            company_ids=company_ids,
            result_format=result_format,
            move_version_at_start=outer_version,
        )

        try:
            # Analytic Balance applies caller-specific analytic record rules
            # after raw ledger aggregation. Group/rule revocation can change
            # visible labels without touching any financial input counter, so
            # its persistent payload must never be reused.
            cache_eligible = bool(
                persist_payload
                and
                outer_version == execution.move_version_at_start
                and self.handler_model not in self._EH_ACL_SENSITIVE_HANDLERS
            )
            if use_cache and cache_eligible:
                cached = Execution.find_cached(
                    self.code,
                    options_hash,
                    company_ids,
                    move_version_at_start=execution.move_version_at_start,
                )
                if cached:
                    payload = cached._load_trusted_payload()
                    if payload is not None:
                        self._eh_assert_currency_scope_supported(
                            payload, company_ids,
                        )
                        payload['execution_id'] = execution.id
                        payload['from_cache'] = True
                        self._eh_apply_annotations(
                            payload, company_ids, effective_options,
                        )
                        rendered_result, result_hash = (
                            self._eh_finalize_rendered_result(
                                payload, result_builder,
                            )
                        )
                        completed = execution.complete_execution(
                            row_count=len(payload.get('lines', [])),
                            result_hash=result_hash,
                            served_from_execution_id=cached.id,
                            cache_eligible=True,
                        )
                        if completed:
                            _logger.info(
                                "Report %s cache HIT served_by=%s source=%s",
                                self.code, execution.id, cached.id,
                            )
                            return rendered_result

            # Cache miss, explicit bypass, stale hit, or uncommitted inputs.
            # Record the exact outer-transaction version used for computation;
            # completion suppresses shared caching when another transaction
            # cannot confirm that snapshot.
            outer_version = self._eh_outer_move_version(company_ids)
            execution.refresh_execution_snapshot(outer_version)
            cache_eligible = (
                cache_eligible
                and execution._current_move_version() == outer_version
            )
            # Pass the report code via context so generic handlers (like
            # the custom report builder) can resolve which definition to
            # interpret without polluting the options dict.
            payload = handler.compute(effective_options)
            self._eh_assert_currency_scope_supported(payload, company_ids)
            # Uniform fold normalization: enforce, identically across every
            # report, the invariant "a caret appears IFF the row has something
            # to expand". Runs right after the handler computes lines and
            # before caching, so the cached payload already carries the
            # normalised flags. Gated on lazy_expand (and off for eager/export)
            # so direct compute() callers, export, and the existing suite see
            # byte-identical lines.
            self._eh_normalize_fold(payload, effective_options)
            # Universal presentation-currency translation: any report can be
            # restated into a chosen currency without each handler knowing.
            # Runs before caching so the cached payload is already in the
            # selected currency (the options hash includes it).
            self._eh_apply_presentation_currency(
                payload, effective_options, company_ids,
            )
            # Attach currency info to every payload so the OWL viewer and
            # the XLSX writer can render amounts with the right symbol /
            # decimal places without each handler having to remember.
            if 'currency' not in payload:
                payload['currency'] = handler.resolve_currency_info(
                    effective_options,
                )
            row_count = len(payload.get('lines', []))
            # Some server-owned delivery paths (notably authenticated portal
            # statements) need a truthful execution/hash audit without
            # retaining the sensitive binary's source payload in an
            # attachment-backed cache.  The caller reaches this switch only
            # through a private in-process corridor; ordinary renders retain
            # the durable reproducibility/cache behaviour.
            compressed = (
                compress_payload(payload) if persist_payload else None
            )
            payload['execution_id'] = execution.id
            payload['from_cache'] = False
            self._eh_apply_annotations(
                payload, company_ids, effective_options,
            )
            rendered_result, result_hash = self._eh_finalize_rendered_result(
                payload, result_builder,
            )
            completion_vals = {
                'row_count': row_count,
                'result_hash': result_hash,
                'cache_eligible': cache_eligible,
            }
            if persist_payload:
                completion_vals['result_payload'] = compressed
            execution.complete_execution(
                **completion_vals
            )
            return rendered_result
        except Exception as exc:
            # Persist a separate error row outside the doomed RPC transaction.
            # Preserve the original render failure if audit persistence fails.
            try:
                durable_id = Execution.record_failure_durable(
                    report_code=self.code,
                    name=self.name,
                    options=effective_options,
                    company_ids=company_ids,
                    result_format=result_format,
                    error_message=str(exc),
                    move_version_at_start=execution.move_version_at_start,
                    definition_id=self.id,
                )
                if execution.state == 'running':
                    execution.fail_execution(str(exc))
                if durable_id:
                    _logger.info(
                        "Persisted durable failure audit %s for local "
                        "execution %s",
                        durable_id, execution.id,
                    )
            except Exception:  # noqa: BLE001 - preserve original exception
                _logger.exception(
                    "Could not persist report failure audit for execution %s",
                    execution.id,
                )
            raise

    def _eh_apply_annotations(self, payload, company_ids, options=None):
        """Attach annotations to the payload's lines/cells, in place.

        Applied after caching so notes are always live and never frozen
        into the cached result. A note with no expression_label is
        attached to the line's meta; one with a label is attached to the
        matching column dict. Each note carries its author, create date and
        a can_delete flag (manager-only) so the viewer can show the date and
        gate the delete affordance without eroding the append-only posture.

        Passing options with show_annotations=False suppresses the pass
        entirely (notes are hidden, not lost). options is optional so older
        callers keep working unchanged.
        """
        self.ensure_one()
        from collections import defaultdict
        # Opt-out: a user can hide notes for a clean print/screenshot without
        # losing them. Absent / truthy keeps the historical behaviour.
        if 'show_annotations' in (options or {}) and not (options or {}).get(
                'show_annotations', True):
            return payload
        annotations = self.env['eh.account.report.annotation'].search([
            ('report_code', '=', self.code),
            ('company_id', 'in', list(company_ids)),
        ])
        if not annotations:
            return payload
        # Manager-gated delete: the user group can create notes but cannot
        # write or unlink them (append-only audit posture), so only managers
        # see the delete affordance. Resolved once, not per-note.
        can_delete = self.env.user.has_group(
            'eh_account_base.group_eh_manager')
        by_key = defaultdict(list)
        for ann in annotations:
            by_key[(ann.line_id, ann.expression_label or False)].append({
                'id': ann.id,
                'text': ann.text,
                'author': ann.create_uid.name,
                'date': (ann.create_date.isoformat()
                         if ann.create_date else False),
                'can_delete': can_delete,
            })
        for line in payload.get('lines', []):
            line_id = line.get('id')
            if not line_id:
                continue
            row_notes = by_key.get((line_id, False))
            if row_notes:
                line.setdefault('meta', {})['annotations'] = row_notes
            for col in line.get('columns', []):
                cell_notes = by_key.get(
                    (line_id, col.get('expression_label')))
                if cell_notes:
                    col['annotations'] = cell_notes
        return payload

    def add_annotation(self, line_id, text, expression_label=False):
        """Create an annotation on this report for the given line/cell."""
        self.ensure_one()
        self._eh_check_access('read')
        return self.env['eh.account.report.annotation'].create({
            'report_code': self.code,
            'line_id': line_id,
            'expression_label': expression_label or False,
            'text': text,
            'company_id': self.env.company.id,
        })

    def delete_annotation(self, annotation_id):
        """Remove a single annotation from this report.

        Manager-gated: the user group can create annotations but cannot write
        or unlink them, so a non-manager call raises an AccessError from the
        ORM, preserving the append-only audit posture.
        Scoped defensively to this report's code and an allowed company so a
        note can never be deleted from the wrong report or a company the
        user is not in. Returns True on a successful unlink, False when the
        id does not resolve to a note on this report (no raise, so a stale
        UI id never errors the viewer).
        """
        self.ensure_one()
        self._eh_check_access('read')
        try:
            ann = self.env['eh.account.report.annotation'].browse(
                int(annotation_id)).exists()
        except (TypeError, ValueError):
            return False
        if not ann or ann.report_code != self.code:
            return False
        allowed_companies = self.env.companies.ids
        if ann.company_id.id not in allowed_companies:
            return False
        # unlink() enforces the manager-only ACL; we deliberately do not
        # sudo() so the audit posture (non-managers cannot delete) holds.
        ann.unlink()
        return True

    def render_xlsx(self, options, use_cache=True):
        """Render the report and return XLSX bytes.

        Equivalent to render() followed by passing the JSON payload to the
        XLSX writer. Cache hits short circuit recomputation, the writer
        runs against the cached payload directly.
        """
        self.ensure_one()
        self._eh_check_access('read')
        # An export must contain the full detail, not the lazy on-demand
        # skeleton the OWL viewer requests: General Ledger / Partner Ledger
        # gate their aml rows on lazy_expand, so a straight-through export of
        # the viewer's options produces a workbook with headers and totals but
        # zero transaction lines. Force eager expansion here.
        options = dict(options, eager_expand=True)
        options.pop('lazy_expand', None)
        writer = XlsxReportWriter(report_name=self.name)
        return self._eh_render_result(
            options,
            result_format='xlsx',
            use_cache=use_cache,
            result_builder=writer.write_payload,
        )

    def export_xlsx_attachment(self, options):
        """Render to XLSX, persist as ir.attachment, and return a download
        action.

        The OWL viewer calls this from the Export to Excel button. It exists
        because passing raw bytes through OWL's RPC layer is awkward; an
        attachment plus an act_url action is the conventional Odoo path.
        """
        self.ensure_one()
        self._eh_check_access('read')
        content = self.render_xlsx(options)
        date_block = options.get('date') or {}
        filename = "%s_%s_to_%s.xlsx" % (
            self.code,
            date_block.get('date_from') or '',
            date_block.get('date_to') or '',
        )
        return self._eh_private_download_action(
            content=content,
            filename=filename,
            mimetype=(
                'application/vnd.openxmlformats-officedocument'
                '.spreadsheetml.sheet'
            ),
            options=options,
        )

    @api.private
    def _eh_private_download_action(
        self, content, filename, mimetype, options,
    ):
        """Persist server-built bytes on an owner-scoped transient.

        Linking exports to shared report definitions or business partners
        widens attachment reads to everyone who can read those records.  This
        helper gives every caller one short-lived, create_uid-scoped resource.
        """
        import base64

        self.ensure_one()
        self._eh_check_access('read')
        effective_options, company_ids = self._eh_effective_options(
            options or {},
        )
        date_block = effective_options.get('date') or {}
        date_from = fields.Date.to_date(date_block.get('date_from'))
        date_to = fields.Date.to_date(date_block.get('date_to'))
        today = fields.Date.context_today(self)
        owner = self.env['eh.account.report.wizard'].create({
            'report_id': self.id,
            'period_preset': 'custom',
            'date_from': date_from or today,
            'date_to': date_to or date_from or today,
            'company_ids': [(6, 0, company_ids)],
        })
        safe_filename = str(filename or 'report').replace('/', '_').replace(
            '\\', '_',
        ).replace('\r', '_').replace('\n', '_')
        # Attachment creation requires write access on the linked resource.
        # Read-only auditors intentionally have only read/create access on the
        # transient, so elevate only this exact server-built row. sudo keeps
        # caller UID/create_uid; later reads still delegate to owner ACL/rule.
        attachment = self.env['ir.attachment'].sudo().create({
            'name': safe_filename,
            'type': 'binary',
            'datas': base64.b64encode(content),
            'mimetype': mimetype,
            'res_model': owner._name,
            'res_id': owner.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'download',
        }

    def expand_line(self, options, line_id, offset=0, limit=None):
        """RPC entry point: fetch one lazy account leaf's child page.

        Resolves the handler (mirroring get_drilldown_for_line), delegates
        to handler.expand_account_line, then applies the same
        presentation-currency restatement and annotations to the returned
        child_lines that the main payload receives, so paged children honour
        currency and notes identically. Does NOT create a cached payload
        row: children are sub-slices of an already-audited render.

        Fallback: any failure returns an empty, collapsed page rather than
        raising, so a failed expand leaves the row collapsed (the §2
        invariant: a broken expand never fans out or crashes the report).
        """
        self.ensure_one()
        # Authorization failures must not look like ordinary empty pages.
        self._eh_check_access('read')
        try:
            safe_offset = max(0, int(offset or 0))
        except (TypeError, ValueError):
            safe_offset = 0
        empty = {
            'child_lines': [], 'has_more': False,
            'next_offset': safe_offset, 'total_count': 0,
        }
        if (not isinstance(line_id, str)
                or len(line_id) > _MAX_EXPAND_LINE_ID
                or safe_offset > _MAX_EXPAND_OFFSET):
            return empty
        try:
            # SECURITY: clamp the requested company scope BEFORE delegating.
            # The handler reads ledgers via the raw-SQL builder / sudo searches
            # that bypass ir.rule, so an unclamped drill-down RPC would leak
            # another company's journal items even though render() clamps. A
            # forbidden request raises inside this try and returns an empty
            # (collapsed) page, matching the "expand never crashes" contract.
            options, company_ids = self._eh_effective_options(options or {})
            handler = self.env[self.handler_model].with_context(
                eh_report_code=self.code,
            )
            requested_limit = (
                handler._resolve_expand_page_size(options)
                if limit is None else limit
            )
            try:
                safe_limit = int(requested_limit)
            except (TypeError, ValueError):
                safe_limit = 80
            safe_limit = max(1, min(safe_limit, _MAX_EXPAND_PAGE_SIZE))
            result = handler.expand_account_line(
                options, line_id, offset=safe_offset, limit=safe_limit,
            )
            if not isinstance(result, dict):
                return empty
            child_lines = result.get('child_lines') or []
            # Restate child monetary cells into the presentation currency
            # and attach annotations, reusing the same helpers the main
            # payload goes through. Wrapped in a sub-payload so the helpers
            # (which expect {columns, lines}) operate over the children.
            try:
                columns = []
                # The handler exposes the host report's columns via compute,
                # but we avoid recomputing; child cells already carry the
                # host expression_labels, so we drive the monetary set from
                # the handler's _build_columns when available.
                if hasattr(handler, '_build_columns'):
                    columns = handler._build_columns() or []
                sub_payload = {
                    'columns': columns,
                    'lines': child_lines,
                    'totals': {},
                    'meta': {
                        'presentation_currency_converted': bool(
                            result.get('presentation_currency_converted')),
                    },
                }
                self._eh_apply_presentation_currency(
                    sub_payload, options, company_ids)
                self._eh_apply_annotations(sub_payload, company_ids, options)
            except Exception:  # pragma: no cover - presentation is best-effort
                _logger.exception(
                    "expand_line presentation/annotation failed for %s %s",
                    self.code, line_id,
                )
            return {
                'child_lines': child_lines,
                'has_more': bool(result.get('has_more')),
                'next_offset': int(result.get('next_offset') or 0),
                'total_count': int(result.get('total_count') or 0),
            }
        except Exception:
            _logger.exception(
                "expand_line failed for report %s line %s; row stays collapsed",
                self.code, line_id,
            )
            return empty

    def get_drilldown_for_line(self, options, line_id):
        """Return the handler's drill down action for a given line id.

        Thin RPC wrapper around the handler's get_drilldown_action so the
        OWL viewer can invoke it without holding a handler reference.
        Returns None when the line has no drill down (the OWL viewer
        treats falsy responses as a no op click).
        """
        self.ensure_one()
        self._eh_check_access('read')
        options, _company_ids = self._eh_effective_options(options or {})
        handler = self.env[self.handler_model].with_context(
            eh_report_code=self.code,
        )
        return handler.get_drilldown_action(options, line_id)

    @api.private
    def _eh_bound_analytic_snapshot_cell(
        self, payload, line_id, expression_label, displayed_amount,
    ):
        """Resolve one exact monetary cell from an audited result payload."""
        self.ensure_one()
        columns = payload.get('columns') if isinstance(payload, dict) else None
        lines = payload.get('lines') if isinstance(payload, dict) else None
        currency = payload.get('currency') if isinstance(payload, dict) else None
        if (
            not isinstance(columns, list)
            or not isinstance(lines, list)
            or not isinstance(currency, dict)
        ):
            raise UserError(_(
                "The displayed report snapshot is malformed. Refresh the "
                "report and try again."
            ))
        column_indexes = [
            index for index, column in enumerate(columns[1:])
            if isinstance(column, dict)
            and column.get('expression_label') == expression_label
        ]
        matching_lines = [
            line for line in lines
            if isinstance(line, dict) and line.get('id') == line_id
        ]
        if len(column_indexes) != 1 or len(matching_lines) != 1:
            raise UserError(_(
                "The selected cell is not part of the displayed report "
                "snapshot. Refresh the report and try again."
            ))
        value_index = column_indexes[0]
        column = columns[value_index + 1]
        line_columns = matching_lines[0].get('columns')
        if not isinstance(line_columns, list) or value_index >= len(line_columns):
            raise UserError(_(
                "The selected cell is not part of the displayed report "
                "snapshot. Refresh the report and try again."
            ))
        cell = line_columns[value_index]
        value = cell.get('value') if isinstance(cell, dict) else None
        if (
            not isinstance(cell, dict)
            or cell.get('expression_label') != expression_label
            or not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
            or not isinstance(displayed_amount, (int, float))
            or isinstance(displayed_amount, bool)
            or not math.isfinite(float(displayed_amount))
            or float(value) != float(displayed_amount)
            or not isinstance(column.get('scope'), dict)
            or not isinstance(currency.get('id'), int)
            or isinstance(currency.get('id'), bool)
            or currency['id'] < 1
        ):
            raise UserError(_(
                "The selected amount does not match the displayed report "
                "snapshot. Refresh the report and try again."
            ))
        return {
            'amount': float(value),
            'scope': column['scope'],
            'currency_id': currency['id'],
        }

    def get_analytic_column_drilldown_page(
        self, options, line_id, expression_label, offset=0, limit=80,
        execution_id=None, displayed_amount=None, page_token=None,
    ):
        """Return a truthful weighted journal-item page for one axis cell.

        Ordinary ``account.move.line`` actions cannot express allocation
        percentages from ``analytic_distribution``.  This RPC therefore
        delegates only to handlers which explicitly opt in to a read-only,
        allocation-aware detail projection.  The clicked scope is rebuilt
        server-side from normalized public options; caller-supplied private
        scope overlays are discarded rather than trusted.
        """
        self.ensure_one()
        self._eh_check_access('read')
        if (
            not isinstance(line_id, str)
            or not line_id
            or len(line_id) > _MAX_EXPAND_LINE_ID
            or not isinstance(expression_label, str)
            or not expression_label
            or len(expression_label) > _MAX_ANALYTIC_DRILLDOWN_EXPRESSION
        ):
            raise UserError(_("Invalid analytic drill-down cell."))
        try:
            safe_offset = int(offset)
            safe_limit = int(limit)
        except (TypeError, ValueError, OverflowError) as exc:
            raise UserError(_("Invalid analytic drill-down page.")) from exc
        if (
            safe_offset < 0
            or safe_offset > _MAX_EXPAND_OFFSET
            or safe_limit < 1
            or safe_limit > _MAX_EXPAND_PAGE_SIZE
        ):
            raise UserError(_("Invalid analytic drill-down page."))
        if (
            not isinstance(execution_id, int)
            or isinstance(execution_id, bool)
            or execution_id < 1
            or page_token not in (None, False, '')
            and (
                not isinstance(page_token, str)
                or len(page_token) > 128
            )
        ):
            raise UserError(_(
                "Invalid displayed report snapshot. Refresh the report and "
                "try again."
            ))

        effective_options, company_ids = self._eh_effective_options(
            options or {},
        )
        # These keys are an internal server overlay.  A browser may retain
        # them in local state after an old build, but it may never choose its
        # own analytic allocation slice by posting them back to this RPC.
        for key in tuple(effective_options):
            if key.startswith('_eh_analytic_column_'):
                effective_options.pop(key, None)
        context = dict(
            self.env.context,
            eh_report_code=self.code,
            allowed_company_ids=company_ids,
        )
        handler = self.env[self.handler_model].with_context(context)
        effective_options = handler.normalize_options(effective_options)
        if (
            self.code not in (
                'profit_and_loss', 'balance_sheet', 'trial_balance',
            )
            or getattr(handler, 'REPORT_CODE', None) != self.code
            or not getattr(
                handler, '_EH_ANALYTIC_COLUMN_DRILLDOWN', False,
            )
        ):
            raise UserError(_(
                "Weighted analytic drill-down is not available for this "
                "report."
            ))

        Execution = self.env['eh.account.report.execution']
        canonical_options = Execution._canonicalise_options(
            effective_options,
        )
        options_hash = Execution._hash_string(json.dumps(
            canonical_options, sort_keys=True, default=str,
        ))
        execution = Execution.search([('id', '=', execution_id)], limit=1)
        if not execution:
            raise AccessError(_(
                "The report execution is not accessible. Refresh the report "
                "and try again."
            ))
        execution._eh_check_access('read')
        if (
            execution.executed_by.id != self.env.uid
            or execution.state != 'done'
            or execution.result_format != 'json'
            or execution.report_code != self.code
        ):
            raise AccessError(_(
                "The report execution does not belong to this displayed "
                "report. Refresh the report and try again."
            ))
        try:
            stored_options = json.loads(execution.options_snapshot)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise UserError(_(
                "The displayed report options snapshot is invalid. Refresh "
                "the report and try again."
            )) from exc
        if (
            not isinstance(stored_options, dict)
            or Execution._canonicalise_options(stored_options)
            != canonical_options
            or execution.options_hash != options_hash
        ):
            raise UserError(_(
                "The report options changed after this result was displayed. "
                "Refresh the report and try again."
            ))
        snapshot_payload = execution._eh_load_bound_json_snapshot(
            self.code, options_hash, company_ids,
        )
        snapshot_cell = self._eh_bound_analytic_snapshot_cell(
            snapshot_payload, line_id, expression_label, displayed_amount,
        )
        page = handler._eh_get_analytic_column_drilldown_page(
            effective_options,
            line_id,
            expression_label,
            offset=safe_offset,
            limit=safe_limit,
            page_token=page_token or None,
            snapshot_binding={
                'execution_id': execution.id,
                'options_hash': options_hash,
                'displayed_amount': snapshot_cell['amount'],
            },
        )
        if (
            not isinstance(page, dict)
            or not isinstance(page.get('total'), (int, float))
            or isinstance(page.get('total'), bool)
            or not math.isfinite(float(page['total']))
            or float(page['total']) != snapshot_cell['amount']
            or (page.get('currency') or {}).get('id')
            != snapshot_cell['currency_id']
            or Execution._canonicalise_options(page.get('scope'))
            != Execution._canonicalise_options(snapshot_cell['scope'])
        ):
            raise UserError(_(
                "The journal items no longer match the displayed amount. "
                "Refresh the report and try again."
            ))
        return page
