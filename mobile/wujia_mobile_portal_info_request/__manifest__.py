# -*- coding: utf-8 -*-
{
    'name': 'Wujia Mobile Portal Info Request',
    'version': '19.0.1.0.1',
    'category': 'Wujia',
    'summary': 'Responsive mobile views and kanban cards for Wujia Info Update Requests',
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': [
        'wujia_info_request',
        'wujia_mobile_core',
    ],
    'data': [
        'views/info_request_mobile_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}