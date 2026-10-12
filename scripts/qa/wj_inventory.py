#!/usr/bin/env python3
"""Đếm call site SHELL của một họ lớp CSS trong mọi module — loại tên con BEM.

Vì sao có file này: hai lần liên tiếp con số bàn giao bị thổi lên vì đếm thô.
D4d bàn giao "51 lượt" trong khi thật là 50; D4e bàn giao "36 lượt" trong khi
thật là 7. Cả hai lần nguyên nhân giống hệt nhau — `'.wujia-mexam-card' in sel`
khớp luôn `.wujia-mexam-card-badge`, `grep wj-pc-metric-card` đếm luôn
`wj-pc-metric-card__icon/__body/__label/__value`.

Quy tắc đếm ở đây: chỉ tính khi tên lớp đứng TRỌN trong thuộc tính class, tức
ký tự liền sau nó là dấu nháy hoặc khoảng trắng — không phải `_`, `-` hay chữ.

    python3 scripts/qa/wj_inventory.py wj-pc-metric-card wj-rep-mcard
    python3 scripts/qa/wj_inventory.py --sites wujia-mdash-card   # xem từng dòng
    python3 scripts/qa/wj_inventory.py --css wj-surface-card   # kèm rule CSS khai lớp đó
"""
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import wj_paths  # noqa: E402


def shell_sites(cls, path):
    """Trả về [(số dòng, nguồn, đoạn class)] cho mỗi call site shell trong một file.

    Hai dạng phải đếm như nhau, nếu không sẽ đếm hụt đúng phần ĐÃ LÀM XONG:

    - `class="wujia-mdash-card …"` — call site chưa migrate;
    - `<t t-set="sc_class" t-value="'wujia-mdash-card …'"/>` — call site ĐÃ migrate
      sang component, lớp cũ được giữ lại qua slot `sc_class`/`ch_class` để CSS con
      và ba danh sách `:is()` hover ở `_interaction.css` không đứt (luật D4 #1).

    Bỏ dạng thứ hai thì D4d đo ra 9 thay vì 50 — tức là càng migrate nhiều, con số
    càng tụt, đúng chiều ngược với sự thật.
    """
    out = []
    # class="..." và t-attf-class="..." — QWeb dùng cả hai.
    attr = re.compile(r'(?:t-attf?-)?class="([^"]*)"')
    # <t t-set="sc_class|ch_class|sc_link_class" t-value="'...'"/> và biến thể nháy kép.
    slot = re.compile(
        r't-set="(?:sc_class|ch_class|sc_link_class)"\s+t-value="\s*\'([^\']*)\'')
    # Ranh giới phải: hết chuỗi hoặc khoảng trắng. Chặn `-`/`_`/chữ để loại con BEM.
    whole = re.compile(r'(?:^|\s)' + re.escape(cls) + r'(?=\s|$)')
    for i, line in enumerate(path.read_text(errors='replace').splitlines(), 1):
        for m in attr.finditer(line):
            if whole.search(m.group(1)):
                out.append((i, 'class', m.group(1)))
        for m in slot.finditer(line):
            if whole.search(m.group(1)):
                out.append((i, 'sc_class', m.group(1)))
    return out


def css_rules(cls, path):
    pat = re.compile(r'\.' + re.escape(cls) + r'(?=[\s,{:>+~]|$)')
    return [(i, l.strip())
            for i, l in enumerate(path.read_text(errors='replace').splitlines(), 1)
            if pat.search(l) and '{' in l]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('classes', nargs='+')
    ap.add_argument('--css', action='store_true', help='liệt kê cả rule CSS khai lớp')
    ap.add_argument('--sites', action='store_true', help='in từng dòng call site')
    args = ap.parse_args()

    mods = wj_paths.iter_modules()
    xml = [f for m in mods for f in sorted(m.glob('views/*.xml'))] + \
        [f for m in mods for f in sorted(m.glob('templates/*.xml'))]
    css = [f for m in mods for f in sorted(m.glob('static/**/*.css'))]

    grand = 0
    for cls in args.classes:
        print(f'\n=== {cls} ===')
        total = 0
        for f in xml:
            hits = shell_sites(cls, f)
            if not hits:
                continue
            total += len(hits)
            print(f'  {len(hits):3d}  {f.relative_to(ROOT)}')
            if args.sites:
                for line, src, klass in hits:
                    print(f'        :{line}  [{src}] {klass}')
        print(f'  ---  {total} call site shell')
        grand += total
        if args.css:
            for f in css:
                for line, rule in css_rules(cls, f):
                    print(f'   css  {f.relative_to(ROOT)}:{line}  {rule}')
    if len(args.classes) > 1:
        print(f'\nTỔNG: {grand} call site shell')


if __name__ == '__main__':
    main()
