"""Sprint M — rework registration schema (skeleton → phiếu đa-nhân-sự).

- Drop uniq(user_id, schedule_id) (không còn 1-user-1-schedule).
- Rename user_id -> requester_user_id (giữ link người đăng ký).
- Drop schedule_id (demo data throwaway; schema mới dùng session_id).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        ALTER TABLE wujia_exam_registration
        DROP CONSTRAINT IF EXISTS wujia_exam_registration_uniq_user_schedule
    """)
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'wujia_exam_registration'
          AND column_name IN ('user_id', 'requester_user_id')
    """)
    cols = {r[0] for r in cr.fetchall()}
    if 'user_id' in cols and 'requester_user_id' not in cols:
        cr.execute("""
            ALTER TABLE wujia_exam_registration
            RENAME COLUMN user_id TO requester_user_id
        """)
        _logger.info("wujia_portal_exam: renamed registration.user_id -> requester_user_id")
    cr.execute("""
        ALTER TABLE wujia_exam_registration DROP COLUMN IF EXISTS schedule_id
    """)
