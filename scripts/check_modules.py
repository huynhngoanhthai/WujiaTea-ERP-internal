"""Kiểm tra trạng thái cài đặt các module Wujia trên server.

Chạy:
  Windows PowerShell:
    Get-Content scripts\\check_modules.py | python odoo19\\odoo-bin shell `
        -c config\\odoo.conf -d wujia_tea_19 --no-http

  Linux/macOS:
    python odoo19/odoo-bin shell -c config/odoo.conf -d wujia_tea_19 --no-http \\
        < scripts/check_modules.py
"""
print("=== TRẠNG THÁI MODULE WUJIA ===\n")
mods = env['ir.module.module'].search([('name', 'like', 'wujia%')], order='name')
if not mods:
    print("KHÔNG có module wujia nào trong DB. Cần chạy -i để install.")
else:
    print(f"{'name':<32} {'state':<15} {'version'}")
    print("-" * 70)
    for m in mods:
        print(f"{m.name:<32} {m.state:<15} {m.installed_version or '—'}")

print("\n=== TEMPLATES có sẵn (ir.ui.view với key portal_home_page) ===")
views = env['ir.ui.view'].sudo().search([('key', '=', 'wujia_portal_base.portal_home_page')])
if views:
    print(f"  ✓ Có {len(views)} view: {views.ids}")
else:
    print("  ✗ KHÔNG có template portal_home_page → cần upgrade wujia_portal_base")

print("\n=== Franchise data ===")
fs = env['wujia.franchise.management'].search([])
print(f"  {len(fs)} franchise: {[f.name for f in fs]}")

print("\n=== Admin membership ===")
admin = env.ref('base.user_admin')
ms = env['wujia.franchise.member'].search([('user_id', '=', admin.id)])
print(f"  Admin (id={admin.id}) có {len(ms)} membership: {[(m.franchise_id.name, m.role) for m in ms]}")
