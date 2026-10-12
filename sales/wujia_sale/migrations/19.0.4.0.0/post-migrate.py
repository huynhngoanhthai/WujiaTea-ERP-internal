"""Sprint 30 — move portal product fields template → variant (BA sheet mục H + L).

Chạy SAU khi ORM tạo cột mới trên product_product; cột cũ trên product_template
vẫn còn trong DB (Odoo không tự drop cột của field đã gỡ khỏi model).
Mọi variant kế thừa flag/min/max của template (data hiện tại chủ yếu 1 variant).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'product_template' AND column_name = 'is_public_website'
    """)
    if cr.fetchone():
        cr.execute("""
            UPDATE product_product pp
            SET is_public_portal = COALESCE(pt.is_public_website, FALSE),
                min_qty = COALESCE(pt.min_qty, 0),
                max_qty = COALESCE(pt.max_qty, 0)
            FROM product_template pt
            WHERE pp.product_tmpl_id = pt.id
        """)
        _logger.info("wujia_sale 19.0.4.0.0: copied portal fields to %s variants", cr.rowcount)
        cr.execute("ALTER TABLE product_template DROP COLUMN IF EXISTS is_public_website")
        cr.execute("ALTER TABLE product_template DROP COLUMN IF EXISTS min_qty")
        cr.execute("ALTER TABLE product_template DROP COLUMN IF EXISTS max_qty")

    # SP public mà min_qty <= 0 → step = 0 không dùng được (BA: public bắt buộc min > 0).
    cr.execute("""
        UPDATE product_product
        SET min_qty = 1
        WHERE is_public_portal = TRUE AND COALESCE(min_qty, 0) <= 0
        RETURNING id
    """)
    fixed = [r[0] for r in cr.fetchall()]
    if fixed:
        _logger.warning(
            "wujia_sale 19.0.4.0.0: %s public products had min_qty<=0, set to 1: %s",
            len(fixed), fixed,
        )

    # Rules noupdate=1 → -u không tự apply: đổi domain rule product, gỡ rule template cũ.
    cr.execute("""
        UPDATE ir_rule SET domain_force = %s
        WHERE id = (SELECT res_id FROM ir_model_data
                    WHERE module = 'wujia_sale' AND name = 'rule_product_product_portal_public')
    """, ("[('is_public_portal', '=', True)]",))
    cr.execute("""
        DELETE FROM ir_rule
        WHERE id = (SELECT res_id FROM ir_model_data
                    WHERE module = 'wujia_sale' AND name = 'rule_product_template_portal_public')
    """)
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'wujia_sale' AND name = 'rule_product_template_portal_public'
    """)
