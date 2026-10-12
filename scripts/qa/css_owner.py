#!/usr/bin/env python3
"""Ai sở hữu CSS portal — đo cho cụm F (F2/F3 dời CSS màn, F4 duyệt rule đè component).

    python3 scripts/qa/css_owner.py --layout-domain            # nhóm class trong portal_layout theo module dùng
    python3 scripts/qa/css_owner.py --overrides                # rule module portal chạm component chung
    python3 scripts/qa/css_owner.py --layout-domain --overrides --json out.json
    python3 scripts/qa/css_owner.py --who wujia-msheet-item     # class này dùng ở đâu

Luật phân loại (--layout-domain), mỗi nhóm class (gốc BEM: bỏ `__x`, `--x`) khai trong wujia_portal_layout/static/assets/css/_*.css:
  - tập module dùng = module portal (khác layout) có class đó trong view XML (lxml: mọi thuộc tính
    *class*, t-value/t-att-* chứa chuỗi), JS static/src, hoặc chuỗi Python controllers/;
  - dùng ở ≥2 module  ⇒ `component` (giữ ở layout);
  - dùng ở đúng 1     ⇒ CSS của màn module đó (ứng viên dời ra ở F2/F3);
  - chỉ layout dùng   ⇒ `khung` (shell layout tự dùng);
  - không ai dùng     ⇒ `orphan`.
Tiền tố động (`t-attf-class="wujia-kpi-icon-{{x}}"`) khớp mọi class bắt đầu bằng tiền tố đó.

--overrides: rule CSS trong wujia_portal_* (trừ layout + code anh Thái) mà phần tử ĐÍCH của selector (compound
cuối, kể cả `:not(...)`) mang class `component` hoặc `khung` — class ở tổ tiên (`.wujia-mpage .x`) chỉ là ngữ cảnh ⇒ tách thuộc tính thành "bố cục" (LAYOUT_PROPS) và "đổi dáng" (còn lại). Chỉ rule có ≥1
thuộc tính đổi dáng mới vào danh sách đổi dáng.
"""
import argparse
import json
import pathlib
import re
import sys
from collections import defaultdict

from lxml import etree

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import wj_paths  # noqa: E402
LAYOUT = 'wujia_portal_layout'
LAYOUT_CSS = wj_paths.module_path(LAYOUT) / 'static/assets/css'
THAI = {'wujia_portal_inspection'}

TOKEN = re.compile(r'(?<![\w-])((?:wj|wujia)-[A-Za-z0-9_-]*)')
SEL_CLASS = re.compile(r'\.((?:wj|wujia)-[A-Za-z0-9_-]+)')
LAYOUT_PROPS = re.compile(
    r'^(margin|padding|gap|row-gap|column-gap|flex|grid|width|min-width|max-width|height|min-height|max-height'
    r'|position|top|right|bottom|left|inset|order|align|justify|place|display|z-index|overflow|box-sizing)(-|$)')


# ---------- CSS ----------

def parse_css(text):
    """[(line, selector, [(prop, value)], media)] — bỏ comment, đi vào @media/@supports, bỏ @keyframes/@font-face."""
    text = re.sub(r'/\*.*?\*/', lambda m: re.sub(r'[^\n]', ' ', m.group(0)), text, flags=re.S)
    rules = []

    def walk(i, end, media):
        buf_start = i
        while i < end:
            c = text[i]
            if c == '{':
                head = text[buf_start:i].strip()
                depth, j = 1, i + 1
                while j < end and depth:
                    depth += {'{': 1, '}': -1}.get(text[j], 0)
                    j += 1
                line = text.count('\n', 0, buf_start + len(text[buf_start:i]) - len(text[buf_start:i].lstrip())) + 1
                if head.startswith('@media') or head.startswith('@supports') or head.startswith('@layer'):
                    walk(i + 1, j - 1, (media + ' ' + head).strip())
                elif not head.startswith('@'):
                    decls = []
                    for d in text[i + 1:j - 1].split(';'):
                        if ':' in d:
                            p, v = d.split(':', 1)
                            decls.append((p.strip().lower(), v.strip()))
                    rules.append((line, ' '.join(head.split()), decls, media))
                i = buf_start = j
                continue
            if c == ';':
                buf_start = i + 1
            i += 1

    walk(0, len(text), '')
    return rules


