"""Sprint 45 — gỡ hẳn 2 model legacy dormant (schedule/result).

Kết quả thi giờ nhập trên `wujia.exam.registration.line`; lịch thi thay bằng
course + session (Sprint M). 2 bảng cũ chỉ còn để portal demo bind → drop.
Dữ liệu là demo/throwaway (registration không còn gắn schedule từ 19.0.3.0.0),
an toàn drop. ir.model / ir.model.fields orphan để ORM tự dọn khi update.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        DROP TABLE IF EXISTS wujia_exam_result CASCADE;
        DROP TABLE IF EXISTS wujia_exam_schedule_franchise_rel CASCADE;
        DROP TABLE IF EXISTS wujia_exam_schedule CASCADE;
    """)
    _logger.info(
        "wujia_portal_exam: dropped legacy tables "
        "wujia_exam_result / wujia_exam_schedule(+rel)")

    # Phiếu mồ côi từ thời schedule (session_id NULL) — không dùng được, chặn
    # not-null constraint session_id. Xóa cả line con rồi tới phiếu.
    cr.execute("""
        DELETE FROM wujia_exam_registration_line
         WHERE registration_id IN (
             SELECT id FROM wujia_exam_registration WHERE session_id IS NULL);
        DELETE FROM wujia_exam_registration WHERE session_id IS NULL;
    """)
    if cr.rowcount:
        _logger.info(
            "wujia_portal_exam: removed %s orphan registration(s) "
            "with null session_id", cr.rowcount)
