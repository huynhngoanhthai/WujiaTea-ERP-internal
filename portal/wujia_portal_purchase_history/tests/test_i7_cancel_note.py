"""I7 — #62 WJ-PH-003 (Lịch sử gồm đơn Đã hủy) + #163 WJ-PH-009 (ghi chú khi đặt hàng trên PC).

Chạy: `--test-tags wujia_ph_i7`.

  1. `TestI7CancelledOrders` — BA 01/10: danh sách / lọc / phân trang / chi tiết có đơn huỷ của cửa hàng
     đang chọn; đơn huỷ cửa hàng khác vẫn không đọc được; 5 nhãn cũ giữ nguyên; Home vẫn không hiện đơn huỷ.
  2. `TestI7OrderingNote` — PC và mobile cùng nội dung `portal_note`, tách khỏi "Ghi chú giao hàng";
     rỗng ⇒ cùng một câu "Không có ghi chú" ở mọi khối ghi chú.
"""
import re
from datetime import date, datetime, timedelta

from lxml import html

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_purchase_history.controllers.portal import WujiaPortalHistory
from odoo.addons.wujia_portal_purchase_history.tests.test_jv8_i18n import ERR_VI, load_vi

PC = "//div[contains(concat(' ', @class, ' '), ' d-lg-block ')]"
MOBILE = "//div[contains(concat(' ', @class, ' '), ' wujia-mhist-detail ')]"
NOTE = "//*[contains(concat(' ', @class, ' '), ' wj-ph-order-note ')]//p[contains(concat(' ', @class, ' '), ' wj-ph-note ')]"


def _text(el):
    return re.sub(r'\s+', ' ', ''.join(el.itertext())).strip()


class I7Common(HttpCase):
    LOGIN = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = load_vi(cls.env)
        env = cls.env
        cls.partner = env['res.partner'].create({'name': '%s partner' % cls.LOGIN})
        cls.franchise = env['wujia.franchise.management'].create({
            'code': cls.LOGIN.upper()[:6], 'name': '%s store' % cls.LOGIN,
            'partner_id': cls.partner.id,
            'franchise_end_date': date.today() + timedelta(days=365),
        })
        other_partner = env['res.partner'].create({'name': '%s other partner' % cls.LOGIN})
        cls.other = env['wujia.franchise.management'].create({
            'code': cls.LOGIN.upper()[:5] + 'X', 'name': '%s other store' % cls.LOGIN,
            'partner_id': other_partner.id,
            'franchise_end_date': date.today() + timedelta(days=365),
        })
        cls.user = env['res.users'].create({
            'name': cls.LOGIN, 'login': cls.LOGIN, 'password': cls.LOGIN, 'lang': 'vi_VN',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])],
        })
        env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.franchise.id, 'role': 'owner',
        })
        cls.product = env['product.product'].create({
            'name': 'Trà test I7', 'is_storable': True, 'list_price': 10000.0,
        })

    def _make_order(self, state='draft', franchise=None, **vals):
        franchise = franchise or self.franchise
        order = self.env['sale.order'].create(dict({
            'partner_id': franchise.partner_id.id,
            'franchise_id': franchise.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 1.0})],
        }, **vals))
        if state in ('sale', 'cancel_after_confirm'):
            order.action_confirm()
        elif state == 'sent':
            order.state = 'sent'
        if state in ('cancel', 'cancel_after_confirm'):
            order._action_cancel()
        return order

    def _get(self, url):
        self.authenticate(self.LOGIN, self.LOGIN)
        res = self.url_open(url, timeout=30)
        self.assertEqual(res.status_code, 200, url)
        return html.fromstring(res.text)

    @staticmethod
    def _list_ids(root):
        ids = set()
        for href in root.xpath("//a/@href"):
            m = re.fullmatch(r'/portal/purchase-history/(\d+)', href)
            if m:
                ids.add(int(m.group(1)))
        return ids


