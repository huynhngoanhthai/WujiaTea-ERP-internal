"""Đo cỡ chữ portal (cụm TS — thang chữ một nguồn ở base).

    python3 scripts/qa/wj_type_audit.py css [--save base.json] [--baseline base.json]
    python3 scripts/qa/wj_type_audit.py screens <base_url> <password> <out.json> [--widths 390,1440]
    python3 scripts/qa/wj_type_audit.py diff <before.json> <after.json>

`css`     đếm `font-size` gõ cứng theo file (chữ / icon / chấm đếm / token); `--baseline` báo file nào tăng.
`screens` mở mọi màn portal (chỉ đọc, cần store cookie HCM-01): cỡ chữ từng phần tử, chữ < 12px, tràn ngang,
          lỗi JS, khung cắt chữ. Khảo sát (inspection) ngoài phạm vi.
`diff`    so hai lần `screens`: số cỡ khác nhau và số chữ < 12px theo từng màn.
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICON = re.compile(r'(\s|>)i$|(\s|>)i[\.:\[]|\.fa\b|\.fa-|\.bx|\.ti-|ico\b|-ico|icon|::?before|::?after|svg|chev|feather|-ic\b|__check\b|__tile\b')
# Chỉ chấm đếm số trên icon; badge trạng thái và số đếm cạnh tiêu đề là chữ (chip / caption).
COUNT = re.compile(r'(header|nav|add|cart|qty)-badge|(^|[-_ .])dot\b|-qty\b|thumb|\bcnt\b')
# Phần tử được miễn sàn 12px khi đo trình duyệt: chấm đếm số, ô ảnh thay thế.
EXEMPT_EL = re.compile(r'header-badge|nav-badge|add-badge|row-thumb|row-qty')

PAGES = ['/portal', '/portal/order', '/portal/order/product/{product}', '/portal/order/cart', '/portal/purchase-history',
         '/portal/purchase-history/{history}', '/portal/delivery', '/portal/delivery/{delivery}', '/portal/debt',
         '/portal/debt/pay', '/portal/debt/payment-history', '/portal/reports/orders', '/portal/return',
         '/portal/return/{return}', '/portal/return/new', '/portal/support', '/portal/support/{support}',
         '/portal/support/new', '/portal/notification', '/portal/notification/{notification}', '/portal/knowledge',
         '/portal/knowledge/{knowledge}', '/portal/exam', '/portal/exam/register', '/portal/exam/registration/{exam}',
         '/portal/info-request', '/portal/info-request/{info}', '/portal/info-request/new', '/portal/profile',
         '/portal/change-password', '/portal/franchise-information']
DETAIL = {'product': (r'/portal/order/product/(\d+)', '/portal/order'),
          'history': (r'/portal/purchase-history/(\d+)$', '/portal/purchase-history'),
          'delivery': (r'/portal/delivery/(\d+)$', '/portal/delivery'),
          'return': (r'/portal/return/(\d+)$', '/portal/return'),
          'support': (r'/portal/support/(\d+)$', '/portal/support'),
          'notification': (r'/portal/notification/(\d+)$', '/portal/notification'),
          'knowledge': (r'/portal/knowledge/([a-z0-9-]+)$', '/portal/knowledge'),
          'exam': (r'/portal/exam/registration/(\d+)$', '/portal/exam'),
          'info': (r'/portal/info-request/(\d+)$', '/portal/info-request')}

JS = r"""() => {
 const skip = el => el.closest('.header-navbar,.main-menu,.wujia-mhome-bottomnav,.wujia-mobile-bottomnav,.modal:not(.show),footer,script,style,noscript,.wujia-store-bar,.wujia-store-mobile-strip,.visually-hidden,.sr-only');
 const out = [], seen = new Set(), w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
 while (w.nextNode()) {
  const t = w.currentNode, el = t.parentElement;
  if (!el || seen.has(el) || !t.textContent.trim() || skip(el)) continue;
  const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
  if (!r.width || !r.height || cs.visibility === 'hidden' || cs.display === 'none' || cs.opacity === '0') continue;
  seen.add(el);
  const cls = [...el.classList].filter(c => !/^(d-|m[tbsexy]?-|p[tbsexy]?-|text-(?!muted)|align-|flex|col|row$|g-|w-|h-)/.test(c)).slice(0, 3).join('.');
  out.push({tag: el.tagName.toLowerCase(), cls, fs: parseFloat(cs.fontSize), fw: cs.fontWeight, lh: cs.lineHeight,
            txt: t.textContent.trim().slice(0, 30)});
 }
 const clip = [];
 for (const e of (document.querySelector('.content-wrapper') || document.body).querySelectorAll('*')) {
  if (e.closest('.modal:not(.show),.apexcharts-canvas,svg,select,.visually-hidden,.sr-only')) continue;
  const cs = getComputedStyle(e);
  if (cs.display === 'none' || cs.display === 'inline' || !e.clientHeight || ['auto', 'scroll'].includes(cs.overflowY)) continue;
  if (cs.webkitLineClamp && cs.webkitLineClamp !== 'none') continue;
  if (/wj-pagination__label/.test(e.className)) continue;
  if (e.scrollHeight > e.clientHeight + 2 && e.innerText.trim())
   clip.push({cls: e.tagName.toLowerCase() + '.' + [...e.classList].slice(0, 2).join('.'), h: e.clientHeight, sh: e.scrollHeight});
 }
 const h1 = [...document.querySelectorAll('h1')].filter(e => e.offsetParent && !e.classList.contains('visually-hidden')).length;
 return {items: out, clip: clip.slice(0, 10), h1, ovf: document.documentElement.scrollWidth > innerWidth};
}"""


def css_files(root=ROOT):
    files = sorted(glob.glob(os.path.join(root, 'base/wujia_portal_layout/static/assets/css/_*.css')))
    files += sorted(f for f in glob.glob(os.path.join(root, 'portal/wujia_portal_*/static/src/**/*.css'), recursive=True)
                    if 'inspection' not in f)
    return [f for f in files if not f.endswith('_variables.css')]


def count_css(root=ROOT):
    """{file: {text, icon, count, token}} — dùng chung cho lệnh `css` và test chặn tăng của layout."""
    report = {}
    for path in css_files(root):
        css = re.sub(r'/\*.*?\*/', '', open(path, encoding='utf-8').read(), flags=re.S)
        c = collections.Counter()
        for sel, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
            sel = ' '.join(sel.split())
            for value in re.findall(r'font-size\s*:\s*([^;}]+)', body):
                c['token' if 'var(' in value else 'icon' if ICON.search(sel) else 'count' if COUNT.search(sel) else 'text'] += 1
        report[os.path.relpath(path, root)] = dict(c)
    return report


def cmd_css(args):
    report = count_css()
    total = collections.Counter()
    for rel, c in report.items():
        total.update(c)
        if c.get('text') or c.get('icon') or c.get('count'):
            print(f"{rel:72} text {c.get('text', 0):4} icon {c.get('icon', 0):3} count {c.get('count', 0):3} token {c.get('token', 0):3}")
    print('TOTAL', dict(total))
    if args.save:
        json.dump(report, open(args.save, 'w'), indent=1, sort_keys=True)
    if args.baseline:
        base = json.load(open(args.baseline))
        worse = [(rel, base.get(rel, {}).get('text', 0), c.get('text', 0)) for rel, c in report.items()
                 if c.get('text', 0) > base.get(rel, {}).get('text', 0)]
        for rel, a, b in worse:
            print(f'TĂNG {rel}: {a} -> {b}')
        sys.exit(1 if worse else 0)


def call_kw(page, base, model, method, args):
    r = page.evaluate('''async ([u, b]) => (await fetch(u, {method: 'POST', headers: {'Content-Type': 'application/json'},
                         body: JSON.stringify(b)})).json()''',
                      [base + '/web/dataset/call_kw', {'jsonrpc': '2.0', 'method': 'call',
                       'params': {'model': model, 'method': method, 'args': args, 'kwargs': {}}}])
    if 'error' in r:
        raise SystemExit(r['error'])
    return r['result']


def cmd_screens(args):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from wj_measure import login
    from playwright.sync_api import sync_playwright
    base = args.base.rstrip('/')
    host = re.sub(r'^https?://', '', base).split(':')[0].split('/')[0]
    res = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for w in [int(x) for x in args.widths.split(',')]:
            ctx = browser.new_context(viewport={'width': w, 'height': 900})
            page = ctx.new_page()
            errs = []
            page.on('pageerror', lambda e: errs.append(str(e)[:120]))
            login(page, base, args.user, args.password)
            sid = call_kw(page, base, 'wujia.franchise.management', 'search', [[['code', '=', args.store]]])[0]
            ctx.add_cookies([{'name': 'wujia_active_franchise_id', 'value': str(sid), 'domain': host, 'path': '/'}])
            ids = {}
            for key, (pat, lst) in DETAIL.items():
                page.goto(base + lst, wait_until='load')
                page.wait_for_timeout(800)
                for href in page.eval_on_selector_all('a[href]', 'as => as.map(a => a.getAttribute("href"))'):
                    m = re.search(pat, re.sub(r'^https?://[^/]+', '', href or '').split('?')[0])
                    if m:
                        ids[key] = m.group(1)
                        break
            for url in PAGES:
                key = re.search(r'\{(\w+)\}', url)
                if key and key.group(1) not in ids:
                    res[f'{url}@{w}'] = None
                    continue
                errs.clear()
                st = page.goto(base + url.format(**ids), wait_until='load')
                page.wait_for_timeout(900)
                d = page.evaluate(JS)
                d.update(url=url.format(**ids), status=st.status if st else 0, errors=list(errs))
                d['small'] = [i['tag'] + '.' + i['cls'] for i in d['items'] if i['fs'] < 12 and not EXEMPT_EL.search(i['cls'])]
                res[f'{url}@{w}'] = d
                flag = ' '.join(x for x in ('OVF' if d['ovf'] else '', f"<12×{len(d['small'])}" if d['small'] else '',
                                            'JS' if d['errors'] else '', f"clip×{len(d['clip'])}" if d['clip'] else '') if x)
                print(w, d['url'], d['status'], 'sizes', sorted({i['fs'] for i in d['items']}), flag, flush=True)
            ctx.close()
    json.dump(res, open(args.out, 'w'), ensure_ascii=False)
    bad = [k for k, v in res.items() if v and (v['ovf'] or v['small'] or v['errors'] or v['status'] != 200)]
    print(f'{sum(1 for v in res.values() if v)} ô đo · {len(bad)} ô lỗi', *bad, sep='\n')


def cmd_diff(args):
    a, b = json.load(open(args.before)), json.load(open(args.after))
    print(f"{'màn@khổ':48} {'cỡ trước':>8} {'cỡ sau':>7} {'<12 trước':>9} {'<12 sau':>8}")
    for key in a:
        va, vb = a.get(key), b.get(key)
        if not va or not vb:
            continue
        small = lambda v: len([i for i in v['items'] if i['fs'] < 12 and not EXEMPT_EL.search(i['cls'])])
        print(f"{key:48} {len({i['fs'] for i in va['items']}):8} {len({i['fs'] for i in vb['items']}):7} "
              f"{small(va):9} {small(vb):8}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('css')
    c.add_argument('--save')
    c.add_argument('--baseline')
    s = sub.add_parser('screens')
    s.add_argument('base')
    s.add_argument('password')
    s.add_argument('out')
    s.add_argument('--widths', default='390,1440')
    s.add_argument('--user', default='admin')
    s.add_argument('--store', default='HCM-01')
    d = sub.add_parser('diff')
    d.add_argument('before')
    d.add_argument('after')
    args = ap.parse_args()
    {'css': cmd_css, 'screens': cmd_screens, 'diff': cmd_diff}[args.cmd](args)


if __name__ == '__main__':
    main()
