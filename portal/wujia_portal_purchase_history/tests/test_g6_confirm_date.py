"""G6 — WJ-ORD-029: "Ngày xác nhận" chỉ hiện khi đơn ĐÃ xác nhận.

Odoo đặt `date_order` = lúc tạo cho báo giá, nên draft/sent mà in `date_order` dưới nhãn "Ngày xác nhận" là
sai nghĩa (BA thấy ở S00075). Chủ dự án chốt 30/09: cột PC ghi "—", chi tiết ẩn hẳn dòng, nhãn "Ngày tạo" ở
chi tiết → "Ngày đặt hàng" (vẫn `create_date`). Không đổi dữ liệu `sale.order`.
"""
from datetime import datetime

import pytz
from lxml import html

from odoo.tests import tagged

from odoo.addons.wujia_portal_purchase_history.controllers.portal import (
    BATCH_STATUS_LABELS, _history_detail_vals, _history_row_vals,
)

from .test_home_order_status import HomeOrderCommon

CONFIRMED_UTC = datetime(2026, 9, 29, 18, 30)   # VN 30/09 01:30 — qua ngày, bắt lỗi quên đổi tz
CREATED_UTC = datetime(2026, 9, 29, 3, 5)       # VN 29/09 10:05


def _t(el):
    return ' '.join(' '.join(el.itertext()).split())


@tagged('post_install', '-at_install', 'wujia_g6')
class TestG6ConfirmDate(HomeOrderCommon):
    LOGIN = 'g6_confirm'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user.tz = 'Asia/Ho_Chi_Minh'

    def order(self, state):
        so = self._make_order(state, date_order=CONFIRMED_UTC)
        so.flush_recordset()
        self.env.cr.execute("UPDATE sale_order SET create_date=%s WHERE id=%s", (CREATED_UTC, so.id))
        so.invalidate_recordset(['create_date'])
        return so

    def vals(self, so, tz='Asia/Ho_Chi_Minh'):
        tz = pytz.timezone(tz)
        return (_history_row_vals(so, {}, BATCH_STATUS_LABELS, tz),
                _history_detail_vals(so, BATCH_STATUS_LABELS, tz)['header'])

    def page(self, url):
        self.env.flush_all()
        self.authenticate(self.LOGIN, self.LOGIN)
        res = self.url_open(url, timeout=30)
        self.assertEqual(res.status_code, 200, url)
        return html.fromstring(res.text)

    # ------------------------------------------------------------ dataset
    def test_draft_and_sent_have_no_confirm_date(self):
        for state in ('draft', 'sent'):
            with self.subTest(state=state):
                so = self.order(state)
                for vals in self.vals(so):
                    self.assertIsNone(vals['confirm_date'])
                    # Ngày đặt hàng = create_date, giờ VN
                    self.assertEqual(vals['create_date'].strftime('%d/%m/%Y %H:%M'), '29/09/2026 10:05')
                self.assertEqual(so.state, state, 'không được đổi dữ liệu đơn')

    def test_sale_confirm_date_in_user_tz(self):
        so = self.order('sale')
        for tz, expected in (('Asia/Ho_Chi_Minh', '30/09/2026 01:30'),
                             ('Asia/Tokyo', '30/09/2026 03:30'),
                             ('America/New_York', '29/09/2026 14:30')):
            with self.subTest(tz=tz):
                for vals in self.vals(so, tz):
                    self.assertEqual(vals['confirm_date'].strftime('%d/%m/%Y %H:%M'), expected)

    def test_delivering_order_keeps_confirm_date(self):
        """"Đang giao"/"Hoàn tất" suy từ chuyến giao — đơn vẫn `sale` ⇒ vẫn có ngày xác nhận."""
        so = self.order('sale')
        self._batch_for(so, 'delivering')
        row, header = self.vals(so)
        self.assertNotEqual(row['state_label'], 'Đã xác nhận')
        self.assertEqual(row['confirm_date'].strftime('%d/%m/%Y %H:%M'), '30/09/2026 01:30')
        self.assertEqual(header['confirm_date'], row['confirm_date'])

    def test_date_order_key_kept(self):
        """Key cũ giữ nguyên cho caller khác — chỉ template Lịch sử đổi sang `confirm_date`."""
        row, header = self.vals(self.order('draft'))
        self.assertEqual(row['date_order'].strftime('%d/%m/%Y %H:%M'), '30/09/2026 01:30')
        self.assertIn('date_order', header)

    # ------------------------------------------------------------ render
    def _pc_cells(self, doc, so):
        """{tiêu đề cột: ô} của dòng đơn trong bảng PC."""
        table = doc.xpath("//table[.//a[contains(@href, '/portal/purchase-history/%s')]]" % so.id)
        self.assertEqual(len(table), 1)
        heads = [_t(th) for th in table[0].xpath('.//thead//th')]
        row = table[0].xpath(".//tr[.//a[contains(@href, '/portal/purchase-history/%s')]]" % so.id)[0]
        return dict(zip(heads, [_t(td) for td in row.xpath('./td')]))

    def test_list_pc_column(self):
        draft, sale = self.order('draft'), self.order('sale')
        doc = self.page('/portal/purchase-history')
        self.assertEqual(self._pc_cells(doc, draft)['Ngày xác nhận'], '—')
        self.assertEqual(self._pc_cells(doc, sale)['Ngày xác nhận'], '30/09/2026')
        self.assertEqual(self._pc_cells(doc, draft)['Ngày tạo'], '29/09/2026 10:05')

    def _kv(self, doc):
        return {_t(kv.xpath('./*[contains(@class, "wj-pc-kv__label")]')[0]):
                _t(kv.xpath('./*[contains(@class, "wj-pc-kv__value")]')[0])
                for kv in doc.xpath("//div[contains(concat(' ', @class, ' '), ' wj-pc-kv ')]")}

    def test_detail_draft_hides_confirm_row(self):
        doc = self.page('/portal/purchase-history/%s' % self.order('draft').id)
        kv = self._kv(doc)
        self.assertNotIn('Ngày xác nhận', kv)
        self.assertNotIn('Ngày tạo', kv)
        self.assertEqual(kv['Ngày đặt hàng'], '29/09/2026 10:05')
        self.assertEqual(kv['Trạng thái'], 'Chờ xác nhận')
        self.assertNotIn('Ngày xác nhận', _t(doc))
        meta = doc.xpath("//p[contains(@class, 'wj-pc-order-head__meta')]")
        self.assertTrue(_t(meta[0]).startswith('Ngày đặt hàng 29/09/2026 10:05'))

    def test_detail_sale_shows_confirm_row(self):
        kv = self._kv(self.page('/portal/purchase-history/%s' % self.order('sale').id))
        self.assertEqual(kv['Ngày xác nhận'], '30/09/2026 01:30')
        self.assertEqual(kv['Ngày đặt hàng'], '29/09/2026 10:05')
