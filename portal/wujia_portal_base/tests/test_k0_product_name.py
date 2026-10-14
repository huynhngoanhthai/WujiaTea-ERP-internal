"""Tên sản phẩm trên portal: cửa hàng đọc tên, không đọc mã nội bộ."""
from odoo.tests import TransactionCase, tagged

from odoo.addons.wujia_portal_base.controllers.utils import portal_product_name


@tagged('post_install', '-at_install', 'wujia_portal_name')
class TestPortalProductName(TransactionCase):

    def test_bo_ma_noi_bo_giu_ten(self):
        product = self.env['product.product'].create({
            'name': 'Trà sữa matcha', 'default_code': 'TS-MAT'})
        self.assertIn('[TS-MAT]', product.display_name)
        self.assertEqual(portal_product_name(product), 'Trà sữa matcha')

    def test_giu_ten_bien_the(self):
        attr = self.env['product.attribute'].create({'name': 'Cỡ'})
        vals = self.env['product.attribute.value'].create(
            [{'name': n, 'attribute_id': attr.id} for n in ('M', 'L')])
        tmpl = self.env['product.template'].create({
            'name': 'Trân châu', 'default_code': 'TP-TC',
            'attribute_line_ids': [(0, 0, {
                'attribute_id': attr.id, 'value_ids': [(6, 0, vals.ids)]})],
        })
        variant = tmpl.product_variant_ids[0]
        variant.default_code = 'TP-TC-M'
        name = portal_product_name(variant)
        self.assertNotIn('TP-TC', name)
        self.assertIn('Trân châu', name)
        self.assertIn('M', name)

    def test_khong_co_san_pham_tra_chuoi_rong(self):
        self.assertEqual(portal_product_name(self.env['product.product']), '')
