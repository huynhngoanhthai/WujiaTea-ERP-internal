"""WJ-ORD-028 (G5) — đo hộp xác nhận gửi đơn ở 6 khổ, CHỈ mở rồi Hủy. An toàn trên UAT.

Mọi request tới `/portal/order/submit` bị chặn ngay trong trình duyệt (route.abort), nên kể cả bấm nhầm
Xác nhận cũng không tạo đơn. Giỏ phải có sẵn hàng (script không thêm hàng; `--fill` chỉ dùng ở local).

Mỗi khổ: bấm "Gửi đơn đặt hàng" → hộp mở, 0 request gửi đơn; panel nằm trong viewport, không tràn ngang,
2 nút cao ≥ 40 (mobile ≥ 44), focus ở Hủy, Tab/Shift+Tab không thoát hộp → Hủy → hộp đóng, focus về nút mở.

  python scripts/qa/wj_order_confirm_probe.py --base http://127.0.0.1:8055 --login dung.multi --fill --shots DIR
  python scripts/qa/wj_order_confirm_probe.py --base https://dev.wujiatea.com.vn --login admin --password …
"""
import argparse
import json
import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(__file__))
from wj_density import login  # noqa: E402
from wj_order_confirm import MODAL_PROBE, fill_cart  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

CASES = [
    ('m360', (360, 800), '/portal/order/cart', '.wujia-mcart-submit'),
    ('m390', (390, 844), '/portal/order/cart', '.wujia-mcart-submit'),
    ('m430', (430, 932), '/portal/order/cart', '.wujia-mcart-submit'),
    ('pc1440-cart', (1440, 900), '/portal/order/cart', '.wj-pc-cart-submit'),
    ('pc1440-order', (1440, 900), '/portal/order', '.wj-pc-cart-submit'),
    ('pc1024-cart', (1024, 768), '/portal/order/cart', '.wj-pc-cart-submit'),
    ('pc992-cart', (992, 768), '/portal/order/cart', '.wj-pc-cart-submit'),
    ('pc992-order', (992, 768), '/portal/order', '.wj-pc-cart-submit'),
]


def run(br, args, name, vp, path, opener):
    ctx = br.new_context(viewport={'width': vp[0], 'height': vp[1]})
    page = ctx.new_page()
    hits = []
    page.route('**/portal/order/submit*', lambda r: (hits.append(r.request.url), r.abort()))
    login(page, args.base, args.login, args.password)
    page.goto(args.base + path, wait_until='load')
    page.wait_for_timeout(400)
    btn = page.locator(opener)
    if not btn.count() or not btn.first.is_visible() or btn.first.is_disabled():
        ctx.close()
        return {'case': name, 'skip': 'không có nút gửi (giỏ trống / ngoài khung giờ)'}
    btn.first.click()
    page.wait_for_timeout(350)
    m = page.evaluate(MODAL_PROBE)
    focus_trap = []
    for key in ('Tab', 'Tab', 'Shift+Tab', 'Shift+Tab'):
        page.keyboard.press(key)
        focus_trap.append(page.evaluate("() => (document.activeElement.dataset || {}).wjOcAction || null"))
    if args.shots:
        page.screenshot(path=os.path.join(args.shots, f'{name}.png'))
    page.locator("[data-wj-oc-action='cancel']").click()
    page.wait_for_timeout(250)
    closed = not page.evaluate(MODAL_PROBE)['open']
    focus_back = page.evaluate("() => document.activeElement && document.activeElement.hasAttribute('data-wj-confirm-open')")
    min_h = 44 if vp[0] < 992 else 40
    chk = {
        'open': m['open'],
        'no_submit_request': not hits,
        'in_viewport': m['open'] and m['panel'][0] >= 0 and m['panel'][1] >= 0
                       and m['panel'][2] <= m['vw'] and m['panel'][3] <= m['vh'],
        'no_overflow_x': m['open'] and not m['overflowX'],
        'btn_height': m['open'] and all(b['h'] >= min_h for b in m['btns']),
        'focus_cancel': m.get('focus') == 'cancel',
        'focus_trapped': all(f in ('cancel', 'confirm') for f in focus_trap),
        'cancel_closes': closed,
        'focus_back': bool(focus_back),
    }
    ctx.close()
    return {'case': name, 'ok': all(chk.values()), 'checks': chk, 'modal': m, 'trap': focus_trap}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://127.0.0.1:8055')
    ap.add_argument('--login', default='dung.multi')
    ap.add_argument('--password', default='wujia@test123')
    ap.add_argument('--fill', action='store_true', help='thêm 2 sản phẩm vào giỏ trước khi đo (CHỈ local)')
    ap.add_argument('--shots')
    ap.add_argument('--out')
    args = ap.parse_args()
    if args.fill and urlparse(args.base).hostname not in ('127.0.0.1', 'localhost'):
        sys.exit('--fill ghi giỏ — chỉ dùng ở local.')
    if args.shots:
        os.makedirs(args.shots, exist_ok=True)
    out = []
    with sync_playwright() as p:
        br = p.chromium.launch()
        if args.fill:
            ctx = br.new_context()
            pg = ctx.new_page()
            login(pg, args.base, args.login, args.password)
            fill_cart(pg, args.base)
            ctx.close()
        for case in CASES:
            r = run(br, args, *case)
            out.append(r)
            if 'skip' in r:
                print(f"SKIP {r['case']:13} {r['skip']}")
                continue
            m = r['modal']
            bad = [k for k, v in r['checks'].items() if not v]
            print(f"{'OK ' if r['ok'] else 'FAIL'} {r['case']:13} panel={m.get('panel')} btn_h={[b['h'] for b in m.get('btns', [])]} "
                  f"{m.get('lines')}mh/{m.get('qty')}sl/{m.get('total')} trap={r['trap']} {'bad=' + ','.join(bad) if bad else ''}")
        br.close()
    if args.out:
        with open(args.out, 'w') as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
    done = [r for r in out if 'skip' not in r]
    print('== ALL OK' if done and all(r['ok'] for r in done) else '== CÓ FAIL / KHÔNG ĐO ĐƯỢC')


if __name__ == '__main__':
    main()
