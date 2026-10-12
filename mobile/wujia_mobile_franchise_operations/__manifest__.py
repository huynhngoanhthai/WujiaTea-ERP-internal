# -*- coding: utf-8 -*-
{
    'name': 'Wujia Mobile Franchise Operations',
    'version': '19.0.1.0.0',
    'category': 'Wujia',
    'summary': 'Responsive mobile views and kanban cards for Wujia Store Operations',
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': [
        'wujia_franchise_operations',
        'wujia_mobile_core',
    ],
    'data': [
        'views/franchise_employee_mobile_views.xml',
        'views/franchise_assignment_mobile_views.xml',
        'views/franchise_schedule_mobile_views.xml',
        'views/franchise_revenue_mobile_views.xml',
        'views/franchise_expense_mobile_views.xml',
        'views/franchise_shift_template_mobile_views.xml',
        'views/franchise_expense_category_mobile_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
