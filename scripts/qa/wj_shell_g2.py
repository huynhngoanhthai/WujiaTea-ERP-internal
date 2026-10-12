#!/usr/bin/env python3
"""Đo shell cụm G2 — dải cửa hàng mobile (141) + giỏ/chuông/khối Cửa hàng PC (140).

141 UI-MOB-STORE-SWITCHER-001: mọi route mobile × 360/390/430 — dải có vai trò, chevron
    chỉ khi user >1 cửa hàng, không tràn ngang; bấm mã/tên/vai trò/chevron đều mở overlay
    chọn cửa hàng; nền lúc nhấn, viền lúc focus bàn phím (ép pseudo bằng CDP, chờ transition).
140 UI-PC-TOPBAR-REG-001: /portal, /portal/order, /portal/order/cart × 1440/1280/1200 —
    lệch tâm icon trong circle 40, hộp badge ∩ hộp icon với số 0/4/12 (gán số vào badge
    trên DOM, không đụng giỏ thật), chip vai trò nằm trong khối Cửa hàng hiện tại.

    python3 scripts/qa/wj_shell_g2.py --base http://127.0.0.1:8032 --login dung.multi
    python3 scripts/qa/wj_shell_g2.py --base https://dev.wujiatea.com.vn --login em.hcm --readonly
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from wj_density import ROUTES, login, resolve_details  # noqa: E402

PC = [(1440, 900), (1280, 800), (1200, 800)]
MOBILE = [(360, 800), (390, 844), (430, 932)]
PC_ROUTES = ['/portal', '/portal/order', '/portal/order/cart']

PC_PROBE = r"""
(count) => {
  const R = e => { const b = e.getBoundingClientRect(); return {x: b.left, y: b.top, w: b.width, h: b.height}; };
  const out = {};
  for (const [k, sel] of [['cart', '.wujia-header-cart-count'], ['bell', '.wujia-header-noti-count']]) {
    const badge = document.querySelector('.wujia-navbar ' + sel); if (!badge) continue;
    // giống header_cart_badge.js / header_bell_badge.js: 0 ⇒ `hidden`
    badge.hidden = count === '0'; badge.textContent = count; badge.classList.toggle('is-active', count !== '0');
    const btn = R(badge.closest('a')), icon = R(badge.closest('a').querySelector('i')), b = R(badge);
    const ox = Math.min(icon.x + icon.w, b.x + b.w) - Math.max(icon.x, b.x);
    const oy = Math.min(icon.y + icon.h, b.y + b.h) - Math.max(icon.y, b.y);
    out[k] = {btn: [btn.w, btn.h], icon: +icon.h.toFixed(1),
              off: [+(icon.x - btn.x - (btn.w - icon.w) / 2).toFixed(1), +(icon.y - btn.y - (btn.h - icon.h) / 2).toFixed(1)],
              overlap: b.w && ox > 0 && oy > 0 ? +(ox * oy).toFixed(1) : 0,
              badgeShown: getComputedStyle(badge).display !== 'none'};
  }
  const blk = document.querySelector('.wujia-store-current-block'), role = blk && blk.querySelector('.wujia-store-role-badge');
  if (blk) { const a = R(blk), r = role && R(role);
    out.store = {inside: !!r && r.x >= a.x && r.x + r.w <= a.x + a.w, role: role && role.textContent.trim(),
                 bg: getComputedStyle(blk).backgroundColor}; }
  return out;
}"""

STRIP_PROBE = r"""() => { const s = document.querySelector('.wujia-store-mobile-strip'); if (!s) return null;
  const R = e => { if (!e) return null; const b = e.getBoundingClientRect(); return [+b.left.toFixed(1), +b.top.toFixed(1), +b.width.toFixed(1), +b.height.toFixed(1)]; };
  const n = s.querySelector('.wujia-store-mobile-strip-name'), role = s.querySelector('.wujia-store-strip-role');
  return {tag: s.tagName, strip: R(s), role: role && role.textContent.trim(), chev: R(s.querySelector('.wujia-store-strip-chevron')),
          ellipsis: n.scrollWidth > n.clientWidth, overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1}; }"""

OVERLAY_OPEN = """() => { const m = document.getElementById('wujiaStoreOverlay');
  return !!m && m.classList.contains('wujia-store-overlay--show'); }"""


def measure(args):
    from playwright.sync_api import sync_playwright
    res = {'base': args.base, 'login': args.login, 'pc': {}, 'mobile': {}, 'tap': {}, 'states': {}}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={'width': 1440, 'height': 900}, has_touch=True)
        if args.readonly:
            res['blocked'] = []
            reads = ('/portal/login', '/portal/notification/unread-count', '/portal/order/cart/count')

            def guard(route, req):
                if req.method in ('GET', 'HEAD') or (req.method == 'POST' and req.url.split('?')[0].endswith(reads)):
                    return route.continue_()
                res['blocked'].append(f'{req.method} {req.url}')
                route.abort()
            ctx.route('**/*', guard)
        page = ctx.new_page()
        login(page, args.base, args.login, args.password)
        for w, h in PC:
            page.set_viewport_size({'width': w, 'height': h})
            for r in PC_ROUTES:
                page.goto(args.base + r, wait_until='load')
                page.wait_for_timeout(args.settle)
                for c in ('0', '4', '12'):
                    res['pc'][f'{w}{r}#{c}'] = page.evaluate(PC_PROBE, c)
        routes = ROUTES + resolve_details(page, args.base)
        for w, h in MOBILE:
            page.set_viewport_size({'width': w, 'height': h})
            for r in routes:
                page.goto(args.base + r, wait_until='load')
                res['mobile'][f'{w}{r}'] = page.evaluate(STRIP_PROBE)
        page.set_viewport_size({'width': 390, 'height': 844})
        page.goto(args.base + '/portal/order', wait_until='load')
        if page.locator('.wujia-store-strip-chevron').count():
            for where, sel in (('code', '.wujia-store-strip-code'), ('name', '.wujia-store-mobile-strip-name'),
                               ('role', '.wujia-store-strip-role'), ('chevron', '.wujia-store-strip-chevron')):
                page.goto(args.base + '/portal/order', wait_until='load')
                page.wait_for_timeout(args.settle)
                page.tap(sel)
                page.wait_for_timeout(400)
                res['tap'][where] = page.evaluate(OVERLAY_OPEN)
            page.goto(args.base + '/portal/order', wait_until='load')
            cdp = ctx.new_cdp_session(page)
            cdp.send('DOM.enable')
            cdp.send('CSS.enable')
            root = cdp.send('DOM.getDocument')['root']['nodeId']
            nid = cdp.send('DOM.querySelector', {'nodeId': root, 'selector': '.wujia-store-mobile-strip'})['nodeId']
            for st in ([], ['active'], ['focus', 'focus-visible']):
                cdp.send('CSS.forcePseudoState', {'nodeId': nid, 'forcedPseudoClasses': st})
                page.wait_for_timeout(400)  # nền có transition
                res['states'][':'.join(st) or 'rest'] = page.evaluate(
                    "() => { const s = getComputedStyle(document.querySelector('.wujia-store-mobile-strip'));"
                    " return [s.backgroundColor, s.outlineStyle, s.outlineWidth]; }")
        browser.close()
    return res


def summary(res):
    pc_bad = [k for k, v in res['pc'].items()
              if any(v.get(i, {}).get('overlap') or any(abs(o) > 0.6 for o in v.get(i, {}).get('off', []))
                     for i in ('cart', 'bell'))
              or not v.get('store', {}).get('inside')]
    mob = {k: v for k, v in res['mobile'].items() if v}
    multi = any(v['chev'] for v in mob.values())
    mob_bad = [k for k, v in mob.items() if v['overflowX'] or not v['role'] or bool(v['chev']) != multi]
    print(f"PC {len(res['pc'])} phép đo, lỗi: {pc_bad or 0}")
    print(f"Mobile {len(mob)}/{len(res['mobile'])} trang có dải ({'có' if multi else 'không'} chevron), lỗi: {mob_bad or 0}")
    if res['tap']:
        print('Bấm mở overlay:', res['tap'], '| trạng thái:', res['states'])
    if 'blocked' in res:
        print('Request bị chặn:', len(res['blocked']))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://127.0.0.1:8032')
    ap.add_argument('--login', default='dung.multi')
    ap.add_argument('--password', default='wujia@test123')
    ap.add_argument('--readonly', action='store_true', help='UAT: chặn mọi request không phải GET, trừ đăng nhập và bộ đếm badge')
    ap.add_argument('--settle', type=int, default=300)
    ap.add_argument('--out', default='wj_shell_g2.json')
    args = ap.parse_args()
    res = measure(args)
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    summary(res)


if __name__ == '__main__':
    main()
