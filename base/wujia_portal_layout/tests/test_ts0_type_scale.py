"""TS0: thang chữ bản 2 BA (16/10/2026) một nguồn ở `_variables.css` + chặn tăng font-size gõ cứng."""
import importlib.util
import json
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

from .test_e5_list_card import _block, _css
from .test_kt_typography import MOBILE_QUERY, _read

# vai trò: (PC fs/lh, mobile fs/lh)
SCALE = {
    'page': ('24px', '32px', '20px', '28px'),
    'section': ('18px', '24px', '16px', '22px'),
    'card': ('17px', '24px', '15px', '20px'),
    'kpi': ('22px', '28px', '18px', '24px'),
    'code': ('16px', '22px', '14px', '20px'),
    'name': ('15px', '20px', '13px', '18px'),
    'body': ('14px', '21px', '13px', '20px'),
    'button': ('14px', '20px', '13px', '18px'),
    'value': ('14px', '20px', '13px', '18px'),
    'label': ('12px', '18px', '13px', None),
    'caption': ('12px', '18px', None, None),
    'chip': ('12px', '16px', None, None),
}

# (file, selector) — title của PageHeader / SectionHeader / CardHeader đọc vai trò.
HEADERS = (
    ('_pc_components.css', '.wj-page-header--pc .wj-page-header__title', 'page'),
    ('_components.css', '.wj-page-header--m .wj-page-header__title', 'page'),
    ('_pc_components.css', '.wj-section-header--pc .wj-section-header__title', 'section'),
    ('_components.css', '.wj-section-header--any .wj-section-header__title', 'section'),
    ('_pc_components.css', '.wj-card-header--pc.wj-card-header--regular .wj-card-header__title', 'card'),
    ('_components.css', '.wj-card-header--any.wj-card-header--regular .wj-card-header__title', 'card'),
)

# Khảo sát (anh Thái) ngoài phạm vi; nút tìm chỉ chứa icon kính lúp (TS6).
TS1_EXEMPT = re.compile(r'\.wj-inspection-pc|^\.wj-filter-search-btn$')
# Mọi cỡ nút cùng một vai trò chữ; sm/md/lg chỉ khác chiều cao + padding.
BUTTONS = (
    ('_components.css', '.wj-btn'),
    ('_components.css', '.wj-btn--sm'),
    ('_components.css', '.wj-btn--lg'),
    ('_components.css', '.btn.btn-sm'),
    ('_pc_components.css', '.wj-pc-btn'),
)

REPO = os.path.dirname(os.path.dirname(get_module_path('wujia_portal_layout')))
AUDIT = os.path.join(REPO, 'scripts', 'qa', 'wj_type_audit.py')
BASELINE = os.path.join(REPO, 'docs', 'typescale', 'css-baseline.json')


def _mobile_root():
    css = _css('_variables.css')
    return _block(css[css.index(MOBILE_QUERY):], ':root')


