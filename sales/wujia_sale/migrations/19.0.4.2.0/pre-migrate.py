"""WJ-PROD-001 — `product.product.description_ecommerce` → `wujia_packaging`.

Tên cũ trùng field Html dịch được của `website_sale` trên `product.template`. Ở
database nào có cài app Thương mại điện tử, cột `product_product.description_ecommerce`
biến thành jsonb trong khi ORM vẫn ghi chuỗi thường ⇒ lưu Quy cách nổ DatatypeMismatch.

Chạy được ở cả ba trạng thái: chưa có cột, cột varchar (local), cột jsonb (UAT).
"""


def _column_type(cr, column):
    cr.execute("""
        SELECT data_type FROM information_schema.columns
        WHERE table_name = 'product_product' AND column_name = %s
    """, (column,))
    row = cr.fetchone()
    return row[0] if row else None


def migrate(cr, version):
    if _column_type(cr, 'wujia_packaging'):
        return

    old_type = _column_type(cr, 'description_ecommerce')
    if not old_type:
        return

    if old_type == 'jsonb':
        # Giữ lại phần chữ: ưu tiên bản en_US, không có thì lấy giá trị dịch đầu tiên.
        cr.execute('ALTER TABLE product_product ADD COLUMN wujia_packaging varchar')
        cr.execute("""
            UPDATE product_product
            SET wujia_packaging = COALESCE(
                description_ecommerce ->> 'en_US',
                (SELECT value FROM jsonb_each_text(description_ecommerce) LIMIT 1)
            )
            WHERE description_ecommerce IS NOT NULL
        """)
        cr.execute('ALTER TABLE product_product DROP COLUMN description_ecommerce')
    else:
        cr.execute('ALTER TABLE product_product RENAME COLUMN description_ecommerce TO wujia_packaging')

    # Dọn metadata tên cũ, nếu không Odoo giữ lại một field mồ côi của product.product.
    cr.execute("""
        SELECT id FROM ir_model_fields
        WHERE model = 'product.product' AND name = 'description_ecommerce'
    """)
    field_ids = [r[0] for r in cr.fetchall()]
    if field_ids:
        cr.execute("""
            DELETE FROM ir_model_data
            WHERE model = 'ir.model.fields' AND res_id IN %s
        """, (tuple(field_ids),))
        cr.execute('DELETE FROM ir_model_fields WHERE id IN %s', (tuple(field_ids),))
