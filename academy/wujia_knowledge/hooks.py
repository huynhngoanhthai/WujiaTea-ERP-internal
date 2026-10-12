"""Đổi chủ phần nghiệp vụ ``wujia_portal_knowledge`` → ``wujia_knowledge`` (F9, ADR-027).

Tách một phần: 3 QWeb portal + 2 mục nav + controller ở lại module cũ.
"""
import logging

from odoo.addons.wujia_core.tools.module_split import imd_names, migrate_ownership

_logger = logging.getLogger(__name__)

OLD_MODULE = 'wujia_portal_knowledge'
NEW_MODULE = 'wujia_knowledge'
MODELS = ['wujia.knowledge.article', 'wujia.knowledge.category', 'wujia.knowledge.tag']
EXTRA = [
    'menu_wujia_knowledge_root', 'menu_wujia_knowledge_articles',
    'menu_wujia_knowledge_categories', 'menu_wujia_knowledge_tags',
]


def pre_init_hook(env):
    names = imd_names(env.cr, OLD_MODULE, MODELS, extra=EXTRA)
    moved = migrate_ownership(env.cr, OLD_MODULE, NEW_MODULE, names=names, models=MODELS)
    _logger.info("%s: doi chu tu %s — %s", NEW_MODULE, OLD_MODULE, moved)
