# -*- coding: utf-8 -*-
{
    'name': "Wujia — View Fields Value",

    'summary': """
        This module allows you to view all field values of the current form view""",

    'description': """
        WujiaTea ERP — View Fields Value
        =================================
        Allows developers and administrators to inspect all field values on any form view,
        including hidden and internal fields.
    """,

    'author': "Apanda, WujiaTea Team",
    'category': 'Technical',
    'version': '19.0.1.0.0',
    'icon': '/wujia_fields_value/static/description/icon.png',

    'depends': ['base', 'web'],

    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'wujia_fields_value/static/src/js/fields_value.js',
            'wujia_fields_value/static/src/xml/fields_value.xml',
            'wujia_fields_value/static/src/scss/fields_value.scss',
        ],
    },
    'license': 'AGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
