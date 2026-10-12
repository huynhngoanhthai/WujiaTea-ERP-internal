# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWujiaMobileFranchiseContract(TransactionCase):

    def test_01_mobile_kanban_view_exists(self):
        """Verify mobile kanban view for franchise contract exists."""
        view = self.env.ref('wujia_mobile_franchise_contract.view_wujia_franchise_contract_kanban_mobile', raise_if_not_found=False)
        self.assertTrue(view, "Mobile kanban view for wujia.franchise.contract should exist.")
        self.assertEqual(view.model, 'wujia.franchise.contract')

    def test_02_action_view_ids_configured(self):
        """Verify action_wujia_franchise_contract contains view_ids list, kanban, form."""
        action = self.env.ref('wujia_franchise_contract.action_wujia_franchise_contract', raise_if_not_found=False)
        self.assertTrue(action, "Action action_wujia_franchise_contract should exist.")
        modes = [v.view_mode for v in action.view_ids]
        self.assertIn('list', modes)
        self.assertIn('kanban', modes)
        self.assertIn('form', modes)
