"""Seed demo data nhỏ cho Sprint 9.13 UI-12 Content Card pages.

Mục đích: tạo ~25 record demo nhỏ để showcase 6 page sau khi deploy:
    /portal                       (home: noti + order + return latest lists)
    /portal/notification          (full notification list)
    /portal/knowledge             (sidebar + article grid)
    /portal/purchase-history      (sale order list)
    /portal/return                (return request list)
    /portal/support               (support ticket list)

Idempotent: mọi record dùng marker `[UI12]` trong name / `ui12-` slug
prefix, search-or-create. Chạy nhiều lần KHÔNG nhân đôi.

Run trên Windows server (D:\\wujia-tea):
    cd D:\\wujia-tea
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    chcp 65001
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    nssm stop Odoo
    python odoo19\\odoo-bin shell `
        -c config\\odoo.conf `
        -d wujia_tea_19 --no-http `
        < scripts\\seed_ui12_demo.py
    nssm start Odoo

Run local dev (Linux):
    cd /home/huyban/odoo-dev/WujiaTea/odoo19
    /home/huyban/miniconda3/envs/odoo/bin/python odoo-bin shell \\
        -c /home/huyban/odoo-dev/WujiaTea/config/odoo.conf \\
        -d wujia_tea_19 --no-http \\
        < /home/huyban/odoo-dev/WujiaTea/scripts/seed_ui12_demo.py
"""
from datetime import datetime, timedelta

MARKER = ''  # Sprint 9.13b 2026-05-27 — dropped visible marker per user feedback.
SLUG_PREFIX = 'ui12-'  # internal slug only — not shown to user.
SUMMARY_TAG = 'Demo Sprint 9.13b'  # internal description tag for idempotency.

print(f"=== SEEDING SPRINT 9.13b DEMO DATA ===")


def upsert(model, domain, vals, label):
    Model = env[model]
    rec = Model.search(domain, limit=1)
    if rec:
        rec.write(vals)
        print(f"  [UPDATE] {label}: {rec.display_name or rec.id}")
    else:
        rec = Model.create(vals)
        print(f"  [CREATE] {label}: {rec.display_name or rec.id}")
    return rec


now = datetime.now()
today = now.date()

# ---------- Cleanup old [UI12] / UI12 records from previous seed runs ----------
print("\n[0] Cleanup legacy [UI12] / UI12 prefixed records")
old_notis = env['wujia.notification'].search([
    '|', ('name', 'ilike', '[UI12]'), ('dispatch_number', 'ilike', 'CV-UI12-'),
])
if old_notis:
    print(f"  Deleting {len(old_notis)} legacy notification(s)")
    old_notis.unlink()
old_returns = env['wujia.return.request'].search([('name', 'ilike', '/UI12/')])
if old_returns:
    print(f"  Deleting {len(old_returns)} legacy return request(s)")
    old_returns.unlink()
old_tickets = env['wujia.support.ticket'].search([('title', 'ilike', '[UI12]')])
if old_tickets:
    print(f"  Deleting {len(old_tickets)} legacy ticket(s)")
    old_tickets.unlink()
old_sos = env['sale.order'].search([('client_order_ref', 'ilike', 'WJ-UI12-SO-')])
if old_sos:
    print(f"  Cancelling+deleting {len(old_sos)} legacy sale order(s)")
    for so in old_sos:
        if so.state not in ('cancel', 'draft'):
            (so._action_cancel() if hasattr(so, '_action_cancel') else so.action_cancel())
        try:
            so.unlink()
        except Exception as ex:
            print(f"    skip {so.name}: {ex}")

# ---------- Franchises (lookup) ----------
print("\n[1] Franchise lookup")
franchises = env['wujia.franchise.management'].search([], limit=3)
if not franchises:
    print("  ERROR: Không có franchise. Cần `wujia_portal_base/data/sample_data.xml` trước.")
    raise SystemExit(1)
print(f"  Found {len(franchises)} franchise: {franchises.mapped('name')}")

