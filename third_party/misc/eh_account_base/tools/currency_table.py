# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Currency-conversion helper for multi-company consolidated reporting.

When a report consolidates several companies that share one currency (the
overwhelmingly common case) every ``aml.balance`` is already expressed in the
presentation currency, so summing them raw is correct. The moment two
companies report in different currencies (e.g. AUD and USD), a raw
``SUM(aml.balance)`` adds dollars and Aussie dollars as if they were equal,
producing a meaningless consolidated figure.

CurrencyTable resolves a single presentation currency and, for each company
in scope, the rate that converts that company's currency into the
presentation currency. It then exposes the SQL fragments the MoveLineQuery
needs to LEFT JOIN a small per-company rate table and multiply each line's
monetary columns by that rate before aggregation.

Design rules (mirroring MoveLineQuery):

1. Plain Python class, no ORM model, so it is unit-testable without the
   registry. Rate seeding is the only env-dependent step and is performed
   lazily; a stub rate map can be injected for unit tests.
2. Two modes. ``monocurrency`` (every company already in the presentation
   currency) emits NO join and NO rate multiply, so the hot path for the
   95% of installs that never consolidate across currencies is byte-for-byte
   identical to a query built without a CurrencyTable. ``multicurrency``
   emits an inner ``JOIN (VALUES ...) ct(company_id, rate)`` keyed on the
   indexed ``aml.company_id`` and a ``rate_expr()`` of ``ct.rate``.
3. Rates come from the ORM (res.currency conversion), seeded as of the
   report's as-of date. A single spot rate per company is used (date-aware
   on the report date_to). Per-aml date-effective rates are a documented
   follow-up; the join column and ``rate_expr`` are already shaped so that
   refinement is a drop-in.
4. Fail closed when a requested conversion has no valid target-currency rate
   at or before the report date. Odoo core deliberately falls back to the
   earliest future rate and then 1.0; either fallback would publish a
   converted label over unproved numbers. Report conversion therefore proves
   the dated rate record first and never emits an SQL identity fallback.
