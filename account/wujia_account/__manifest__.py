{
    'name': 'Wujia — Accounting franchise link',
    'version': '19.0.1.2.0',
    'category': 'Wujia',
    'summary': 'Franchise scope for invoices/payments + portal debt aggregates',
    'description': """
Wujia — Accounting franchise link
=================================
Backend seam for the portal debts screens (BA task Tasks!STT9, BA doc "Portal debts &
payments controller", tab 1. Model/ Field section N, Controller CT-050..CT-055).

Adds the 3 custom fields agreed with BA:

- ``account.move.franchise_id`` — store scope of the invoice / credit note.
- ``account.payment.franchise_id`` — store scope of the payment (stored compute from the
  reconciled invoice).
- ``res.partner.bank.portal_payment_enabled`` — shows the receiving account on the portal.

Plus 2 perf aggregates on ``wujia.franchise.management`` (the "n overdue" badge is read on
every portal page — stored + daily cron, NO on-the-fly query).

No new model, no new sequence, no change to the standard accounting rules.
""",
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': ['account', 'wujia_franchise', 'wujia_sale'],
    'data': [
        'data/ir_cron.xml',
        'views/account_move_views.xml',
        'views/account_payment_views.xml',
        'views/res_partner_bank_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
