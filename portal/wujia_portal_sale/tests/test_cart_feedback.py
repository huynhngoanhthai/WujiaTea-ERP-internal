"""Phản hồi khi bỏ sản phẩm khỏi giỏ: hỏi bằng hộp của portal (`#wjCartRemove`) thay
`window.confirm`, xoá xong báo bằng thẻ dùng chung `wjToast` (khung `wujia_portal_layout`).

Luồng trình duyệt thật (mở/Hủy/Esc/nền/Xoá, vị trí thẻ ở PC + mobile) đo bằng Playwright lúc
nghiệm thu; ở đây khoá phần server + markup mà JS dựa vào.
"""
import os

from lxml import html as lhtml

from odoo.tests import tagged

from . import test_f6_cart_submit as f6  # module, không import class: loader sẽ chạy lại cả F6

HERE = os.path.dirname(__file__)
JS = os.path.join(HERE, '..', 'static', 'src', 'js', 'portal_cart_sync.js')


@tagged('post_install', '-at_install', 'wujia_g5')
class TestCartFeedback(f6.TestF6CartSubmit):
    """Kế thừa fixture F6 (cửa hàng + chủ + sản phẩm) — chỉ chạy test bên dưới."""

    for _name in [n for n in dir(f6.TestF6CartSubmit)
                  if n.startswith('test_') and callable(getattr(f6.TestF6CartSubmit, n))]:
        locals()[_name] = None
    del _name

    def page(self, url):
        res = self.url_open(url)
        self.assertEqual(res.status_code, 200, url)
        return lhtml.fromstring(res.text)

    def test_remove_modal_on_cart_and_catalog(self):
        self.put(self.p_free, 3)
        for url in ('/portal/order/cart', '/portal/order'):
            with self.subTest(url=url):
                modals = self.page(url).xpath('//*[@id="wjCartRemove"]')
                self.assertEqual(len(modals), 1)
                modal = modals[0]
                self.assertIn('hidden', modal.attrib)
                # Cùng khuôn hộp gửi đơn ⇒ ẩn/hiện + nút chia đôi ở màn hẹp đã có sẵn CSS.
                self.assertIn('wj-order-confirm', modal.get('class').split())
                panel = modal.xpath('.//*[@role="dialog"]')[0]
                self.assertEqual(panel.get('aria-modal'), 'true')
                self.assertTrue(modal.xpath('.//*[@data-wj-cr="name"]'))
                buttons = modal.xpath('.//button')
                self.assertEqual([b.get('data-wj-cr-action') for b in buttons], ['cancel', 'confirm'])
                self.assertIn('wj-btn--secondary', buttons[0].get('class'))
                self.assertIn('wj-btn--danger', buttons[1].get('class'))

    def test_trash_button_sits_in_a_named_row(self):
        """JS lấy `data-line-id` + tên sản phẩm từ dòng chứa nút thùng rác."""
        self.put(self.p_free, 3)
        doc = self.page('/portal/order/cart')
        for btn_cls, row_cls, name_cls in (('wj-pc-cart-del', 'wj-pc-cart-row', 'wj-pc-cart-prod-name'),
                                           ('wujia-mcart-del', 'wujia-mcart-row', 'wujia-mcart-row-name')):
            with self.subTest(button=btn_cls):
                buttons = doc.xpath(f'//button[contains(@class, "{btn_cls}")]')
                self.assertTrue(buttons)
                for btn in buttons:
                    row = btn.xpath(f'ancestor::*[contains(@class, "{row_cls}")]')[0]
                    self.assertTrue(row.get('data-line-id'))
                    name = row.xpath(f'.//*[contains(@class, "{name_cls}")]')[0]
                    self.assertEqual(name.text_content().strip(), self.p_free.name)

    def test_remove_answers_removed_so_the_toast_shows(self):
        line = self.put(self.p_free, 3)
        res = self.rpc('/portal/order/cart/remove', line_id=line.id)
        self.assertIs(res['removed'], True)
        self.assertEqual(self.qty_of(self.p_free), 0)

    def test_cart_js_asks_in_page_and_uses_shared_toast(self):
        with open(JS, encoding='utf-8') as fh:
            js = fh.read()
        self.assertIn('getElementById("wjCartRemove")', js)
        self.assertIn('window.wjToast(', js)
        # Hộp trình duyệt chỉ còn là đường lui khi trang thiếu hộp của portal.
        self.assertEqual(js.count('window.confirm('), 1)
