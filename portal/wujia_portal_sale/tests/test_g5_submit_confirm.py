"""G5 — WJ-ORD-028 (hộp xác nhận trước khi gửi đơn) + WJ-ORD-027 (lọc gửi lại được).

Luồng trình duyệt thật (mở/Hủy/Esc/nền/double-click, 4 khổ) đo ở `scripts/qa/wj_order_confirm.py`
và `scripts/qa/wj_resubmit.py`; ở đây khoá phần server + markup mà JS dựa vào.
"""
import os
import re
from datetime import timedelta
from unittest.mock import patch

from lxml import html as lhtml

from odoo import fields
from odoo.tests import tagged

from . import test_f6_cart_submit as f6  # module, không import class: loader sẽ chạy lại cả F6

HERE = os.path.dirname(__file__)
ADDONS = os.path.normpath(os.path.join(HERE, '..', '..'))


def _read(*parts):
    with open(os.path.join(ADDONS, *parts), encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install', 'wujia_g5')
class TestG5SubmitConfirm(f6.TestF6CartSubmit):
    """Kế thừa fixture F6 (cửa hàng + chủ + sản phẩm) — chỉ chạy test G5 bên dưới."""

    # F6 đã chạy các test gốc ở class của nó; không lặp lại ở đây.
    # (chỉ method: `test_cursor_lock_timeout`… cũng mang tiền tố test_)
    for _name in [n for n in dir(f6.TestF6CartSubmit)
                  if n.startswith('test_') and callable(getattr(f6.TestF6CartSubmit, n))]:
        locals()[_name] = None
    del _name

    # ------------------------------------------------------------ helpers
    def make_order(self, user=None, state='draft', age=None):
        with patch.object(self.Settings, '_is_within_order_window', return_value=f6.OPEN):
            so = self.env['sale.order'].create({
                'partner_id': self.partner.id, 'franchise_id': self.franchise.id,
                'is_portal_order': True, 'portal_requester_user_id': (user or self.user).id})
        if state != 'draft':
            self.env.cr.execute("UPDATE sale_order SET state=%s WHERE id=%s", (state, so.id))
        if age:
            self.env.cr.execute("UPDATE sale_order SET create_date=%s WHERE id=%s",
                                (fields.Datetime.now() - age, so.id))
        self.env.invalidate_all()
        return so

    def page(self, url):
        res = self.url_open(url)
        self.assertEqual(res.status_code, 200, url)
        return lhtml.fromstring(res.text)

    # ------------------------------------------------------------ 148 server: gửi lại khi giỏ đã rỗng
    def test_double_submit_lands_on_same_order(self):
        self.put(self.p_free, 3)
        first = self.submit()
        so = self.portal_orders()
        self.assertEqual(len(so), 1)
        self.assertEqual(first, f'/portal/purchase-history/{so.id}?message=order_submitted')
        # lượt 2 (Back rồi gửi lại / request trùng tới sau khi lượt 1 commit)
        self.assertEqual(self.submit(), first)
        self.assertEqual(self.submit(flow='m'), f'/portal/order/submitted/{so.id}')
        self.assertEqual(self.portal_orders(), so)

    def test_recent_own_order_redirects(self):
        so = self.make_order()
        self.assertEqual(self.submit(), f'/portal/purchase-history/{so.id}?message=order_submitted')
        self.assertEqual(self.submit(flow='m'), f'/portal/order/submitted/{so.id}')

    def test_no_recent_order_keeps_cart_empty_error(self):
        self.assertEqual(self.submit(), '/portal/order/cart?error=CART_EMPTY')

    def test_other_user_order_not_matched(self):
        other = self.env['res.users'].create({
            'name': 'g5_other', 'login': 'g5_other', 'password': 'g5_other',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])]})
        self.env['wujia.franchise.member'].create({
            'user_id': other.id, 'franchise_id': self.franchise.id, 'role': 'staff'})
        self.make_order(user=other)
        self.assertEqual(self.submit(), '/portal/order/cart?error=CART_EMPTY')

    def test_old_order_not_matched(self):
        self.make_order(age=timedelta(minutes=3))
        self.assertEqual(self.submit(), '/portal/order/cart?error=CART_EMPTY')

    def test_confirmed_order_not_matched(self):
        self.make_order(state='sale')
        self.assertEqual(self.submit(), '/portal/order/cart?error=CART_EMPTY')

    def test_newest_recent_order_wins(self):
        self.make_order(age=timedelta(seconds=60))
        newest = self.make_order()
        self.assertEqual(self.submit(flow='m'), f'/portal/order/submitted/{newest.id}')

    # ------------------------------------------------------------ 148 markup: nút mở hộp, không tự gửi
    def _assert_confirm_markup(self, doc, opener_cls):
        modal = doc.get_element_by_id('wjOrderConfirm')
        self.assertIsNotNone(modal)
        self.assertIn('hidden', modal.attrib)
        panel = modal.xpath('.//*[@role="dialog"]')[0]
        self.assertEqual(panel.get('aria-modal'), 'true')
        actions = [b.get('data-wj-oc-action') for b in modal.xpath('.//button')]
        self.assertEqual(actions, ['cancel', 'confirm'])
        self.assertEqual({e.get('data-wj-oc') for e in modal.xpath('.//*[@data-wj-oc]')},
                         {'changed', 'store', 'lines', 'qty', 'total', 'note'})
        forms = doc.xpath('//form[@data-wj-confirm-form]')
        self.assertTrue(forms)
        for form in forms:
            self.assertEqual(form.get('action'), '/portal/order/submit')
            self.assertEqual(form.get('data-oc-store'), 'F6 store')
            self.assertEqual(form.get('data-oc-lines'), '2')
            self.assertEqual(form.get('data-oc-qty'), '5')
            self.assertTrue(form.get('data-oc-total'))
        openers = doc.xpath(f'//button[contains(@class, "{opener_cls}")]')
        self.assertTrue(openers)
        for btn in openers:
            # type=submit giữ fallback không-JS; JS chặn click và mở hộp
            self.assertEqual(btn.get('type'), 'submit')
            self.assertEqual(btn.get('data-wj-confirm-open'), '1')

    def test_cart_page_markup(self):
        self.put(self.p_free, 3)
        self.put(self.p_max, 2)
        doc = self.page('/portal/order/cart')
        self._assert_confirm_markup(doc, 'wj-pc-cart-submit')
        self._assert_confirm_markup(doc, 'wujia-mcart-submit')

    def test_catalog_page_markup(self):
        self.put(self.p_free, 3)
        self.put(self.p_max, 2)
        self._assert_confirm_markup(self.page('/portal/order'), 'wj-pc-cart-submit')

    def test_open_modal_creates_nothing(self):
        """GET trang (mở hộp là thuần client) không đụng giỏ hay đơn."""
        self.put(self.p_free, 3)
        self.page('/portal/order/cart')
        self.assertFalse(self.portal_orders())
        self.assertEqual(self.qty_of(self.p_free), 3)

    # ------------------------------------------------------------ 147
    def test_mobile_search_always_has_category(self):
        """Ô ẩn `category_id` phải có sẵn để chip AJAX ghi vào; thiếu thì tìm kiếm mất danh mục."""
        doc = self.page('/portal/order')
        inp = doc.xpath('//form[contains(@class, "wujia-morder-search")]//input[@name="category_id"]')
        self.assertEqual(len(inp), 1)
        self.assertEqual(inp[0].get('type'), 'hidden')
        self.assertEqual(inp[0].get('value'), '')
        categ = self.env['product.category'].create({'name': 'G5 Trà'})
        self.p_free.categ_id = categ
        doc = self.page(f'/portal/order?category_id={categ.id}')
        inp = doc.xpath('//form[contains(@class, "wujia-morder-search")]//input[@name="category_id"]')
        self.assertEqual(inp[0].get('value'), str(categ.id))

    def test_ajax_list_releases_submit_guard(self):
        """Lọc AJAX ở lại trang ⇒ phải gỡ cờ chống bấm lặp, nếu không lần lọc thứ 2 bị chặn im."""
        ajax = _read('wujia_portal_base', 'static', 'src', 'js', 'wj_ajax_list.js')
        guard = _read('wujia_portal_layout', 'static', 'assets', 'js', 'wujia_button_loading.js')
        self.assertIn('new CustomEvent("wj:form:release"', ajax)
        self.assertIn('load(url, true, form)', ajax)
        self.assertEqual(ajax.count('releaseForm(form);'), 2)  # thành công + bị lượt sau huỷ
        self.assertIn('addEventListener("wj:form:release"', guard)
        self.assertIn('delete form.dataset.wjSubmitting', guard)

    def test_order_js_no_own_submit_flag(self):
        """portal_order.js không được tự chặn theo cờ của CMP-BTN-001 (nút gửi mobile chết)."""
        js = _read('wujia_portal_sale', 'static', 'src', 'js', 'portal_order.js')
        code = re.sub(r'/\*.*?\*/|//[^\n]*', '', js, flags=re.S)
        self.assertNotIn('wjSubmitting', code)
        self.assertIn('requestSubmit', js)
