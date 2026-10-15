#!/usr/bin/env python3
"""Nguồn duy nhất về bố cục thư mục module (ADR-028).

    python3 scripts/wj_paths.py --addons-path     # dòng addons_path cho odoo.conf
    python3 scripts/wj_paths.py --where <module>  # thư mục của một module
    python3 scripts/wj_paths.py --list            # folder -> module
    python3 scripts/wj_paths.py --changed-modules <cũ> <mới>   # module cần -u khi deploy

Thêm folder mới: thêm vào ADDON_DIRS, rồi sinh lại addons_path ở mọi máy.
"""
import argparse
import fnmatch
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

WUJIA_DIRS = ('base', 'franchise', 'sales', 'logistics', 'account', 'academy', 'service',
              'portal', 'mobile', 'bi')
VENDOR_DIRS = ('tools', 'themes', 'third_party/oca', 'third_party/oca_queue',
               'third_party/om', 'third_party/misc')
ADDON_DIRS = WUJIA_DIRS + VENDOR_DIRS + ('addons',)


def odoo_dir():
    """Odoo core: biến WUJIA_ODOO, không có thì ../Odoo19C, ../odoo19, rồi ./odoo19."""
    cands = [
        os.environ.get('WUJIA_ODOO'),
        ROOT.parent / 'Odoo19C',
        ROOT.parent / 'odoo19',
        ROOT / 'odoo19',
    ]
    for c in cands:
        if c and (pathlib.Path(c) / 'odoo-bin').is_file():
            return pathlib.Path(c).resolve()
    return (ROOT.parent / 'odoo19').resolve() if (ROOT.parent / 'odoo19' / 'odoo-bin').is_file() else ROOT / 'odoo19'


def iter_modules(pattern='*', dirs=ADDON_DIRS):
    """Thư mục module (có __manifest__.py) khớp pattern, sắp theo tên module."""
    found = []
    for d in dirs:
        base = ROOT / d
        if base.is_dir():
            found += [p for p in base.iterdir()
                      if fnmatch.fnmatch(p.name, pattern) and (p / '__manifest__.py').is_file()]
    return sorted(found, key=lambda p: p.name)


def module_path(name):
    for d in ADDON_DIRS:
        p = ROOT / d / name
        if (p / '__manifest__.py').is_file():
            return p
    return None


def module_of(path):
    """Tên module chứa một file nằm trong repo, None nếu file không thuộc module nào."""
    p = pathlib.Path(path).resolve()
    for parent in [p] + list(p.parents):
        if parent == ROOT:
            break
        if (parent / '__manifest__.py').is_file():
            return parent.name
    return None


def folder_of(name):
    p = module_path(name)
    return p.parent.relative_to(ROOT).as_posix() if p else None


def addons_path(odoo=None):
    odoo = pathlib.Path(odoo) if odoo else odoo_dir()
    return ','.join([(odoo / 'addons').as_posix()] + [(ROOT / d).as_posix() for d in ADDON_DIRS])


def changed_modules(old=None, new='HEAD'):
    """Module có file đổi NỘI DUNG giữa hai commit; file chỉ đổi chỗ (R100) không tính."""
    if old and old != new:
        cmd = ['git', 'diff', '--name-status', '-M', old, new]
    else:
        cmd = ['git', 'diff-tree', '--no-commit-id', '--name-status', '-M', '-r', new]
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout
    dirs = sorted(ADDON_DIRS, key=len, reverse=True)
    mods = set()
    for line in out.splitlines():
        status, *paths = line.split('\t')
        if status == 'R100' or not paths:
            continue
        path = paths[-1]
        for d in dirs:
            if path.startswith(d + '/'):
                name = path[len(d) + 1:].split('/')[0]
                if (ROOT / d / name / '__manifest__.py').is_file():
                    mods.add(name)
                break
    return sorted(mods)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--addons-path', action='store_true')
    ap.add_argument('--odoo', help='thư mục Odoo core (mặc định tự dò)')
    ap.add_argument('--odoo-dir', action='store_true', help='in thư mục Odoo core dò được')
    ap.add_argument('--where', metavar='MODULE')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--changed-modules', nargs='*', metavar='COMMIT',
                    help='module đổi nội dung giữa [CŨ] [MỚI], cách nhau dấu phẩy (cho deploy -u)')
    args = ap.parse_args()
    if args.changed_modules is not None:
        print(','.join(changed_modules(*args.changed_modules[:2])))
    elif args.addons_path:
        print(addons_path(args.odoo))
    elif args.odoo_dir:
        print(odoo_dir())
    elif args.where:
        p = module_path(args.where)
        if not p:
            sys.exit(f'không có module {args.where}')
        print(p)
    elif args.list:
        for d in ADDON_DIRS:
            mods = [p.name for p in iter_modules(dirs=(d,))]
            print(f'{d:22} {len(mods):2}  ' + ' '.join(mods))
    else:
        ap.print_help()


if __name__ == '__main__':
    main()
