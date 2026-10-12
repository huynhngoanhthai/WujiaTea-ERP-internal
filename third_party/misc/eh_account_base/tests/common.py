# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Shared test fixtures for the ERP Heritage accounting suite.

Two base classes:

* EhAccountUnitTestCase: pure unit tests, no DB seeding beyond what TransactionCase
  already provides. Use for SQL builder shape assertions, cache layer tests,
  options canonicalisation tests.
* EhAccountIntegrationTestCase: integration tests that need a chart of accounts
  and a posted journal entry. The setUpClass seeds a minimal CoA and a
  reusable balanced entry.
"""

from odoo import fields
from odoo.tests import TransactionCase, new_test_user


class EhAccountUnitTestCase(TransactionCase):
    """Lightweight base class. No accounting fixtures.

    Suitable for tests that exercise pure Python helpers (SQL builder, cache,
    canonicalisation) and only need self.env.cr to be available.
    """


class EhAccountIntegrationTestCase(TransactionCase):
    """Integration base class with a seeded chart of accounts and partners."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls._original_fiscal_calendar = {
            'fiscalyear_last_day': cls.company.fiscalyear_last_day,
            'fiscalyear_last_month': cls.company.fiscalyear_last_month,
        }
        # Calendar-year expectations in the shared accounting fixtures must
        # be deterministic across no-demo databases. Odoo 17's Australian
        # localisation seeds a June year-end; individual non-calendar tests
        # opt into that policy explicitly and restore it afterwards.
        cls.company.sudo().write({
            'fiscalyear_last_day': 31,
            'fiscalyear_last_month': '12',
        })
        # Odoo 16 refuses to post a mail message when the author has no email
        # ("Unable to send message, please configure the sender's email
        # address"); 17+ tolerate it. Workflows here post chatter/activities,
        # so give the acting user and company a sender address.
        if not cls.env.user.email:
            cls.env.user.email = 'eh-tester@example.com'
        if not cls.company.email:
            cls.company.email = 'eh-company@example.com'
        # Pin the company currency to USD so currency-sensitive tests behave
        # identically across series: Odoo 16 defaults the company currency to
        # EUR while 17/18/19 default to USD, which otherwise makes a test that
        # writes an EUR rate skip it (a company never rates its own currency).
        # Safe here because no journal entry exists yet.
        usd = cls.env.ref('base.USD')
        if not usd.active:
            usd.sudo().write({'active': True})
        if cls.company.currency_id != usd:
            cls.company.sudo().write({'currency_id': usd.id})
        # Keep shared accounting fixtures tax-neutral. Odoo 16 seeds a 5%
        # company default tax while later no-demo databases do not, which
        # silently changes invoice totals whenever a test intentionally omits
        # tax_ids. Tax-specific tests set their taxes explicitly.
        default_tax_vals = {}
        for field_name in ('account_sale_tax_id', 'account_purchase_tax_id'):
            if field_name in cls.company._fields and cls.company[field_name]:
                default_tax_vals[field_name] = False
        if default_tax_vals:
            cls.company.sudo().write(default_tax_vals)
        # A true upgrade runs post-install tests in a database that can still
        # contain chart-template groups seeded by the baseline series.  The
        # shared fixture promises a minimal chart, so remove that ambient
        # hierarchy before creating its accounts.  TransactionCase rolls this
        # test-only isolation back; production chart data is never changed.
        cls._isolate_account_groups(cls.env, cls.company)
        # Bank journals inherit their suspense and outstanding-payment
        # accounts from these company defaults. On a demo-less Odoo 16
        # company they are unset, so bank statement lines and payments are
        # refused ("no Suspense Account configured"). Provision them so any
        # bank journal a test creates works; 17/18/19 already have them.
        suspense = cls._ensure_account(
            cls.env, '1099', 'Bank Suspense', 'asset_current')
        # A bank journal's suspense account is reconcilable in real Odoo;
        # reclassifying a statement line's residual clears the counter-leg
        # against the original suspense line, which requires reconciliation.
        # Provision it as such here so fixtures mirror a correctly
        # configured chart of accounts.
        if not suspense.reconcile:
            suspense.sudo().reconcile = True
        outstanding = cls._ensure_account(
            cls.env, '1098', 'Outstanding Payments', 'asset_current')
        # Outstanding receipt/payment accounts must be reconcilable: Odoo
        # validates that a company payment debit/credit account is a
        # reconcilable account.
        if not outstanding.reconcile:
            outstanding.sudo().reconcile = True
        comp_vals = {}
        comp_fields = cls.company._fields
        if ('account_journal_suspense_account_id' in comp_fields
                and not cls.company.account_journal_suspense_account_id):
            comp_vals['account_journal_suspense_account_id'] = suspense.id
        for fname in ('account_journal_payment_debit_account_id',
                      'account_journal_payment_credit_account_id'):
            if fname in comp_fields and not cls.company[fname]:
                comp_vals[fname] = outstanding.id
        if comp_vals:
            cls.company.sudo().write(comp_vals)

        cls.account_receivable = cls._ensure_account(
            cls.env, '1100', 'Trade Receivables', 'asset_receivable',
        )
        cls.account_payable = cls._ensure_account(
            cls.env, '2100', 'Trade Payables', 'liability_payable',
        )
        cls.account_revenue = cls._ensure_account(
            cls.env, '4000', 'Sales Revenue', 'income',
        )
        cls.account_expense = cls._ensure_account(
            cls.env, '5000', 'Cost of Sales', 'expense',
        )
        cls.account_cash = cls._ensure_account(
            cls.env, '1000', 'Cash on Hand', 'asset_cash',
        )
        cls.account_equity = cls._ensure_account(
            cls.env, '3000', 'Owner Equity', 'equity',
        )

        cls.journal_misc = cls._ensure_journal(
            cls.env, cls.company, 'general', 'MISC', 'Miscellaneous',
        )
        # Odoo 17/18/19 auto-provision sale/purchase journals on the company;
        # Odoo 16 with --without-demo does not, so tests that create customer
        # invoices or vendor bills fail at posting with "No journal ... for
        # sale/purchase". Provision them explicitly (search-first, so nothing
        # changes on versions that already have them).
        cls.journal_sale = cls._ensure_journal(
            cls.env, cls.company, 'sale', 'INV', 'Customer Invoices',
            default_account=cls.account_revenue,
        )
        cls.journal_purchase = cls._ensure_journal(
            cls.env, cls.company, 'purchase', 'BILL', 'Vendor Bills',
            default_account=cls.account_expense,
        )

        # On a demo-less Odoo 16/17 company there is no chart-of-accounts
        # template, so partners have no default receivable/payable account
        # ("Partner X has no receivable account configured"). Set the
        # company-wide property defaults so every partner (existing and new)
        # resolves to these accounts. Odoo 18 removed ir.property (replaced by
        # company-dependent fields) and provisions these differently, so this
        # only runs where ir.property exists.
        if 'ir.property' in cls.env.registry:
            IrProperty = cls.env['ir.property'].sudo()
            for prop_name, account in (
                ('property_account_receivable_id', cls.account_receivable),
                ('property_account_payable_id', cls.account_payable),
            ):
                if not IrProperty._get(prop_name, 'res.partner'):
                    IrProperty._set_default(
                        prop_name, 'res.partner', account, company=cls.company)
            # Product category income/expense defaults, so an invoice line
            # with a product resolves an account on a demo-less 16 company.
            for prop_name, account in (
                ('property_account_income_categ_id', cls.account_revenue),
                ('property_account_expense_categ_id', cls.account_expense),
            ):
                if not IrProperty._get(prop_name, 'product.category'):
                    IrProperty._set_default(
                        prop_name, 'product.category', account,
                        company=cls.company)

        cls.partner_a = cls.env['res.partner'].create({'name': 'Test Partner A'})
        cls.partner_b = cls.env['res.partner'].create({'name': 'Test Partner B'})

    @classmethod
    def tearDownClass(cls):
        try:
            cls.company.sudo().write(cls._original_fiscal_calendar)
        finally:
            super().tearDownClass()

    @staticmethod
    def _ensure_account(env, code, name, account_type):
        # account.account became multi-company (company_ids, Many2many) in
        # Odoo 18; before that it carries a single company_id. Resolve the
        # field at runtime so the helper works across series.
        Account = env['account.account']
        multi = 'company_ids' in Account._fields
        company_field = 'company_ids' if multi else 'company_id'
        company_value = (
            [(6, 0, env.company.ids)] if multi else env.company.id)
        existing = Account.search(
            [
                ('code', '=', code),
                (company_field, 'in', env.company.ids),
            ],
            limit=1,
        )
        if existing:
            return existing
        vals = {
            'code': code,
            'name': name,
            'account_type': account_type,
            company_field: company_value,
        }
        # Reconcilable types must carry reconcile=True for amount_residual to
        # compute correctly. Aged receivable/payable tests rely on this.
        if account_type in (
            'asset_receivable', 'liability_payable', 'liability_credit_card',
        ):
            vals['reconcile'] = True
        return env['account.account'].create(vals)

    @staticmethod
    def _ensure_journal(env, company, jtype, code, name, default_account=None):
        """Return the company's journal of the given type, creating a minimal
        one if the framework did not provision it (Odoo 16 without demo)."""
        Journal = env['account.journal']
        journal = Journal.search(
            [('company_id', '=', company.id), ('type', '=', jtype)], limit=1,
        )
        if journal:
            # Localisations can provision the journal without a default
            # account.  Tests that later omit an invoice-line account still
            # need the same deterministic fixture as a freshly created
            # journal.  Preserve every non-empty localisation choice.
            if default_account is not None and not journal.default_account_id:
                journal.with_company(company).write({
                    'default_account_id': default_account.id,
                })
            return journal
        vals = {
            'name': name, 'code': code, 'type': jtype,
            'company_id': company.id,
        }
        if default_account is not None:
            vals['default_account_id'] = default_account.id
        return Journal.create(vals)

    @staticmethod
    def _isolate_account_groups(env, company):
        """Remove chart-seeded account groups from the minimal test chart."""
        root_company = (
            company.root_id if 'root_id' in company._fields else company
        )
        env['account.group'].with_company(company).search([
            ('company_id', '=', root_company.id),
        ]).unlink()

    def _create_accounting_branch(self, vals):
        """Create a branch after loading its inherited chart deterministically.

        Odoo 17 defers a branch's chart-template load to a precommit hook.  The
        shared fixture normalises the root company's fiscal calendar after its
        localisation was loaded, so replaying that localisation directly on a
        new branch would temporarily restore the template calendar and violate
        Odoo's root-delegated fiscal-year constraint.  Load under the original
        template calendar, then restore the normalised calendar on the root;
        Odoo propagates that delegated value to the new branch.
        """
        Company = self.env['res.company']
        branch_vals = dict(vals)
        parent = Company.browse(branch_vals.get('parent_id')).exists()
        if not parent:
            return Company.create(branch_vals)

        root = parent.root_id if 'root_id' in Company._fields else parent
        current_calendar = {
            'fiscalyear_last_day': root.fiscalyear_last_day,
            'fiscalyear_last_month': root.fiscalyear_last_month,
        }
        original_calendar = getattr(
            self, '_original_fiscal_calendar', current_calendar,
        )
        must_restore_template_calendar = (
            'parent_ids' in Company._fields
            and root == self.company.root_id
            and current_calendar != original_calendar
            and bool(getattr(root, 'chart_template', False))
        )

        if must_restore_template_calendar:
            with self.env.cr.savepoint():
                root.sudo().write(original_calendar)
                branch = Company.create(branch_vals)
                self.env.cr.flush()
            # Odoo 17 propagates root-delegated fields to branches one field
            # at a time in sorted name order.  A combined 30-Jun -> 31-Dec
            # write therefore applies day=31 while the branch still carries
            # month=Jun and fails the calendar constraint.  Day 1 is valid in
            # every month and provides a constraint-safe transition while
            # keeping root and branch values identical after every write.
            root.sudo().write({'fiscalyear_last_day': 1})
            root.sudo().write({
                'fiscalyear_last_month':
                    current_calendar['fiscalyear_last_month'],
            })
            root.sudo().write({
                'fiscalyear_last_day':
                    current_calendar['fiscalyear_last_day'],
            })
            return branch

        branch = Company.create(branch_vals)
        self.env.cr.flush()
        return branch

    @classmethod
    def _bank_validator_user(cls, company=None):
        """Return a non-super user allowed to manage partner-bank trust.

        Odoo 17+ deliberately refuses trust changes made by the superuser
        outside install mode.  Tests must exercise the same authorised
        corridor as a real operator.  Odoo 16 has the trust field but not the
        dedicated validation group, so resolve that group only when present.
        """
        company = company or cls.company
        users = cls.__dict__.get('_eh_bank_validator_users')
        if users is None:
            users = {}
            cls._eh_bank_validator_users = users
        user = users.get(company.id)
        if user and user.exists():
            return user

        groups = ['base.group_user', 'base.group_partner_manager']
        if cls.env.ref(
            'account.group_validate_bank_account',
            raise_if_not_found=False,
        ):
            groups.append('account.group_validate_bank_account')
        user = new_test_user(
            cls.env,
            login='eh_bank_validator_%s_%s' % (
                cls.__name__.lower(), company.id,
            ),
            groups=','.join(groups),
            company_id=company.id,
        )
        users[company.id] = user
        return user

    @classmethod
    def _create_partner_bank_as_validator(cls, vals):
        """Create a partner bank through the authorised trust actor."""
        Bank = cls.env['res.partner.bank']
        bank_vals = dict(vals)
        if 'allow_out_payment' not in Bank._fields:
            bank_vals.pop('allow_out_payment', None)
        partner = cls.env['res.partner'].browse(
            bank_vals.get('partner_id'),
        )
        company = partner.company_id or cls.company
        validator = cls._bank_validator_user(company)
        return Bank.with_user(validator).create(bank_vals)

    @classmethod
    def _write_partner_bank_as_validator(cls, bank, vals):
        """Update bank master/trust fields through the authorised actor."""
        bank_vals = dict(vals)
        if 'allow_out_payment' not in bank._fields:
            bank_vals.pop('allow_out_payment', None)
        company = bank.company_id or bank.partner_id.company_id or cls.company
        validator = cls._bank_validator_user(company)
        return bank.with_user(validator).write(bank_vals)

    @classmethod
    def post_balanced_move(cls, lines, journal=None, date=None):
        """Helper: create and post a balanced journal entry.

        :param lines: list of dicts with keys: account (required), debit,
            credit, partner, name, date_maturity.
        :param journal: optional account.journal record (defaults to misc).
        :param date: optional date (defaults to today).
        :return: the posted account.move record.
        """
        journal = journal or cls.journal_misc
        date = date or fields.Date.today()
        line_vals = []
        for line in lines:
            vals = {
                'account_id': line['account'].id,
                'debit': line.get('debit', 0.0),
                'credit': line.get('credit', 0.0),
                'partner_id': line['partner'].id if line.get('partner') else False,
                'name': line.get('name', '/'),
            }
            if 'date_maturity' in line:
                vals['date_maturity'] = line['date_maturity']
            line_vals.append((0, 0, vals))
        move = cls.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': date,
            'line_ids': line_vals,
        })
        move.action_post()
        return move
