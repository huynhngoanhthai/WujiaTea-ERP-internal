"""J-V4 — cụm Đặt hàng có câu gốc tiếng Anh: user vi_VN thấy y như trước, en_US thấy EN.

Neo đối chứng là câu tiếng Việt viết cứng TRƯỚC J-V4 (bảng `_BEFORE_*`, git baa5b547): đổi câu EN
mà quên glossary/.po thì đỏ ở đây, không đợi probe text.
"""
import os
import re

from odoo.exceptions import ValidationError
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.wujia_portal_base.controllers.utils import _RateLimiter
from odoo.addons.wujia_portal_base.tests.css_probe import CUSTOM
from odoo.addons.wujia_portal_sale.controllers.portal import (
    ERROR_MESSAGES, LINE_INVALID_MESSAGES, QTY_MESSAGES, SUCCESS_MESSAGES,
)
from odoo.addons.wujia_sale.tests.common import load_vi

VI_MODULES = ('wujia_portal_layout', 'wujia_portal_base', 'wujia_sale', 'wujia_order_window',
              'wujia_portal_sale')

_BEFORE_ERRORS = {
    'STORE_NOT_SELECTED': "Vui lòng chọn cửa hàng trước khi đặt hàng.",
    'STORE_ACCESS_DENIED': "Bạn không có quyền thao tác tại cửa hàng này.",
    'MEMBERSHIP_INACTIVE': "Tài khoản của bạn hiện không còn hiệu lực tại cửa hàng này.",
    'ORDER_TIME_NOT_CONFIGURED': "Chưa có cấu hình thời gian đặt hàng. Vui lòng liên hệ {brand}.",
    'ORDER_TIME_CLOSED': "Hiện ngoài khung giờ đặt hàng. Vui lòng gửi đơn trong thời gian cho phép.",
    'STORE_TZ_NOT_CONFIGURED': "Cửa hàng chưa cấu hình múi giờ nên chưa thể đặt hàng. Vui lòng liên hệ {brand}.",
    'PRODUCT_NOT_AVAILABLE': "Sản phẩm này hiện không còn được phép đặt hàng.",
    'MIN_QTY_NOT_CONFIGURED': "Sản phẩm chưa được cấu hình số lượng đặt tối thiểu. Vui lòng liên hệ {brand}.",
    'QTY_BELOW_MIN': "Số lượng thấp hơn mức tối thiểu của sản phẩm.",
    'QTY_ABOVE_MAX': "Số lượng vượt mức tối đa của sản phẩm.",
    'QTY_INVALID_STEP': "Số lượng phải tăng theo bước bằng số lượng tối thiểu.",
    'CART_EMPTY': "Giỏ hàng chưa có sản phẩm.",
    'CART_LOAD_FAILED': "Không thể tải giỏ hàng. Vui lòng thử lại.",
    'CART_HAS_INVALID_PRODUCT': "Một số sản phẩm trong giỏ không còn được phép đặt. Vui lòng kiểm tra lại.",
    'CART_QUANTITY_INVALID': "Số lượng một số sản phẩm chưa hợp lệ. Vui lòng kiểm tra lại.",
    'CART_IS_PROCESSING': "Giỏ hàng đang được một người dùng khác gửi đơn. Vui lòng thử lại sau.",
    'STORE_CUSTOMER_NOT_CONFIGURED': "Cửa hàng chưa được cấu hình khách hàng đặt hàng. Vui lòng liên hệ {brand}.",
    'ORDER_CREATE_FAILED': "Không thể tạo đơn hàng. Vui lòng thử lại hoặc liên hệ {brand}.",
    'OLD_PORTAL_QUOTATION_CANCEL_FAILED': "Không thể hoàn tất đơn hàng do đơn nháp cũ chưa được xử lý. Vui lòng thử lại.",
    'PRODUCT_LIST_UNAVAILABLE': "Không thể tải danh sách sản phẩm. Vui lòng thử lại.",
    'invalid_input': "Dữ liệu gửi lên không hợp lệ.",
    'no_active_franchise': "Vui lòng chọn cửa hàng trước khi đặt hàng.",
    'cart_empty': "Giỏ hàng chưa có sản phẩm.",
    'branch_locked': "Cửa hàng đang tạm khóa đặt hàng. Vui lòng liên hệ {brand}.",
    'outside_order_window': "Hiện ngoài khung giờ đặt hàng. Vui lòng gửi đơn trong thời gian cho phép.",
    'internal_error': "Có lỗi xảy ra. Vui lòng thử lại hoặc liên hệ {brand}.",
}
_BEFORE_QTY = {
    'QTY_BELOW_MIN': "Số lượng tối thiểu của {name} là {limit}.",
    'QTY_INVALID_STEP': "Số lượng của {name} phải tăng theo bước {limit}.",
    'QTY_ABOVE_MAX': "Số lượng tối đa của {name} là {limit}.",
}
_BEFORE_LINE = {
    'PRODUCT_NOT_AVAILABLE': "Sản phẩm không còn được phép đặt.",
    'MIN_QTY_NOT_CONFIGURED': "Sản phẩm chưa cấu hình số lượng tối thiểu.",
    'CART_QUANTITY_INVALID': "Số lượng chưa hợp lệ (min/bước/max).",
}
_BEFORE_SUCCESS = {'order_submitted': "Đã gửi đơn đặt hàng thành công."}

