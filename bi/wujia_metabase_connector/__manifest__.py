# -*- coding: utf-8 -*-
{
    'name': 'Wujia Metabase BI Connector',
    'version': '19.0.1.0.1',
    'category': 'Wujia',
    'summary': 'Metabase BI Dashboard Connector with Signed JWT Iframe and Dynamic Menu Generation',
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': [
        'base',
    ],
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'views/metabase_instance_views.xml',
        'views/metabase_dashboard_views.xml',
        'views/metabase_menus.xml',
        'views/metabase_iframe_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'wujia_metabase_connector/static/src/metabase_dashboard_action/metabase_dashboard_action.js',
            'wujia_metabase_connector/static/src/metabase_dashboard_action/metabase_dashboard_action.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
