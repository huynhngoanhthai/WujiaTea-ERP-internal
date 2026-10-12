"""E5b1 — dấu "chưa đọc" của Thông báo sau khi ruột item về CMP-LC-001 (LC-16).

Luật F5b: hợp đồng component ở `wujia_portal_layout`, bảng call site ở
`wujia_portal_base`, còn HÀNH VI RIÊNG của màn thì nằm ở chính module này.
Dấu chưa đọc là hành vi riêng: nó là thứ duy nhất phân biệt hai bản ghi giống
hệt nhau, và không phép đo dáng nào bắt được khi nó biến mất.
"""
import os
import re

from lxml import etree

from odoo.tests import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = os.path.join(HERE, 'static', 'src', 'css', 'portal_notification.css')
VIEW = os.path.join(HERE, 'views', 'portal_notification.xml')


def _css():
    with open(CSS, encoding='utf-8') as fh:
        return re.sub(r'/\*.*?\*/', '', fh.read(), flags=re.S)


def _view():
    return etree.parse(VIEW).getroot()


@tagged('post_install', '-at_install', 'wujia_notification')
class TestNotificationReadStateE5b(TransactionCase):

    def test_item_la_list_card(self):
        items = [el for el in _view().iter()
                 if 'wj-lc' in ((el.get('class') or el.get('t-attf-class') or '').split())]
        self.assertEqual(len(items), 1, 'danh sách phải có đúng 1 item mẫu ListCard')
        self.assertIn('wj-data-item',
                      (items[0].get('class') or items[0].get('t-attf-class') or '').split(),
                      'item thiếu dáng ngoài D5')

    def test_lop_chua_doc_van_do_markup_dat(self):
        """`is-unread` cũ đi cùng họ `wujia-mnoti-row`; nay là lớp trạng thái riêng."""
        markup = open(VIEW, encoding='utf-8').read()
        self.assertIn('wujia-mnoti-unread', markup, 'mất lớp đánh dấu chưa đọc')
        self.assertIn('wujia-mnoti-dot', markup, 'mất chấm chưa đọc trong đầu card')

    def test_thanh_accent_chua_doc_van_song(self):
        """Thanh 4px mép trái là tín hiệu chưa đọc nhìn thấy được — mất nó thì
        danh sách trông đều tăm tắp mà không số đo nào đỏ."""
        css = _css()
        self.assertIn('.wujia-mnoti-unread::before', css)
        self.assertRegex(css, r'\.wujia-mnoti-unread\s*\{[^}]*position:\s*relative')

    def test_trang_thai_khong_gianh_lai_dang_cua_item(self):
        """LC-24: lớp trạng thái của màn chỉ được đổi MÀU/nền, không đặt lại
        đệm/viền/bo — dáng là việc của `.wj-data-item`."""
        css = _css()
        body = re.search(r'\.wujia-mnoti-unread\s*\{([^}]*)\}', css).group(1)
        for cam in ('padding', 'border-radius', 'min-height'):
            self.assertNotRegex(body, r'\b%s\s*:' % cam,
                                'trạng thái chưa đọc giành lại dáng (%s)' % cam)

    def test_cham_chua_doc_co_o_chiem_cho(self):
        """E5c: `.wj-lc__state` không phải flex, nên span rỗng là inline ⇒ w/h bị bỏ
        qua và chấm đo được 0px. Phải tự khai ô chiếm chỗ."""
        css = _css()
        body = re.search(r'\.wujia-mnoti-dot\s*\{([^}]*)\}', css).group(1)
        self.assertRegex(body, r'display:\s*(inline-block|inline-flex|flex|block)',
                         'chấm chưa đọc còn là inline — không hiện ra dù khai w/h')
