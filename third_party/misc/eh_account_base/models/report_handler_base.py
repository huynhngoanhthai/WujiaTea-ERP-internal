# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Abstract base for dynamic report handlers.

Concrete handlers _inherit this model and override compute(). The
orchestrator (eh.account.dynamic.report) instantiates the handler by model
name and calls compute() with the options dict.

Why an Odoo AbstractModel and not a plain Python class:

* Localizations and add ons can extend a handler with _inherit, override
  compute(), and add new lines or columns without touching the base addon.
* Discovery through self.env[handler_model] is one line and consistent with
  the rest of the framework.
* Inheritance composition (multiple addons stacking on the same handler)
  works out of the box.

Shared helpers live here so concrete handlers stay small and focused on
report specific math:

* _extract_date(options, key): pulls and parses a date from options['date'].
* _iso_date(value): renders a date or string back to ISO format.
* get_drilldown_action(options, line_id): default account drill down to
  filtered journal items. Concrete handlers override only when their
  line_id scheme differs.
"""

from calendar import monthrange
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

from odoo.addons.eh_account_base.tools.sql_builder import MoveLineQuery
from odoo.addons.eh_account_base.tools.currency_table import CurrencyTable


_EH_MAX_ANALYTIC_COLUMN_GROUPS = 8
_EH_MAX_COMPARISON_PERIODS = 12
_EH_MAX_VALUE_COLUMNS = 48


class EhAccountDynamicReportHandler(models.AbstractModel):
    _name = 'eh.account.dynamic.report.handler'
    _description = "Base for ERP Heritage dynamic report handlers"

    REPORT_CODE = ''
    REPORT_NAME = ""
    _UNSUPPORTED_OPTION_KEYS = frozenset()
    # Column axes are opt-in because their public selectors otherwise become
    # false audit/cache state on handlers which compute only one value column.
    # Concrete handlers must declare every axis they apply financially.
    _EH_COLUMN_AXIS_CAPABILITIES = frozenset()
    _EH_COMPARISON_AXIS_OPTION_KEYS = (
        'comparison',
        'comparison_number',
        'comparison_custom_date_from',
        'comparison_custom_date_to',
        'comparison_order',
    )
    _EH_ANALYTIC_COLUMN_OPTION_KEYS = (
        'analytic_column_account_ids',
        'analytic_column_plan_ids',
    )
    # Keep direct handler calls within the same resource budget enforced by
    # eh.account.dynamic.report.expand_line's public RPC boundary.
    _MAX_EXPAND_PAGE_SIZE = 500
    _MAX_ANALYTIC_COLUMN_GROUPS = _EH_MAX_ANALYTIC_COLUMN_GROUPS
    _MAX_COMPARISON_PERIODS = _EH_MAX_COMPARISON_PERIODS
    _MAX_VALUE_COLUMNS = _EH_MAX_VALUE_COLUMNS

    @api.model
    @api.private
    def normalize_options(self, options):
        """Remove dimensions this handler cannot apply coherently.

        This runs in the orchestrator before audit/cache hashing and before
        post-processing.  A handler-local copy inside ``compute`` is too late:
        an unsupported value would still fragment cache keys and could drive a
        central post-processor such as presentation-currency conversion.
        """
        normalized = dict(options or {})
        for key in self._UNSUPPORTED_OPTION_KEYS:
            normalized.pop(key, None)
        self._eh_assert_column_axis_capabilities(normalized)
        normalized = self._eh_normalize_column_axis_options(normalized)
        capabilities = frozenset(self._EH_COLUMN_AXIS_CAPABILITIES or ())
        if 'comparison' not in capabilities:
            for key in self._EH_COMPARISON_AXIS_OPTION_KEYS:
                normalized.pop(key, None)
        if 'analytic_columns' not in capabilities:
            for key in self._EH_ANALYTIC_COLUMN_OPTION_KEYS:
                normalized.pop(key, None)
        # Axis canonicalisation supplies semantic defaults.  A handler which
        # explicitly rejects one of those dimensions must still remove it
        # from cache identity and compute input.
        for key in self._UNSUPPORTED_OPTION_KEYS:
            normalized.pop(key, None)
        return normalized

    @api.model
    def _eh_assert_column_axis_capabilities(self, options):
        """Reject active axes the concrete handler cannot compute.

        This guard runs from ``normalize_options`` before the orchestrator
        creates an execution.  Empty/default controls are harmless and are
        removed from unsupported handlers' canonical options below; active
        selectors fail closed instead of being audited as though they affected
        figures.
        """
        options = options or {}
        capabilities = frozenset(self._EH_COLUMN_AXIS_CAPABILITIES or ())
        unsupported = []
        comparison = options.get('comparison') or 'none'
        if comparison != 'none' and 'comparison' not in capabilities:
            unsupported.append(_('comparison columns'))
        if (
            'analytic_columns' not in capabilities
            and any(
                options.get(key)
                for key in self._EH_ANALYTIC_COLUMN_OPTION_KEYS
            )
        ):
            unsupported.append(_('analytic columns'))
        if unsupported:
            raise UserError(_(
                "Report %(report)s does not support these column-axis "
                "dimensions: %(dimensions)s.",
                report=self.REPORT_NAME or self._description,
                dimensions=', '.join(unsupported),
            ))

    @api.model
    @api.private
    def build_default_options(self):
        """Return the default options dict for this report.

        Subclasses may override to add report specific defaults. Always call
        super() and merge.
        """
        today = fields.Date.context_today(self)
        first_of_month = today.replace(day=1)
        return {
            'date': {
                'mode': 'range',
                'date_from': first_of_month.isoformat(),
                'date_to': today.isoformat(),
            },
            'company_ids': list(
                self.env.context.get(
                    'allowed_company_ids',
                    [self.env.company.id],
                )
            ),
            'journal_ids': [],
            'partner_ids': [],
            'account_ids': [],
            'analytic_account_ids': [],
            'analytic_plan_ids': [],
            'analytic_column_account_ids': [],
            'analytic_column_plan_ids': [],
            'unfolded_lines': [],
            'show_zero': False,
            'posted_only': True,
            'comparative': None,
            'comparison_number': 1,
            'comparison_custom_date_from': '',
            'comparison_custom_date_to': '',
            'comparison_order': 'descending',
            'currency_display': 'symbol',
        }

    # ---- comparison x analytic column-axis contract ----

    @staticmethod
    def _eh_normalize_id_set(value, option_name):
        """Return a sorted, duplicate-free positive integer option set."""
        if value is None:
            return []
        if not isinstance(value, (list, tuple, set)):
            raise UserError(_(
                "%(option)s must contain only record IDs.",
                option=option_name,
            ))
        ids = set()
        for record_id in value:
            if isinstance(record_id, bool):
                raise UserError(_(
                    "%(option)s must contain only record IDs.",
                    option=option_name,
                ))
            try:
                normalized_id = int(record_id)
            except (TypeError, ValueError, OverflowError) as exc:
                raise UserError(_(
                    "%(option)s must contain only record IDs.",
                    option=option_name,
                )) from exc
            # ``int(7.5)`` silently truncates. Numeric strings remain valid
            # RPC IDs, but every non-string numeric value must already be a
            # whole number.
            if not isinstance(record_id, str) and record_id != normalized_id:
                raise UserError(_(
                    "%(option)s must contain only record IDs.",
                    option=option_name,
                ))
            ids.add(normalized_id)
        if any(record_id <= 0 for record_id in ids):
            raise UserError(_(
                "%(option)s must contain only positive record IDs.",
                option=option_name,
            ))
        return sorted(ids)

    @staticmethod
    def _eh_normalize_comparison_number(value):
        """Return one positive whole comparison count without truncation."""
        if isinstance(value, bool):
            raise UserError(_(
                "Comparison period count must be a whole number."
            ))
        try:
            number = int(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise UserError(_(
                "Comparison period count must be a whole number."
            )) from exc
        # Keep backwards compatibility for integer strings and whole numeric
        # values (3.0, Decimal('3')). Reject int()'s silent 3.7 -> 3 coercion.
        if not isinstance(value, str) and value != number:
            raise UserError(_(
                "Comparison period count must be a whole number."
            ))
        if number < 1:
            raise UserError(_(
                "Comparison period count must be at least one."
            ))
        return number

    @api.model
    def _eh_normalize_column_axis_options(self, options):
        """Canonicalise public column-axis options before hash or compute.

        Existing ``analytic_account_ids`` / ``analytic_plan_ids`` stay global
        row filters.  Horizontal selectors have separate option keys and are
        canonical sets.  Server-only scope keys are discarded here so an RPC
        caller cannot smuggle a pre-resolved analytic allocation into render.
        Scoped compute helpers add those keys only after this boundary.
        """
        normalized = dict(options or {})
        for key in (
            '_eh_analytic_column_active',
            '_eh_analytic_column_account_ids',
            '_eh_analytic_column_plan_ids',
            '_eh_analytic_column_is_total',
            '_eh_column_expression',
        ):
            normalized.pop(key, None)

        for key in (
            'analytic_column_account_ids',
            'analytic_column_plan_ids',
        ):
            normalized[key] = self._eh_normalize_id_set(
                normalized.get(key), key,
            )

        group_count = (
            len(normalized['analytic_column_account_ids'])
            + len(normalized['analytic_column_plan_ids'])
        )
        if group_count > _EH_MAX_ANALYTIC_COLUMN_GROUPS:
            raise UserError(_(
                "Reports support at most %(maximum)s analytic column groups.",
                maximum=_EH_MAX_ANALYTIC_COLUMN_GROUPS,
            ))

        comparison = normalized.get('comparison') or 'none'
        if comparison not in (
            'none', 'previous_period', 'previous_year', 'custom',
        ):
            raise UserError(_(
                "Unsupported comparison mode %(mode)s.",
                mode=comparison,
            ))
        comparison_number = self._eh_normalize_comparison_number(
            normalized.get('comparison_number', 1),
        )
        if comparison in ('none', 'custom'):
            comparison_number = 1
        if comparison_number > _EH_MAX_COMPARISON_PERIODS:
            raise UserError(_(
                "Reports support at most %(maximum)s comparison periods.",
                maximum=_EH_MAX_COMPARISON_PERIODS,
            ))

        order = normalized.get('comparison_order', 'descending')
        if order not in ('ascending', 'descending'):
            raise UserError(_(
                "Comparison order must be ascending or descending."
            ))
        if comparison == 'none':
            # Hidden inactive controls carry no financial meaning and must
            # neither activate an axis nor fragment cache identity.
            order = 'descending'
        normalized['comparison_order'] = order
        if comparison == 'custom':
            custom_from = normalized.get('comparison_custom_date_from')
            custom_to = normalized.get('comparison_custom_date_to')
            if not custom_from or not custom_to:
                raise UserError(_(
                    "Custom comparison requires both From and To dates."
                ))
            try:
                custom_from = fields.Date.to_date(custom_from)
                custom_to = fields.Date.to_date(custom_to)
            except (TypeError, ValueError) as exc:
                raise UserError(_(
                    "Custom comparison dates must use YYYY-MM-DD."
                )) from exc
            if custom_from > custom_to:
                raise UserError(_(
                    "Custom comparison From date cannot be after To date."
                ))
            normalized['comparison_custom_date_from'] = self._iso_date(
                custom_from,
            )
            normalized['comparison_custom_date_to'] = self._iso_date(
                custom_to,
            )
        else:
            # Hidden stale custom dates carry no financial meaning and must
            # not fragment report-cache identity.
            normalized['comparison_custom_date_from'] = ''
            normalized['comparison_custom_date_to'] = ''
        normalized['comparison_number'] = comparison_number

        if group_count:
            company_ids = (
                normalized.get('company_ids')
                or self.env.context.get('allowed_company_ids')
                or [self.env.company.id]
            )
            # Resolve once at trust boundary.  Compute helpers resolve again
            # to return labels/account expansion, never under sudo.
            self._eh_resolve_analytic_column_scopes(
                normalized, company_ids,
            )
        return normalized

    @api.model
    def _eh_column_axis_requested(self, options, allow_analytic=False):
        """Whether caller explicitly requests new multi-axis rendering.

        Default descending single comparison remains on legacy
        current/prior/variance layout.  Ascending order, custom dates,
        multiple prior periods, or supported analytic selectors opt in.
        """
        options = options or {}
        comparison = options.get('comparison') or 'none'
        number = self._eh_normalize_comparison_number(
            options.get('comparison_number', 1),
        )
        if comparison == 'custom' or number > 1:
            return True
        if (
            comparison != 'none'
            and options.get('comparison_order') == 'ascending'
        ):
            return True
        return bool(
            allow_analytic
            and (
                options.get('analytic_column_account_ids')
                or options.get('analytic_column_plan_ids')
            )
        )

    @api.model
    def _eh_resolve_comparison_dates(
        self, mode, date_from, date_to,
    ):
        """Resolve one prior window, shared by all report handler shapes."""
        if mode == 'previous_period':
            if (
                date_from.day == 1
                and date_to.day == monthrange(
                    date_to.year, date_to.month,
                )[1]
            ):
                months = (
                    (date_to.year - date_from.year) * 12
                    + date_to.month - date_from.month + 1
                )
                prior_from = date_from - relativedelta(months=months)
                prior_to = date_from - timedelta(days=1)
                return prior_from, prior_to, _("Previous period")
            length = (date_to - date_from).days + 1
            prior_to = date_from - timedelta(days=1)
            prior_from = prior_to - timedelta(days=length - 1)
            return prior_from, prior_to, _("Previous period")
        if mode == 'previous_year':
            prior_from = date_from - relativedelta(years=1)
            prior_to = date_to - relativedelta(years=1)
            return prior_from, prior_to, _("Same period last year")
        return None, None, ''

    @api.model
    def _eh_resolve_period_scopes(
        self, options, date_from, date_to, snapshot=False,
        max_periods=None,
    ):
        """Return deterministic ordered current/comparison period scopes.

        ``snapshot`` is metadata for balance-style consumers.  Shifted range
        boundaries remain explicit; snapshot handlers keep their cumulative
        SQL semantics and use each scope's ``date_to`` as as-of date.
        """
        options = options or {}
        try:
            date_from = fields.Date.to_date(date_from)
            date_to = fields.Date.to_date(date_to)
        except (TypeError, ValueError) as exc:
            raise UserError(_("Report dates must use YYYY-MM-DD.")) from exc
        if not date_from or not date_to or date_from > date_to:
            raise UserError(_("Report From date cannot be after To date."))

        limit = _EH_MAX_COMPARISON_PERIODS
        if max_periods is not None:
            limit = min(limit, int(max_periods))
        comparison = options.get('comparison') or 'none'
        if comparison not in (
            'none', 'previous_period', 'previous_year', 'custom',
        ):
            raise UserError(_(
                "Unsupported comparison mode %(mode)s.",
                mode=comparison,
            ))
        number = self._eh_normalize_comparison_number(
            options.get('comparison_number', 1),
        )
        if comparison == 'custom':
            number = 1
        if number > limit:
            raise UserError(_(
                "Reports support at most %(maximum)s comparison periods.",
                maximum=limit,
            ))

        company_ids = self._eh_normalize_id_set(
            options.get('company_ids') or [self.env.company.id],
            'company_ids',
        )

        def make_scope(key, label, role, range_from, range_to, index):
            return {
                'key': key,
                'label': label,
                'role': role,
                'date_from': self._iso_date(range_from),
                'date_to': self._iso_date(range_to),
                'company_ids': company_ids,
                'comparison_index': index,
                'is_current': index == 0,
                'snapshot': bool(snapshot),
            }

        current_label = (
            _("As of %(date)s", date=self._iso_date(date_to))
            if snapshot else _(
                "%(date_from)s to %(date_to)s",
                date_from=self._iso_date(date_from),
                date_to=self._iso_date(date_to),
            )
        )
        periods = [make_scope(
            'period_current', current_label, 'current',
            date_from, date_to, 0,
        )]
        order = options.get('comparison_order', 'descending')
        if order not in ('ascending', 'descending'):
            raise UserError(_(
                "Comparison order must be ascending or descending."
            ))
        if comparison == 'custom':
            custom_from = options.get('comparison_custom_date_from')
            custom_to = options.get('comparison_custom_date_to')
            if not custom_from or not custom_to:
                raise UserError(_(
                    "Custom comparison requires both From and To dates."
                ))
            custom_from = fields.Date.to_date(custom_from)
            custom_to = fields.Date.to_date(custom_to)
            if custom_from > custom_to:
                raise UserError(_(
                    "Custom comparison From date cannot be after To date."
                ))
            custom_label = (
                _("As of %(date)s", date=self._iso_date(custom_to))
                if snapshot else _(
                    "%(date_from)s to %(date_to)s",
                    date_from=self._iso_date(custom_from),
                    date_to=self._iso_date(custom_to),
                )
            )
            periods.append(make_scope(
                'period_comparison_1', custom_label, 'comparison',
                custom_from, custom_to, 1,
            ))
        elif comparison in ('previous_period', 'previous_year'):
            cursor_from, cursor_to = date_from, date_to
            for index in range(1, number + 1):
                prior_from, prior_to, _label = (
                    self._eh_resolve_comparison_dates(
                        comparison, cursor_from, cursor_to,
                    )
                )
                if not prior_from or not prior_to:
                    break
                prior_label = (
                    _("As of %(date)s", date=self._iso_date(prior_to))
                    if snapshot else _(
                        "%(date_from)s to %(date_to)s",
                        date_from=self._iso_date(prior_from),
                        date_to=self._iso_date(prior_to),
                    )
                )
                periods.append(make_scope(
                    'period_comparison_%d' % index,
                    prior_label, 'comparison',
                    prior_from, prior_to, index,
                ))
                cursor_from, cursor_to = prior_from, prior_to

        if order == 'ascending':
            periods.reverse()
        return periods

    @api.model
    def _eh_resolve_analytic_column_scopes(
        self, options, company_ids, max_groups=None,
    ):
        """Resolve horizontal analytic groups under caller ACL, never sudo.

        Account groups reject company-incompatible records.  A selected plan
        includes visible accounts on itself and descendants, limited to
        selected companies (or shared accounts).  Expanded account IDs travel
        with plan scope so SQL, exports, and drilldown use identical members.
        """
        options = options or {}
        company_ids = self._eh_normalize_id_set(
            company_ids, 'company_ids',
        )
        companies = self.env['res.company'].browse(company_ids).exists()
        if set(companies.ids) != set(company_ids):
            raise UserError(_(
                "One or more selected companies no longer exist."
            ))
        companies._eh_check_access('read')
        compatible_company_ids = set(company_ids)
        if 'parent_path' in companies._fields:
            for company in companies:
                compatible_company_ids.update(
                    int(ancestor_id)
                    for ancestor_id in (company.parent_path or '').split('/')
                    if ancestor_id
                )
        account_ids = self._eh_normalize_id_set(
            options.get('analytic_column_account_ids'),
            'analytic_column_account_ids',
        )
        plan_ids = self._eh_normalize_id_set(
            options.get('analytic_column_plan_ids'),
            'analytic_column_plan_ids',
        )
        limit = _EH_MAX_ANALYTIC_COLUMN_GROUPS
        if max_groups is not None:
            limit = min(limit, int(max_groups))
        if len(account_ids) + len(plan_ids) > limit:
            raise UserError(_(
                "Reports support at most %(maximum)s analytic column groups.",
                maximum=limit,
            ))
        if not account_ids and not plan_ids:
            return []

        Analytic = self.env['account.analytic.account'].with_context(
            active_test=False,
        )
        Plan = self.env['account.analytic.plan'].with_context(
            active_test=False,
        )

        def check_read_access(records):
            # Compatibility API exists on every supported Odoo 16-19 series.
            # Both calls use caller env; neither elevates through sudo.
            records._eh_check_access('read')

        scopes = []
        if account_ids:
            accounts = Analytic.browse(account_ids).exists()
            if set(accounts.ids) != set(account_ids):
                raise UserError(_(
                    "One or more selected analytic accounts no longer exist."
                ))
            check_read_access(accounts)
            incompatible = accounts.filtered(
                lambda account: (
                    account.company_id
                    and account.company_id.id not in compatible_company_ids
                )
            )
            if incompatible:
                raise UserError(_(
                    "Analytic account %(account)s is outside selected "
                    "company scope.",
                    account=incompatible[0].display_name,
                ))
            by_id = {account.id: account for account in accounts}
            for account_id in account_ids:
                account = by_id[account_id]
                scopes.append({
                    'key': 'analytic_account_%d' % account.id,
                    'label': account.display_name,
                    'analytic_account_ids': [account.id],
                    'analytic_plan_ids': [],
                    'company_ids': company_ids,
                    'is_total': False,
                })

        if plan_ids:
            plans = Plan.browse(plan_ids).exists()
            if set(plans.ids) != set(plan_ids):
                raise UserError(_(
                    "One or more selected analytic plans no longer exist."
                ))
            check_read_access(plans)
            if 'company_id' in Plan._fields:
                incompatible_plans = plans.filtered(
                    lambda plan: (
                        plan.company_id
                        and plan.company_id.id not in compatible_company_ids
                    )
                )
                if incompatible_plans:
                    raise UserError(_(
                        "Analytic plan %(plan)s is outside selected company "
                        "scope.",
                        plan=incompatible_plans[0].display_name,
                    ))
            by_id = {plan.id: plan for plan in plans}
            for plan_id in plan_ids:
                plan = by_id[plan_id]
                descendants = Plan.search([
                    ('id', 'child_of', plan.id),
                ], order='id')
                check_read_access(descendants)
                plan_accounts = Analytic.search([
                    ('plan_id', 'in', descendants.ids),
                    '|',
                    ('company_id', '=', False),
                    ('company_id', 'in', sorted(compatible_company_ids)),
                ], order='id')
                check_read_access(plan_accounts)
                scopes.append({
                    'key': 'analytic_plan_%d' % plan.id,
                    'label': plan.display_name,
                    'analytic_account_ids': plan_accounts.ids,
                    'analytic_plan_ids': [plan.id],
                    'company_ids': company_ids,
                    'is_total': False,
                })
        return scopes

    @api.model
    def _eh_build_value_scopes(
        self, periods, analytics, include_total=True, max_columns=None,
    ):
        """Build deterministic period x analytic scopes for independent SQL.

        When analytic groups exist, each period receives a separate baseline
        Total scope with empty column-analytic selectors.  Consumers must
        compute this scope independently: overlapping analytic groups and
        unallocated journal items make summing visible slices incorrect.
        """
        periods = list(periods or [])
        analytics = list(analytics or [])
        if not periods:
            return []
        limit = _EH_MAX_VALUE_COLUMNS
        if max_columns is not None:
            limit = min(limit, int(max_columns))
        analytic_axis = list(analytics)
        if analytics and include_total:
            analytic_axis.append({
                'key': 'analytic_total',
                'label': _("Total"),
                'analytic_account_ids': [],
                'analytic_plan_ids': [],
                'is_total': True,
            })
        cardinality = len(periods) * (len(analytic_axis) or 1)
        if cardinality > limit:
            raise UserError(_(
                "Report column selection produces %(count)s value columns; "
                "maximum is %(maximum)s.",
                count=cardinality,
                maximum=limit,
            ))

        values = []
        for period in periods:
            groups = analytic_axis or [None]
            for analytic in groups:
                public_scope = {
                    # Snapshot figures are cumulative.  Keep shifted
                    # period.date_from for labels/comparison metadata, but
                    # expose truthful drilldown/compute scope from epoch.
                    'date_from': (
                        '0001-01-01'
                        if period.get('snapshot')
                        else period['date_from']
                    ),
                    'date_to': period['date_to'],
                    'company_ids': list(period.get('company_ids') or []),
                    'comparison_index': int(
                        period.get('comparison_index') or 0,
                    ),
                    'is_total': bool(analytic and analytic.get('is_total')),
                }
                analytic_key = None
                analytic_label = ''
                if analytic is not None:
                    analytic_key = analytic['key']
                    analytic_label = analytic['label']
                    public_scope['analytic_account_ids'] = list(
                        analytic.get('analytic_account_ids') or [],
                    )
                    public_scope['analytic_plan_ids'] = list(
                        analytic.get('analytic_plan_ids') or [],
                    )
                key_parts = ['amount', period['key']]
                if analytic_key:
                    key_parts.append(analytic_key)
                key = '__'.join(key_parts)
                label = (
                    "%s — %s" % (period['label'], analytic_label)
                    if analytic_label and len(periods) > 1
                    else (analytic_label or period['label'])
                )
                values.append({
                    'key': key,
                    'label': label,
                    'period_key': period['key'],
                    'period_label': period['label'],
                    'analytic_key': analytic_key,
                    'analytic_label': analytic_label,
                    'role': period.get('role') or 'current',
                    'is_total': public_scope['is_total'],
                    'scope': public_scope,
                })
        return values

    @api.model
    def _eh_scope_options(self, options, value_scope):
        """Overlay one value scope without clobbering global row filters."""
        scoped = dict(options or {})
        value_scope = value_scope or {}
        public_scope = value_scope.get('scope') or value_scope
        date_block = dict(scoped.get('date') or {})
        if public_scope.get('date_from'):
            date_block['date_from'] = public_scope['date_from']
            date_block['date_to'] = public_scope['date_to']
        scoped['date'] = date_block
        if 'company_ids' in public_scope:
            scoped['company_ids'] = list(public_scope['company_ids'])
            if scoped.get('primary_company_id') not in scoped['company_ids']:
                scoped['primary_company_id'] = (
                    scoped['company_ids'][0]
                    if scoped['company_ids'] else False
                )

        has_analytic_scope = (
            'analytic_account_ids' in public_scope
            or 'analytic_plan_ids' in public_scope
        )
        if has_analytic_scope:
            scoped['_eh_analytic_column_active'] = True
            scoped['_eh_analytic_column_account_ids'] = list(
                public_scope.get('analytic_account_ids') or [],
            )
            scoped['_eh_analytic_column_plan_ids'] = list(
                public_scope.get('analytic_plan_ids') or [],
            )
            scoped['_eh_analytic_column_is_total'] = bool(
                public_scope.get('is_total'),
            )
        else:
            scoped.pop('_eh_analytic_column_active', None)
            scoped.pop('_eh_analytic_column_account_ids', None)
            scoped.pop('_eh_analytic_column_plan_ids', None)
            scoped.pop('_eh_analytic_column_is_total', None)
        # Scoped compute is terminal, never another axis expansion.
        scoped['analytic_column_account_ids'] = []
        scoped['analytic_column_plan_ids'] = []
        scoped['comparison'] = 'none'
        scoped['comparison_number'] = 1
        scoped['comparison_order'] = 'descending'
        scoped['comparison_custom_date_from'] = ''
        scoped['comparison_custom_date_to'] = ''
        # Per-scope builders feed one merged multi-column payload.  Their
        # individual single-value leaves must never advertise lazy expansion,
        # which cannot reconstruct every sibling scope on demand.
        scoped['lazy_expand'] = False
        return scoped

    @api.model
    def _eh_build_scope_column_layout(
        self, value_scopes, label_name=None,
    ):
        """Build flat authoritative columns carrying exact scope metadata."""
        columns = [{
            'expression_label': 'account',
            'name': label_name if label_name is not None else _("Account"),
            'figure_type': 'string',
        }]
        for value_scope in value_scopes or []:
            columns.append({
                'expression_label': value_scope['key'],
                'name': value_scope['label'],
                'figure_type': 'monetary',
                'scope': dict(value_scope['scope']),
            })
        return columns

    @staticmethod
    def _eh_first_line_value(line):
        columns = (line or {}).get('columns') or []
        return columns[0].get('value') or 0.0 if columns else 0.0

    @api.model
    @api.private
    def merge_scoped_results(
        self, scoped_results, options=None, presentation_converted=False,
        currency=None, total_key='amount',
    ):
        """Merge independently computed scope results into aligned rows.

        ``scoped_results`` items carry ``scope``, ``lines``, and ``totals``.
        Every cell, including analytic Total, comes from its own supplied
        result.  No selected slice is summed to manufacture a baseline.
        """
        scoped_results = list(scoped_results or [])
        currency = currency or self._eh_monetary_currency(
            options=options,
            company_ids=(options or {}).get('company_ids'),
            presentation_converted=presentation_converted,
        )
        maps = [
            {
                line['id']: line
                for line in (result.get('lines') or [])
            }
            for result in scoped_results
        ]
        ordered_ids = []
        templates = {}
        for result in scoped_results:
            result_lines = result.get('lines') or []
            result_ids = [line['id'] for line in result_lines]
            for position, line in enumerate(result_lines):
                line_id = line['id']
                if line_id in templates:
                    continue
                templates[line_id] = line
                # Insert before nearest following line already present. This
                # keeps a prior-only account inside its section (before that
                # section's known total), instead of appending after report
                # grand totals and breaking hierarchy/fold order.
                following = next((
                    candidate
                    for candidate in result_ids[position + 1:]
                    if candidate in ordered_ids
                ), None)
                if following is not None:
                    ordered_ids.insert(
                        ordered_ids.index(following), line_id,
                    )
                    continue
                preceding = next((
                    candidate
                    for candidate in reversed(result_ids[:position])
                    if candidate in ordered_ids
                ), None)
                if preceding is not None:
                    ordered_ids.insert(
                        ordered_ids.index(preceding) + 1, line_id,
                    )
                else:
                    ordered_ids.append(line_id)

        merged = []
        for line_id in ordered_ids:
            row = dict(templates[line_id])
            row['columns'] = []
            for result, line_map in zip(scoped_results, maps):
                value_scope = result['scope']
                value = self._eh_first_line_value(line_map.get(line_id))
                row['columns'].append({
                    'expression_label': value_scope['key'],
                    'value': self._eh_round_monetary(
                        value, currency=currency,
                    ),
                    'scope': dict(value_scope['scope']),
                })
            merged.append(row)

        totals = {}
        for result in scoped_results:
            value_scope = result['scope']
            source_totals = result.get('totals')
            if isinstance(source_totals, dict):
                value = source_totals.get(total_key, 0.0)
            else:
                value = source_totals or 0.0
            totals[value_scope['key']] = self._eh_round_monetary(
                value or 0.0, currency=currency,
            )
        return {'lines': merged, 'totals': totals}

    @api.model
    @api.private
    def compute(self, options):
        """Compute the report data.

        Returns a dict with keys:

        * columns: list of dicts with name, expression_label, figure_type
          (string, monetary, percentage, integer, float, date, boolean).
        * lines: list of dicts with id, name, level, columns (list of value
          dicts), unfoldable (bool), parent_id (optional), meta (optional).
        * totals: optional dict mapping expression_label to summary value.
        * generated_at: ISO datetime string.
        """
        raise NotImplementedError(
            "Concrete handlers must override compute(options)."
        )

    @api.model
    @api.private
    def resolve_currency_info(self, options):
        """Resolve the currency block to attach to a report payload.

        When a single company is in scope, the company's currency is the
        report currency; when multiple companies share the same currency,
        the same applies. When the scope spans companies with different
        currencies the report cannot be expressed in a single currency
        without conversion, so we mark the payload as multi_currency and
        leave amount formatting to use no symbol.

        Returns a dict with keys: id, name, symbol, position, decimal_places,
        multi_currency.
        """
        company_ids = (
            options.get('company_ids')
            or list(self.env.context.get(
                'allowed_company_ids', [self.env.company.id],
            ))
        )
        companies = self.env['res.company'].sudo().browse(company_ids)
        currencies = companies.mapped('currency_id')
        unique = currencies.filtered(lambda c: c)
        if len(unique) <= 1 and unique:
            currency = unique[:1]
            return {
                'id': currency.id,
                'name': currency.name,
                'symbol': currency.symbol,
                'position': currency.position,
                'decimal_places': currency.decimal_places,
                'multi_currency': False,
            }
        return {
            'id': False,
            'name': '',
            'symbol': '',
            'position': 'after',
            'decimal_places': 2,
            'multi_currency': True,
        }

    @api.model
    def _eh_monetary_currency(
        self, options=None, company_ids=None, presentation_converted=False,
    ):
        """Resolve currency owning numeric precision for one payload.

        Raw handlers round in ledger currency. Handlers which already
        converted SQL aggregates pass ``presentation_converted=True`` and
        round in requested presentation currency. Mixed raw-currency scopes
        are rejected later by orchestrator, so first company is only used for
        same-currency scopes.
        """
        options = options or {}
        Currency = self.env['res.currency']
        # Lazy expansion resolves this once per page, then passes only the
        # trusted transient ID to every row projection.  Avoids an ORM
        # existence lookup for each journal item without mutating/caching the
        # caller's canonical report options.
        internal_currency_id = options.get(
            '_eh_internal_monetary_currency_id',
        )
        if internal_currency_id:
            try:
                return Currency.browse(int(internal_currency_id))
            except (TypeError, ValueError, OverflowError):
                pass
        if presentation_converted and options.get(
                'presentation_currency_id'):
            try:
                currency = Currency.browse(
                    int(options['presentation_currency_id']),
                ).exists()
            except (TypeError, ValueError, OverflowError):
                currency = Currency
            if currency:
                return currency[:1]
        raw_company_ids = (
            company_ids
            or options.get('company_ids')
            or self.env.context.get('allowed_company_ids')
            or [self.env.company.id]
        )
        try:
            normalized_company_ids = [
                int(company_id) for company_id in raw_company_ids
            ]
        except (TypeError, ValueError, OverflowError):
            normalized_company_ids = [self.env.company.id]
        primary_company_id = options.get('primary_company_id')
        try:
            primary_company_id = int(primary_company_id or 0)
        except (TypeError, ValueError, OverflowError):
            primary_company_id = 0
        if primary_company_id not in normalized_company_ids:
            primary_company_id = normalized_company_ids[0]
        company = self.env['res.company'].browse(
            primary_company_id,
        ).exists()
        return (company or self.env.company).currency_id

    @api.model
    def _eh_round_monetary(
        self, value, options=None, company_ids=None,
        presentation_converted=False, currency=None,
    ):
        """Round monetary value with currency precision, never fixed 2dp."""
        currency = currency or self._eh_monetary_currency(
            options=options,
            company_ids=company_ids,
            presentation_converted=presentation_converted,
        )
        return currency.round(value) if currency else value

    @api.model
    def _eh_is_zero_monetary(
        self, value, options=None, company_ids=None,
        presentation_converted=False, currency=None,
    ):
        """Currency-aware zero check paired with `_eh_round_monetary`."""
        currency = currency or self._eh_monetary_currency(
            options=options,
            company_ids=company_ids,
            presentation_converted=presentation_converted,
        )
        return currency.is_zero(value) if currency else not value

    @api.model
    @api.private
    def apply_common_filters(self, query, options):
        """Apply the standard option filters (journal_ids, partner_ids,
        account_ids, account_type_ids, analytic_account_ids,
        analytic_plan_ids) to a
        MoveLineQuery. Centralised so adding a new dimension lands in one
        place instead of every concrete handler.
        """
        if options.get('journal_ids'):
            query.where_journals(options['journal_ids'])
        if options.get('partner_ids'):
            query.where_partners(options['partner_ids'])
        if options.get('account_ids'):
            query.where_accounts(options['account_ids'])
        if options.get('account_type_ids'):
            query.where_account_types(options['account_type_ids'])
        if options.get('analytic_account_ids'):
            query.where_analytic_accounts(options['analytic_account_ids'])
        if options.get('analytic_plan_ids'):
            query.where_analytic_plans(options['analytic_plan_ids'])
        if options.get('_eh_analytic_column_active') and not options.get(
                '_eh_analytic_column_is_total'):
            # Column allocation is a second dimension.  Global analytic
            # filters above keep their row-membership predicate; this scope
            # adds an intersecting predicate and owns monetary allocation.
            column_account_ids = options.get(
                '_eh_analytic_column_account_ids',
            )
            column_plan_ids = options.get(
                '_eh_analytic_column_plan_ids',
            )
            if column_account_ids is not None:
                query.where_analytic_column_accounts(
                    column_account_ids,
                    require_match=True,
                )
            elif column_plan_ids is not None:
                query.where_analytic_column_plans(
                    column_plan_ids,
                    require_match=True,
                )
        return query

    # ---- fiscal-year + multi-currency consolidation (WS4) ----

    @api.model
    def _resolve_currency_table(
        self, options, company_ids, as_of_date=None,
    ):
        """Build the CurrencyTable for a consolidated report run.

        A table is built only when options['presentation_currency_id'] is
        explicit. Without that option, mixed company currencies remain marked
        as mixed instead of being silently restated. The table is seeded as of
        explicit ``as_of_date`` or report date_to (spot-rate-as-of-close
        consolidation). In the common
        own-currency case it reports is_monocurrency True and threads through
        MoveLineQuery with zero SQL effect, so the hot path is unchanged.

        Requested conversion fails closed when no valid target-currency rate
        exists on or before that date. Validation happens here, before any
        report SQL or conversion metadata can claim translated numbers.
        """
        options = options or {}
        try:
            company_ids = [
                int(c) for c in (company_ids or [self.env.company.id])
            ]
        except (TypeError, ValueError):  # pragma: no cover - defensive
            company_ids = [self.env.company.id]
        presentation_currency_id = options.get('presentation_currency_id')
        if not presentation_currency_id:
            return None
        try:
            presentation_currency_id = int(presentation_currency_id)
        except (TypeError, ValueError):
            return None
        if not self.env['res.currency'].browse(
                presentation_currency_id).exists():
            return None
        if as_of_date is None:
            try:
                as_of_date = self._extract_date(options, 'date_to')
            except UserError:
                as_of_date = fields.Date.context_today(self)
        elif isinstance(as_of_date, str):
            as_of_date = fields.Date.to_date(as_of_date)
        currency_table = CurrencyTable(
            self.env,
            company_ids=company_ids,
            presentation_currency_id=presentation_currency_id,
            as_of_date=as_of_date,
        )
        if not currency_table.is_monocurrency:
            currency_table.rate_map
        return currency_table

    @api.model
    def _presentation_currency_meta(self, currency_table):
        """Payload contract proving handler already owns monetary conversion.

        Orchestrator checks ``presentation_currency_converted`` before its
        legacy whole-payload converter. This prevents double conversion while
        retaining central currency formatting. Closing-spot policy, as-of
        date, and actual target-rate dates remain explicit in payload meta.
        """
        if currency_table is None:
            return {}
        meta = {
            'presentation_currency_converted': True,
            'presentation_currency_id': (
                currency_table.presentation_currency_id),
            'multi_currency': not currency_table.is_monocurrency,
        }
        meta.update(currency_table.translation_metadata())
        return meta

    @api.model
    def _fiscalyear_start_for(self, company, date):
        """Return the first day of the fiscal year of `company` containing
        `date`.

        Wraps res.company.compute_fiscalyear_dates so GL, TB and the
        sectioned reports share one fiscal-year resolution. Honours a
        staggered (non-calendar) fiscal year automatically because the core
        helper already handles fiscalyear_last_day / fiscalyear_last_month.

        FALLBACK: if the company has no usable fiscal-year configuration, or
        the core helper raises, degrade to the calendar-year start
        (1 January of `date`'s year) rather than raising. A missing fiscal
        year must never break a report.
        """
        try:
            company = company.sudo()
            company.ensure_one()
            fy = company.compute_fiscalyear_dates(date)
            start = fy.get('date_from')
            if start is not None:
                return start
        except Exception:  # pragma: no cover - defensive
            pass
        # Calendar-year fallback.
        try:
            return date.replace(month=1, day=1)
        except Exception:  # pragma: no cover - defensive
            return date

    @api.model
    def _fiscalyear_starts(self, company_ids, date):
        """Map {company_id: fiscal_year_start_date} for `date`.

        O(companies) Python calls, each yielding at most one start date, so
        callers can bind them as a small CASE keyed on aml.company_id rather
        than issuing a query per company. Degrades per company to the
        calendar-year start via _fiscalyear_start_for.
        """
        starts = {}
        companies = self.env['res.company'].sudo().browse([
            int(c) for c in (company_ids or [])
        ])
        for company in companies:
            starts[company.id] = self._fiscalyear_start_for(company, date)
        return starts

    @api.model
    def _fiscalyear_start_case(self, fy_starts, default_date):
        """SQL CASE mapping aml.company_id -> that company's fiscal-year start.

        O(companies) bound constants, not O(rows), so the fiscal-year split
        stays a single SQL pass even when consolidated companies run on
        different fiscal calendars. A company absent from the map (should not
        happen) falls back to default_date (the report's date_from), which
        collapses its P&L current-FY-to-date contribution to zero rather than
        mis-rolling. Shared on the base so GL, TB and later sectioned reports
        bind the identical expression.
        """
        if not fy_starts:
            return SQL("%s::date", default_date)
        whens = []
        for company_id, start in fy_starts.items():
            whens.append(
                SQL("WHEN %s THEN %s::date", int(company_id), start))
        return SQL(
            "CASE aml.company_id %s ELSE %s::date END",
            SQL(" ").join(whens), default_date,
        )

    @api.model
    @api.private
    def get_drilldown_action(self, options, line_id):
        """Default drill down: open filtered journal items when line_id is
        of the form 'account-N'. Concrete handlers override only when their
        line_id scheme differs or when they want to disable drill down.
        """
        # A native account.move.line domain cannot represent weighted
        # analytic_distribution allocation.  Opening gross journal items for
        # a 60% cell is materially false.  Fail closed until a handler owns a
        # dedicated weighted drilldown RPC/action.  An independent analytic
        # Total with no global analytic filter remains a gross-ledger scope
        # and may use this ordinary action.
        global_analytic = bool(
            options.get('analytic_account_ids')
            or options.get('analytic_plan_ids')
        )
        column_account_ids = options.get(
            '_eh_analytic_column_account_ids',
        )
        column_plan_ids = options.get(
            '_eh_analytic_column_plan_ids',
        )
        column_analytic = bool(column_account_ids or column_plan_ids)
        if global_analytic or column_analytic:
            return None
        if not line_id or not isinstance(line_id, str):
            return None
        if not line_id.startswith('account-'):
            return None
        try:
            account_id = int(line_id.split('-', 1)[1])
        except ValueError:
            return None
        try:
            date_from = self._extract_date(options, 'date_from')
            date_to = self._extract_date(options, 'date_to')
        except UserError:
            return None
        company_ids = options.get('company_ids') or [self.env.company.id]
        domain = [
            ('account_id', '=', account_id),
            ('company_id', 'in', list(company_ids)),
            ('date', '>=', self._iso_date(date_from)),
            ('date', '<=', self._iso_date(date_to)),
        ]
        if options.get('posted_only', True):
            # Follow the authoritative move, not account.move.line's stored
            # projection (which can contain pre-control legacy drift).
            domain.append(('move_id.state', '=', 'posted'))
        # Audit-cell fidelity: fold the same journal / partner filters the
        # report applied so the opened journal items reconstruct exactly
        # the figure in the cell, not a broader account total.
        domain += self._eh_drilldown_filter_domain(options)
        return {
            'type': 'ir.actions.act_window',
            'name': _("Journal Items"),
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': domain,
            'context': {'search_default_group_move': 1},
        }

    @api.model
    def _eh_drilldown_filter_domain(self, options):
        """Domain fragments mirroring the report's common filters, so a
        drilldown matches the filtered cell. Journal, partner, and account
        type filters translate cleanly to an account.move.line domain; analytic
        filters are left to the SQL path (their distribution match does
        not express as a simple domain). ``get_drilldown_action`` therefore
        fails closed for those scopes instead of returning gross rows."""
        extra = []
        journal_ids = options.get('journal_ids')
        if journal_ids:
            extra.append(('journal_id', 'in', list(journal_ids)))
        partner_ids = options.get('partner_ids')
        if partner_ids:
            extra.append(('partner_id', 'in', list(partner_ids)))
        account_type_ids = options.get('account_type_ids')
        if account_type_ids:
            extra.append((
                'account_id.account_type',
                'in',
                list(account_type_ids),
            ))
        return extra

    # ---- lazy expand engine (Wave 0 / Part A engine contract) ----

    @api.model
    def _resolve_expand_page_size(self, options):
        """Default page size for a lazy expand page.

        Reads res.company.eh_expand_page_size (Integer, default 80);
        options['expand_page_size'] overrides when present and valid.
        Mirrors the GL _resolve_row_limit shape. Degrades to a safe
        constant if the company field is absent (older schema) so the
        engine never raises here.
        """
        try:
            company_default = int(
                self.env.company.eh_expand_page_size or 80,
            )
        except Exception:  # pragma: no cover - schema fallback
            company_default = 80
        company_default = max(
            1, min(company_default, self._MAX_EXPAND_PAGE_SIZE),
        )
        requested = options.get('expand_page_size')
        if requested is None:
            return company_default
        try:
            requested = int(requested)
        except (TypeError, ValueError, OverflowError):
            return company_default
        if requested <= 0:
            return company_default
        return min(requested, self._MAX_EXPAND_PAGE_SIZE)

    @api.model
    def _account_line_is_expandable(self, line):
        """Decide whether an account leaf is a lazy-expandable line.

        Returns True for an account leaf (a line carrying
        meta.account_id) in a single-current-period mode. Returns False
        in any multi-column mode (comparison / N-period / horizontal
        pivot) because a single journal item cannot fill the prior /
        group / total columns, which would mis-align the positional
        column slicing on the client.

        The mode is read from the line's own options snapshot when the
        caller stashes one in meta['_expand_options']; otherwise the
        decision is made purely on the presence of meta.account_id and
        callers gate the multi-column case before constructing the leaf.
        """
        meta = (line or {}).get('meta') or {}
        if not meta.get('account_id'):
            return False
        opts = meta.get('_expand_options') or {}
        if self._eh_options_are_multi_column(opts):
            return False
        return True

    @api.model
    def _eh_options_are_multi_column(self, options):
        """True when options describe a layout a single aml cannot fill."""
        options = options or {}
        comparison = options.get('comparison') or 'none'
        number = self._eh_normalize_comparison_number(
            options.get('comparison_number', 1),
        )
        if comparison and comparison != 'none':
            return True
        if number > 1:
            return True
        if options.get('horizontal_group_by'):
            return True
        return False

    @api.model
    def _eh_apply_leaf_lazy_flags(self, line, options):
        """Stamp the lazy/unfoldable flags on an account leaf in place.

        Backward compatible on two axes:

        1. The lazy path is opt-in via options['lazy_expand'] (set by the
           OWL viewer). Without it the leaf keeps its legacy
           unfoldable: False shape, so direct compute() callers, export,
           and the existing test suite see byte-identical leaves.
        2. Even with the flag, a non-expandable leaf (multi-column mode,
           or no account_id) keeps unfoldable: False.
        """
        options = options or {}
        if not options.get('lazy_expand') or options.get('eager_expand'):
            return line
        meta = line.setdefault('meta', {})
        meta['_expand_options'] = options or {}
        expandable = self._account_line_is_expandable(line)
        # The transient options snapshot must not leak into the payload
        # (it bloats the cache key surface and is not serialisable-stable).
        meta.pop('_expand_options', None)
        if expandable:
            line['unfoldable'] = True
            line['unfolded'] = False
            line['lazy'] = True
            line['has_more'] = False
            meta['expandable'] = True
        return line

    @api.model
    def _expand_account_id_from_line_id(self, line_id):
        """Parse 'account-N' into N. Returns None on any other shape."""
        if not line_id or not isinstance(line_id, str):
            return None
        if not line_id.startswith('account-'):
            return None
        tail = line_id.split('-', 1)[1]
        try:
            return int(tail)
        except (ValueError, TypeError):
            return None

    @api.model
    def _expand_build_page_query(
        self, options, account_id, date_from, date_to, currency_table=None,
    ):
        """Build the MoveLineQuery for one account's journal-item page.

        Reuses apply_common_filters and the report's [date_from, date_to]
        window so the page reconstructs EXACTLY the figure in the parent
        cell. Returns a query with all the columns _expand_child_columns
        may read; callers add offset/limit/order.
        """
        company_ids = options.get('company_ids') or [self.env.company.id]
        posted_only = bool(options.get('posted_only', True))
        currency_table = currency_table or self._resolve_currency_table(
            options, company_ids, as_of_date=date_to,
        )
        query = MoveLineQuery(
            self.env, company_ids=company_ids,
            currency_table=currency_table,
        )
        query.where_date_range(date_from=date_from, date_to=date_to)
        query.where_accounts([account_id])
        if posted_only:
            query.where_posted_only()
        self.apply_common_filters(query, options)
        return query

    @api.model
    def _expand_select_columns(self, query):
        """Add the canonical aml column projection to an expand query."""
        query.select_field('id', alias='aml_id')
        query.select_field('account_id')
        query.select_field('partner_id')
        query.select_field('date')
        query.select_debit_converted()
        query.select_credit_converted()
        query.select_balance_converted()
        query.select_field('amount_currency')
        query.select_field('currency_id')
        query.select_field('name', alias='line_label')
        query.select_field('ref')
        query.join_journal()
        query.select(SQL("aj.code"), 'journal_code')
        query.join_partner()
        query.select(SQL("p.name"), 'partner_name')
        query.select(SQL("am.name"), 'move_name')
        return query

    @api.model
    @api.private
    def expand_account_line(self, options, line_id, offset=0, limit=None):
        """Shared server engine: fetch one account's journal-item page.

        Returns {child_lines, has_more, next_offset, total_count}.

        Parses 'account-N', builds a single-account MoveLineQuery over the
        report window with the report's common filters applied (so the page
        reconciles exactly to the cell), runs a count-only pre-flight for
        total_count, then fetches a (limit + 1) page ordered by (date, id);
        the +1 row is the has-more probe and is dropped before mapping.
        Each fetched row is projected through _expand_child_columns.
        """
        try:
            offset = max(0, int(offset or 0))
        except (TypeError, ValueError, OverflowError):
            offset = 0
        empty = {
            'child_lines': [], 'has_more': False,
            'next_offset': offset, 'total_count': 0,
        }
        account_id = self._expand_account_id_from_line_id(line_id)
        if account_id is None:
            return empty
        try:
            date_from = self._extract_date(options, 'date_from')
            date_to = self._extract_date(options, 'date_to')
        except UserError:
            return empty

        if limit is None:
            limit = self._resolve_expand_page_size(options)
        try:
            limit = int(limit)
        except (TypeError, ValueError, OverflowError):
            limit = self._resolve_expand_page_size(options)
        if limit <= 0:
            limit = self._resolve_expand_page_size(options)
        limit = min(limit, self._MAX_EXPAND_PAGE_SIZE)

        company_ids = options.get('company_ids') or [self.env.company.id]
        currency_table = self._resolve_currency_table(
            options, company_ids, as_of_date=date_to,
        )

        # Count-only pre-flight: same filters, single COUNT.
        count_query = self._expand_build_page_query(
            options, account_id, date_from, date_to,
            currency_table=currency_table,
        )
        count_query.select_count(alias='row_count')
        count_rows = count_query.execute()
        total_count = int(count_rows[0]['row_count']) if count_rows else 0

        page_query = self._expand_build_page_query(
            options, account_id, date_from, date_to,
            currency_table=currency_table,
        )
        self._expand_select_columns(page_query)
        page_query.order_by('date', 'ASC')
        page_query.order_by('id', 'ASC')
        page_query.offset(offset)
        page_query.limit(limit + 1)
        rows = page_query.execute()

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]

        child_lines = []
        child_options = dict(options)
        rounding_currency = self._eh_monetary_currency(
            options=options,
            company_ids=options.get('company_ids'),
            presentation_converted=bool(
                options.get('presentation_currency_id'),
            ),
        )
        if rounding_currency:
            child_options['_eh_internal_monetary_currency_id'] = (
                rounding_currency.id
            )
        for aml_row in rows:
            child_lines.extend(
                self._expand_child_columns(child_options, aml_row),
            )

        return {
            'child_lines': child_lines,
            'has_more': has_more,
            'next_offset': offset + len(rows),
            'total_count': total_count,
            'presentation_currency_converted': bool(
                currency_table is not None
                and not currency_table.is_monocurrency
            ),
        }

    @api.model
    def _expand_child_columns(self, options, aml_row):
        """Per-report column projection for one fetched journal item.

        Base default: a single child line carrying date / move / partner /
        label and one signed amount in a 'balance' (fallback 'amount')
        column. Concrete handlers override to map onto the host report's
        own expression_labels. Returns a LIST of line dicts (one per aml
        in the base case) so an override may, in principle, emit several.
        """
        amount = self._eh_round_monetary(
            float(aml_row.get('balance') or 0.0),
            options=options,
            company_ids=options.get('company_ids'),
            presentation_converted=bool(
                options.get('presentation_currency_id'),
            ),
        )
        date_val = aml_row.get('date')
        return [{
            'id': "aml-%s" % aml_row.get('aml_id'),
            'name': aml_row.get('ref') or aml_row.get('line_label') or '',
            'level': 2,
            'columns': self._expand_default_columns(aml_row, amount),
            'unfoldable': False,
            'unfolded': False,
            'lazy': False,
            'meta': {
                'kind': 'aml',
                'aml_id': aml_row.get('aml_id'),
                'account_id': aml_row.get('account_id'),
                'date': self._iso_date(date_val) if date_val else None,
                'move': aml_row.get('move_name') or '',
                'partner': aml_row.get('partner_name') or '',
            },
        }]

    @api.model
    def _expand_default_columns(self, aml_row, amount):
        """Default single-amount column projection.

        Emits one cell per non-label column of the host report. Because the
        base default cannot know the host report's columns, it emits a
        single 'amount' cell; overrides replace this with the host layout.
        """
        return [{'expression_label': 'amount', 'value': amount}]

    # ---- shared helpers used by concrete handlers ----

    def _extract_date(self, options, key):
        """Pull options['date'][key] and return a Python date.

        Raises UserError if the date is missing. The error message includes
        the report's display name so the user can identify which report
        rejected the input.
        """
        date_block = options.get('date') or {}
        value = date_block.get(key)
        if not value:
            raise UserError(_(
                "%(report)s requires options['date'][%(key)s].",
                report=self.REPORT_NAME or "Report",
                key=repr(key),
            ))
        if isinstance(value, str):
            return fields.Date.from_string(value)
        return value

    @staticmethod
    def _iso_date(value):
        """Render a date or compatible value back to ISO format."""
        return value.isoformat() if hasattr(value, 'isoformat') else str(value)
