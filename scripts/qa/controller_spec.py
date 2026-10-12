#!/usr/bin/env python3
"""Trích LUẬT NGHIỆP VỤ trong thân mỗi @http.route — nền cho tài liệu BA (DOC-CTRL v2).

    python3 scripts/qa/controller_spec.py --json docs/controller-spec/routes_deep.json
    python3 scripts/qa/controller_spec.py --route /portal/order      # soi 1 đường dẫn
    python3 scripts/qa/controller_spec.py --domains                  # liệt kê domain để đo UAT

Khác `controller_inventory.py` (chỉ metadata): file này đọc THÂN hàm, xuất ra
    · điều kiện lọc dữ liệu (domain) kèm model, thứ tự sắp xếp, giới hạn bản ghi
    · chuỗi kiểm: mỗi `if ... -> return/raise/redirect` theo đúng thứ tự code chạy
    · ghi gì vào DB: create/write/unlink + tên trường
    · template QWeb render, đích redirect
    · method nghiệp vụ được gọi (để biết phải lần tiếp vào model nào)

Vẫn đọc AST, không grep — grep đếm cả chuỗi lẫn chú thích (bài học C8/D4e).
Máy chỉ sinh METADATA; câu mô tả nghiệp vụ trong tài liệu do người đọc code viết.
"""
import argparse
import ast
import json
import re
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import wj_paths  # noqa: E402

SEARCH_OPS = {'search', 'search_count', 'search_read', 'read_group', '_read_group'}
WRITE_OPS = {'create', 'write', 'unlink', 'copy'}
READ_OPS = {'browse', 'read', 'exists', 'mapped', 'filtered', 'sorted'}
ORM_OPS = SEARCH_OPS | WRITE_OPS | READ_OPS | {'sudo', 'with_context', 'with_user', 'ensure_one'}


def src(node):
    try:
        return ast.unparse(node)
    except Exception:
        return '?'