@tagged('post_install', '-at_install', 'wujia_history', 'wujia_ph_i7')
class TestI7CancelledOrders(I7Common):
    LOGIN = 'i7_cancel'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        self = cls
        cls.draft = I7Common._make_order(self, 'draft')
        cls.sent = I7Common._make_order(self, 'sent')
        cls.sale = I7Common._make_order(self, 'sale')
        cls.cancelled = I7Common._make_order(self, 'cancel')
        cls.cancelled_confirmed = I7Common._make_order(self, 'cancel_after_confirm')
        cls.other_cancelled = I7Common._make_order(self, 'cancel', franchise=cls.other)
        cls.mine = cls.draft | cls.sent | cls.sale | cls.cancelled | cls.cancelled_confirmed

    def test_list_all_includes_cancelled_of_current_store_only(self):
        ids = self._list_ids(self._get('/portal/purchase-history?page_size=50'))
        self.assertEqual(ids, set(self.mine.ids), 'Tất cả = mọi đơn của cửa hàng đang chọn, kể cả đơn huỷ')
        self.assertNotIn(self.other_cancelled.id, ids)

    def test_filter_cancelled(self):
        root = self._get('/portal/purchase-history?state=cancel&page_size=50')
        self.assertEqual(self._list_ids(root), {self.cancelled.id, self.cancelled_confirmed.id})
        badges = root.xpath("//span[contains(@class,'wj-status-badge--danger')]")
        self.assertTrue(badges and all(_text(b) == 'Đã hủy' for b in badges), [_text(b) for b in badges])
        # Mobile không có ô chọn trạng thái ⇒ chip "Đã hủy" phải có và đang bật.
        chip = root.xpath("//*[@id='wj-hist-mchips']//a[@href='/portal/purchase-history?state=cancel']")
        self.assertEqual(len(chip), 1)
        self.assertEqual(_text(chip[0]), 'Đã hủy')
        self.assertIn('is-active', chip[0].get('class'))

    def test_old_filters_unchanged(self):
        for state, expected in (('draft', self.draft), ('sent', self.sent), ('sale', self.sale)):
            with self.subTest(state=state):
                ids = self._list_ids(self._get('/portal/purchase-history?state=%s&page_size=50' % state))
                self.assertEqual(ids, set(expected.ids))

    def test_filter_option_cancel_is_last(self):
        opts = WujiaPortalHistory()._state_options(self.env['sale.order'])
        self.assertEqual([k for k, _l in opts], ['draft', 'sent', 'sale', 'delivering', 'done', 'cancel'])
        root = self._get('/portal/purchase-history')
        opt = root.xpath("//option[@value='cancel']")
        self.assertTrue(opt and _text(opt[0]) == 'Đã hủy')

    def test_pagination_with_cancelled(self):
        extra = self.env['sale.order']
        for i in range(8):
            extra |= self._make_order('cancel' if i % 3 == 0 else 'draft')
        expected = set((self.mine | extra).ids)
        self.assertEqual(len(expected), 13)
        p1 = self._list_ids(self._get('/portal/purchase-history?page_size=10&page=1'))
        p2 = self._list_ids(self._get('/portal/purchase-history?page_size=10&page=2'))
        self.assertEqual((len(p1), len(p2)), (10, 3))
        self.assertFalse(p1 & p2)
        self.assertEqual(p1 | p2, expected)

    def test_detail_cancelled_same_store(self):
        for order in (self.cancelled, self.cancelled_confirmed):
            with self.subTest(order=order.name):
                root = self._get('/portal/purchase-history/%d' % order.id)
                badges = root.xpath("//span[contains(@class,'wj-status-badge--danger')]")
                self.assertEqual({_text(b) for b in badges}, {'Đã hủy'})
                self.assertFalse(root.xpath("//*[contains(@class,'wj-pc-empty')]"))

    def test_detail_cancelled_other_store_blocked(self):
        root = self._get('/portal/purchase-history/%d' % self.other_cancelled.id)
        self.assertIn(ERR_VI['ERR_NOT_FOUND'], _text(root))
        self.assertNotIn(self.other_cancelled.name, _text(root))
        res = self.url_open('/portal/purchase-history/%d.pdf' % self.other_cancelled.id, timeout=30)
        self.assertEqual(res.status_code, 404)

    def test_home_still_hides_cancelled(self):
        root = self._get('/portal')
        hrefs = set(root.xpath("//a/@href"))
        for order in (self.cancelled, self.cancelled_confirmed):
            self.assertNotIn('/portal/purchase-history/%d' % order.id, hrefs)


