# -*- coding: utf-8 -*-
"""Sprint PC-1 — dev-only gallery of the wj-pc-* desktop component layer
(BA pc_source_ui_v1_4). Internal users only: it is a living reference used to
QA components against the BA SVGs and to copy markup when reworking desktop
screens in later sprints. Not linked in any portal menu; harmless static markup.
"""
from odoo import _, http
from odoo.http import request


class WujiaPcPreview(http.Controller):

    @http.route('/portal/_pc-preview', type='http', auth='user',
                website=False, sitemap=False)
    def pc_preview(self, **kw):
        # Restrict to internal staff — franchise portal users have no reason to see it.
        if not request.env.user.has_group('base.group_user'):
            return request.redirect('/portal')
        # Gallery mẫu: dựng pager bằng chính `build_pager` để trang mẫu không bao giờ
        # lệch với component thật (trước E3c là markup tĩnh, đã lạc hậu). Import TẠI CHỖ:
        # `wujia_portal_base` phụ thuộc vào module này, import ở đầu file là vòng tròn.
        from odoo.addons.wujia_portal_base.controllers.utils import build_pager
        return request.render('wujia_portal_layout.pc_preview_page', {
            'pgn': build_pager(128, 2, 10, path='/portal/_pc-preview',
                               item_label=_('records'), page_size_options=(10, 20, 50)),
        })