SALE_DIR = os.path.join(CUSTOM, 'wujia_portal_sale')
JS_FILES = ('portal_order.js', 'portal_cart_sync.js')
PAGES = ('portal_order_catalog.xml', 'portal_order_cart.xml', 'portal_order_product_detail.xml')


@tagged('post_install', '-at_install', 'wujia_f6')
class TestSaleI18nJV4(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env_vi = load_vi(cls.env, VI_MODULES)
        cls.env_en = cls.env(context=dict(cls.env.context, lang='en_US'))

    def test_messages_vi_unchanged(self):
        for name, table, before in (('ERROR', ERROR_MESSAGES, _BEFORE_ERRORS),
                                    ('QTY', QTY_MESSAGES, _BEFORE_QTY),
                                    ('LINE', LINE_INVALID_MESSAGES, _BEFORE_LINE),
                                    ('SUCCESS', SUCCESS_MESSAGES, _BEFORE_SUCCESS)):
            self.assertEqual(set(table), set(before), name)
            for code, vn in before.items():
                with self.subTest(table=name, code=code):
                    self.assertEqual(self.env_vi._(table[code]), vn)
                    en = self.env_en._(table[code])
                    self.assertNotEqual(en, vn)
                    # Placeholder giữ nguyên ⇒ `.format()` / `_wj_brand_text` không gãy ở mọi ngôn ngữ.
                    self.assertEqual(sorted(re.findall(r'\{\w+\}', en)), sorted(re.findall(r'\{\w+\}', vn)))

    def test_composed_labels_follow_lang(self):
        """Câu trước đây ghép bằng f-string (khung qua đêm, ngày khung kế, số nguyên) nay là 1 câu dịch."""
        args = dict(start='10:00', end='04:00', tz='UTC+7')
        self.assertEqual(self.env_vi._('%(start)s today – %(end)s tomorrow (%(tz)s)', **args),
                         '10:00 hôm nay – 04:00 ngày mai (UTC+7)')
        self.assertEqual(self.env_en._('%(start)s today – %(end)s tomorrow (%(tz)s)', **args),
                         '10:00 today – 04:00 tomorrow (UTC+7)')
        self.assertEqual(self.env_vi._('Today, %s', '06/10/2026'), 'Hôm nay, Ngày 06/10/2026')
        self.assertEqual(self.env_vi._('On %s', '07/10/2026'), 'Ngày 07/10/2026')
        self.assertEqual(self.env_vi._('The quantity of %s must be a whole number.', 'F6 Max'),
                         'Số lượng của F6 Max phải là số nguyên.')

    def test_sale_constraints_follow_lang(self):
        categ = self.env['wujia.product.category'].create({'name': 'JV4 C'})
        product = self.env['product.product'].create(
            {'name': 'JV4 P', 'type': 'consu', 'public_categ_id': categ.id})
        cases = (({'is_public_portal': True, 'min_qty': 0}, 'phải có số lượng tối thiểu > 0',
                  'must have a minimum quantity > 0'),
                 ({'min_qty': -1}, 'không thể âm', 'cannot be negative'))
        for vals, vn, en in cases:
            for env, text in ((self.env_vi, vn), (self.env_en, en)):
                with self.subTest(vals=vals, lang=env.lang), self.assertRaises(ValidationError) as cm:
                    product.with_env(env).write(vals)
                self.assertIn(text, str(cm.exception))

    def test_js_messages_have_translatable_source(self):
        """Mọi key `m("…")` / `this.msg("…")` của JS phải có `data-wj-msg-*` trên #wj-cart-sync,
        và cả 3 trang dùng JS đều gọi gốc đó (không còn div trần thiếu câu)."""
        keys = set()
        for name in JS_FILES:
            with open(os.path.join(SALE_DIR, 'static', 'src', 'js', name), encoding='utf-8') as fh:
                keys |= set(re.findall(r'\b(?:m|this\.msg)\("([a-z-]+)"', fh.read()))
        self.assertGreaterEqual(len(keys), 13)
        arch = self.env_vi.ref('wujia_portal_sale.cart_sync_root').arch
        for key in sorted(keys):
            with self.subTest(key=key):
                self.assertIn("'data-wj-msg-%s'" % key, arch)
        self.assertIn('Xoá sản phẩm này khỏi giỏ?', arch)  # câu JS ra tiếng Việt ở vi_VN
        modal = self.env_vi.ref('wujia_portal_sale.cart_remove_modal').arch
        for text in ('Xoá sản phẩm này khỏi giỏ?', '>Hủy<', '>Xoá<'):
            self.assertIn(text, modal)
        for name in PAGES:
            with open(os.path.join(SALE_DIR, 'views', name), encoding='utf-8') as fh:
                src = fh.read()
            with self.subTest(page=name):
                self.assertIn('t-call="wujia_portal_sale.cart_sync_root"', src)
                self.assertNotIn('<div id="wj-cart-sync" class="d-none" t-att-data-franchise-id="active_franchise_id"/>', src)


@tagged('post_install', '-at_install', 'wujia_f6')
class TestSaleErrorLangJV4(HttpCase):
    """Câu lỗi JSON của giỏ ra theo ngôn ngữ user (đi từ request.env), không cố định tiếng Việt."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_vi(cls.env, VI_MODULES)
        partner = cls.env['res.partner'].create({'name': 'JV4 partner'})
        franchise = cls.env['wujia.franchise.management'].create({
            'code': 'JV4', 'name': 'JV4 store', 'franchise_end_date': '2030-01-01',
            'partner_id': partner.id})
        for lang in ('vi_VN', 'en_US'):
            user = cls.env['res.users'].create({
                'name': 'jv4_%s' % lang, 'login': 'jv4_%s' % lang, 'password': 'jv4_%s' % lang,
                'lang': lang, 'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
            cls.env['wujia.franchise.member'].create({
                'user_id': user.id, 'franchise_id': franchise.id, 'role': 'owner'})
        cls.p_max = cls.env['product.product'].create({
            'name': 'JV4 Max', 'type': 'consu', 'list_price': 1000,
            'is_public_portal': True, 'min_qty': 2, 'max_qty': 10,
            'public_categ_id': cls.env['wujia.product.category'].create({'name': 'JV4 Categ'}).id})
        cls.hidden = cls.env['product.product'].create({'name': 'JV4 Hidden', 'type': 'consu'})

    def setUp(self):
        super().setUp()
        _RateLimiter._store.clear()

    def test_error_follows_user_lang(self):
        expected = {
            'vi_VN': ("Sản phẩm này hiện không còn được phép đặt hàng.",
                      "Số lượng tối thiểu của JV4 Max là 2.", "Số lượng của JV4 Max phải là số nguyên."),
            'en_US': ("This product can no longer be ordered.",
                      "The minimum quantity of JV4 Max is 2.", "The quantity of JV4 Max must be a whole number."),
        }
        for lang, (not_available, below_min, not_integer) in expected.items():
            with self.subTest(lang=lang):
                self.authenticate('jv4_%s' % lang, 'jv4_%s' % lang)
                res = self.make_jsonrpc_request('/portal/order/cart/add', {'product_id': self.hidden.id})
                self.assertEqual(res['message'], not_available)
                res = self.make_jsonrpc_request('/portal/order/cart/add', {'product_id': self.p_max.id, 'qty': 1})
                self.assertEqual(res['message'], below_min)
                res = self.make_jsonrpc_request('/portal/order/cart/add', {'product_id': self.p_max.id, 'qty': '1.5'})
                self.assertEqual(res['message'], not_integer)
