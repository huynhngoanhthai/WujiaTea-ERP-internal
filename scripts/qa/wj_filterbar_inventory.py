#!/usr/bin/env python3
"""Kiểm kê thanh lọc portal theo CẤU TRÚC — chân lý của acceptance FB-10.

Bản gốc của E4a nằm ở `scratchpad/e4/` và đã mất, nên lần này script sống
trong repo. Đếm bằng `lxml` (node `<form method="get">` có hậu duệ
`input`/`select`/`textarea`), KHÔNG bằng grep tên lớp — bài học D4e: grep thô
bắt cả tên con BEM nên ra 36 trong khi sự thật là 7.

FB-10 = "không tự thêm/bớt điều kiện giữa PC/mobile": chạy script trước và sau
khi sửa, bộ `name` của từng màn phải giống hệt.

    python3 scripts/qa/wj_filterbar_inventory.py            # bảng chi tiết
    python3 scripts/qa/wj_filterbar_inventory.py --md       # bảng markdown
    python3 scripts/qa/wj_filterbar_inventory.py --json f.json
    python3 scripts/qa/wj_filterbar_inventory.py --diff before.json
"""
import argparse
import json
import os
import re
import sys

from lxml import etree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wj_paths  # noqa: E402

# Hai form của nhóm Khảo sát là defer (luật 08/09); form cỡ trang của
# Pagination (E3) không phải Filter. Vẫn liệt kê, chỉ gắn cờ.
DEFER_MODULES = ('wujia_portal_inspection', 'wujia_franchise_inspection')
NOT_FILTER_CLASSES = ('wj-pagination__size-form',)

# Định nghĩa component, không phải call site.
COMPONENT_FILES = ('base/wujia_portal_layout/views/wj_filter_bar.xml',)

CONTROL_TAGS = ('input', 'select', 'textarea')


def _attr(el, name):
    """Giá trị thô của attr, chấp nhận cả biến thể QWeb t-att / t-attf."""
    for key in (name, 't-att-' + name, 't-attf-' + name):
        if el.get(key) is not None:
            return el.get(key)
    return None


def _text(el):
    return re.sub(r'\s+', ' ', ''.join(el.itertext())).strip()


def _classes(el):
    raw = (_attr(el, 'class') or '')
    return [c for c in re.split(r'\s+', raw) if c and '#{' not in c]


def _viewport(el):
    """PC hay mobile — suy từ tổ tiên mang d-none/d-lg-none (bố cục portal)."""
    pc = mob = False
    node = el
    while node is not None and node.tag is not etree.Comment:
        cls = ' '.join(_classes(node))
        if 'd-lg-none' in cls or 'wujia-mpage' in cls:
            mob = True
        if re.search(r'\bd-none\b.*\bd-lg-', cls):
            pc = True
        node = node.getparent()
    if pc and not mob:
        return 'pc'
    if mob and not pc:
        return 'm'
    return 'pc+m'


def _control(el):
    tag = etree.QName(el).localname
    name = _attr(el, 'name')
    if not name:
        return None
    kind = tag
    if tag == 'input':
        kind = (_attr(el, 'type') or 'text').lower()
    return {
        'name': name.strip(),
        'kind': kind,
        'label': (_attr(el, 'aria-label') or _attr(el, 'placeholder') or '') .strip(),
    }


