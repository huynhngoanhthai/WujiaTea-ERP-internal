# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPortalExamMobile(TransactionCase):

    def setUp(self):
        super().setUp()
        self.actions = [
            self.env.ref('wujia_exam.action_wujia_exam_session'),
            self.env.ref('wujia_exam.action_wujia_exam_registration'),
            self.env.ref('wujia_exam.action_wujia_exam_course'),
            self.env.ref('wujia_exam.action_wujia_exam_time_slot'),
        ]
        self.kanban_views = [
            self.env.ref('wujia_mobile_portal_exam.view_wujia_exam_session_kanban_mobile'),
            self.env.ref('wujia_mobile_portal_exam.view_wujia_exam_registration_kanban_mobile'),
            self.env.ref('wujia_mobile_portal_exam.view_wujia_exam_course_kanban_mobile'),
            self.env.ref('wujia_mobile_portal_exam.view_wujia_exam_time_slot_kanban_mobile'),
        ]

    def test_01_actions_dual_device_modes(self):
        """Verify all 4 actions include list, kanban, form in exact dual-device sequence."""
        for act in self.actions:
            self.assertIn('kanban', act.view_mode)
            view_ids = act.view_ids.sorted('sequence')
            modes = [v.view_mode for v in view_ids]
            self.assertEqual(modes, ['list', 'kanban', 'form'], f"Failed on action {act.name}")
            self.assertEqual(view_ids[0].view_mode, 'list')
            self.assertEqual(view_ids[1].view_mode, 'kanban')
            self.assertEqual(view_ids[2].view_mode, 'form')

    def test_02_kanban_views_structure(self):
        """Verify all 4 mobile kanban views contain wj_mobile_kanban and wj_mobile_card."""
        for view in self.kanban_views:
            self.assertTrue(view)
            arch = view.arch
            self.assertIn('wj_mobile_kanban', arch, f"Missing wj_mobile_kanban in {view.name}")
            self.assertIn('wj_mobile_card', arch, f"Missing wj_mobile_card in {view.name}")

    def test_03_auto_install_flag(self):
        """Verify module has auto_install enabled."""
        module = self.env['ir.module.module'].search([
            ('name', '=', 'wujia_mobile_portal_exam')
        ])
        self.assertTrue(module)
        self.assertTrue(module.auto_install)
