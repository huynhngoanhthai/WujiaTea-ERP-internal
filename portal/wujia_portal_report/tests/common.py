REPORT_MODULES = ('wujia_portal_layout', 'wujia_portal_base', 'wujia_portal_report')


def load_vi(env, modules=REPORT_MODULES):
    """Bật vi_VN + nạp .po của `modules`; trả env `lang=vi_VN` (Phần V §6 #5)."""
    env['res.lang']._activate_lang('vi_VN')
    env['ir.module.module'].search([('name', 'in', modules), ('state', '=', 'installed')])._update_translations(['vi_VN'])
    return env(context=dict(env.context, lang='vi_VN'))