@tagged('post_install', '-at_install', 'wujia_ts0_type_scale')
class TestTs0TypeScale(TransactionCase):

    def test_so_ban_2(self):
        root, mobile = _block(_css('_variables.css'), ':root'), _mobile_root()
        for role, (pc_fs, pc_lh, m_fs, m_lh) in SCALE.items():
            with self.subTest(role=role):
                self.assertRegex(root, r'--wj-t-%s-fs\s*:\s*%s;' % (role, pc_fs))
                self.assertRegex(root, r'--wj-t-%s-lh\s*:\s*%s;' % (role, pc_lh))
                for key, val in (('fs', m_fs), ('lh', m_lh)):
                    if val:
                        self.assertRegex(mobile, r'--wj-t-%s-%s\s*:\s*%s;' % (role, key, val))
                    else:
                        self.assertNotRegex(mobile, r'--wj-t-%s-%s\s*:' % (role, key))

    def test_html_14_moi_kho(self):
        """Một cỡ gốc ở mọi khổ, cùng số với Vuexy components.css (nạp sau) ⇒ rem không đổi theo khổ."""
        css = _css('_variables.css')
        self.assertEqual(re.findall(r'html\s*\{\s*font-size\s*:\s*([^;]+);', css), ['14px'])
        vuexy = _read('wujia_portal_layout', 'static/assets/css/components.css')
        self.assertRegex(vuexy, r'html\s*\{[^}]*font-size\s*:\s*14px')

    def test_header_doc_vai_tro(self):
        for path, selector, role in HEADERS:
            with self.subTest(selector=selector):
                rule = _block(_read('wujia_portal_layout', 'static/assets/css/' + path), selector)
                self.assertRegex(rule, r'font-size:\s*var\(--wj-t-%s-fs\)\s*!important' % role)
                self.assertRegex(rule, r'line-height:\s*var\(--wj-t-%s-lh\)' % role)
        root = _block(_css('_variables.css'), ':root')
        self.assertRegex(root, r'--wujia-m-sechead-fs\s*:\s*var\(--wj-t-section-fs\)')

    def test_class_vai_tro(self):
        css = _css('_components.css')
        for role in SCALE:
            with self.subTest(role=role):
                self.assertRegex(_block(css, '.wj-t-%s' % role), r'var\(--wj-t-%s-fs\)' % role)

    def _audit(self):
        if not (os.path.isfile(AUDIT) and os.path.isfile(BASELINE)):
            self.skipTest('thiếu scripts/qa hoặc baseline (máy chủ không có repo đầy đủ)')
        spec = importlib.util.spec_from_file_location('wj_type_audit', AUDIT)
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)
        return audit

    def test_ts1_component_doc_vai_tro(self):
        """TS1: chữ trong hai file component dùng chung chỉ đọc vai trò (icon + chấm đếm chờ TS6)."""
        audit = self._audit()
        for name in ('_components.css', '_pc_components.css'):
            css = _css(name)
            for sel, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
                sel = ' '.join(sel.split())
                if TS1_EXEMPT.search(sel) or audit.ICON.search(sel) or audit.COUNT.search(sel):
                    continue
                for value in re.findall(r'font-size\s*:\s*([^;}]+)', body):
                    with self.subTest(file=name, selector=sel):
                        self.assertIn('var(--', value)
        for path, selector in BUTTONS:
            with self.subTest(selector=selector):
                rule = _block(_read('wujia_portal_layout', 'static/assets/css/' + path), selector)
                self.assertRegex(rule, r'font-size:\s*var\(--wj-t-button-fs\)')

    def test_ts2_khung_doc_vai_tro(self):
        """TS2: đăng nhập + tài khoản PC + sidebar chỉ đọc vai trò; token header là alias của thang."""
        audit = self._audit()
        for name in ('_auth.css', '_pc_account.css', '_sidebar.css'):
            for sel, body in re.findall(r'([^{}]+)\{([^{}]*)\}', _css(name)):
                sel = ' '.join(sel.split())
                if audit.ICON.search(sel) or audit.COUNT.search(sel):
                    continue
                for value in re.findall(r'font-(?:size|weight)\s*:\s*([^;}]+)', body):
                    with self.subTest(file=name, selector=sel):
                        self.assertIn('var(--', value)
        root = _block(_css('_variables.css'), ':root')
        for token, role in (('menu-text-size', 'value-fs'), ('menu-text-lh', 'value-lh'),
                            ('navbar-pill-font', 'value-fs'), ('navbar-pill-label-size', 'label-fs')):
            with self.subTest(token=token):
                self.assertRegex(root, r'--wujia-%s:\s*var\(--wj-t-%s\)' % (token, role))

    def test_chan_tang_font_size_go_cung(self):
        """TS1–TS6 chỉ được giảm: mỗi file không nhiều chữ/icon/chấm đếm gõ cứng hơn baseline."""
        audit = self._audit()
        with open(BASELINE, encoding='utf-8') as fh:
            base = json.load(fh)
        for rel, counts in audit.count_css(REPO).items():
            for kind in ('text', 'icon', 'count'):
                with self.subTest(file=rel, kind=kind):
                    self.assertLessEqual(counts.get(kind, 0), base.get(rel, {}).get(kind, 0))
