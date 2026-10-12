# -*- coding: utf-8 -*-
{
    'name': 'Wujia Portal — Inspection (Khảo sát)',
    'version': '19.0.1.8.0',
    'category': 'Wujia',
    'summary': 'Giao diện xem phiếu khảo sát đánh giá cửa hàng nhượng quyền',
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': ['wujia_portal_base', 'wujia_portal_layout', 'wujia_franchise', 'wujia_franchise_inspection'],
    'data': [
        'security/ir.model.access.csv',
        'views/sidenav_inherit.xml',
        'views/portal_inspection_list_templates.xml',
        'views/portal_inspection_detail_templates.xml',
        'views/portal_inspection_remediation_templates.xml',
        'views/portal_inspection_success_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'wujia_portal_inspection/static/src/css/portal_inspection.css',
            'wujia_portal_inspection/static/src/js/portal_inspection_detail.js',
            'wujia_portal_inspection/static/src/js/portal_inspection_list.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
