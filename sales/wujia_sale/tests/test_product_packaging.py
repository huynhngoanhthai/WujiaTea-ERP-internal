"""WJ-PROD-001 — nhập/sửa/xoá Quy cách trên biến thể sản phẩm."""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'wujia_sale')
class TestProductPackaging(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env['product.product'].create({
            'name': 'Hồng Trà Đài Loan KHÔNG Đường',
            'type': 'consu',
            'public_categ_id': cls.env['wujia.product.category'].create({'name': 'Trà'}).id,
        })

    def test_write_edit_clear_packaging(self):
        self.product.write({'wujia_packaging': '500 ml'})
        self.product.invalidate_recordset()
        self.assertEqual(self.product.wujia_packaging, '500 ml')

        self.product.write({'wujia_packaging': '10kg/bao'})
        self.product.invalidate_recordset()
        self.assertEqual(self.product.wujia_packaging, '10kg/bao')

        self.product.write({'wujia_packaging': False})
        self.product.invalidate_recordset()
        self.assertFalse(self.product.wujia_packaging)

    def test_write_with_other_portal_fields(self):
        # Lưu chung với các field portal khác không được kéo theo lỗi schema.
        self.product.write({
            'wujia_packaging': '120 cái/thùng',
            'name_chinese': '台灣無糖紅茶',
            'min_qty': 5,
            'is_public_portal': True,
        })
        self.product.invalidate_recordset()
        self.assertEqual(self.product.wujia_packaging, '120 cái/thùng')
        self.assertEqual(self.product.min_qty, 5)

    def test_field_is_plain_char_not_translated(self):
        # Tên cũ trùng field dịch được của website_sale ⇒ cột jsonb, WJ-PROD-001.
        field = self.env['product.product']._fields['wujia_packaging']
        self.assertEqual(field.type, 'char')
        self.assertFalse(field.translate)
