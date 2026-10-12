# -*- coding: utf-8 -*-
"""Chuyển quyền sở hữu bản ghi khi tách phân hệ Khảo sát ra khỏi ``wujia_franchise``.

Trước bản 19.0.5.0.0 của ``wujia_franchise``, toàn bộ model/view/menu/group/rule/ACL của
phân hệ Khảo sát do chính module đó khai báo. Sau khi tách, chúng do
``wujia_franchise_inspection`` khai báo, nhưng ``ir_model_data`` trên các CSDL đang chạy
vẫn ghi chủ cũ. Nếu không đổi chủ trước khi nạp dữ liệu module mới thì:

* Odoo tạo BẢN SAO xmlid dưới tên module mới, còn bản cũ bị ``_process_end`` dọn đi
  => user rơi khỏi nhóm quyền giám sát, ir.rule biến mất;
* các dòng ``ir.model`` / ``ir.model.fields`` cũ bị dọn => nguy cơ rơi bảng dữ liệu khảo sát.

Hook chạy ở ``pre_init_hook`` vì Odoo KHÔNG chạy script migration cho lần cài đầu tiên.
Chỉ đổi cột ``module``; không đụng bản ghi nghiệp vụ, không đụng ``res_groups_users_rel``.
"""
import logging

_logger = logging.getLogger(__name__)

OLD_MODULE = 'wujia_franchise'
NEW_MODULE = 'wujia_franchise_inspection'

#: view / action / menu / template / group / rule / ACL đã rời khỏi wujia_franchise
MOVED_XMLIDS = [
        'access_franchise_inspection_admin', 'access_franchise_inspection_attendance_line_admin', 'access_franchise_inspection_attendance_line_inspector',
        'access_franchise_inspection_attendance_line_portal', 'access_franchise_inspection_category_admin', 'access_franchise_inspection_category_inspector',
        'access_franchise_inspection_category_portal', 'access_franchise_inspection_exam_line_admin', 'access_franchise_inspection_exam_line_inspector',
        'access_franchise_inspection_exam_line_portal', 'access_franchise_inspection_grade_admin', 'access_franchise_inspection_grade_inspector',
        'access_franchise_inspection_grade_portal', 'access_franchise_inspection_inspector', 'access_franchise_inspection_line_admin',
        'access_franchise_inspection_line_inspector', 'access_franchise_inspection_line_portal', 'access_franchise_inspection_portal',
        'access_franchise_inspection_question_admin', 'access_franchise_inspection_question_inspector', 'access_franchise_inspection_question_portal',
        'access_franchise_inspection_report_line_admin', 'access_franchise_inspection_report_line_inspector', 'access_franchise_inspection_report_line_portal',
        'access_franchise_inspection_template_admin', 'access_franchise_inspection_template_inspector', 'access_franchise_inspection_template_line_admin',
        'access_franchise_inspection_template_line_inspector', 'access_franchise_inspection_template_line_portal', 'access_franchise_inspection_template_portal',
        'access_supervision_schedule_admin', 'access_supervision_schedule_inspector', 'access_supervision_schedule_portal',
        'action_franchise_needed_inspection', 'action_wujia_franchise_inspection', 'action_wujia_franchise_inspection_category',
        'action_wujia_franchise_inspection_grade', 'action_wujia_franchise_inspection_history', 'action_wujia_franchise_inspection_question',
        'action_wujia_franchise_inspection_remediation', 'action_wujia_franchise_inspection_report_result', 'action_wujia_franchise_inspection_report_violation',
        'action_wujia_franchise_inspection_template', 'action_wujia_supervision_schedule', 'group_supervision_admin',
        'group_supervision_inspector', 'inspection_survey_do_page', 'menu_wujia_inspection_category',
        'menu_wujia_inspection_config_root', 'menu_wujia_inspection_history', 'menu_wujia_inspection_pending_store',
        'menu_wujia_inspection_question_bank', 'menu_wujia_inspection_ranking', 'menu_wujia_inspection_remediation',
        'menu_wujia_inspection_report_result', 'menu_wujia_inspection_report_root', 'menu_wujia_inspection_report_violation',
        'menu_wujia_inspection_schedule', 'menu_wujia_inspection_sheet', 'menu_wujia_inspection_supervision_root',
        'menu_wujia_inspection_template', 'res_groups_privilege_supervision', 'rule_franchise_inspection_admin',
        'rule_franchise_inspection_exam_line_admin', 'rule_franchise_inspection_exam_line_inspector', 'rule_franchise_inspection_exam_line_portal',
        'rule_franchise_inspection_inspector', 'rule_franchise_inspection_line_admin', 'rule_franchise_inspection_line_inspector',
        'rule_franchise_inspection_line_portal', 'rule_franchise_inspection_portal', 'rule_supervision_schedule_admin',
        'rule_supervision_schedule_inspector', 'rule_supervision_schedule_portal', 'view_wujia_franchise_inspection_category_form',
        'view_wujia_franchise_inspection_category_tree', 'view_wujia_franchise_inspection_form', 'view_wujia_franchise_inspection_grade_form',
        'view_wujia_franchise_inspection_grade_list', 'view_wujia_franchise_inspection_line_form', 'view_wujia_franchise_inspection_line_search',
        'view_wujia_franchise_inspection_line_violation_graph', 'view_wujia_franchise_inspection_line_violation_pivot', 'view_wujia_franchise_inspection_line_violation_tree',
        'view_wujia_franchise_inspection_list', 'view_wujia_franchise_inspection_question_form', 'view_wujia_franchise_inspection_question_search',
        'view_wujia_franchise_inspection_question_tree', 'view_wujia_franchise_inspection_report_graph', 'view_wujia_franchise_inspection_report_pivot',
        'view_wujia_franchise_inspection_search', 'view_wujia_franchise_inspection_template_form', 'view_wujia_franchise_inspection_template_search',
        'view_wujia_franchise_inspection_template_tree', 'view_wujia_supervision_schedule_calendar', 'view_wujia_supervision_schedule_form',
        'view_wujia_supervision_schedule_search', 'view_wujia_supervision_schedule_tree',
]