# ---------- 1. Notifications (5 record) — idempotent on dispatch_number ----------
print(f"\n[2] Notifications (5 records)")
ntypes = {t.code: t for t in env['wujia.notification.type'].search([])}
noti_samples = [
    ('URG',   'Cập nhật giá sản phẩm tháng 6 — áp dụng từ 01/06',  'urgent'),
    ('GEN',   'Lịch giao hàng tuần này có thay đổi do kho HQ kiểm kê', 'normal'),
    ('PROMO', 'Combo sinh nhật khách hàng — khởi động chương trình', 'normal'),
    ('SYS',   'Bảo trì hệ thống POS đêm 30/05 từ 22h–24h', 'normal'),
    ('GEN',   'Mời họp đối tác nhượng quyền tháng 6 — link Google Meet', 'normal'),
]
for i, (code, title, prio) in enumerate(noti_samples):
    dispatch = f'CV-DEMO-{i+1:03d}'
    upsert(
        'wujia.notification',
        [('dispatch_number', '=', dispatch)],
        {
            'name': title,
            'type_id': ntypes.get(code).id if ntypes.get(code) else False,
            'dispatch_number': dispatch,
            # Sprint 41: date -> published_date, cờ `published` -> state.
            'published_date': now - timedelta(hours=i*6),
            'content': (
                f'<p><strong>{title}</strong></p>'
                f'<p>Nội dung thông báo #{i+1}. Vui lòng xem kỹ và phản hồi nếu có thắc mắc.</p>'
                f'<ul><li>Áp dụng cho toàn bộ cửa hàng nhượng quyền</li><li>Hiệu lực từ {today.isoformat()}</li></ul>'
            ),
            # Sprint 42: chọn cửa hàng cụ thể thì target_mode phải là 'manual'.
            'target_mode': 'manual',
            'franchise_ids': [(6, 0, franchises.ids)],
            'state': 'published',
            'priority': prio,
        },
        f'noti #{i+1}',
    )

# ---------- 2. Knowledge: 2 category + 5 article — idempotent on code/slug ----------
print(f"\n[3] Knowledge categories + articles")
cat_ops = upsert(
    'wujia.knowledge.category',
    [('code', '=', f'{SLUG_PREFIX}ops')],
    {'code': f'{SLUG_PREFIX}ops', 'name': 'Vận hành', 'sequence': 10,
     'description': 'Quy trình + checklist vận hành cửa hàng.'},
    'cat ops',
)
cat_prod = upsert(
    'wujia.knowledge.category',
    [('code', '=', f'{SLUG_PREFIX}prod')],
    {'code': f'{SLUG_PREFIX}prod', 'name': 'Sản phẩm', 'sequence': 20,
     'description': 'Công thức + pha chế.'},
    'cat prod',
)

article_samples = [
    (cat_ops,  'Checklist mở cửa hàng buổi sáng',  'mandatory', 'published'),
    (cat_ops,  'Quy trình giao ca giữa nhân viên',  'important', 'published'),
    (cat_prod, 'Công thức Hồng Trà Sữa size M',     'mandatory', 'published'),
    (cat_prod, 'Pha trà Đào Olong size L',          'new',       'published'),
    (cat_prod, 'Cách bảo quản nguyên liệu trong tủ mát', 'important', 'published'),
]
for i, (cat, title, badge, state) in enumerate(article_samples):
    slug = f'{SLUG_PREFIX}{i+1:02d}'
    upsert(
        'wujia.knowledge.article',
        [('slug', '=', slug)],
        {
            'name': title,
            'slug': slug,
            'category_id': cat.id,
            'summary': f'Tóm tắt cho bài {title}.',
            'content': f'<h3>{title}</h3><p>Nội dung chi tiết cho bài viết.</p>',
            'state': state,
            'portal_badge': badge,
            'publish_date': now - timedelta(days=i),
            'sequence': 10 + i,
        },
        f'article #{i+1}',
    )

