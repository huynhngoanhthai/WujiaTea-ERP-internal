# -*- coding: utf-8 -*-
"""E8b — sidebar đổi neo nhóm (`nav_header_utils` → 3 nhóm + `nav_end`).

View con cũ trong DB còn xpath vào neo đã gỡ; khi arch mới của `layout_sidenav` được
ghi, Odoo kiểm cả view con ⇒ "Element cannot be located". Xoá chúng TRƯỚC khi nạp data;
mỗi module sở hữu mục sẽ tạo lại view của mình khi được `-u` cùng lượt.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    parent = env.ref("wujia_portal_layout.layout_sidenav", raise_if_not_found=False)
    if not parent:
        return
    env["ir.ui.view"].with_context(active_test=False).search(
        [("inherit_id", "=", parent.id)]
    ).unlink()
