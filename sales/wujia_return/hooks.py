"""Đổi chủ phần nghiệp vụ ``wujia_portal_return`` → ``wujia_return`` (F13, ADR-027).

Tách một phần: 3 QWeb portal + mục sidenav/bottomnav + controller ở lại module cũ.
"""
import logging

from odoo.addons.wujia_core.tools.module_split import imd_names, migrate_ownership

_logger = logging.getLogger(__name__)

OLD_MODULE = 'wujia_portal_return'
NEW_MODULE = 'wujia_return'
MODELS = ['wujia.return.request', 'wujia.return.issue.type', 'wujia.compensation.allocation',
          'wujia.compensation.process.wizard', 'wujia.compensation.process.wizard.group',
          'wujia.compensation.process.wizard.line', 'sale.order', 'stock.picking', 'product.product']
EXTRA = [
    'res_groups_privilege_return', 'group_return_user', 'group_return_manager',
    'menu_wujia_return_root', 'menu_wujia_return_operation', 'menu_wujia_return_request',
    'menu_wujia_return_order', 'menu_wujia_return_config', 'menu_wujia_return_issue_type',
    'issue_type_packaging', 'issue_type_wrong_product', 'issue_type_expired',
    'issue_type_short_qty', 'issue_type_other',
]


def pre_init_hook(env):
    names = imd_names(env.cr, OLD_MODULE, MODELS, extra=EXTRA)
    moved = migrate_ownership(env.cr, OLD_MODULE, NEW_MODULE, names=names, models=MODELS)
    _logger.info("%s: doi chu tu %s — %s", NEW_MODULE, OLD_MODULE, moved)
