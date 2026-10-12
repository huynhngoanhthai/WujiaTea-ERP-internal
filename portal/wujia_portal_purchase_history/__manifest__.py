{
    'name': 'Wujia Portal — Purchase History',
    'version': '19.0.4.1.0',
    'category': 'Wujia',
    'summary': 'Portal order history — list + detail (BA controller CT-024/025)',
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': ['wujia_sale', 'wujia_portal_base', 'wujia_delivery'],
    'data': [
        'views/sidenav_inherit.xml',
        'views/bottomnav_inherit.xml',
        'views/portal_history.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'wujia_portal_purchase_history/static/src/css/portal_history.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
