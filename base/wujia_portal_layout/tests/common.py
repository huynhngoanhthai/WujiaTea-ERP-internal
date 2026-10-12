"""J-V1 — câu gốc của khung là tiếng Anh, tiếng Việt nằm ở `i18n/vi_VN.po`.

Test assert nhãn tiếng Việt chạy ở `lang=vi_VN` (quy ước Phần V §6 #5: không xoá assert).
"""


def load_vi(env):
    """Bật vi_VN + nạp .po của khung; trả env `lang=vi_VN`.

    `_activate_lang` chỉ bật ngôn ngữ, KHÔNG nạp .po ⇒ phải `_update_translations` (bài học J-T1).
    """
    env['res.lang']._activate_lang('vi_VN')
    env['ir.module.module'].search(
        [('name', '=', 'wujia_portal_layout')])._update_translations(['vi_VN'])
    return env(context=dict(env.context, lang='vi_VN'))
