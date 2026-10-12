"""E4a (quét nhiều module) — call site FilterBar CMP-FB-001 của 2 route mẫu BA.

F5b dời khỏi `wujia_portal_layout`: khung không được biết màn nào. Hợp đồng template
+ CSS của component vẫn ở layout.
"""
import os
import re

from lxml import etree

from odoo.tests import TransactionCase, tagged

CUSTOM = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _view(module, filename):
    path = os.path.join(CUSTOM, module, 'views', filename)
    with open(path, 'rb') as fh:
        return etree.fromstring(fh.read())


def _raw(module, filename):
    with open(os.path.join(CUSTOM, module, 'views', filename),
              encoding='utf-8') as fh:
        return fh.read()


def _ctrl(module):
    with open(os.path.join(CUSTOM, module, 'controllers', 'portal.py'),
              encoding='utf-8') as fh:
        return fh.read()


# Sáu màn có ô ngày — E4c bắt chúng dùng CHUNG một thông điệp, một chỗ hiển thị.
_DATE_VIEWS = (
    ('wujia_portal_purchase_history', 'portal_history.xml'),
    ('wujia_portal_delivery', 'portal_delivery.xml'),
    ('wujia_portal_notification', 'portal_notification.xml'),
    ('wujia_portal_return', 'portal_return_list.xml'),
    ('wujia_portal_exam', 'portal_exam.xml'),
    ('wujia_portal_report', 'portal_report_orders.xml'),
)