def scan_file(path):
    try:
        tree = etree.parse(path)
    except etree.XMLSyntaxError as exc:              # noqa: BLE001
        print('!! %s: %s' % (path, exc), file=sys.stderr)
        return []
    out = []
    for form in tree.iter('form'):
        # HTML mặc định là GET khi thiếu `method` — 2 form Khảo sát nằm ở đây.
        if (_attr(form, 'method') or 'get').lower() != 'get':
            continue
        controls = []
        for el in form.iter(*CONTROL_TAGS):
            ctl = _control(el)
            if ctl:
                controls.append(ctl)
        if not controls:
            continue
        submit = reset = ''
        for btn in form.iter('button'):
            if (_attr(btn, 'type') or '').lower() == 'submit':
                submit = _text(btn) or '(icon)'
        for a in form.iter('a'):
            cls = ' '.join(_classes(a))
            if 'secondary' in cls or 'reset' in cls.lower():
                reset = _text(a)
        classes = _classes(form)
        rel = os.path.relpath(path, ROOT)
        module = wj_paths.module_of(path) or '?'
        flag = ''
        if rel in COMPONENT_FILES:
            flag = 'component'
        elif module in DEFER_MODULES:
            flag = 'defer'
        elif any(c in NOT_FILTER_CLASSES for c in classes):
            flag = 'không phải Filter'
        out.append({
            'file': rel,
            'line': form.sourceline,
            'module': module,
            'vp': _viewport(form),
            'classes': classes,
            'action': _attr(form, 'action') or '',
            'params': controls,
            'submit': submit,
            'reset': reset,
            'flag': flag,
            # Chip do part/slot render ⇒ chỉ đếm node có class chứa 'chip'.
            'chips': sum(1 for el in form.iter()
                         if el.tag is not etree.Comment
                         and any('chip' in c for c in _classes(el))),
        })
    return out


def collect():
    rows = []
    for mod_dir in wj_paths.iter_modules():
        for base, _dirs, files in os.walk(mod_dir):
            for fn in sorted(files):
                if fn.endswith('.xml') and '/static/' not in base.replace(os.sep, '/'):
                    rows.extend(scan_file(os.path.join(base, fn)))
    rows.sort(key=lambda r: (r['file'], r['line']))
    return rows


def key(row):
    return '%s:%s' % (row['file'], row['line'])


def render(rows, as_md):
    real = [r for r in rows if not r['flag']]
    if as_md:
        print('| Màn / file | Dòng | VP | Họ class | Điều kiện | Chip | Submit | Reset | Cờ |')
        print('|---|---|---|---|---|---|---|---|---|')
        for r in rows:
            cond = '<br>'.join('`%s` · %s' % (p['name'], p['kind']) for p in r['params'])
            print('| `%s` | %s | %s | `%s` | %s | %s | %s | %s | %s |' % (
                r['file'], r['line'], r['vp'], ' '.join(r['classes'])[:40] or '—',
                cond, r['chips'] or '—', r['submit'] or '—', r['reset'] or '—',
                r['flag'] or ''))
    else:
        for r in rows:
            print('%-78s %5s  %-4s %s' % (r['file'], r['line'], r['vp'],
                                          ' '.join(r['classes'])[:46]))
            print('        params: %s' % ', '.join(
                '%s(%s)' % (p['name'], p['kind']) for p in r['params']))
            print('        submit=%r reset=%r chips=%s %s' % (
                r['submit'], r['reset'], r['chips'], r['flag']))
    print('\n%d form GET có control · %d thanh lọc thật (bỏ %d defer/không-phải-filter)'
          % (len(rows), len(real), len(rows) - len(real)))


def diff(rows, before_path):
    before = {key(r): r for r in json.load(open(before_path))}
    now = {key(r): r for r in rows}
    bad = 0
    for k in sorted(set(before) | set(now)):
        b, n = before.get(k), now.get(k)
        if not b or not n:
            # Dòng dịch chuyển là bình thường khi sửa view ⇒ so theo action+vp.
            continue
        bp = [p['name'] for p in b['params']]
        np_ = [p['name'] for p in n['params']]
        if sorted(bp) != sorted(np_):
            bad += 1
            print('FB-10 LỆCH %s\n    trước: %s\n    sau  : %s' % (k, bp, np_))
    # So theo route để bắt cả trường hợp form bị dời dòng.
    def by_route(src):
        agg = {}
        for r in src.values():
            if r['flag']:
                continue
            agg.setdefault((r['action'], r['vp']), set()).update(
                p['name'] for p in r['params'])
        return agg
    ba, na = by_route(before), by_route(now)
    for k in sorted(set(ba) | set(na)):
        if ba.get(k, set()) != na.get(k, set()):
            bad += 1
            print('FB-10 LỆCH THEO ROUTE %s\n    trước: %s\n    sau  : %s'
                  % (k, sorted(ba.get(k, [])), sorted(na.get(k, []))))
    print('\nFB-10: %s' % ('ĐẠT — 0 lệch' if not bad else '%d lệch' % bad))
    return bad



