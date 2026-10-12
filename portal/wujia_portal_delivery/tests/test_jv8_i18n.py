"""J-V8a — câu gốc của màn Giao hàng là tiếng Anh; user vi_VN phải thấy y chữ trước phiên.

Bảng VN chép nguyên từ source TRƯỚC J-V8a (HEAD 5dc1c1a0) — chốt chặn khi ai đó đổi câu EN mà quên
glossary/.po. Chạy: `--test-tags wujia_jv8`.
"""
import re

from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase

from odoo.addons.wujia_portal_base.controllers.utils import status_badge
from odoo.addons.wujia_portal_delivery.controllers import portal as ctrl
from odoo.addons.wujia_portal_delivery.tests.test_delivery_c5 import DeliveryFixture

DELIVERY_MODULES = ('wujia_portal_layout', 'wujia_portal_base', 'wujia_delivery', 'wujia_portal_delivery')

# controllers/portal.py trước J-V8a: (nhãn, bậc màu).
BADGE_VI = {
    'draft': ('Sắp giao', 'processing'), 'assigned': ('Sắp giao', 'processing'),
    'loading': ('Sắp giao', 'processing'), 'delivering': ('Đang giao', 'processing'),
    'done': ('Đã giao', 'success'), 'cancelled': ('Đã hủy', 'danger'),
}
VN_CHARS = re.compile('[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', re.I)


def load_vi(env):
    env['res.lang']._activate_lang('vi_VN')
    env['ir.module.module'].search([('name', 'in', DELIVERY_MODULES)])._update_translations(['vi_VN'])
    return env(context=dict(env.context, lang='vi_VN'))


def _arch(view, env):
    return re.sub(r'<!--.*?-->', '', view.with_env(env).arch, flags=re.S)


def _text(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))


@tagged('post_install', '-at_install', 'wujia_delivery_c5', 'wujia_jv8')
class TestJv8DeliveryLabels(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env_vi = load_vi(cls.env)
        cls.env_en = cls.env(context=dict(cls.env.context, lang='en_US'))

    def test_batch_badge_vi_unchanged(self):
        self.assertEqual(set(ctrl.MOBILE_BATCH_BADGE), set(BADGE_VI))
        for key, (old, variant) in BADGE_VI.items():
            with self.subTest(key=key):
                lazy, modifier = ctrl.MOBILE_BATCH_BADGE[key]
                self.assertEqual(self.env_vi._(lazy), old)
                self.assertEqual(self.env_en._(lazy), lazy._source)
                self.assertFalse(VN_CHARS.search(lazy._source))
                # Màu ghim cứng theo trạng thái, không tra theo nhãn ⇒ đổi câu không đổi màu.
                self.assertEqual(modifier, status_badge(variant))

    def test_pager_label(self):
        label = 'trips'  # gán biến: tránh extractor kéo file test vào .pot
        self.assertEqual(self.env_vi._(label), 'chuyến')
        src = open(ctrl.__file__, encoding='utf-8').read()
        self.assertNotIn("item_label='", src)
        self.assertFalse(VN_CHARS.search(re.sub(r'#.*', '', re.sub(r'"""(.|\n)*?"""', '', src))))

    def test_view_labels_in_arch(self):
        cases = {
            'wujia_portal_delivery.portal_delivery_results_part': ('chuyến · Mới nhất trước', 'Xem'),
            'wujia_portal_delivery.portal_delivery_tracking': (
                'Tìm mã chuyến / mã SO', 'Trạng thái', 'Tất cả trạng thái', 'Sắp giao', 'Đang giao', 'Đã giao'),
            # ★J-VR: cột số lượng mobile — vi giữ "SL", en "Qty" (máy quét sót chữ viết tắt không dấu).
            'wujia_portal_delivery.portal_delivery_detail': ('STT', '<span class="qt">SL</span>'),
        }
        for xmlid, words in cases.items():
            view = self.env.ref(xmlid)
            arch_vi, arch_en = _arch(view, self.env_vi), _arch(view, self.env_en)
            with self.subTest(xmlid=xmlid):
                for w in words:
                    self.assertIn(w, arch_vi)
                self.assertFalse(VN_CHARS.search(arch_en), VN_CHARS.findall(arch_en)[:5])
                self.assertNotIn('>Xem<', arch_en)
                self.assertNotIn('>STT<', arch_en)
                self.assertNotIn('>SL<', arch_en)


@tagged('post_install', '-at_install', 'wujia_delivery_c5', 'wujia_jv8')
class TestJv8DeliveryPages(HttpCase, DeliveryFixture):
    LOGIN = 'jv8_dlv'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_vi(cls.env)
        cls._setup_delivery_data()
        cls.user = cls.env['res.users'].create({
            'name': cls.LOGIN, 'login': cls.LOGIN, 'password': cls.LOGIN, 'lang': 'vi_VN',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        cls.env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.franchise.id, 'role': 'owner'})

    def _open(self, url, lang):
        self.user.lang = lang
        self.env.flush_all()
        # Ngôn ngữ phiên chốt lúc đăng nhập ⇒ đổi lang thì đăng nhập lại.
        self.authenticate(self.LOGIN, self.LOGIN)
        res = self.url_open(url, timeout=30)
        self.assertEqual(res.status_code, 200, url)
        return res

    def test_list_singular_badge_placeholder(self):
        url = '/portal/delivery?q=%s' % self.batch_going.name
        en_html = self._open(url, 'en_US').text
        en = _text(en_html)
        self.assertIn('1 trip ', en)
        self.assertNotIn('1 trips', en)
        self.assertIn('Delivering', en)
        self.assertIn('placeholder="Search trip code / SO code"', en_html)
        self.assertIn('All statuses', en_html)
        vi_html = self._open(url, 'vi_VN').text
        vi = _text(vi_html)
        self.assertIn('1 chuyến', vi)
        self.assertIn('Đang giao', vi)
        self.assertIn('placeholder="Tìm mã chuyến / mã SO"', vi_html)
        self.assertIn('Tất cả trạng thái', vi_html)
        self.assertNotIn('Delivering', vi)

    def test_detail_badge_follows_lang(self):
        url = '/portal/delivery/%d' % self.batch_done.id
        self.assertIn('Delivered', _text(self._open(url, 'en_US').text))
        vi = _text(self._open(url, 'vi_VN').text)
        self.assertIn('Đã giao', vi)
        self.assertNotIn('Delivered', vi)

    def test_ics_follows_lang(self):
        url = '/portal/delivery/%d.ics' % self.batch_soon.id
        en = self._open(url, 'en_US').text
        self.assertIn('SUMMARY:Delivery %s' % self.batch_soon.name, en)
        self.assertIn('Batch: %s' % self.batch_soon.name, en)
        vi = self._open(url, 'vi_VN').text
        self.assertIn('SUMMARY:Giao hàng %s' % self.batch_soon.name, vi)
        self.assertIn('Mã lô: %s' % self.batch_soon.name, vi)
