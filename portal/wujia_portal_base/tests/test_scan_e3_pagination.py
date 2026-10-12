"""E3 (nhiều module) — phép toán `build_pager`, cỡ trang và call site pager.

F5b dời khỏi `wujia_portal_layout`: `build_pager`/`parse_page_size` là hàm của
`portal_base`, và việc quét call site là việc của tầng ghép. Hợp đồng render của
component `wj_pagination` vẫn ở layout.
"""
import os
import re

from lxml import etree

from odoo.tests import TransactionCase, tagged

from odoo.addons.wujia_portal_base.controllers.utils import (
    ELLIPSIS, build_pager, parse_page_size,
)

CUSTOM = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _view(module, filename):
    with open(os.path.join(CUSTOM, module, 'views', filename), 'rb') as fh:
        return etree.fromstring(fh.read())


@tagged('post_install', '-at_install', 'wujia_pagination_e3')
class TestBuildPager(TransactionCase):
    """Phép toán phân trang — trước E3 bị chép tay ở 7 controller."""

    def test_so_trang_va_khoang_hien_thi(self):
        p = build_pager(11, 1, 10, path='/x')
        self.assertEqual((p['total_pages'], p['from_'], p['to']), (2, 1, 10))
        p = build_pager(11, 2, 10, path='/x')
        self.assertEqual((p['page'], p['from_'], p['to']), (2, 11, 11))

    def test_trang_vuot_nguong_ve_trang_cuoi(self):
        self.assertEqual(build_pager(11, 99, 10, path='/x')['page'], 2)

    def test_trang_rac_va_am_ve_mot(self):
        for bad in ('abc', 0, -5, None):
            self.assertEqual(build_pager(50, bad, 10, path='/x')['page'], 1)

    def test_khong_co_ban_ghi_van_mot_trang_va_khoang_rong(self):
        p = build_pager(0, 1, 10, path='/x')
        self.assertEqual((p['total_pages'], p['from_'], p['to']), (1, 0, 0))

    def test_page_size_bi_kep_va_rac_ve_mac_dinh(self):
        self.assertEqual(build_pager(10, 1, 9999, path='/x')['page_size'], 100)
        self.assertEqual(build_pager(10, 1, 'x', path='/x')['page_size'], 20)

    def test_numbers_rut_gon_bang_dau_ba_cham(self):
        nums = build_pager(200, 10, 10, path='/x')['numbers']
        self.assertEqual(nums[0], 1)
        self.assertEqual(nums[-1], 20)
        self.assertIn(ELLIPSIS, nums)
        self.assertIn(10, nums)

    def test_chi_dung_url_cho_so_trang_thuc_su_hien(self):
        """1500 user: 500 trang mà dựng 500 URL là phí — chỉ dựng chỗ render."""
        p = build_pager(5000, 1, 10, path='/x')
        self.assertEqual(p['total_pages'], 500)
        self.assertEqual(set(p['urls']), {n for n in p['numbers'] if n != ELLIPSIS})

    def test_url_mang_so_trang(self):
        p = build_pager(30, 2, 10, path='/portal/x')
        self.assertTrue(p['prev_url'].startswith('/portal/x?'))
        self.assertIn('page=1', p['prev_url'])
        self.assertIn('page=3', p['next_url'])


