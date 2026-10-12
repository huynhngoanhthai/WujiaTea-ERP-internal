# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
eh.account.report.wizard: transient model that gathers report parameters
from the user and triggers the render and export pipeline.

Generic enough to drive every dynamic report. Concrete report addons add
window actions that pre fill report_id via context, so the user lands on a
form already scoped to a single report.
"""

import base64
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EhAccountReportWizard(models.TransientModel):
    _name = 'eh.account.report.wizard'
    _description = "ERP Heritage report run wizard"

    report_id = fields.Many2one(
        'eh.account.dynamic.report',
        required=True,
        ondelete='cascade',
        help="Report definition the wizard runs against.",
    )
    report_code = fields.Char(related='report_id.code', readonly=True)

    period_preset = fields.Selection(
        [
            ('mtd', "Month to Date"),
            ('qtd', "Quarter to Date"),
            ('ytd', "Year to Date"),
            ('last_month', "Last Month"),
            ('last_quarter', "Last Quarter"),
            ('last_year', "Last Year"),
            ('custom', "Custom"),
        ],
        default='mtd',
        required=True,
        help=(
            "Quick period selector. MTD/QTD/YTD run from the start of "
            "the current month/quarter/fiscal year through today. The "
            "Last variants cover the most recently completed period. "
            "Custom unlocks Date From and Date To for free entry."
        ),
    )
    date_from = fields.Date(
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
        help="Inclusive start date of the reporting window.",
    )
    date_to = fields.Date(
        required=True,
        default=lambda self: fields.Date.context_today(self),
        help="Inclusive end date of the reporting window.",
    )

    company_ids = fields.Many2many(
        'res.company',
        'eh_account_report_wizard_company_rel',
        'wizard_id', 'company_id',
        required=True,
        default=lambda self: self.env.company,
        domain=lambda self: [('id', 'in', self.env.companies.ids)],
    )
    journal_ids = fields.Many2many(
        'account.journal',
        'eh_account_report_wizard_journal_rel',
        'wizard_id', 'journal_id',
    )
    partner_ids = fields.Many2many(
        'res.partner',
        'eh_account_report_wizard_partner_rel',
        'wizard_id', 'partner_id',
    )
    account_ids = fields.Many2many(
        'account.account',
        'eh_account_report_wizard_account_rel',
        'wizard_id', 'account_id',
    )

    hierarchical_groups = fields.Boolean(
        default=True,
        help=(
            "When set, P&L and Balance Sheet lines are nested under "
            "their account.group hierarchy with expand / collapse "
            "controls. When unset, accounts render as a flat list "
            "(useful when the chart of accounts has no groups "
            "configured)."
        ),
    )
    cash_flow_method = fields.Selection(
        [
            ('direct', "Direct"),
            ('indirect', "Indirect"),
        ],
        default='direct',
        help=(
            "Cash Flow Statement method. Direct shows cash receipts "
            "and payments by activity. Indirect starts from net income "
            "and adjusts for non-cash items and working-capital "
            "movements (preferred by most auditors). Only applies to "
            "the Cash Flow report; ignored elsewhere."
        ),
    )
    posted_only = fields.Boolean(
        default=True,
        help=(
            "When set, only entries in state=posted are included. "
            "Draft and cancelled entries are excluded. Recommended for "
            "reports that feed financial statements."
        ),
    )
    show_zero = fields.Boolean(
        default=False,
        help=(
            "When set, accounts and partners with a zero balance over "
            "the period are still rendered. Useful for full chart-of-"
            "accounts coverage; off by default to keep reports compact."
        ),
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_(
                    "Date From cannot be later than Date To.",
                ))

    @api.constrains('company_ids')
    def _check_company_scope(self):
        allowed = set(self.env.companies.ids)
        for wizard in self:
            # Inspect the module-owned relation itself after capturing the
            # caller's allowed scope.  Reading ``company_ids`` through the
            # ORM can hide an out-of-scope company behind res.company record
            # rules (or retain a pre-invalidation M2M cache value), which
            # would make this validation incorrectly conclude it is safe.
            self.env.cr.execute(
                "SELECT company_id "
                "FROM eh_account_report_wizard_company_rel "
                "WHERE wizard_id = %s",
                (wizard.id,),
            )
            selected = {row[0] for row in self.env.cr.fetchall()}
            forbidden = selected - allowed
            if forbidden:
                raise ValidationError(_(
                    "Selected companies must belong to the active allowed "
                    "company scope."
                ))

    @api.onchange('period_preset', 'company_ids')
    def _onchange_period_preset(self):
        """Recompute date_from / date_to when the user picks a preset.

        The custom preset leaves the dates alone so the user can set
        them by hand. Today's date is computed at onchange time, so
        opening the wizard in the morning vs the afternoon picks the
        same calendar period.
        """
        for rec in self:
            if rec.period_preset == 'custom' or not rec.period_preset:
                continue
            today = fields.Date.context_today(rec)
            companies = rec.company_ids or rec.env.company
            fiscal_calendars = {
                (
                    company.fiscalyear_last_month,
                    company.fiscalyear_last_day,
                )
                for company in companies
            }
            if (
                rec.period_preset in {
                    'qtd', 'ytd', 'last_quarter', 'last_year',
                }
                and len(fiscal_calendars) > 1
            ):
                raise ValidationError(_(
                    "A fiscal-period preset requires all selected companies "
                    "to share the same fiscal-year calendar."
                ))
            df, dt = rec._period_preset_dates(
                rec.period_preset,
                today,
                company=companies[:1],
            )
            rec.date_from = df
            rec.date_to = dt

    @api.model
    def _period_preset_dates(self, preset, today, company=None):
        """Return (date_from, date_to) for a named preset.

        Fiscal YTD, fiscal QTD, previous quarter, and previous year follow the
        selected company's configured fiscal calendar. Calendar-month presets
        remain calendar based. Callers may pass an explicit company; otherwise
        the active company owns the policy.
        """
        company = company or self.env.company
        fiscal_dates = company.compute_fiscalyear_dates(today)
        fiscal_start = fiscal_dates['date_from']
        quarter_start = fiscal_start
        while quarter_start + relativedelta(months=3) <= today:
            quarter_start += relativedelta(months=3)
        if preset == 'mtd':
            return today.replace(day=1), today
        if preset == 'qtd':
            return quarter_start, today
        if preset == 'ytd':
            return fiscal_start, today
        if preset == 'last_month':
            first_of_this_month = today.replace(day=1)
            last_month_end = first_of_this_month - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            return last_month_start, last_month_end
        if preset == 'last_quarter':
            return (
                quarter_start - relativedelta(months=3),
                quarter_start - timedelta(days=1),
            )
        if preset == 'last_year':
            prior_fiscal_dates = company.compute_fiscalyear_dates(
                fiscal_start - timedelta(days=1)
            )
            return (
                prior_fiscal_dates['date_from'],
                prior_fiscal_dates['date_to'],
            )
        return today.replace(day=1), today

    def _build_options(self):
        self.ensure_one()
        self._check_company_scope()
        company_ids = self.company_ids.ids or [self.env.company.id]
        return {
            'date': {
                'mode': 'range',
                'date_from': self.date_from.isoformat(),
                'date_to': self.date_to.isoformat(),
            },
            'company_ids': company_ids,
            'journal_ids': self.journal_ids.ids,
            'partner_ids': self.partner_ids.ids,
            'account_ids': self.account_ids.ids,
            'posted_only': bool(self.posted_only),
            'show_zero': bool(self.show_zero),
            'cash_flow_method': self.cash_flow_method or 'direct',
            'hierarchical_groups': bool(self.hierarchical_groups),
        }

    def action_export_xlsx(self):
        self.ensure_one()
        options = self._build_options()
        content = self.report_id.render_xlsx(options)
        filename = "%s_%s_to_%s.xlsx" % (
            self.report_id.code,
            self.date_from.isoformat(),
            self.date_to.isoformat(),
        )
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(content),
            'mimetype': (
                'application/vnd.openxmlformats-officedocument'
                '.spreadsheetml.sheet'
            ),
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'download',
        }