def literal(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return src(node)


def env_model(node):
    """Trả tên model nếu node là env['x.y'] (có thể lồng .sudo()/.with_context())."""
    cur = node
    while isinstance(cur, ast.Call):
        cur = cur.func
    while isinstance(cur, ast.Attribute) and cur.attr in ORM_OPS:
        cur = cur.value
        while isinstance(cur, ast.Call):
            cur = cur.func
    if isinstance(cur, ast.Subscript):
        val = cur.value
        is_env = (isinstance(val, ast.Attribute) and val.attr == 'env') or \
                 (isinstance(val, ast.Name) and val.id == 'env')
        if is_env:
            key = literal(cur.slice)
            if isinstance(key, str) and '.' in key:
                return key
    return None


class Walker(ast.NodeVisitor):
    """Đi theo thân hàm, nhớ biến nào đang trỏ model nào."""

    def __init__(self):
        self.vars = {}          # tên biến -> model
        self.queries = []       # đọc dữ liệu
        self.writes = []        # ghi dữ liệu
        self.renders = []
        self.redirects = []
        self.guards = []
        self.calls = []         # method nghiệp vụ (không phải ORM)
        self.trace = {}         # tên biến -> [(dòng, câu lệnh)] dựng dần domain

    # -- nhớ biến trỏ model --------------------------------------------------
    def visit_Assign(self, node):
        m = env_model(node.value)
        if m:
            for t in node.targets:
                if isinstance(t, ast.Name):
                    self.vars[t.id] = m
        for t in node.targets:
            if isinstance(t, ast.Name):
                self.trace.setdefault(t.id, []).append((node.lineno, src(node)))
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        if isinstance(node.target, ast.Name):
            self.trace.setdefault(node.target.id, []).append((node.lineno, src(node)))
        self.generic_visit(node)

    def base_model(self, func_node):
        """Model của lời gọi `<gì đó>.op(...)`."""
        owner = func_node.value if isinstance(func_node, ast.Attribute) else None
        if owner is None:
            return None
        m = env_model(owner)
        if m:
            return m
        cur = owner
        while isinstance(cur, ast.Call):
            cur = cur.func
        while isinstance(cur, ast.Attribute) and cur.attr in ORM_OPS:
            cur = cur.value
            while isinstance(cur, ast.Call):
                cur = cur.func
        if isinstance(cur, ast.Name):
            return self.vars.get(cur.id)
        if isinstance(cur, ast.Attribute):
            return self.vars.get(cur.attr)
        return None

    # -- lời gọi -------------------------------------------------------------
    def visit_Call(self, node):
        f = node.func
        if isinstance(f, ast.Attribute):
            op = f.attr
            model = self.base_model(f)
            kw = {k.arg: src(k.value) for k in node.keywords if k.arg}
            if op in SEARCH_OPS:
                dom = src(node.args[0]) if node.args else kw.get('domain', '[]')
                self.queries.append({
                    'line': node.lineno, 'op': op, 'model': model or src(f.value),
                    'domain': dom,
                    'order': kw.get('order'), 'limit': kw.get('limit'),
                    'offset': kw.get('offset'),
                    'groupby': src(node.args[1]) if op in ('read_group', '_read_group')
                    and len(node.args) > 1 else None,
                    'sudo': '.sudo()' in src(f.value),
                })
            elif op in WRITE_OPS:
                fields = None
                if node.args and isinstance(node.args[0], ast.Dict):
                    fields = [literal(k) for k in node.args[0].keys]
                elif node.args and isinstance(node.args[0], ast.List):
                    fields = []
                    for el in node.args[0].elts:
                        if isinstance(el, ast.Dict):
                            fields += [literal(k) for k in el.keys]
                self.writes.append({
                    'line': node.lineno, 'op': op, 'model': model or src(f.value),
                    'fields': fields, 'sudo': '.sudo()' in src(f.value),
                })
            elif op == 'render':
                tpl = literal(node.args[0]) if node.args else None
                self.renders.append({'line': node.lineno, 'template': tpl})
            elif op == 'redirect':
                self.redirects.append({'line': node.lineno, 'target': src(node.args[0])
                                       if node.args else None})
            elif op in ('append', 'extend', 'insert') and isinstance(f.value, ast.Name):
                self.trace.setdefault(f.value.id, []).append((node.lineno, src(node)))
            elif op not in ORM_OPS and not op.startswith('__'):
                owner_src = src(f.value)
                self.calls.append({'line': node.lineno, 'name': op,
                                   'on': model or owner_src, 'args': [src(a) for a in node.args]})
        elif isinstance(f, ast.Name):
            self.calls.append({'line': node.lineno, 'name': f.id, 'on': None,
                               'args': [src(a) for a in node.args]})
        self.generic_visit(node)


def exit_action(stmts):
    """Câu lệnh thoát ở cuối một nhánh: return / raise / redirect."""
    for st in stmts:
        if isinstance(st, ast.Return):
            return 'return', src(st.value) if st.value else 'None'
        if isinstance(st, ast.Raise):
            return 'raise', src(st.exc) if st.exc else '?'
    return None, None


def collect_guards(body, out, depth=0):
    """Mọi `if <điều kiện>:` mà nhánh thân thoát ra — đúng thứ tự code chạy."""
    for st in body:
        if isinstance(st, ast.If):
            kind, what = exit_action(st.body)
            if kind:
                out.append({'line': st.lineno, 'depth': depth,
                            'cond': src(st.test), 'action': kind, 'target': what})
            collect_guards(st.body, out, depth + 1)
            collect_guards(st.orelse, out, depth + 1)
        elif isinstance(st, (ast.For, ast.While, ast.With, ast.Try)):
            for attr in ('body', 'orelse', 'finalbody', 'handlers'):
                sub = getattr(st, attr, None) or []
                if attr == 'handlers':
                    for h in sub:
                        collect_guards(h.body, out, depth + 1)
                else:
                    collect_guards(sub, out, depth + 1)


def route_decorators(func):
    out = []
    for dec in func.decorator_list:
        if isinstance(dec, ast.Call):
            f = dec.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, 'id', None)
            if name == 'route':
                out.append(dec)
    return out


def other_decorators(func):
    out = []
    for dec in func.decorator_list:
        name = None
        if isinstance(dec, ast.Call):
            f = dec.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, 'id', None)
            if name == 'route':
                continue
            out.append(src(dec))
        else:
            out.append(src(dec))
    return out


