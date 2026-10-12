"""E1 / UI-MOB-HOME-004 — 4 chỉ số Home mobile: một cỡ chữ, số tiền không bị bẻ dòng.

Ô KPI rộng ~64px ở 360px (328 content − hero pad 32, chia 4, trừ padding tile). BA khoá
hai quan hệ: cả 4 giá trị dùng CHUNG một khai báo cỡ chữ (cấm giảm riêng ô Công nợ), và
số tiền phải trọn một dòng. `overflow-wrap: anywhere` của C7 chính là thứ cho phép bẻ
`-72449 $` thành `-7244` / `9 $`; chuỗi dài nay đã rút gọn ở nguồn (`_short_amount`).

Call site của màn Home đã dời sang `wujia_portal_base/tests/test_home_kpi_e1.py` ở F5b.
"""

import os
import re

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'wujia_home_kpi_e1')
class TestHomeKpiValueStaysOnOneLine(TransactionCase):

    CSS = '_components.css'

    def _read(self, name):
        path = os.path.join(os.path.dirname(__file__), '..', 'static', 'assets', 'css', name)
        with open(path, encoding='utf-8') as fh:
            return fh.read()

    def _rule(self, css, selector):
        m = re.search(re.escape(selector) + r'\s*\{([^}]*)\}', css)
        self.assertTrue(m, 'không tìm thấy rule %s' % selector)
        return m.group(1)

    def test_value_may_not_break_inside_a_number(self):
        body = self._rule(self._read(self.CSS), '.wujia-mhome-kpi-value')
        self.assertRegex(body, r'white-space:\s*nowrap')
        self.assertRegex(body, r'font-variant-numeric:\s*tabular-nums')
        # `anywhere`/`break-all`/`break-word` đều cho phép bẻ giữa chữ số.
        self.assertNotRegex(body, r'(overflow-wrap|word-break|word-wrap)\s*:')

    def test_tile_keeps_min_width_zero_so_nowrap_cannot_widen_the_column(self):
        # Track `1fr` lấy min-content làm cỡ tối thiểu; chỉ `min-width: 0` trên ô con mới
        # giữ 4 cột đều nhau khi giá trị dài hơn cột.
        self.assertRegex(self._rule(self._read(self.CSS), '.wujia-mhome-kpi'),
                         r'min-width:\s*0')

    def test_all_four_values_share_one_font_size_owner(self):
        css = self._read(self.CSS)
        owners = [s for s in re.findall(r'([^{}]+)\{([^}]*)\}', css)
                  if 'wujia-mhome-kpi-value' in s[0] and re.search(r'font-size\s*:', s[1])]
        self.assertEqual(len(owners), 2, 'chỉ được 1 khai báo gốc + 1 breakpoint ≤380px')
        for selector, _body in owners:
            self.assertEqual(selector.strip().rstrip(), '.wujia-mhome-kpi-value',
                             'không được nhắm riêng ô nào (BA cấm giảm riêng Công nợ)')
