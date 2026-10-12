# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFranchiseOperationsMobile(TransactionCase):

    def setUp(self):
        super().setUp()
        self.actions = [
            self.env.ref('wujia_franchise_operations.action_wujia_franchise_employee'),
            self.env.ref('wujia_franchise_operations.action_wujia_franchise_employee_assignment'),
            self.env.ref('wujia_franchise_operations.action_wujia_franchise_work_schedule'),
            self.env.ref('wujia_franchise_operations.action_wujia_franchise_revenue'),
            self.env.ref('wujia_franchise_operations.action_wujia_franchise_expense'),
            self.env.ref('wujia_franchise_operations.action_wujia_franchise_shift_template'),
            self.env.ref('wujia_franchise_operations.action_wujia_franchise_expense_category'),
        ]
        self.kanban_views = [
            self.env.ref('wujia_mobile_franchise_operations.view_wujia_franchise_employee_kanban_mobile'),
            self.env.ref('wujia_mobile_franchise_operations.view_wujia_franchise_employee_assignment_kanban_mobile'),
            self.env.ref('wujia_mobile_franchise_operations.view_wujia_franchise_work_schedule_kanban_mobile'),
            self.env.ref('wujia_mobile_franchise_operations.view_wujia_franchise_revenue_kanban_mobile'),
            self.env.ref('wujia_mobile_franchise_operations.view_wujia_franchise_expense_kanban_mobile'),
            self.env.ref('wujia_mobile_franchise_operations.view_wujia_franchise_shift_template_kanban_mobile'),
            self.env.ref('wujia_mobile_franchise_operations.view_wujia_franchise_expense_category_kanban_mobile'),
        ]

    def test_01_actions_dual_device_modes(self):
        """Verify all 7 actions include list, kanban in exact dual-device sequence."""
        for act in self.actions:
            self.assertIn('kanban', act.view_mode)
            view_ids = act.view_ids.sorted('sequence')
            modes = [v.view_mode for v in view_ids]
            self.assertEqual(modes[0], 'list', f"First mode should be list on action {act.name}")
            self.assertEqual(modes[1], 'kanban', f"Second mode should be kanban on action {act.name}")

    def test_02_kanban_views_structure(self):
        """Verify all 7 mobile kanban views contain wj_mobile_kanban and wj_mobile_card."""
        for view in self.kanban_views:
            self.assertTrue(view)
            arch = view.arch
            self.assertIn('wj_mobile_kanban', arch, f"Missing wj_mobile_kanban in {view.name}")
            self.assertIn('wj_mobile_card', arch, f"Missing wj_mobile_card in {view.name}")

    def test_03_auto_install_flag(self):
        """Verify module has auto_install enabled."""
        module = self.env['ir.module.module'].search([
            ('name', '=', 'wujia_mobile_franchise_operations')
        ])
        self.assertTrue(module)
        self.assertTrue(module.auto_install)
