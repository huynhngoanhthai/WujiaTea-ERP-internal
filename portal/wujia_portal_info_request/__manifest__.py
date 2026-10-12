{
    'name': 'Wujia Portal — Info Update Request',
    'version': '19.0.3.3.0',
    'category': 'Wujia',
    'summary': 'Portal screens to request store information updates '
               '(business rules in wujia_info_request).',
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': ['wujia_portal_base', 'wujia_info_request'],
    'data': [
        'views/portal_info_request_list.xml',
        'views/portal_info_request_form.xml',
        'views/portal_info_request_detail.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
