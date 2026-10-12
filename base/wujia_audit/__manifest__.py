# -*- coding: utf-8 -*-
{
    'name': 'Wujia audit Tracking',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': 'Configure chatter field tracking dynamically without touching Python source code',
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/wujia_field_tracking_config_views.xml',
        'views/wujia_field_tracking_menus.xml',
        'views/mail_tracking_value_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
