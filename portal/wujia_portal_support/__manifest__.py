{
    'name': 'Wujia Portal — Support Tickets',
    'version': '19.0.5.3.0',
    'category': 'Wujia',
    'summary': 'Support request screens on the store portal — business logic in wujia_support (F10)',
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': ['wujia_portal_base', 'wujia_support'],
    'data': [
        'views/bottomnav_inherit.xml',
        'views/sidenav_inherit.xml',
        'views/portal_support.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'wujia_portal_support/static/src/css/portal_support.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
