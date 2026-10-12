"""J-V6 — seed loại lỗi (``noupdate``) đổi câu gốc VN → EN cho DB đã cài.

DB cũ lưu câu VN ở khoá ``en_US`` (câu gốc trong XML là tiếng Việt). ``noupdate`` ⇒ ``-u`` không ghi lại,
nên migration 19.0.2.0.0 gọi ``issue_types_source_to_en``. File này giữ nguyên câu VN cũ làm dữ liệu
đối chiếu (``scripts/qa/vn_hardcode_scan.py`` DATA_FILES).
"""
from odoo.tools import SQL

# xmlid → {field: (câu VN cũ, câu gốc EN mới)} — khớp data/return_issue_type_data.xml.
ISSUE_TYPE_SEED = {
    'issue_type_packaging': {
        'name': ('Hỏng bao bì', 'Damaged packaging'),
        'note': ('Bao bì rách, móp, ướt khi giao', 'Packaging torn, dented or wet on delivery'),
    },
    'issue_type_wrong_product': {
        'name': ('Sai sản phẩm', 'Wrong product'),
        'note': ('Giao sai sản phẩm so với đơn đặt', 'Delivered product differs from the order'),
    },
    'issue_type_expired': {
        'name': ('Hết hạn / cận date', 'Expired / near expiry'),
        'note': ('Sản phẩm đã hết hạn hoặc cận date theo quy định', 'Product expired or near expiry per policy'),
    },
    'issue_type_short_qty': {
        'name': ('Thiếu số lượng', 'Short quantity'),
        'note': ('Giao thiếu so với SL trên đơn', 'Delivered less than the ordered quantity'),
    },
    'issue_type_other': {
        'name': ('Lỗi khác', 'Other issue'),
        'note': ('Các trường hợp khác — ghi chú trong phần lý do', 'Other cases — describe in the note'),
    },
}


def issue_types_source_to_en(cr, module='wujia_return'):
    """Bản ghi seed mà ``en_US`` còn ĐÚNG câu VN cũ (HQ chưa sửa tay) ⇒ ``en_US`` = EN; ``vi_VN`` = câu VN cũ
    nếu chưa có khoá ``vi_VN`` (có rồi thì giữ). Bản ghi đã sửa tay giữ nguyên. Trả số field đã đổi."""
    changed = 0
    for xmlid, fields_ in ISSUE_TYPE_SEED.items():
        cr.execute(
            "SELECT res_id FROM ir_model_data WHERE module = %s AND name = %s AND model = %s",
            (module, xmlid, 'wujia.return.issue.type'))
        row = cr.fetchone()
        if not row:
            continue
        for fname, (vn, en) in fields_.items():
            col = SQL.identifier(fname)
            cr.execute(SQL(
                """UPDATE wujia_return_issue_type
                      SET %(col)s = %(col)s || jsonb_build_object('en_US', %(en)s::text)
                                  || CASE WHEN %(col)s ? 'vi_VN' THEN '{}'::jsonb
                                          ELSE jsonb_build_object('vi_VN', %(vn)s::text) END
                    WHERE id = %(id)s AND %(col)s ->> 'en_US' = %(vn)s""",
                col=col, en=en, vn=vn, id=row[0]))
            changed += cr.rowcount
    return changed
