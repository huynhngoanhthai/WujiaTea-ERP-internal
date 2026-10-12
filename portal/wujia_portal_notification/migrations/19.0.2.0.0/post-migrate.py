"""Sprint 41 — dọn sau khi ORM đã load schema mới.

  - đẩy ir.sequence qua mốc `code` đã cấp ở pre-migrate (tránh trùng mã);
  - drop cờ `published` cũ (đã chuyển hết sang `state` — spec F cấm 2 field cùng nghĩa).
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    total = env['wujia.notification'].with_context(active_test=False).search_count([])
    seq = env['ir.sequence'].search([('code', '=', 'wujia.notification')], limit=1)
    if seq and seq.number_next <= total:
        seq.write({'number_next': total + 1})

    cr.execute('ALTER TABLE wujia_notification DROP COLUMN IF EXISTS published')
