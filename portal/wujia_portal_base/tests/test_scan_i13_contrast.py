"""I13 / WJ-PORTAL-UI-006 — quét CSS mọi module portal của mình (tầng ghép).

Token đạt AA được khoá ở `wujia_portal_layout/tests/test_i13_contrast.py`. Ở đây chặn việc
màn nào đó dùng lại màu brand / xám cũ làm MÀU CHỮ, hoặc đặt chữ trắng lên nền brand nhạt.
Nhóm Khảo sát của anh Thái nằm ngoài phạm vi.
"""
import os
import re

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

CUSTOM = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
THAI_MODULES = ('wujia_portal_inspection',)

# #28A9DF 2.68 · #168FC2 3.66 · xám cũ 2.5–3.2 trên trắng.
BAD_TEXT = re.compile(
    r'var\(--(?:wujia-primary|wj-primary|wj-pc-primary|wujia-primary-dark)\b(?![\w-])'
    r'|#(?:28A9DF|168FC2|8A939E|8A9099|9CA3AF|94A3B8|64748B|91979F|7C8088)\b', re.I)
# Nền mà chữ trắng chỉ đạt 2.5–3.7.
BAD_FILL = re.compile(
    r'var\(--(?:wujia-primary|wj-primary|wj-pc-primary|wujia-primary-dark|wujia-success|'
    r'wujia-danger|wujia-warning)\)|#(?:28A9DF|168FC2|16A34A|22C55E|EF4444|F29A1F|D97706)\b', re.I)
WHITE = re.compile(r'(?<![\w-])color\s*:\s*(?:#fff(?:fff)?|white)\b', re.I)


def _css_files():
    for mod in sorted(os.listdir(CUSTOM)):
        if not mod.startswith('wujia_portal_') or mod in THAI_MODULES:
            continue
        for root, _dirs, files in os.walk(os.path.join(CUSTOM, mod, 'static')):
            for name in files:
                if name.endswith('.css'):
                    yield os.path.relpath(os.path.join(root, name), CUSTOM)


def _blocks(css):
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', css):
        yield m.group(1).strip(), m.group(2)


@tagged('post_install', '-at_install', 'wujia_i13')
class TestNoBrandColouredText(TransactionCase):

    def _scan(self, check):
        hits = []
        for rel in _css_files():
            with open(os.path.join(CUSTOM, rel), encoding='utf-8') as fh:
                for selector, body in _blocks(fh.read()):
                    for msg in check(selector, body):
                        hits.append('%s: %s → %s' % (rel, selector[:80], msg))
        return hits

    def test_scan_covers_the_portal(self):
        files = list(_css_files())
        self.assertGreaterEqual(len(files), 15, files)
        self.assertFalse([f for f in files if f.startswith(THAI_MODULES)])

    def test_no_text_in_brand_or_old_grey(self):
        def check(_sel, body):
            for decl in re.findall(r'(?<![\w-])color\s*:\s*([^;]+)', body):
                if BAD_TEXT.search(decl):
                    yield decl.strip()
        hits = self._scan(check)
        self.assertFalse(hits, 'chữ còn dùng màu brand/xám cũ (<4.5) — dùng '
                               '--wujia-brand-text / --wujia-text-muted:\n' + '\n'.join(hits))

    def test_white_text_sits_on_dark_fill(self):
        def check(_sel, body):
            if not WHITE.search(body):
                return
            for decl in re.findall(r'(?<![\w-])background(?:-color)?\s*:\s*([^;]+)', body):
                if BAD_FILL.search(decl):
                    yield decl.strip()
        hits = self._scan(check)
        self.assertFalse(hits, 'chữ trắng trên nền sáng — dùng token *-fill:\n' + '\n'.join(hits))
