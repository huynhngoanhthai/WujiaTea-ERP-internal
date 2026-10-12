"""WJ-HOME-009 (150) + WJ-HOME-010 (151) — đơn gần đây trên Home phải nói GIỐNG Lịch sử.

Chạy: `--test-tags wujia_home_order_status`.

  1. `TestHomeOrderStatus` — 151: cùng một SO thì nhãn + màu badge trên Home PC, Home mobile,
     dòng danh sách và trang chi tiết Lịch sử trùng nhau (draft/sent/sale/đang giao/hoàn tất).
     Home từng có bảng riêng (draft → "Nháp") trong khi Lịch sử nói "Chờ xác nhận".
  2. `TestHomeOrderTime`  — 150: giờ đặt hàng trên Home PC = mobile = giờ user (tz rỗng →
     giờ mặc định dự án). Block PC cũ (trước G3b) in thẳng date_order UTC nên lệch 7 tiếng.

Nằm ở purchase_history vì phải so với `_history_row_vals` — portal_base không import lên được.
"""
import re
from datetime import date, datetime, timedelta

from lxml import html

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_base.controllers.utils import portal_order_badge, portal_tz
from odoo.addons.wujia_portal_purchase_history.controllers.portal import (
    BATCH_STATUS_LABELS, _history_detail_vals, _history_row_vals,
)

PC = "//div[contains(concat(' ', @class, ' '), ' wujia-home-pc ')]"
MOBILE = "//div[contains(concat(' ', @class, ' '), ' wujia-mhome ')]"
CHANNELS = (('pc', PC), ('mobile', MOBILE))


def _text(el):
    return re.sub(r'\s+', ' ', ''.join(el.itertext())).strip()


class HomeOrderCommon(HttpCase):
    LOGIN = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # J-V2: nhãn trạng thái của portal_base là `_lt` (câu gốc EN) ⇒ chạy ở vi_VN để giữ assert tiếng Việt.
        cls.env['res.lang']._activate_lang('vi_VN')
        cls.env = cls.env(context=dict(cls.env.context, lang='vi_VN'))
        env = cls.env
        cls.partner = env['res.partner'].create({'name': '%s partner' % cls.LOGIN})
        cls.franchise = env['wujia.franchise.management'].create({
            'code': cls.LOGIN.upper()[:6], 'name': '%s store' % cls.LOGIN,
            'partner_id': cls.partner.id,
            'franchise_end_date': date.today() + timedelta(days=365),
        })
        cls.user = env['res.users'].create({
            'name': cls.LOGIN, 'login': cls.LOGIN, 'password': cls.LOGIN,
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])],
        })
        env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.franchise.id, 'role': 'owner',
        })
        cls.product = env['product.product'].create({
            'name': 'Trà sữa test Home', 'is_storable': True, 'list_price': 10000.0,
        })

    def _make_order(self, state='draft', date_order=None):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'franchise_id': self.franchise.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 2.0})],
        })
        if state == 'sale':
            order.action_confirm()
        elif state == 'sent':
            order.state = 'sent'
        # action_confirm ghi đè date_order ⇒ đặt SAU cùng. Mặc định: mới nhất để lên đầu Home.
        order.date_order = date_order or datetime.now() + timedelta(days=1)
        return order

    def _batch_for(self, order, status):
        batch = self.env['stock.picking.batch'].create({'name': 'HOME-%s' % status})
        pickings = order.picking_ids.filtered(lambda p: p.state != 'cancel')
        self.assertTrue(pickings, 'đơn đã xác nhận phải sinh picking')
        pickings.batch_id = batch
        batch.delivery_batch_status = status
        order.invalidate_recordset(['batch_id'])

    def _home_rows(self, order):
        """{kênh: <a> dòng của đơn} trên Home — mỗi kênh đúng 1 dòng."""
        self.env.flush_all()
        self.authenticate(self.LOGIN, self.LOGIN)
        res = self.url_open('/portal', timeout=30)
        self.assertEqual(res.status_code, 200)
        doc = html.fromstring(res.text)
        rows = {}
        for name, xp in CHANNELS:
            box = doc.xpath(xp)
            self.assertEqual(len(box), 1, 'thiếu khối Home %s' % name)
            hit = box[0].xpath(".//a[@href='/portal/purchase-history/%s']" % order.id)
            self.assertEqual(len(hit), 1, 'Home %s phải có đúng 1 dòng cho %s' % (name, order.name))
            rows[name] = hit[0]
        return rows


