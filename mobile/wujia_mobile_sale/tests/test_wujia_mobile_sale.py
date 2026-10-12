# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWujiaMobileSale(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({
            'name': 'Test Store Partner Mobile',
            'is_franchise': True,
        })
        self.store = self.env['wujia.franchise.management'].create({
            'code': 'MOBI01',
            'name': 'Mobile Test Store',
            'partner_id': self.partner.id,
        })
        self.so = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'franchise_id': self.store.id,
            'is_portal_order': True,
        })

    def test_01_mobile_card_helpers(self):
        """Verify mobile card title and badge class helpers compute correctly."""
        self.assertEqual(self.so.mobile_badge_class, 'wj_mobile_badge--warning')
        self.assertIn('Mobile Test Store', self.so.mobile_card_title)

    def test_02_views_exist(self):
        """Verify mobile kanban view loads cleanly."""
        kanban_view = self.env.ref('wujia_mobile_sale.view_sale_order_kanban_wujia_mobile', raise_if_not_found=False)
        self.assertTrue(kanban_view, "Mobile kanban view for sale.order should exist.")
        self.assertEqual(kanban_view.model, 'sale.order')

    def test_03_mobile_form_view_arch(self):
        """Verify mobile form view inherits and renders cleanly."""
        form_view = self.env.ref('wujia_mobile_sale.view_sale_order_form_wujia_mobile', raise_if_not_found=False)
        self.assertTrue(form_view, "Mobile form view for sale.order should exist.")
        arch = self.env['sale.order'].get_view(form_view.id, 'form')['arch']
        self.assertIn('o_wujia_mobile_form', arch)
        self.assertIn('o_wujia_mb_sticky_actions', arch)

