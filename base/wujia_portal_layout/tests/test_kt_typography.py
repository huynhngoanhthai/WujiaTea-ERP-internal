"""KT #191/#193/#73/#83: thang chữ theo vai trò (số #183), một H1 mỗi màn chi tiết, chữ đếm nghiệp vụ."""
import re

from odoo.tests import TransactionCase, tagged

from .test_e5_list_card import _block, _css
from odoo.addons.wujia_portal_layout.tests.src_paths import src

MOBILE_QUERY = '@media (max-width: 991.98px)'

# (module, file CSS, selector) — chữ thân màn chi tiết phải đọc token --wj-t-*.
TOKEN_RULES = (
    ('wujia_portal_layout', 'static/assets/css/_pc_components.css', '.wj-pc-kv__label'),
    ('wujia_portal_layout', 'static/assets/css/_pc_components.css', '.wj-pc-kv__value'),
    ('wujia_portal_delivery', 'static/src/css/portal_delivery.css', '.wujia-mdelivery-row-label'),
    ('wujia_portal_delivery', 'static/src/css/portal_delivery.css', '.wujia-mdelivery-inf-updated'),
    ('wujia_portal_return', 'static/src/css/portal_return.css', '.wujia-mreturn-row-code'),
    ('wujia_portal_return', 'static/src/css/portal_return.css', '.wujia-mreturn-resp-body'),
    ('wujia_portal_notification', 'static/src/css/portal_notification.css', '.wujia-mnoti-detail-typedesc'),
    ('wujia_portal_notification', 'static/src/css/portal_notification.css', '.wujia-mnoti-detail-link-sub'),
    ('wujia_portal_notification', 'static/src/css/portal_notification.css', '.wujia-mnoti-detail-file-meta'),
    ('wujia_portal_base', 'static/src/css/portal_dashboard.css', '.profile-dl dt'),
    ('wujia_portal_base', 'static/src/css/portal_dashboard.css', '.profile-dl dd'),
)

DETAIL_CSS = (
    ('wujia_portal_delivery', 'static/src/css/portal_delivery.css', r'mdelivery-(inf|row|prod|depval)'),
    ('wujia_portal_return', 'static/src/css/portal_return.css', r'mreturn-(resp|summary|row)'),
    ('wujia_portal_support', 'static/src/css/portal_support.css', r'(bubble|detail)'),
    ('wujia_portal_notification', 'static/src/css/portal_notification.css', r'noti-detail'),
    ('wujia_portal_knowledge', 'static/src/css/portal_knowledge.css', r'(article|mknow-(body|lead|meta|att))'),
    ('wujia_portal_exam', 'static/src/css/portal_exam.css', r'exam-pc-kv'),
)

# Màn chi tiết: PageHeader là H1 duy nhất ⇒ view không tự viết <h1>.
DETAIL_VIEWS = (
    'wujia_portal_knowledge.portal_knowledge_detail',
    'wujia_portal_exam.portal_exam_registration_detail',
    'wujia_portal_sale.portal_order_product_detail',
)


def _read(module, path):
    with open(src(module, path), encoding='utf-8') as fh:
        return re.sub(r'/\*.*?\*/', '', fh.read(), flags=re.S)


def _px(value):
    m = re.match(r'^\s*([\d.]+)(px|rem)', value)
    if not m:
        return None
    return float(m.group(1)) * (16 if m.group(2) == 'rem' else 1)


@tagged('post_install', '-at_install', 'wujia_kt_typography')
class TestKtTypography(TransactionCase):

    def _arch(self, xmlid):
        return self.env.ref(xmlid).arch_db

    def test_thang_chu_dung_so_183(self):
        root = _block(_css('_variables.css'), ':root')
        expect = {'name-fs': '15px', 'name-fw': '600', 'label-fs': '12px', 'label-fw': '500',
                  'value-fs': '14px', 'strong-fw': '600', 'caption-fs': '12px'}
        for key, val in expect.items():
            self.assertRegex(root, r'--wj-t-%s\s*:\s*%s;' % (key, val), key)
        css = _css('_variables.css')
        mobile = css[css.index(MOBILE_QUERY):]
        self.assertRegex(mobile, r'--wj-t-value-fs\s*:\s*13px;')

    def test_listcard_doc_cung_thang(self):
        """#183 và chữ màn chi tiết cùng một nguồn số."""
        root = _block(_css('_variables.css'), ':root')
        self.assertRegex(root, r'--wj-lc-title-fs\s*:\s*var\(--wj-t-name-fs\)')
        self.assertRegex(root, r'--wj-lc-label-fs\s*:\s*var\(--wj-t-label-fs\)')

    def test_chu_than_chi_tiet_doc_token(self):
        for module, path, selector in TOKEN_RULES:
            with self.subTest(selector=selector):
                blk = _block(_read(module, path), selector)
                self.assertRegex(blk, r'font-size\s*:\s*var\(--wj-t-[a-z]+-fs\)')

    def test_chi_tiet_khong_chu_duoi_12px(self):
        for module, path, pattern in DETAIL_CSS:
            css = _read(module, path)
            for sel, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
                if not re.search(pattern, sel):
                    continue
                for value in re.findall(r'font-size\s*:\s*([^;]+);', body):
                    size = _px(value)
                    with self.subTest(module=module, selector=sel.strip()):
                        self.assertTrue(size is None or size >= 12, '%s = %s' % (sel.strip(), value))

    def test_mot_h1_moi_man_chi_tiet(self):
        for xmlid in DETAIL_VIEWS:
            with self.subTest(view=xmlid):
                arch = self._arch(xmlid)
                self.assertNotIn('<h1', arch)
                self.assertIn('wujia_portal_layout.wj_page_header', arch)

    def test_khong_lap_ten_duoi_page_header(self):
        self.assertNotIn('<h3 t-out="product.name"', self._arch('wujia_portal_sale.portal_order_product_detail'))
        arch = self._arch('wujia_portal_knowledge.portal_knowledge_detail')
        self.assertNotIn('article-title', arch)
        self.assertEqual(arch.count('ph_title" t-value="article.name"'), 2)

    def test_thi_chi_tiet_back_trong_page_header(self):
        """#193: không còn hàng Back riêng — back nằm trong PageHeader như nhóm chuẩn."""
        arch = self._arch('wujia_portal_exam.portal_exam_registration_detail')
        self.assertNotIn('wj-exam-pc-back', arch)
        self.assertNotIn('wj-pc-page-header', arch)
        self.assertIn('ph_back_url', arch)

    def test_chu_dem_la_danh_tu_nghiep_vu(self):
        """#83: Hỗ trợ/Đổi trả đếm 'yêu cầu', Lịch sử đếm 'đơn hàng'; #73 số không nằm ở PageHeader PC."""
        support = self._arch('wujia_portal_support.portal_support_list')
        self.assertIn('>request<', support)
        self.assertNotIn('>tickets<', support)
        returns = self._arch('wujia_portal_return.portal_return_list')
        self.assertNotIn('>results<', returns)
        self.assertIn('total_items', returns)
        history = self._arch('wujia_portal_purchase_history.portal_history_results_part')
        self.assertNotIn('records', history)
        vi = self.env.ref('wujia_portal_purchase_history.portal_history_results_part').with_context(lang='vi_VN').arch_db
        self.assertIn('đơn hàng</t>', vi)
        self.assertNotIn('pccount', self._arch('wujia_portal_purchase_history.portal_history_list'))
