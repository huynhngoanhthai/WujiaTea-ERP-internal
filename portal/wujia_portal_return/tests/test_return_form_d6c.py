"""D6c — form Bù hàng: UAT-BH-009 (control + nhãn) + UAT-BH-007 nửa dropdown.

  BH-009  "Form có kích thước, khoảng cách và bo góc nhất quán; thao tác chạm dễ
          dàng ở 360px trở lên; trình đọc màn hình xác định đúng tên của từng trường."
  BH-007  "…có vùng hiển thị tên đầy đủ sau khi chọn."

Dáng thật do `scripts/qa/wj_formcontrol.py` đo trên trình duyệt; ở đây khoá hợp đồng
cấu trúc + CSS/JS nguồn.
"""
import os
import re

from lxml import etree

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

HERE = os.path.dirname(__file__)
MOD = os.path.abspath(os.path.join(HERE, '..'))
FORM = os.path.join(MOD, 'views', 'portal_return_form.xml')
CSS = os.path.join(MOD, 'static', 'src', 'css', 'portal_return.css')
JS = os.path.join(MOD, 'static', 'src', 'js', 'portal_return.js')
SHARED_CSS = os.path.join(get_module_path('wujia_portal_layout'),
                          'static', 'assets', 'css', '_components.css')
OTHER_FORMS = {
    'wujia_portal_support': ('views', 'portal_support.xml'),
    'wujia_portal_info_request': ('views', 'portal_info_request_form.xml'),
}

CONTROLS = ('input', 'select', 'textarea')


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _strip_comments(css):
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


def _controls(node):
    out = []
    for tag in CONTROLS:
        for el in node.iter(tag):
            if (el.get('type') or '') != 'hidden':
                out.append(el)
    return out


