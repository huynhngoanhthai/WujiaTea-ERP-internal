#!/usr/bin/env python3
"""Ma trận role × cửa hàng × route — nghiệm thu ★IR cụm I (chỉ đọc, đo được trên UAT).

Mỗi ngữ cảnh = (tài khoản, cookie cửa hàng đang chọn). Cookie `wujia_active_franchise_id` đặt thẳng
vào trình duyệt ⇒ không gọi /portal/franchise/switch, không ghi gì lên server. Chỉ GET trang.

Mỗi ô: HTTP, URL cuối, trang "Không có quyền" (#153), khối nhắc chọn cửa hàng (#152/#157),
pageerror, tràn ngang, ảnh. Kỳ vọng tính theo luật:
  - chưa chọn cửa hàng (nhiều cửa hàng) ⇒ màn dữ liệu hiện khối nhắc chọn, không lộ số liệu;
  - staff tại cửa hàng đang chọn ⇒ Công nợ / Báo cáo / Yêu cầu cập nhật trả 403;
  - owner/manager ⇒ 200, không khối nhắc, không 403.

    python3 scripts/qa/wj_ir_matrix.py --base https://dev.wujiatea.com.vn \
        --ctx em.hcm:wujia@test123: --ctx admin:Wujia@2026:none --ctx admin:Wujia@2026:HCM-01 ... \
        --out docs/i-review/matrix.json --shots docs/i-review/shots
"""
import argparse
import json
import pathlib
import re
import sys
import xmlrpc.client

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from wj_contrast import ROUTES, DETAILS  # noqa: E402
from wj_measure import login  # noqa: E402

COOKIE = 'wujia_active_franchise_id'
ADMIN_ONLY = ('/portal/debt', '/portal/reports/orders', '/portal/info-request')
# Màn không phụ thuộc dữ liệu cửa hàng ⇒ không kỳ vọng khối nhắc chọn.
STORE_FREE = ('/portal/profile', '/portal/change-password', '/portal/knowledge',
              '/portal/franchise-information', '/portal/support/new', '/portal/notification')

PROBE = r"""
() => {
  const vis = el => !!el && el.offsetParent !== null;
  const any = sel => [...document.querySelectorAll(sel)].some(vis);
  const de = document.documentElement;
  return {
    no_perm: any('.wj-no-permission'),
    scope_prompt: any('.wj-store-scope-prompt'),
    overflow: Math.max(0, de.scrollWidth - de.clientWidth),
    h1: [...document.querySelectorAll('h1')].length,
    title: document.title,
  };
}
"""


def store_ids(base, db, login_, pwd):
    """{code: id} cửa hàng user truy cập được — đọc qua XML-RPC chỉ đọc."""
    common = xmlrpc.client.ServerProxy(base + '/xmlrpc/2/common')
    uid = common.authenticate(db, login_, pwd, {})
    obj = xmlrpc.client.ServerProxy(base + '/xmlrpc/2/object')
    rows = obj.execute_kw(db, uid, pwd, 'wujia.franchise.member', 'search_read',
                          [[('user_id', '=', uid)]], {'fields': ['franchise_id', 'role']})
    out = {}
    for r in rows:
        name = r['franchise_id'][1]
        code = re.match(r'\[([^\]]+)\]', name)
        out[code.group(1) if code else name] = (r['franchise_id'][0], r['role'])
    return out


def expect(route, role, picked, multi):
    base_route = '/' + '/'.join(route.strip('/').split('/')[:2])
    if multi and not picked:
        if base_route in STORE_FREE or route in STORE_FREE:
            return 'ok'
        return 'prompt'
    if role == 'staff' and base_route in ADMIN_ONLY:
        return 'no_perm'
    return 'ok'


