"""target_mode cho dữ liệu cũ — thông báo đang có tick cửa hàng thì giữ đúng phạm vi đó.

Field mới `target_mode` có default 'all', Odoo điền 'all' cho mọi dòng cũ. Nhưng thông báo
nào đã có franchise_ids (tick tay từ Sprint 32) mà để 'all' thì constraint _check_target sẽ
báo lỗi và phạm vi gửi cũng bị hiểu sai → chuyển sang 'manual', giữ nguyên danh sách đã tick.
"""


def migrate(cr, version):
    cr.execute("""
        UPDATE wujia_notification
           SET target_mode = 'manual'
         WHERE id IN (SELECT DISTINCT notification_id FROM wujia_notification_franchise_rel)
    """)
