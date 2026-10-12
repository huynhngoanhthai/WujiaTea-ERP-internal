# -*- coding: utf-8 -*-
"""WJ-ORD-MOB-SPACING-001 — nhịp đầu trang Đặt hàng mobile: search → chip 12, chip →
"Danh sách sản phẩm" 8 (đo UAT trước sửa: 23 và 14).

BA: chỉ đặt nhịp ở wrapper trang, KHÔNG ghi đè FilterChip/FilterBar chung; giữ input 44,
chip và vùng bấm. Số đo trình duyệt ở `scripts/qa/wj_density.py` (khóa `order`).
"""
import os
import re

from odoo.tests import TransactionCase, tagged

CSS = os.path.join(os.path.dirname(__file__), '..', 'static', 'src', 'css', 'portal_order.css')


def _rules():
    with open(CSS, encoding='utf-8') as fh:
        css = re.sub(r'/\*.*?\*/', '', fh.read(), flags=re.S)
    return [(m.group(1).strip(), m.group(2)) for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', css)]


@tagged('post_install', '-at_install', 'wujia_order_spacing_g1')
class TestOrderMobileSpacing(TransactionCase):

    def test_search_den_chip_12(self):
        body = dict(_rules()).get('.wujia-morder > .wujia-morder-search')
        self.assertIsNotNone(body)
        self.assertIn('margin-bottom: calc(12px - var(--wujia-mshell-content-gap))', body)

    def test_chip_den_danh_sach_8(self):
        body = dict(_rules()).get('.wujia-morder #wj-ord-mbody > .wj-section-header--m')
        self.assertIsNotNone(body)
        self.assertRegex(body, r'margin-top:\s*0\s*;')

    def test_khong_ghi_de_filter_chung(self):
        """Rule nào chạm lớp FilterChip/FilterBar chung trong file trang là phá phạm vi 144."""
        hits = [s for s, _b in _rules() if re.search(r'\.wj-filter-(chip|chips|card|bar)\b', s)]
        self.assertFalse(hits, hits)
