"""Đổi chủ bản ghi ``wujia_portal_order_window`` → ``wujia_order_window`` (pilot tách, ADR-027).

Module cũ đã rút hết và gỡ khỏi repo; hook giữ lại cho DB chưa nâng cấp (DB mới: 0 dòng, vô hại).
"""
import logging

from odoo.addons.wujia_core.tools.module_split import migrate_ownership

_logger = logging.getLogger(__name__)

OLD_MODULE = 'wujia_portal_order_window'
NEW_MODULE = 'wujia_order_window'


def pre_init_hook(env):
    moved = migrate_ownership(env.cr, OLD_MODULE, NEW_MODULE)
    _logger.info("%s: doi chu tu %s — %s", NEW_MODULE, OLD_MODULE, moved)
