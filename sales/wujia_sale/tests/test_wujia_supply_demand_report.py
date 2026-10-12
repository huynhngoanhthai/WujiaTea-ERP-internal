# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'wujia_sale')
class TestWujiaSupplyDemandReport(TransactionCase):
    """Automated Unit Tests for Muc Q: Today's Order Supply & Demand Report.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env['res.partner']
        cls.Product = cls.env['product.product']
        cls.SaleOrder = cls.env['sale.order']
        cls.StockQuant = cls.env['stock.quant']
        cls.StockLocation = cls.env['stock.location']

        cls.customer = cls.Partner.create({'name': 'Test Franchise Customer'})

        cls.product_1 = cls.Product.create({
            'name': 'Test Hong Tra Dai Loan',
            'default_code': 'TEST_TEA_01',
            'is_storable': True,  # Odoo 19: chỉ hàng lưu kho mới có quant
            'list_price': 50000,
        })
        cls.product_2 = cls.Product.create({
            'name': 'Test Sua Tuoi',
            'default_code': 'TEST_MILK_02',
            'is_storable': True,  # Odoo 19: chỉ hàng lưu kho mới có quant
            'list_price': 70000,
        })

        # Create export location
        cls.export_location = cls.StockLocation.create({
            'name': 'Test Export Warehouse Location',
            'usage': 'internal',
            'is_export': True,
        })

        # Add stock quants to export location
        cls.StockQuant.create({
            'product_id': cls.product_1.id,
            'location_id': cls.export_location.id,
            'quantity': 500.0,
            'reserved_quantity': 0.0,
        })
        cls.StockQuant.create({
            'product_id': cls.product_2.id,
            'location_id': cls.export_location.id,
            'quantity': 100.0,
            'reserved_quantity': 0.0,
        })

    def test_01_supply_demand_report_computation(self):
        """Test report computation when Sale Orders are confirmed."""
        # Create confirmed Sale Order
        so = self.SaleOrder.create({
            'partner_id': self.customer.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.product_1.id,
                    'product_uom_qty': 200.0,
                    'price_unit': 50000,
                }),
                (0, 0, {
                    'product_id': self.product_2.id,
                    'product_uom_qty': 150.0,
                    'price_unit': 70000,
                }),
            ]
        })
        so.action_confirm()
        # Báo cáo là SQL view (_auto=False) ⇒ ORM không tự flush sale.order/line trước khi search.
        self.env.flush_all()

        # Query report model
        report_p1 = self.env['wujia.sale.supply.demand.report'].search([
            ('product_id', '=', self.product_1.id)
        ])
        self.assertTrue(report_p1, "Report record for product 1 must exist")
        self.assertEqual(report_p1.qty_ordered, 200.0)
        self.assertEqual(report_p1.qty_available, 500.0)
        self.assertEqual(report_p1.qty_shortage, 0.0)
        self.assertEqual(report_p1.warning_status, 'ok')

        report_p2 = self.env['wujia.sale.supply.demand.report'].search([
            ('product_id', '=', self.product_2.id)
        ])
        self.assertTrue(report_p2, "Report record for product 2 must exist")
        self.assertEqual(report_p2.qty_ordered, 150.0)
        self.assertEqual(report_p2.qty_available, 100.0)
        self.assertEqual(report_p2.qty_shortage, 50.0)
        self.assertEqual(report_p2.warning_status, 'warning')

    def test_02_action_and_menu_exist(self):
        """Verify action and menuitem for supply demand report."""
        action = self.env.ref('wujia_sale.action_wujia_sale_supply_demand_report')
        self.assertEqual(action.res_model, 'wujia.sale.supply.demand.report')

        menu = self.env.ref('wujia_sale.menu_wujia_sale_supply_demand_report')
        self.assertEqual(menu.action.id, action.id)
