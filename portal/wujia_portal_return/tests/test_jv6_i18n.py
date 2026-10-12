"""J-V6 — câu gốc của Đổi trả / Bù hàng là tiếng Anh; user vi_VN phải thấy y chữ trước phiên.

Bảng VN dưới đây chép nguyên từ source TRƯỚC J-V6 (HEAD 0d6464be) — chốt chặn khi ai đó đổi
câu EN mà quên glossary/.po.
"""

import os
import re

from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase

from odoo.addons.wujia_portal_base.controllers.utils import status_badge_for
from odoo.addons.wujia_portal_base.tests.common import legacy_vn_badge
from odoo.addons.wujia_return.tests.common import JPEG, ReturnFixture

from .common import load_vi

# Nhãn viết cứng trong controllers/portal.py trước J-V6.
RESOLUTION_VI = {
    'exchange': 'Đổi hàng', 'return': 'Trả hàng', 'compensation': 'Bù hàng', 'refuse': 'Từ chối',
}
COMP_STATUS_VI = {
    'none': 'Chưa xử lý', 'allocated': 'Đã lên đơn bù', 'partial': 'Đang bù một phần', 'done': 'Đã bù đủ',
}
FILTER_ALL_VI = '— Tất cả trạng thái —'
# `_so_delivery_label` trước J-V6.
DELIVERY_VI = {
    'Compensation order cancelled': 'Đơn bù đã bị hủy',
    'No delivery slip yet': 'Chưa tạo phiếu giao',
    'Not delivered': 'Chưa giao',
    'Fully delivered': 'Đã giao đủ',
}
# Câu JS placeholder select sản phẩm trước J-V6 (portal_return.js).
JS_VI = {
    'select-product': '— Chọn sản phẩm —',
    'no-products': '— Đơn không có sản phẩm —',
}
JS_EN = {
    'select-product': '— Select a product —',
    'no-products': '— Order has no products —',
}


def _text(html):
    """Chữ hiển thị thô: bỏ thẻ, gộp khoảng trắng."""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))


def _strip_comments(arch):
    return re.sub(r'<!--.*?-->', '', arch, flags=re.S)


MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@tagged('post_install', '-at_install', 'wujia_return_ct', 'wujia_jv6')
class TestJv6Labels(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env_vi = load_vi(cls.env)
        cls.env_en = cls.env(context=dict(cls.env.context, lang='en_US'))

    def test_resolution_labels(self):
        from odoo.addons.wujia_portal_return.controllers.portal import RESOLUTION_LABELS
        self.assertEqual(set(RESOLUTION_LABELS), set(RESOLUTION_VI))
        for key, old in RESOLUTION_VI.items():
            with self.subTest(key=key):
                lazy = RESOLUTION_LABELS[key]
                self.assertEqual(self.env_vi._(lazy), old)
                self.assertEqual(self.env_en._(lazy), lazy._source)
                self.assertNotEqual(lazy._source, old)

    def test_compensation_status_vi_unchanged_and_same_colour(self):
        from odoo.addons.wujia_portal_return.controllers.portal import COMPENSATION_STATUS_LABELS
        self.assertEqual(set(COMPENSATION_STATUS_LABELS), set(COMP_STATUS_VI))
        for key, old in COMP_STATUS_VI.items():
            with self.subTest(key=key):
                lazy, css = COMPENSATION_STATUS_LABELS[key]
                self.assertEqual(self.env_vi._(lazy), old)
                self.assertEqual(self.env_en._(lazy), lazy._source)
                # Màu không đổi so với nhãn VN cũ (câu EN có trong _STATUS_TERMS_BY_VARIANT).
                self.assertEqual(css, legacy_vn_badge(old))
                self.assertEqual(status_badge_for(lazy._source), css)

    def test_filter_all_and_pager_label(self):
        from odoo.addons.wujia_portal_return.controllers import portal as ctrl
        self.assertEqual(self.env_vi._(ctrl.FILTER_ALL_LABEL), FILTER_ALL_VI)
        self.assertEqual(self.env_en._(ctrl.FILTER_ALL_LABEL), '— All statuses —')
        src = open(ctrl.__file__, encoding='utf-8').read()
        self.assertIn("item_label=_lt('requests')", src)
        self.assertEqual(self.env_vi._(ctrl._lt('requests')), 'yêu cầu')

    def test_delivery_labels_and_generic_error(self):
        from odoo.addons.wujia_portal_return.controllers import portal as ctrl
        src = open(ctrl.__file__, encoding='utf-8').read()
        for en, old in DELIVERY_VI.items():
            with self.subTest(en=en):
                self.assertIn("request.env._('%s')" % en, src)
                self.assertEqual(self.env_vi._(en), old)
        self.assertEqual(self.env_vi._('Delivered %d/%d slips') % (1, 3), 'Đã giao 1/3 phiếu')
        self.assertEqual(
            self.env_vi._('Could not submit the request. Please check the information and try again.'),
            'Không thể gửi yêu cầu. Vui lòng kiểm tra lại thông tin và thử lại.')

    def test_view_labels_in_arch(self):
        """Arch vi_VN của 3 màn vẫn chứa chữ cũ; en_US là câu gốc EN."""
        cases = {
            'wujia_portal_return.portal_return_list': (
                'Yêu cầu đổi trả', 'Danh sách yêu cầu đổi trả', 'Chưa có yêu cầu nào.', 'kết quả',
                'Mã YC / mã đơn / sản phẩm', 'Lọc theo trạng thái'),
            'wujia_portal_return.portal_return_form': (
                'Tạo yêu cầu bù hàng', '— Chọn loại lỗi —', 'Sản phẩm (trong đơn)', *JS_VI.values()),
            'wujia_portal_return.portal_return_detail': (
                'Phương án xử lý', 'Tình trạng bù', 'Không có ghi chú.', 'ảnh đính kèm'),
        }
        for xmlid, words in cases.items():
            view = self.env.ref(xmlid)
            # Comment XML (ghi chú dev, không hiển thị) không dịch ⇒ bỏ trước khi so.
            arch_vi = _strip_comments(view.with_env(self.env_vi).arch)
            arch_en = _strip_comments(view.with_env(self.env_en).arch)
            for word in words:
                with self.subTest(view=xmlid, word=word):
                    self.assertIn(word, arch_vi)
                    self.assertNotIn(word, arch_en)


@tagged('post_install', '-at_install', 'wujia_return_ct', 'wujia_jv6')
class TestJv6JsMessages(TransactionCase):
    """Mọi key `msg("<key>"` trong portal_return.js có `data-wj-msg-<key>` trên CẢ hai select đơn
    (PC + mobile), và fallback trong .js là tiếng Anh."""

    def _read(self, rel):
        with open(os.path.join(MODULE_DIR, rel), encoding='utf-8') as fh:
            return fh.read()

    def test_every_js_key_has_an_attribute_on_both_selects(self):
        js = self._read('static/src/js/portal_return.js')
        keys = set(re.findall(r'msg\("([\w-]+)"', js))
        self.assertEqual(keys, set(JS_EN))
        xml = self._read('views/portal_return_form.xml')
        self.assertEqual(xml.count('t-att="_ret_line_msgs"'), 2)
        for key in keys:
            with self.subTest(key=key):
                self.assertEqual(xml.count("'data-wj-msg-%s'" % key), 1)
        for en in JS_EN.values():
            self.assertIn(en, js)
            self.assertIn(en, xml)

    def test_no_vietnamese_left_in_js(self):
        js = self._read('static/src/js/portal_return.js')
        code = re.sub(r'/\*.*?\*/|//[^\n]*', '', js, flags=re.S)
        for vi in JS_VI.values():
            self.assertNotIn(vi, code)


@tagged('post_install', '-at_install', 'wujia_return_ct', 'wujia_jv6')
class TestJv6PortalByLang(HttpCase, ReturnFixture):
    """User vi_VN thấy chữ cũ, en_US thấy câu gốc EN — cùng dữ liệu, cùng route."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_vi(cls.env)
        cls._setup_return_data()
        for login, lang in (('jv6_vi', 'vi_VN'), ('jv6_en', 'en_US')):
            user = cls.env['res.users'].create({
                'name': login, 'login': login, 'password': login, 'lang': lang,
                'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
            })
            cls.env['wujia.franchise.member'].create({
                'user_id': user.id, 'franchise_id': cls.franchise.id, 'role': 'owner'})
        # Đúng MỘT yêu cầu của cửa hàng ⇒ kiểm luôn số ít EN ("1 result" / "1 request").
        cls.rr = cls._request(resolution_type='compensation', approved_qty=20.0,
                              approved_uom_id=cls.uom_kg.id, compensation_product_id=cls.product.id)
        # Một ảnh ⇒ khối ảnh hiện, kiểm số ít "1 attached photo".
        cls.rr.image_attachment_ids = cls.env['ir.attachment'].create({
            'name': 'jv6.jpg', 'raw': JPEG, 'mimetype': 'image/jpeg'})

    def _get(self, login, url):
        self.authenticate(login, login)
        res = self.url_open(url, timeout=30)
        self.assertEqual(res.status_code, 200)
        return res.text

    def test_list_vi_and_en(self):
        vi = self._get('jv6_vi', '/portal/return')
        en = self._get('jv6_en', '/portal/return')
        self.assertIn(self.rr.name, vi)
        for word in ('Danh sách yêu cầu đổi trả', 'Mã YC / mã đơn / sản phẩm', FILTER_ALL_VI):
            self.assertIn(word, vi)
            self.assertNotIn(word, en)
        for word in ('Return request list', 'Request no. / order no. / product', '— All statuses —'):
            self.assertIn(word, en)
        text_vi, text_en = _text(vi), _text(en)
        self.assertIn('1 kết quả', text_vi)
        self.assertIn('1 yêu cầu', text_vi)
        self.assertRegex(text_en, r'\b1 result\b')
        self.assertRegex(text_en, r'\b1 request\b')
        self.assertNotRegex(text_en, r'\b1 (results|requests)\b')

    def test_form_vi_and_en(self):
        vi = self._get('jv6_vi', '/portal/return/new')
        en = self._get('jv6_en', '/portal/return/new')
        for key in JS_VI:
            with self.subTest(key=key):
                self.assertEqual(vi.count('data-wj-msg-%s="%s"' % (key, JS_VI[key])), 2)
                self.assertEqual(en.count('data-wj-msg-%s="%s"' % (key, JS_EN[key])), 2)
        self.assertIn('Tạo yêu cầu bù hàng', vi)
        self.assertIn('Create compensation request', en)
        self.assertNotIn('Tạo yêu cầu bù hàng', en)

    def test_detail_with_compensation_vi_and_en(self):
        url = '/portal/return/%s' % self.rr.id
        vi = self._get('jv6_vi', url)
        en = self._get('jv6_en', url)
        for word in ('Phương án xử lý', 'Bù hàng', 'Tình trạng bù', 'Chưa xử lý', 'Không có ghi chú.'):
            self.assertIn(word, vi)
        for word in ('Resolution', 'Compensation', 'Compensation status', 'Not processed', 'No notes.'):
            self.assertIn(word, en)
        for word in ('Phương án xử lý', 'Tình trạng bù', 'Chưa xử lý', 'Không có ghi chú.'):
            self.assertNotIn(word, en)
        # Badge giữ màu cũ ở cả hai ngôn ngữ.
        css = legacy_vn_badge(COMP_STATUS_VI['none'])
        self.assertIn('wj-status-badge %s' % css, vi)
        self.assertIn('wj-status-badge %s' % css, en)
        self.assertIn('1 ảnh đính kèm', _text(vi))
        self.assertRegex(_text(en), r'\b1 attached photo\b')
        self.assertNotIn('1 attached photos', _text(en))
