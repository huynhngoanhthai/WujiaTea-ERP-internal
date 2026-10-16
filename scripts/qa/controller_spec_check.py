#!/usr/bin/env python3
r"""Kiểm chứng tài liệu đặc tả chi tiết controller — chạy trước khi giao BA.

    python3 scripts/qa/controller_spec_check.py

Ba phép kiểm (không đếm tay — bài học DOC-CTRL):
  1. Phủ đường dẫn: mọi path trong routes_deep.json phải xuất hiện trong .tex.
  2. Khuôn phiếu màn: mỗi \section trong ch03..ch09 phải đủ 7 khối \mvao..\mhoi
     (mục tổng hợp / quy ước / đường dẫn cũ được miễn — khai trong EXEMPT).
  3. Số UAT: mọi \uat{...} chứa số phải khớp một phép đếm trong uat_counts.json
     hoặc là số suy ra được (tỉ lệ n/m) — cảnh báo, không chặn.

    python3 scripts/qa/controller_spec_check.py
    python3 scripts/qa/controller_spec_check.py --uat-only
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = ROOT / 'docs' / 'controller-spec'
BLOCKS = ('mvao', 'mai', 'mhien', 'mloc', 'mkiem', 'mghi', 'mhoi')
# Mục không phải "phiếu màn": phần quy ước chung, đường dẫn cũ gộp, mục tổng hợp.
EXEMPT = ('Quy ước dùng chung', 'Đường dẫn cũ', 'Bốn đường dẫn cũ',
          'Đối chiếu', 'Code đã có', 'Bốn cách hiểu', 'Ba cách chặn',
          'Toàn bộ điểm', 'BA đừng', 'Phân hệ chưa có', 'Dữ liệu UAT',
          'Ba đính chính', 'luật dùng chung', 'Trang xem trước')


def chapters():
    return sorted(SPEC.glob('ch*.tex'))


def check_routes():
    deep = json.loads((SPEC / 'routes_deep.json').read_text())
    items = deep['routes'] if isinstance(deep, dict) and 'routes' in deep else deep
    paths = set()
    for r in items:
        for p in (r.get('paths') or [r.get('path')]):
            if p:
                paths.add(p)
    body = '\n'.join(f.read_text() for f in chapters())
    missing = sorted(p for p in paths if p not in body)
    print(f'1. Phủ đường dẫn: {len(paths) - len(missing)}/{len(paths)}')
    for p in missing:
        print(f'   THIẾU  {p}')
    return not missing


def check_template():
    bad = []
    total = 0
    for f in chapters():
        if f.name.startswith(('ch01', 'ch02')):
            continue
        parts = re.split(r'\n\\section\{', f.read_text())
        for sec in parts[1:]:
            title = sec.split('}')[0]
            if any(title.startswith(x) or x in title for x in EXEMPT):
                continue
            total += 1
            have = ''.join('1' if f'\\{b}' in sec else '0' for b in BLOCKS)
            if have != '1' * len(BLOCKS):
                bad.append((f.name, title, have))
    print(f'2. Khuôn phiếu màn: {total - len(bad)}/{total} màn đủ 7 khối')
    for name, title, have in bad:
        print(f'   THIẾU  {name} · {title} · {have}')
    return not bad


def check_uat():
    counts = json.loads((SPEC / 'uat_counts.json').read_text())
    known = {str(p['count']) for p in counts['probes']}
    body = '\n'.join(f.read_text() for f in chapters())
    used = re.findall(r'\\uat\{([^}]*)\}', body)
    nums = [u for u in used if u.isdigit()]
    unknown = sorted({u for u in nums if u not in known}, key=int)
    print(f'2b. Số UAT: {len(used)} chỗ dùng \\uat, '
          f'{len(set(nums) & known)} số khớp bảng đếm')
    if unknown:
        print('   (số không có trong bảng đếm — đo riêng, kiểm bằng mắt): '
              + ', '.join(unknown))
    print(f"   đo lúc {counts['measured_at']} trên {counts['db']}")
    return True


def main():
    ok = all([check_routes(), check_template(), check_uat()])
    print('=> ĐẠT' if ok else '=> CHƯA ĐẠT')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