#: field khảo sát từng khai trên wujia.franchise.management, nay do module mới khai
MOVED_MGMT_FIELDS = [
        'area_manager_user_id', 'consecutive_c_count', 'consecutive_cd_count',
        'consecutive_d_count', 'effective_supervision_user_id', 'inspection_chart_data',
        'inspection_ids', 'latest_grade_id', 'latest_inspection_date',
        'latest_inspection_id', 'latest_total_score', 'next_supervision_date',
]

#: model chuyển hẳn sang module mới — khớp theo tiền tố để lấy cả ir.model lẫn ir.model.fields
MOVED_MODEL_PREFIXES = [
        'wujia_franchise_inspection', 'wujia_supervision_schedule',
]


def migrate_ownership(cr):
    """Đổi cột ``module`` của ir_model_data từ module cũ sang module mới."""
    total = 0

    cr.execute(
        "UPDATE ir_model_data SET module = %s WHERE module = %s AND name IN %s",
        (NEW_MODULE, OLD_MODULE, tuple(MOVED_XMLIDS)),
    )
    total += cr.rowcount
    _logger.info("Chuyen %s xmlid view/menu/group/rule/ACL sang %s", cr.rowcount, NEW_MODULE)

    for prefix in MOVED_MODEL_PREFIXES:
        cr.execute(
            """UPDATE ir_model_data SET module = %s
                 WHERE module = %s
                   AND (name = %s OR name LIKE %s OR name LIKE %s OR name LIKE %s)""",
            (NEW_MODULE, OLD_MODULE,
             'model_' + prefix, 'model_' + prefix + '\\_%',
             'field_' + prefix + '\\_\\_%', 'constraint_' + prefix + '\\_%'),
        )
        total += cr.rowcount
        _logger.info("Chuyen %s dong ir.model/ir.model.fields cua %s", cr.rowcount, prefix)

    if MOVED_MGMT_FIELDS:
        names = ['field_wujia_franchise_management__' + f for f in MOVED_MGMT_FIELDS]
        cr.execute(
            "UPDATE ir_model_data SET module = %s WHERE module = %s AND name IN %s",
            (NEW_MODULE, OLD_MODULE, tuple(names)),
        )
        total += cr.rowcount
        _logger.info("Chuyen %s field khao sat tren wujia.franchise.management", cr.rowcount)

    return total


def pre_init_hook(env):
    moved = migrate_ownership(env.cr)
    _logger.info("wujia_franchise_inspection: da chuyen chu %s ban ghi ir_model_data", moved)
