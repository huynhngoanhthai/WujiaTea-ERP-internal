"""C1 / WJ-FRANCHISE-001 — điền cửa hàng cho phiếu kho CŨ đang bỏ trống.

Ưu tiên đơn bán nguồn (SO là nguồn chân lý), sau đó mới suy từ partner giao hàng.
Chỉ chạm dòng `franchise_id IS NULL`.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE stock_picking p
           SET franchise_id = s.franchise_id
          FROM sale_order s
         WHERE s.name = p.origin
           AND p.franchise_id IS NULL
           AND s.franchise_id IS NOT NULL
    """)
    _logger.info('C1: filled franchise from sales order for %s old pickings', cr.rowcount)

    cr.execute("""
        WITH m AS (
            SELECT partner_id, min(id) AS fid, count(*) AS n
            FROM wujia_franchise_management
            WHERE partner_id IS NOT NULL AND active AND status NOT IN ('closed', 'expired')
            GROUP BY partner_id
        ), uniq AS (SELECT partner_id, fid FROM m WHERE n = 1)
        UPDATE stock_picking sp
           SET franchise_id = u.fid
          FROM uniq u, res_partner p
         WHERE p.id = sp.partner_id
           AND u.partner_id IN (p.id, p.commercial_partner_id)
           AND sp.franchise_id IS NULL
    """)
    _logger.info('C1: filled franchise from partner for %s old pickings', cr.rowcount)
