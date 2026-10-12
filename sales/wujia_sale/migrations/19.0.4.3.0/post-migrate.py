"""C1 / WJ-FRANCHISE-001 — điền cửa hàng cho đơn bán CŨ đang bỏ trống.

Chỉ chạm dòng `franchise_id IS NULL` mà partner map ĐÚNG MỘT cửa hàng còn hiệu lực —
chứng từ đã có giá trị (kể cả lệch với partner) giữ nguyên, đó là quyết định của kế toán.
Odoo không tự tính lại bản ghi cũ khi field thường thành stored compute nên phải làm tay.
"""
import logging

_logger = logging.getLogger(__name__)

UNIQUE_MAP = """
    WITH m AS (
        SELECT partner_id, min(id) AS fid, count(*) AS n
        FROM wujia_franchise_management
        WHERE partner_id IS NOT NULL AND active AND status NOT IN ('closed', 'expired')
        GROUP BY partner_id
    )
    SELECT partner_id, fid FROM m WHERE n = 1
"""


def migrate(cr, version):
    cr.execute(f"""
        WITH uniq AS ({UNIQUE_MAP})
        UPDATE sale_order s
           SET franchise_id = u.fid
          FROM uniq u, res_partner p
         WHERE p.id = s.partner_id
           AND u.partner_id IN (p.id, p.commercial_partner_id)
           AND s.franchise_id IS NULL
    """)
    _logger.info('C1: filled franchise for %s legacy sale orders', cr.rowcount)

    cr.execute("""
        UPDATE sale_order s
           SET franchise_partner_id = f.partner_id
          FROM wujia_franchise_management f
         WHERE f.id = s.franchise_id
           AND s.franchise_partner_id IS NULL
           AND f.partner_id IS NOT NULL
    """)
    _logger.info('C1: filled store partner for %s legacy sale orders', cr.rowcount)
