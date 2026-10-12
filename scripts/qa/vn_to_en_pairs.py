#!/usr/bin/env python3
"""Cặp câu (VN cũ → EN mới) cho Phần V — Việt hoá source (next-session-clusters-J.md §6).

Quy trình 1 phiên V (mỗi module):
    python3 scripts/qa/vn_to_en_pairs.py draft --module wujia_portal_layout
        → docs/i18n-pairs/wujia_portal_layout.csv (cột `en` điền sẵn nếu glossary đã có câu VN đó)
    (dev điền cột `en`; dòng muốn tự sửa tay thì để `mode=manual`)
    python3 scripts/qa/vn_to_en_pairs.py check --module wujia_portal_layout
    python3 scripts/qa/vn_to_en_pairs.py apply --module wujia_portal_layout [--dry-run] [--base <thư mục copy>]
        → thay câu trong source (XML text/attr dịch được, _()/_lt, string=) + thêm dòng `key=EN, VN=câu cũ`
          vào docs/i18n-glossary.csv; in danh sách phải sửa tay (biểu thức t-*, hằng Python, JS, attr không dịch).
    python3 scripts/sync_translations.py --modules <module> --langs vi_VN   → vi_VN.po + .pot

Chạy bằng python env Odoo (cần lxml): /opt/homebrew/Caskroom/miniconda/base/envs/odoo19/bin/python3 trên Mac.
"""
import argparse
import csv
import html
import os
import re
import shutil
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vn_hardcode_scan import BASE, VN, modules, scan, wj_paths  # noqa: E402

PAIRS_DIR = os.path.join(BASE, 'docs', 'i18n-pairs')
GLOSSARY = os.path.join(BASE, 'docs', 'i18n-glossary.csv')
FIELDS = ['file', 'line', 'category', 'attr', 'vn', 'en', 'mode', 'note']

# Odoo chỉ dịch các attribute này (odoo/tools/translate.py TRANSLATED_ATTRS, Odoo 19) + `value` của input text/nút.
# `data-*` tuỳ ý KHÔNG dịch ⇒ chuỗi JS đi đường <t t-set> (quy ước J-V0 §6).
TRANSLATED_ATTRS = {
    'string', 'add-label', 'help', 'sum', 'avg', 'confirm', 'placeholder', 'alt', 'title', 'aria-label',
    'aria-keyshortcuts', 'aria-placeholder', 'aria-roledescription', 'aria-valuetext',
    'value_label', 'data-tooltip', 'label', 'confirm-label', 'confirm-title', 'cancel-label',
}
TRANSLATED_ATTRS |= {'t-attf-' + a for a in TRANSLATED_ATTRS}
# Loại tự thay được; còn lại (qweb_expr, py_literal, js_*, css) cần sửa tay theo quy ước §6.
AUTO = {'qweb_text', 'qweb_attr', 'data_record', 'py_gettext', 'py_field'}
ATTR_RE = re.compile(r'^([\w:.-]+)="(.*)"$', re.S)
PLACEHOLDER_RE = re.compile(r'%\(\w+\)[sdf]|%[sdf]|\{\w*\}|\$\{[^}]*\}|<[^>]+>')


def norm(text):
    return ' '.join(text.split())


def pairs_path(module):
    return os.path.join(PAIRS_DIR, module + '.csv')