def analyse(func):
    w = Walker()
    for st in func.body:
        w.visit(st)
    guards = []
    collect_guards(func.body, guards)
    for q in w.queries:
        dom = (q.get('domain') or '').strip()
        if re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', dom) and dom in w.trace:
            q['domain_trace'] = [{'line': ln, 'stmt': st}
                                 for ln, st in sorted(w.trace[dom])
                                 if ln <= q['line']]
    return {
        'params': [a.arg for a in func.args.args if a.arg != 'self'],
        'defaults': {a.arg: src(d) for a, d in zip(
            func.args.args[len(func.args.args) - len(func.args.defaults):],
            func.args.defaults)},
        'kwarg': func.args.kwarg.arg if func.args.kwarg else None,
        'queries': w.queries, 'writes': w.writes, 'renders': w.renders,
        'redirects': w.redirects, 'guards': guards,
        'calls': [c for c in w.calls if c['name'] not in {'_', 'str', 'int', 'len', 'get'}],
    }


def parse_file(path, module):
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    helpers, rows = {}, []
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        funcs = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for func in funcs:
            if not route_decorators(func):
                helpers[func.name] = {'line': func.lineno, 'class': cls.name,
                                      'doc': (ast.get_docstring(func) or '').strip(),
                                      **analyse(func)}
        for func in funcs:
            for dec in route_decorators(func):
                paths = literal(dec.args[0]) if dec.args else []
                if isinstance(paths, str):
                    paths = [paths]
                kw = {k.arg: literal(k.value) for k in dec.keywords if k.arg}
                rows.append({
                    'module': module, 'file': str(path.relative_to(ROOT)),
                    'line': func.lineno, 'class': cls.name, 'method': func.name,
                    'paths': paths or [], 'type': kw.get('type', 'http'),
                    'auth': kw.get('auth', 'user'), 'methods': kw.get('methods'),
                    'csrf': kw.get('csrf'), 'website': kw.get('website'),
                    'decorators': other_decorators(func),
                    'doc': (ast.get_docstring(func) or '').strip(),
                    **analyse(func),
                })
    for fn in [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        helpers[fn.name] = {'line': fn.lineno, 'class': None,
                            'doc': (ast.get_docstring(fn) or '').strip(), **analyse(fn)}
    return rows, helpers


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--json', dest='out')
    ap.add_argument('--route', help='chỉ in route có đường dẫn chứa chuỗi này')
    ap.add_argument('--module', help='chỉ module này')
    ap.add_argument('--domains', action='store_true', help='in mọi domain (đo UAT)')
    args = ap.parse_args()

    rows, helpers = [], {}
    for mod_dir in wj_paths.iter_modules('wujia*'):
        if args.module and mod_dir.name != args.module:
            continue
        cdir = mod_dir / 'controllers'
        if not cdir.is_dir():
            continue
        for py in sorted(cdir.glob('*.py')):
            if py.name == '__init__.py':
                continue
            r, h = parse_file(py, mod_dir.name)
            rows.extend(r)
            if h:
                helpers[str(py.relative_to(ROOT))] = h

    if args.domains:
        seen = set()
        for r in rows:
            for q in r['queries']:
                key = (q['model'], q['domain'])
                if key in seen:
                    continue
                seen.add(key)
                print(f"{r['paths'][0] if r['paths'] else r['method']:45s} "
                      f"{q['model']:32s} {q['domain']}")
        print(f'\n{len(seen)} cặp (model, domain) khác nhau')
        return 0

    if args.route:
        for r in rows:
            if any(args.route in p for p in r['paths']):
                print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0

    data = {'root': str(ROOT), 'routes': rows, 'helpers': helpers,
            'total_routes': len(rows),
            'total_paths': sum(len(r['paths']) for r in rows)}
    if args.out:
        out = pathlib.Path(args.out)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'→ {out}')
    print(f"route {len(rows)} · path {data['total_paths']} · "
          f"query {sum(len(r['queries']) for r in rows)} · "
          f"write {sum(len(r['writes']) for r in rows)} · "
          f"guard {sum(len(r['guards']) for r in rows)} · "
          f"file helper {len(helpers)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
