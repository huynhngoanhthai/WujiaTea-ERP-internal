"""WJ-NOTI-001 — dấu đã đọc theo phạm vi mới.

Toàn hệ (không có cửa hàng nhận) ⇒ gộp mọi dấu của (thông báo, user) thành 1 dòng franchise NULL
(read_date sớm nhất, last_open_date muộn nhất). Chỉ định ⇒ chỉ giữ dấu mang đúng cửa hàng nhận;
dấu thiếu cửa hàng / sai cửa hàng bị xoá (không đoán phạm vi — chủ dự án chốt 09/10/2026).
"""
import logging

_logger = logging.getLogger(__name__)

BROADCAST = """
    NOT EXISTS (SELECT 1 FROM wujia_notification_franchise_rel fr
                 WHERE fr.notification_id = r.notification_id)
"""
OUT_OF_SCOPE = """
    NOT ({bc}) AND (r.franchise_id IS NULL OR NOT EXISTS (
        SELECT 1 FROM wujia_notification_franchise_rel fr
         WHERE fr.notification_id = r.notification_id AND fr.franchise_id = r.franchise_id))
""".format(bc=BROADCAST)


def _count(cr, where):
    cr.execute("SELECT count(*) FROM wujia_notification_read r WHERE " + where)
    return cr.fetchone()[0]


def migrate(cr, version):
    cr.execute("SELECT count(DISTINCT (r.notification_id, r.user_id)) FROM wujia_notification_read r WHERE "
               + BROADCAST)
    pairs = cr.fetchone()[0]
    total_before = _count(cr, "TRUE")

    # 1. Toàn hệ: dòng NULL đã có lấy mốc sớm/muộn nhất của mọi dòng cùng cặp; chưa có thì tạo.
    cr.execute("""
        WITH agg AS (
            SELECT r.notification_id, r.user_id,
                   min(r.read_date) AS read_date, max(r.last_open_date) AS last_open_date
              FROM wujia_notification_read r WHERE {bc}
             GROUP BY r.notification_id, r.user_id
        )
        UPDATE wujia_notification_read t
           SET read_date = agg.read_date, last_open_date = agg.last_open_date
          FROM agg
         WHERE t.notification_id = agg.notification_id AND t.user_id = agg.user_id
           AND t.franchise_id IS NULL
    """.format(bc=BROADCAST))
    cr.execute("""
        INSERT INTO wujia_notification_read
               (notification_id, user_id, franchise_id, read_date, last_open_date,
                create_uid, create_date, write_uid, write_date)
        SELECT r.notification_id, r.user_id, NULL, min(r.read_date), max(r.last_open_date),
               1, now() AT TIME ZONE 'UTC', 1, now() AT TIME ZONE 'UTC'
          FROM wujia_notification_read r
         WHERE {bc}
         GROUP BY r.notification_id, r.user_id
        HAVING bool_and(r.franchise_id IS NOT NULL)
    """.format(bc=BROADCAST))
    merged = cr.rowcount
    cr.execute("DELETE FROM wujia_notification_read r WHERE r.franchise_id IS NOT NULL AND " + BROADCAST)
    broadcast_dropped = cr.rowcount
    after_pairs = _count(cr, "r.franchise_id IS NULL AND " + BROADCAST)
    if after_pairs != pairs:
        raise RuntimeError("wujia_notification: broadcast read merge %s/%s" % (after_pairs, pairs))

    # 2. Chỉ định: dấu không xác định được / sai cửa hàng nhận ⇒ xoá, ghi log từng dòng.
    cr.execute("""
        DELETE FROM wujia_notification_read r WHERE {oos}
        RETURNING r.id, r.notification_id, r.user_id, r.franchise_id
    """.format(oos=OUT_OF_SCOPE))
    dropped = cr.fetchall()
    for row in dropped:
        _logger.info("wujia_notification: drop out-of-scope read id=%s noti=%s user=%s store=%s", *row)
    if _count(cr, OUT_OF_SCOPE) or _count(cr, "r.franchise_id IS NOT NULL AND " + BROADCAST):
        raise RuntimeError("wujia_notification: out-of-scope read marks remain")

    _logger.info(
        "wujia_notification read scope: %s rows -> %s · broadcast pairs %s (new NULL %s, store rows "
        "removed %s) · targeted out-of-scope removed %s",
        total_before, _count(cr, "TRUE"), pairs, merged, broadcast_dropped, len(dropped),
    )
