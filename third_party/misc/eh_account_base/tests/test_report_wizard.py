# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Tests for eh.account.report.wizard.

Covers:

* Default options dict structure mirrors what handlers expect.
* Date constraint: date_from must not be later than date_to.
* action_export_xlsx returns a download action and creates an attachment.
* Empty company_ids selection falls back to the active company.
"""

import base64
from unittest.mock import patch

from datetime import date, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import EhAccountUnitTestCase

WIZARD_TEST_HANDLER = 'eh.account.dynamic.report.handler'


def _wizard_payload():
    return {
        'columns': [
            {'expression_label': 'account', 'name': 'Account',
             'figure_type': 'string'},
            {'expression_label': 'value', 'name': 'Value',
             'figure_type': 'monetary'},
        ],
        'lines': [
            {'id': 'l1', 'name': 'Test Line', 'level': 1,
             'columns': [{'expression_label': 'value', 'value': 42.0}]},
        ],
        'totals': {'value': 42.0},
        'generated_at': '2026-01-01T00:00:00',
    }


@tagged('eh_account_base', 'integration', 'post_install', '-at_install')
class TestReportWizard(EhAccountUnitTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fiscal_test_company = cls.env.company
        cls.original_user_company = cls.env.user.company_id
        cls.original_fiscal_calendar = {
            'fiscalyear_last_month': (
                cls.fiscal_test_company.fiscalyear_last_month
            ),
            'fiscalyear_last_day': cls.fiscal_test_company.fiscalyear_last_day,
        }
        # Calendar-based expectations below must not depend on the locale of
        # the no-demo database used by a particular Odoo series.
        cls.fiscal_test_company.sudo().write({
            'fiscalyear_last_month': '12',
            'fiscalyear_last_day': 31,
        })
        cls.report = cls.env['eh.account.dynamic.report'].create({
            'code': 'wizard_test',
            'name': 'Wizard Test',
            'handler_model': WIZARD_TEST_HANDLER,
        })

    @classmethod
    def tearDownClass(cls):
        try:
            cls.fiscal_test_company.sudo().write(
                cls.original_fiscal_calendar,
            )
            # Company creation updates the current user's company set in
            # Odoo 17 and resets lazy environment-company properties. Pin the
            # main company again so this class cannot leak a test company.
            cls.env.user.sudo().write({
                'company_id': cls.original_user_company.id,
            })
        finally:
            super().tearDownClass()

    def _make_wizard(self, **overrides):
        vals = {
            'report_id': self.report.id,
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
            'posted_only': True,
            'show_zero': False,
        }
        vals.update(overrides)
        return self.env['eh.account.report.wizard'].create(vals)

    def test_build_options_shape(self):
        wizard = self._make_wizard()
        options = wizard._build_options()
        self.assertIn('date', options)
        self.assertEqual(options['date']['date_from'], '2026-01-01')
        self.assertEqual(options['date']['date_to'], '2026-12-31')
        self.assertTrue(options['posted_only'])
        self.assertFalse(options['show_zero'])
        self.assertIn(self.env.company.id, options['company_ids'])

    def test_build_options_includes_partner_and_account_filters(self):
        partner = self.env['res.partner'].create({'name': 'Filtered'})
        wizard = self._make_wizard(partner_ids=[(6, 0, [partner.id])])
        options = wizard._build_options()
        self.assertEqual(options['partner_ids'], [partner.id])

    def test_invalid_date_range_raises(self):
        # Odoo 19's _assertRaises only accepts a single class. The wizard
        # raises UserError (constraints fire there).
        with self.assertRaises(UserError):
            self._make_wizard(
                date_from='2026-12-31',
                date_to='2026-01-01',
            )

    def test_action_export_xlsx_creates_attachment_and_returns_url(self):
        wizard = self._make_wizard()
        HandlerClass = type(self.env[WIZARD_TEST_HANDLER])
        with patch.object(
            HandlerClass,
            'compute',
            return_value=_wizard_payload(),
        ):
            action = wizard.action_export_xlsx()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertIn('/web/content/', action['url'])
        # The attachment should exist and contain XLSX bytes.
        attachment_id = int(
            action['url'].split('/web/content/')[1].split('?')[0]
        )
        attachment = self.env['ir.attachment'].browse(attachment_id)
        self.assertTrue(attachment.exists())
        self.assertEqual(
            attachment.mimetype,
            'application/vnd.openxmlformats-officedocument'
            '.spreadsheetml.sheet',
        )
        # First two bytes of any XLSX (ZIP container) are 'PK'.
        decoded = base64.b64decode(attachment.datas)
        self.assertEqual(decoded[:2], b'PK')
        self.assertIn('wizard_test', attachment.name)

    def test_report_definition_opens_executable_wizard_action(self):
        action = self.report.action_open_run_wizard()
        self.assertEqual(action['res_model'], 'eh.account.report.wizard')
        self.assertEqual(action['target'], 'new')
        self.assertEqual(action['context']['default_report_id'], self.report.id)
        self.assertIn(
            self.env.company.id,
            action['context']['allowed_company_ids'],
        )

    def test_default_company_when_none_selected(self):
        wizard = self._make_wizard(company_ids=[(6, 0, [])])
        # The constraint requires company_ids; clear via write to bypass.
        self.env.cr.execute(
            "DELETE FROM eh_account_report_wizard_company_rel "
            "WHERE wizard_id = %s",
            (wizard.id,),
        )
        wizard.invalidate_recordset(['company_ids'])
        options = wizard._build_options()
        self.assertEqual(options['company_ids'], [self.env.company.id])

    def test_build_options_rejects_company_outside_active_scope(self):
        foreign = self.env['res.company'].sudo().create({
            'name': 'Wizard Foreign Company',
        })
        Wizard = self.env['eh.account.report.wizard'].with_context(
            allowed_company_ids=[self.env.company.id],
        )
        wizard = Wizard.create({
            'report_id': self.report.id,
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.env.cr.execute(
            "INSERT INTO eh_account_report_wizard_company_rel "
            "(wizard_id, company_id) VALUES (%s, %s)",
            (wizard.id, foreign.id),
        )
        wizard.invalidate_recordset(['company_ids'])
        with self.assertRaisesRegex(
                ValidationError, 'active allowed company scope'):
            wizard._build_options()

    def test_report_presentation_policies_are_exposed_in_settings(self):
        field_names = {
            'eh_pnl_finance_cost_account_ids',
            'eh_pnl_tax_expense_account_ids',
            'eh_pnl_deferred_tax_account_ids',
            'eh_cash_equivalent_account_ids',
            'eh_cash_fx_revaluation_journal_id',
            'eh_cf_interest_paid_section',
            'eh_cf_interest_received_section',
            'eh_cf_dividends_paid_section',
            'eh_cf_dividends_received_section',
            'eh_cf_tax_fallback',
        }
        Settings = self.env['res.config.settings']
        self.assertTrue(field_names.issubset(Settings._fields))
        settings_view = self.env.ref(
            'eh_account_base.res_config_settings_view_form_eh',
            raise_if_not_found=False,
        )
        # Settings' ``<block>/<setting>`` architecture does not exist in
        # Odoo 16, so the backport deliberately drops this inherited view.
        # Keep testing model exposure and persistence on that series; inspect
        # the view whenever the core architecture can load it.
        if settings_view:
            for field_name in field_names:
                self.assertIn(
                    'name="%s"' % field_name, settings_view.arch_db,
                )

        settings = Settings.create({
            'company_id': self.env.company.id,
            'eh_cf_interest_paid_section': 'financing',
        })
        self.assertEqual(settings.eh_cf_interest_paid_section, 'financing')
        self.assertEqual(
            self.env.company.eh_cf_interest_paid_section, 'financing',
        )

    def test_optional_settings_blocks_follow_installed_modules(self):
        settings = self.env['res.config.settings'].create({
            'company_id': self.env.company.id,
        })
        mapping = {
            'eh_forecast_module_installed':
                'eh_account_dynamic_reports_pro',
            'eh_assets_module_installed': 'eh_account_assets_pro',
            'eh_collections_module_installed': 'eh_account_collections',
            'eh_approval_module_installed': 'eh_account_approval',
            'eh_sepa_dd_module_installed': 'eh_account_sepa_dd',
            'eh_ap_automation_module_installed':
                'eh_account_ap_automation',
        }
        installed = set(self.env['ir.module.module'].sudo().search([
            ('name', 'in', list(mapping.values())),
            ('state', '=', 'installed'),
        ]).mapped('name'))
        for field_name, module_name in mapping.items():
            self.assertEqual(bool(settings[field_name]), module_name in installed)

        view = self.env.ref(
            'eh_account_base.res_config_settings_view_form_eh',
            raise_if_not_found=False,
        )
        if view:
            self.assertIn(
                'invisible="not eh_forecast_module_installed"',
                view.arch_db,
            )
            self.assertIn(
                'invisible="not eh_assets_module_installed"',
                view.arch_db,
            )

    def test_company_report_resource_limits_are_positive_and_relational(self):
        Company = self.env.company
        for vals, message in (
            ({'eh_gl_row_limit': 0}, 'GL Row Limit'),
            ({'eh_expand_page_size': 0}, 'Lazy Expand Page Size'),
            ({
                'eh_gl_row_limit': 50,
                'eh_expand_page_size': 51,
            }, 'cannot exceed'),
        ):
            with self.subTest(vals=vals), \
                    self.assertRaisesRegex(ValidationError, message), \
                    self.env.cr.savepoint():
                Company.write(vals)
            Company.invalidate_recordset(list(vals))

    # ---- period preset math ----

    def test_period_preset_mtd(self):
        Wizard = self.env['eh.account.report.wizard']
        df, dt = Wizard._period_preset_dates('mtd', date(2026, 5, 14))
        self.assertEqual(df, date(2026, 5, 1))
        self.assertEqual(dt, date(2026, 5, 14))

    def test_period_preset_qtd_q2(self):
        Wizard = self.env['eh.account.report.wizard']
        df, dt = Wizard._period_preset_dates(
            'qtd', date(2026, 5, 14), company=self.fiscal_test_company,
        )
        self.assertEqual(df, date(2026, 4, 1))
        self.assertEqual(dt, date(2026, 5, 14))

    def test_period_preset_qtd_q4(self):
        Wizard = self.env['eh.account.report.wizard']
        df, dt = Wizard._period_preset_dates(
            'qtd', date(2026, 11, 14), company=self.fiscal_test_company,
        )
        self.assertEqual(df, date(2026, 10, 1))
        self.assertEqual(dt, date(2026, 11, 14))

    def test_period_preset_ytd(self):
        Wizard = self.env['eh.account.report.wizard']
        df, dt = Wizard._period_preset_dates(
            'ytd', date(2026, 5, 14), company=self.fiscal_test_company,
        )
        self.assertEqual(df, date(2026, 1, 1))
        self.assertEqual(dt, date(2026, 5, 14))

    def test_period_preset_last_month(self):
        Wizard = self.env['eh.account.report.wizard']
        df, dt = Wizard._period_preset_dates('last_month', date(2026, 5, 14))
        self.assertEqual(df, date(2026, 4, 1))
        self.assertEqual(dt, date(2026, 4, 30))

    def test_period_preset_last_month_january(self):
        Wizard = self.env['eh.account.report.wizard']
        df, dt = Wizard._period_preset_dates('last_month', date(2026, 1, 14))
        self.assertEqual(df, date(2025, 12, 1))
        self.assertEqual(dt, date(2025, 12, 31))

    def test_period_preset_last_quarter(self):
        Wizard = self.env['eh.account.report.wizard']
        # Q2 -> last quarter is Q1.
        df, dt = Wizard._period_preset_dates(
            'last_quarter', date(2026, 5, 14),
            company=self.fiscal_test_company,
        )
        self.assertEqual(df, date(2026, 1, 1))
        self.assertEqual(dt, date(2026, 3, 31))
        # Q1 -> last quarter is prior-year Q4.
        df, dt = Wizard._period_preset_dates(
            'last_quarter', date(2026, 2, 1),
            company=self.fiscal_test_company,
        )
        self.assertEqual(df, date(2025, 10, 1))
        self.assertEqual(dt, date(2025, 12, 31))

    def test_period_preset_last_year(self):
        Wizard = self.env['eh.account.report.wizard']
        df, dt = Wizard._period_preset_dates(
            'last_year', date(2026, 5, 14),
            company=self.fiscal_test_company,
        )
        self.assertEqual(df, date(2025, 1, 1))
        self.assertEqual(dt, date(2025, 12, 31))

    def test_fiscal_presets_follow_non_calendar_company_year(self):
        company = self.env['res.company'].create({
            'name': 'July-June Fiscal Calendar',
            'parent_id': False,
            'fiscalyear_last_month': '6',
            'fiscalyear_last_day': 30,
        })
        Wizard = self.env[
            'eh.account.report.wizard'
        ].with_company(company)
        today = date(2026, 5, 14)
        self.assertEqual(
            Wizard._period_preset_dates('ytd', today),
            (date(2025, 7, 1), today),
        )
        self.assertEqual(
            Wizard._period_preset_dates('qtd', today),
            (date(2026, 4, 1), today),
        )
        self.assertEqual(
            Wizard._period_preset_dates('last_quarter', today),
            (date(2026, 1, 1), date(2026, 3, 31)),
        )
        self.assertEqual(
            Wizard._period_preset_dates('last_year', today),
            (date(2024, 7, 1), date(2025, 6, 30)),
        )

    def test_fiscal_preset_rejects_mixed_company_calendars(self):
        calendar = self.env['res.company'].create({
            'name': 'Calendar Fiscal Year',
            'parent_id': False,
            'fiscalyear_last_month': '12',
            'fiscalyear_last_day': 31,
        })
        july_june = self.env['res.company'].create({
            'name': 'July-June Fiscal Year',
            'parent_id': False,
            'fiscalyear_last_month': '6',
            'fiscalyear_last_day': 30,
        })
        wizard = self._make_wizard(
            company_ids=[(6, 0, [calendar.id, july_june.id])],
            period_preset='ytd',
        )
        with self.assertRaises(ValidationError):
            wizard._onchange_period_preset()
