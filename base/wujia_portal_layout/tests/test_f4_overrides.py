# -*- coding: utf-8 -*-
"""F4 — biến thể dáng của component chung sống ở khung.

Phần kiểm call site của 12 module nghiệp vụ đã dời sang
`wujia_portal_base/tests/test_scan_f4_overrides.py` ở F5b.
"""
import os
import re

from odoo.tests import TransactionCase, tagged

CSS_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'assets', 'css')


def _read(name):
    with open(os.path.join(CSS_DIR, name), encoding='utf-8') as fh:
        return fh.read()


def _nocomment(css):
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


@tagged('post_install', '-at_install', 'wujia_f4')
class TestF4Variants(TransactionCase):

    def test_eyebrow_variant_beats_compact_title(self):
        # Rule cỡ chữ compact là (0,3,0)!important ⇒ biến thể phải (0,4,0)!important.
        comp = _nocomment(_read('_components.css'))
        for plat in ('any', 'm', 'pc'):
            with self.subTest(plat=plat):
                self.assertIn('.wj-card-header.wj-card-header--%s.wj-card-header--eyebrow '
                              '.wj-card-header__title' % plat, comp)
        self.assertRegex(comp, r'--eyebrow \.wj-card-header__title\s*\{[^}]*font-size:\s*11px\s*!important')


@tagged('post_install', '-at_install', 'wujia_f4')
class TestF4InteractionList(TransactionCase):

    def _lists(self):
        css = _nocomment(_read('_interaction.css'))
        return css, re.findall(r':is\(([^{]*?)\)\s*:not\(\.is-disabled\)', css)

    def test_state_lists_name_components_not_screens(self):
        css, lists = self._lists()
        self.assertEqual(len(lists), 3, 'transition + hover + active')
        for body in lists:
            self.assertIn('.wj-state-surface', body)
            self.assertIn('a.wj-data-item', body)
            self.assertNotRegex(body, r'\.wujia-m(?!account)[a-z]+-|\.wj-(debt|exam|pc-cart|pc-dlv|inspection)')
        # Nhóm Khảo sát tách rule riêng — không kéo đặc hiệu của cả danh sách.
        self.assertEqual(css.count('.wj-inspection-pc .wj-pc-page-btn:not(.is-active):not(.is-disabled)'), 3)
        self.assertNotIn(':is(.article-content', css)
        self.assertIn('.wj-richtext a', css)

    def test_no_blanket_tag_rule_for_table_headers(self):
        """FR-B(a): `table th{16px!important}` từng thắng mọi component ⇒ 14/17 bảng PC sai cỡ.
        Đã gỡ; cấm thêm lại luật quét theo THẺ (không class) cho đầu bảng."""
        for name in ('style.css', '_components.css', '_pc_components.css', '_wujia_theme.css'):
            with self.subTest(file=name):
                self.assertNotRegex(_nocomment(_read(name)), r'(?m)^\s*table\s+th\s*\{')
