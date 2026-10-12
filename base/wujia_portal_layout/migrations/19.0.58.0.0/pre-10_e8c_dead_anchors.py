# -*- coding: utf-8 -*-
"""E8c — menu avatar + sheet "Thêm" đổi neo.

Thân menu avatar dời vào partial `wj_acct_menu_items` (hết `a[@href='/portal/change-password']`
trong header), sheet "Thêm" bỏ dòng `/portal/profile` (neo mới `msheet_end`). View con cũ còn
xpath vào neo đã gỡ ⇒ khi arch mới được ghi, Odoo kiểm cả view con ⇒ "Element cannot be
located". Xoá TRƯỚC khi nạp data, chỉ những view còn neo chết; module sở hữu tạo lại view của
mình khi `-u` cùng lượt. View không dùng neo chết (giỏ, chuông, Khảo sát) giữ nguyên.
"""

from odoo import SUPERUSER_ID, api

PARENTS = (
    "wujia_portal_layout.layout_top_navbar",
    "wujia_portal_layout.mobile_header",
    "wujia_portal_layout.mobile_bottomnav",
)
DEAD_ANCHORS = (
    "@href='/portal/change-password'",
    "@href='/portal/profile'",
    "wujia-msheet-list')]/a[1]",
)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    parent_ids = [v.id for v in (env.ref(x, raise_if_not_found=False) for x in PARENTS) if v]
    if not parent_ids:
        return
    children = env["ir.ui.view"].with_context(active_test=False).search(
        [("inherit_id", "in", parent_ids)]
    )
    children.filtered(
        lambda v: any(a in (v.arch_db or "") for a in DEAD_ANCHORS)
    ).unlink()
