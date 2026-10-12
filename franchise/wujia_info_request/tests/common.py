def load_vi(env, modules=('wujia_info_request',)):
    """Bật vi_VN + nạp .po của `modules`; trả env `lang=vi_VN` (Phần V §6 #5)."""
    env['res.lang']._activate_lang('vi_VN')
    env['ir.module.module'].search([
        ('name', 'in', modules), ('state', '=', 'installed'),
    ])._update_translations(['vi_VN'])
    return env(context=dict(env.context, lang='vi_VN'))
