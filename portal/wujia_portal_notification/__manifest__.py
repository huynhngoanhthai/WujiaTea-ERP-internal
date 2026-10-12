{
    'name': 'Wujia Portal — Notification',
    'version': '19.0.5.2.0',
    'category': 'Wujia',
    'summary': 'Notification screens on the store portal + header bell — business logic in wujia_notification (F11)',
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': ['wujia_portal_base', 'wujia_notification'],
    'data': [
        'views/bottomnav_inherit.xml',
        'views/header_bell_inherit.xml',
        'views/portal_notification.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'wujia_portal_notification/static/src/css/portal_notification.css',
            'wujia_portal_notification/static/src/js/header_bell_badge.js',
            'wujia_portal_notification/static/src/js/portal_notification_pc.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
