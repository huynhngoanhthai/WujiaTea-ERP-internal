"""Cụm C5 — dữ liệu giao hàng portal (WJ-DELIVERY-005/006/007, WJ-HOME-003).

Chạy: `--test-tags wujia_delivery_c5`.

`get_upcoming_batches` và controller đều đọc `request` → phần dữ liệu Home/list test
qua HttpCase (đúng đường người dùng đi), phần mapping giờ test thẳng helper.
"""

import re
from datetime import datetime, timedelta

import pytz

from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase

from odoo.addons.wujia_portal_base.controllers.utils import (
    DEPARTURE_LABEL_ACTUAL, DEPARTURE_LABEL_PLANNED,
    departure_label, departure_value, format_order_names, to_local_dt,
)


class DeliveryFixture:
    """Fixture chung: 1 cửa hàng + 1 cửa hàng khác + 3 chuyến (sắp giao / đang giao / đã giao)."""

    @classmethod
    def _setup_delivery_data(cls):
        env = cls.env
        Partner = env['res.partner']
        Franchise = env['wujia.franchise.management']
        cls.franchise = Franchise.create({
            'code': 'HC5A', 'name': 'C5 store A', 'franchise_end_date': '2030-01-01',
            'partner_id': Partner.create({'name': 'C5A partner'}).id})
        cls.other = Franchise.create({
            'code': 'HC5B', 'name': 'C5 store B', 'franchise_end_date': '2030-01-01',
            'partner_id': Partner.create({'name': 'C5B partner'}).id})
        cls.product = env['product.product'].create({
            'name': 'C5 product', 'type': 'consu', 'list_price': 100_000})
        cls.picking_type = env['stock.warehouse'].search([], limit=1).out_type_id

        now = datetime.now()
        cls.tomorrow = now.replace(microsecond=0) + timedelta(days=1)
        # Chuyến sắp giao: 1 đơn chưa giao + 1 đơn đã huỷ (không được đếm).
        cls.batch_soon = cls._batch('C5/SOON', 'assigned', cls.tomorrow)
        cls.so_open = cls._order(cls.franchise)
        cls._picking(cls.so_open, cls.franchise, cls.batch_soon)
        cls.so_cancel = cls._order(cls.franchise)
        cls._picking(cls.so_cancel, cls.franchise, cls.batch_soon).action_cancel()
        # Chuyến đang giao: đã xuất phát thật, lịch dự kiến muộn hơn giờ thực tế.
        cls.batch_going = cls._batch('C5/GOING', 'delivering', cls.tomorrow + timedelta(hours=2))
        cls.batch_going.actual_departure = cls.tomorrow
        cls.so_going = cls._order(cls.franchise)
        cls._picking(cls.so_going, cls.franchise, cls.batch_going)
        # Chuyến đã giao xong: phải biến khỏi Home, vẫn còn ở /portal/delivery.
        cls.batch_done = cls._batch('C5/DONE', 'done', cls.tomorrow)
        cls.so_done = cls._order(cls.franchise)
        cls._picking(cls.so_done, cls.franchise, cls.batch_done)
        # Chuyến chưa đặt lịch: vẫn chưa giao nên phải hiện, xếp cuối.
        cls.batch_noplan = cls._batch('C5/NOPLAN', 'draft', False)
        cls.so_noplan = cls._order(cls.franchise)
        cls._picking(cls.so_noplan, cls.franchise, cls.batch_noplan)
        # Cửa hàng khác — không được rò sang.
        cls.batch_other = cls._batch('C5/OTHER', 'assigned', cls.tomorrow)
        cls._picking(cls._order(cls.other), cls.other, cls.batch_other)

    @classmethod
    def _batch(cls, name, status, planned):
        return cls.env['stock.picking.batch'].create({
            'name': name, 'delivery_batch_status': status, 'planned_departure': planned})

    @classmethod
    def _order(cls, franchise):
        return cls.env['sale.order'].create({
            'partner_id': franchise.partner_id.id,
            'franchise_id': franchise.id,
            'order_line': [(0, 0, {'product_id': cls.product.id, 'product_uom_qty': 2})],
        })

    @classmethod
    def _picking(cls, order, franchise, batch):
        return cls.env['stock.picking'].create({
            'picking_type_id': cls.picking_type.id,
            'partner_id': franchise.partner_id.id,
            'franchise_id': franchise.id,
            'sale_id': order.id,
            'batch_id': batch.id,
            'location_id': cls.picking_type.default_location_src_id.id,
            'location_dest_id': cls.picking_type.default_location_dest_id.id,
        })


