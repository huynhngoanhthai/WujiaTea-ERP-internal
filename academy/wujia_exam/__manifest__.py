{
    'name': 'Wujia Exams',
    'version': '19.0.1.2.0',
    'category': 'Wujia',
    'summary': 'Franchise exam registration — exam courses, time slots, exam sessions, multi-person registrations, results.',
    'description': """
Training / exam business logic. Split out of wujia_portal_exam (F12, ADR-027).

- Models wujia.exam.time.slot (time slots), wujia.exam.course (courses, code WJ-CRS/),
  wujia.exam.session (exam sessions, code WJ-EXS/, capacity, result publishing),
  wujia.exam.registration (registrations, code WJ-EXR/) + wujia.exam.registration.line (participants).
- _effective_max_per_registration / _portal_* / register_from_portal: rules shared by every channel.
""",
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': ['mail', 'wujia_franchise'],
    'data': [
        'security/wujia_exam_groups.xml',
        'security/ir.model.access.csv',
        'security/wujia_exam_rules.xml',
        'data/ir_sequence_data.xml',
        'views/backend_exam_time_slot_views.xml',
        'views/backend_exam_course_views.xml',
        'views/backend_exam_session_views.xml',
        'views/backend_exam_registration_views.xml',
        'views/backend_menu.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
