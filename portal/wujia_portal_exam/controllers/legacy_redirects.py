# -*- coding: utf-8 -*-
"""Sprint 9.21 — 301 từ slug v14 cũ về route kebab-case của v19.

Portal v14 dùng slug gạch dưới / dài dòng. ~1500 người dùng nhượng quyền có thể còn
bookmark hoặc email HQ trỏ vào đó, nên giữ 301 vĩnh viễn. Slug dưới đây đã xác nhận
tồn tại trong nguồn v14 (`wujia_tea_odoo14`) — không bịa redirect cho slug chưa từng có.

F5a: dời khỏi `wujia_portal_layout` về module sở hữu route đích (ADR-027 — khung không
biết màn nghiệp vụ).
"""
from odoo import http
from odoo.http import request


class WujiaExamLegacyRedirects(http.Controller):

    @http.route('/portal/exam-registration', type='http', auth='public', sitemap=False)
    def legacy_exam_registration(self, **kw):
        return request.redirect('/portal/exam', code=301)
