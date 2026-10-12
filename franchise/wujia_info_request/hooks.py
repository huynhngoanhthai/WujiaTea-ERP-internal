"""Đổi chủ phần nghiệp vụ ``wujia_portal_info_request`` → ``wujia_info_request`` (F8, ADR-027).

Tách một phần: 3 QWeb portal + controller ở lại module cũ.
"""
import logging

from odoo.addons.wujia_core.tools.module_split import imd_names, migrate_ownership

_logger = logging.getLogger(__name__)

OLD_MODULE = 'wujia_portal_info_request'
NEW_MODULE = 'wujia_info_request'
MODELS = ['wujia.info.update.request']
EXTRA = ['menu_wujia_info_update_request_root']


def pre_init_hook(env):
    names = imd_names(env.cr, OLD_MODULE, MODELS, extra=EXTRA)
    moved = migrate_ownership(env.cr, OLD_MODULE, NEW_MODULE, names=names, models=MODELS)
    _logger.info("%s: doi chu tu %s — %s", NEW_MODULE, OLD_MODULE, moved)
