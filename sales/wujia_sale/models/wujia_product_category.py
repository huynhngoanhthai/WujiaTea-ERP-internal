from odoo import fields, models


class WujiaProductCategory(models.Model):
    """Danh mục sản phẩm portal — thay product.public.category (website_sale)
    để không kéo website stack vào hệ thống. BA cập nhật sheet Model Field."""
    _name = 'wujia.product.category'
    _description = 'Wujia Portal Product Category'
    _order = 'sequence, name'

    name = fields.Char(string='Category name', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    product_ids = fields.One2many('product.product', 'public_categ_id', string='Product')
