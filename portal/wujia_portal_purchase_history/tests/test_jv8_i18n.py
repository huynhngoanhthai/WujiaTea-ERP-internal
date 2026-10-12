"""J-V8a — câu gốc của màn Lịch sử đặt hàng là tiếng Anh; user vi_VN phải thấy y chữ trước phiên.

Bảng VN chép nguyên từ source TRƯỚC J-V8a (HEAD 5dc1c1a0) — chốt chặn khi ai đó đổi câu EN mà quên
glossary/.po. Chạy: `--test-tags wujia_jv8`.
"""
import re
from datetime import date, datetime, timedelta

from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase

from odoo.addons.wujia_portal_purchase_history.controllers import portal as ctrl

HISTORY_MODULES = ('wujia_portal_layout', 'wujia_portal_base', 'wujia_delivery', 'wujia_portal_purchase_history')

# controllers/portal.py trước J-V8a.
BATCH_VI = {
    'draft': 'Nháp', 'assigned': 'Đã gán xe', 'loading': 'Đang chất hàng',
    'delivering': 'Đang giao', 'done': 'Đã giao xong', 'cancelled': 'Hủy chuyến',
}
ERR_VI = {
    'ERR_NO_STORE': 'Không xác định được cửa hàng đang thao tác. Vui lòng chọn lại cửa hàng.',
    'ERR_NOT_FOUND': 'Không tìm thấy đơn hàng hoặc bạn không có quyền xem đơn hàng này.',
}
VN_CHARS = re.compile('[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', re.I)


def load_vi(env):
    env['res.lang']._activate_lang('vi_VN')
    env['ir.module.module'].search([('name', 'in', HISTORY_MODULES)])._update_translations(['vi_VN'])
    return env(context=dict(env.context, lang='vi_VN'))


def _arch(view, env):
    return re.sub(r'<!--.*?-->', '', view.with_env(env).arch, flags=re.S)


def _text(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))


