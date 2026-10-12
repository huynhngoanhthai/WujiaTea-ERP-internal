#!/usr/bin/env python3
"""F5b — kiểm kê test cross-module: test của module A đọc file/arch của module B."""
import argparse
import ast
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wj_paths  # noqa: E402
MOD_RE = re.compile(r'wujia_(?:portal|franchise|mobile)_[a-z_]+|wujia_(?:core|sale|fleet|delivery|account|franchise)\b')
ASSERT_RE = re.compile(r'self\.assert\w*\(|self\.fail\(')
DB_RE = re.compile(r'_arch\(|ir\.ui\.view|self\.env|url_open|_render\(')
DISK_RE = re.compile(r'_css\(|open\(|os\.path|read_text')


def scan_dir(tests_dir, owner):
    rows = []
    for name in sorted(os.listdir(tests_dir)):
        if not (name.startswith('test_') and name.endswith('.py')):
            continue
        path = os.path.join(tests_dir, name)
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        tree = ast.parse(src)
        mod_level = sorted(set(MOD_RE.findall(_module_level_source(src, tree))) - {owner})
        for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            cls_seg = ast.get_source_segment(src, cls) or ''
            cls_body_mods = sorted(set(MOD_RE.findall(_class_level_source(src, cls))) - {owner})
            for fn in [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name.startswith('test')]:
                seg = _body_source(src, fn)
                mods = sorted(set(MOD_RE.findall(seg)) - {owner})
                inherited = sorted(set(mod_level + cls_body_mods) - set(mods))
                rows.append({
                    'file': name,
                    'class': cls.name,
                    'test': fn.name,
                    'line': fn.lineno,
                    'asserts': len(ASSERT_RE.findall(seg)),
                    'modules': mods,
                    'modules_inherited': inherited,
                    'reads_db': bool(DB_RE.search(seg)) or bool(DB_RE.search(cls_seg)),
                    'reads_disk': bool(DISK_RE.search(seg)) or bool(DISK_RE.search(cls_seg)),
                })
    return rows


def _is_doc(node):
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)


def _module_level_source(src, tree):
    # Bỏ docstring: câu "đã dời sang wujia_portal_base" trong mô tả không phải là
    # phụ thuộc — đếm cả nó là tự lừa mình.
    out = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) and not _is_doc(node):
            out.append(ast.get_source_segment(src, node) or '')
    return '\n'.join(out)


def _body_source(src, fn):
    parts = [ast.get_source_segment(src, n) or '' for n in fn.body if not _is_doc(n)]
    return '\n'.join(parts)


def _class_level_source(src, cls):
    out = []
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith('test'):
            continue
        if _is_doc(node):
            continue
        out.append(ast.get_source_segment(src, node) or '')
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--modules', nargs='*', default=['wujia_portal_layout'])
    ap.add_argument('--all-portal', action='store_true', help='quét mọi module wujia_* có tests/')
    ap.add_argument('--json')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    mods = args.modules
    if args.all_portal:
        mods = [p.name for p in wj_paths.iter_modules('wujia_*') if (p / 'tests').is_dir()]

    rows = []
    for mod in mods:
        tests_dir = os.path.join(str(wj_paths.module_path(mod) or mod), 'tests')
        if not os.path.isdir(tests_dir):
            print(f'!! {mod}: không có tests/', file=sys.stderr)
            continue
        for row in scan_dir(tests_dir, mod):
            row['owner'] = mod
            rows.append(row)

    cross = [r for r in rows if r['modules'] or r['modules_inherited']]
    total_a = sum(r['asserts'] for r in rows)
    cross_a = sum(r['asserts'] for r in cross)
    if not args.quiet:
        by_file = {}
        for r in cross:
            key = (r['owner'], r['file'])
            t, a = by_file.get(key, (0, 0))
            by_file[key] = (t + 1, a + r['asserts'])
        for (owner, f), (t, a) in sorted(by_file.items(), key=lambda kv: -kv[1][0]):
            print(f'{owner:30} {f:30} {t:3} test {a:4} assert')
    print(f'TOTAL tests={len(rows)} asserts={total_a} | CROSS tests={len(cross)} asserts={cross_a}')

    if args.json:
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump({'rows': rows, 'total_tests': len(rows), 'total_asserts': total_a,
                       'cross_tests': len(cross), 'cross_asserts': cross_a}, fh, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
