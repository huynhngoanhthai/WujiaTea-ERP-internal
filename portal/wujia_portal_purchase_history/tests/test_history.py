"""Sprint 49 — cụm E Lịch sử đặt hàng (WJ-PH-002 / -003 / -007).

Chạy: `--test-tags wujia_history`.

  1. `TestHistoryTimezone` — quy đổi UTC↔giờ user khi HIỂN THỊ và khi LỌC theo ngày,
     kể cả user có tz rỗng / tz rác (không được nổ trang).
  2. `TestHistoryStatus`   — 5 nhãn trạng thái gộp (đơn + chuyến giao) và domain lọc
     tương ứng, đặc biệt nhánh 'sale' không được nuốt đơn chưa có chuyến.
  3. `TestHistoryPageSize` — WJ-PH-008: mặc định 10 dòng/trang + whitelist option.

Không import `account.tests.common` (freezegun cũ trong env, xem Sprint 48).
"""

from datetime import date, datetime, timedelta

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.wujia_portal_base.controllers.utils import (
    DEFAULT_PORTAL_TZ, local_day_range_utc, portal_tz, to_local_dt,
)
from odoo.addons.wujia_portal_purchase_history.controllers.portal import (
    PAGE_SIZE, PAGE_SIZE_OPTIONS, _history_row_vals, _order_status, _parse_page_size,
    _status_domain,
)


class HistoryCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # J-V2: nhãn trạng thái của portal_base là `_lt` (câu gốc EN) ⇒ chạy ở vi_VN để giữ assert tiếng Việt.
        cls.env['res.lang']._activate_lang('vi_VN')
        cls.env = cls.env(context=dict(cls.env.context, lang='vi_VN'))
        cls.partner = cls.env['res.partner'].create({'name': 'History Test Store'})
        cls.franchise = cls.env['wujia.franchise.management'].create({
            'code': 'HIST01',
            'name': 'Cửa hàng test lịch sử',
            'partner_id': cls.partner.id,
            'franchise_end_date': date.today() + timedelta(days=365),
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Trà sữa test',
            'is_storable': True,
            'list_price': 10000.0,
        })

    @classmethod
    def _make_order(cls, state='draft'):
        order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'franchise_id': cls.franchise.id,
            'order_line': [(0, 0, {
                'product_id': cls.product.id,
                'product_uom_qty': 2.0,
            })],
        })
        if state == 'sale':
            order.action_confirm()
        elif state == 'sent':
            order.state = 'sent'
        return order


