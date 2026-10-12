#!/usr/bin/env python3
"""Đo riêng từng issue cụm I theo "Kết quả mong muốn" — chỉ đọc, chạy được trên UAT (★IR).

Chỉ GET trang + mở/đóng hộp thoại phía client; không bấm gửi/xác nhận, không đổi cửa hàng
qua server (cookie đặt thẳng trong trình duyệt). Mỗi phép đo in PASS/FAIL + số đo.

    python3 scripts/qa/wj_ir_checks.py --base https://dev.wujiatea.com.vn --out docs/i-review/checks.json
"""
import argparse
import datetime
import json
import pathlib
import re
import sys
import xmlrpc.client
import zoneinfo

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from wj_measure import login  # noqa: E402

COOKIE = 'wujia_active_franchise_id'
RES = []


def check(issue, name, ok, detail=''):
    RES.append({'issue': issue, 'name': name, 'ok': bool(ok), 'detail': detail})
    print(f"{'PASS' if ok else 'FAIL'} #{issue} {name} — {detail}", flush=True)


def rpc(args):
    common = xmlrpc.client.ServerProxy(args.base + '/xmlrpc/2/common')
    uid = common.authenticate(args.db, 'admin', args.admin_password, {})
    obj = xmlrpc.client.ServerProxy(args.base + '/xmlrpc/2/object')
    return lambda *a, **k: obj.execute_kw(args.db, uid, args.admin_password, *a, **k)


def new_page(browser, args, user, pwd, width, height=900, store=None):
    ctx = browser.new_context(viewport={'width': width, 'height': height})
    page = ctx.new_page()
    page.errors = []
    page.on('pageerror', lambda e: page.errors.append(str(e)[:160]))
    login(page, args.base, user, pwd)
    if store:
        host = re.sub(r'^https?://', '', args.base).split(':')[0]
        ctx.add_cookies([{'name': COOKIE, 'value': str(store), 'domain': host, 'path': '/'}])
    return ctx, page


def go(page, args, route):
    resp = page.goto(args.base + route, wait_until='load', timeout=45000)
    page.wait_for_timeout(500)
    return resp.status if resp else 0


def vis_text(page):
    return page.evaluate("() => document.body.innerText")


