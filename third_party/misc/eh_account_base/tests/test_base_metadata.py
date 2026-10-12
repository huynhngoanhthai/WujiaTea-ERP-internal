# -*- encoding: utf-8 -*-
##############################################################################
# ERP Heritage - Copyright (C) 2026 (https://www.erpheritage.com.au/)
##############################################################################
"""Upgrade/listing/navigation regressions for base-owned metadata."""

import ast
from pathlib import Path

from odoo.tests import tagged

from .common import EhAccountUnitTestCase


@tagged('eh_account_base', 'unit')
class TestBaseMetadata(EhAccountUnitTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.module_root = Path(__file__).parents[1]
        cls.manifest = ast.literal_eval(
            (cls.module_root / '__manifest__.py').read_text()
        )

    def test_partner_core_table_ddl_is_versioned_not_registry_time(self):
        partner_source = (
            self.module_root / 'models' / 'res_partner.py'
        ).read_text()
        self.assertNotIn('def _auto_init', partner_source)
        migrations = sorted(
            (self.module_root / 'migrations').glob('*/post-migration.py')
        )
        ddl_migrations = [
            migration for migration in migrations
            if 'ALTER TABLE res_partner' in migration.read_text()
        ]
        self.assertEqual(len(ddl_migrations), 1)
        migration_version = tuple(
            int(part) for part in ddl_migrations[0].parent.name.split('.')
        )
        manifest_version = tuple(
            int(part) for part in self.manifest['version'].split('.')
        )
        self.assertLessEqual(migration_version, manifest_version)

    def test_base_does_not_rename_core_finance_menu(self):
        execution_views = (
            self.module_root / 'views' / 'report_execution_views.xml'
        ).read_text()
        self.assertNotIn('id="account.menu_finance"', execution_views)
        self.assertIn('parent="account.menu_finance"', execution_views)

    def test_listing_version_and_capability_copy_match_current_bytes(self):
        listing = (
            self.module_root / 'static' / 'description' / 'index.html'
        ).read_text()
        self.assertIn('v%s' % self.manifest['version'], listing)
        self.assertNotIn('no web assets bundle', listing)
        self.assertNotIn(
            'prints plain numeric values with no currency symbol', listing,
        )
        self.assertIn('ERP Heritage - Your Odoo Partner', (
            self.module_root / 'hooks.py'
        ).read_text())
