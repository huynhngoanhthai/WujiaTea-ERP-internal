# -*- coding: utf-8 -*-
"""G1 (quét nhiều module) — người đọc chiều cao thanh dưới mobile.

UI-MOB-BOTTOMNAV-DENSITY-001 hạ thanh dưới 83 → 72 + safe area. `--wujia-mnav-height`
chỉ là phần KHÔNG tính safe area; khối cố định đặt phía trên nav (CTA dính, thanh giỏ,
sheet) mà bám biến này sẽ chồng lên nav trên máy có home-indicator (đo trước sửa: sheet
Thêm chồng 8px khi safe area 34). Ngoài khung, mọi module phải bám `--wujia-mnav-total`.
"""
import os
import re

from odoo.tests import TransactionCase, tagged

from odoo.addons.wujia_portal_base.tests.css_probe import CUSTOM, _strip_comments


def _portal_css():
    for mod in sorted(os.listdir(CUSTOM)):
        if not mod.startswith('wujia_portal_') or 'inspection' in mod or mod == 'wujia_portal_layout':
            continue
        for dirpath, _dirs, files in os.walk(os.path.join(CUSTOM, mod, 'static')):
            for f in files:
                if f.endswith('.css'):
                    path = os.path.join(dirpath, f)
                    with open(path, encoding='utf-8') as fh:
                        yield os.path.relpath(path, CUSTOM), _strip_comments(fh.read())


@tagged('post_install', '-at_install', 'wujia_mobile_density_g1')
class TestBottomNavReaders(TransactionCase):

    def test_ngoai_khung_chi_doc_mnav_total(self):
        hits = [path for path, css in _portal_css() if '--wujia-mnav-height' in css]
        self.assertFalse(hits, 'bám --wujia-mnav-height (thiếu safe area):\n  ' + '\n  '.join(hits))

    def test_khong_neo_cung_83(self):
        """Con số cũ của thanh dưới không được sống lại dưới dạng px cứng."""
        hits = []
        for path, css in _portal_css():
            for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', css):
                if re.search(r'(?<![\d.])83px', m.group(2)):
                    hits.append('%s: %s' % (path, m.group(1).strip()[:50]))
        self.assertFalse(hits, 'neo cứng 83px:\n  ' + '\n  '.join(hits))