# ---------- 3. Return requests (5 record, 5 state) — idempotent on name code ----------
# Sprint K redesign: một sản phẩm mỗi phiếu. Model wujia.return.error.type và các
# field error_id / expected_delivery_date / refuse_reason không còn tồn tại.
print(f"\n[4] Return requests (5 records)")
issue_types = env['wujia.return.issue.type'].search([], limit=5)
rr_products = env['product.product'].search([('sale_ok', '=', True)], limit=5)
rr_uom = env.ref('uom.product_uom_unit', raise_if_not_found=False)
states = ['draft', 'submitted', 'approved', 'rejected', 'done']
state_labels = {'draft': 'Nháp', 'submitted': 'Đã gửi', 'approved': 'Đã duyệt',
                'rejected': 'Từ chối', 'done': 'Hoàn thành'}
if not (issue_types and rr_products and rr_uom):
    print("    ! bỏ qua: thiếu loại lỗi / sản phẩm / đơn vị tính")
else:
    for i, st in enumerate(states):
        code = f'WJ-RR/DEMO/{i+1:03d}'
        upsert(
            'wujia.return.request',
            [('name', '=', code)],
            {
                'name': code,
                'franchise_id': franchises[i % len(franchises)].id,
                'request_date': now - timedelta(days=i),
                'state': st,
                'product_id': rr_products[i % len(rr_products)].id,
                'request_qty': 1.0 + i,
                'request_uom_id': rr_uom.id,
                'opening_datetime': now - timedelta(days=i, hours=2),
                'issue_type_id': issue_types[i % len(issue_types)].id,
                'note': f'Yêu cầu đổi trả #{i+1} — trạng thái {state_labels[st]}',
                'reject_reason': 'Không đủ chứng cứ ảnh' if st == 'rejected' else False,
            },
            f'return #{i+1} {st}',
        )

# ---------- 3b. Products — minimum 5 for sale order seeding ----------
print(f"\n[5a] Products (ensure at least 5 storable goods)")
Product = env['product.product']
product_samples = [
    ('TS-HONG', 'Hồng Trà Sữa size M',     45000.0),
    ('TS-DAO',  'Trà Đào Olong size L',    52000.0),
    ('TS-MAT',  'Matcha Latte size M',     48000.0),
    ('TP-PUDD', 'Pudding Trứng',            8000.0),
    ('TP-CHEE', 'Topping Phô Mai Macchiato', 9000.0),
]
products_list = []
for ref, name, price in product_samples:
    rec = upsert(
        'product.product',
        [('default_code', '=', ref)],
        {
            'default_code': ref,
            'name': name,
            'type': 'consu',
            'list_price': price,
            'sale_ok': True,
            'purchase_ok': True,
            # Sprint 30: flag portal ở variant-level; public bắt buộc min_qty > 0.
            'is_public_portal': True,
            'min_qty': 1,
        },
        f'product {ref}',
    )
    products_list.append(rec.id)
products = Product.browse(products_list)
products.filtered(lambda p: not p.is_public_portal or p.min_qty <= 0).write(
    {'is_public_portal': True, 'min_qty': 1}
)

# ---------- 4. Sale orders (5 record, mix state) — idempotent on client_order_ref ----------
print(f"\n[5b] Sale orders (5 records)")
SO = env['sale.order']
Member = env['wujia.franchise.member']
if not products:
    print("  WARNING: không có product nào — bỏ qua tạo SO.")
