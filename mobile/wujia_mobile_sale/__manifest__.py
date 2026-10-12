# -*- coding: utf-8 -*-
{
    'name': 'Wujia Mobile Sale',
    'version': '19.0.1.0.0',
    'category': 'Wujia',
    'summary': 'Responsive mobile views and kanban cards for Wujia Sales Orders',
    'description': """Responsive mobile views and kanban cards for Wujia Sales Orders""",
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': [
        'sale',
        'wujia_mobile_core',
    ],
    'data': [
        'views/sale_order_mobile_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
