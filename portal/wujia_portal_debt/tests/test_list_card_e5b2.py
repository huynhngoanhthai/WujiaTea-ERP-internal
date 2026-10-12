"""E5b2 — hành vi RIÊNG của màn Công nợ sau khi ruột card về `wj_list_card`.

Chốt của chủ dự án đầu phiên: số tiền tách làm NHÃN + GIÁ TRỊ đậm, nhãn đổi theo
trạng thái hoá đơn ("Còn lại" / "Đã trả" / "Được trừ"). Đây là chỗ duy nhất ghim
việc đó; sổ đăng ký chung chỉ biết "đã gọi component".
"""
import re

from lxml import etree

from odoo.tests import TransactionCase, tagged

from odoo.addons.wujia_portal_base.tests.css_probe import _css, _mod_css, _rule, _view


@tagged('post_install', '-at_install', 'wujia_list_card_e5')
class TestDebtListCardE5b2(TransactionCase):

    def setUp(self):
        super().setUp()
        self.root = _view('wujia_portal_debt', 'portal_debt.xml')

    def _item(self, ho):
        got = [el for el in self.root.iter()
               if re.match(r'%s(?![-\w])' % re.escape(ho),
                           el.get('class') or el.get('t-attf-class') or '')]
        self.assertEqual(len(got), 1, '%s: phải đúng 1 item mẫu' % ho)
        return got[0]

    def _hang_tien(self, item):
        for row in item.xpath('.//t[@t-call="wujia_portal_layout.wj_list_card_row"]'):
            if row.xpath('./t[@t-set="lcr_strong"]'):
                return row
        self.fail('không tìm thấy hàng tiền (lcr_strong)')

    def test_nhan_tien_doi_theo_trang_thai(self):
        """Ba nhãn phải cùng nằm trên MỘT biểu thức — tách thành ba hàng là ba
        chỗ phải sửa khi BA đổi chữ."""
        # J-V5: nhãn là text node trong MỘT <t t-set> (dịch được qua .po), không còn
        # biểu thức chuỗi tiếng Việt — vẫn một chỗ duy nhất.
        nhan = self._hang_tien(self._item('wj-debt-inv')).xpath('./t[@t-set="lcr_label"]')
        self.assertEqual(len(nhan), 1, 'hàng tiền thiếu nhãn')
        body = etree.tostring(nhan[0], encoding='unicode')
        for chu in ('Remaining', 'Amount paid', 'Deducted'):
            self.assertIn(chu, body, 'mất nhãn %s' % chu)
        self.assertIn("'paid'", body)
        self.assertIn("'credit'", body)

    def test_giay_bao_co_ra_so_am(self):
        """LC-09 cấm mất dữ liệu: giấy báo có TRỪ vào nợ ⇒ giá trị mang dấu âm,
        không chỉ đổi nhãn rồi để số dương như hoá đơn."""
        gia_tri = self._hang_tien(self._item('wj-debt-inv')).xpath(
            './t[@t-set="lcr_value"]/@t-value')[0]
        self.assertIn("vnd(-inv['amount'])", gia_tri.replace(' ', ''))

    def test_hai_hang_tien_deu_dung_khuon_inline(self):
        """Tiền là trường NGẮN ⇒ đứng cột phải cùng hàng meta (LC-05), không
        chiếm cả hàng."""
        for ho in ('wj-debt-inv', 'wj-debt-pay'):
            row = self._hang_tien(self._item(ho))
            self.assertIn("'wj-lc__row--inline'",
                          row.xpath('./t[@t-set="lcr_class"]/@t-value'),
                          '%s: hàng tiền không dùng khuôn inline' % ho)
            self.assertFalse(row.xpath('./t[@t-set="lcr_full"]'),
                             '%s: tiền chiếm cả hàng' % ho)

    def test_chu_so_cung_be_rong(self):
        """Tiền xếp cột dọc: không tabular-nums thì mỗi card lệch vài px. Số nằm
        ở `.wj-lc__value` của khung nên ghim luôn contract đó."""
        than = _rule(_css('_components.css'), '.wj-lc__value')
        self.assertIsNotNone(than, 'mất rule .wj-lc__value')
        self.assertRegex(than, r'font-variant-numeric:\s*tabular-nums')

    def test_mau_trang_thai_van_bam_dung_so_tien(self):
        """Đỏ (quá hạn) / xanh (đã trả) trước đây tô `.wj-debt-inv__amount`; sau
        migrate phải chuyển sang giá trị đậm, nếu không màu tô trượt ra cả card."""
        css = _css('_components.css')
        self.assertIsNotNone(_rule(css, '.wj-lc__value--strong'))
        mau = _mod_css('wujia_portal_debt', 'portal_debt.css')
        for trang_thai in ('overdue', 'paid'):
            self.assertRegex(
                mau, r'\.wj-debt-inv--%s \.wj-lc__value--strong\s*\{' % trang_thai,
                'mất màu trạng thái %s trên số tiền' % trang_thai)