def _css(module, relpath):
    with open(os.path.join(CUSTOM, module, *relpath.split('/')),
              encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install', 'wujia_filter_e4')
class TestFilterBarCallSites(TransactionCase):
    """FB-09 mục 1–2: hai route mẫu BA phải gọi component, không tự dựng lại."""

    def test_pc_lich_su_dat_hang_goi_component_va_giu_page_size(self):
        root = _view('wujia_portal_purchase_history', 'portal_history.xml')
        calls = root.xpath('.//t[@t-call="wujia_portal_layout.wj_filter_bar"]')
        # E4b2 thêm call site mobile cùng view ⇒ lọc đúng cái PC.
        self.assertEqual(len(calls), 2)
        calls = [c for c in calls
                 if c.xpath('.//t[@t-set="fb_platform"]')[0].get('t-value') == "'pc'"]
        # WJ-PH-008: mất hidden page_size là người dùng phải chọn lại số dòng.
        self.assertEqual(
            len(calls[0].xpath('.//input[@name="page_size"][@type="hidden"]')), 1)

    def test_mobile_giao_hang_goi_component_giu_id_va_hidden_bs(self):
        root = _view('wujia_portal_delivery', 'portal_delivery.xml')
        calls = root.xpath('.//t[@t-call="wujia_portal_layout.wj_filter_bar"]')
        # E4b1 thêm call site PC cùng view ⇒ phải lọc đúng cái mobile.
        self.assertEqual(len(calls), 2)
        call = [c for c in calls
                if c.xpath('.//t[@t-set="fb_platform"]')[0].get('t-value') == "'m'"][0]
        self.assertEqual(
            call.xpath('.//t[@t-set="fb_id"]')[0].get('t-value'), "'wj-dlv-mform'")
        bs = call.xpath('.//input[@name="bs"][@id="wj-dlv-bs"]')
        self.assertEqual(len(bs), 1)
        self.assertNotIn('t-if', bs[0].attrib)

    def test_hai_man_mau_khong_con_tu_dung_thanh_loc(self):
        for mod, fn, old in (
                ('wujia_portal_purchase_history', 'portal_history.xml',
                 'wj-pc-filterbar'),
                ('wujia_portal_delivery', 'portal_delivery.xml', 'wj-filter-card')):
            root = _view(mod, fn)
            forms = [f for f in root.iter('form')
                     if old in (f.get('class') or '')]
            self.assertEqual(forms, [], f'{fn}: còn form tự dựng {old}')


@tagged('post_install', '-at_install', 'wujia_filter_e4')
class TestFilterBarCallSiteStyle(TransactionCase):

    def test_khong_con_inline_style_o_thanh_loc_hai_man_mau(self):
        for mod, fn in (('wujia_portal_purchase_history', 'portal_history.xml'),
                        ('wujia_portal_delivery', 'portal_delivery.xml'),
                        ('wujia_portal_layout', 'pc_preview.xml')):
            root = _view(mod, fn)
            for call in root.xpath('.//t[@t-call="wujia_portal_layout.wj_filter_bar"]'):
                self.assertEqual(call.xpath('.//*[@style]'), [],
                                 f'{fn}: còn inline style trong thanh lọc')


# --------------------------------------------------------------------------
# E4b1 — 9 thanh lọc PC về component. Quét nhiều module ⇒ ở `portal_base` (F5b).
# --------------------------------------------------------------------------

# (module, file view, bộ `name` PHẢI có — FB-10 "điều kiện trước = sau")
PC_CALL_SITES = [
    ('wujia_portal_support', 'portal_support.xml', {'state'}),
    ('wujia_portal_knowledge', 'portal_knowledge.xml', {'keyword'}),
    ('wujia_portal_return', 'portal_return_list.xml',
     {'q', 'state', 'date_from', 'date_to'}),
    ('wujia_portal_info_request', 'portal_info_request_list.xml',
     {'state', 'request_type'}),
    ('wujia_portal_delivery', 'portal_delivery.xml',
     {'q', 'bs', 'date_from', 'date_to'}),
    ('wujia_portal_notification', 'portal_notification.xml',
     {'keyword', 'type_id', 'unread', 'date_from', 'date_to', 'tab'}),
    ('wujia_portal_exam', 'portal_exam.xml',
     {'q', 'state', 'result', 'date_from', 'date_to'}),
    ('wujia_portal_report', 'portal_report_orders.xml', {'date_from', 'date_to'}),
    ('wujia_portal_sale', 'portal_order_catalog.xml', {'keyword', 'category_id'}),
]

# Họ class bản địa đã xoá ở E4b1 — còn sót là có màn dựng lại thanh lọc riêng.
DEAD_FAMILIES = ('wj-pc-noti-filter', 'wj-pc-noti-field', 'wj-rep-pcfilter__',
                 'wj-exam-pc-fc--', 'wj-exam-pc-filterbar')


def _pc_call(root):
    """t-call component mang fb_platform='pc' (mỗi view tối đa một cái)."""
    for call in root.xpath('.//t[@t-call="wujia_portal_layout.wj_filter_bar"]'):
        plat = call.xpath('.//t[@t-set="fb_platform"]')
        if plat and plat[0].get('t-value') == "'pc'":
            return call
    return None


def _names_of(call):
    """Bộ `name` mà call site khai — gom cả search/dates/selects/hidden."""
    names = set()
    for setter in call.xpath('.//t[@t-set]'):
        key, val = setter.get('t-set'), setter.get('t-value') or ''
        if key == 'fb_search':
            names |= set(re.findall(r"'name':\s*'([^']+)'", val))
        elif key == 'fb_selects':
            names |= set(re.findall(r"'name':\s*'([^']+)'", val))
        elif key == 'fb_dates':
            for side in ('from', 'to'):
                m = re.search(r"'%s_name':\s*'([^']+)'" % side, val)
                names.add(m.group(1) if m else 'date_' + side)
    names |= {i.get('name') for i in call.xpath('.//input[@type="hidden"][@name]')}
    return names


@tagged('post_install', '-at_install', 'wujia_filter_e4')
class TestFilterBarPcCallSitesE4b1(TransactionCase):
    """E4b1: mọi thanh lọc PC của portal phải là MỘT component."""

    def test_chin_man_pc_deu_goi_component(self):
        for module, fn, _names in PC_CALL_SITES:
            call = _pc_call(_view(module, fn))
            self.assertIsNotNone(call, '%s: thanh lọc PC chưa gọi wj_filter_bar' % fn)

    def test_giu_nguyen_bo_dieu_kien_loc_tung_man(self):
        """FB-10 — acceptance chính: không thêm/bớt điều kiện nào."""
        for module, fn, names in PC_CALL_SITES:
            call = _pc_call(_view(module, fn))
            self.assertEqual(_names_of(call), names, '%s: bộ điều kiện lọc lệch' % fn)

    def test_khong_con_thanh_loc_tu_dung_o_chin_man(self):
        for module, fn, _names in PC_CALL_SITES:
            root = _view(module, fn)
            for form in root.iter('form'):
                cls = form.get('class') or ''
                if 'wj-filter-card' in cls or 'morder-search' in cls:
                    continue        # thanh lọc mobile — lượt E4b2
                self.assertNotIn('row g-2', cls, '%s: còn thanh lọc Bootstrap' % fn)
                self.assertNotIn('wj-pc-filterbar', cls,
                                 '%s: còn thanh lọc PC tự dựng' % fn)

    def test_khong_con_ho_class_ban_dia_cua_thanh_loc(self):
        for module, fn, _names in PC_CALL_SITES:
            raw = _raw(module, fn)
            for dead in DEAD_FAMILIES:
                self.assertNotIn(dead, raw, '%s: còn họ class %s' % (fn, dead))

    def test_nhan_nut_ve_chuan_fb02(self):
        """Không call site nào được đè nhãn về 'Tìm'/'Lọc'/'Áp dụng'/'Đặt lại'."""
        for module, fn, _names in PC_CALL_SITES:
            call = _pc_call(_view(module, fn))
            for key in ('fb_submit_label', 'fb_reset_label'):
                self.assertEqual(call.xpath('.//t[@t-set="%s"]' % key), [],
                                 '%s: đè nhãn %s, phải dùng mặc định' % (fn, key))

    def test_hai_thanh_nam_control_dung_bien_the_dense(self):
        """Thông báo + Thi có 5 control: thiếu --dense là tụt xuống 2 hàng ở 1440."""
        for module, fn in (('wujia_portal_notification', 'portal_notification.xml'),
                           ('wujia_portal_exam', 'portal_exam.xml')):
            call = _pc_call(_view(module, fn))
            cls = call.xpath('.//t[@t-set="fb_class"]')
            self.assertTrue(cls and 'wj-pc-filterbar--dense' in cls[0].get('t-value'),
                            '%s: thiếu wj-pc-filterbar--dense' % fn)

    def test_man_thi_dung_o_ngay_that_ca_hai_kho(self):
        """E4c: ô chữ tự gõ không ai kiểm được định dạng — cả hai khổ về type=date,
        knob `kind` đã gỡ khỏi component nên đặt lại là render ra thừa."""
        raw = _raw('wujia_portal_exam', 'portal_exam.xml')
        self.assertNotIn("'kind'", raw)


@tagged('post_install', '-at_install', 'wujia_filter_e4')
class TestFilterBarLegacyCssNarrowed(TransactionCase):
    """Luật 4: họ class cũ chỉ còn nhóm Khảo sát dùng ⇒ thu hẹp, KHÔNG xoá."""

    def test_ho_class_cu_thu_hep_vao_man_khao_sat(self):
        css = _css('wujia_portal_layout',
                   'static/assets/css/_pc_components.css')
        for sel in ('.wj-pc-filter-control', '.wj-pc-filter-search'):
            for line in css.splitlines():
                if line.lstrip().startswith(sel):
                    self.fail('%s còn rule toàn cục, phải nằm dưới .wj-inspection-pc'
                              % sel)
            self.assertIn('.wj-inspection-pc %s' % sel, css,
                          '%s bị xoá hẳn — màn Khảo sát sẽ gãy ngầm' % sel)

    def test_man_khao_sat_khong_bi_dung_toi(self):
        raw = _raw('wujia_portal_inspection',
                   'portal_inspection_list_templates.xml')
        self.assertIn('wj-pc-filter-control', raw)

    def test_bien_the_dense_ton_tai_trong_css(self):
        css = _css('wujia_portal_layout',
                   'static/assets/css/_pc_components.css')
        self.assertIn('.wj-pc-filterbar--dense', css)


# --------------------------------------------------------------------------
# E4b2 — thanh lọc MOBILE về component. Màn Thi cố ý ở lại: khối ngày của nó
# chưa nối, E4c đưa vào component ĐỒNG THỜI với wiring (chốt của chủ dự án).
# --------------------------------------------------------------------------

M_CALL_SITES = [
    ('wujia_portal_purchase_history', 'portal_history.xml',
     {'page_size', 'q', 'date_from', 'date_to'}),
    ('wujia_portal_notification', 'portal_notification.xml', {'unread', 'keyword'}),
    ('wujia_portal_support', 'portal_support.xml', {'state', 'q'}),
    ('wujia_portal_knowledge', 'portal_knowledge.xml', {'keyword'}),
    ('wujia_portal_return', 'portal_return_list.xml',
     {'q', 'state', 'date_from', 'date_to'}),
    ('wujia_portal_report', 'portal_report_orders.xml', {'date_from', 'date_to'}),
]

# id khối chip/lỗi mà `wj_ajax_list.js` thay theo id — mất id là mất AJAX mà
# không màn nào báo lỗi (chỉ nháy cả trang).
AJAX_SLOTS = {
    'wujia_portal_support': ['wj-sup-mchips'],
    'wujia_portal_knowledge': ['wj-know-mchips'],
}


def _m_call(root):
    for call in root.xpath('.//t[@t-call="wujia_portal_layout.wj_filter_bar"]'):
        plat = call.xpath('.//t[@t-set="fb_platform"]')
        if plat and plat[0].get('t-value') == "'m'":
            return call
    return None


@tagged('post_install', '-at_install', 'wujia_filter_e4')
class TestFilterBarMobileCallSitesE4b2(TransactionCase):
    """E4b2: thanh lọc mobile cũng là MỘT component, bộ điều kiện y nguyên."""

    def test_sau_man_mobile_deu_goi_component(self):
        for module, fn, _names in M_CALL_SITES:
            self.assertIsNotNone(_m_call(_view(module, fn)),
                                 '%s: thanh lọc mobile chưa gọi wj_filter_bar' % fn)

    def test_giu_nguyen_bo_dieu_kien_loc_mobile(self):
        """FB-10 bản tĩnh — bản render đo bằng wj_filterbar_inventory.py."""
        for module, fn, names in M_CALL_SITES:
            call = _m_call(_view(module, fn))
            self.assertEqual(_names_of(call), names,
                             '%s: bộ điều kiện lọc mobile lệch' % fn)

    def test_khong_con_thanh_loc_mobile_tu_dung(self):
        for module, fn, _names in M_CALL_SITES:
            root = _view(module, fn)
            for form in root.iter('form'):
                cls = form.get('class') or ''
                self.assertNotIn('wj-filter-card', cls,
                                 '%s: còn thanh lọc mobile tự dựng' % fn)
                self.assertNotIn('wj-rep-mfilter', cls,
                                 '%s: còn thanh lọc mobile tự dựng' % fn)

    def test_chip_giu_id_slot_ajax_khi_vao_slot_tho(self):
        """Chip nằm trong `fb_chips`; mất id là `wj_ajax_list.js` hết chỗ thay."""
        for module, ids in AJAX_SLOTS.items():
            fn = dict((m, f) for m, f, _n in M_CALL_SITES)[module]
            call = _m_call(_view(module, fn))
            chips = call.xpath('.//t[@t-set="fb_chips"]')
            self.assertTrue(chips, '%s: chip không còn đi qua slot fb_chips' % fn)
            for slot_id in ids:
                self.assertTrue(chips[0].xpath('.//*[@id="%s"]' % slot_id),
                                '%s: mất id %s ⇒ mất AJAX' % (fn, slot_id))

    def test_chip_va_loi_dung_part_template_van_nam_trong_slot(self):
        """Lịch sử/Thông báo render chip bằng part template — phải nằm trong slot,
        ra ngoài form là chip rơi khỏi vùng lọc và AJAX thay hụt."""
        for module, fn, slot, part in (
                ('wujia_portal_purchase_history', 'portal_history.xml',
                 'fb_error', 'merr'),
                ('wujia_portal_purchase_history', 'portal_history.xml',
                 'fb_chips', 'mchips'),
                ('wujia_portal_notification', 'portal_notification.xml',
                 'fb_chips', 'mchips')):
            call = _m_call(_view(module, fn))
            node = call.xpath('.//t[@t-set="%s"]' % slot)
            self.assertTrue(node, '%s: thiếu slot %s' % (fn, slot))
            xp = './/t[@t-set="part"][@t-value="\'%s\'"]' % part
            self.assertTrue(node[0].xpath(xp),
                            '%s: slot %s không gọi part %s' % (fn, slot, part))

    def test_khong_man_nao_kep_lai_khoang_ngay(self):
        """Kẹp min/max chặn IM LẶNG cú dời khoảng về trước — đã gỡ ở E4c,
        màn nào đặt lại là tái sinh đúng lỗi vừa sửa."""
        for module, fn in _DATE_VIEWS:
            self.assertNotIn("'clamp'", _raw(module, fn),
                             '%s: đặt lại kẹp ngày' % fn)

    def test_doi_tra_giu_select_tu_submit(self):
        call = _m_call(_view('wujia_portal_return', 'portal_return_list.xml'))
        sel = call.xpath('.//t[@t-set="fb_selects"]')[0].get('t-value')
        self.assertIn("'auto': True", sel)
        self.assertIn('filter_options', sel)

    def test_bao_cao_khong_con_ho_class_rieng(self):
        raw = _raw('wujia_portal_report', 'portal_report_orders.xml')
        self.assertNotIn('wj-rep-mfilter', raw)
        css = _css('wujia_portal_report', 'static/src/css/portal_report.css')
        self.assertNotIn('wj-rep-mfilter', css)

    def test_nhan_nut_mobile_khong_bi_de(self):
        for module, fn, _names in M_CALL_SITES:
            call = _m_call(_view(module, fn))
            self.assertEqual(call.xpath('.//t[@t-set="fb_submit_label"]'), [],
                             '%s: đè nhãn nút, phải dùng mặc định "Tìm kiếm"' % fn)


@tagged('post_install', '-at_install', 'wujia_filter_e4')
class TestFilterBarMobileLeftovers(TransactionCase):
    """Hai chỗ CỐ Ý không vào component + luật 44 cũ phải thu hẹp."""

    def test_dat_hang_giu_thanh_rieng_nhung_ve_chuan_38_44(self):
        raw = _raw('wujia_portal_sale', 'portal_order_catalog.xml')
        # Ô tìm phải bọc <label>: div thì bấm vào lề 44 không focus được ô 38.
        self.assertIn('<label class="wujia-morder-search-input">', raw)
        css = _css('wujia_portal_sale', 'static/src/css/portal_order.css')
        btn = css[css.index('.wujia-morder-search-btn {'):]
        btn = btn[:btn.index('}')]
        # E6b1: 38 không còn viết cứng ở đây mà đọc token chung của thanh lọc, để
        # đổi FB-08 một chỗ là cả 21 thanh theo. Con số vẫn được ghim — ở token.
        self.assertIn('width: var(--wj-filter-btn-h-m)', btn)
        tokens = _css('wujia_portal_layout', 'static/assets/css/_variables.css')
        self.assertRegex(tokens, r'--wj-filter-btn-h-m:\s*38px')
        self.assertIn('border-radius: 10px', btn)
        self.assertIn('.wujia-morder-search-btn::before', css)
        self.assertIn('min-height: 44px', css)

    def test_cong_no_giu_component_rieng_theo_fb09(self):
        """FB-09 mục 9 + Figma v31: Công nợ có thanh lọc riêng đã duyệt — 0 byte."""
        raw = _raw('wujia_portal_debt', 'portal_debt.xml')
        self.assertIn('wj_debt_filter', raw)
        self.assertNotIn('wujia_portal_layout.wj_filter_bar', raw)

    def test_man_thi_mobile_da_vao_component_kem_wiring(self):
        """E4c: khối dựng tay của màn Thi có 2 ô ngày KHÔNG `name` nên bấm tìm
        không gửi gì — vào component là phải kèm `fb_action` + `fb_dates`."""
        root = _view('wujia_portal_exam', 'portal_exam.xml')
        call = _m_call(root)
        self.assertIsNotNone(call, 'màn Thi mobile chưa gọi wj_filter_bar')
        act = call.xpath('.//t[@t-set="fb_action"]')
        self.assertTrue(act and act[0].get('t-value') == "'/portal/exam'")
        self.assertTrue(call.xpath('.//t[@t-set="fb_dates"]'), 'thiếu ô ngày')
        raw = _raw('wujia_portal_exam', 'portal_exam.xml')
        self.assertNotIn("t-value=\"'wj-filter-card'\"", raw,
                         'còn sót khối dựng tay')

    def test_khong_dung_module_anh_thai(self):
        raw = _raw('wujia_portal_inspection',
                   'portal_inspection_list_templates.xml')
        self.assertNotIn('wj_filter_bar', raw)
        self.assertNotIn('wj-filter-card', raw)


@tagged('post_install', '-at_install', 'wujia_filter_e4')
class TestKhoangNgayNguocE4c(TransactionCase):
    """E4c: sáu màn có ngày nói CÙNG một câu, ở CÙNG một chỗ — trong thanh lọc."""

    def test_sau_man_deu_lay_thong_diep_tu_nguon_chung(self):
        """Trước E4c mỗi màn một câu chữ, có màn tính rồi không in ra đâu cả."""
        for module, _fn in _DATE_VIEWS:
            src = _ctrl(module)
            self.assertIn('date_range_error', src,
                          '%s: không dùng nguồn chung' % module)
            self.assertNotIn("'Từ ngày không được lớn hơn", src,
                             '%s: còn câu chữ riêng' % module)

    def test_moi_man_bao_loi_ngay_trong_thanh_loc(self):
        """`fb_error` = báo TẠI thanh lọc; banner đầu trang là chỗ khác."""
        for module, fn in _DATE_VIEWS:
            raw = _raw(module, fn)
            self.assertIn('class="wj-filter-error" role="alert"', raw,
                          '%s: thiếu ô báo lỗi chuẩn' % fn)
            self.assertIn("t-att-hidden=\"None if filter_error else 'hidden'\"", raw,
                          '%s: ô lỗi không luôn hiện diện' % fn)
            self.assertGreaterEqual(
                len(_view(module, fn).xpath('.//t[@t-set="fb_error"]')), 2,
                '%s: thiếu slot fb_error cho một trong hai khổ' % fn)

    def test_id_o_bao_loi_deu_nam_trong_wjl_slots(self):
        """Thiếu id trong `wjl_slots`: lọc lại bằng AJAX giữ nguyên lỗi cũ."""
        for module, fn in _DATE_VIEWS:
            raw = _raw(module, fn)
            slots = re.search(r'wjl_slots"\s*\n?\s*t-value="\'([^\']+)\'', raw)
            self.assertTrue(slots, '%s: không tìm thấy wjl_slots' % fn)
            declared = slots.group(1).split(',')
            for eid in re.findall(r'id="([a-z0-9-]*err)"', raw):
                self.assertIn(eid, declared, '%s: %s ngoài wjl_slots' % (fn, eid))

    def test_man_co_fragment_phai_in_ca_hai_manh_loi(self):
        """Giao hàng/Thông báo thay bằng fragment: thiếu part là rơi tải lại trang.

        Phải soi ĐÚNG template fragment — cắt chuỗi từ `wjl_fragment` trở đi là
        soi nhầm phần trang đầy đủ, part vẫn còn ở call site nên guard mù.
        """
        for module, fn in (('wujia_portal_delivery', 'portal_delivery.xml'),
                           ('wujia_portal_notification', 'portal_notification.xml')):
            root = _view(module, fn)
            frag = [t for t in root.xpath('.//template')
                    if (t.get('id') or '').endswith('_results')]
            self.assertEqual(len(frag), 1, '%s: không thấy template fragment' % fn)
            parts = {n.get('t-value') for n in frag[0].xpath('.//t[@t-set="part"]')}
            parts |= set(frag[0].xpath('.//t[@t-foreach]/@t-foreach'))
            blob = ' '.join(p or '' for p in parts)
            for part in ("'pcerr'", "'merr'"):
                self.assertIn(part, blob, '%s: fragment thiếu %s' % (fn, part))

    def test_css_bao_loi_o_dung_chu_layout(self):
        """6 màn dùng chung ⇒ CSS về `wujia_portal_layout` (luật F2/F3 css_owner)."""
        # Phải khớp CẢ dấu `{`: '.wj-filter-error' là tiền tố của mọi tên đổi đi
        # ('.wj-filter-error-x') nên assert lỏng sẽ xanh cả khi rule đã mất.
        self.assertIn('.wj-filter-error {',
                      _css('wujia_portal_layout',
                           'static/assets/css/_components.css'))
        self.assertNotIn('.wj-filter-error {',
                         _css('wujia_portal_purchase_history',
                              'static/src/css/portal_history.css'))