else:
    # 5 orders: 2 draft, 2 confirmed (sale), 1 cancel
    order_plan = [
        ('draft',  3),  # qty 3
        ('sale',   5),
        ('draft',  2),
        ('sale',   8),
        ('cancel', 4),
    ]
    for i, (target_state, qty) in enumerate(order_plan):
        franch = franchises[i % len(franchises)]
        client_ref = f'WJ-DEMO-SO-{i+1:03d}'
        membership = Member.search(
            [('franchise_id', '=', franch.id), ('is_currently_valid', '=', True)],
            limit=1,
        )
        if not membership:
            print(f"  WARNING: franchise {franch.name} chưa có member valid — bỏ qua SO #{i+1}")
            continue
        existing = SO.search([('client_order_ref', '=', client_ref)], limit=1)
        if existing:
            print(f"  [SKIP] SO {client_ref} đã tồn tại: {existing.name} ({existing.state})")
            continue
        partner = franch.partner_id or env['res.partner'].search([('is_company', '=', True)], limit=1)
        so = SO.create({
            'partner_id': partner.id,
            'is_portal_order': True,
            'franchise_id': franch.id,
            'franchise_partner_id': partner.id,
            'portal_requester_user_id': membership.user_id.id,
            'portal_member_id': membership.id,
            'client_order_ref': client_ref,
            'origin': 'Wujia Portal Demo',
            'date_order': now - timedelta(days=i),
            'order_line': [(0, 0, {
                'product_id': products[i % len(products)].id,
                'product_uom_qty': qty,
            })],
        })
        if target_state in ('sale', 'cancel'):
            so.action_confirm()
        if target_state == 'cancel':
            so._action_cancel() if hasattr(so, '_action_cancel') else so.action_cancel()
        print(f"  [CREATE] SO {client_ref}: {so.name} → state={so.state}")

# ---------- 5. Support tickets (6 record, full 6 state) — idempotent on title ----------
print(f"\n[6] Support tickets (6 records)")
admin = env.ref('base.user_admin')
sup_cats = {c.code: c for c in env['wujia.support.category'].search([])}
if not sup_cats:
    print("  WARNING: không có support category — bỏ qua tickets.")
else:
    # Titles are unique enough to use as idempotency key.
    ticket_samples = [
        ('pos',       'new',              'urgent', 'POS treo ở bước thanh toán'),
        ('delivery',  'in_progress',      'normal', 'Giao thiếu 2 hộp trà ô long'),
        ('account',   'waiting_customer', 'normal', 'Reset mật khẩu user POS'),
        ('product',   'resolved',         'normal', 'Sai mã SP TR-001 trên portal'),
        ('operation', 'closed',           'normal', 'Yêu cầu banner marketing Tết'),
        ('order',     'cancelled',        'normal', 'Đặt nhầm đơn 2 lần — huỷ'),
    ]
    for i, (cat_code, state, prio, title) in enumerate(ticket_samples):
        if cat_code not in sup_cats:
            print(f"  SKIP: category code '{cat_code}' không tồn tại.")
            continue
        vals = {
            'title': title,
            'description': f'<p>{title}.</p><p>Ticket #{i+1}, state={state}.</p>',
            'franchise_id': franchises[i % len(franchises)].id,
            'created_by_id': admin.id,
            'category_id': sup_cats[cat_code].id,
            'priority': prio,
            'state': state,
        }
        if state in ('in_progress', 'waiting_customer', 'resolved'):
            vals['assigned_user_id'] = admin.id
            vals['in_progress_date'] = now - timedelta(days=i)
        if state == 'resolved':
            vals['resolved_date'] = now - timedelta(hours=12)
        if state == 'closed':
            vals['closed_date'] = now - timedelta(days=10)
        if state == 'cancelled':
            vals['cancel_reason'] = 'Cửa hàng chủ động huỷ — đặt trùng.'
        upsert(
            'wujia.support.ticket',
            [('title', '=', title)],
            vals,
            f'ticket #{i+1} {state}',
        )

# ---------- Commit ----------
env.cr.commit()
print(f"\n=== DONE — đã commit transaction ===")
print("Verify:")
print("  /portal                    → 4 KPI card + 3 latest list (5 noti / 5 order / 5 return)")
print("  /portal/notification       → 5 noti record")
print("  /portal/knowledge          → 2 category + 5 article")
print("  /portal/purchase-history   → 5 sale order (2 draft, 2 confirmed, 1 cancel)")
print("  /portal/return             → 5 return request (full 5 state)")
print("  /portal/support            → 6 ticket (full 6 state)")
