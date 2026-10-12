# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Intermediate handler base for section based reports.

Profit and Loss, Balance Sheet, and other "sections of accounts" reports
share the same shape:

* One or more sections, each containing a header line, one line per
  contributing account, and a section total.
* Per account aggregation comes from a single SQL pass per section,
  composed via MoveLineQuery.
* Optional aggregate scalars (Current Year Earnings on a Balance Sheet,
  for example) come from a smaller SQL pass with no group by.

Concrete handlers _inherit this model and call the helpers; they decide
which sections to render, how the totals roll up, and which line ids to
issue. Trial Balance and General Ledger do NOT inherit this base because
their layout differs.
"""

import hashlib
import hmac
import json
import math

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import SQL

from odoo.addons.eh_account_base.tools.sql_builder import MoveLineQuery


class EhAccountDynamicReportSectionedHandler(models.AbstractModel):
    _name = 'eh.account.dynamic.report.handler.sectioned'
    _inherit = 'eh.account.dynamic.report.handler'
    _description = "Base for section based dynamic report handlers"

    # Concrete handlers opt in only after every monetary path and payload
    # metadata path has adopted handler-owned presentation conversion. This
    # prevents partial conversion in older sectioned handlers that still rely
    # on the orchestrator's legacy whole-payload conversion.
    _EH_SQL_PRESENTATION_CURRENCY = False
    _EH_ANALYTIC_COLUMN_DRILLDOWN = False
    _EH_ANALYTIC_DRILLDOWN_SNAPSHOT = False
    _MAX_ANALYTIC_DRILLDOWN_ROWS = 20_000

    # ---- column layout ----
    #
    # Default labels are resolved with _() inside each method so they pick
    # up the active language at call time. Function-default expressions are
    # evaluated once at import time, so a literal default of "Description"
    # would freeze the English string. None signals "use the translated
    # default", and callers can still override with their own string.

    @api.model
    def _build_two_column_layout(self, label_name=None, amount_name=None):
        """Return the standard two column layout: label on the left,
        monetary amount on the right. Most section based reports use this.
        """
        return [
            {'expression_label': 'account',
             'name': label_name if label_name is not None else _("Description"),
             'figure_type': 'string'},
            {'expression_label': 'amount',
             'name': amount_name if amount_name is not None else _("Amount"),
             'figure_type': 'monetary'},
        ]

    @api.model
    def _build_comparative_column_layout(
        self, label_name=None, current_label=None,
        prior_label=None, variance_label=None,
        variance_pct_label=None,
    ):
        """Return the comparative four-column layout: label + current
        amount + prior amount + variance + variance %. Used when
        options['comparison'] is set.
        """
        return [
            {'expression_label': 'account',
             'name': label_name if label_name is not None else _("Description"),
             'figure_type': 'string'},
            {'expression_label': 'amount',
             'name': current_label if current_label is not None else _("Current"),
             'figure_type': 'monetary'},
            {'expression_label': 'prior_amount',
             'name': prior_label if prior_label is not None else _("Prior"),
             'figure_type': 'monetary'},
            {'expression_label': 'variance',
             'name': variance_label if variance_label is not None else _("Variance"),
             'figure_type': 'monetary'},
            {'expression_label': 'variance_pct',
             'name': variance_pct_label if variance_pct_label is not None else _("Var %"),
             'figure_type': 'percentage'},
        ]

    # ---- comparison helpers ----

    @api.model
    def _resolve_comparison_dates(self, mode, date_from, date_to):
        """Return (prior_from, prior_to, label) for a given comparison mode.

        Modes supported:
        * 'previous_period' shifts a complete calendar-month window by its
          number of months. Arbitrary partial windows retain equal-day
          semantics.
        * 'previous_year' shifts both ends back by one calendar year. A
          leap-day input (Feb 29) is shifted to Feb 28 of the prior year.

        Returns (None, None, '') for any other mode (no comparison).
        """
        return self._eh_resolve_comparison_dates(
            mode, date_from, date_to,
        )

    @staticmethod
    def _safe_pct(prior, current):
        """Variance percentage that does not divide by zero. Returns the
        difference as a fraction (1.0 = 100%) so the figure_type 'percentage'
        renders it correctly. With a zero prior, returns 1.0 if the current
        is non-zero (full overrun) and 0.0 otherwise.
        """
        if prior:
            return (current - prior) / abs(prior)
        if current:
            return 1.0
        return 0.0

    @api.model
    @api.private
    def merge_comparative_lines(
        self, current_lines, prior_lines, options=None,
        presentation_converted=False, currency=None,
    ):
        """Merge two single-amount line lists into multi-column lines.

        Both inputs are line lists as produced by the section helpers
        below; matching is by line.id. The output extends each current
        line's `columns` with the prior-period amount, the variance, and
        the variance percentage. Lines that exist in only one of the
        inputs receive zero on the missing side.
        """
        currency = currency or self._eh_monetary_currency(
            options=options,
            company_ids=(options or {}).get('company_ids'),
            presentation_converted=presentation_converted,
        )
        prior_by_id = {l['id']: l for l in prior_lines}
        merged = []
        seen = set()
        for cur in current_lines:
            seen.add(cur['id'])
            cur_amount = self._line_first_value(cur)
            prior = prior_by_id.get(cur['id'])
            prior_amount = self._line_first_value(prior) if prior else 0.0
            variance = self._eh_round_monetary(
                (cur_amount or 0.0) - (prior_amount or 0.0),
                currency=currency,
            )
            new_line = dict(cur)
            new_line['columns'] = [
                {'expression_label': 'amount', 'value': cur_amount},
                {'expression_label': 'prior_amount', 'value': prior_amount},
                {'expression_label': 'variance', 'value': variance},
                {'expression_label': 'variance_pct',
                 'value': self._safe_pct(prior_amount, cur_amount)},
            ]
            merged.append(new_line)
        # Lines that exist only in the prior period: emit them with a
        # zero current amount so the user sees that the activity has
        # ceased.
        for prior_id, prior in prior_by_id.items():
            if prior_id in seen:
                continue
            prior_amount = self._line_first_value(prior)
            new_line = dict(prior)
            new_line['columns'] = [
                {'expression_label': 'amount', 'value': 0.0},
                {'expression_label': 'prior_amount', 'value': prior_amount},
                {'expression_label': 'variance',
                 'value': self._eh_round_monetary(
                     -prior_amount, currency=currency)},
                {'expression_label': 'variance_pct', 'value': -1.0},
            ]
            merged.append(new_line)
        return merged

    @staticmethod
    def _line_first_value(line):
        if not line:
            return 0.0
        cols = line.get('columns') or []
        if not cols:
            return 0.0
        return cols[0].get('value') or 0.0

    # ---- N-period comparison ----

    @api.model
    def _resolve_comparison_periods(self, mode, date_from, date_to, number):
        """Return a list of (prior_from, prior_to, label) for `number`
        successive prior periods.

        Each period is the comparison of the one before it, so
        'previous_period' walks back window-by-window and 'previous_year'
        walks back year-by-year. Used for N-period side-by-side reports.
        """
        number = self._eh_normalize_comparison_number(number)
        periods = []
        cur_from, cur_to = date_from, date_to
        for index in range(max(0, number)):
            prior_from, prior_to, label = self._resolve_comparison_dates(
                mode, cur_from, cur_to)
            if not (prior_from and prior_to):
                break
            if number > 1:
                label = _("%(label)s -%(n)s", label=label, n=index + 1)
            periods.append((prior_from, prior_to, label))
            cur_from, cur_to = prior_from, prior_to
        return periods

    @api.model
    def _build_n_period_column_layout(self, current_label, period_labels):
        """Label column + the current amount + one amount column per prior
        period (prior_1, prior_2, ...)."""
        columns = [
            {'expression_label': 'account', 'name': _("Account"),
             'figure_type': 'string'},
            {'expression_label': 'amount',
             'name': current_label or _("Current"),
             'figure_type': 'monetary'},
        ]
        for idx, label in enumerate(period_labels, start=1):
            columns.append({
                'expression_label': 'prior_%d' % idx,
                'name': label, 'figure_type': 'monetary',
            })
        return columns

    @api.model
    @api.private
    def merge_n_period_lines(self, current_lines, prior_line_lists):
        """Merge the current line list with N prior line lists into rows
        carrying the current amount plus one amount per prior period.

        Matching is by line id. A line missing from a prior period shows
        zero for that period; a line that exists only in a prior period
        is appended with zero current.
        """
        prior_maps = [
            {l['id']: l for l in prior} for prior in prior_line_lists
        ]
        merged = []
        seen = set()
        for cur in current_lines:
            seen.add(cur['id'])
            new_line = dict(cur)
            cols = [{'expression_label': 'amount',
                     'value': self._line_first_value(cur)}]
            for idx, prior_map in enumerate(prior_maps, start=1):
                prior = prior_map.get(cur['id'])
                cols.append({
                    'expression_label': 'prior_%d' % idx,
                    'value': self._line_first_value(prior) if prior else 0.0,
                })
            new_line['columns'] = cols
            merged.append(new_line)
        # Lines present only in a prior period (rare but possible).
        for idx, prior_map in enumerate(prior_maps, start=1):
            for prior_id, prior in prior_map.items():
                if prior_id in seen:
                    continue
                seen.add(prior_id)
                cols = [{'expression_label': 'amount', 'value': 0.0}]
                for j, other_map in enumerate(prior_maps, start=1):
                    other = other_map.get(prior_id)
                    cols.append({
                        'expression_label': 'prior_%d' % j,
                        'value': (self._line_first_value(other)
                                  if other else 0.0),
                    })
                new_line = dict(prior)
                new_line['columns'] = cols
                merged.append(new_line)
        return merged

    # ---- horizontal column groups ----

    @api.model
    def _build_horizontal_column_layout(self, group_labels):
        """Label column + one amount column per group + a total column."""
        columns = [
            {'expression_label': 'account', 'name': _("Account"),
             'figure_type': 'string'},
        ]
        for idx, label in enumerate(group_labels, start=1):
            columns.append({
                'expression_label': 'group_%d' % idx,
                'name': label, 'figure_type': 'monetary'})
        columns.append({
            'expression_label': 'total', 'name': _("Total"),
            'figure_type': 'monetary'})
        return columns

    @api.model
    @api.private
    def merge_horizontal_groups(
        self, group_line_lists, options=None,
        presentation_converted=False, currency=None,
    ):
        """Pivot N independently-computed line lists side by side.

        Each line id becomes one row carrying one amount column per group
        (group_1..group_N) plus a row total. Row order follows the first
        group; lines appearing only in later groups are appended. A line
        missing from a group contributes zero to that group's column.
        """
        currency = currency or self._eh_monetary_currency(
            options=options,
            company_ids=(options or {}).get('company_ids'),
            presentation_converted=presentation_converted,
        )
        maps = [{l['id']: l for l in group} for group in group_line_lists]

        def _make_row(line_id, template):
            cols = []
            total = 0.0
            for idx, group_map in enumerate(maps, start=1):
                value = (self._line_first_value(group_map[line_id])
                         if line_id in group_map else 0.0)
                cols.append({
                    'expression_label': 'group_%d' % idx,
                    'value': self._eh_round_monetary(
                        value, currency=currency),
                })
                total += value
            cols.append({'expression_label': 'total',
                         'value': self._eh_round_monetary(
                             total, currency=currency)})
            row = dict(template)
            row['columns'] = cols
            return row

        merged = []
        seen = set()
        for line in group_line_lists[0] if group_line_lists else []:
            seen.add(line['id'])
            merged.append(_make_row(line['id'], line))
        for group in group_line_lists[1:]:
            for line in group:
                if line['id'] in seen:
                    continue
                seen.add(line['id'])
                merged.append(_make_row(line['id'], line))
        return merged

    # ---- query helpers ----

    @api.model
    def _fetch_grouped_account_totals(
        self, account_types=None, company_ids=None,
        date_from=None, date_to=None,
        posted_only=True, options=None, sign=1, currency_table=None,
    ):
        """Run a per account aggregation and return a list of dicts.

        Each result dict has keys: account_id, account_code, account_name,
        amount. The amount is the sum of balance for the matching journal
        lines, multiplied by sign. Sign is +1 for naturally debit accounts
        (assets, expenses) and -1 for naturally credit accounts (income,
        liabilities, equity), so amounts always present as positive in the
        report.
        """
        options = options or {}
        company_ids = company_ids or [self.env.company.id]
        if currency_table is None and self._EH_SQL_PRESENTATION_CURRENCY:
            currency_table = self._resolve_currency_table(
                options, company_ids, as_of_date=date_to,
            )
        if options.get('cash_basis'):
            return self._cash_basis_grouped_totals(
                account_types=account_types, company_ids=company_ids,
                date_from=date_from, date_to=date_to,
                posted_only=posted_only, options=options, sign=sign,
                currency_table=currency_table,
            )
        query = MoveLineQuery(
            self.env, company_ids=company_ids,
            currency_table=currency_table,
        )
        query.where_date_range(date_from=date_from, date_to=date_to)
        if posted_only:
            query.where_posted_only()
        if account_types:
            query.where_account_types(account_types)
        self.apply_common_filters(query, options)

        query.select_field('account_id')
        query.select_account_field('code', alias='account_code')
        query.select_account_field('name', alias='account_name')
        query.select_balance_sum_converted('balance')
        query.group_by(
            SQL("aml.account_id"),
            query._account_code_sql(),
            query._translated_account_name_sql(),
        )
        query.order_by_account_field('code', 'ASC')

        rows = query.execute()
        return [
            {
                'account_id': r['account_id'],
                'account_code': r['account_code'],
                'account_name': r['account_name'],
                'amount': float(r['balance'] or 0.0) * sign,
            }
            for r in rows
        ]

    @api.model
    def _fetch_aggregate_balance(
        self, account_types=None, company_ids=None,
        date_from=None, date_to=None,
        posted_only=True, options=None, sign=1, currency_table=None,
    ):
        """Return a scalar: sum of balance with the given filters, multiplied
        by sign. No group by. Useful for computed lines like Current Year
        Earnings on a Balance Sheet.
        """
        options = options or {}
        company_ids = company_ids or [self.env.company.id]
        if currency_table is None and self._EH_SQL_PRESENTATION_CURRENCY:
            currency_table = self._resolve_currency_table(
                options, company_ids, as_of_date=date_to,
            )
        query = MoveLineQuery(
            self.env, company_ids=company_ids,
            currency_table=currency_table,
        )
        query.where_date_range(date_from=date_from, date_to=date_to)
        if posted_only:
            query.where_posted_only()
        if account_types:
            query.where_account_types(account_types)
        self.apply_common_filters(query, options)

        query.select_balance_sum_converted('balance')
        rows = query.execute()
        if not rows:
            return 0.0
        return float(rows[0].get('balance') or 0.0) * sign

    # ---- cash-basis recognition ----

    @api.model
    def _cash_basis_grouped_totals(
        self, account_types, company_ids, date_from, date_to,
        posted_only, options, sign, currency_table=None,
    ):
        """Per-account totals recognised on a cash basis.

        Invoice income / expense is recognised by settlement occurring inside
        ``[date_from, date_to]`` regardless of the invoice date. A move with no
        receivable/payable line (a direct cash entry) is recognised on its own
        line date. This period-flow treatment is essential for a monthly cash
        P&L: an invoice posted in December and paid in January belongs in the
        January cash result, not in neither period.
        """
        company_ids = tuple(sorted({int(c) for c in company_ids}))
        if currency_table is None and self._EH_SQL_PRESENTATION_CURRENCY:
            currency_table = self._resolve_currency_table(
                options, company_ids, as_of_date=date_to,
            )

        # Reuse one MoveLineQuery as a safe filter/expression composer, then
        # place its predicates inside a cash-recognition CTE.  Monetary
        # expressions therefore retain literal dimensions, weighted analytic
        # allocation, and optional presentation-currency conversion.
        query = MoveLineQuery(
            self.env,
            company_ids=company_ids,
            currency_table=currency_table,
        )
        if account_types:
            query.where_account_types(account_types)
        self.apply_common_filters(query, options)
        query.join_account()
        account_code = query._account_code_sql()
        account_name = query._translated_account_name_sql()
        recognised_balance = query._analytic_weighted(
            query._balance_expr(),
        )

        settlement_window = SQL("TRUE")
        direct_window = SQL("TRUE")
        if date_from:
            from_value = self._iso_date(date_from)
            settlement_window = SQL(
                "%s AND partial.max_date >= %s",
                settlement_window, from_value,
            )
            direct_window = SQL(
                "%s AND aml.date >= %s", direct_window, from_value,
            )
        if date_to:
            to_value = self._iso_date(date_to)
            settlement_window = SQL(
                "%s AND partial.max_date <= %s",
                settlement_window, to_value,
            )
            direct_window = SQL(
                "%s AND aml.date <= %s", direct_window, to_value,
            )

        joins = [
            SQL("JOIN account_account acc ON acc.id = aml.account_id"),
            SQL("JOIN account_move am ON am.id = aml.move_id"),
        ]
        if 'res_company' in query._joined_tables:
            joins.append(SQL(
                "JOIN res_company aml_company "
                "ON aml_company.id = aml.company_id"
            ))
        if query._has_currency_conversion():
            joins.append(currency_table.join_sql('aml'))

        wheres = [SQL("aml.company_id IN %s", company_ids)]
        if posted_only:
            wheres.append(SQL("am.state = %s", 'posted'))
        else:
            wheres.append(SQL("am.state != %s", 'cancel'))
        wheres.extend(query._wheres)
        recognition_fraction = SQL(
            "CASE WHEN ar_ap.total_amount IS NULL THEN 1.0 "
            "ELSE LEAST(1.0, GREATEST(0.0, "
            "COALESCE(settled.paid_amount, 0.0) "
            "/ NULLIF(ar_ap.total_amount, 0.0))) END"
        )
        recognised_predicate = SQL(
            "((ar_ap.total_amount IS NULL AND (%s)) OR "
            "(ar_ap.total_amount IS NOT NULL "
            "AND COALESCE(settled.paid_amount, 0.0) > 0.0))",
            direct_window,
        )

        sql = SQL(
            "WITH ar_ap_lines AS ("
            " SELECT ar_line.id, ar_line.move_id, ABS(ar_line.balance) amount"
            " FROM account_move_line ar_line"
            " JOIN account_account ar_acc ON ar_acc.id = ar_line.account_id"
            " WHERE ar_line.company_id IN %s"
            " AND ar_acc.account_type IN %s"
            "), ar_ap AS ("
            " SELECT move_id, SUM(amount) AS total_amount"
            " FROM ar_ap_lines GROUP BY move_id"
            "), settlement_links AS ("
            " SELECT partial.debit_move_id AS line_id, partial.amount"
            " FROM account_partial_reconcile partial"
            " WHERE %s"
            " UNION ALL"
            " SELECT partial.credit_move_id AS line_id, partial.amount"
            " FROM account_partial_reconcile partial"
            " WHERE %s"
            "), settled AS ("
            " SELECT ar_line.move_id, SUM(link.amount) AS paid_amount"
            " FROM ar_ap_lines ar_line"
            " JOIN settlement_links link ON link.line_id = ar_line.id"
            " GROUP BY ar_line.move_id"
            ")"
            " SELECT aml.account_id AS account_id,"
            " %s AS account_code, %s AS account_name,"
            " SUM((%s) * (%s)) AS balance"
            " FROM account_move_line aml %s"
            " LEFT JOIN ar_ap ON ar_ap.move_id = aml.move_id"
            " LEFT JOIN settled ON settled.move_id = aml.move_id"
            " WHERE %s AND %s"
            " GROUP BY aml.account_id, %s, %s"
            " ORDER BY %s ASC",
            company_ids,
            ('asset_receivable', 'liability_payable'),
            settlement_window,
            settlement_window,
            account_code,
            account_name,
            recognised_balance,
            recognition_fraction,
            SQL(" ").join(joins),
            SQL(" AND ").join(wheres),
            recognised_predicate,
            account_code,
            account_name,
            account_code,
        )
        self.env.flush_all()
        self.env.cr.execute(sql)
        return [{
            'account_id': row['account_id'],
            'account_code': row['account_code'],
            'account_name': row['account_name'],
            'amount': float(row['balance'] or 0.0) * sign,
        } for row in self.env.cr.dictfetchall()]

    # ---- line factories ----

    @api.model
    def _render_account_lines(
        self, rows, show_zero=False, options=None,
        presentation_converted=False, currency=None,
    ):
        """Convert grouped account totals into report line dicts.

        When options are supplied, each account leaf is stamped with the
        lazy-expand flags via _eh_apply_leaf_lazy_flags (no-op in
        multi-column modes). Omitting options preserves the legacy
        unfoldable: False leaf so callers that never expand are unchanged.
        """
        currency = currency or self._eh_monetary_currency(
            options=options,
            company_ids=(options or {}).get('company_ids'),
            presentation_converted=presentation_converted,
        )
        lines = []
        for r in rows:
            amount = self._eh_round_monetary(
                r['amount'], currency=currency)
            if not show_zero and self._eh_is_zero_monetary(
                    amount, currency=currency):
                continue
            line = {
                'id': "account-%s" % r['account_id'],
                'name': "%s %s" % (r['account_code'], r['account_name']),
                'level': 1,
                'columns': [
                    {'expression_label': 'amount', 'value': amount},
                ],
                'unfoldable': False,
                'meta': {
                    'account_id': r['account_id'],
                    'account_code': r['account_code'],
                },
            }
            if options is not None:
                self._eh_apply_leaf_lazy_flags(line, options)
            lines.append(line)
        return lines

    # ---- lazy expand projection (single-amount sectioned reports) ----

    # Account types that carry a naturally-debit balance: a positive
    # SUM(balance) presents as a positive figure (sign +1). Credit-natural
    # types (income, liability, equity) are flipped with sign -1, matching
    # _fetch_grouped_account_totals' per-section sign argument. Mirrors the
    # P&L / Balance-Sheet display convention from accounting first
    # principles (assets and expenses debit-natural; income, liabilities,
    # equity credit-natural).
    _DEBIT_NATURAL_TYPES = frozenset({
        'asset_receivable', 'asset_cash', 'asset_current',
        'asset_non_current', 'asset_prepayments', 'asset_fixed',
        'expense', 'expense_other', 'expense_depreciation',
        'expense_direct_cost',
    })

    @api.model
    def _expand_account_sign(self, account):
        """Return +1 for debit-natural accounts, -1 for credit-natural.

        Used by _expand_child_columns so a single journal item's signed
        contribution to the cell matches the aggregate's sign convention
        (cell = SUM(balance) * sign). Defaults to +1 for unknown types so
        the child still reconciles for any debit-natural-by-default chart.
        """
        try:
            acc_type = account.account_type
        except Exception:  # pragma: no cover - defensive
            return 1
        return 1 if acc_type in self._DEBIT_NATURAL_TYPES else -1

    @api.model
    def _expand_child_columns(self, options, aml_row):
        """Sectioned override: map one aml's signed balance into 'amount'.

        sign * balance reproduces the per-account aggregate term, so the
        page of children sums to the parent cell. All non-amount columns
        carry the descriptive cells in meta; the single value column is
        'amount' to match the host report's one-column layout.
        """
        account_id = aml_row.get('account_id')
        account = self.env['account.account'].browse(account_id)
        sign = self._expand_account_sign(account)
        currency_id = options.get('_eh_internal_monetary_currency_id')
        currency = (
            self.env['res.currency'].browse(int(currency_id))
            if currency_id else self._eh_monetary_currency(
                options=options,
                company_ids=options.get('company_ids'),
                presentation_converted=bool(
                    options.get('presentation_currency_id')),
            )
        )
        signed = self._eh_round_monetary(
            float(aml_row.get('balance') or 0.0) * sign,
            currency=currency,
        )
        date_val = aml_row.get('date')
        return [{
            'id': "aml-%s" % aml_row.get('aml_id'),
            'name': aml_row.get('ref') or aml_row.get('line_label') or '',
            'level': 2,
            'columns': [{'expression_label': 'amount', 'value': signed}],
            'unfoldable': False,
            'unfolded': False,
            'lazy': False,
            'meta': {
                'kind': 'aml',
                'aml_id': aml_row.get('aml_id'),
                'account_id': account_id,
                'date': self._iso_date(date_val) if date_val else None,
                'move': aml_row.get('move_name') or '',
                'partner': aml_row.get('partner_name') or '',
            },
        }]

    # ---- truthful analytic-column drilldown ----

    @api.model
    def _eh_analytic_drilldown_account_types(self):
        """Account types allowed to appear as leaves in this report."""
        return ()

    @api.model
    def _eh_analytic_drilldown_currency_table(
        self, options, company_ids, date_from, date_to,
    ):
        """Resolve the report-owned conversion policy for one detail cell."""
        return self._resolve_currency_table(
            options, company_ids, as_of_date=date_to,
        )

    @api.model
    def _eh_analytic_drilldown_scope(self, options, expression_label):
        """Rebuild and select one period x analytic scope by stable key."""
        date_from = self._extract_date(options, 'date_from')
        date_to = self._extract_date(options, 'date_to')
        company_ids = options.get('company_ids') or [self.env.company.id]
        periods = self._eh_resolve_period_scopes(
            options,
            date_from,
            date_to,
            snapshot=self._EH_ANALYTIC_DRILLDOWN_SNAPSHOT,
            max_periods=self._MAX_COMPARISON_PERIODS,
        )
        analytics = self._eh_resolve_analytic_column_scopes(
            options, company_ids,
        )
        if not analytics:
            raise UserError(_(
                "The selected cell is not an analytic allocation column."
            ))
        value_scopes = self._eh_build_value_scopes(
            periods, analytics, include_total=True,
        )
        matches = [
            value_scope for value_scope in value_scopes
            if value_scope.get('key') == expression_label
        ]
        if len(matches) != 1:
            raise UserError(_("The selected report column is no longer valid."))
        value_scope = matches[0]
        public_scope = value_scope.get('scope') or {}
        if (
            value_scope.get('is_total')
            or not value_scope.get('analytic_key')
            or not (
                public_scope.get('analytic_account_ids')
                or public_scope.get('analytic_plan_ids')
            )
        ):
            raise UserError(_(
                "The selected cell is not an analytic allocation column."
            ))
        return value_scope

    @api.model
    def _eh_analytic_drilldown_global_filters(self, options):
        """Resolve public analytic filters under the caller's own ACL.

        ``MoveLineQuery.where_analytic_plans`` uses a raw recursive lookup,
        which is appropriate for aggregate report SQL but cannot be trusted
        at a detail boundary.  Expand selected plans through ORM searches so
        only caller-visible plans/accounts can affect returned rows.
        """
        account_ids = self._eh_normalize_id_set(
            options.get('analytic_account_ids'),
            'analytic_account_ids',
        )
        plan_ids = self._eh_normalize_id_set(
            options.get('analytic_plan_ids'),
            'analytic_plan_ids',
        )
        Analytic = self.env['account.analytic.account'].with_context(
            active_test=False,
        )
        Plan = self.env['account.analytic.plan'].with_context(
            active_test=False,
        )
        if account_ids:
            accounts = Analytic.browse(account_ids).exists()
            if set(accounts.ids) != set(account_ids):
                raise UserError(_(
                    "One or more analytic filters no longer exist."
                ))
            accounts._eh_check_access('read')
        plan_account_ids = []
        if plan_ids:
            plans = Plan.browse(plan_ids).exists()
            if set(plans.ids) != set(plan_ids):
                raise UserError(_(
                    "One or more analytic plan filters no longer exist."
                ))
            plans._eh_check_access('read')
            descendants = Plan.search([
                ('id', 'child_of', plans.ids),
            ], order='id')
            descendants._eh_check_access('read')
            plan_accounts = Analytic.search([
                ('plan_id', 'in', descendants.ids),
            ], order='id') if descendants else Analytic
            if descendants:
                plan_accounts._eh_check_access('read')
                plan_account_ids = plan_accounts.ids
        return account_ids, plan_ids, plan_account_ids

    @api.model
    def _eh_analytic_drilldown_query(
        self, options, account_id, date_from, date_to, currency_table,
        global_account_ids, global_plan_ids, global_plan_account_ids,
    ):
        """Build the exact weighted query without raw plan expansion."""
        company_ids = options.get('company_ids') or [self.env.company.id]
        query = MoveLineQuery(
            self.env,
            company_ids=company_ids,
            currency_table=currency_table,
        )
        query.where_date_range(date_from=date_from, date_to=date_to)
        query.where_accounts([account_id])
        if options.get('posted_only', True):
            query.where_posted_only()
        safe_options = dict(options)
        safe_options['analytic_account_ids'] = list(global_account_ids)
        safe_options['analytic_plan_ids'] = []
        self.apply_common_filters(query, safe_options)
        if global_plan_ids:
            if global_plan_account_ids:
                # A separate WHERE preserves account-filter AND plan-filter
                # membership.  The column scope still owns allocation weight.
                query.where_analytic_accounts(global_plan_account_ids)
            else:
                query.where_raw(SQL("FALSE"))
        return query

    @api.model
    def _eh_analytic_drilldown_readable_rows(self, rows):
        """Verify AML, move, and partner rules before returning any value."""
        move_line_ids = [int(row['move_line_id']) for row in rows]
        if not move_line_ids:
            return {}, {}, {}
        MoveLine = self.env['account.move.line']
        readable_lines = MoveLine.search([('id', 'in', move_line_ids)])
        if set(readable_lines.ids) != set(move_line_ids):
            raise AccessError(_(
                "You do not have access to every journal item in this cell."
            ))
        readable_lines._eh_check_access('read')
        line_by_id = {line.id: line for line in readable_lines}

        move_ids = sorted({line.move_id.id for line in readable_lines})
        readable_moves = self.env['account.move'].search([
            ('id', 'in', move_ids),
        ])
        if set(readable_moves.ids) != set(move_ids):
            raise AccessError(_(
                "You do not have access to every journal item in this cell."
            ))
        readable_moves._eh_check_access('read')
        move_by_id = {move.id: move for move in readable_moves}

        partner_ids = sorted({
            line.partner_id.id for line in readable_lines if line.partner_id
        })
        readable_partners = self.env['res.partner'].search([
            ('id', 'in', partner_ids),
        ]) if partner_ids else self.env['res.partner']
        if set(readable_partners.ids) != set(partner_ids):
            raise AccessError(_(
                "You do not have access to every journal item in this cell."
            ))
        if readable_partners:
            readable_partners._eh_check_access('read')
        partner_by_id = {
            partner.id: partner for partner in readable_partners
        }
        return line_by_id, move_by_id, partner_by_id

    @api.model
    def _eh_analytic_drilldown_account_matches_companies(
        self, account, company_ids,
    ):
        """Apply core's chart-account branch ownership contract.

        Odoo 17-19 can expose a root-owned account to descendant branches;
        comparing ``account.company_ids`` with the selected branch ids rejects
        that valid core relationship.  Ask ``account.account`` for its native
        check-company domain when available.  Odoo 16 lacks that API and keeps
        the previous exact-company/global fallback.
        """
        companies = self.env['res.company'].browse([
            int(company_id) for company_id in (company_ids or [])
        ]).exists()
        domain_builder = getattr(account, '_check_company_domain', None)
        filtered_domain = getattr(account, 'filtered_domain', None)
        if callable(domain_builder) and callable(filtered_domain):
            try:
                return any(
                    bool(account.filtered_domain(domain_builder(company)))
                    for company in companies
                )
            except (AttributeError, TypeError, ValueError):
                # Legacy runtimes have no hierarchy-aware account contract.
                pass
        if 'company_ids' in account._fields:
            account_company_ids = set(account.company_ids.ids)
            return (
                not account_company_ids
                or bool(account_company_ids & set(companies.ids))
            )
        if 'company_id' in account._fields:
            return not account.company_id or account.company_id in companies
        return True

    @api.model
    def _eh_analytic_drilldown_page_token(
        self, weighted_rows, raw_amounts, total, currency, value_scope,
        line_id, expression_label, limit, snapshot_binding,
    ):
        """Digest the ordered candidates and bind their page contract.

        Count and aggregate are insufficient: replacing one allocation with
        another equal allocation keeps both stable while an offset page moves.
        Cover every ordered AML id, move id and unrounded contribution, then
        bind that set to the exact execution/cell/options/scope/page size.
        """
        binding = snapshot_binding if isinstance(snapshot_binding, dict) else {}
        if (
            len(weighted_rows) != len(raw_amounts)
            or not isinstance(binding.get('execution_id'), int)
            or isinstance(binding.get('execution_id'), bool)
            or binding['execution_id'] < 1
            or not isinstance(binding.get('options_hash'), str)
            or len(binding['options_hash']) != 64
            or not isinstance(binding.get('displayed_amount'), (int, float))
            or isinstance(binding.get('displayed_amount'), bool)
            or not math.isfinite(float(binding['displayed_amount']))
        ):
            raise UserError(_(
                "The weighted-detail snapshot contract is invalid. Refresh "
                "the report and try again."
            ))
        candidates = []
        for row, raw_amount in zip(weighted_rows, raw_amounts):
            if (
                not isinstance(row, dict)
                or not isinstance(raw_amount, (int, float))
                or isinstance(raw_amount, bool)
                or not math.isfinite(float(raw_amount))
            ):
                raise UserError(_(
                    "The journal items changed while detail was being "
                    "prepared. Refresh the report and try again."
                ))
            candidates.append({
                'move_line_id': int(row.get('move_line_id') or 0),
                'move_id': int(row.get('move_id') or 0),
                # Preserve sub-currency allocation changes which rounded
                # display values would erase.
                'raw_amount': repr(float(raw_amount)),
            })
        candidate_digest = hashlib.sha256(json.dumps(
            candidates, sort_keys=True, separators=(',', ':'),
        ).encode('utf-8')).hexdigest()
        contract = {
            'version': 1,
            'execution_id': binding['execution_id'],
            'options_hash': binding['options_hash'],
            'line_id': line_id,
            'expression_label': expression_label,
            'displayed_amount': repr(float(binding['displayed_amount'])),
            'total': repr(float(total)),
            'currency_id': int(currency.id),
            'scope': value_scope.get('scope') or {},
            'limit': int(limit),
            'total_count': len(candidates),
            'candidate_digest': candidate_digest,
        }
        return hashlib.sha256(json.dumps(
            contract, sort_keys=True, separators=(',', ':'), default=str,
        ).encode('utf-8')).hexdigest()

    @api.model
    def _eh_assert_analytic_drilldown_page_token(
        self, offset, supplied_token, expected_token,
    ):
        """Require the first page's exact token for every later page."""
        if supplied_token not in (None, False, ''):
            if (
                not isinstance(supplied_token, str)
                or len(supplied_token) != 64
                or not hmac.compare_digest(supplied_token, expected_token)
            ):
                raise UserError(_(
                    "Weighted detail changed while paging; reopen the cell."
                ))
        elif offset:
            raise UserError(_(
                "Weighted detail pages must be opened in sequence. Reopen "
                "the cell and try again."
            ))

    @api.model
    @api.private
    def _eh_get_analytic_column_drilldown_page(
        self, options, line_id, expression_label, offset=0, limit=80,
        page_token=None, snapshot_binding=None,
    ):
        """Return one record-rule-safe weighted detail page.

        All candidate ids are rule-checked before pagination.  If even one
        contributing AML or related display record is not readable, the
        entire cell fails closed instead of returning a misleading subtotal.
        """
        if not self._EH_ANALYTIC_COLUMN_DRILLDOWN:
            raise UserError(_(
                "Weighted analytic drill-down is not available for this "
                "report."
            ))
        if options.get('cash_basis'):
            raise UserError(_(
                "Weighted analytic detail is unavailable for cash-basis "
                "recognition."
            ))
        value_scope = self._eh_analytic_drilldown_scope(
            options, expression_label,
        )
        scoped_options = self._eh_scope_options(options, value_scope)
        account_id = self._expand_account_id_from_line_id(line_id)
        if account_id is None:
            raise UserError(_("The selected report row is not an account."))
        account = self.env['account.account'].search([
            ('id', '=', account_id),
        ], limit=1)
        if not account:
            raise AccessError(_("The selected account is not accessible."))
        account._eh_check_access('read')
        allowed_types = set(self._eh_analytic_drilldown_account_types())
        if not allowed_types or account.account_type not in allowed_types:
            raise UserError(_("The selected account is not part of this report."))
        company_ids = scoped_options.get('company_ids') or [
            self.env.company.id,
        ]
        if not self._eh_analytic_drilldown_account_matches_companies(
            account, company_ids,
        ):
            raise AccessError(_(
                "The selected account is outside company scope."
            ))

        date_from = self._extract_date(scoped_options, 'date_from')
        date_to = self._extract_date(scoped_options, 'date_to')
        currency_table = self._eh_analytic_drilldown_currency_table(
            scoped_options, company_ids, date_from, date_to,
        )
        presentation_converted = bool(
            currency_table is not None
            and not currency_table.is_monocurrency
        )
        currency = self._eh_monetary_currency(
            options=scoped_options,
            company_ids=company_ids,
            presentation_converted=presentation_converted,
        )
        global_accounts, global_plans, global_plan_accounts = (
            self._eh_analytic_drilldown_global_filters(scoped_options)
        )

        rows_query = self._eh_analytic_drilldown_query(
            scoped_options,
            account_id,
            date_from,
            date_to,
            currency_table,
            global_accounts,
            global_plans,
            global_plan_accounts,
        )
        rows_query.select_field('id', alias='move_line_id')
        rows_query.select_field('move_id')
        rows_query.select_balance_converted(alias='allocated_balance')
        rows_query.order_by('date', 'ASC')
        rows_query.order_by('id', 'ASC')
        rows_query.limit(self._MAX_ANALYTIC_DRILLDOWN_ROWS + 1)
        weighted_rows = rows_query.execute()
        if len(weighted_rows) > self._MAX_ANALYTIC_DRILLDOWN_ROWS:
            raise UserError(_(
                "This cell contains too many journal items for safe detail "
                "inspection. Narrow the report filters and try again."
            ))
        line_by_id, move_by_id, partner_by_id = (
            self._eh_analytic_drilldown_readable_rows(weighted_rows)
        )

        total_query = self._eh_analytic_drilldown_query(
            scoped_options,
            account_id,
            date_from,
            date_to,
            currency_table,
            global_accounts,
            global_plans,
            global_plan_accounts,
        )
        total_query.select_balance_sum_converted(alias='allocated_total')
        total_rows = total_query.execute()
        sign = self._expand_account_sign(account)
        raw_total = float(
            total_rows[0].get('allocated_total') or 0.0
        ) if total_rows else 0.0
        raw_amounts = [
            float(row.get('allocated_balance') or 0.0) * sign
            for row in weighted_rows
        ]
        rounding_quantum = max(float(currency.rounding or 0.0), 1e-9)
        raw_reconciliation = raw_total * sign - math.fsum(raw_amounts)
        if (
            not math.isfinite(raw_total)
            or not all(math.isfinite(amount) for amount in raw_amounts)
            or abs(raw_reconciliation) > rounding_quantum
        ):
            raise UserError(_(
                "The journal items changed while detail was being "
                "prepared. Refresh the report and try again."
            ))
        total = self._eh_round_monetary(
            raw_total * sign, currency=currency,
        )

        # Every value sent to browser is currency-rounded. Reconcile aggregate
        # display residue on final row of full deterministic result set, not on
        # final row of each page, so page size/order cannot change amounts.
        amounts = [
            self._eh_round_monetary(amount, currency=currency)
            for amount in raw_amounts
        ]
        if amounts:
            amounts[-1] = self._eh_round_monetary(
                float(total) - math.fsum(amounts[:-1]),
                currency=currency,
            )
            if self._eh_round_monetary(
                math.fsum(amounts), currency=currency,
            ) != float(total):
                raise UserError(_(
                    "The journal items changed while detail was being "
                    "prepared. Refresh the report and try again."
                ))

        total_count = len(weighted_rows)
        expected_page_token = self._eh_analytic_drilldown_page_token(
            weighted_rows, raw_amounts, total, currency, value_scope,
            line_id, expression_label, limit, snapshot_binding,
        )
        self._eh_assert_analytic_drilldown_page_token(
            offset, page_token, expected_page_token,
        )
        page_rows = []
        page_end = min(total_count, offset + limit)
        for index in range(offset, page_end):
            weighted = weighted_rows[index]
            move_line_id = int(weighted['move_line_id'])
            line = line_by_id[move_line_id]
            move = move_by_id[line.move_id.id]
            partner = (
                partner_by_id.get(line.partner_id.id)
                if line.partner_id else None
            )
            page_rows.append({
                'id': 'aml-%d' % move_line_id,
                'move_line_id': move_line_id,
                'move_id': move.id,
                'values': {
                    'date': fields.Date.to_string(line.date),
                    'move': move.name or '',
                    'partner': partner.display_name if partner else '',
                    'label': line.ref or line.name or '',
                    'allocated_amount': amounts[index],
                },
            })

        decimals = max(0, min(6, int(currency.decimal_places or 0)))
        return {
            'columns': [
                {'key': 'date', 'name': _("Date"), 'figure_type': 'date'},
                {'key': 'move', 'name': _("Journal Entry"),
                 'figure_type': 'string'},
                {'key': 'partner', 'name': _("Partner"),
                 'figure_type': 'string'},
                {'key': 'label', 'name': _("Label"),
                 'figure_type': 'string'},
                {'key': 'allocated_amount', 'name': _("Allocated Amount"),
                 'figure_type': 'monetary'},
            ],
            'rows': page_rows,
            'total': float(total),
            'offset': offset,
            'limit': limit,
            'total_count': total_count,
            'has_more': offset + len(page_rows) < total_count,
            'page_token': expected_page_token,
            'currency': {
                'id': currency.id,
                'name': currency.name or '',
                'symbol': currency.symbol or '',
                'position': currency.position,
                'decimal_places': decimals,
            },
            'scope': dict(value_scope['scope']),
        }

    @api.model
    def _render_account_lines_grouped(
        self, rows, section_id, show_zero=False,
        unfolded_ids=None, options=None, presentation_converted=False,
        currency=None,
    ):
        """Convert per-account totals into a hierarchical line list
        nested by account.group.

        Walks account.account.group_id and account.group.parent_id to
        build the full group path for each account. Emits one line per
        group ancestor (level >= 1, unfoldable) and one line per
        account (leaf) parented to the deepest group. Accounts without
        a group attach directly to the section header.

        :param rows: list of {account_id, account_code, account_name,
            amount} dicts as returned by _fetch_grouped_account_totals.
        :param section_id: id of the parent section (the section header
            is emitted by the caller via _section_header_line).
        :param show_zero: include groups / accounts with zero balance.
        :param unfolded_ids: set of line ids the caller has marked as
            unfolded; lines whose parent is folded are still emitted
            but the renderer hides them. Defaults to "all groups
            unfolded" so the report renders fully expanded on first
            load.

        Returns the nested line list (excluding the section header
        itself, which the caller emits separately).
        """
        if not rows:
            return []
        currency = currency or self._eh_monetary_currency(
            options=options,
            company_ids=(options or {}).get('company_ids'),
            presentation_converted=presentation_converted,
        )
        unfolded_ids = unfolded_ids if unfolded_ids is not None else set()
        Account = self.env['account.account'].sudo()
        accounts = Account.browse([r['account_id'] for r in rows])
        # Cache amount per account_id for O(1) lookup.
        amount_by_id = {
            r['account_id']: self._eh_round_monetary(
                r['amount'], currency=currency)
            for r in rows
        }
        code_by_id = {r['account_id']: r['account_code'] for r in rows}
        name_by_id = {r['account_id']: r['account_name'] for r in rows}

        # Resolve full group path per account: list of (group_id,
        # group_name, group_code) from root to leaf, or [] for
        # ungrouped accounts. account.group.parent_id is the upstream
        # field that gives us the parent chain.
        group_paths = {}
        Group = self.env['account.group'].sudo()
        for acc in accounts:
            chain = []
            grp = acc.group_id
            while grp:
                chain.append((
                    grp.id,
                    grp.name or grp.display_name,
                    grp.code_prefix_start or '',
                ))
                grp = grp.parent_id
            chain.reverse()
            group_paths[acc.id] = chain

        # Aggregate amounts up the group tree. group_totals keys are
        # (section_id, group_id_path_tuple) so we can sum every account
        # that lives at or below each ancestor group.
        group_totals = {}  # path_tuple -> total
        accounts_by_group = {}  # path_tuple -> list of account ids
        for acc_id in amount_by_id:
            path = group_paths[acc_id]
            cumulative = ()
            # Accumulate at every ancestor depth.
            for entry in path:
                cumulative = cumulative + (entry[0],)
                group_totals[cumulative] = (
                    group_totals.get(cumulative, 0.0) + amount_by_id[acc_id]
                )
            # Track which group is the immediate parent for ungrouped
            # accounts (path empty -> attach to section header directly).
            parent_path = tuple(e[0] for e in path)
            accounts_by_group.setdefault(parent_path, []).append(acc_id)

        # Pre-compute the line id we will emit for each (path) tuple
        # so children can reference parent ids consistently.
        def _line_id_for_path(path_tuple):
            if not path_tuple:
                return "section-%s-header" % section_id
            return "section-%s-group-%s" % (
                section_id,
                "_".join(str(g) for g in path_tuple),
            )

        # Emit lines depth-first: every group, then its accounts,
        # sorted so that children appear under the right ancestor.
        lines = []
        # Build a sorted set of group paths (every prefix).
        all_paths = set()
        for parent_path in accounts_by_group:
            cumulative = ()
            for g in parent_path:
                cumulative = cumulative + (g,)
                all_paths.add(cumulative)
        # Sort paths so parents render before children, and siblings
        # render in code-prefix order to match the chart-of-accounts.
        def _path_sort_key(p):
            # Look up the code_prefix_start for each leg of the path
            # so siblings sort by prefix; falls back to id.
            keys = []
            for gid in p:
                grp = Group.browse(gid)
                keys.append((grp.code_prefix_start or '', gid))
            return keys
        ordered_paths = sorted(all_paths, key=_path_sort_key)

        # For each path, emit the group header then any accounts that
        # live exactly at that path. Accounts without a group emit
        # before any group lines (they hang directly off the section
        # header) so the user sees ungrouped items at the top.
        ungrouped = accounts_by_group.get((), [])
        if ungrouped:
            ungrouped.sort(key=lambda aid: code_by_id.get(aid, ''))
            for aid in ungrouped:
                amt = amount_by_id[aid]
                if not show_zero and self._eh_is_zero_monetary(
                        amt, currency=currency):
                    continue
                leaf = {
                    'id': "account-%s" % aid,
                    'name': "%s %s" % (code_by_id[aid], name_by_id[aid]),
                    'level': 1,
                    'parent_id': "section-%s-header" % section_id,
                    'columns': [
                        {'expression_label': 'amount', 'value': amt},
                    ],
                    'unfoldable': False,
                    'meta': {
                        'account_id': aid,
                        'account_code': code_by_id[aid],
                    },
                }
                if options is not None:
                    self._eh_apply_leaf_lazy_flags(leaf, options)
                lines.append(leaf)

        for path in ordered_paths:
            path_total = self._eh_round_monetary(
                group_totals.get(path, 0.0), currency=currency)
            if not show_zero and self._eh_is_zero_monetary(
                    path_total, currency=currency):
                continue
            grp = Group.browse(path[-1])
            depth = len(path)
            parent_path = path[:-1]
            parent_id = _line_id_for_path(parent_path)
            this_id = _line_id_for_path(path)
            unfolded = (
                not unfolded_ids
                or this_id in unfolded_ids
            )
            lines.append({
                'id': this_id,
                # Human label stays human. Prefix remains a structured sort /
                # grouping key, avoiding labels such as "10 10 Current Assets"
                # when upstream display_name already contains the prefix.
                'name': grp.name or grp.display_name or '',
                'level': depth,
                'parent_id': parent_id,
                'columns': [
                    {'expression_label': 'amount', 'value': path_total},
                ],
                'unfoldable': True,
                'unfolded': unfolded,
                'meta': {
                    'kind': 'account_group',
                    'group_id': grp.id,
                    'group_key': {
                        'id': grp.id,
                        'code_prefix': grp.code_prefix_start or '',
                    },
                    'group_label': grp.name or grp.display_name or '',
                    'depth': depth,
                },
            })
            # Accounts whose parent path is exactly this path.
            for aid in sorted(
                accounts_by_group.get(path, []),
                key=lambda a: code_by_id.get(a, ''),
            ):
                amt = amount_by_id[aid]
                if not show_zero and self._eh_is_zero_monetary(
                        amt, currency=currency):
                    continue
                leaf = {
                    'id': "account-%s" % aid,
                    'name': "%s %s" % (code_by_id[aid], name_by_id[aid]),
                    'level': depth + 1,
                    'parent_id': this_id,
                    'columns': [
                        {'expression_label': 'amount', 'value': amt},
                    ],
                    'unfoldable': False,
                    'meta': {
                        'account_id': aid,
                        'account_code': code_by_id[aid],
                    },
                }
                if options is not None:
                    self._eh_apply_leaf_lazy_flags(leaf, options)
                lines.append(leaf)
        return lines

    @api.model
    def _section_header_line(self, name, section_id):
        # Empty string instead of None for the value: keeps the cell
        # blank in the OWL renderer and the PDF/XLSX exporter, but is
        # also serialisable through XML-RPC (where None is rejected
        # unless allow_none=True is set on the Marshaller, which the
        # Odoo default Marshaller does not).
        return {
            'id': "section-%s-header" % section_id,
            'name': name,
            'level': 0,
            'columns': [{'expression_label': 'amount', 'value': ''}],
            'unfoldable': False,
            'meta': {'kind': 'section_header', 'section_id': section_id},
        }

    @api.model
    def _section_total_line(
        self, name, total, section_id, options=None,
        presentation_converted=False, currency=None,
    ):
        currency = currency or self._eh_monetary_currency(
            options=options,
            company_ids=(options or {}).get('company_ids'),
            presentation_converted=presentation_converted,
        )
        return {
            'id': "section-%s-total" % section_id,
            'name': name,
            'level': 0,
            'columns': [
                {'expression_label': 'amount',
                 'value': self._eh_round_monetary(
                     total, currency=currency)},
            ],
            'unfoldable': False,
            'meta': {'kind': 'section_total', 'section_id': section_id},
        }

    @api.model
    def _computed_line(
        self, line_id, name, amount, kind='computed', options=None,
        presentation_converted=False, currency=None,
    ):
        """Standalone computed line (Net Profit, Current Year Earnings,
        Balance Check, etc.). Sits at level 0 in bold.
        """
        currency = currency or self._eh_monetary_currency(
            options=options,
            company_ids=(options or {}).get('company_ids'),
            presentation_converted=presentation_converted,
        )
        return {
            'id': line_id,
            'name': name,
            'level': 0,
            'columns': [
                {'expression_label': 'amount',
                 'value': self._eh_round_monetary(
                     amount, currency=currency)},
            ],
            'unfoldable': False,
            'meta': {'kind': kind},
        }