@tagged('post_install', '-at_install', 'wujia_history', 'wujia_ph_i7')
class TestI7OrderingNote(I7Common):
    LOGIN = 'i7_note'
    NOTE_TEXT = 'Giao trước 9h\nGọi chị Lan khi tới\nQA-RETEST-' + 'X' * 120

    def _notes(self, order):
        root = self._get('/portal/purchase-history/%d' % order.id)
        return root.xpath(PC + NOTE), root.xpath(MOBILE + NOTE), root

    def test_pc_and_mobile_show_same_note(self):
        order = self._make_order('draft', portal_note=self.NOTE_TEXT)
        pc, mobile, root = self._notes(order)
        self.assertEqual((len(pc), len(mobile)), (1, 1), 'mỗi kênh đúng một khối Ghi chú khi đặt hàng')
        raw = ''.join(pc[0].itertext())
        self.assertEqual(raw.strip(), self.NOTE_TEXT, 'giữ nguyên xuống dòng + chuỗi dài')
        self.assertEqual(''.join(mobile[0].itertext()).strip(), self.NOTE_TEXT)
        self.assertNotIn('wj-ph-note--empty', pc[0].get('class'))
        for block in (PC, MOBILE):
            heads = [_text(h) for h in root.xpath(block + "//*[contains(concat(' ', @class, ' '), ' wj-ph-order-note ')]"
                                                         "//*[self::h2 or self::h3 or self::h4]")]
            self.assertIn('Ghi chú khi đặt hàng', heads)

    def test_empty_note_uses_one_empty_state_not_delivery_note(self):
        order = self._make_order('sale')
        batch = self.env['stock.picking.batch'].create({'name': 'I7-NOTE', 'delivery_note': 'GIAO-CỔNG-SAU'})
        order.picking_ids.filtered(lambda p: p.state != 'cancel').batch_id = batch
        pc, mobile, root = self._notes(order)
        for el in pc + mobile:
            self.assertEqual(_text(el), 'Không có ghi chú')
            self.assertIn('wj-ph-note--empty', el.get('class'))
        # Ghi chú giao hàng vẫn ở panel chuyến giao, không lẫn sang khối ghi chú đặt hàng.
        self.assertIn('GIAO-CỔNG-SAU', _text(root))

    def test_empty_delivery_note_same_text_on_both_channels(self):
        order = self._make_order('sale')
        batch = self.env['stock.picking.batch'].create({'name': 'I7-NODN'})
        order.picking_ids.filtered(lambda p: p.state != 'cancel').batch_id = batch
        root = self._get('/portal/purchase-history/%d' % order.id)
        for block, label_cls, value_cls in ((PC, 'wj-pc-kv__label', 'wj-pc-kv__value'),
                                            (MOBILE, 'wujia-mhist-kv-label', 'wujia-mhist-kv-value')):
            labels = root.xpath(block + "//span[contains(@class,'%s')][normalize-space()='Ghi chú giao hàng']" % label_cls)
            self.assertEqual(len(labels), 1, block)
            value = labels[0].getnext()
            self.assertIn(value_cls, value.get('class'))
            self.assertEqual(_text(value), 'Không có ghi chú')