@tagged('post_install', '-at_install', 'wujia_home_order_status')
class TestHomeOrderStatus(HomeOrderCommon):
    LOGIN = 'home_st151'

    def _assert_same_everywhere(self, order, expected_label, expected_variant):
        tz = portal_tz(self.env)
        row = _history_row_vals(order, {}, BATCH_STATUS_LABELS, tz)
        detail = _history_detail_vals(order, BATCH_STATUS_LABELS, tz)['header']
        badge_cls = 'wj-status-badge--%s' % expected_variant
        self.assertEqual((row['state_label'], row['badge']), (expected_label, badge_cls))
        self.assertEqual((detail['state_label'], detail['badge']), (expected_label, badge_cls))
        self.assertEqual(portal_order_badge(order), (expected_label, badge_cls))
        for name, a in self._home_rows(order).items():
            with self.subTest(channel=name, order=order.name):
                badge = a.xpath(".//span[contains(concat(' ', @class, ' '), ' wj-status-badge ')]")
                self.assertEqual(len(badge), 1)
                self.assertEqual(_text(badge[0]), expected_label)
                self.assertIn(badge_cls, badge[0].get('class').split())

    def test_draft_is_waiting_for_confirmation_not_draft(self):
        """Lỗi gốc BA (S00075): Home 'Nháp', Lịch sử 'Chờ xác nhận'."""
        self._assert_same_everywhere(self._make_order('draft'), 'Chờ xác nhận', 'pending')

    def test_sent(self):
        self._assert_same_everywhere(self._make_order('sent'), 'Đã gửi', 'pending')

    def test_confirmed_without_batch(self):
        self._assert_same_everywhere(self._make_order('sale'), 'Đã xác nhận', 'info')

    def test_delivering_batch_overrides_on_home_too(self):
        order = self._make_order('sale')
        self._batch_for(order, 'delivering')
        self._assert_same_everywhere(order, 'Đang giao', 'processing')

    def test_done_batch_overrides_on_home_too(self):
        order = self._make_order('sale')
        self._batch_for(order, 'done')
        self._assert_same_everywhere(order, 'Hoàn tất', 'success')

    def test_home_hides_cancelled_like_history(self):
        """cancel: Lịch sử loại khỏi danh sách ⇒ Home cũng không hiện (không có nhãn để so)."""
        keep = self._make_order('draft', date_order=datetime.now())
        cancelled = self._make_order('draft')
        cancelled.action_cancel()
        self.env.flush_all()
        self.authenticate(self.LOGIN, self.LOGIN)
        doc = html.fromstring(self.url_open('/portal', timeout=30).text)
        for name, xp in CHANNELS:
            box = doc.xpath(xp)[0]
            self.assertFalse(box.xpath(".//a[@href='/portal/purchase-history/%s']" % cancelled.id), name)
            self.assertTrue(box.xpath(".//a[@href='/portal/purchase-history/%s']" % keep.id), name)


@tagged('post_install', '-at_install', 'wujia_home_order_status')
class TestHomeOrderTime(HomeOrderCommon):
    LOGIN = 'home_tz150'
    UTC_1557 = datetime(2026, 9, 29, 15, 57, 0)     # S00075 BA đo: backend 22:57 giờ VN

    def _home_time(self, tz):
        self.user.tz = tz
        order = self._make_order('draft', date_order=self.UTC_1557)
        subs = {}
        for name, a in self._home_rows(order).items():
            first_sub = a.xpath(".//span[contains(concat(' ', @class, ' '), ' wujia-mdash-row-sub ')]")[0]
            subs[name] = _text(first_sub)
        return subs

    def test_vietnam_user_sees_2257_on_pc_and_mobile(self):
        self.assertEqual(self._home_time('Asia/Ho_Chi_Minh'),
                         {'pc': '22:57 29/09/2026', 'mobile': '22:57 29/09/2026'})

    def test_empty_tz_falls_back_to_project_default(self):
        self.assertEqual(self._home_time(False),
                         {'pc': '22:57 29/09/2026', 'mobile': '22:57 29/09/2026'})

    def test_other_tz_follows_user(self):
        self.assertEqual(self._home_time('Asia/Tokyo'),
                         {'pc': '00:57 30/09/2026', 'mobile': '00:57 30/09/2026'})
