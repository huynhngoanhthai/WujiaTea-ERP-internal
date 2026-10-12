{
    'name': 'Wujia Portal — Delivery Tracking',
    'version': '19.0.4.2.1',
    'category': 'Wujia',
    'summary': 'Portal delivery trip tracking — batch list + detail (desktop + mobile Figma 4731)',
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': ['wujia_delivery', 'wujia_portal_base'],
    'data': [
        'views/sidenav_inherit.xml',
        'views/bottomnav_inherit.xml',
        'views/portal_delivery.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'wujia_portal_delivery/static/src/css/portal_delivery.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
