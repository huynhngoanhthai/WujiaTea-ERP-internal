# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWujiaMobileFranchise(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({
            'name': 'Test Store Partner Mobile Franchise',
            'is_franchise': True,
        })
        self.store = self.env['wujia.franchise.management'].create({
            'code': 'FRMOBI01',
            'name': 'Franchise Mobile Store',
            'partner_id': self.partner.id,
        })

    def test_01_mobile_view_exists(self):
        """Verify mobile kanban view for franchise management exists."""
        view = self.env.ref('wujia_mobile_franchise.view_wujia_franchise_management_kanban_mobile', raise_if_not_found=False)
        self.assertTrue(view, "Mobile kanban view for wujia.franchise.management should exist.")
        self.assertEqual(view.model, 'wujia.franchise.management')

    def test_02_area_ward_member_kanban_views_exist(self):
        """Verify mobile kanban views exist for area, ward, and member models."""
        models = [
            ('wujia_mobile_franchise.view_res_area_kanban_mobile', 'res.area'),
            ('wujia_mobile_franchise.view_res_ward_kanban_mobile', 'res.ward'),
            ('wujia_mobile_franchise.view_wujia_franchise_member_kanban_mobile', 'wujia.franchise.member'),
        ]
        for xml_id, model in models:
            view = self.env.ref(xml_id, raise_if_not_found=False)
            self.assertTrue(view, f"Mobile kanban view {xml_id} should exist.")
            self.assertEqual(view.model, model)

    def test_03_actions_view_ids_configured(self):
        """Verify area, ward, and member actions contain kanban in view_ids."""
        actions = [
            'wujia_core.action_res_area',
            'wujia_core.action_res_ward',
            'wujia_franchise.action_wujia_franchise_member',
        ]
        for act_id in actions:
            action = self.env.ref(act_id, raise_if_not_found=False)
            self.assertTrue(action, f"Action {act_id} should exist.")
            modes = [v.view_mode for v in action.view_ids]
            self.assertIn('kanban', modes, f"Action {act_id} view_ids should include kanban mode.")
