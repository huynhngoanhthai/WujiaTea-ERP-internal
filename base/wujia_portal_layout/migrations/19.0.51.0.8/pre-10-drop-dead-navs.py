# -*- coding: utf-8 -*-
"""F5a — xoá view sidenav/bottomnav đã gỡ khỏi source.

Odoo chỉ dọn record mồ côi ở CUỐI lượt nạp, nên view cũ còn trong DB vẫn được
kiểm tra khi các view mới của phiên F5a được ghi ⇒ phải xoá TRƯỚC khi nạp data.
"""

from odoo import SUPERUSER_ID, api

DEAD_VIEWS = (
    "wujia_portal_layout.layout_sidenav_figma",
)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid in DEAD_VIEWS:
        view = env.ref(xmlid, raise_if_not_found=False)
        if view:
            view.unlink()
