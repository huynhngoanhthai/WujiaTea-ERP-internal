from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    # Bản đã cài trước J-B2: tên thương hiệu trống ⇒ portal hiện tên công ty ("My Company" trên UAT).
    api.Environment(cr, SUPERUSER_ID, {})['res.company']._wj_fill_default_brand_name()
