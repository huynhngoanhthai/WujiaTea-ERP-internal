"""wjToast — thẻ báo kết quả dùng chung (thay các toast viết tay từng màn).

Khoá hợp đồng của khung: script được nạp, dáng chỉ dùng token, thẻ nổi trên modal, chữ đưa vào
bằng `textContent`. Màu chữ/nền của thẻ đã nằm trong lưới AA của `test_i13_contrast.py`
(`--wujia-text-primary` trên `--wujia-bg-card`; chữ trắng trên `--wujia-success-fill`/`--wujia-danger-fill`).
Phép quét "không màn nào tự dựng toast" ở `wujia_portal_base/tests/test_scan_toast.py`.
"""
import os
import re

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

ROOT = os.path.join(os.path.dirname(__file__), '..')


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install', 'wujia_toast')
class TestToastContract(TransactionCase):

    def test_script_loaded_after_wj_msg(self):
        assets = _read('views', 'assets.xml')
        self.assertLess(assets.index('/js/wj_msg.js'), assets.index('/js/wj_toast.js'))

    def test_style_uses_tokens_only(self):
        css = _read('static', 'assets', 'css', '_components.css')
        block = css[css.index('===== Toast (wjToast)'):]
        self.assertNotRegex(block, r'#[0-9A-Fa-f]{3,8}\b')
        for token in ('--wujia-toast-z', '--wujia-toast-shadow', '--wujia-bg-card',
                      '--wujia-text-primary', '--wujia-success-fill', '--wujia-danger-fill'):
            self.assertIn('var(%s)' % token, block)
        # Mobile: thẻ chạy hết bề ngang, không còn ghim góc phải.
        mobile = block[block.index('@media (max-width: 991.98px)'):]
        self.assertRegex(mobile, r'\.wj-toast-host\s*\{[^}]*left:[^}]*right:[^}]*width:\s*auto')

    def test_toast_floats_above_modal(self):
        tokens = dict(re.findall(r'(--[\w-]+)\s*:\s*([^;]+);', _read('static', 'assets', 'css', '_variables.css')))
        modal_z = int(re.search(r'\.wj-pc-modal__backdrop\s*\{[^}]*z-index:\s*(\d+)',
                                _read('static', 'assets', 'css', '_pc_components.css')).group(1))
        self.assertGreater(int(tokens['--wujia-toast-z']), modal_z)

    def test_text_is_never_parsed_as_html(self):
        js = _read('static', 'assets', 'js', 'wj_toast.js')
        self.assertIn('label.textContent = text', js)
        self.assertNotIn('innerHTML', js)
        # Vị trí bám đáy thanh trên của CẢ hai kênh.
        self.assertIn('.wujia-mheader, .wujia-navbar', js)
