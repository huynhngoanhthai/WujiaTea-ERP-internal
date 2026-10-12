# -*- coding: utf-8 -*-
{
    'name': 'Wujia Mobile Core',
    'version': '19.0.1.0.0',
    'category': 'Wujia/Mobile',
    'summary': 'Core Mobile UI Framework & Standards for WujiaTea ERP Backend Web Client',
    'description': """Core Mobile UI Framework & Standards for WujiaTea ERP Backend Web Client""",
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
    ],
    'data': [
        'security/wujia_mobile_core_groups.xml',
        'security/ir.model.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'wujia_mobile_core/static/src/scss/_variables.scss',
            'wujia_mobile_core/static/src/scss/_mixins.scss',
            'wujia_mobile_core/static/src/scss/_kanban.scss',
            'wujia_mobile_core/static/src/scss/_header.scss',
            'wujia_mobile_core/static/src/scss/_badges.scss',
            'wujia_mobile_core/static/src/scss/_empty_state.scss',
            'wujia_mobile_core/static/src/scss/_loading.scss',
            'wujia_mobile_core/static/src/scss/_utilities.scss',
            'wujia_mobile_core/static/src/scss/_form.scss',
            'wujia_mobile_core/static/src/xml/wujia_mobile_templates.xml',
            'wujia_mobile_core/static/src/components/empty_state/wujia_mobile_empty_state.js',
            'wujia_mobile_core/static/src/components/empty_state/wujia_mobile_empty_state.xml',
            'wujia_mobile_core/static/src/components/skeleton/wujia_mobile_skeleton.js',
            'wujia_mobile_core/static/src/components/skeleton/wujia_mobile_skeleton.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
