"""C1 / WJ-FRANCHISE-001 + WJ-DEBT-006 — điền cửa hàng cho hoá đơn CŨ đang bỏ trống.

Ba nguồn theo thứ tự tin cậy: hoá đơn gốc của giấy báo có (reversed_entry_id) → đơn bán
nguồn → partner map duy nhất. Chỉ chạm dòng `franchise_id IS NULL`.
Xong thì tính lại 2 aggregate công nợ portal để badge không lệch.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE account_move cn
           SET franchise_id = src.franchise_id
          FROM account_move src
         WHERE src.id = cn.reversed_entry_id
           AND cn.franchise_id IS NULL
           AND src.franchise_id IS NOT NULL
    """)
    _logger.info('C1: set franchise from the origin invoice on %s old credit notes', cr.rowcount)

    cr.execute("""
        UPDATE account_move m
           SET franchise_id = s.franchise_id
          FROM sale_order s
         WHERE s.name = m.invoice_origin
           AND m.franchise_id IS NULL
           AND s.franchise_id IS NOT NULL
    """)
    _logger.info('C1: set franchise from the sale order on %s old invoices', cr.rowcount)

    cr.execute("""
        WITH m AS (
            SELECT partner_id, min(id) AS fid, count(*) AS n
            FROM wujia_franchise_management
            WHERE partner_id IS NOT NULL AND active AND status NOT IN ('closed', 'expired')
            GROUP BY partner_id
        ), uniq AS (SELECT partner_id, fid FROM m WHERE n = 1)
        UPDATE account_move am
           SET franchise_id = u.fid
          FROM uniq u, res_partner p
         WHERE p.id = am.partner_id
           AND u.partner_id IN (p.id, p.commercial_partner_id)
           AND am.franchise_id IS NULL
           AND am.move_type IN ('out_invoice', 'out_refund')
    """)
    _logger.info('C1: set franchise from the partner on %s old invoices', cr.rowcount)

    # Badge công nợ portal đọc 2 field store → tính lại sau khi dữ liệu đổi.
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['wujia.franchise.management']._cron_recompute_portal_debt()