def read_pairs(module):
    path = pairs_path(module)
    if not os.path.exists(path):
        sys.exit('chưa có %s — chạy `draft` trước' % os.path.relpath(path, BASE))
    with open(path, encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


def write_pairs(module, rows):
    os.makedirs(PAIRS_DIR, exist_ok=True)
    with open(pairs_path(module), 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, FIELDS)
        w.writeheader()
        w.writerows(rows)


def load_glossary(path=GLOSSARY):
    """(key → VN, VN → [key]) từ docs/i18n-glossary.csv."""
    by_key, by_vn = {}, defaultdict(list)
    if os.path.exists(path):
        with open(path, encoding='utf-8', newline='') as fh:
            for row in csv.DictReader(fh):
                key, vn = norm(row.get('key') or ''), norm(row.get('VN') or '')
                if key:
                    by_key.setdefault(key, vn)
                    if vn:
                        by_vn[vn].append(key)
    return by_key, by_vn


# ------------------------------------------------------------------ draft

def draft(module):
    _, by_vn = load_glossary()
    old = {}
    if os.path.exists(pairs_path(module)):
        for r in read_pairs(module):
            old[(r['file'], r['category'], r['attr'], r['vn'])] = r
    rows = []
    for _mod, _own, cat, path, line, text in scan({module}, raw=True):
        if cat == 'test':
            continue
        attr = ''
        if cat in ('qweb_attr', 'qweb_expr', 'data_record') and (m := ATTR_RE.match(text)):
            attr, text = m.group(1), m.group(2)
        vn = norm(text)
        mode = 'auto' if cat in AUTO else 'manual'
        note = ''
        if cat in ('qweb_attr', 'data_record') and attr and attr not in TRANSLATED_ATTRS and attr != 'value':
            mode, note = 'manual', 'attr `%s` Odoo không dịch ⇒ <t t-set> (quy ước §6)' % attr
        prev = old.get((path, cat, attr, vn))
        en = prev['en'] if prev else (by_vn[vn][0] if len(by_vn.get(vn, [])) == 1 else '')
        if prev:
            mode, note = prev['mode'] or mode, prev['note'] or note
        rows.append({'file': path, 'line': line, 'category': cat, 'attr': attr, 'vn': vn,
                     'en': en, 'mode': mode, 'note': note})
    rows.sort(key=lambda r: (r['file'], int(r['line'])))
    write_pairs(module, rows)
    auto = sum(r['mode'] == 'auto' for r in rows)
    pre = sum(bool(r['en']) for r in rows)
    print('%s: %d dòng (auto %d · manual %d) · EN điền sẵn từ glossary %d → %s'
          % (module, len(rows), auto, len(rows) - auto, pre, os.path.relpath(pairs_path(module), BASE)))


# ------------------------------------------------------------------ check

def check(module, quiet=False):
    rows = read_pairs(module)
    by_key, _ = load_glossary()
    errors, warns = [], []
    en_to_vn = defaultdict(set)
    vn_to_en = defaultdict(set)
    for i, r in enumerate(rows, 2):
        where = '%s:%s (dòng csv %d)' % (r['file'], r['line'], i)
        en, vn = norm(r['en']), r['vn']
        if r['mode'] not in ('auto', 'manual'):
            errors.append('%s: mode phải là auto|manual' % where)
        if not en:
            (errors if r['mode'] == 'auto' else warns).append('%s: chưa có EN — %s' % (where, vn[:60]))
            continue
        if VN.search(en):
            errors.append('%s: EN còn dấu tiếng Việt — %s' % (where, en[:60]))
        if sorted(PLACEHOLDER_RE.findall(en)) != sorted(PLACEHOLDER_RE.findall(vn)):
            errors.append('%s: placeholder/thẻ lệch VN %s ≠ EN %s'
                          % (where, PLACEHOLDER_RE.findall(vn), PLACEHOLDER_RE.findall(en)))
        en_to_vn[en].add(vn)
        vn_to_en[vn].add(en)
        if en in by_key and by_key[en] and by_key[en] != vn:
            errors.append('%s: glossary đã có "%s" = "%s" ≠ "%s" ⇒ đổi câu EN (msgid trùng là 1 bản dịch)'
                          % (where, en, by_key[en], vn))
    for en, vns in en_to_vn.items():
        if len(vns) > 1:
            errors.append('EN "%s" dùng cho %d câu VN khác nhau: %s ⇒ msgid trùng chỉ có 1 bản dịch'
                          % (en, len(vns), ' | '.join(sorted(vns))))
    for vn, ens in vn_to_en.items():
        if len(ens) > 1:
            warns.append('VN "%s" có %d bản EN: %s (được, nếu khác ngữ cảnh)' % (vn, len(ens), ' | '.join(sorted(ens))))
    if not quiet:
        for w in warns:
            print('  ⚠', w)
        for e in errors:
            print('  ✗', e)
    print('%s: %d dòng · %d lỗi · %d cảnh báo' % (module, len(rows), len(errors), len(warns)))
    return errors


# ------------------------------------------------------------------ apply

def xml_pattern(vn, in_attr):
    """Regex khớp câu VN (đã gộp khoảng trắng) trong source XML: chấp nhận entity + xuống dòng."""
    alt = {'&': '(?:&amp;|&#38;|&)', '<': '&lt;', '>': '(?:&gt;|>)', '"': '(?:&quot;|")', "'": "(?:&apos;|&#39;|')",
           ' ': '(?: |&nbsp;|&#160;)'}
    out = []
    for word in vn.split(' '):
        out.append(''.join(alt.get(c, re.escape(c)) for c in word))
    sep = r'\s+' if not in_attr else r'(?:\s+|&#10;)+'
    return re.compile(sep.join(out))


def py_escape(en, quote):
    return en.replace('\\', '\\\\').replace(quote, '\\' + quote)


def in_script(src, pos):
    start = src.rfind('<script', 0, pos)
    return start >= 0 and src.rfind('</script>', 0, pos) < start


def apply(module, dry_run=False, base=BASE):
    if check(module, quiet=True):
        sys.exit('còn lỗi — chạy `check` xem chi tiết, sửa xong mới apply')
    rows = read_pairs(module)
    by_file = defaultdict(list)
    manual, missing, done = [], [], []
    for r in rows:
        if r['mode'] != 'auto' or not norm(r['en']):
            manual.append(r)
        else:
            by_file[r['file']].append(r)
    for rel, items in by_file.items():
        path = os.path.join(base, rel)
        src = open(path, encoding='utf-8').read()
        is_xml = rel.endswith('.xml')
        # Thay từ cuối file lên đầu ⇒ số dòng của các dòng phía trên không lệch.
        for r in sorted(items, key=lambda r: int(r['line']), reverse=True):
            en = norm(r['en'])
            lines = src.splitlines(True)
            line_start = sum(len(l) for l in lines[:int(r['line']) - 1])
            if is_xml:
                pat = xml_pattern(r['vn'], bool(r['attr']))
                if r['attr']:
                    # lxml báo dòng CUỐI của thẻ mở ⇒ attr nằm ở dòng đó hoặc phía trên: lấy lần khớp gần nhất
                    # trong attr đúng tên, kết thúc trước hết dòng báo.
                    line_end = line_start + len(lines[int(r['line']) - 1]) if int(r['line']) <= len(lines) else len(src)
                    attr_re = re.compile(r'\b%s\s*=\s*"([^"]*)"' % re.escape(r['attr']))
                    m = None
                    for am in attr_re.finditer(src, max(0, line_start - 4000), line_end):
                        hit = pat.fullmatch(am.group(1).strip())
                        if hit:
                            off = am.start(1) + len(am.group(1)) - len(am.group(1).lstrip())
                            m = re.compile(re.escape(hit.group(0))).search(src, off)
                else:
                    m = pat.search(src, line_start)
                if m and in_script(src, m.start()):
                    r['note'] = (r['note'] + ' · ' if r['note'] else '') + 'nằm trong <script> ⇒ sửa tay'
                    manual.append(r)
                    continue
                new = html.escape(en, quote=bool(r['attr']))
            else:
                m = re.compile(re.escape(r['vn'])).search(src, line_start)
                new = py_escape(en, src[m.start() - 1]) if m and src[m.start() - 1] in '\'"' else en
            if not m:
                missing.append(r)
                continue
            src = src[:m.start()] + new + src[m.end():]
            done.append(r)
        if not dry_run:
            open(path, 'w', encoding='utf-8').write(src)
    added = 0
    glossary = os.path.join(base, 'docs', 'i18n-glossary.csv')
    if not dry_run and done and os.path.exists(glossary):
        by_key, _ = load_glossary(glossary)
        new_rows = {}
        for r in done:
            en = norm(r['en'])
            if en not in by_key and en not in new_rows:
                new_rows[en] = r['vn']
        if new_rows:
            with open(glossary, encoding='utf-8', newline='') as fh:
                header = next(csv.reader(fh))
            with open(glossary, 'a', encoding='utf-8', newline='') as fh:
                w = csv.DictWriter(fh, header)
                for en, vn in new_rows.items():
                    w.writerow({'key': en, 'VN': vn})
            added = len(new_rows)
    print('%s%s: thay %d · không tìm thấy %d · sửa tay %d · glossary +%d'
          % ('[dry-run] ' if dry_run else '', module, len(done), len(missing), len(manual), added))
    for r in missing:
        print('  ? không thấy   %s:%s [%s] %s' % (r['file'], r['line'], r['category'], r['vn'][:70]))
    for r in manual:
        print('  ✎ sửa tay      %s:%s [%s%s] %s → %s %s' % (
            r['file'], r['line'], r['category'], (' ' + r['attr']) if r['attr'] else '', r['vn'][:50],
            norm(r['en'])[:40] or '(chưa có EN)', ('— ' + r['note']) if r['note'] else ''))
    return done, missing, manual


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=('draft', 'check', 'apply'))
    ap.add_argument('--module', required=True)
    ap.add_argument('--dry-run', action='store_true', help='apply: không ghi file')
    ap.add_argument('--base', default=BASE, help='apply: gốc repo để ghi (vd bản copy tạm để thử)')
    a = ap.parse_args()
    if a.module not in set(modules()):
        ap.error('không có module %s' % a.module)
    if a.cmd == 'draft':
        draft(a.module)
    elif a.cmd == 'check':
        return 1 if check(a.module) else 0
    else:
        rel = os.path.join(wj_paths.folder_of(a.module), a.module)
        if os.path.abspath(a.base) != BASE and not os.path.isdir(os.path.join(a.base, rel)):
            shutil.copytree(os.path.join(BASE, rel), os.path.join(a.base, rel))
        apply(a.module, a.dry_run, os.path.abspath(a.base))
    return 0


if __name__ == '__main__':
    sys.exit(main())
