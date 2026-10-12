"""E5b2 — hành vi RIÊNG của màn Thi sau khi ruột card về `wj_list_card`.

Sổ đăng ký chung (`wujia_portal_base/tests/test_scan_e5_list_card.py`) chỉ canh
"đã gọi component / họ cũ đã biến mất". Ba thứ dưới đây là của riêng màn này và
migrate rất dễ làm gãy, nên theo luật F5b chúng ở lại module Thi:

  · hook JS của wizard (bước 1 chép meta sang thẻ "đã chọn", nút Chọn nhảy bước 2);
  · nút Chọn chỉ hiện với khoá CHƯA đóng và là control RIÊNG (LC-11);
  · ba trạng thái kết quả nhân sự vẫn ra badge compact.
"""
import os
import re

from odoo.tests import TransactionCase, tagged

from odoo.addons.wujia_exam.tests.common import load_vi
from odoo.addons.wujia_portal_base.tests.css_probe import CUSTOM, _view

JS = os.path.join(CUSTOM, 'wujia_portal_exam', 'static', 'src', 'js',
                  'portal_exam_wizard.js')


@tagged('post_install', '-at_install', 'wujia_list_card_e5')
class TestExamListCardE5b2(TransactionCase):

    def setUp(self):
        super().setUp()
        self.root = _view('wujia_portal_exam', 'portal_exam.xml')
        with open(JS, encoding='utf-8') as fh:
            self.js = fh.read()

    def _khoa(self):
        got = self.root.xpath('//div[contains(@t-attf-class, "wujia-mexam-course")]')
        self.assertEqual(len(got), 1, 'không còn item khoá thi ở bước 1')
        return got[0]

    def _nhan_su(self):
        got = self.root.xpath('//div[contains(@class, "wujia-mexam-rrow")]')
        self.assertEqual(len(got), 1, 'không còn item nhân sự ở phiếu đăng ký')
        return got[0]

    def test_hook_wizard_con_nguyen(self):
        """Ba data-attr điều khiển wizard phải ở lại CHÍNH item, không rơi vào
        một thẻ con nào đó khi dựng lại ruột."""
        item = self._khoa()
        self.assertIsNotNone(item.get('t-att-data-exam-closed'))
        self.assertIsNotNone(item.get('t-att-data-exam-course-id'))
        self.assertTrue(item.xpath('.//*[@data-exam-choose]'), 'mất nút chuyển bước')

    def test_js_neo_vao_lop_hanh_vi(self):
        """JS đọc meta để chép sang thẻ "đã chọn". Neo vào lớp trình bày cũ là
        lần sau đổi anatomy lại gãy im lặng ⇒ bắt buộc `js-exam-course-meta`."""
        self.assertIn('js-exam-course-meta', self.js)
        # Tên khoá: JS chép sang thẻ "đã chọn"; sau E5b2 nó ở đầu ListCard chứ
        # không còn ở wj_card_header ⇒ đọc sai là bước 2 hiện tiêu đề rỗng.
        self.assertIn("card.querySelector('.wj-lc__name')", self.js)
        self.assertIn(".js-exam-course-meta .wj-lc__value", self.js)
        row = self._khoa().xpath('.//t[@t-set="lcr_class"]/@t-value')
        self.assertIn("'js-exam-course-meta'", row, 'hàng meta mất lớp hành vi')
        for cu in ('wujia-mexam-course-meta', 'wujia-mexam-course-title',
                   'wujia-mexam-course-choose'):
            self.assertNotIn(cu, self.js, 'JS còn bám lớp trình bày đã gỡ: %s' % cu)

    def test_nut_chon_la_control_rieng_va_an_khi_khoa_dong(self):
        """LC-11: nút nằm ở slot `lc_actions`, không lồng trong thẻ mở chi tiết."""
        item = self._khoa()
        act = item.xpath('.//t[@t-set="lc_actions"]')
        self.assertEqual(len(act), 1, 'nút Chọn không ở slot lc_actions')
        nut = act[0].xpath('.//a[@data-exam-choose]')
        self.assertEqual(len(nut), 1)
        self.assertEqual(nut[0].get('t-if'), "not c['closed']",
                         'khoá đã đóng vẫn hiện nút Chọn')
        self.assertFalse(nut[0].xpath('ancestor::a'), 'interactive lồng interactive')

    def test_badge_ket_qua_du_ba_trang_thai(self):
        """Đạt / Không đạt / Chờ kết quả — cả ba đều là badge compact 12px."""
        state = self._nhan_su().xpath('.//t[@t-set="lc_state"]')[0]
        xml = re.sub(r'\s+', ' ', ''.join(state.itertext()) + ' '
                     + ' '.join(el.get('t-out') or el.get('t-attf-class') or ''
                                for el in state.iter()))
        # J-V3: nguồn là câu gốc tiếng Anh; user vi_VN vẫn thấy đủ ba nhãn cũ.
        for chu in ('Pass', 'Fail', 'Awaiting result'):
            self.assertIn(chu, xml, 'mất trạng thái %s' % chu)
        arch_vi = load_vi(self.env, ('wujia_portal_exam',)).ref(
            'wujia_portal_exam.portal_exam_registration_detail').arch
        for chu in ('Đạt', 'Không đạt', 'Chờ kết quả'):
            self.assertIn(chu, arch_vi, 'mất trạng thái %s' % chu)
        badges = state.xpath('.//span[contains(@class, "wj-status-badge")]'
                             ' | .//span[contains(@t-attf-class, "wj-status-badge")]')
        self.assertEqual(len(badges), 2, 'hai nhánh published/chờ kết quả')
        for b in badges:
            cls = b.get('class') or b.get('t-attf-class') or ''
            self.assertIn('wj-status-badge--compact', cls, 'badge kết quả không compact')

    def test_o_icon_ket_qua_la_tile_chung(self):
        """Icon pass/fail/idle là TÍN HIỆU trạng thái ⇒ đi qua `wj-lc__tile` của
        khung, màn chỉ tô màu (`-ico`), không tự dựng ô vuông riêng."""
        tile = self._nhan_su().xpath('.//span[contains(@t-attf-class, "wj-lc__tile")]')
        self.assertEqual(len(tile), 1)
        cls = tile[0].get('t-attf-class')
        self.assertIn('wujia-mexam-rrow-ico', cls)
        for trang_thai in ('is-pass', 'is-fail', 'is-idle'):
            self.assertIn(trang_thai, cls)
