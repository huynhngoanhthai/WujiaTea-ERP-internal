{
    'name': 'Wujia Portal — Debts & payments',
    'version': '19.0.5.2.1',
    'category': 'Wujia',
    'summary': 'Weekly debts, payment history and bank transfer screen (portal mobile + PC)',
    'description': """
Wujia Portal — Debts & payments
===============================
Builds the 7 Figma screens ``WJ_Debt_..._MVP_v31`` (page Dashboard, node 5013).

**Sprint 43** — UI only (seam ``wujia.portal.debt`` returns plain dicts, 0 query).
**Sprint 48** — real backend (BA task Tasks!STT9, Controller CT-050..CT-055): the seam
reads ``account.move``/``account.payment`` scoped by ``franchise_id`` (3 custom fields in
module ``wujia_account``), the debt badge uses stored perf fields, the controller blocks Staff.
Templates/CSS/JS unchanged — only the seam internals + controller guard.
**Sprint 49** — PC layout 1920×1080 (BA task Tasks!STT10, Figma ``WJ_Debt_PC_MVP_v1_1``
node 5077): desktop block ``.wj-debt-pc`` (d-none d-lg-block) on the ``wj-pc-*`` system /
``pc_source_ui_v1_5`` shell — Debts/History tabs, filter, 3-column summary (5 state variants),
paginated invoice table, empty box, QR modal. Mobile unchanged (wrapped in ``d-lg-none``).
The seam grows **additively** (each invoice adds ``total/paid/remaining``; ``get_payments``
adds ``keyword``) + the controller adds PC context — NO field/rule/migration change.
**J-V5** — source strings in English, Vietnamese via ``i18n/vi_VN.po``.
""",
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': ['wujia_portal_base', 'wujia_account'],
    'data': [
        'views/portal_debt.xml',
        'views/sidenav_inherit.xml',
        'views/bottomnav_inherit.xml',
        'views/home_kpi_inherit.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'wujia_portal_debt/static/src/css/portal_debt.css',
            'wujia_portal_debt/static/src/js/portal_debt.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