@tagged('post_install', '-at_install', 'wujia_delivery_c5')
class TestDepartureMapping(TransactionCase, DeliveryFixture):
    """WJ-DELIVERY-007 — có giờ thực tế thì dùng giờ thực tế, chưa có thì giờ dự kiến."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_delivery_data()

    def test_planned_when_not_departed(self):
        dt, is_actual = departure_value(self.batch_soon)
        self.assertEqual(dt, self.batch_soon.planned_departure)
        self.assertFalse(is_actual)
        # J-V2: nhãn `_lt`, không có request ⇒ tiếng Anh; tiếng Việt kiểm qua .po.
        self.assertEqual(departure_label(is_actual), 'Departure (planned)')
        self.assertEqual(self._vi()._(DEPARTURE_LABEL_PLANNED), 'Xuất phát (dự kiến)')

    def test_actual_wins_after_departure(self):
        dt, is_actual = departure_value(self.batch_going)
        self.assertEqual(dt, self.batch_going.actual_departure)
        self.assertNotEqual(dt, self.batch_going.planned_departure)
        self.assertTrue(is_actual)
        self.assertEqual(departure_label(is_actual), 'Departure (actual)')
        self.assertEqual(self._vi()._(DEPARTURE_LABEL_ACTUAL), 'Xuất phát (thực tế)')

    def _vi(self):
        self.env['res.lang']._activate_lang('vi_VN')
        return self.env(context=dict(self.env.context, lang='vi_VN'))

    def test_order_names_shortened(self):
        self.assertEqual(format_order_names([]), '—')
        self.assertEqual(format_order_names(['S1', 'S2']), 'S1, S2')
        self.assertEqual(format_order_names(['S1', 'S2', 'S3', 'S4']), 'S1, S2 +2')


@tagged('post_install', '-at_install', 'wujia_delivery_c5')
class TestDeliveryPortalData(HttpCase, DeliveryFixture):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_delivery_data()
        cls.user = cls.env['res.users'].create({
            'name': 'c5_owner', 'login': 'c5_owner', 'password': 'c5_owner',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        cls.env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.franchise.id, 'role': 'owner'})

    def _get(self, url):
        self.authenticate('c5_owner', 'c5_owner')
        res = self.url_open(url, timeout=30)
        self.assertEqual(res.status_code, 200)
        return res.text

    @staticmethod
    def _text(html):
        return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))

    @classmethod
    def _chip_all(cls, html):
        return int(re.search(r'Tất cả\s*(\d+)', cls._text(html)).group(1))

    @classmethod
    def _home_delivery_block(cls, html):
        """Chỉ phần "Giao hàng sắp tới" — Home còn block Đơn hàng gần đây cũng in mã SO."""
        text = cls._text(html)
        start = text.index('Giao hàng sắp tới')
        return text[start:text.index('Đơn hàng gần đây', start)]

    # ---- WJ-DELIVERY-006 ----------------------------------------------
    def test_chip_all_follows_search(self):
        full = self._chip_all(self._get('/portal/delivery'))
        filtered_html = self._get('/portal/delivery?q=%s' % self.batch_going.name)
        self.assertEqual(self._chip_all(filtered_html), 1)
        self.assertIn(self.batch_going.name, filtered_html)
        self.assertNotIn(self.batch_soon.name, filtered_html)
        # Xoá search → count trở về tập đầy đủ theo current store.
        self.assertEqual(self._chip_all(self._get('/portal/delivery')), full)
        self.assertGreaterEqual(full, 3)

    def test_status_chip_does_not_zero_other_chips(self):
        html = self._get('/portal/delivery?bs=done')
        self.assertEqual(self._chip_all(html), self._chip_all(self._get('/portal/delivery')))

    # ---- WJ-DELIVERY-007 (đường render thật) ---------------------------
    def test_list_shows_actual_departure(self):
        html = self._get('/portal/delivery?q=%s' % self.batch_going.name)
        self.assertIn('Xuất phát (thực tế)', html)
        tz = pytz.timezone('Asia/Ho_Chi_Minh')
        actual = to_local_dt(self.batch_going.actual_departure, tz).strftime('%d/%m · %H:%M')
        planned = to_local_dt(self.batch_going.planned_departure, tz).strftime('%d/%m · %H:%M')
        self.assertIn(actual, self._text(html))
        self.assertNotIn(planned, self._text(html))

    def test_detail_labels_planned_when_not_departed(self):
        html = self._get('/portal/delivery/%d' % self.batch_soon.id)
        self.assertIn('Xuất phát (dự kiến)', html)
        self.assertNotIn('Xuất phát (thực tế)', html)

    # ---- WJ-HOME-003 + WJ-DELIVERY-005 ---------------------------------
    def test_home_hides_finished_batches(self):
        block = self._home_delivery_block(self._get('/portal'))
        self.assertIn(self.batch_soon.name, block)
        self.assertNotIn(self.batch_done.name, block)
        self.assertNotIn(self.batch_other.name, block)

    def test_home_counts_only_undelivered_orders(self):
        block = self._home_delivery_block(self._get('/portal'))
        # so_open + so_going + so_noplan; chuyến đã giao và phiếu huỷ không tính.
        self.assertIn('3 đơn chưa giao', block)
        self.assertIn(self.so_open.name, block)
        self.assertNotIn(self.so_cancel.name, block)
        self.assertNotIn(self.so_done.name, block)

    def test_home_prefers_scheduled_batches(self):
        """Chuyến có lịch đứng trước; chuyến chưa đặt lịch xếp cuối (limit 2 nên chưa hiện)."""
        block = self._home_delivery_block(self._get('/portal'))
        self.assertIn(self.batch_soon.name, block)
        self.assertIn(self.batch_going.name, block)
        self.assertNotIn(self.batch_noplan.name, block)


@tagged('post_install', '-at_install', 'wujia_delivery_c5')
class TestHomeUnscheduledOnly(HttpCase, DeliveryFixture):
    """Ca UAT: cửa hàng chỉ có 1 chuyến chưa hoàn thành và chuyến đó CHƯA đặt lịch."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        partner = cls.env['res.partner'].create({'name': 'C5C partner'})
        cls.franchise = cls.env['wujia.franchise.management'].create({
            'code': 'HC5C', 'name': 'C5 store C', 'franchise_end_date': '2030-01-01',
            'partner_id': partner.id})
        cls.product = cls.env['product.product'].create({
            'name': 'C5C product', 'type': 'consu', 'list_price': 50_000})
        cls.picking_type = cls.env['stock.warehouse'].search([], limit=1).out_type_id
        cls.batch = cls._batch('C5/NOSCHED', 'draft', False)
        cls.order = cls._order(cls.franchise)
        cls._picking(cls.order, cls.franchise, cls.batch)
        user = cls.env['res.users'].create({
            'name': 'c5_owner_c', 'login': 'c5_owner_c', 'password': 'c5_owner_c',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        cls.env['wujia.franchise.member'].create({
            'user_id': user.id, 'franchise_id': cls.franchise.id, 'role': 'owner'})

    def test_home_shows_unscheduled_batch(self):
        self.authenticate('c5_owner_c', 'c5_owner_c')
        res = self.url_open('/portal', timeout=30)
        self.assertEqual(res.status_code, 200)
        block = TestDeliveryPortalData._home_delivery_block(res.text)
        self.assertIn('1 đơn chưa giao', block)
        self.assertIn(self.batch.name, block)
        self.assertIn(self.order.name, block)
        self.assertNotIn('Chưa có chuyến giao sắp tới', block)
