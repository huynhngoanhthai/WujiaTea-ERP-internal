from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'wujia_sale')
class TestSaleOrderGift(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Store Partner Test',
        })
        cls.regular_product = cls.env['product.product'].create({
            'name': 'Regular Milk Tea',
            'type': 'consu',
            'list_price': 50000.0,
            'sale_ok': True,
        })
        cls.gift_product = cls.env['product.product'].create({
            'name': 'Free Tasting Syrup',
            'type': 'consu',
            'list_price': 25000.0,
            'sale_ok': True,
        })

        cls.manager_user = cls.env['res.users'].create({
            'name': 'Sales Manager User',
            'login': 'sales_manager_test',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('sales_team.group_sale_manager').id,
            ])],
        })
        cls.regular_user = cls.env['res.users'].create({
            'name': 'Standard User',
            'login': 'regular_user_test',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
            ])],
        })

        cls.order1 = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [(0, 0, {
                'product_id': cls.regular_product.id,
                'product_uom_qty': 2.0,
                'price_unit': 50000.0,
            })],
        })
        cls.order2 = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [(0, 0, {
                'product_id': cls.regular_product.id,
                'product_uom_qty': 3.0,
                'price_unit': 50000.0,
            })],
        })

    def test_add_gift_success_multi_so(self):
        wizard = self.env['wujia.sale.order.gift.wizard'].with_user(self.manager_user).with_context(
            active_ids=[self.order1.id, self.order2.id],
            active_model='sale.order',
        ).create({
            'product_id': self.gift_product.id,
            'quantity': 2.0,
        })
        res = wizard.action_apply_gift()
        self.assertEqual(res.get('type'), 'ir.actions.act_window_close')

        for order in (self.order1, self.order2):
            self.assertEqual(len(order.order_line), 2)
            gift_line = order.order_line.filtered(lambda l: l.wujia_is_gift)
            self.assertTrue(gift_line)
            self.assertEqual(gift_line.product_id, self.gift_product)
            self.assertEqual(gift_line.product_uom_qty, 2.0)
            self.assertEqual(gift_line.price_unit, 0.0)
            self.assertEqual(gift_line.discount, 0.0)
            self.assertEqual(gift_line.price_subtotal, 0.0)

            # Verify message logged in chatter
            messages = order.message_ids.filtered(lambda m: self.gift_product.display_name in (m.body or ''))
            self.assertTrue(messages)

    def test_atomic_rollback_on_non_draft(self):
        # Set order2 to 'sale' state
        self.order2.state = 'sale'

        wizard = self.env['wujia.sale.order.gift.wizard'].with_user(self.manager_user).with_context(
            active_ids=[self.order1.id, self.order2.id],
            active_model='sale.order',
        ).create({
            'product_id': self.gift_product.id,
            'quantity': 1.0,
        })

        with self.assertRaises(UserError) as cm:
            wizard.action_apply_gift()

        self.assertIn(self.order2.name, str(cm.exception))
        # Ensure order1 was NOT modified (atomic rollback)
        self.assertEqual(len(self.order1.order_line), 1)
        self.assertFalse(self.order1.order_line.filtered(lambda l: l.wujia_is_gift))

    def test_zero_price_protection(self):
        gift_line = self.env['sale.order.line'].create({
            'order_id': self.order1.id,
            'product_id': self.gift_product.id,
            'product_uom_qty': 1.0,
            'wujia_is_gift': True,
        })
        self.assertEqual(gift_line.price_unit, 0.0)
        self.assertEqual(gift_line.discount, 0.0)

        # Attempt to overwrite price and discount
        gift_line.write({'price_unit': 20000.0, 'discount': 10.0})
        self.assertEqual(gift_line.price_unit, 0.0)
        self.assertEqual(gift_line.discount, 0.0)

        # Recompute price
        gift_line._compute_price_unit()
        self.assertEqual(gift_line.price_unit, 0.0)

    def test_wizard_validation(self):
        wizard = self.env['wujia.sale.order.gift.wizard'].with_user(self.manager_user).with_context(
            active_ids=[self.order1.id],
        ).create({
            'product_id': self.gift_product.id,
            'quantity': 0.0,
        })
        with self.assertRaises(UserError):
            wizard.action_apply_gift()

    def test_access_rights(self):
        with self.assertRaises(AccessError):
            self.env['wujia.sale.order.gift.wizard'].with_user(self.regular_user).with_context(
                active_ids=[self.order1.id],
            ).create({
                'product_id': self.gift_product.id,
                'quantity': 1.0,
            })
