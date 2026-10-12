"""Bind admin vào toàn bộ franchise đang có với role owner.

Mục đích: trên server production, admin (Mitchell Admin) chưa có
wujia.franchise.member nào → portal dashboard trống. Script này gán admin
làm owner toàn bộ franchise để test portal.

Cách chạy:

  Linux/macOS:
    cd /home/huyban/odoo-dev/WujiaTea/odoo19
    python odoo-bin shell -c ../config/odoo.conf -d wujia_tea_19 --no-http \\
        < ../scripts/seed_admin_franchise.py

  Windows cmd.exe:
    cd D:\\wujia-tea
    python odoo19\\odoo-bin shell -c config\\odoo.conf -d wujia_tea_19 ^
        --no-http < scripts\\seed_admin_franchise.py

  Windows PowerShell (KHÔNG hỗ trợ < redirect — dùng Get-Content pipe):
    cd D:\\wujia-tea
    Get-Content scripts\\seed_admin_franchise.py | `
        python odoo19\\odoo-bin shell -c config\\odoo.conf `
        -d wujia_tea_19 --no-http

Idempotent: search-or-create theo (user_id, franchise_id).
"""
print("=== SEED ADMIN FRANCHISE MEMBERSHIP ===")

admin = env.ref('base.user_admin')
print(f"Admin user: {admin.name} (id={admin.id})")

franchises = env['wujia.franchise.management'].search([])
if not franchises:
    print("WARNING: không có wujia.franchise.management nào. Cần seed franchise trước.")
else:
    print(f"Found {len(franchises)} franchise: {franchises.mapped('name')}")
    Member = env['wujia.franchise.member']
    for f in franchises:
        existing = Member.search([
            ('user_id', '=', admin.id),
            ('franchise_id', '=', f.id),
        ], limit=1)
        if existing:
            if not existing.active or not existing.is_currently_valid:
                existing.write({'active': True, 'date_to': False})
                print(f"  [UPDATE] {f.name}: reactivated membership")
            else:
                print(f"  [SKIP] {f.name}: admin đã có membership active (role={existing.role})")
        else:
            new = Member.create({
                'user_id': admin.id,
                'franchise_id': f.id,
                'role': 'owner',
                'is_primary_owner': False,  # giữ primary_owner cũ nếu có
            })
            print(f"  [CREATE] {f.name}: admin → owner (id={new.id})")

env.cr.commit()
print("\n=== DONE — admin giờ thấy toàn bộ data portal ===")
