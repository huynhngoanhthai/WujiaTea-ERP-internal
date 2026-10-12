"""Sprint 30 — gỡ view template cũ TRƯỚC khi load data mới.

product.product form kế thừa product.template form (mode primary) → view cũ
add field is_public_website vào template form sẽ lọt vào combined arch của
view variant mới và fail validation (field đã gỡ). Orphan cleanup của Odoo
chạy CUỐI upgrade — quá muộn, phải xoá ở pre-migrate.
"""


def migrate(cr, version):
    cr.execute("""
        DELETE FROM ir_ui_view
        WHERE id IN (SELECT res_id FROM ir_model_data
                     WHERE module = 'wujia_sale'
                       AND model = 'ir.ui.view'
                       AND name IN ('view_product_template_form_wujia',
                                    'view_product_template_tree_wujia',
                                    'product_template_search_wujia'))
    """)
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'wujia_sale'
          AND model = 'ir.ui.view'
          AND name IN ('view_product_template_form_wujia',
                       'view_product_template_tree_wujia',
                       'product_template_search_wujia')
    """)
