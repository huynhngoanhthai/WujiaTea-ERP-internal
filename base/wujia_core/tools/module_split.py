"""Đổi chủ bản ghi khi tách một phân hệ ra module khác (ADR-027 §Quy trình tách).

Chỉ chạm cột ``module`` — không sửa dữ liệu, quyền, menu hay ràng buộc. Không đổi chủ thì lúc
``-u`` Odoo tạo bản sao dưới tên module mới rồi ``_process_end`` dọn bản cũ (user rơi khỏi
group, sequence chạy lại); ``ir_model_constraint`` để chủ cũ thì module mới sinh dòng trùng tên
và dòng cũ mồ côi khi gỡ vỏ. Gọi ở ``pre_init_hook`` của module mới vì lần cài đầu Odoo không
chạy migration script. Tiện ích thuần ``cr`` — đặt ở L1 để mọi module nghiệp vụ dùng chung.
"""

# ir_model_data.model → (FROM, cột id, cột model, model là chuỗi hay id ir_model)
_BY_MODEL = {
    'ir.model': ("ir_model t", "t.id", "t.model", True),
    'ir.model.fields': ("ir_model_fields t", "t.id", "t.model", True),
    'ir.model.fields.selection': ("ir_model_fields_selection t JOIN ir_model_fields f ON f.id = t.field_id",
                                  "t.id", "f.model", True),
    'ir.model.constraint': ("ir_model_constraint t", "t.id", "t.model", False),
    'ir.model.inherit': ("ir_model_inherit t", "t.id", "t.model_id", False),
    'ir.model.access': ("ir_model_access t", "t.id", "t.model_id", False),
    'ir.rule': ("ir_rule t", "t.id", "t.model_id", False),
    'ir.ui.view': ("ir_ui_view t", "t.id", "t.model", True),
    'ir.actions.act_window': ("ir_act_window t", "t.id", "t.res_model", True),
    'ir.actions.server': ("ir_act_server t", "t.id", "t.model_id", False),
    # ir.cron kế thừa ir.actions.server (Odoo 17+): model nằm ở ir_act_server
    'ir.cron': ("ir_cron t JOIN ir_act_server a ON a.id = t.ir_actions_server_id", "t.id", "a.model_id", False),
    'mail.template': ("mail_template t", "t.id", "t.model_id", False),
    'ir.sequence': ("ir_sequence t", "t.id", "t.code", True),
}


def imd_names(cr, old, models, extra=()):
    """Tên ``ir_model_data`` của ``old`` gắn với ``models`` (kể cả model kế thừa như
    ``sale.order`` — chỉ lấy dòng do ``old`` sở hữu, không đụng module khác).

    Menu, group, dữ liệu mẫu không có cột model ⇒ truyền qua ``extra``. Sequence khớp theo
    ``code`` = tên model. Đối chiếu kết quả với ``SELECT name FROM ir_model_data WHERE module=%s``
    trước khi tin: phần dư là thứ ở lại (đúng) hoặc thứ quên liệt kê (sai).
    """
    names = set(extra)
    for imd_model, (source, id_col, model_col, is_text) in _BY_MODEL.items():
        where = f"{model_col} IN %s" if is_text else f"{model_col} IN (SELECT id FROM ir_model WHERE model IN %s)"
        cr.execute(f"""SELECT d.name FROM ir_model_data d
                        WHERE d.module = %s AND d.model = %s
                          AND d.res_id IN (SELECT {id_col} FROM {source} WHERE {where})""",
                   (old, imd_model, tuple(models)))
        names.update(r[0] for r in cr.fetchall())
    return sorted(names)


def migrate_ownership(cr, old, new, names=None, models=None):
    """Chuyển ``ir_model_data`` (``names``) + ràng buộc/quan hệ bảng (``models``) của ``old`` sang ``new``.

    ``None`` ⇒ chuyển tất cả (module cũ bị rút hết, như F7). Tách một phần: ``names=imd_names(...)``
    và ``models`` = các model đi theo (kể cả model kế thừa có field/ràng buộc chuyển đi).
    """
    cr.execute("SELECT id FROM ir_module_module WHERE name = %s", (new,))
    row = cr.fetchone()
    if not row:
        raise ValueError(f"migrate_ownership: module {new!r} is not in ir_module_module")
    new_id = row[0]
    if names is None:
        cr.execute("UPDATE ir_model_data SET module = %s WHERE module = %s", (new, old))
    else:
        cr.execute("UPDATE ir_model_data SET module = %s WHERE module = %s AND name IN %s",
                   (new, old, tuple(names) or ('',)))
    moved = {'ir_model_data': cr.rowcount}
    for table in ('ir_model_constraint', 'ir_model_relation'):
        query = f"""
            UPDATE {table} t SET module = %s
             WHERE t.module = (SELECT id FROM ir_module_module WHERE name = %s)"""
        params = [new_id, old]
        if models is not None:
            query += " AND t.model IN (SELECT id FROM ir_model WHERE model IN %s)"
            params.append(tuple(models))
        cr.execute(query, params)
        moved[table] = cr.rowcount
    return moved