@tagged('post_install', '-at_install', 'wujia_pagination_e3')
class TestPaginationCallSites(TransactionCase):
    """Call site lượt E3a — không còn họ pager riêng, đi qua component."""

    MIGRATED = [
        ('wujia_portal_purchase_history', 'portal_history.xml', 2),
        ('wujia_portal_support', 'portal_support.xml', 2),
        # E3b
        ('wujia_portal_notification', 'portal_notification.xml', 2),
        ('wujia_portal_delivery', 'portal_delivery.xml', 2),
        ('wujia_portal_knowledge', 'portal_knowledge.xml', 2),
        ('wujia_portal_return', 'portal_return_list.xml', 2),
        ('wujia_portal_info_request', 'portal_info_request_list.xml', 1),
        ('wujia_portal_base', 'portal_franchise_information.xml', 2),
        # E3c — 5 khối cuối của kiểm kê + 2 khối mobile vốn thiếu hẳn pager
        ('wujia_portal_exam', 'portal_exam.xml', 2),
        ('wujia_portal_debt', 'portal_debt.xml', 3),
        ('wujia_portal_sale', 'portal_order_catalog.xml', 2),
        ('wujia_portal_layout', 'pc_preview.xml', 1),
    ]
    LEGACY = ('wj-pc-pagination', 'wujia-mhist-pager', 'wujia-pagination',
              'wj-pc-page-btn', 'wujia-mknow-pager', 'wujia-mnoti-pager',
              'wj-exam-pc-pagination', 'wj-pc-order-pager', 'wj-debt-pc-pagination',
              'wj-debt-pc-pagebtn', 'wj-debt-pc-pagesize')

    def test_call_site_di_qua_component(self):
        for module, filename, n in self.MIGRATED:
            root = _view(module, filename)
            calls = root.xpath('//t[@t-call="wujia_portal_layout.wj_pagination"]')
            self.assertEqual(len(calls), n, '%s: số call site pager đổi' % module)

    def test_khong_con_ho_pager_cu(self):
        for module, filename, _n in self.MIGRATED:
            raw = etree.tostring(_view(module, filename), encoding='unicode')
            for cls in self.LEGACY:
                self.assertNotIn(cls, raw, '%s còn họ cũ %s' % (module, cls))


@tagged('post_install', '-at_install', 'wujia_pagination_e3')
class TestPageSizeParam(TransactionCase):
    """Cỡ trang: một đường đọc chung, chỉ nhận giá trị có trong ô chọn."""

    def test_rac_va_thieu_ve_mac_dinh_cua_route(self):
        for value in (None, '', 'abc', '0', '-5', '7', '1000'):
            self.assertEqual(parse_page_size(value, 20), 20, 'rác: %r' % value)

    def test_gia_tri_trong_o_chon_thi_nhan(self):
        self.assertEqual(parse_page_size('50', 20), 50)
        self.assertEqual(parse_page_size(10, 20), 10)

    def test_bac_rieng_cua_tung_man(self):
        """Kiến thức là lưới 3 cột nên bậc là bội của 12 — bậc chung 10/20/50 sẽ làm
        mặc định 12 rơi ra ngoài ô chọn (ô select không có mục nào được chọn)."""
        self.assertEqual(parse_page_size('24', 12, (12, 24, 48)), 24)
        self.assertEqual(parse_page_size('20', 12, (12, 24, 48)), 12)
        # Neo vào chính controller, không chỉ vào hàm: đổi bậc ở đó phải làm đỏ test này.
        from odoo.addons.wujia_portal_knowledge.controllers import portal as kn
        self.assertEqual(kn.PAGE_SIZE, 12)
        self.assertIn(kn.PAGE_SIZE, kn.PAGE_SIZE_OPTIONS, 'mặc định rơi ngoài ô chọn')
        self.assertTrue(all(o % kn.PAGE_SIZE == 0 for o in kn.PAGE_SIZE_OPTIONS),
                        'bậc Kiến thức phải là bội của 12 cho lưới 3 cột')


