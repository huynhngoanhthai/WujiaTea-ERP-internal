"""J-V8b — câu gốc màn Báo cáo đặt hàng là tiếng Anh; user vi_VN phải thấy y chữ trước phiên.

Bảng VN chép nguyên từ source TRƯỚC J-V8b (HEAD dbd4335b). Chạy: `--test-tags wujia_jv8b`.
"""
import io
import re
from datetime import datetime

import openpyxl

from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase

from odoo.addons.wujia_portal_report.controllers import portal as ctrl

from .common import load_vi

STATE_VI = {
    'draft': ('Nháp', '#8A939E'), 'sent': ('Đã gửi', '#20A0BC'), 'sale': ('Đã xác nhận', '#16A34A'),
    'done': ('Hoàn thành', '#244B87'), 'cancel': ('Đã hủy', '#EF4444'),
}
EXPORT_VI = ['Mã đơn', 'Ngày đặt', 'Cửa hàng', 'Khách hàng', 'Trạng thái', 'Số dòng', 'Tổng tiền']
VIEWS = (
    'wujia_portal_report.portal_report_orders',
    'wujia_portal_report.layout_sidenav_report',
    'wujia_portal_report.mobile_bottomnav_report',
)
VN_CHARS = re.compile('[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', re.I)


def _arch(view, env):
    return re.sub(r'<!--.*?-->', '', view.with_env(env).arch, flags=re.S)


def _text(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))


