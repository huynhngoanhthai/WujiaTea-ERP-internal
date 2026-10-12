"""E6c — nút màn Thi sau khi về atom Button CMP-BTN-001 (`UI-BUTTON-001`).

Sổ chung (`wujia_portal_base/tests/test_scan_e6_button.py`) canh "đủ call site /
họ cũ biến mất". Ở đây là phần riêng của màn Thi (luật F5b):

  · ô chọn ngày, ô khung giờ, FAB, nút lùi đầu wizard là BOUNDARY — nhưng phải
    ĐỌC TOKEN nút (chốt chủ dự án 23/09) để đổi token một chỗ là theo cả hai;
  · nút dựng bằng JS (sửa/xóa dòng người thi) cũng là atom và có tên đọc được;
  · gửi đăng ký dùng `.is-loading` của atom: giữ bề rộng, chặn bấm lặp.
"""
import os
import re

from odoo.tests import TransactionCase, tagged

from odoo.addons.wujia_portal_base.tests.css_probe import CUSTOM, _mod_css, _strip_comments, _view

MOD = os.path.join(CUSTOM, 'wujia_portal_exam')
BOUNDARY = ('wj-exam-pc-day', 'wj-exam-pc-slot', 'wujia-mexam-cal-day', 'wujia-mexam-slot',
            'wujia-mexam-fab', 'wujia-mexam-back')
# (selector gốc của khối, khai kích thước phải đọc token)
TOKEN_BLOCKS = (
    ('.wj-exam-pc-day', ('height',)),
    ('.wj-exam-pc-slot', ('min-height',)),
    ('.wujia-mexam-cal-day', ('width', 'height')),
    ('.wujia-mexam-slot', ('min-height',)),
    ('.wujia-mexam-fab', ('height',)),
)
SELECTED = ('.wj-exam-pc-day.is-selected', '.wj-exam-pc-slot.is-selected',
            '.wujia-mexam-cal-day.is-available.is-selected',
            '.wujia-mexam-slot.is-selected .wujia-mexam-slot-radio')


def _js(name):
    with open(os.path.join(MOD, 'static', 'src', 'js', name), encoding='utf-8') as fh:
        return fh.read()


def _block(css, selector):
    m = re.search(r'(?:^|[}\s])%s\s*\{([^{}]*)\}' % re.escape(selector), css)
    return m.group(1) if m else None


def _decls(body):
    return {k.strip(): v.strip() for k, v in
            (d.split(':', 1) for d in body.split(';') if ':' in d)}


@tagged('post_install', '-at_install', 'wujia_button_e6')
class TestExamButtonE6c(TransactionCase):

    def setUp(self):
        super().setUp()
        self.css = _strip_comments(_mod_css('wujia_portal_exam', 'portal_exam.css'))

    def test_boundary_khong_mang_atom(self):
        root = _view('wujia_portal_exam', 'portal_exam.xml')
        for el in root.iter():
            cls = ((el.get('class') or '') + ' ' + (el.get('t-attf-class') or '')).split()
            ranh = [b for b in BOUNDARY if any(c == b or c.startswith(b + '--') for c in cls)]
            if ranh:
                self.assertFalse({'wj-btn', 'wj-iconbtn'} & set(cls),
                                 '%s bị kéo về atom' % ranh[0])
        for name in ('portal_exam_pc.js', 'portal_exam_wizard.js'):
            for cn in re.findall(r"className\s*=\s*['\"]([^'\"]+)", _js(name)):
                if any(b in cn for b in BOUNDARY):
                    self.assertNotIn('wj-btn', cn, name)

    def test_boundary_doc_token_nut(self):
        """Khai px cứng ở đây là sau này sửa token nút sẽ sót ô lịch/khung giờ."""
        for selector, dims in TOKEN_BLOCKS:
            body = _block(self.css, selector)
            self.assertIsNotNone(body, 'mất khối %s' % selector)
            d = _decls(body)
            for dim in dims:
                self.assertIn(dim, d, '%s thiếu %s' % (selector, dim))
                self.assertIn('var(--wj-btn-', d[dim],
                              '%s %s = %s, phải đọc token --wj-btn-*' % (selector, dim, d[dim]))
            radius = d.get('border-radius')
            if radius is not None:
                self.assertRegex(radius, r'^(var\(--[\w-]+\)|50%)$',
                                 '%s border-radius %s là số cứng' % (selector, radius))

    def test_trang_thai_chon_dung_mau_primary_cua_atom(self):
        for selector in SELECTED:
            body = _block(self.css, selector)
            self.assertIsNotNone(body, 'mất khối %s' % selector)
            self.assertIn('var(--wujia-cta)', body, selector)
            self.assertNotRegex(body, r'--(wj-pc|wujia)-primary\)', selector)

    def test_nut_dung_bang_js_la_atom_co_ten(self):
        js = _js('portal_exam_pc.js')
        for moc in ('data-wj-exam-line-edit', 'data-wj-exam-line-remove'):
            m = re.search(r'<button[^>]*%s[^>]*>' % moc, js)
            self.assertTrue(m, 'mất nút %s' % moc)
            self.assertIn('wj-iconbtn wj-iconbtn--ghost', m.group(0), moc)
            self.assertIn('aria-label="', m.group(0), moc)
        self.assertNotIn('wj-exam-pc-iconbtn', js + self.css)

    def test_gui_dang_ky_dung_loading_cua_atom(self):
        """Đổi chữ nút khi gửi làm nút co/giãn — atom giữ bề rộng bằng `.is-loading`."""
        for name, moc in (('portal_exam_pc.js', 'setBusy(sendBtn, true)'),
                          ('portal_exam_wizard.js', 'setBusy(submit, true)')):
            js = _js(name)
            self.assertIn(moc, js, name)
            self.assertRegex(js, r"classList\.toggle\(['\"]is-loading['\"]", name)
            self.assertNotRegex(js, r'textContent\s*=\s*[\'"]Đang gửi', name)

    def test_nut_lui_wizard_co_ten_doc_duoc(self):
        root = _view('wujia_portal_exam', 'portal_exam.xml')
        backs = [el for el in root.iter() if 'wujia-mexam-back' in (el.get('class') or '').split()]
        self.assertEqual(len(backs), 4)
        for el in backs:
            self.assertTrue((el.get('aria-label') or '').strip(), 'nút lùi wizard thiếu aria-label')
