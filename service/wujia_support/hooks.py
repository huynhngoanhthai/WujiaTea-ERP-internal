"""Đổi chủ phần nghiệp vụ ``wujia_portal_support`` → ``wujia_support`` (F10, ADR-027).

Tách một phần: 3 QWeb portal + 2 mục nav + controller ở lại module cũ.
"""
import logging

from odoo.addons.wujia_core.tools.module_split import imd_names, migrate_ownership

_logger = logging.getLogger(__name__)

OLD_MODULE = 'wujia_portal_support'
NEW_MODULE = 'wujia_support'
MODELS = ['wujia.support.ticket', 'wujia.support.category']
EXTRA = [
    'menu_wujia_support_root', 'menu_wujia_support_tickets',
    'menu_wujia_support_tickets_all', 'menu_wujia_support_categories',
    'category_order', 'category_delivery', 'category_product', 'category_pos',
    'category_operation', 'category_account', 'category_other',
]


def pre_init_hook(env):
    names = imd_names(env.cr, OLD_MODULE, MODELS, extra=EXTRA)
    moved = migrate_ownership(env.cr, OLD_MODULE, NEW_MODULE, names=names, models=MODELS)
    _logger.info("%s: doi chu tu %s — %s", NEW_MODULE, OLD_MODULE, moved)
