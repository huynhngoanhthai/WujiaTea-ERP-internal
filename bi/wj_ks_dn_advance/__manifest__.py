# -*- coding: utf-8 -*-
{
    'name': 'Wujia Dashboard Ninja Advance',

    'summary': """Advance features for the Wujia Dashboard Ninja port (Odoo 19):
custom SQL query items, list-view layouts, redirect links and PDF print/mail.
Based on Ksolves Dashboard Ninja Advance v16 (TV mode / carousel / website dashboard stripped).""",

    'description': """
Wujia internal port of Dashboard Ninja Advance (Ksolves) v16 -> Odoo 19.
- TV mode, item carousel and website dashboard not included.
- Model names kept as ks_dashboard_ninja.* for data compatibility.
- Feature JS (query rendering, label/redirect widgets, PDF) is layered in per feature step.
""",

    'author': 'Ksolves India Ltd. (port: Wujia)',
    'maintainer': 'Wujia',
    'website': 'https://store.ksolves.com/',
    'license': 'OPL-1',
    'category': 'Services',
    'version': '19.0.1.0.0',

    'images': ['static/description/icon.png'],

    'depends': ['wj_ks_dashboard_ninja', 'mail'],

    'data': [
        # NOTE: views/ks_dashboard_ninja_item_view_inherit.xml is deliberately NOT loaded yet.
        # The v18 base item form already merged the query-awareness, so the v16 inherit needs
        # reconciliation (not a mechanical attrs port) — deferred to the SQL-query feature step.
        'views/ks_dashboard_form_view_inherit.xml',
        'views/ks_mail_template.xml',
    ],

    'installable': True,
    'application': False,
    'uninstall_hook': 'ks_dna_uninstall_hook',
}
