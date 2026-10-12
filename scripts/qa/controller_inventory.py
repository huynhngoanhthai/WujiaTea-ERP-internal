#!/usr/bin/env python3
"""Kiểm kê @http.route của mọi module wujia_* bằng AST — dựng bảng controller cho BA.

    python3 scripts/qa/controller_inventory.py
    python3 scripts/qa/controller_inventory.py --json docs/controller-inventory/routes.json
    python3 scripts/qa/controller_inventory.py --all      # cả module bên thứ ba

Đọc AST, không grep: grep thô đếm cả chuỗi và comment (bài học C8/D4e). Mỗi hàm mang
@http.route xuất ra module · file:dòng · class · method · path · type · auth · methods ·
csrf · docstring dòng đầu · model env[...] đọc trong thân hàm.
"""
import argparse
import ast
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import wj_paths  # noqa: E402


def literal(node):
    """ast.literal_eval an toàn; không phải hằng thì trả chuỗi nguồn."""
    try:
        return ast.literal_eval(node)
    except Exception:
        try:
            return ast.unparse(node)
        except Exception:
            return None


def route_decorators(func):
    """Các decorator @http.route / @route của một hàm."""
    out = []
    for dec in func.decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        f = dec.func
        name = None
        if isinstance(f, ast.Attribute):
            name = f.attr
        elif isinstance(f, ast.Name):
            name = f.id
        if name == 'route':
            out.append(dec)
    return out


def models_used(func):
    """Tên model xuất hiện dưới dạng env['x.y'] trong thân hàm, giữ thứ tự gặp."""
    found = []
    for node in ast.walk(func):
        if isinstance(node, ast.Subscript):
            val = node.value
            is_env = (isinstance(val, ast.Attribute) and val.attr == 'env') or \
                     (isinstance(val, ast.Name) and val.id == 'env')
            if is_env:
                key = literal(node.slice)
                if isinstance(key, str) and '.' in key and key not in found:
                    found.append(key)
    return found


def parse_file(path, module):
    src = path.read_text(encoding='utf-8')
    tree = ast.parse(src, filename=str(path))
    rows = []
    classes = []
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        bases = [ast.unparse(b) for b in cls.bases]
        funcs = [n for n in cls.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        has_route = any(route_decorators(f) for f in funcs)
        # Kế thừa CustomerPortal / AuthSignupHome cũng là controller: nhận diện bằng
        # có route, đừng chỉ nhìn tên base (base 'AuthSignupHome' không chứa 'Controller').
        if has_route or any('Controller' in b for b in bases):
            classes.append(cls.name)
        for func in funcs:
            for dec in route_decorators(func):
                paths = literal(dec.args[0]) if dec.args else None
                if isinstance(paths, str):
                    paths = [paths]
                kw = {k.arg: literal(k.value) for k in dec.keywords if k.arg}
                doc = ast.get_docstring(func) or ''
                rows.append({
                    'module': module,
                    'file': str(path.relative_to(ROOT)),
                    'line': func.lineno,
                    'class': cls.name,
                    'bases': bases,
                    'method': func.name,
                    'paths': paths or [],
                    'type': kw.get('type', 'http'),
                    'auth': kw.get('auth', 'user'),
                    'methods': kw.get('methods'),
                    'csrf': kw.get('csrf'),
                    'website': kw.get('website'),
                    'sitemap': kw.get('sitemap'),
                    'doc': doc.strip().splitlines()[0].strip() if doc.strip() else '',
                    'models': models_used(func),
                })
    return rows, classes


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--json', dest='out', help='ghi JSON ra file')
    ap.add_argument('--all', action='store_true',
                    help='quét mọi module trong repo, không chỉ wujia_*')
    args = ap.parse_args()

    pattern = '*' if args.all else 'wujia*'
    rows, classes, files, helpers = [], [], [], []
    for mod_dir in wj_paths.iter_modules(pattern):
        cdir = mod_dir / 'controllers'
        if not cdir.is_dir():
            continue
        for py in sorted(cdir.glob('*.py')):
            if py.name == '__init__.py':
                continue
            r, c = parse_file(py, mod_dir.name)
            rel = str(py.relative_to(ROOT))
            if r:
                files.append(rel)
            else:
                helpers.append(rel)
            rows.extend(r)
            classes.extend(f'{mod_dir.name}.{x}' for x in c)

    data = {
        'root': str(ROOT),
        'total_routes': len(rows),
        'total_paths': sum(len(r['paths']) for r in rows),
        'total_classes': len(classes),
        'files_with_routes': files,
        'files_without_routes': helpers,
        'classes': classes,
        'routes': rows,
    }

    if args.out:
        out = pathlib.Path(args.out)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'→ {out}')

    print(f'route (hàm)   : {len(rows)}')
    print(f'đường dẫn     : {data["total_paths"]}')
    print(f'class          : {len(classes)}')
    print(f'file có route  : {len(files)}')
    print(f'file 0 route   : {len(helpers)}  {helpers}')
    per = {}
    for r in rows:
        per[r['module']] = per.get(r['module'], 0) + 1
    print('\n-- route theo module --')
    for m, n in sorted(per.items(), key=lambda kv: -kv[1]):
        print(f'{n:4d}  {m}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
