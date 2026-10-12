# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWujiaMobileFranchiseInspection(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({
            'name': 'Test Store Partner Mobile Inspection',
            'is_franchise': True,
        })
        self.store = self.env['wujia.franchise.management'].create({
            'code': 'INSMOBI01',
            'name': 'Inspection Mobile Test Store',
            'partner_id': self.partner.id,
        })

    def test_01_mobile_view_exists(self):
        """Verify mobile kanban view for franchise inspection exists."""
        view = self.env.ref('wujia_mobile_franchise_inspection.view_wujia_franchise_inspection_kanban_mobile', raise_if_not_found=False)
        self.assertTrue(view, "Mobile kanban view for wujia.franchise.inspection should exist.")
        self.assertEqual(view.model, 'wujia.franchise.inspection')

    def test_02_supervision_schedule_kanban_view_exists(self):
        """Verify mobile kanban view for supervision schedule exists."""
        view = self.env.ref('wujia_mobile_franchise_inspection.view_wujia_supervision_schedule_kanban_mobile', raise_if_not_found=False)
        self.assertTrue(view, "Mobile kanban view for wujia.supervision.schedule should exist.")
        self.assertEqual(view.model, 'wujia.supervision.schedule')

    def test_03_configuration_kanban_views_exist(self):
        """Verify mobile kanban views exist for configuration models."""
        models = [
            ('wujia_mobile_franchise_inspection.view_wujia_franchise_inspection_template_kanban_mobile', 'wujia.franchise.inspection.template'),
            ('wujia_mobile_franchise_inspection.view_wujia_franchise_inspection_category_kanban_mobile', 'wujia.franchise.inspection.category'),
            ('wujia_mobile_franchise_inspection.view_wujia_franchise_inspection_question_kanban_mobile', 'wujia.franchise.inspection.question'),
            ('wujia_mobile_franchise_inspection.view_wujia_franchise_inspection_grade_kanban_mobile', 'wujia.franchise.inspection.grade'),
        ]
        for xml_id, model in models:
            view = self.env.ref(xml_id, raise_if_not_found=False)
            self.assertTrue(view, f"Mobile kanban view {xml_id} should exist.")
            self.assertEqual(view.model, model)

    def test_04_action_view_ids_configured(self):
        """Verify configuration actions contain kanban in view_ids."""
        actions = [
            'wujia_franchise_inspection.action_wujia_franchise_inspection_template',
            'wujia_franchise_inspection.action_wujia_franchise_inspection_category',
            'wujia_franchise_inspection.action_wujia_franchise_inspection_question',
            'wujia_franchise_inspection.action_wujia_franchise_inspection_grade',
            'wujia_franchise_inspection.action_franchise_needed_inspection',
        ]
        for act_id in actions:
            action = self.env.ref(act_id, raise_if_not_found=False)
            self.assertTrue(action, f"Action {act_id} should exist.")
            modes = [v.view_mode for v in action.view_ids]
            self.assertIn('kanban', modes, f"Action {act_id} view_ids should include kanban mode.")
