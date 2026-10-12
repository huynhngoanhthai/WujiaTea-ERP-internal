"""Task STT3 — luật bù hàng dùng chung mọi kênh (12 acceptance BA; phần HTTP ở wujia_portal_return).

Chạy: `--test-tags wujia_return_ct`.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.wujia_return.models.wujia_return_request import ORDER_WINDOW_DAYS

from .common import ReturnFixture, load_vi


@tagged('post_install', '-at_install', 'wujia_return_ct')
class TestEligibleOrders(TransactionCase, ReturnFixture):
    """Đơn đã xác nhận, đúng cửa hàng, giao hoàn tất toàn bộ chưa quá 10 ngày (WJ-RETURN-001)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_return_data()

    def _eligible(self, franchise):
        domain = self.env['wujia.return.request']._portal_eligible_order_domain([franchise.id])
        return self.env['sale.order'].search(domain)

    def _outgoing(self, order):
        return order.picking_ids.filtered(lambda p: p.picking_type_id.code == 'outgoing')

    def test_confirmed_recent_order_is_eligible(self):
        self.assertIn(self.order_ok, self._eligible(self.franchise))

    def test_old_order_delivered_recently_is_eligible(self):
        self.assertLess(self.order_old.date_order, fields.Datetime.now() - timedelta(days=ORDER_WINDOW_DAYS))
        self.assertIn(self.order_old, self._eligible(self.franchise))

    def test_undelivered_order_excluded(self):
        self.assertFalse(self.order_undelivered.wj_delivery_done_date)
        self.assertNotIn(self.order_undelivered, self._eligible(self.franchise))

    def test_delivered_beyond_window_excluded(self):
        self.assertNotIn(self.order_expired, self._eligible(self.franchise))

    def test_draft_order_excluded(self):
        self.assertNotIn(self.order_draft, self._eligible(self.franchise))

    def test_other_store_order_excluded(self):
        self.assertNotIn(self.order_other, self._eligible(self.franchise))

    def test_backorder_waits_for_last_delivery(self):
        order = self._order(self.franchise, self.product, confirm=True)
        first = self._deliver(order, days_ago=12, qty=2)
        backorder = self._outgoing(order) - first
        self.assertEqual(len(backorder), 1)
        self.assertNotIn(backorder.state, ('done', 'cancel'))
        self.assertFalse(order.wj_delivery_done_date)
        self.assertNotIn(order, self._eligible(self.franchise))
        self._deliver(order, days_ago=1, picking=backorder)
        self.assertEqual(order.wj_delivery_done_date, backorder.date_done)
        self.assertIn(order, self._eligible(self.franchise))

    def test_cancelled_backorder_closes_delivery(self):
        order = self._order(self.franchise, self.product, confirm=True)
        first = self._deliver(order, days_ago=4, qty=2)
        (self._outgoing(order) - first).action_cancel()
        self.assertEqual(order.wj_delivery_done_date, first.date_done)
        self.assertIn(order, self._eligible(self.franchise))

    def test_fully_cancelled_delivery_has_no_mark(self):
        order = self._order(self.franchise, self.product, confirm=True)
        self._outgoing(order).action_cancel()
        self.assertFalse(order.wj_delivery_done_date)
        self.assertNotIn(order, self._eligible(self.franchise))

    def test_pending_incoming_return_does_not_reopen_delivery(self):
        order = self.order_ok
        out = self._outgoing(order)
        self.env['stock.picking'].create({
            'picking_type_id': self.env.ref('stock.picking_type_in').id,
            'partner_id': order.partner_id.id,
            'sale_id': order.id,
            'location_id': out.location_dest_id.id,
            'location_dest_id': out.location_id.id,
        })
        self.assertEqual(order.wj_delivery_done_date, out.date_done)
        self.assertIn(order, self._eligible(self.franchise))


