{
    'name': 'Wujia Portal — Exam (Training / Exams)',
    'version': '19.0.7.4.0',
    'category': 'Wujia',
    'summary': 'Portal exam registration screens (PC + mobile) — business logic lives in wujia_exam (F12).',
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': ['wujia_portal_base', 'wujia_exam'],
    'data': [
        'views/bottomnav_inherit.xml',
        'views/sidenav_inherit.xml',
        'views/portal_exam.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'wujia_portal_exam/static/src/css/portal_exam.css',
            'wujia_portal_exam/static/src/js/portal_exam_wizard.js',
            'wujia_portal_exam/static/src/js/portal_exam_pc.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