def bem_root(cls):
    return re.split(r'__|--', cls, 1)[0]


# ---------- nơi dùng ----------

def module_of(path):
    return wj_paths.module_of(path)


def tokens_in(s):
    return set(TOKEN.findall(s or ''))


def usage_index():
    """{module: set(token)} — token kết thúc bằng '-' là tiền tố động."""
    used = defaultdict(set)
    for mod_dir in wj_paths.iter_modules('wujia_portal_*'):
        mod = mod_dir.name
        for xml in mod_dir.glob('views/**/*.xml'):
            try:
                tree = etree.parse(str(xml))
            except etree.XMLSyntaxError:
                used[mod] |= tokens_in(xml.read_text(encoding='utf-8'))
                continue
            for el in tree.iter():
                if not isinstance(el.tag, str):
                    continue
                for k, v in el.attrib.items():
                    if 'class' in k or k.startswith('t-att') or k in ('t-value', 't-set', 'expr'):
                        used[mod] |= tokens_in(v)
                if el.tag == 'attribute' and el.get('name') == 'class':
                    used[mod] |= tokens_in(el.text)
        for js in mod_dir.glob('static/src/**/*.js'):
            used[mod] |= tokens_in(js.read_text(encoding='utf-8', errors='ignore'))
        if mod == LAYOUT:
            for js in mod_dir.glob('static/assets/js/wujia_*.js'):
                used[mod] |= tokens_in(js.read_text(encoding='utf-8', errors='ignore'))
        for py in mod_dir.glob('controllers/**/*.py'):
            used[mod] |= tokens_in(py.read_text(encoding='utf-8'))
    return used


def users_of(cls, used):
    out = set()
    for mod, toks in used.items():
        if cls in toks or any(t.endswith('-') and len(t) > 4 and cls.startswith(t) for t in toks):
            out.add(mod)
    return out


# ---------- báo cáo ----------

def layout_domain(used):
    defs, members = defaultdict(list), defaultdict(set)
    for css in sorted(LAYOUT_CSS.glob('_*.css')):
        for line, sel, _decls, _m in parse_css(css.read_text(encoding='utf-8')):
            for cls in set(SEL_CLASS.findall(sel)):
                root = bem_root(cls)
                members[root].add(cls)
                if f'{css.name}:{line}' not in defs[root]:
                    defs[root].append(f'{css.name}:{line}')
    rows = []
    for cls in sorted(defs):
        users = set().union(*(users_of(c, used) for c in members[cls] | {cls}))
        others = sorted(users - {LAYOUT})
        if len(others) >= 2:
            owner = 'component'
        elif len(others) == 1:
            owner = others[0]
        elif LAYOUT in users:
            owner = 'khung'
        else:
            owner = 'orphan'
        rows.append({'class': cls, 'owner': owner, 'users': sorted(users), 'members': sorted(members[cls]), 'defs': defs[cls]})
    return rows


def split_top(sel, seps):
    """Tách selector ở ký tự trong `seps` nằm ngoài ngoặc."""
    parts, depth, buf = [], 0, ''
    for ch in sel:
        depth += {'(': 1, ')': -1}.get(ch, 0)
        if depth == 0 and ch in seps:
            parts.append(buf)
            buf = ''
        else:
            buf += ch
    return [x.strip() for x in parts + [buf] if x.strip()]


def subject(sel):
    """Compound cuối có class — phần tử nhận style (`.wj-pc-table thead th` ⇒ `.wj-pc-table`); tổ tiên xa hơn chỉ là ngữ cảnh."""
    for comp in reversed(split_top(sel, ' >+~')):
        if '.' in comp:
            return re.sub(r'::?(before|after|placeholder|marker)\b.*$', '', comp)
    return ''


