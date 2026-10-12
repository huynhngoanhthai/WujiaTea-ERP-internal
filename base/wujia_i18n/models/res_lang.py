import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Ngôn ngữ bật sẵn cho mọi người chọn (chủ dự án chốt 05/10, J-V0). Bật thêm ngôn ngữ khác ở
# Settings → Languages là bộ chọn portal có ngay (WJ-LANG-001), không cần sửa danh sách này.
WJ_LANGS = ('vi_VN', 'en_US', 'th_TH', 'zh_CN')


class ResLang(models.Model):
    _inherit = 'res.lang'

    @api.model
    def _wj_enable_languages(self, codes=WJ_LANGS):
        """Bật các ngôn ngữ còn tắt + nạp `.po` của mọi module đã cài cho ngôn ngữ đó."""
        active = self._get_active_by('code')
        missing = [code for code in codes if code not in active]
        if not missing:
            return []
        modules = self.env['ir.module.module'].search([('state', '=', 'installed')])
        for code in missing:
            self._activate_lang(code)
            # _activate_lang chỉ bật, không nạp bản dịch (bài học J-T1).
            modules._update_translations(code)
        _logger.info("wujia_i18n: enabled languages %s", ", ".join(missing))
        return missing