@tagged('post_install', '-at_install', 'wujia_jv8b')
class TestJv8bReportLabels(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env_vi = load_vi(cls.env)
        cls.env_en = cls.env(context=dict(cls.env.context, lang='en_US'))

    def test_state_labels_and_colors_unchanged(self):
        self.assertEqual(list(ctrl.STATE_LABELS), list(STATE_VI))
        for state, (old_label, old_color) in STATE_VI.items():
            with self.subTest(state=state):
                lazy, color = ctrl.STATE_LABELS[state]
                self.assertEqual(color, old_color)
                self.assertEqual(ctrl._state_label(self.env_vi, state), old_label)
                self.assertEqual(ctrl._state_label(self.env_en, state), lazy._source)
                self.assertFalse(VN_CHARS.search(lazy._source))
        self.assertEqual(ctrl._state_label(self.env_vi, 'weird'), 'weird')
        self.assertEqual(ctrl._state_label(self.env_vi, False), '')

    def test_export_headers_unchanged(self):
        self.assertEqual([self.env_vi._(h) for h in ctrl.EXPORT_HEADERS], EXPORT_VI)
        for header in ctrl.EXPORT_HEADERS:
            self.assertFalse(VN_CHARS.search(header._source))

    def test_title_and_decimal_point(self):
        title = 'Order report'
        self.assertEqual(self.env_vi._(title), 'Báo cáo đặt hàng')
        self.assertEqual(ctrl._decimal_point(self.env_vi), ',')
        self.assertEqual(ctrl._decimal_point(self.env_en), '.')

    def test_controller_source_has_no_vietnamese(self):
        src = open(ctrl.__file__, encoding='utf-8').read()
        code = re.sub(r'#.*', '', re.sub(r'"""(.|\n)*?"""', '', src))
        self.assertFalse(VN_CHARS.search(code), VN_CHARS.findall(code)[:5])

    def test_view_labels_in_arch(self):
        words = {
            'wujia_portal_report.portal_report_orders': (
                'Tổng đơn hàng', 'Không xác định', 'Doanh thu', 'Tổng', '%s đơn', 'đơn hàng', 'sản phẩm',
                'Chưa có dữ liệu trong khoảng đã chọn.', 'Số trong cột: số đơn', 'Doanh thu ('),
            'wujia_portal_report.layout_sidenav_report': ('Báo cáo',),
            'wujia_portal_report.mobile_bottomnav_report': ('Báo cáo',),
        }
        for xmlid in VIEWS:
            view = self.env.ref(xmlid)
            arch_vi, arch_en = _arch(view, self.env_vi), _arch(view, self.env_en)
            with self.subTest(xmlid=xmlid):
                for w in words[xmlid]:
                    self.assertIn(w, arch_vi)
                self.assertFalse(VN_CHARS.search(arch_en), VN_CHARS.findall(arch_en)[:5])
                self.assertNotRegex(view.arch, re.compile(r"or '[^']*" + VN_CHARS.pattern, re.I))


@tagged('post_install', '-at_install', 'wujia_jv8b')
class TestJv8bReportPages(HttpCase):
    LOGIN = 'jv8b_rep'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_vi(cls.env)
        env = cls.env
        partner = env['res.partner'].create({'name': 'JV8B report partner'})
        cls.franchise = env['wujia.franchise.management'].create({
            'code': 'JV8R', 'name': 'JV8B report store', 'partner_id': partner.id,
            'franchise_end_date': '2030-01-01',
        })
        cls.user = env['res.users'].create({
            'name': cls.LOGIN, 'login': cls.LOGIN, 'password': cls.LOGIN, 'lang': 'vi_VN',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])],
        })
        env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.franchise.id, 'role': 'owner'})
        product = env['product.product'].create({'name': 'JV8B tea', 'list_price': 10000.0})
        # Đúng 1 đơn đã xác nhận, 1 sản phẩm ⇒ thấy số ít ở cả KPI lẫn top sản phẩm.
        cls.order = env['sale.order'].create({
            'partner_id': partner.id, 'franchise_id': cls.franchise.id,
            'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 1.0})],
        })
        cls.order.action_confirm()
        cls.order.date_order = datetime.now()

    def _open(self, url, lang):
        self.user.lang = lang
        self.env.flush_all()
        # Ngôn ngữ phiên chốt lúc đăng nhập ⇒ đổi lang thì đăng nhập lại.
        self.authenticate(self.LOGIN, self.LOGIN)
        res = self.url_open(url, timeout=30)
        self.assertEqual(res.status_code, 200, url)
        return res

    def test_singular_counts_follow_lang(self):
        en = _text(self._open('/portal/reports/orders', 'en_US').text)
        self.assertIn('1 order in total', en)
        self.assertIn('1 product ', en)
        self.assertNotIn('1 orders', en)
        self.assertNotIn('1 products', en)
        vi = _text(self._open('/portal/reports/orders', 'vi_VN').text)
        self.assertIn('1 đơn hàng', vi)
        self.assertIn('1 sản phẩm', vi)
        self.assertNotIn('order in total', vi)

    def test_chart_messages_follow_lang(self):
        en = self._open('/portal/reports/orders', 'en_US').text
        vi = self._open('/portal/reports/orders', 'vi_VN').text
        cases = {
            'order': ('%s order', '%s đơn'),
            'orders': ('%s orders', '%s đơn'),
            'total': ('Total', 'Tổng'),
            'revenue': ('Revenue', 'Doanh thu'),
            'million': ('%sM', '%str'),
            'thousand': ('%sK', '%sk'),
            'no-data': ('No data in the selected range.', 'Chưa có dữ liệu trong khoảng đã chọn.'),
        }
        for key, (msg_en, msg_vi) in cases.items():
            with self.subTest(key=key):
                # Đủ ở cả gốc mobile lẫn PC (JS đọc từ gốc gần nhất).
                self.assertEqual(en.count('data-wj-msg-%s="%s"' % (key, msg_en)), 2)
                self.assertEqual(vi.count('data-wj-msg-%s="%s"' % (key, msg_vi)), 2)
        self.assertIn('"decimal_point": ","', vi.replace('&#34;', '"').replace('&quot;', '"'))

    def test_state_summary_follows_lang(self):
        self.assertIn('Confirmed', _text(self._open('/portal/reports/orders', 'en_US').text))
        self.assertIn('Đã xác nhận', _text(self._open('/portal/reports/orders', 'vi_VN').text))

    def _xlsx_rows(self, lang):
        res = self._open('/portal/reports/orders/export.xlsx', lang)
        ws = openpyxl.load_workbook(io.BytesIO(res.content)).active
        return [[c.value for c in row] for row in ws.iter_rows(max_row=2)]

    def test_export_follows_lang(self):
        head_en, row_en = self._xlsx_rows('en_US')
        self.assertEqual(head_en, [h._source for h in ctrl.EXPORT_HEADERS])
        self.assertEqual(row_en[4], 'Confirmed')
        head_vi, row_vi = self._xlsx_rows('vi_VN')
        self.assertEqual(head_vi, EXPORT_VI)
        self.assertEqual(row_vi[4], 'Đã xác nhận')
