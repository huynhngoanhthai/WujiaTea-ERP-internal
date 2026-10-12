# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'wujia_metabase_connector')
class TestMetabaseConnector(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.instance = cls.env['metabase.instance'].create({
            'name': 'Test Metabase Instance',
            'base_url': 'https://bi-test.wujiatea.com/',
            'embedding_secret': '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
            'token_expiry_minutes': 15,
        })
        cls.parent_menu = cls.env['ir.ui.menu'].create({
            'name': 'Test Parent Menu',
            'sequence': 99,
        })

    def test_01_instance_base_url_strip(self):
        """Verify trailing slash in base_url is automatically stripped."""
        self.assertEqual(self.instance.base_url, 'https://bi-test.wujiatea.com')

    def test_02_instance_constraints(self):
        """Verify token_expiry_minutes constraint."""
        with self.assertRaises(ValidationError):
            self.env['metabase.instance'].create({
                'name': 'Invalid Instance',
                'base_url': 'https://bi-invalid.com',
                'embedding_secret': 'secret',
                'token_expiry_minutes': 0,
            })

    def test_03_dashboard_creation_and_dynamic_menu(self):
        """Verify creating a dashboard dynamically generates an act_url action and ir.ui.menu."""
        dashboard = self.env['metabase.dashboard'].create({
            'name': 'Test Overview Dashboard',
            'instance_id': self.instance.id,
            'dashboard_id': 2,
            'show_under_menu_id': self.parent_menu.id,
            'height': 900,
        })

        self.assertTrue(dashboard.action_id, "Client action should be generated.")
        self.assertTrue(dashboard.menu_id, "Child menu item should be generated.")
        self.assertEqual(dashboard.menu_id.parent_id, self.parent_menu)
        self.assertEqual(dashboard.action_id.tag, "wujia_metabase_dashboard_client_action")

    def test_04_dashboard_unlink_cleans_menu(self):
        """Verify unlinking a dashboard deletes its generated menu and action."""
        dashboard = self.env['metabase.dashboard'].create({
            'name': 'Temporary Dashboard',
            'instance_id': self.instance.id,
            'dashboard_id': 3,
            'show_under_menu_id': self.parent_menu.id,
        })
        menu_id = dashboard.menu_id.id
        action_id = dashboard.action_id.id

        dashboard.unlink()

        self.assertFalse(self.env['ir.ui.menu'].browse(menu_id).exists(), "Generated menu should be deleted.")
        self.assertFalse(self.env['ir.actions.client'].browse(action_id).exists(), "Generated action should be deleted.")

    def test_05_dashboard_constraints(self):
        """Verify invalid dashboard_id raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.env['metabase.dashboard'].create({
                'name': 'Invalid ID',
                'instance_id': self.instance.id,
                'dashboard_id': -1,
            })