# --------------------------------------------------------------------------
# Chế độ RENDER — chân lý thật của FB-10.
#
# Quét XML chỉ thấy call site CHƯA migrate: khi màn gọi `t-call` component thì
# `<form>` biến mất khỏi file màn. Muốn so "điều kiện trước = sau" thì phải đọc
# DOM đã render của từng route × khổ.
# --------------------------------------------------------------------------

ROUTES_PC = [
    '/portal/purchase-history', '/portal/delivery', '/portal/return',
    '/portal/support', '/portal/knowledge', '/portal/info-request',
    '/portal/notification', '/portal/exam', '/portal/reports/orders',
    '/portal/order', '/portal/debt', '/portal/debt/payment-history',
]

RENDER_JS = r"""
() => {
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
  };
  const out = [];
  document.querySelectorAll('form').forEach((f) => {
    const m = (f.getAttribute('method') || 'get').toLowerCase();
    if (m !== 'get' || !vis(f)) return;
    const params = [];
    f.querySelectorAll('input, select, textarea').forEach((el) => {
      if (!el.name) return;
      const type = (el.getAttribute('type') || el.tagName.toLowerCase()).toLowerCase();
      params.push(el.name + '(' + type + ')');
    });
    if (!params.length) return;
    let submit = '', reset = '';
    f.querySelectorAll('button, a').forEach((b) => {
      const t = (b.innerText || '').replace(/\s+/g, ' ').trim();
      if (b.tagName === 'BUTTON' && (b.type || '').toLowerCase() === 'submit') {
        submit = t || '(icon)';
      } else if (b.tagName === 'A' && /secondary|reset/i.test(b.className)) {
        reset = t;
      }
    });
    const r = f.getBoundingClientRect();
    out.push({
      cls: (f.className || '').toString().trim(),
      id: f.id || '',
      action: (f.getAttribute('action') || ''),
      params: params,
      submit: submit,
      reset: reset,
      chips: f.querySelectorAll('[class*="chip"]').length,
      h: Math.round(r.height * 100) / 100,
      rows: new Set([...f.querySelectorAll('input:not([type=hidden]), select, button[type=submit]')]
              .filter(vis).map(e => Math.round(e.getBoundingClientRect().top))).size,
      ctl: [...f.querySelectorAll('input:not([type=hidden]), select')].filter(vis).map(e => {
        const b = e.getBoundingClientRect();
        // Vùng chạm = WRAPPER <label> (Q1: hộp 38 nằm trong label 44). `closest` với
        // danh sách selector trả về TỔ TIÊN GẦN NHẤT khớp bất kỳ cái nào — với ô ngày
        // đó là `__box` 38, nên phải hỏi <label> trước, nếu không số chạm báo thiếu.
        const box = e.closest('label')
                 || e.closest('.wj-filter-search-field, .wj-filter-date__box') || e;
        const bb = box.getBoundingClientRect();
        return {n: e.name, h: Math.round(b.height * 100) / 100,
                hit: Math.round(bb.height * 100) / 100,
                top: Math.round(bb.top)};
      }),
    });
  });
  return out;
}
"""


