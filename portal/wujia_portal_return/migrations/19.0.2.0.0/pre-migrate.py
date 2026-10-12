"""Sprint K1 — schema migration.

Chuyển wujia.return.request từ multi-line sang single-product; rename
wujia.return.error.type → wujia.return.issue.type. Không giả định có prod data
(dev DB) nhưng vẫn phòng thủ để `-u` không crash.
"""
import logging

_logger = logging.getLogger(__name__)


def _col_exists(cr, table, col):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name=%s AND column_name=%s", (table, col))
    return bool(cr.fetchone())


def _rename_col(cr, table, old, new):
    if _col_exists(cr, table, old) and not _col_exists(cr, table, new):
        cr.execute('ALTER TABLE "%s" RENAME COLUMN "%s" TO "%s"' % (table, old, new))
        _logger.info("K1 migrate: %s.%s -> %s", table, old, new)


def migrate(cr, version):
    if not version:
        return

    # 1) Bỏ model line (multi-line -> single-product header)
    cr.execute("DROP TABLE IF EXISTS wujia_return_request_line CASCADE")

    # 2) Rename cột giữ dữ liệu tương thích
    _rename_col(cr, 'wujia_return_request', 'order_id', 'sale_order_id')
    _rename_col(cr, 'wujia_return_request', 'refuse_reason', 'reject_reason')
    _rename_col(cr, 'wujia_return_request', 'created_by_user_id', 'requester_user_id')

    # 3) Bỏ cột không còn trong spec BA
    for col in ('error_id', 'expected_delivery_date'):
        if _col_exists(cr, 'wujia_return_request', col):
            cr.execute('ALTER TABLE wujia_return_request DROP COLUMN "%s"' % col)

    # 4) Remap state cũ 'sent' -> 'submitted'
    if _col_exists(cr, 'wujia_return_request', 'state'):
        cr.execute(
            "UPDATE wujia_return_request SET state='submitted' WHERE state='sent'")

    # 5) Bỏ bảng error.type cũ (tạo lại thành issue.type fresh)
    cr.execute("DROP TABLE IF EXISTS wujia_return_error_type CASCADE")
