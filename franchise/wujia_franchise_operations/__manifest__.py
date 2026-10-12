# -*- coding: utf-8 -*-
{
    'name': 'Wujia Franchise Store Operations',
    'version': '19.0.1.0.0',
    'category': 'Franchise',
    'summary': 'Internal Franchise Store Operations MVP (Employee, Shift, Schedule, Expense, Revenue)',
    'description': """
WujiaTea ERP — Franchise Store Operations (MVP Backend-Only)
============================================================
Provides internal management for franchise store operations:
- Franchise Employee profiles & store assignments
- Shift templates & work schedule planning with calendar view
- Operating expense categories & expense tracking (no accounting moves)
- Daily revenue declaration & idempotent tracking (no accounting moves)
- Smart buttons on Franchise Store Master form
    """,
    'author': 'WujiaTea ERP Team',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'wujia_franchise',
    ],
    'data': [
        'security/franchise_operations_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/wujia_franchise_expense_category_data.xml',
        'data/wujia_franchise_shift_template_data.xml',
        'views/menu_views.xml',
        'views/employee_views.xml',
        'views/employee_assignment_views.xml',
        'views/shift_template_views.xml',
        'views/work_schedule_views.xml',
        'views/expense_category_views.xml',
        'views/expense_views.xml',
        'wizard/revenue_import_wizard_views.xml',
        'wizard/revenue_compute_wizard_views.xml',
        'views/revenue_views.xml',
        'views/wujia_franchise_management_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
