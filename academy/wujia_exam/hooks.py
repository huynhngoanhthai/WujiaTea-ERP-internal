"""Đổi chủ phần nghiệp vụ ``wujia_portal_exam`` → ``wujia_exam`` (F12, ADR-027).

Tách một phần: 3 QWeb portal + mục sidenav/bottomnav + controller ở lại module cũ.
"""
import logging

from odoo.addons.wujia_core.tools.module_split import imd_names, migrate_ownership

_logger = logging.getLogger(__name__)

OLD_MODULE = 'wujia_portal_exam'
NEW_MODULE = 'wujia_exam'
MODELS = ['wujia.exam.time.slot', 'wujia.exam.course', 'wujia.exam.session',
          'wujia.exam.registration', 'wujia.exam.registration.line']
EXTRA = [
    'res_groups_privilege_exam', 'group_exam_user', 'group_exam_manager',
    'menu_wujia_exam_root', 'menu_wujia_exam_operation', 'menu_wujia_exam_session',
    'menu_wujia_exam_registration', 'menu_wujia_exam_config', 'menu_wujia_exam_course',
    'menu_wujia_exam_time_slot',
]


def pre_init_hook(env):
    names = imd_names(env.cr, OLD_MODULE, MODELS, extra=EXTRA)
    moved = migrate_ownership(env.cr, OLD_MODULE, NEW_MODULE, names=names, models=MODELS)
    _logger.info("%s: doi chu tu %s — %s", NEW_MODULE, OLD_MODULE, moved)