"""

import math

from odoo import _, fields
from odoo.exceptions import UserError
from odoo.tools import SQL


class CurrencyTable:
    """Resolve per-company conversion rates into a presentation currency.

    Usage::

        ct = CurrencyTable(env, company_ids=[1, 2], presentation_currency_id=7)
        if not ct.is_monocurrency:
            # MoveLineQuery emits ct.join_sql('aml') and multiplies by
            # ct.rate_expr().
            ...

    The instance is cheap to construct; rate seeding runs lazily the first
    time a multicurrency consumer asks for the join or rate expression.
    """

    def __init__(self, env, company_ids, presentation_currency_id=None,
                 as_of_date=None, rate_map=None):
        self.env = env
        self.company_ids = tuple(
            int(c) for c in (company_ids or ()) if c is not None
        )
        # Presentation currency: explicit option wins, else the active
        # company's currency. Resolved to an int id so the seeding step and
        # the monocurrency decision never browse a falsey record.
        if presentation_currency_id:
            self.presentation_currency_id = int(presentation_currency_id)
        else:
            self.presentation_currency_id = (
                env.company.currency_id.id if env is not None else False
            )
        self.as_of_date = (
            fields.Date.to_date(as_of_date) if as_of_date else None
        )
        # Kept as an empty compatibility surface for extensions that inspected
        # the old fallback disclosure. Conversion no longer has fallbacks.
        self.fallback_flags = []
        # Actual target-rate record date used for each converted company.
        self._rate_date_map = {}
        # _rate_map: {company_id: float rate}. Injected (unit tests) or
        # seeded lazily from the ORM. None means "not yet seeded".
        self._rate_map = dict(rate_map) if rate_map is not None else None
        self._seeded = rate_map is not None
        # Cache the monocurrency decision so repeated property reads are free.
        self._is_monocurrency = None

    # ---- mode decision ----

    @property
    def is_monocurrency(self):
        """True when no conversion is needed (zero-overhead hot path).

        Monocurrency holds when no presentation currency could be resolved
        (degrade to raw sum, exactly like today), or when every company in
        scope already reports in the presentation currency. A single company
        still needs conversion when the requested presentation currency is
        different from its ledger currency. In every monocurrency case
        ``join_sql`` and the converted-sum expressions fall back to the legacy
        raw form, so a single-company report in its own currency is unaffected.
        """
        if self._is_monocurrency is not None:
            return self._is_monocurrency
        result = self._compute_is_monocurrency()
        self._is_monocurrency = result
        return result

    def _compute_is_monocurrency(self):
        if not self.presentation_currency_id:
            return True
        try:
            companies = self.env['res.company'].sudo().browse(
                list(self.company_ids))
            currency_ids = set(companies.mapped('currency_id').ids)
        except Exception:  # pragma: no cover - defensive
            return True
        if not currency_ids:
            return True
        # All companies already in the presentation currency -> no conversion.
        return currency_ids == {self.presentation_currency_id}

    # ---- rate seeding (lazy, env-dependent) ----

    def _seed_rates(self):
        """Populate {company_id: rate-to-presentation-currency}.

        Uses the ORM conversion rate (res.currency._get_conversion_rate),
        which converts an amount expressed in the company currency into the
        presentation currency for the given company and date. A company
        already in the presentation currency gets exactly 1.0 and never hits
        a rate lookup. Every other company must have a valid target-currency
        rate dated on or before ``as_of_date``.
        """
        if self._seeded:
            return
        rate_map = {}
        Currency = self.env['res.currency'].sudo()
        presentation = Currency.browse(self.presentation_currency_id)
        companies = self.env['res.company'].sudo().browse(
            list(self.company_ids))
        for company in companies:
            company_currency = company.currency_id
            if not company_currency or not presentation:
                raise UserError(_(
                    "Cannot translate %(company)s because its source or "
                    "presentation currency is missing.",
                    company=company.display_name,
                ))
            if company_currency.id == self.presentation_currency_id:
                rate_map[company.id] = 1.0
                continue
            rate = self._resolve_company_rate(
                company_currency, presentation, company)
            rate_map[company.id] = rate
        self._rate_map = rate_map
        self._seeded = True

    def _resolve_company_rate(self, company_currency, presentation, company):
        """Rate to convert company_currency -> presentation for one company.

        Proves a target rate exists at or before the report date before asking
        core for its conversion ratio. This blocks core's earliest-future and
        identity fallbacks from entering financial-report numbers.
        """
        if not self.as_of_date:
            raise UserError(_(
                "A report end date is required for presentation-currency "
                "translation."
            ))
        rate_record = self._strict_target_rate_record(presentation, company)
        rate = self.env['res.currency']._get_conversion_rate(
            company_currency, presentation, company, self.as_of_date,
        )
        try:
            rate = float(rate)
        except (TypeError, ValueError, OverflowError) as exc:
            raise UserError(self._invalid_rate_message(
                company_currency, presentation, company,
            )) from exc
        if not math.isfinite(rate) or rate <= 0.0:
            raise UserError(self._invalid_rate_message(
                company_currency, presentation, company,
            ))
        self._rate_date_map[company.id] = fields.Date.to_string(
            rate_record.name,
        )
        return rate

    def _strict_target_rate_record(self, presentation, company):
        """Return exact target rate allowed for company/date, or fail closed."""
        root_company = getattr(company, 'root_id', False) or company
        rate_record = self.env['res.currency.rate'].sudo().search([
            ('currency_id', '=', presentation.id),
            ('company_id', 'in', [False, root_company.id]),
            ('name', '<=', self.as_of_date),
        ], order='company_id, name desc', limit=1)
        try:
            value = float(rate_record.rate) if rate_record else 0.0
            valid = math.isfinite(value) and value > 0.0
        except (TypeError, ValueError, OverflowError):
            valid = False
        if not valid:
            company_currency = company.currency_id
            raise UserError(self._invalid_rate_message(
                company_currency, presentation, company,
            ))
        return rate_record

    def _invalid_rate_message(self, company_currency, presentation, company):
        return _(
            "No valid %(source)s to %(target)s exchange rate exists for "
            "%(company)s on or before %(date)s. Add a dated rate, then rerun "
            "the report.",
            source=company_currency.display_name,
            target=presentation.display_name,
            company=company.display_name,
            date=fields.Date.to_string(self.as_of_date),
        )

    def _validate_injected_rates(self):
        """Keep white-box injected maps subject to production invariants."""
        rate_map = self._rate_map or {}
        for company_id in self.company_ids:
            try:
                value = float(rate_map[company_id])
                valid = math.isfinite(value) and value > 0.0
            except (KeyError, TypeError, ValueError, OverflowError):
                valid = False
            if not valid:
                raise UserError(_(
                    "Currency conversion rate is missing or invalid for "
                    "company %(company_id)s.",
                    company_id=company_id,
                ))

    @property
    def rate_map(self):
        """The seeded {company_id: rate} map (seeds lazily)."""
        if not self._seeded:
            self._seed_rates()
        self._validate_injected_rates()
        return dict(self._rate_map or {})

    @property
    def rate_date_map(self):
        """Actual {company_id: target-rate-date} map used for translation."""
        if not self.is_monocurrency and not self._seeded:
            self._seed_rates()
        return dict(self._rate_date_map)

    def translation_metadata(self):
        """Audit metadata for current closing-spot translation table."""
        if self.is_monocurrency:
            return {}
        # Seed/validate before metadata can claim conversion.
        self.rate_map
        return {
            'currency_translation_policy': 'closing_spot',
            'currency_translation_as_of_date': fields.Date.to_string(
                self.as_of_date,
            ),
            'currency_translation_rate_dates': {
                str(company_id): rate_date
                for company_id, rate_date in self.rate_date_map.items()
            },
        }

    def period_metadata(self, label):
        """Compact one-period audit entry for comparison payloads."""
        metadata = self.translation_metadata()
        if not metadata:
            return None
        return {
            'label': label,
            'policy': metadata['currency_translation_policy'],
            'as_of_date': metadata['currency_translation_as_of_date'],
            'rate_dates': metadata['currency_translation_rate_dates'],
        }

    # ---- SQL fragments consumed by MoveLineQuery ----

    def join_sql(self, aml_alias='aml'):
        """Inner JOIN fragment binding a per-company rate, or empty SQL.

        Monocurrency -> empty (no join), so the rendered query is identical
        to one built without a CurrencyTable. Multicurrency -> a complete,
        validated VALUES table joined on company id. Missing values raise
        before SQL construction; no row can silently convert at identity.
        """
        if self.is_monocurrency:
            return SQL("")
        rate_map = self.rate_map
        if not rate_map:
            return SQL("")
        # Build "(company_id, rate), (company_id, rate), ..." with every
        # value bound as a parameter (no interpolation of user/runtime data).
        value_rows = []
        for company_id in self.company_ids:
            rate = rate_map[company_id]
            value_rows.append(SQL("(%s, %s)", int(company_id), float(rate)))
        values_clause = SQL(", ").join(value_rows)
        # aml_alias is a fixed internal identifier ('aml'); guard anyway and
        # bind it as a quoted identifier so it can never carry an injection.
        alias = aml_alias if (
            isinstance(aml_alias, str) and aml_alias.isidentifier()
        ) else 'aml'
        return SQL(
            "JOIN (VALUES %s) AS ct (company_id, rate) "
            "ON ct.company_id = %s.company_id",
            values_clause, SQL.identifier(alias),
        )

    def rate_expr(self):
        """SQL scalar the converted-sum expressions multiply by.

        Monocurrency -> ``SQL("1")`` so ``balance * 1`` folds to the legacy
        plain sum. Multicurrency -> validated ``ct.rate``; no SQL fallback.
        """
        if self.is_monocurrency:
            return SQL("1")
        return SQL("ct.rate")
