# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def post_init_hook(env):
    """Run migration for legacy store contract dates after module installation."""
    env['wujia.franchise.management']._migrate_legacy_franchise_contracts()