@tagged('post_install', '-at_install', 'wujia_pagination_e3')
class TestPaginationE3bCallSites(TransactionCase):
    """Ba rủi ro riêng của E3b — mỗi cái từng là lỗi thật trên màn đang sửa."""

    E3B = [
        ('wujia_portal_notification', 'portal_notification.xml'),
        ('wujia_portal_delivery', 'portal_delivery.xml'),
        ('wujia_portal_knowledge', 'portal_knowledge.xml'),
        ('wujia_portal_return', 'portal_return_list.xml'),
        ('wujia_portal_info_request', 'portal_info_request_list.xml'),
        ('wujia_portal_base', 'portal_franchise_information.xml'),
    ]

    def test_khong_con_link_trang_tu_noi_tay(self):
        """Ca BA nêu: info-request tự nối `?page=&state=&request_type=` nên đổi trang
        là rơi `q`/`date_from`/`date_to`. URL trang nay chỉ đến từ `build_pager`."""
        for module, filename in self.E3B:
            raw = etree.tostring(_view(module, filename), encoding='unicode')
            self.assertNotIn('?page=', raw, '%s: còn tự nối link trang' % module)
            self.assertNotIn('page_previous', raw, '%s: còn pager dict cũ' % module)

    def test_chu_tiem_khong_lay_tu_trang_dang_xem(self):
        """Phân trang đẩy chủ tiệm sang trang 2 ⇒ lọc trên `members` là mất tên
        người phụ trách ngay khi cửa hàng có hơn 10 thành viên."""
        root = _view('wujia_portal_base', 'portal_franchise_information.xml')
        owner = root.xpath('//t[@t-set="owner_member"]')[0].get('t-value')
        self.assertEqual(owner, 'franchise.main_owner_member_id')

    def test_dong_dem_thanh_vien_la_tong_that(self):
        """`len(members)` sau phân trang chỉ còn số dòng của trang đang xem."""
        root = _view('wujia_portal_base', 'portal_franchise_information.xml')
        raw = etree.tostring(root, encoding='unicode')
        self.assertNotIn('len(members)', raw, 'dòng đếm vẫn theo trang')
        # Tổng thật do component in ("Hiển thị 1–10 / N thành viên"), không đếm lại.
        foot = root.xpath('//div[@class="wj-pc-acct-members__foot"]'
                          '/t[@t-call="wujia_portal_layout.wj_pagination"]')
        self.assertEqual(len(foot), 1, 'chân bảng thành viên không gọi component')


