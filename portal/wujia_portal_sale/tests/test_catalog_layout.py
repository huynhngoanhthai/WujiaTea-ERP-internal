"""RESP-MOB-ORDER-002 — card sản phẩm mobile: tên nằm riêng hàng trên của grid.

Chạy: `--test-tags wujia_catalog_layout`.

Khoá CẤU TRÚC chứ không khoá px: CSS grid `.wujia-morder-row` chỉ cho tên ăn hết
bề ngang khi 4 phần tử (thumb / tên / meta / nút giỏ) là con TRỰC TIẾP của row.
Bọc thêm một lớp là tên co lại về ~150px như lúc BA báo lỗi.
"""

from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'wujia_catalog_layout')
class TestCatalogMobileRow(TransactionCase):

    def _row(self):
        view = self.env.ref('wujia_portal_sale.portal_order_catalog_results_part')
        arch = etree.fromstring(view.arch_db)
        rows = arch.xpath("//div[@class='wujia-morder-row']")
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_row_children_are_the_four_grid_cells(self):
        classes = [c.get('class', '') for c in self._row()
                   if isinstance(c.tag, str)]   # bỏ node comment
        self.assertEqual(classes, [
            'wujia-morder-row-thumb',
            'wujia-morder-row-name',
            'wujia-morder-row-meta',
            'wujia-morder-cartctl',
        ])

    def test_price_and_spec_sit_in_the_meta_cell(self):
        row = self._row()
        meta = row.xpath("./span[@class='wujia-morder-row-meta']")[0]
        self.assertTrue(meta.xpath("./span[@class='wujia-morder-row-spec']"))
        self.assertTrue(meta.xpath("./span[@class='wujia-morder-row-price']"))
        # Giá KHÔNG được nằm chung ô với tên — đó là layout cũ gây lỗi.
        self.assertFalse(row.xpath(".//a[@class='wujia-morder-row-name']//*"))

    def test_name_is_the_product_link(self):
        name = self._row().xpath("./a[@class='wujia-morder-row-name']")[0]
        self.assertIn('/portal/order/product/', name.get('t-attf-href', ''))