@tagged('post_install', '-at_install', 'wujia_return_ct')
class TestCompensationConfig(TransactionCase, ReturnFixture):
    """Acceptance #6 — thiếu cấu hình bù thì báo bằng câu nghiệp vụ."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # J-V6: câu gốc là tiếng Anh ⇒ assert câu tiếng Việt chạy ở vi_VN.
        cls.env = load_vi(cls.env)
        cls._setup_return_data()
        cls.Req = cls.env['wujia.return.request']

    def test_configured_product_passes(self):
        self.assertIsNone(self.Req._portal_check_product_config(self.product))

    def test_unconfigured_product_gets_business_message(self):
        msg = self.Req._portal_check_product_config(self.product_noconf)
        self.assertIn('chưa được cấu hình chính sách bù hàng', msg)

    def test_accumulate_needs_positive_integer_ratio(self):
        self.product.compensation_unit_qty = 2.5
        self.assertIsNotNone(self.Req._portal_check_product_config(self.product))
        self.product.compensation_unit_qty = 10.0
        self.assertIsNone(self.Req._portal_check_product_config(self.product))

    def test_accumulate_ratio_zero_rejected(self):
        # `@api.constrains` của product chặn ghi 0 vào DB, nên dựng bản ghi
        # in-memory để kiểm đúng lớp luật portal (dữ liệu cũ/import có thể lọt).
        ghost = self.env['product.product'].new({
            'name': 'ghost',
            'compensation_enabled': True,
            'compensation_policy': 'accumulate',
            'compensation_claim_uom_id': self.uom_kg.id,
            'compensation_delivery_uom_id': self.uom_kg.id,
            'compensation_unit_qty': 0.0,
        })
        self.assertIsNotNone(self.Req._portal_check_product_config(ghost))

    def test_exact_policy_rejects_uom_of_another_family(self):
        self.product.compensation_policy = 'exact'
        self.product.compensation_delivery_uom_id = self.uom_unit
        self.assertIsNotNone(self.Req._portal_check_product_config(self.product))


@tagged('post_install', '-at_install', 'wujia_return_ct')
class TestCompensationOrder(TransactionCase, ReturnFixture):
    """Acceptance #10/#11/#12 — SO bù 0đ + đúng thuế + 'sent'; huỷ SO thì đóng quyền lợi."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_return_data()

    def _approved_request(self, qty=20.0):
        rr = self._request(state='approved', resolution_type='compensation',
                           approved_qty=qty, approved_uom_id=self.uom_kg.id,
                           compensation_product_id=self.product.id,
                           compensation_delivery_uom_id=self.uom_kg.id,
                           compensation_unit_qty=10.0,
                           compensation_policy='accumulate')
        rr.approved_date = fields.Datetime.now()
        return rr

    def _process(self, requests):
        wizard = self.env['wujia.compensation.process.wizard'].with_context(
            active_ids=requests.ids).create({})
        wizard.action_confirm()
        return requests.allocation_ids.sale_order_id

    def test_so_is_zero_priced_sent_and_not_confirmed(self):
        rr = self._approved_request()
        order = self._process(rr)
        self.assertEqual(order.state, 'sent')
        self.assertEqual(order.amount_untaxed, 0.0)
        self.assertTrue(order.is_return_order)
        line = order.order_line[0]
        self.assertEqual(line.price_unit, 0.0)
        # Thuế lấy theo cấu hình sản phẩm, không bị ép rỗng.
        self.assertEqual(line.tax_ids, self.tax)

    def test_progress_fields_after_allocation(self):
        rr = self._approved_request()
        self._process(rr)
        self.assertEqual(rr.allocated_qty, 20.0)
        self.assertEqual(rr.compensated_qty, 0.0)   # chưa giao thì chưa tính
        self.assertEqual(rr.remaining_qty, 20.0)
        self.assertEqual(rr.compensation_status, 'allocated')
        self.assertEqual(rr.state, 'processing')

    def test_cancel_so_closes_request_without_restoring_entitlement(self):
        rr = self._approved_request()
        order = self._process(rr)
        order._action_cancel()
        self.assertEqual(rr.allocation_ids.mapped('state'), ['cancel'])
        self.assertEqual(rr.allocation_ids.released_qty, 0.0)  # KHÔNG hoàn quyền lợi
        self.assertEqual(rr.state, 'done')
        self.assertTrue(rr.resolved_date)

    def test_cancelled_request_is_not_reprocessable(self):
        rr = self._approved_request()
        order = self._process(rr)
        order._action_cancel()
        wizard = self.env['wujia.compensation.process.wizard']
        self.assertFalse(wizard._is_eligible(rr))

    def test_cancel_normal_order_does_not_touch_requests(self):
        rr = self._approved_request()
        self._process(rr)
        self.order_ok._action_cancel()
        self.assertEqual(rr.state, 'processing')
        self.assertEqual(rr.allocation_ids.mapped('state'), ['allocated'])