@tagged('post_install', '-at_install', 'wujia_history', 'wujia_jv8')
class TestJv8HistoryLabels(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env_vi = load_vi(cls.env)
        cls.env_en = cls.env(context=dict(cls.env.context, lang='en_US'))

    def test_batch_status_labels_vi_unchanged(self):
        self.assertEqual(set(ctrl.BATCH_STATUS_LABELS), set(BATCH_VI))
        for key, old in BATCH_VI.items():
            with self.subTest(key=key):
                lazy = ctrl.BATCH_STATUS_LABELS[key]
                self.assertEqual(self.env_vi._(lazy), old)
                self.assertEqual(self.env_en._(lazy), lazy._source)
                self.assertFalse(VN_CHARS.search(lazy._source))
        # Khoá bảng nhãn = khoá selection của field (lệch ⇒ chi tiết đơn rơi về "Chưa có thông tin giao hàng").
        sel = dict(self.env['stock.picking.batch']._fields['delivery_batch_status'].selection)
        self.assertEqual(set(sel), set(BATCH_VI))

    def test_error_messages_vi_unchanged(self):
        for name, old in ERR_VI.items():
            with self.subTest(name=name):
                lazy = getattr(ctrl, name)
                self.assertEqual(self.env_vi._(lazy), old)
                self.assertFalse(VN_CHARS.search(lazy._source))

    def test_backend_requester_brand_after_translation(self):
        lazy = ctrl.BACKEND_REQUESTER_LABEL
        self.assertEqual(self.env_vi._(lazy), '{brand} tạo đơn')
        brand = self.env.company._wj_brand_info()['name']
        partner = self.env['res.partner'].create({'name': 'JV8 partner'})
        order = self.env['sale.order'].create({'partner_id': partner.id})
        self.assertEqual(ctrl._requester_display(order.with_env(self.env_vi)), '%s tạo đơn' % brand)
        self.assertEqual(ctrl._requester_display(order.with_env(self.env_en)), '%s (backend)' % brand)

    def test_pager_uses_shared_records_label(self):
        src = open(ctrl.__file__, encoding='utf-8').read()
        self.assertNotIn("item_label='", src)
        self.assertFalse(VN_CHARS.search(re.sub(r'#.*', '', re.sub(r'"""(.|\n)*?"""', '', src))))

    def test_view_labels_in_arch(self):
        cases = {
            'wujia_portal_purchase_history.portal_history_results_part': ('Chưa giao', 'đơn', 'đơn gần nhất'),
            'wujia_portal_purchase_history.portal_history_list': ('Tìm theo mã đơn', 'Tất cả trạng thái'),
            'wujia_portal_purchase_history.portal_history_detail': (
                'Chi tiết đơn hàng', 'Chưa giao', 'Chưa có thông tin giao hàng', 'Không có ghi chú',
                'Trạng thái giao hàng', 'Ghi chú khi đặt hàng', 'Tổng cộng', 'sản phẩm',
                '· SL: x'),
        }
        for xmlid, words in cases.items():
            view = self.env.ref(xmlid)
            arch_vi, arch_en = _arch(view, self.env_vi), _arch(view, self.env_en)
            with self.subTest(xmlid=xmlid):
                for w in words:
                    self.assertIn(w, arch_vi)
                self.assertFalse(VN_CHARS.search(arch_en), VN_CHARS.findall(arch_en)[:5])
                # Câu dự phòng không còn nằm trong biểu thức (biểu thức không dịch được).
                self.assertNotRegex(view.arch, re.compile(r"or '[^']*" + VN_CHARS.pattern, re.I))


@tagged('post_install', '-at_install', 'wujia_history', 'wujia_jv8')
class TestJv8HistoryPages(HttpCase):
    LOGIN = 'jv8_hist'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_vi(cls.env)
        env = cls.env
        cls.partner = env['res.partner'].create({'name': 'JV8 store partner'})
        cls.franchise = env['wujia.franchise.management'].create({
            'code': 'JV8H', 'name': 'JV8 history store', 'partner_id': cls.partner.id,
            'franchise_end_date': date.today() + timedelta(days=365),
        })
        cls.user = env['res.users'].create({
            'name': cls.LOGIN, 'login': cls.LOGIN, 'password': cls.LOGIN, 'lang': 'vi_VN',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])],
        })
        env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.franchise.id, 'role': 'owner'})
        product = env['product.product'].create({'name': 'JV8 tea', 'is_storable': True, 'list_price': 10000.0})
        # Đúng 1 đơn, 1 dòng sản phẩm, chưa có chuyến giao, không ghi chú ⇒ thấy số ít + mọi câu dự phòng.
        cls.order = env['sale.order'].create({
            'partner_id': cls.partner.id, 'franchise_id': cls.franchise.id,
            'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 1.0})],
        })
        cls.order.date_order = datetime.now()

    def _get(self, url, lang):
        self.user.lang = lang
        self.env.flush_all()
        # Ngôn ngữ phiên chốt lúc đăng nhập ⇒ đổi lang thì đăng nhập lại.
        self.authenticate(self.LOGIN, self.LOGIN)
        res = self.url_open(url, timeout=30)
        self.assertEqual(res.status_code, 200, url)
        return _text(res.text)

    def test_list_singular_and_placeholder(self):
        en = self._get('/portal/purchase-history', 'en_US')
        self.assertIn('1 order ', en)
        self.assertNotIn('1 orders', en)
        self.assertIn('1 latest order ', en)
        self.assertIn('Not delivered yet', en)
        vi = self._get('/portal/purchase-history', 'vi_VN')
        self.assertIn('1 đơn ', vi)
        self.assertIn('1 đơn gần nhất', vi)
        self.assertIn('Chưa giao', vi)
        self.assertNotIn('Not delivered yet', vi)

    def test_list_filter_texts(self):
        self.user.lang = 'en_US'
        self.env.flush_all()
        self.authenticate(self.LOGIN, self.LOGIN)
        en = self.url_open('/portal/purchase-history', timeout=30).text
        self.assertIn('placeholder="Search by order code"', en)
        self.assertIn('All statuses', en)
        self.user.lang = 'vi_VN'
        self.env.flush_all()
        self.authenticate(self.LOGIN, self.LOGIN)
        vi = self.url_open('/portal/purchase-history', timeout=30).text
        self.assertIn('placeholder="Tìm theo mã đơn"', vi)
        self.assertIn('Tất cả trạng thái', vi)

    def test_detail_fallbacks_and_singular(self):
        url = '/portal/purchase-history/%d' % self.order.id
        en = self._get(url, 'en_US')
        for s in ('Not delivered yet', 'No delivery information yet', 'No notes', '1 product ', '01 product '):
            self.assertIn(s, en)
        self.assertNotIn('1 products', en)
        vi = self._get(url, 'vi_VN')
        for s in ('Chưa giao', 'Chưa có thông tin giao hàng', 'Không có ghi chú', '1 sản phẩm', '01 sản phẩm'):
            self.assertIn(s, vi)

    def test_detail_batch_status_follows_lang(self):
        order = self.order.copy({'franchise_id': self.franchise.id})
        order.action_confirm()
        batch = self.env['stock.picking.batch'].create({'name': 'JV8/LOAD', 'delivery_batch_status': 'loading'})
        order.picking_ids.filtered(lambda p: p.state != 'cancel').batch_id = batch
        url = '/portal/purchase-history/%d' % order.id
        self.assertIn('Loading goods', self._get(url, 'en_US'))
        self.assertIn('Đang chất hàng', self._get(url, 'vi_VN'))

    def test_not_found_message(self):
        en = self._get('/portal/purchase-history/999999999', 'en_US')
        self.assertIn('Order not found or you are not allowed to view this order.', en)
        vi = self._get('/portal/purchase-history/999999999', 'vi_VN')
        self.assertIn(ERR_VI['ERR_NOT_FOUND'], vi)