def render_scan(args):
    """Đọc DOM thật: trả {route: {vp: [form...]}}."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from playwright.sync_api import sync_playwright
    from wj_measure import login

    out = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_context(viewport={'width': 1440, 'height': 900}).new_page()
        login(page, args.base, args.portal_login, args.password)
        for w in args.widths:
            page.set_viewport_size({'width': w, 'height': 900})
            for route in args.routes:
                page.goto('%s%s' % (args.base, route), wait_until='load')
                page.wait_for_timeout(args.settle)
                landed = page.url.split(args.base)[-1].split('?')[0]
                # Route có thể mang sẵn query (ép màn ra khỏi trạng thái rỗng) —
                # so phần path, nếu không mọi route như vậy đều bị báo 'redirect'.
                if landed.rstrip('/') != route.split('?')[0].rstrip('/'):
                    out.setdefault(route, {})['%s' % w] = 'redirect:%s' % landed
                    continue
                out.setdefault(route, {})['%s' % w] = page.evaluate(RENDER_JS)
        browser.close()
    return out


def render_report(data):
    total = 0
    for route in sorted(data):
        for w in sorted(data[route], key=int):
            forms = data[route][w]
            if isinstance(forms, str):
                print('  ~ %-32s %4s  %s' % (route, w, forms))
                continue
            for f in forms:
                total += 1
                print('%-32s %4s  %-46s h=%-6s hàng=%s' % (
                    route, w, (f['cls'] or f['id'])[:46], f['h'], f['rows']))
                print('%42s params: %s' % ('', ', '.join(f['params'])))
                print('%42s submit=%r reset=%r chips=%s' % (
                    '', f['submit'], f['reset'], f['chips']))
                if f['ctl']:
                    print('%42s control: %s' % ('', ' · '.join(
                        '%s %s/%s@%s' % (c['n'], c['h'], c['hit'], c['top'])
                        for c in f['ctl'])))
    print('\n%d form GET nhìn thấy được trên %d route' % (total, len(data)))


def render_diff(before_path, now):
    before = json.load(open(before_path))
    bad = 0
    for route in sorted(set(before) | set(now)):
        for w in sorted(set(before.get(route, {})) | set(now.get(route, {})), key=int):
            b = before.get(route, {}).get(w)
            n = now.get(route, {}).get(w)
            if isinstance(b, str) or isinstance(n, str) or b is None or n is None:
                if b != n:
                    bad += 1
                    print('LỆCH TRẠNG THÁI %s @%s: trước=%r sau=%r' % (route, w, b, n))
                continue
            bp = sorted(p.split('(')[0] for f in b for p in f['params'])
            np_ = sorted(p.split('(')[0] for f in n for p in f['params'])
            if bp != np_:
                bad += 1
                print('FB-10 LỆCH %s @%s\n    trước: %s\n    sau  : %s' % (route, w, bp, np_))
    print('\nFB-10 (render): %s' % ('ĐẠT — 0 lệch' if not bad else '%d lệch' % bad))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--md', action='store_true')
    ap.add_argument('--json')
    ap.add_argument('--diff', metavar='BEFORE.json')
    ap.add_argument('--base', help='đo DOM thật thay vì quét XML')
    ap.add_argument('--portal-login', default='em.hcm')
    ap.add_argument('--password', default='wujia@test123')
    ap.add_argument('--routes', nargs='*', default=None)
    ap.add_argument('--widths', nargs='*', type=int, default=[1440, 1024, 992, 391])
    ap.add_argument('--settle', type=int, default=450)
    args = ap.parse_args()

    if args.base:
        args.routes = args.routes or ROUTES_PC
        data = render_scan(args)
        if args.json:
            json.dump(data, open(args.json, 'w'), ensure_ascii=False, indent=1)
            print('→ %s' % args.json)
        if args.diff:
            sys.exit(1 if render_diff(args.diff, data) else 0)
        if not args.json:
            render_report(data)
        return

    rows = collect()
    if args.json:
        json.dump(rows, open(args.json, 'w'), ensure_ascii=False, indent=1)
        print('→ %s (%d form)' % (args.json, len(rows)))
    if args.diff:
        sys.exit(1 if diff(rows, args.diff) else 0)
    if not args.json:
        render(rows, args.md)


if __name__ == '__main__':
    main()
