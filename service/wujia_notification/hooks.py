"""Đổi chủ phần nghiệp vụ ``wujia_portal_notification`` → ``wujia_notification`` (F11, ADR-027).

Tách một phần: 4 QWeb portal + chuông header + mục nav + controller ở lại module cũ.
"""
import logging

from odoo.addons.wujia_core.tools.module_split import imd_names, migrate_ownership

_logger = logging.getLogger(__name__)

OLD_MODULE = 'wujia_portal_notification'
NEW_MODULE = 'wujia_notification'
MODELS = ['wujia.notification', 'wujia.notification.type', 'wujia.notification.read']
EXTRA = [
    'res_groups_privilege_notification', 'group_notification_user', 'group_notification_manager',
    'menu_wujia_notification_root', 'menu_wujia_notification',
    'menu_wujia_notification_config', 'menu_wujia_notification_type',
    'ntype_urgent', 'ntype_general', 'ntype_promo', 'ntype_system', 'ntype_other',
]


def pre_init_hook(env):
    names = imd_names(env.cr, OLD_MODULE, MODELS, extra=EXTRA)
    moved = migrate_ownership(env.cr, OLD_MODULE, NEW_MODULE, names=names, models=MODELS)
    _logger.info("%s: doi chu tu %s — %s", NEW_MODULE, OLD_MODULE, moved)