def run(args):
    from playwright.sync_api import sync_playwright
    x = rpc(args)
    ids = {r['code']: r['id'] for r in x('wujia.franchise.management', 'search_read', [[]], {'fields': ['code']})}
    hcm, hn1 = ids['HCM-01'], ids['HN-01']
    own = ('em.hcm', args.password)
    adm = ('admin', args.admin_password)
    with sync_playwright() as pw:
        b = pw.chromium.launch()

        # ---------- #62 + #163: Lịch sử gồm đơn huỷ, ghi chú đặt hàng PC/mobile, IDOR ----------
        ctx, p = new_page(b, args, *own, 1440)
        go(p, args, '/portal/purchase-history?state=cancel')
        t = vis_text(p)
        check(62, 'lọc Đã hủy (PC) có đơn huỷ S00076', 'S00076' in t, 'thấy S00076' if 'S00076' in t else t[:120])
        st = go(p, args, '/portal/purchase-history/76')
        check(62, 'chi tiết đơn huỷ mở được', st == 200 and 'S00076' in vis_text(p), f'HTTP {st}')
        hn_order = x('sale.order', 'search', [[('franchise_id', '=', hn1)]], {'limit': 1})[0]
        st = go(p, args, f'/portal/purchase-history/{hn_order}')
        leak = f'S000{hn_order}' in vis_text(p) or re.search(rf'S0*{hn_order}\b', vis_text(p))
        check(62, 'IDOR: đơn HN-01 không đọc được từ HCM-01', not leak, f'HTTP {st} url={p.url.replace(args.base, "")}')
        go(p, args, '/portal/purchase-history/77')
        n = p.locator('.wj-ph-note').filter(has_text='QA-RETEST-ISSUE-148-DOUBLECLICK').count()
        check(163, 'PC chi tiết S00077 có Ghi chú khi đặt hàng', n >= 1, f'{n} khối')
        ctx.close()
        ctx, p = new_page(b, args, *own, 390, 844)
        go(p, args, '/portal/purchase-history/77')
        n = p.locator('.wj-ph-note:visible').filter(has_text='QA-RETEST-ISSUE-148-DOUBLECLICK').count()
        check(163, 'mobile cùng nội dung ghi chú', n >= 1, f'{n} khối')
        ctx.close()

        # ---------- #152 / #157: chưa chọn cửa hàng ⇒ khối nhắc, không lộ dữ liệu ----------
        ctx, p = new_page(b, args, *adm, 1440)
        for route in ('/portal', '/portal/delivery', '/portal/reports/orders', '/portal/return',
                      '/portal/info-request', '/portal/exam'):
            st = go(p, args, route)
            prompt = p.locator('.wj-store-scope-prompt:visible').count()
            t = vis_text(p)
            codes = sorted(set(re.findall(r'\bS0\d{4}\b|RTN/\d+/\d+|INF/\S+', t)))
            empty_exam = route == '/portal/exam' and 'Chưa có đăng ký thi' in t
            check(152 if route != '/portal/exam' else 157, f'chưa chọn {route}: nhắc chọn, 0 mã chứng từ',
                  st == 200 and prompt and not codes and not empty_exam,
                  f'HTTP {st} prompt={prompt} codes={codes[:4]}')
        ctx.close()

        # ---------- #153: staff tại HN-01 (admin) — không tài chính / quản trị ----------
        ctx, p = new_page(b, args, *adm, 1440, store=hn1)
        go(p, args, '/portal')
        debt_kpi = p.locator('a[href^="/portal/debt"]:visible').count()
        check(153, 'Home staff: không ô/lối vào Công nợ', debt_kpi == 0, f'{debt_kpi} link /portal/debt hiện')
        for route in ('/portal/debt', '/portal/debt/payment-history', '/portal/reports/orders',
                      '/portal/info-request', '/portal/info-request/new'):
            st = go(p, args, route)
            check(153, f'staff {route} ⇒ 403 Không có quyền', st == 403 and p.locator('.wj-no-permission:visible').count(),
                  f'HTTP {st}')
        nav = p.eval_on_selector_all('nav a[href], .main-menu a[href], aside a[href]',
                                     'els => els.filter(e => e.offsetParent).map(e => e.getAttribute("href"))')
        bad = [h for h in nav if h and h.startswith(('/portal/debt', '/portal/reports', '/portal/info-request'))]
        check(153, 'menu staff ẩn Công nợ/Báo cáo/YC cập nhật', not bad, f'{bad}')
        ctx.close()
        ctx, p = new_page(b, args, *adm, 1440, store=hcm)
        for route in ('/portal/debt', '/portal/reports/orders', '/portal/info-request'):
            st = go(p, args, route)
            check(153, f'manager HCM-01 {route} ⇒ 200', st == 200 and not p.locator('.wj-no-permission:visible').count(),
                  f'HTTP {st}')
        ctx.close()

        # ---------- #156: Đổi trả không còn Lưu nháp ----------
        for w, h in ((1440, 900), (390, 844)):
            ctx, p = new_page(b, args, *own, w, h)
            go(p, args, '/portal/return/new')
            t = vis_text(p)
            drafts = len(re.findall(r'Lưu nháp|Save draft', t, re.I))
            check(156, f'form đổi trả {w}: không có Lưu nháp', drafts == 0, f'{drafts} chỗ')
            ctx.close()

        # ---------- #159: một số chưa đọc cho Home / chuông / endpoint ----------
        ctx, p = new_page(b, args, *own, 1440)
        go(p, args, '/portal')
        # Endpoint type='json' ⇒ phải POST JSON-RPC (GET trả 415).
        ep_n = p.evaluate("""async () => (await (await fetch('/portal/notification/unread-count', {method: 'POST',
            headers: {'Content-Type': 'application/json'}, body: JSON.stringify({jsonrpc: '2.0', params: {}})})).json()).result.count""")
        bell = p.locator('.wujia-header-noti-count:visible')
        bell_n = int(bell.first.inner_text().strip() or 0) if bell.count() else 0
        kpi = p.locator('a[href^="/portal/notification"]:visible').first.inner_text()
        kpi_n = int((re.findall(r'\d+', kpi) or ['0'])[0])
        go(p, args, '/portal/notification?unread=1')
        rows = p.locator('.wj-pc-noti-row--unread:visible').count()
        check(159, 'chuông = Home = endpoint = lọc Chưa đọc', ep_n == bell_n == kpi_n == rows,
              f'endpoint={ep_n} chuông={bell_n} home={kpi_n} lọc={rows}')
        ctx.close()

        # ---------- #160: chi tiết SP mobile hàng hành động trong viewport ----------
        prod = x('product.product', 'search', [[('sale_ok', '=', True)]], {'limit': 1})
        for w, h in ((360, 800), (390, 844), (430, 932)):
            ctx, p = new_page(b, args, *own, w, h)
            go(p, args, '/portal/order')
            href = p.eval_on_selector_all('a[href^="/portal/order/product/"]', 'els => els.map(e => e.getAttribute("href"))')
            route = href[0] if href else f'/portal/order/product/{prod[0]}'
            go(p, args, route)
            r = p.evaluate("""() => {
              const vw = document.documentElement.clientWidth;
              const els = [...document.querySelectorAll('button, a, input')].filter(e => e.offsetParent &&
                 /Thêm vào giỏ|Xem giỏ|Add to cart|View cart/i.test(e.innerText || e.value || '') );
              const qty = [...document.querySelectorAll('input[type=number], input[name*=qty]')].filter(e => e.offsetParent);
              const all = els.concat(qty).map(e => e.getBoundingClientRect());
              return {n: all.length, out: all.filter(b => b.left < -0.5 || b.right > vw + 0.5).length,
                      ovf: document.documentElement.scrollWidth - vw};
            }""")
            check(160, f'SP {route} @{w}: số lượng/Thêm/Xem giỏ trong viewport',
                  r['n'] >= 2 and r['out'] == 0 and r['ovf'] <= 1, f"{r}")
            ctx.close()

        # ---------- #162: phiếu hỗ trợ mobile có nội dung gốc ----------
        tk = x('wujia.support.ticket', 'search_read', [[('franchise_id', '=', hcm), ('description', '!=', False)]],
               {'fields': ['name'], 'limit': 1}) or x('wujia.support.ticket', 'search_read', [[('franchise_id', '=', hcm)]],
                                                      {'fields': ['name'], 'limit': 1})
        if tk:
            ctx, p = new_page(b, args, *adm, 390, 844, store=hcm)
            st = go(p, args, f"/portal/support/{tk[0]['id']}")
            n = p.locator('.wj-sup-content:visible').count()
            ovf = p.evaluate('() => document.documentElement.scrollWidth - document.documentElement.clientWidth')
            check(162, f"mobile {tk[0]['name']} có khối nội dung", st == 200 and n >= 1 and ovf <= 1, f'HTTP {st} khối={n} ovf={ovf}')
            ctx.close()

        # ---------- #164 + #167: ngôn ngữ header ----------
        for w in (1440, 1920):
            ctx, p = new_page(b, args, *own, w, 1080)
            for route in ('/portal', '/portal/inspection'):
                go(p, args, route)
                r = p.evaluate("""() => {
                  const f = [...document.querySelectorAll('.dropdown-language .flag-icon, .selected-language .flag-icon, .dropdown-language [class*=flag]')]
                     .find(e => e.offsetParent);
                  const lbl = [...document.querySelectorAll('.dropdown-language, .selected-language')].find(e => e.offsetParent);
                  if (!f) return {flag: null, label: lbl ? lbl.innerText.trim() : null};
                  const b = f.getBoundingClientRect();
                  return {w: Math.round(b.width * 10) / 10, h: Math.round(b.height * 10) / 10, cls: f.className,
                          label: lbl ? lbl.innerText.trim() : null};
                }""")
                if route == '/portal/inspection':
                    check(164, f'Khảo sát @{w} header tiếng Việt', r.get('label') and 'Việt' in r['label'], f'{r}')
                else:
                    check(167, f'cờ đang chọn @{w} ≈20×15', r.get('w') and 18 <= r['w'] <= 22 and 13 <= r['h'] <= 17, f'{r}')
            ctx.close()

        # ---------- #168: token chữ ListCard ----------
        ctx, p = new_page(b, args, *own, 390, 844)
        go(p, args, '/portal/purchase-history')
        r = p.evaluate("""() => {
          const cs = s => { const e = [...document.querySelectorAll(s)].find(x => x.offsetParent); if (!e) return null;
            const c = getComputedStyle(e); return `${c.fontSize}/${c.fontWeight}/${c.lineHeight}`; };
          return {title: cs('.wj-lc__name, .wj-lc__title'), label: cs('.wj-lc__label'), value: cs('.wj-lc__value')};
        }""")
        check(168, 'ListCard title 15/600/20 · label 12/500/18 · value 13/500/18',
              r['label'] == '12px/500/18px' and (r['value'] or '').startswith('13px/') and (r['title'] or '').startswith('15px/600'),
              f'{r}')
        ctx.close()

        # ---------- #169: hộp chọn cửa hàng là dialog, focus + Esc ----------
        for w, h in ((1440, 900), (390, 844)):
            ctx, p = new_page(b, args, *adm, w, h, store=hcm)
            go(p, args, '/portal')
            trig = p.locator('[aria-haspopup="dialog"]:visible').first
            if not trig.count():
                check(169, f'@{w} có trigger aria-haspopup=dialog', False, 'không thấy')
                ctx.close()
                continue
            trig.focus()
            p.keyboard.press('Enter')
            p.wait_for_timeout(400)
            d = p.evaluate("""() => {
              const dlg = [...document.querySelectorAll('[role=dialog]')].find(e => e.offsetParent);
              if (!dlg) return {dialog: false};
              return {dialog: true, modal: dlg.getAttribute('aria-modal'), named: !!(dlg.getAttribute('aria-labelledby') || dlg.getAttribute('aria-label')),
                      focusIn: dlg.contains(document.activeElement)};
            }""")
            escaped = 0
            for _ in range(10):
                p.keyboard.press('Tab')
                if not p.evaluate("() => { const d=[...document.querySelectorAll('[role=dialog]')].find(e=>e.offsetParent); return !!d && d.contains(document.activeElement); }"):
                    escaped += 1
            p.keyboard.press('Escape')
            p.wait_for_timeout(300)
            back = p.evaluate("() => document.activeElement && document.activeElement.getAttribute('aria-haspopup') === 'dialog'")
            closed = not p.evaluate("() => [...document.querySelectorAll('[role=dialog]')].some(e => e.offsetParent)")
            check(169, f'@{w} dialog modal có tên, focus trong, Tab không thoát, Esc đóng + trả focus',
                  d.get('dialog') and d.get('modal') == 'true' and d.get('named') and d.get('focusIn') and escaped == 0 and closed and back,
                  f'{d} tab_thoát={escaped} đóng={closed} focus_về_trigger={back}')
            ctx.close()

        # ---------- #171: Home PC bỏ tiêu đề/câu chào, H1 ẩn ----------
        for w, h in ((1440, 900), (390, 844)):
            ctx, p = new_page(b, args, *own, w, h)
            go(p, args, '/portal')
            r = p.evaluate("""() => {
              const h1 = [...document.querySelectorAll('h1')];
              const vis = h1.filter(e => { const b = e.getBoundingClientRect(); return b.width > 2 && b.height > 2; });
              return {h1: h1.length, h1_visible: vis.length, h1_text: h1.map(e => e.innerText.trim()).slice(0, 2),
                      greet: /Chào mừng|Welcome/.test(document.body.innerText)};
            }""")
            check(171, f'Home @{w}: 1 H1 ẩn, không câu chào', r['h1'] == 1 and r['h1_visible'] == 0 and not r['greet'], f'{r}')
            ctx.close()

        # ---------- #172 + #173 + #174: Hồ sơ cửa hàng ----------
        f = x('wujia.franchise.management', 'read', [[hcm]], {'fields': ['franchise_end_date', 'partner_id']})[0]
        tz = x('res.partner', 'read', [[f['partner_id'][0]]], {'fields': ['tz']})[0]['tz'] or 'Asia/Ho_Chi_Minh'
        today = datetime.datetime.now(zoneinfo.ZoneInfo(tz)).date()
        want = (datetime.date.fromisoformat(f['franchise_end_date']) - today).days if f['franchise_end_date'] else None
        texts = {}
        for w, h in ((1440, 900), (390, 844)):
            ctx, p = new_page(b, args, *own, w, h)
            go(p, args, '/portal/franchise-information')
            t = vis_text(p)
            texts[w] = t
            nums = [int(n) for n in re.findall(r'(\d+)\s*(?:ngày|days)', t)]
            check(173, f'@{w} số ngày còn lại = {want} (hết hạn {f["franchise_end_date"]}, hôm nay {today})',
                  want in nums, f'thấy {nums}')
            if w == 390:
                for vw in (320, 360, 390, 430):
                    p.set_viewport_size({'width': vw, 'height': 844})
                    p.wait_for_timeout(200)
                    r = p.evaluate("""() => {
                      const ns = [...document.querySelectorAll('.wj-lc__name')].filter(e => e.offsetParent);
                      return {n: ns.length, clipped: ns.filter(e => e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1).length,
                              minw: Math.min(...ns.map(e => Math.round(e.getBoundingClientRect().width))),
                              ovf: document.documentElement.scrollWidth - document.documentElement.clientWidth};
                    }""")
                    check(174, f'thành viên @{vw}: tên không cắt, không tràn', r['n'] and r['clipped'] == 0 and r['ovf'] <= 1, f'{r}')
            ctx.close()
        labels = ['Ngày khai trương', 'Điện thoại', 'Email', 'Hợp đồng', 'Người phụ trách']
        miss = {w: [l for l in labels if l.lower() not in texts[w].lower()] for w in texts}
        check(172, 'PC + mobile đủ nhóm trường', not miss[1440] and not miss[390], f'thiếu {miss}')
        b.close()

    bad = [r for r in RES if not r['ok']]
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.out).write_text(json.dumps(RES, ensure_ascii=False, indent=1))
    print(f'\nTOTAL {len(RES) - len(bad)}/{len(RES)} PASS → {args.out}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--db', default='wujia_tea_19')
    ap.add_argument('--password', default='wujia@test123')
    ap.add_argument('--admin-password', default='Wujia@2026')
    ap.add_argument('--out', default='docs/i-review/checks.json')
    run(ap.parse_args())
