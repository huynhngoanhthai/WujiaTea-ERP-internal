"""Sprint 32 — align priority keys sang BA (normal/important/urgent) TRƯỚC khi load
selection mới; drop unique(notification,user) cũ để chuyển sang unique kèm franchise."""


def migrate(cr, version):
    # low → normal, high → important (urgent/normal giữ nguyên).
    cr.execute("UPDATE wujia_notification SET priority = 'normal' WHERE priority = 'low'")
    cr.execute("UPDATE wujia_notification SET priority = 'important' WHERE priority = 'high'")

    # Bỏ unique cũ (notification_id, user_id) — read giờ theo cả cửa hàng.
    cr.execute("""
        ALTER TABLE wujia_notification_read
        DROP CONSTRAINT IF EXISTS wujia_notification_read_uniq_noti_user
    """)
