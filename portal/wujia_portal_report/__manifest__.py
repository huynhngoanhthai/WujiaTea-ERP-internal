{
    'name': 'Wujia Portal — Reports',
    'version': '19.0.3.3.0',
    'category': 'Wujia',
    'summary': 'Order report for owners and managers (BA Phase 1)',
    'description': 'Page /portal/reports/orders with KPI cards, a 12-month bar chart, top products and status distribution. Staff are redirected away.',
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': ['wujia_sale', 'wujia_portal_base'],
    'data': [
        'views/portal_report_orders.xml',
        'views/bottomnav_inherit.xml',
        'views/sidenav_inherit.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'wujia_portal_report/static/src/css/portal_report.css',
            'wujia_portal_report/static/src/js/portal_report_charts.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
