"""J-V7 — seed loại thông báo (``noupdate``) đổi câu gốc VN → EN cho DB đã cài.

DB cũ lưu câu VN ở khoá ``en_US`` (câu gốc trong XML là tiếng Việt). ``noupdate`` ⇒ ``-u`` không ghi lại,
nên migration 19.0.2.0.0 gọi ``notification_types_source_to_en``. File này giữ nguyên câu VN cũ làm dữ liệu
đối chiếu (``scripts/qa/vn_hardcode_scan.py`` DATA_FILES).
"""

# xmlid → (câu VN cũ, câu gốc EN mới) của field ``name`` — khớp data/notification_type_data.xml.
NOTIFICATION_TYPE_SEED = {
    'ntype_urgent': ('Khẩn cấp', 'Emergency'),
    'ntype_general': ('Thông báo chung', 'General notice'),
    'ntype_promo': ('Khuyến mãi', 'Promotion'),
    'ntype_system': ('Hệ thống', 'System'),
    'ntype_other': ('Khác', 'Other'),
}


def notification_types_source_to_en(cr, module='wujia_notification'):
    """Bản ghi seed mà ``en_US`` còn ĐÚNG câu VN cũ (HQ chưa sửa tay) ⇒ ``en_US`` = EN; ``vi_VN`` = câu VN cũ
    nếu chưa có khoá ``vi_VN`` (có rồi thì giữ). Bản ghi đã sửa tay giữ nguyên. Trả số bản ghi đã đổi."""
    changed = 0
    for xmlid, (vn, en) in NOTIFICATION_TYPE_SEED.items():
        cr.execute(
            "SELECT res_id FROM ir_model_data WHERE module = %s AND name = %s AND model = %s",
            (module, xmlid, 'wujia.notification.type'))
        row = cr.fetchone()
        if not row:
            continue
        cr.execute(
            """UPDATE wujia_notification_type
                  SET name = name || jsonb_build_object('en_US', %(en)s::text)
                              || CASE WHEN name ? 'vi_VN' THEN '{}'::jsonb
                                      ELSE jsonb_build_object('vi_VN', %(vn)s::text) END
                WHERE id = %(id)s AND name ->> 'en_US' = %(vn)s""",
            {'en': en, 'vn': vn, 'id': row[0]})
        changed += cr.rowcount
    return changed
