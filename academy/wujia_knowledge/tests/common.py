"""Tiện ích test dùng chung (J-V7)."""


def load_vi(env, modules=('wujia_knowledge',)):
    """Bật vi_VN + nạp .po của `modules`; trả env `lang=vi_VN`.

    J-V7: câu gốc là tiếng Anh ⇒ test assert câu tiếng Việt chạy ở vi_VN, không xoá assert
    (Phần V §6 #5). `_activate_lang` không nạp .po ⇒ `_update_translations`.
    """
    env['res.lang']._activate_lang('vi_VN')
    env['ir.module.module'].search([
        ('name', 'in', modules), ('state', '=', 'installed'),
    ])._update_translations(['vi_VN'])
    return env(context=dict(env.context, lang='vi_VN'))
