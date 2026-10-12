# -*- coding: utf-8 -*-
{
    'name': 'Wujia Franchise — Store Inspection',
    'version': '19.0.1.0.0',
    'category': 'Wujia',
    'summary': 'Store inspection, supervision, quality scoring, and evaluation module for franchise system',
    'author': 'WujiaTea',
    'description': """
Franchise Store Inspection & Supervision Management:

1. wujia.franchise.inspection — phiếu khảo sát & đánh giá chất lượng:
   - Chấm điểm theo tiêu chí/nhóm, tính tổng điểm và tự động xếp loại (grade).
   - Quy trình: draft -> in_progress -> need_remediation -> done / cancel.
   - Quản lý khắc phục vi phạm: thời hạn deadline, ảnh minh chứng, duyệt sửa đổi.
   - UI ĐỘC LẬP (list/form/kanban/pivot/graph) + Giao diện Web Survey (mobile/GPS).

2. wujia.supervision.schedule — lịch giám sát cửa hàng:
   - Lập kế hoạch kiểm tra định kỳ, phân công giám sát viên (Supervisor).
   - UI ĐỘC LẬP (list/form/calendar).

3. Cấu hình tiêu chuẩn (Supervision Config):
   - wujia.franchise.inspection.template, category, question, grade.
   - UI ĐỘC LẬP trong menu cấu hình riêng.

Extension kế thừa:
   - wujia.franchise.management: thêm supervisor phụ trách, lịch kiểm tra gần nhất, điểm/xếp loại mới nhất, chart lịch sử điểm + smart-button phiếu khảo sát.
""",
    'license': 'LGPL-3',
    'depends': [
        'wujia_franchise',
        'wujia_core',
        'contacts',
        'portal',
        'mail',
    ],
    'data': [
        'security/wujia_inspection_groups.xml',
        'security/ir.model.access.csv',
        'security/wujia_inspection_rules.xml',
        'data/inspection_grade_data.xml',
        'data/wujia_inspection_bootstrap.xml',
        'views/wujia_franchise_inspection_template_views.xml',
        'views/wujia_franchise_inspection_question_views.xml',
        'views/wujia_franchise_inspection_grade_views.xml',
        'views/wujia_franchise_inspection.xml',
        'views/wujia_franchise_inspection_report_templates.xml',
        'views/inspection_survey_web_templates.xml',
        'views/wujia_franchise_inspection_history_views.xml',
        'views/wujia_franchise_inspection_remediation_views.xml',
        'views/wujia_franchise_inspection_report_views.xml',
        'views/wujia_franchise_inspection_violation_views.xml',
        'views/wujia_franchise_needed_inspection_views.xml',
        'views/wujia_supervision_schedule_views.xml',
        'views/wujia_franchise_management_inspection_views.xml',
        'views/res_config_settings_views.xml',
        'views/wujia_franchise_inspection_menu.xml',
        'views/res_users_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'wujia_franchise_inspection/static/src/css/wujia_inspection.css',
            'wujia_franchise_inspection/static/src/js/wujia_inspection_chart.js',
            'wujia_franchise_inspection/static/src/js/wujia_gps_field.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