@tagged('post_install', '-at_install', 'wujia_history')
class TestHistoryTimezone(HistoryCommon):
    """WJ-PH-002 — portal hiện sớm 7 giờ + lọc ngày lệch nửa ngày."""

    def _tz_vn(self):
        self.env.user.tz = 'Asia/Ho_Chi_Minh'
        return portal_tz(self.env)

    def test_display_shifts_to_user_tz(self):
        # BA đo: SO tạo 13:22 UTC, backend/chatter hiện 20:22 → portal phải hiện 20:22.
        tz = self._tz_vn()
        order = self._make_order()
        order.flush_recordset()
        self.env.cr.execute(
            "UPDATE sale_order SET create_date = %s WHERE id = %s",
            (datetime(2026, 7, 30, 13, 22, 0), order.id),
        )
        order.invalidate_recordset(['create_date'])
        row = _history_row_vals(order, {}, {}, tz)
        self.assertEqual(row['create_date'].strftime('%d/%m/%Y %H:%M'), '30/07/2026 20:22')

    def test_display_none_stays_none(self):
        self.assertIsNone(to_local_dt(None, self._tz_vn()))

    def test_invalid_user_tz_falls_back(self):
        """tz rác/rỗng → giờ VN mặc định, KHÔNG raise.

        ORM chặn giá trị ngoài selection nên dữ liệu hỏng chỉ vào được bằng SQL
        (import/migration cũ) — test đi đúng đường đó. 'Asia/Saigon' là alias hợp lệ
        của pytz, vẫn phải ra 20:22.
        """
        for bad in ('Asia/Saigon', 'Khong/Ton/Tai', None):
            self.env.cr.execute(
                "UPDATE res_partner SET tz = %s WHERE id = %s",
                (bad, self.env.user.partner_id.id),
            )
            self.env.user.invalidate_recordset(['tz'])
            tz = portal_tz(self.env)
            local = to_local_dt(datetime(2026, 7, 30, 13, 22, 0), tz)
            self.assertEqual(local.strftime('%H:%M'), '20:22',
                             'tz=%r phải rơi về %s, không nổ trang' % (bad, DEFAULT_PORTAL_TZ))

    def test_day_range_converted_to_utc(self):
        tz = self._tz_vn()
        utc_from, utc_to = local_day_range_utc(date(2026, 7, 30), date(2026, 7, 30), tz)
        # 00:00 giờ VN ngày 30 = 17:00 UTC ngày 29.
        self.assertEqual(utc_from, datetime(2026, 7, 29, 17, 0, 0))
        self.assertEqual(utc_to.strftime('%Y-%m-%d %H:%M'), '2026-07-30 16:59')

    def test_day_range_missing_bound(self):
        tz = self._tz_vn()
        utc_from, utc_to = local_day_range_utc(date(2026, 7, 30), None, tz)
        self.assertTrue(utc_from)
        self.assertIsNone(utc_to)

    def test_early_morning_order_inside_today_filter(self):
        """Đơn tạo 06:30 sáng giờ VN (= 23:30 UTC hôm trước) phải nằm trong lọc "ngày đó"."""
        tz = self._tz_vn()
        order = self._make_order()
        order.flush_recordset()
        self.env.cr.execute(
            "UPDATE sale_order SET create_date = %s WHERE id = %s",
            (datetime(2026, 7, 29, 23, 30, 0), order.id),
        )
        order.invalidate_recordset(['create_date'])
        utc_from, utc_to = local_day_range_utc(date(2026, 7, 30), date(2026, 7, 30), tz)
        found = self.env['sale.order'].search([
            ('id', '=', order.id),
            ('create_date', '>=', utc_from), ('create_date', '<=', utc_to),
        ])
        self.assertEqual(found, order, 'lọc theo ngày địa phương phải bắt được đơn 06:30 sáng')
        # Và cách CŨ (so ngày local thẳng với cột UTC) thì bỏ sót — đây chính là bug.
        old_way = self.env['sale.order'].search([
            ('id', '=', order.id),
            ('create_date', '>=', datetime(2026, 7, 30, 0, 0, 0)),
        ])
        self.assertFalse(old_way)


