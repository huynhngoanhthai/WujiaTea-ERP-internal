"""Sprint 41 — backend quản lý thông báo (BA spec phần F).

Chuẩn bị schema TRƯỚC khi ORM load model mới + tạo constraint:
  - `date` → `published_date` (rename, KHÔNG drop dữ liệu — spec F §8/§9);
  - sinh `state` từ cờ `published` cũ (`published` chỉ drop ở post-migrate);
  - điền `code` duy nhất cho record cũ TRƯỚC khi unique(code) được tạo.
"""


def _has_column(cr, column):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'wujia_notification' AND column_name = %s
    """, (column,))
    return bool(cr.fetchone())


def migrate(cr, version):
    if not _has_column(cr, 'published_date'):
        cr.execute('ALTER TABLE wujia_notification RENAME COLUMN date TO published_date')

    cr.execute('ALTER TABLE wujia_notification ADD COLUMN IF NOT EXISTS state varchar')
    cr.execute("""
        UPDATE wujia_notification
        SET state = CASE WHEN published IS TRUE THEN 'published' ELSE 'draft' END
        WHERE state IS NULL
    """)

    cr.execute('ALTER TABLE wujia_notification ADD COLUMN IF NOT EXISTS portal_visible boolean')
    cr.execute('UPDATE wujia_notification SET portal_visible = TRUE WHERE portal_visible IS NULL')

    cr.execute('ALTER TABLE wujia_notification ADD COLUMN IF NOT EXISTS active boolean')
    cr.execute('UPDATE wujia_notification SET active = TRUE WHERE active IS NULL')

    # ANN/<năm phát hành>/<số thứ tự 4 chữ số> — post-migrate đẩy ir.sequence qua mốc này.
    cr.execute('ALTER TABLE wujia_notification ADD COLUMN IF NOT EXISTS code varchar')
    cr.execute("""
        UPDATE wujia_notification n SET code = s.new_code
        FROM (
            SELECT id,
                   'ANN/' || to_char(COALESCE(published_date, now()), 'YYYY') || '/'
                   || lpad((row_number() OVER (ORDER BY id))::text, 4, '0') AS new_code
            FROM wujia_notification WHERE code IS NULL
        ) s
        WHERE n.id = s.id
    """)

    cr.execute('ALTER TABLE wujia_notification ADD COLUMN IF NOT EXISTS published_by_id integer')
    cr.execute("""
        UPDATE wujia_notification
        SET published_by_id = (SELECT id FROM res_users WHERE login = 'admin' LIMIT 1)
        WHERE state = 'published' AND published_by_id IS NULL
    """)
