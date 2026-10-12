"""Sprint K1 — dọn metadata orphan sau khi bỏ error.type / request.line."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Seed error_type_* (noupdate) trỏ vào bảng đã drop → xoá pointer dangling.
    cr.execute(
        "DELETE FROM ir_model_data "
        "WHERE module='wujia_portal_return' AND name LIKE 'error_type_%'")

    # ir.model của model đã bỏ (_process_end thường dọn, đây là belt-and-suspenders).
    cr.execute(
        "DELETE FROM ir_model "
        "WHERE model IN ('wujia.return.error.type', 'wujia.return.request.line')")
    cr.execute(
        "DELETE FROM ir_model_data WHERE model='ir.model' "
        "AND name IN ('model_wujia_return_error_type', 'model_wujia_return_request_line')")

    # Sequence prefix WJ-RR/ -> RTN/ (data XML noupdate=1 nên không tự update DB cũ).
    cr.execute(
        "UPDATE ir_sequence SET prefix='RTN/%(y)s/' "
        "WHERE code='wujia.return.request' AND prefix='WJ-RR/%(y)s/'")

    _logger.info("K1 post-migrate: cleaned obsolete return metadata + RTN prefix")