@tagged('post_install', '-at_install', 'wujia_pagination_e3')
class TestPaginationE3cCallSites(TransactionCase):
    """Lượt cuối: 10 họ pager theo route đi hẳn khỏi portal, chỉ nhóm Khảo sát giữ
    lại (defer, luật 08/09) và phải nằm trong đúng vỏ của nó."""

    # Họ cũ + file CSS từng khai dáng cho chúng. Đọc THẲNG file: một call site đi
    # rồi mà rule dáng còn ở lại là nợ kỹ thuật vô hình (không test nào bắt).
    CSS_FILES = [
        ('wujia_portal_layout', 'static/assets/css/_components.css'),
        ('wujia_portal_layout', 'static/assets/css/_pc_components.css'),
        ('wujia_portal_layout', 'static/assets/css/_interaction.css'),
        ('wujia_portal_layout', 'static/assets/css/_variables.css'),
        ('wujia_portal_exam', 'static/src/css/portal_exam.css'),
        ('wujia_portal_debt', 'static/src/css/portal_debt.css'),
        ('wujia_portal_notification', 'static/src/css/portal_notification.css'),
        ('wujia_portal_sale', 'static/src/css/portal_order.css'),
    ]
    LEGACY = TestPaginationCallSites.LEGACY

    def _file(self, module, relpath):
        with open(os.path.join(CUSTOM, module, *relpath.split('/')),
                  encoding='utf-8') as fh:
            return re.sub(r'/\*.*?\*/', '', fh.read(), flags=re.S)

    def test_khong_con_dang_cua_ho_cu_trong_css(self):
        """Trừ đúng một ngoại lệ: rule thu hẹp vào `.wj-inspection-pc` để nhóm Khảo
        sát (defer) giữ nguyên dáng — thu hẹp chứ không còn là dáng dùng chung."""
        for module, relpath in self.CSS_FILES:
            css = self._file(module, relpath)
            for dong in css.split('\n'):
                if '{' not in dong and ',' not in dong:
                    continue
                for ho in self.LEGACY:
                    if ho in dong:
                        self.assertIn('.wj-inspection-pc', dong,
                                      '%s: còn khai dáng cho họ cũ %s' % (relpath, ho))

    def test_o_co_trang_cong_no_la_dieu_khien_that(self):
        """Trước E3c là nhãn tĩnh `10 / trang` bấm không được (họ lỗi "pager giả"
        mà D5 từng bắt) ⇒ nay phải là bậc thật đi qua `parse_page_size`."""
        from odoo.addons.wujia_portal_debt.controllers import portal as debt
        self.assertEqual(debt._PC_PAGE_SIZE, 10)
        self.assertIn(debt._PC_PAGE_SIZE, debt._PC_PAGE_SIZES,
                      'mặc định rơi ngoài ô chọn')
        self.assertEqual(parse_page_size('50', debt._PC_PAGE_SIZE, debt._PC_PAGE_SIZES), 50)

    def test_bac_co_trang_catalog_la_boi_cua_mac_dinh(self):
        """Lưới sản phẩm: bậc không phải bội của 24 sẽ làm vỡ hàng cuối."""
        from odoo.addons.wujia_portal_sale.controllers import portal as sale
        self.assertEqual(sale.PAGE_SIZE, 24)
        self.assertIn(sale.PAGE_SIZE, sale.PAGE_SIZE_OPTIONS)
        self.assertTrue(all(o % sale.PAGE_SIZE == 0 for o in sale.PAGE_SIZE_OPTIONS))

    def test_hai_man_mobile_co_pager(self):
        """Lỗi nghiệp vụ thật lộ ra khi kiểm kê: server cắt trang mà khối mobile của
        Thi và Đặt hàng không có nút trang nào ⇒ không xem được từ trang 2."""
        for module, filename, slot_id in (
                ('wujia_portal_exam', 'portal_exam.xml', 'wj-exam-mbody'),
                ('wujia_portal_sale', 'portal_order_catalog.xml', 'wj-ord-mbody')):
            root = _view(module, filename)
            khoi = root.xpath('//div[@id="%s"]' % slot_id)
            self.assertEqual(len(khoi), 1, '%s: không thấy khối mobile' % module)
            self.assertTrue(
                khoi[0].xpath('.//t[@t-call="wujia_portal_layout.wj_pagination"]'),
                '%s: khối mobile vẫn không có pager' % module)

    def test_dong_tong_ky_loc_khong_bi_pager_nuot(self):
        """Tổng thanh toán là thông tin của KỲ LỌC ⇒ phải hiện cả khi 1 trang, nên
        nằm ngoài component (component tự ẩn khi total_pages <= 1)."""
        root = _view('wujia_portal_debt', 'portal_debt.xml')
        tong = root.xpath('//*[contains(@class, "wj-debt-pc-histfoot__total")]')
        self.assertEqual(len(tong), 1, 'mất dòng tổng của kỳ lọc')
        self.assertFalse(
            tong[0].xpath('ancestor::t[@t-call="wujia_portal_layout.wj_pagination"]'),
            'dòng tổng bị kéo vào trong pager ⇒ 1 trang là mất')

    def test_khong_con_link_trang_tu_noi_tay(self):
        """Ba controller cuối từng tự nối query-string (exam `querystring`, debt
        `?week=&page=`, catalog `_fallback_pager`) — nguồn của lỗi rơi bộ lọc."""
        for module, filename in (
                ('wujia_portal_exam', 'portal_exam.xml'),
                ('wujia_portal_debt', 'portal_debt.xml'),
                ('wujia_portal_sale', 'portal_order_catalog.xml')):
            raw = etree.tostring(_view(module, filename), encoding='unicode')
            self.assertNotIn('?page=', raw, '%s: còn tự nối link trang' % module)
            self.assertNotIn('page_previous', raw, '%s: còn pager dict cũ' % module)
            self.assertNotIn('querystring', raw, '%s: còn biến querystring' % module)
        for module in ('wujia_portal_exam', 'wujia_portal_debt', 'wujia_portal_sale'):
            with open(os.path.join(CUSTOM, module, 'controllers', 'portal.py'),
                      encoding='utf-8') as fh:
                py = fh.read()
            self.assertNotIn('_fallback_pager', py, '%s: còn pager tự chế' % module)
            self.assertIn('build_pager', py, '%s: không đi qua nguồn chung' % module)
