# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Report-input freshness and company-scoped presentation policy.

The public compatibility field ``res.company.eh_move_version`` remains the
report-cache freshness signal, but its counters live in dedicated tables.
Posting therefore locks only the affected company's tiny counter row instead
of the business-critical ``res_company`` row.  Global presentation inputs
(partner labels, currencies, account tags, and report definitions) advance one
separate epoch, so they no longer lock every company counter and serialize
posting across the whole database.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class EhAccountReportCompanyVersion(models.Model):
    """Private per-company cache epoch, isolated from ``res_company`` locks."""

    _name = 'eh.account.report.company.version'
    _description = "Accounting report company input version"
    _log_access = False

    company_id = fields.Many2one(
        'res.company', required=True, ondelete='cascade', index=True,
    )
    version = fields.Integer(required=True, default=0, readonly=True)

    _company_unique = models.Constraint(
        'unique(company_id)',
        'Each company has one accounting report input version.',
    )


class EhAccountReportGlobalVersion(models.Model):
    """Private singleton epoch for report inputs shared by all companies."""

    _name = 'eh.account.report.global.version'
    _description = "Accounting report global input version"
    _log_access = False

    version = fields.Integer(required=True, default=0, readonly=True)


class ResCompany(models.Model):
    _inherit = 'res.company'

    eh_move_version = fields.Integer(
        string="Move Version Counter",
        compute='_compute_eh_move_version',
        readonly=True,
        help=(
            "Server-owned monotonic version of report-visible inputs, "
            "including ledger, master-data, configuration, currency-rate, "
            "and supported sub-ledger changes. Used by the ERP Heritage "
            "reporting cache to detect staleness. Do not edit manually."
        ),
    )

    def _compute_eh_move_version(self):
        """Read the isolated company counter plus the shared global epoch."""
        if not self:
            return
        self.env.cr.execute(
            "SELECT to_regclass('eh_account_report_company_version'), "
            "to_regclass('eh_account_report_global_version')"
        )
        company_table, global_table = self.env.cr.fetchone()
        if not company_table or not global_table:
            # Registry installation can inspect company fields before every
            # addon table is initialised. No report execution exists then.
            for company in self:
                company.eh_move_version = 0
            return
        self.env.cr.execute(
            "SELECT company_id, version "
            "FROM eh_account_report_company_version WHERE company_id IN %s",
            (tuple(self.ids),),
        )
        local_versions = dict(self.env.cr.fetchall())
        self.env.cr.execute(
            "SELECT version FROM eh_account_report_global_version "
            "WHERE id = 1"
        )
        row = self.env.cr.fetchone()
        global_version = int(row[0]) if row else 0
        for company in self:
            company.eh_move_version = (
                global_version + int(local_versions.get(company.id, 0))
            )

    # ------------------------------------------------------------------
    # Settings persisted on the company so they survive across sessions.
    # The corresponding res.config.settings fields mirror these via
    # related/readonly=False so the operator edits them on the
    # standard Settings page.
    # ------------------------------------------------------------------

    # Reporting engine
    eh_gl_row_limit = fields.Integer(
        string="GL Row Limit",
        default=10000,
        help="Maximum row materialisation cap for row-driven reports.",
    )
    eh_expand_page_size = fields.Integer(
        string="Lazy Expand Page Size",
        default=80,
        help=(
            "Number of journal items fetched per page when an account "
            "line is expanded on demand in a dynamic report. Lower values "
            "feel snappier on huge accounts; higher values page less often."
        ),
    )
    eh_dashboard_lookback_days = fields.Integer(
        string="Dashboard Lookback (days)",
        default=180,
        help="History window scanned by the financial dashboard tiles.",
    )

    _positive_report_row_limit = models.Constraint(
        'CHECK (eh_gl_row_limit > 0)',
        'GL Row Limit must be greater than zero.',
    )
    _positive_expand_page_size = models.Constraint(
        'CHECK (eh_expand_page_size > 0)',
        'Lazy Expand Page Size must be greater than zero.',
    )
    _expand_page_within_row_limit = models.Constraint(
        'CHECK (eh_expand_page_size <= eh_gl_row_limit)',
        'Lazy Expand Page Size cannot exceed GL Row Limit.',
    )

    @api.constrains('eh_gl_row_limit', 'eh_expand_page_size')
    def _check_eh_report_resource_limits(self):
        for company in self:
            if company.eh_gl_row_limit <= 0:
                raise ValidationError(_(
                    "GL Row Limit must be greater than zero.",
                ))
            if company.eh_expand_page_size <= 0:
                raise ValidationError(_(
                    "Lazy Expand Page Size must be greater than zero.",
                ))
            if company.eh_expand_page_size > company.eh_gl_row_limit:
                raise ValidationError(_(
                    "Lazy Expand Page Size cannot exceed GL Row Limit.",
                ))

    # Reports Pro: forecasting defaults
    eh_forecast_default_horizon = fields.Integer(
        string="Default Forecast Horizon (months)",
        default=12,
    )
    eh_forecast_default_history_months = fields.Integer(
        string="Default Forecast History (months)",
        default=24,
    )

    # Assets and leases
    eh_asset_default_useful_life_months = fields.Integer(
        string="Default Asset Useful Life (months)",
        default=60,
    )
    eh_lease_default_term_months = fields.Integer(
        string="Default Lease Term (months)",
        default=36,
    )

    # Collections
    eh_collections_grace_days = fields.Integer(
        string="Collections Grace Days",
        default=14,
    )

    # AP Automation: parser defaults
    eh_ap_invoice_ref_regex = fields.Char(
        string="AP Invoice Ref Regex",
        default=r'(?im)Invoice[:#\s]+([A-Z0-9\-]+)',
    )
    eh_ap_total_regex = fields.Char(
        string="AP Total Amount Regex",
        default=r'(?im)Total[:\s]+([0-9][0-9,\.]*)',
    )

    # SEPA Direct Debit
    eh_sepa_dd_default_instrument = fields.Selection(
        [('CORE', "CORE (consumer)"),
         ('B2B', "B2B (business-to-business)")],
        string="Default SEPA DD Local Instrument",
        default='CORE',
    )

    # Approval workflow
    eh_approval_material_change_pct = fields.Float(
        string="Approval Material Change %",
        default=10.0,
        help=(
            "If a request amount changes by more than this percentage "
            "after first approval, the workflow re-approves from step zero."
        ),
    )

    # Profit and Loss by-function presentation (IAS 1.82/85).
    #
    # Finance Costs and Tax Expense have no dedicated Odoo account_type, so
    # the by-function income statement resolves them from these explicit
    # per-company account mappings. Left empty, both subtotals are zero and
    # Profit for the Period ties to the by-nature Net Profit unchanged.
    eh_pnl_finance_cost_account_ids = fields.Many2many(
        comodel_name='account.account',
        relation='eh_company_pnl_finance_cost_account_rel',
        column1='company_id',
        column2='account_id',
        string="Finance Cost Accounts",
        help=(
            "Expense accounts presented on the Finance Costs line of the "
            "by-function Profit and Loss. These are excluded from Operating "
            "Expenses so nothing is counted twice."
        ),
    )
    # Cash Flow Statement: cash and cash equivalents (IAS 7.6/7.46).
    #
    # By default only `asset_cash` accounts are treated as cash. Companies
    # holding short term, highly liquid investments (money market funds,
    # term deposits under three months) can mark those accounts here so
    # the Cash Flow Statement treats them as cash equivalents: transfers
    # between cash and these accounts are excluded from the activity
    # sections, and their balances count towards opening and closing cash.
    # Left empty, behaviour is unchanged.
    eh_cash_equivalent_account_ids = fields.Many2many(
        comodel_name='account.account',
        relation='eh_company_cash_equivalent_account_rel',
        column1='company_id',
        column2='account_id',
        string="Cash Equivalent Accounts",
        help=(
            "Accounts treated as cash equivalents on the Cash Flow "
            "Statement, alongside Bank and Cash accounts. Movements "
            "between cash and these accounts are presented as pure cash "
            "transfers (no activity), and their balances are included in "
            "the opening and closing cash position."
        ),
    )
    eh_pnl_tax_expense_account_ids = fields.Many2many(
        comodel_name='account.account',
        relation='eh_company_pnl_tax_expense_account_rel',
        column1='company_id',
        column2='account_id',
        string="Tax Expense Accounts",
        help=(
            "Expense accounts presented on the Tax Expense line of the "
            "by-function Profit and Loss. These are excluded from Operating "
            "Expenses so nothing is counted twice."
        ),
    )
    # Profit and Loss by-function: deferred tax split (IAS 1.82 / IAS 12.81(c)).
    #
    # The income statement must present current tax and deferred tax as
    # distinct amounts. Accounts marked here are the deferred-tax portion of
    # the Tax Expense mapping; the remainder is the current-tax portion. Left
    # empty, the by-function Profit and Loss shows a single Tax Expense line
    # exactly as before, so existing output is unchanged.
    eh_pnl_deferred_tax_account_ids = fields.Many2many(
        comodel_name='account.account',
        relation='eh_company_pnl_deferred_tax_account_rel',
        column1='company_id',
        column2='account_id',
        string="Deferred Tax Accounts",
        help=(
            "Tax-expense accounts whose movement is deferred tax. On the "
            "by-function Profit and Loss the Tax Expense subtotal is split "
            "into a Current Tax line and a Deferred Tax line; these accounts "
            "form the Deferred Tax line, and the remaining Tax Expense "
            "accounts form the Current Tax line. Left empty, a single Tax "
            "Expense line is shown."
        ),
    )
    # Cash Flow Statement: additional exchange-difference journal (IAS 7.28).
    #
    # The FX effect on cash held is detected from moves posted in the
    # standard currency_exchange_journal_id. Some deployments post bank /
    # cash revaluation entries in a dedicated journal instead (for example a
    # month-end foreign-currency revaluation run). Set that journal here so
    # its cash-touching moves are recognised as exchange-rate effects rather
    # than leaking into the opening-to-closing difference. Left empty, the
    # detection seam and report output are unchanged.
    eh_cash_fx_revaluation_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string="Cash Revaluation Journal",
        help=(
            "Additional journal whose cash-touching entries revalue cash "
            "held for exchange-rate changes, presented on the Effect of "
            "exchange rate changes on cash line of the Cash Flow Statement, "
            "alongside the standard exchange difference journal."
        ),
    )
    # Cash Flow Statement: IAS 7.31/7.33/7.34 presentation policy.
    #
    # IAS 7.31 requires interest and dividends received and paid to be
    # disclosed separately, each classified in a consistent manner from
    # period to period. The standard allows a choice of section: interest
    # paid is usually operating but may be presented as financing; interest
    # and dividends received are usually operating but may be presented as
    # investing; dividends paid are usually financing but may be presented
    # as operating. These company-level defaults drive where the dedicated
    # disclosure lines appear on the Cash Flow Statement; a per-render
    # override is available through the report options. Income taxes paid
    # have no policy field: IAS 7.35 classifies them as operating unless
    # they can be specifically identified with financing or investing
    # activities, which this report does not attempt automatically.
    eh_cf_interest_paid_section = fields.Selection(
        [('operating', "Operating activities"),
         ('financing', "Financing activities")],
        string="Interest Paid Presentation",
        default='operating',
        help=(
            "Cash Flow Statement section carrying the Interest Paid "
            "disclosure line (IAS 7.31/7.33)."
        ),
    )
    eh_cf_interest_received_section = fields.Selection(
        [('operating', "Operating activities"),
         ('investing', "Investing activities")],
        string="Interest Received Presentation",
        default='operating',
        help=(
            "Cash Flow Statement section carrying the Interest Received "
            "disclosure line (IAS 7.31/7.33)."
        ),
    )
    eh_cf_dividends_paid_section = fields.Selection(
        [('financing', "Financing activities"),
         ('operating', "Operating activities")],
        string="Dividends Paid Presentation",
        default='financing',
        help=(
            "Cash Flow Statement section carrying the Dividends Paid "
            "disclosure line (IAS 7.31/7.34)."
        ),
    )
    eh_cf_dividends_received_section = fields.Selection(
        [('operating', "Operating activities"),
         ('investing', "Investing activities")],
        string="Dividends Received Presentation",
        default='operating',
        help=(
            "Cash Flow Statement section carrying the Dividends Received "
            "disclosure line (IAS 7.31/7.33)."
        ),
    )
    # Cash Flow Statement: income-taxes-paid fallback measurement (IAS 7.35).
    #
    # With no account tagged EH Income Tax Paid the report can fall back to
    # measuring the Income Taxes Paid line from cash settlements against the
    # accounts named as tax repartition targets (the tax-authority payables
    # core Odoo posts tax to). That measurement cannot distinguish income
    # tax from indirect taxes (VAT / GST remittances qualify), so it is
    # strictly opt-in: left off (the default) an untagged book shows no
    # Income Taxes Paid line and the statement is unchanged. Tagging the
    # income tax accounts is always the accurate configuration; this switch
    # is for books that want a taxes-paid line without tagging and accept
    # the mixed measurement.
    eh_cf_tax_fallback = fields.Boolean(
        string="Taxes Paid Fallback",
        default=False,
        help=(
            "Without any account tagged EH Income Tax Paid, show an Income "
            "Taxes Paid line on the Cash Flow Statement measured from cash "
            "settlements against the tax repartition target accounts. "
            "Includes indirect tax (VAT/GST) remittances; tag the income "
            "tax accounts instead for an exact line."
        ),
    )

    # Report presentation-policy fields. A change to any of these changes
    # report output (by-function P&L mapping, cash-flow sectioning, cash-
    # equivalent set), yet none of them move a journal entry, so without a
    # bump here the reporting cache would serve figures/labels computed under
    # the old configuration until an unrelated move posts.
    _EH_REPORT_CONFIG_FIELDS = frozenset({
        'eh_pnl_finance_cost_account_ids', 'eh_pnl_tax_expense_account_ids',
        'eh_pnl_deferred_tax_account_ids', 'eh_cash_equivalent_account_ids',
        'eh_cf_interest_paid_section', 'eh_cf_interest_received_section',
        'eh_cf_dividends_paid_section', 'eh_cf_dividends_received_section',
        'eh_cf_tax_fallback', 'eh_cash_fx_revaluation_journal_id',
        'eh_gl_row_limit', 'eh_expand_page_size', 'currency_id',
        'currency_exchange_journal_id',
        'income_currency_exchange_account_id',
        'expense_currency_exchange_account_id',
        'fiscalyear_last_day', 'fiscalyear_last_month',
        'account_fiscal_country_id', 'parent_id', 'partner_id',
        'active',
    })

    @api.model_create_multi
    def create(self, vals_list):
        if (
            any('eh_move_version' in vals for vals in vals_list)
            or self.env.context.get('default_eh_move_version')
        ):
            raise AccessError(_(
                "The report-input version counter is server-owned and "
                "cannot be supplied when creating a company."
            ))
        create_context = dict(self.env.context)
        create_context.pop('default_eh_move_version', None)
        create_self = self.with_context(create_context)
        companies = super(ResCompany, create_self).create(vals_list)
        companies._eh_bump_move_version(companies.ids)
        return companies

    def write(self, vals):
        # ``readonly=True`` only controls clients; RPC callers may still
        # submit the field explicitly.  Only the atomic SQL helper below may
        # advance this monotonic freshness counter.  Reject ORM writes even
        # under sudo so no generic elevated path can rewind it and revive a
        # stale financial-report cache entry.
        if 'eh_move_version' in vals:
            raise AccessError(_(
                "The report-input version counter is server-owned and "
                "cannot be edited directly."
            ))
        commercial_projection_moves = self.env['account.move']
        if 'partner_id' in vals and self:
            # ``hr_expense``'s commercial-root rule compares the move partner
            # with company.partner_id, but core does not declare that nested
            # dependency. Snapshot the moves before changing company identity,
            # then recompute through Base's narrow installed-MRO helper.
            commercial_projection_moves = self.env[
                'account.move'
            ].sudo().search([('company_id', 'in', self.ids)])
        moved_subtree_ids = set()
        if 'parent_id' in vals and self:
            moved_subtree_ids.update(self.sudo().with_context(
                active_test=False,
            ).search([
                ('id', 'child_of', self.ids),
            ]).ids)
        res = super().write(vals)
        if self._EH_REPORT_CONFIG_FIELDS.intersection(vals):
            bump_ids = set(self.ids)
            if 'parent_id' in vals:
                moved_subtree_ids.update(self.sudo().with_context(
                    active_test=False,
                ).search([
                    ('id', 'child_of', self.ids),
                ]).ids)
                bump_ids.update(moved_subtree_ids)
            self._eh_bump_move_version(bump_ids)
        if commercial_projection_moves:
            # Imported lazily because this module precedes account_move in
            # models/__init__.py; at runtime the complete registry is loaded.
            from .account_move import (
                _EH_COMMERCIAL_PROJECTION_REFRESH,
                _EH_COMMERCIAL_PROJECTION_REFRESH_CAPABILITY,
            )
            commercial_projection_moves.with_context(**{
                _EH_COMMERCIAL_PROJECTION_REFRESH:
                    _EH_COMMERCIAL_PROJECTION_REFRESH_CAPABILITY,
            })._eh_refresh_commercial_projection()
        return res

    @api.model
    @api.private
    def _eh_bump_move_version(self, company_ids):
        """Atomically advance isolated counters for affected companies.

        The upsert retains the required commit-order serialization only for
        writers affecting the same company's report inputs. It never locks a
        ``res_company`` row, and it never touches unrelated companies.
        """
        ids = tuple(sorted({int(company_id) for company_id in company_ids}))
        if not ids:
            return
        self.env.cr.execute(
            "SELECT to_regclass('eh_account_report_company_version')"
        )
        if not self.env.cr.fetchone()[0]:
            # Only reachable while this addon is creating its own schema.
            return
        self.env.cr.execute(
            "INSERT INTO eh_account_report_company_version "
            "(company_id, version) "
            "SELECT id, 1 FROM res_company WHERE id IN %s "
            "ON CONFLICT (company_id) DO UPDATE SET version = "
            "eh_account_report_company_version.version + 1",
            (ids,),
        )
        self.env['res.company'].browse(ids).invalidate_recordset(
            ['eh_move_version'],
        )

    @api.model
    @api.private
    def _eh_bump_global_report_version(self):
        """Advance the singleton epoch for shared report presentation inputs."""
        self.env.cr.execute(
            "SELECT to_regclass('eh_account_report_global_version')"
        )
        if not self.env.cr.fetchone()[0]:
            return
        self.env.cr.execute(
            "INSERT INTO eh_account_report_global_version (id, version) "
            "VALUES (1, 1) ON CONFLICT (id) DO UPDATE SET version = "
            "eh_account_report_global_version.version + 1"
        )
        self.sudo().with_context(active_test=False).search([]).invalidate_recordset(
            ['eh_move_version'],
        )
