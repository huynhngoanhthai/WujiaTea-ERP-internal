# -*- coding: utf-8 -*-
{
    'name': 'Wujia Mobile Portal Exam',
    'version': '19.0.1.0.1',
    'category': 'Wujia',
    'summary': 'Responsive mobile views and kanban cards for Wujia Training & Exams',
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': [
        'wujia_exam',
        'wujia_mobile_core',
    ],
    'data': [
        'views/exam_session_mobile_views.xml',
        'views/exam_registration_mobile_views.xml',
        'views/exam_course_mobile_views.xml',
        'views/exam_time_slot_mobile_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
