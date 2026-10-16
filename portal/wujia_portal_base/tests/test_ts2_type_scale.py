"""TS2: chữ ở Home + chọn cửa hàng chỉ đọc vai trò `--wj-t-*` (icon chờ TS6)."""
import re

from odoo.tests import TransactionCase, tagged

from .css_probe import _mod_css, _strip_comments, src

ICON = re.compile(r'(\s|>)i$|icon|-tile\b|chev')


@tagged('post_install', '-at_install', 'wujia_ts2_type_scale')
class TestTs2TypeScale(TransactionCase):

    def _assert_roles(self, label, css):
        for sel, body in re.findall(r'([^{}]+)\{([^{}]*)\}', _strip_comments(css)):
            sel = ' '.join(sel.split())
            if ICON.search(sel):
                continue
            for value in re.findall(r'font-(?:size|weight)\s*:\s*([^;}]+)', body):
                with self.subTest(file=label, selector=sel):
                    self.assertIn('var(--', value)

    def test_css_doc_vai_tro(self):
        for name in ('portal_dashboard.css', 'store_picker.css'):
            self._assert_roles(name, _mod_css('wujia_portal_base', name))

    def test_modal_chon_cua_hang_doc_vai_tro(self):
        with open(src('wujia_portal_base', 'views', 'store_picker_modal.xml'), encoding='utf-8') as fh:
            xml = fh.read()
        style = re.search(r'<style[^>]*>(.*?)</style>', xml, re.S).group(1)
        self._assert_roles('store_picker_modal.xml', style)

    def test_kpi_home_mot_co(self):
        rule = re.search(r'\.wujia-kpi-value\s*\{([^}]*)\}', _mod_css('wujia_portal_base', 'portal_dashboard.css')).group(1)
        self.assertIn('var(--wj-t-kpi-fs)', rule)
