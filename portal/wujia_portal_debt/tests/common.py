"""J-V5 — câu gốc của phân hệ Công nợ là tiếng Anh, tiếng Việt nằm ở `i18n/vi_VN.po`."""

DEBT_MODULES = ('wujia_portal_layout', 'wujia_portal_base', 'wujia_account', 'wujia_portal_debt')


def load_vi(env, modules=DEBT_MODULES):
    """Bật vi_VN + nạp .po của `modules`; trả env `lang=vi_VN`.

    Test assert câu tiếng Việt chạy ở vi_VN, không xoá assert (Phần V §6 #5). `_activate_lang`
    không nạp .po ⇒ `_update_translations`. Module chưa cài bị bỏ qua.
    """
    env['res.lang']._activate_lang('vi_VN')
    env['ir.module.module'].search([
        ('name', 'in', modules), ('state', '=', 'installed'),
    ])._update_translations(['vi_VN'])
    return env(context=dict(env.context, lang='vi_VN'))