@tagged('post_install', '-at_install', 'wujia_return_d6')
class TestReturnFormD6c(TransactionCase):

    def setUp(self):
        super().setUp()
        self.root = etree.parse(FORM)
        self.css = _read(CSS)
        self.shared = _strip_comments(_read(SHARED_CSS))
        self.js = _read(JS)

    # ------------------------------------------------------------ BH-009 nhãn
    def test_moi_nhan_tro_toi_mot_control_co_that(self):
        ids = {el.get('id') for el in self.root.iter() if el.get('id')}
        labels = [l for l in self.root.iter('label') if l.get('class')]
        self.assertGreaterEqual(len(labels), 16, 'kiểm kê D6a: 14+ nhãn ở hai khối')
        thieu = [(l.get('class'), ''.join(l.itertext()).strip()[:28])
                 for l in labels if l.get('for') not in ids]
        self.assertFalse(thieu, f'nhãn không nối được control: {thieu}')

    def test_moi_control_co_ten_cho_trinh_doc_man_hinh(self):
        fors = {l.get('for') for l in self.root.iter('label')}
        trần = [(el.tag, el.get('name')) for el in _controls(self.root)
                if el.get('id') not in fors and not el.get('aria-label')]
        self.assertFalse(trần, f'control không có nhãn lẫn aria-label: {trần}')

    def test_id_khong_trung_giua_khoi_pc_va_mobile(self):
        """Hai khối render ĐỒNG THỜI (chỉ ẩn bằng d-none) — trùng id là hỏng `for`."""
        ids = [el.get('id') for el in self.root.iter() if el.get('id')]
        self.assertEqual(len(ids), len(set(ids)), f'id trùng: {ids}')
        pc = {i for i in ids if i.startswith('wj-ret-pc-')}
        mo = {i for i in ids if i.startswith('wj-ret-m-')}
        self.assertTrue(pc and mo)
        self.assertFalse(pc & mo)

    # ------------------------------------------------------- BH-009 kích thước
    def test_form_mobile_dung_lop_chuan_hoa_control(self):
        forms = [f for f in self.root.iter('form')
                 if 'wj-mform' in (f.get('class') or '').split()]
        self.assertEqual(len(forms), 1, 'form mobile phải mang lớp wj-mform')

    def test_rule_chung_dat_48px_va_radius_token(self):
        m = re.search(r'\.wj-mform \.form-control,\s*\.wj-mform \.form-select\s*\{([^}]*)\}',
                      self.shared)
        self.assertIsNotNone(m, 'thiếu rule chuẩn hoá control của wj-mform')
        body = m.group(1)
        self.assertIn('min-height: 48px', body)
        self.assertIn('var(--wujia-surface-tonal-radius)', body,
                      'radius phải lấy token dùng chung, không gõ số cứng')

    def test_o_loc_dat_nguong_cham_44(self):
        """Q1 (12/09) thay luật 44 quét rộng của D6c: hộp nhìn thấy 38, vùng chạm 44
        nằm ở wrapper. Hợp đồng chi tiết thuộc test của khung (F5b)."""
        for sel in ('.wj-filter-date--hit,\n.wj-filter-selectwrap',
                    'label.wj-filter-search-field'):
            m = re.search(re.escape(sel) + r'\s*\{([^}]*)\}', self.shared)
            self.assertIsNotNone(m, f'thiếu rule chạm cho {sel}')
            self.assertIn('44px', m.group(1))

    def test_hai_truong_chat_xuong_mot_cot_o_360(self):
        css = _strip_comments(self.css)
        m = re.search(r'@media \(max-width: 360px\)\s*\{([^}]*\}[^}]*)\}', css)
        self.assertIsNotNone(m, 'thiếu breakpoint 360 cho cặp trường chật')
        self.assertIn('.wujia-mreturn-grid2', m.group(1))
        self.assertIn('grid-template-columns: 1fr;', m.group(1))

    # -------------------------------------------------------- BH-007 dropdown
    def test_co_vung_ten_day_du_o_ca_hai_khoi(self):
        full = self.root.xpath('//*[contains(@class, "wj-return-line-full")]')
        self.assertEqual(len(full), 2, 'mỗi khối PC/mobile một vùng tên đầy đủ')
        sels = self.root.xpath('//select[contains(@class, "wj-return-line")]')
        self.assertEqual(len(sels), 2)
        for s in sels:
            self.assertIn(s.get('aria-describedby'), {f.get('id') for f in full})

    def test_ten_day_du_lay_nguyen_van_tu_label_controller(self):
        self.assertIn('opt.dataset.full = l.label;', self.js,
                      'tên phải giữ NGUYÊN VĂN, không cắt/ghép thêm')
        self.assertIn('full.textContent = label', self.js)
        self.assertNotIn('slice', self.js.split('const full =')[1].split('orderSel.addEventListener')[0])
        self.assertIn('lineSel.addEventListener("change", showFull)', self.js)

    def test_vung_ten_day_du_khong_cat_chu(self):
        m = re.search(r'\.wj-return-line-full\s*\{([^}]*)\}', _strip_comments(self.css))
        self.assertIsNotNone(m)
        body = m.group(1)
        self.assertIn('overflow-wrap: anywhere', body)
        self.assertNotIn('nowrap', body)
        self.assertNotIn('line-clamp', body)

    # ------------------------------------------------ hai form còn lại cùng chuẩn
    def test_hai_form_mobile_khac_cung_theo_chuan(self):
        for mod, parts in OTHER_FORMS.items():
            root = etree.parse(os.path.join(get_module_path(mod), *parts))
            forms = [f for f in root.iter('form')
                     if 'wj-mform' in (f.get('class') or '').split()]
            self.assertTrue(forms, f'{mod}: form mobile chưa mang lớp wj-mform')
            ids = {el.get('id') for el in root.iter() if el.get('id')}
            fors = {l.get('for') for l in root.iter('label') if l.get('for')}
            self.assertTrue(fors, f'{mod}: không nhãn nào nối control')
            self.assertFalse(fors - ids, f'{mod}: nhãn trỏ id không tồn tại: {fors - ids}')
            trần = [el.get('name') for f in forms for el in _controls(f)
                    if el.get('id') not in fors and not el.get('aria-label')
                    and el.get('type') != 'radio']
            self.assertFalse(trần, f'{mod}: control thiếu nhãn: {trần}')