def overrides(domain):
    shared = {c for r in domain if r['owner'] in ('component', 'khung') for c in r['members']}
    out = []
    for mod_dir in wj_paths.iter_modules('wujia_portal_*'):
        mod = mod_dir.name
        if mod == LAYOUT or mod in THAI:
            continue
        for css in sorted(mod_dir.glob('static/src/**/*.css')):
            for line, sel, decls, media in parse_css(css.read_text(encoding='utf-8')):
                hit = sorted(set().union(*(SEL_CLASS.findall(subject(x)) for x in split_top(sel, ','))) & shared)
                if not hit or not decls:
                    continue
                style = sorted({p for p, _ in decls if not p.startswith('--') and not LAYOUT_PROPS.match(p)})
                layout = sorted({p for p, _ in decls if LAYOUT_PROPS.match(p)})
                out.append({'module': mod, 'at': f'{css.name}:{line}', 'selector': sel, 'media': media,
                            'components': hit, 'kind': 'đổi dáng' if style else 'bố cục',
                            'style_props': style, 'layout_props': layout})
    return out


def print_domain(rows):
    by = defaultdict(list)
    for r in rows:
        by[r['owner']].append(r)
    total = len(rows)
    screen = {k: v for k, v in by.items() if k not in ('component', 'khung', 'orphan')}
    print(f'# --layout-domain — {total} nhóm class (gốc BEM) trong {LAYOUT} _*.css\n')
    print('| Nhóm | Số nhóm class |\n|---|---|')
    for k in sorted(screen, key=lambda k: -len(screen[k])):
        print(f'| `{k}` | {len(screen[k])} |')
    print(f'| **CSS của 1 màn (cộng)** | **{sum(len(v) for v in screen.values())}** |')
    for k in ('component', 'khung', 'orphan'):
        print(f'| {k} | {len(by.get(k, []))} |')
    for k in sorted(screen, key=lambda k: -len(screen[k])):
        print(f'\n### → `{k}` — {len(screen[k])}\n')
        for r in screen[k]:
            more = f" (+{len(r['defs']) - 4})" if len(r['defs']) > 4 else ''
            print(f"- `{r['class']}` — {', '.join(r['defs'][:4])}{more}")


def print_overrides(rows):
    style = [r for r in rows if r['kind'] == 'đổi dáng']
    print(f'\n# --overrides — {len(rows)} rule chạm component/khung, {len(style)} đổi dáng\n')
    by = defaultdict(list)
    for r in style:
        by[r['module']].append(r)
    print('| Module | Đổi dáng | Chỉ bố cục |\n|---|---|---|')
    for mod in sorted({r['module'] for r in rows}):
        n_layout = sum(1 for r in rows if r['module'] == mod and r['kind'] == 'bố cục')
        print(f'| `{mod}` | {len(by.get(mod, []))} | {n_layout} |')
    for mod in sorted(by):
        print(f'\n### `{mod}` — {len(by[mod])} rule đổi dáng\n')
        for r in by[mod]:
            sel = r['selector'] if len(r['selector']) <= 90 else r['selector'][:90] + '…'
            print(f"- `{r['at']}` `{sel}` — đổi: {', '.join(r['style_props'])}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--layout-domain', action='store_true')
    ap.add_argument('--overrides', action='store_true')
    ap.add_argument('--who', nargs='*')
    ap.add_argument('--json')
    args = ap.parse_args()
    if not (args.layout_domain or args.overrides or args.who):
        ap.print_help()
        return 0

    used = usage_index()
    if args.who:
        for cls in args.who:
            print(cls, '→', ', '.join(sorted(users_of(cls, used))) or '(không ai)')
    domain = layout_domain(used)
    result = {}
    if args.layout_domain:
        print_domain(domain)
        result['layout_domain'] = domain
    if args.overrides:
        ov = overrides(domain)
        print_overrides(ov)
        result['overrides'] = ov
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