@tagged('post_install', '-at_install', 'wujia_history')
class TestHistoryStatus(HistoryCommon):
    """WJ-PH-003 — phương án (a): trạng thái chuyến giao đè trạng thái đơn."""

    def _batch_for(self, order, status):
        """Gán picking của đơn vào 1 batch có delivery_batch_status cho trước."""
        batch = self.env['stock.picking.batch'].create({'name': 'BATCH-%s' % status})
        pickings = order.picking_ids.filtered(lambda p: p.state != 'cancel')
        self.assertTrue(pickings, 'đơn đã xác nhận phải sinh picking')
        pickings.batch_id = batch
        batch.delivery_batch_status = status
        order.invalidate_recordset(['batch_id'])
        return batch

    def test_label_draft_and_sent(self):
        self.assertEqual(_order_status(self._make_order('draft')), ('Chờ xác nhận', 'pending'))
        self.assertEqual(_order_status(self._make_order('sent')), ('Đã gửi', 'sent'))

    def test_label_confirmed_without_batch(self):
        self.assertEqual(_order_status(self._make_order('sale')), ('Đã xác nhận', 'confirmed'))

    def test_label_delivering_overrides(self):
        order = self._make_order('sale')
        self._batch_for(order, 'delivering')
        self.assertEqual(_order_status(order), ('Đang giao', 'transit'))

    def test_label_done_overrides(self):
        order = self._make_order('sale')
        self._batch_for(order, 'done')
        self.assertEqual(_order_status(order), ('Hoàn tất', 'done'))

    def test_label_neutral_batch_keeps_order_state(self):
        for status in ('draft', 'assigned', 'loading', 'cancelled'):
            order = self._make_order('sale')
            self._batch_for(order, status)
            self.assertEqual(_order_status(order), ('Đã xác nhận', 'confirmed'),
                             'chuyến %s không được đổi nhãn đơn' % status)

    # ---------------- domain lọc phải khớp ĐÚNG nhãn hiển thị ----------------
    def _search(self, key):
        return self.env['sale.order'].search(
            [('franchise_id', '=', self.franchise.id)] + _status_domain(key))

    def test_domain_sale_keeps_order_without_batch(self):
        """Bẫy NULL: `not in` trên đường dẫn m2o sẽ loại luôn đơn chưa có chuyến."""
        plain = self._make_order('sale')
        delivering = self._make_order('sale')
        self._batch_for(delivering, 'delivering')
        result = self._search('sale')
        self.assertIn(plain, result, 'đơn chưa có chuyến vẫn là "Đã xác nhận"')
        self.assertNotIn(delivering, result, 'đơn đang giao không được nằm trong "Đã xác nhận"')

    def test_domain_delivering_and_done(self):
        delivering = self._make_order('sale')
        self._batch_for(delivering, 'delivering')
        done = self._make_order('sale')
        self._batch_for(done, 'done')
        self.assertEqual(self._search('delivering'), delivering)
        self.assertEqual(self._search('done'), done)

    def test_domain_matches_displayed_label(self):
        """Mỗi đơn phải xuất hiện ở đúng 1 nhóm lọc — nhóm ứng với nhãn đang hiển thị."""
        orders = [self._make_order('draft'), self._make_order('sent'), self._make_order('sale')]
        for status in ('delivering', 'done', 'cancelled'):
            o = self._make_order('sale')
            self._batch_for(o, status)
            orders.append(o)
        keys = ('draft', 'sent', 'sale', 'delivering', 'done')
        buckets = {k: self._search(k) for k in keys}
        for order in orders:
            label = _order_status(order)[0]
            hits = [k for k in keys if order in buckets[k]]
            self.assertEqual(len(hits), 1,
                             'đơn %s (%s) khớp %s nhóm lọc' % (order.name, label, len(hits)))


@tagged('post_install', '-at_install', 'wujia_history')
class TestHistoryPageSize(HistoryCommon):
    """WJ-PH-008 — mặc định 10 dòng/trang (source PC v1.5) + chặn giá trị lạ."""

    def test_default_is_ten(self):
        self.assertEqual(PAGE_SIZE, 10)
        self.assertEqual(_parse_page_size(None), 10)
        self.assertEqual(_parse_page_size(''), 10)

    def test_selector_options_are_the_whitelist(self):
        # Template đọc chính hằng này → select và validate không bao giờ lệch nhau.
        self.assertEqual(PAGE_SIZE_OPTIONS, (10, 20, 50))
        self.assertIn(PAGE_SIZE, PAGE_SIZE_OPTIONS)

    def test_valid_values_kept(self):
        for value in PAGE_SIZE_OPTIONS:
            self.assertEqual(_parse_page_size(str(value)), value)

    def test_invalid_values_fall_back(self):
        for bad in ('abc', '7', '0', '-5', '9999', 3.5, [], None):
            self.assertEqual(_parse_page_size(bad), PAGE_SIZE,
                             'page_size=%r phải rơi về mặc định' % (bad,))

    def test_pages_do_not_overlap_or_drop(self):
        """13 đơn / 10 dòng: trang 1 + trang 2 = đủ 13 đơn, không trùng."""
        orders = self.env['sale.order'].browse()
        for _ in range(13):
            orders |= self._make_order()
        domain = [('franchise_id', '=', self.franchise.id), ('state', '!=', 'cancel')]
        SO = self.env['sale.order']
        total = SO.search_count(domain)
        self.assertEqual(total, 13)
        page1 = SO.search(domain, limit=PAGE_SIZE, offset=0, order='create_date desc')
        page2 = SO.search(domain, limit=PAGE_SIZE, offset=PAGE_SIZE, order='create_date desc')
        self.assertEqual(len(page1), 10)
        self.assertEqual(len(page2), 3)
        self.assertFalse(page1 & page2, 'đơn không được lặp giữa 2 trang')
        self.assertEqual(page1 | page2, orders)
