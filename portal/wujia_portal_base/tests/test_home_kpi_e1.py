"""E1 / UI-MOB-HOME-004 — màn Home mobile dùng đúng lớp giá trị KPI.

F5b dời khỏi `wujia_portal_layout`: màn Home thuộc `portal_base`. Phần CSS của ô KPI
vẫn ở khung (`wujia_portal_layout/tests/test_e1_home_kpi.py`).
"""
from lxml import html

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'wujia_home_kpi_e1')
class TestHomeKpiCallSite(TransactionCase):

    def test_four_tiles_still_one_row_with_the_same_value_class(self):
        arch = self.env.ref('wujia_portal_base.portal_home_page').arch_db
        root = html.fromstring('<div>%s</div>' % arch)
        row = root.xpath('.//div[@class="wujia-mhome-hero-kpis"]')
        self.assertEqual(len(row), 1)
        tiles = row[0].xpath('./*[contains(@class,"wujia-mhome-kpi")]')
        self.assertEqual(len(tiles), 4)
        for tile in tiles:
            self.assertEqual(
                len(tile.xpath('.//span[@class="wujia-mhome-kpi-value"]')), 1)
