{
    'name': 'Wujia Portal — Knowledge Library',
    'version': '19.0.5.1.0',
    'category': 'Wujia',
    'summary': 'Knowledge library portal screens (business logic in wujia_knowledge).',
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': ['wujia_portal_base', 'wujia_knowledge'],
    'data': [
        'views/bottomnav_inherit.xml',
        'views/sidenav_inherit.xml',
        'views/portal_knowledge.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'wujia_portal_knowledge/static/src/css/portal_knowledge.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
