# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestInfoRequestMobile(TransactionCase):

    def setUp(self):
        super().setUp()
        self.action = self.env.ref(
            'wujia_info_request.action_wujia_info_update_request'
        )
        self.kanban_view = self.env.ref(
            'wujia_mobile_portal_info_request.view_wujia_info_update_request_kanban'
        )

    def test_01_action_view_modes(self):
        """Verify action window includes kanban in dual-device order."""
        self.assertIn('kanban', self.action.view_mode)
        view_ids = self.action.view_ids.sorted('sequence')
        modes = [v.view_mode for v in view_ids]
        self.assertEqual(modes, ['list', 'kanban', 'form'])
        self.assertEqual(view_ids[0].view_mode, 'list')
        self.assertEqual(view_ids[1].view_mode, 'kanban')
        self.assertEqual(view_ids[2].view_mode, 'form')

    def test_02_kanban_view_structure(self):
        """Verify mobile kanban view contains wj_mobile_kanban and wj_mobile_card."""
        self.assertTrue(self.kanban_view)
        arch = self.kanban_view.arch
        self.assertIn('wj_mobile_kanban', arch)
        self.assertIn('wj_mobile_card', arch)

    def test_03_auto_install_flag(self):
        """Verify module has auto_install enabled."""
        module = self.env['ir.module.module'].search([
            ('name', '=', 'wujia_mobile_portal_info_request')
        ])
        self.assertTrue(module)
        self.assertTrue(module.auto_install)