def run(args):
    from playwright.sync_api import sync_playwright
    shots = pathlib.Path(args.shots)
    shots.mkdir(parents=True, exist_ok=True)
    out = {'base': args.base, 'cells': []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for spec in args.ctx:
            user, pwd, store = spec.split(':')
            stores = store_ids(args.base, args.db, user, pwd)
            multi = len(stores) > 1
            fid, role = (stores.get(store) or (None, None)) if store and store != 'none' else (None, None)
            if not multi and stores:
                fid, role = next(iter(stores.values()))
            tag = f'{user}@{store or "auto"}'
            for width in args.widths:
                ctx = browser.new_context(viewport={'width': width, 'height': 900 if width > 900 else 844})
                page = ctx.new_page()
                errors = []
                page.on('pageerror', lambda e, errs=errors: errs.append(str(e)[:200]))
                login(page, args.base, user, pwd)
                host = re.sub(r'^https?://', '', args.base).split(':')[0]
                if fid and multi:
                    ctx.add_cookies([{'name': COOKIE, 'value': str(fid), 'domain': host, 'path': '/'}])
                else:
                    ctx.clear_cookies(name=COOKIE)
                routes = list(args.routes)
                for list_route, pat in DETAILS:
                    try:
                        page.goto(args.base + list_route, wait_until='domcontentloaded')
                        hrefs = page.eval_on_selector_all('a[href]', 'els => els.map(e => e.getAttribute("href"))')
                        hit = next((h for h in hrefs if re.match(pat, h or '')), None)
                        if hit:
                            routes.append(hit)
                    except Exception:  # noqa: BLE001 — chi tiết thiếu thì bỏ, ô list vẫn đo
                        pass
                for route in routes:
                    errors.clear()
                    # Không dùng networkidle: bus.bus giữ long-poll nên trang không bao giờ "rảnh mạng".
                    try:
                        resp = page.goto(args.base + route, wait_until='load', timeout=45000)
                        page.wait_for_timeout(600)
                        status = resp.status if resp else 0
                    except Exception as e:  # noqa: BLE001 — ô treo ghi BAD, không dừng ma trận
                        errors.append(f'goto: {str(e)[:120]}')
                        status = 0
                    p = page.evaluate(PROBE)
                    want = expect(route, role, bool(fid), multi)
                    got = 'no_perm' if p['no_perm'] else ('prompt' if p['scope_prompt'] else 'ok')
                    ok = (status < 500 and not errors and p['overflow'] <= 1 and got == want
                          and '/web/login' not in page.url and '/portal/login' not in page.url)
                    name = f"{tag}_{width}_{route.strip('/').replace('/', '_') or 'root'}.png"
                    if args.shots_all or not ok:
                        page.screenshot(path=str(shots / name), full_page=False)
                    out['cells'].append({
                        'ctx': tag, 'role': role, 'multi': multi, 'width': width, 'route': route,
                        'status': status, 'final': page.url.replace(args.base, ''), 'got': got, 'want': want,
                        'pageerror': list(errors), 'overflow': p['overflow'], 'h1': p['h1'], 'ok': ok,
                    })
                    flag = 'OK ' if ok else 'BAD'
                    print(f'{flag} {tag:22s} {width} {route:42s} {status} got={got} want={want} '
                          f'err={len(errors)} ovf={p["overflow"]}', flush=True)
                ctx.close()
        browser.close()
    bad = [c for c in out['cells'] if not c['ok']]
    out['summary'] = {'cells': len(out['cells']), 'bad': len(bad)}
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"\nTOTAL {len(out['cells']) - len(bad)}/{len(out['cells'])} OK → {args.out}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--db', default='wujia_tea_19')
    ap.add_argument('--ctx', action='append', required=True, help='login:password:STORECODE|none|')
    ap.add_argument('--routes', nargs='*', default=ROUTES)
    ap.add_argument('--widths', nargs='*', type=int, default=[1440, 390])
    ap.add_argument('--out', default='docs/i-review/matrix.json')
    ap.add_argument('--shots', default='docs/i-review/shots')
    ap.add_argument('--shots-all', action='store_true')
    run(ap.parse_args())
