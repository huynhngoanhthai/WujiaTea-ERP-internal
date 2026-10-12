"""Sprint 32 — backfill read tracking sau khi thêm cột franchise_id + last_open_date.

Best-effort: gán franchise_id cho read line legacy nếu user chỉ thuộc đúng 1 cửa hàng
(else để NULL — read cũ sẽ được tạo lại per-store khi user mở lại). last_open_date = read_date."""


def migrate(cr, version):
    # last_open_date chưa có → coi lần đọc đầu là lần mở gần nhất.
    cr.execute("""
        UPDATE wujia_notification_read
        SET last_open_date = read_date
        WHERE last_open_date IS NULL
    """)

    # Gán cửa hàng cho read line legacy khi user thuộc duy nhất 1 cửa hàng.
    cr.execute("""
        UPDATE wujia_notification_read r
        SET franchise_id = m.franchise_id
        FROM (
            SELECT user_id, MIN(franchise_id) AS franchise_id
            FROM wujia_franchise_member
            WHERE user_id IS NOT NULL AND franchise_id IS NOT NULL
            GROUP BY user_id
            HAVING COUNT(DISTINCT franchise_id) = 1
        ) m
        WHERE r.franchise_id IS NULL AND r.user_id = m.user_id
    """)
