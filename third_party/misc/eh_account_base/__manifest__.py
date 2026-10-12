# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
{
    'name': 'Accounting Suite Base',
    'summary': 'Shared reporting engine for the ERP Heritage Odoo 19 Community accounting suite, providing a reproducible report-execution audit log and a move-version result cache. Append-only audit log of every report render with user, timestamp, the full options snapshot, runtime, and a SHA-256 result hash for XLSX and PDF output, plus a multi-company analytic-aware parameterised SQL builder with no raw user input in SQL, a three-tier User/Manager/read-only Auditor privilege model, and a currency-aware XLSX writer. Odoo 19 Community accounting reporting engine, reproducible financial report audit trail, move-version report cache invalidation, multi-company parameterised SQL builder, append-only audit log, read-only auditor role, SHA-256 report hash compliance, currency-aware XLSX export, analytic-aware journal item aggregation.',
    'description': """The shared engine that powers the ERP Heritage accounting modules for Odoo 19 Community. It auto-installs as a dependency of any ERP Heritage accounting module, so you do not need to install it by hand.

What this module gives you directly

Reproducible report audit log. Every report render is recorded as an eh.account.report.execution row: who ran it, when, with the full options snapshot, how long it took, and a SHA-256 hash of the result (for XLSX and PDF output). Re-running a report from its stored options snapshot against an unchanged ledger returns the same cached payload, so the figures reproduce exactly. The log is append-only.

Precise cache invalidation. A server-owned per-company report-input counter is incremented atomically for posted-ledger changes and report-visible master data, configuration, exchange rates, and supported suite sub-ledgers. The direct SQL increment has no read-modify-write race. Cache lookups carry the counter, exact company scope, normalized options, primary-company policy, and language, so stale or cross-scope payloads are recomputed instead of served.

Parameterised SQL builder. A multi-company, analytic-aware query composer that the report handlers use on the hot path. Every value binds as a query parameter, identifiers come from a fixed whitelist, no user input is interpolated into raw SQL, and every query is company-scoped so there is no cross-company leakage. It is plain Python and unit-testable without the Odoo registry.

Three-tier privilege model. User, Manager, and a read-only Auditor role, decoupled from the standard Odoo accounting groups, so an auditor can read the execution log and reports without any write access.

What other ERP Heritage modules build on top

Dynamic Account Reports (free): P&L, Balance Sheet, Trial Balance, General Ledger, Aged Receivable and Payable, Cash Flow, Partner Ledger. Dynamic Reports Pro: custom report builder, scheduled email delivery, multi-period forecasting, budget variance. Bank Reconciliation Pro, Collections Workbench, Period Close Workflow, Multi-Version Budget Pro, Recurring Invoices Pro, Post-Dated Cheques, FX Period-End Revaluation, IFRS 16 Lease and Fixed Assets, Vendor Bill Automation.

Engineering principles

No silent fallbacks. Missing config, missing accounts, and malformed input each surface explicit messages naming the bad field. Failed renders are recorded too: on exception the execution row is marked error with the message and the exception is re-raised. Multi-company aware throughout. Plain Python tools (SQL builder, payload codec, XLSX writer) are unit-tested without the ORM, which keeps the hot path predictable.""",
    'author': 'ERP Heritage',
    'website': 'https://www.erpheritage.com.au/',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'version': '19.0.1.8.0',
    'depends': ['account'],
    'data': [
        'views/res_partner_statistics_views.xml',
        'security/eh_security.xml',
        'security/eh_isolation_rules.xml',
        'security/ir.model.access.csv',
        'data/paperformat.xml',
        'report/eh_report_base.xml',
        'report/account_move_report.xml',
        'views/report_execution_views.xml',
        'views/dynamic_report_views.xml',
        'views/report_wizard_views.xml',
        'views/legacy_seal_reversal_views.xml',
        'views/res_config_settings_views.xml',
        'data/menus.xml',
    ],
    'assets': {
        # House design-token bridge. Loaded FIRST in the backend bundle so
        # var(--eh-*) is defined before any consumer (dashboard, dynamic
        # report viewer) uses it. eh_account_base is the common dependency of
        # the whole accounting suite, so a single source of truth here keeps
        # every surface on the same palette/rhythm without re-declaring hex.
        'web.assets_backend': [
            ('prepend', 'eh_account_base/static/src/scss/eh_tokens.scss'),
            'eh_account_base/static/src/views/fields/list_statistics/list_statistics.scss',
            'eh_account_base/static/src/views/fields/list_statistics/list_statistics.js',
            'eh_account_base/static/src/views/fields/list_statistics/list_statistics.xml',
        ],
    },
    'demo': ['demo/base_demo.xml'],
    'images': ['static/description/banner.gif'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
