#!/usr/bin/env python3
"""Kiểm luật tầng module ADR-027 + luật folder ADR-028 trên __manifest__.py của mọi module wujia_* — chỉ báo, exit 0.

    python3 scripts/qa/check_layers.py
    python3 scripts/qa/check_layers.py --json out.json
    python3 scripts/qa/check_layers.py --strict      # exit 1 nếu có vi phạm (dùng sau khi mục D chốt)

Tầng (ADR-027, chapter 74):
  L1  wujia_core (+ wujia_ui_core, *_core platform)
  L2  nghiệp vụ  — wujia_sale, _fleet, _delivery, _account, _franchise*
  L2  khung kênh — wujia_portal_layout | wujia_mobile_core
  L3a wujia_portal_base (nền ghép portal)
  L3b wujia_portal_<chức năng> | wujia_mobile_<x>

Module mới chưa khai trong LAYER thì báo `chưa phân tầng` — thêm vào bảng, đừng đoán theo tên.
"""
import argparse
import ast
import json
import pathlib
import re
import sys

# Add odoo/odoo and odoo/addons to sys.path to allow importing Odoo modules


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import wj_paths  # noqa: E402

CORE, BIZ, FRAME, BASE, CHANNEL = 'L1 core', 'L2 nghiệp vụ', 'L2 khung', 'L3a portal_base', 'L3b ghép'

LAYER = {
    'wujia_core': CORE, 'wujia_i18n': CORE, 'wujia_audit': CORE,
    'wujia_sale': BIZ, 'wujia_order_window': BIZ, 'wujia_info_request': BIZ, 'wujia_knowledge': BIZ, 'wujia_support': BIZ, 'wujia_notification': BIZ, 'wujia_exam': BIZ, 'wujia_return': BIZ, 'wujia_fleet': BIZ, 'wujia_delivery': BIZ, 'wujia_account': BIZ,
    'wujia_franchise': BIZ, 'wujia_franchise_contract': BIZ,
    'wujia_franchise_inspection': BIZ, 'wujia_franchise_operations': BIZ,
    'wujia_portal_layout': FRAME, 'wujia_mobile_core': FRAME,
    'wujia_portal_base': BASE,
}

# portal_* đang ôm model nghiệp vụ, chờ tách ở F8–F13 (plan cụm F §1.A1)
PENDING_SPLIT = set()

# vỏ rỗng sau khi tách, chờ Uninstall rồi xoá thư mục — không xét luật tầng
DEPRECATED = set()

THAI = {
    'wujia_franchise', 'wujia_franchise_contract', 'wujia_franchise_inspection',
    'wujia_franchise_operations', 'wujia_portal_inspection', 'wujia_mobile_core',
}


def layer_of(name):
    if name in LAYER:
        return LAYER[name]
    if name.startswith(('wujia_portal_', 'wujia_mobile_')):
        return CHANNEL
    return None


def channel_of(name):
    if name.startswith('wujia_portal_') or name == 'wujia_portal_layout':
        return 'portal'
    if name.startswith('wujia_mobile_'):
        return 'mobile'
    return None


def load_manifests():
    out = {}
    for mod_dir in wj_paths.iter_modules('wujia_*'):
        mf = mod_dir / '__manifest__.py'
        data = ast.literal_eval(mf.read_text(encoding='utf-8'))
        out[mf.parent.name] = [d for d in data.get('depends', [])]
    return out


def closure(name, deps, seen=None):
    seen = set() if seen is None else seen
    for d in deps.get(name, []):
        if d not in seen:
            seen.add(d)
            closure(d, deps, seen)
    return seen



FRAME_MODULE = 'wujia_portal_layout'
ROUTE_RE = re.compile(r"/portal(?:/[A-Za-z0-9_\-]+)*")
OWN_ROUTE_RE = re.compile(r"@http\.route\(\s*\[?\s*(['\"])(/portal[^'\"]*)\1")


def frame_own_routes():
    """Route do CHÍNH khung khai bằng @http.route (bỏ phần converter <...>)."""
    own = {'/portal'}
    for py in sorted((wj_paths.module_path(FRAME_MODULE) / 'controllers').glob('*.py')):
        for _q, route in OWN_ROUTE_RE.findall(py.read_text(encoding='utf-8')):
            own.add(route.split('<')[0].rstrip('/') or '/portal')
    return own


def check_frame_routes():
    """R6 — khung kênh KHÔNG được biết route của màn nghiệp vụ (cụm F, phiên F5a).

    Quét views/ + controllers/ của wujia_portal_layout: mọi đường dẫn /portal/... không
    phải route của chính khung là vi phạm ⇒ mục menu/link đó phải do module sở hữu route
    chèn vào bằng inherit. Không quét CSS/JS: ở đó /portal chỉ nằm trong chú thích.
    """
    own = frame_own_routes()
    out = []
    root = wj_paths.module_path(FRAME_MODULE)
    for f in sorted(list((root / 'views').glob('*.xml')) + list((root / 'controllers').glob('*.py'))):
        for i, line in enumerate(f.read_text(encoding='utf-8').split('\n'), 1):
            if line.lstrip().startswith(('<!--', '#')):
                continue
            for route in ROUTE_RE.findall(line):
                route = route.rstrip('/')
                if route in own or any(route.startswith(o + '/') for o in own if o != '/portal'):
                    continue
                if route == '/portal':
                    continue
                out.append({'file': str(f.relative_to(ROOT)), 'line': i, 'route': route})
    return out


def _py_files(mod):
    root = wj_paths.module_path(mod)
    for f in sorted(root.rglob('*.py')):
        if 'tests' in f.relative_to(root).parts or '__pycache__' in f.parts:
            continue
        yield f


def _method_owners():
    """Tên method → các module wujia_* định nghĩa nó (bỏ tests/)."""
    out = {}
    for mod in (p.name for p in wj_paths.iter_modules('wujia_*')):
        for f in _py_files(mod):
            try:
                tree = ast.parse(f.read_text(encoding='utf-8'))
            except SyntaxError:
                continue
            for n in ast.walk(tree):
                if isinstance(n, ast.FunctionDef):
                    out.setdefault(n.name, set()).add(mod)
    return out


def _in_odoo_core(name):
    """Method trùng tên với method của Odoo/addons ⇒ không kết luận được, bỏ qua."""
    pat = re.compile(rf'^\s*def {re.escape(name)}\s*\(', re.M)
    odoo = wj_paths.odoo_dir()
    for base in (odoo / 'odoo', odoo / 'addons'):
        if not base.is_dir():
            continue
        for f in base.rglob('*.py'):
            try:
                if pat.search(f.read_text(encoding='utf-8', errors='ignore')):
                    return True
            except OSError:
                continue
    return False


def check_runtime_calls(deps):
    """R7 — gọi method của module KHÔNG depend thì phải có guard (FR-A3).

    `check_layers` vốn chỉ đọc `__manifest__.py`, nên một call chéo tầng lúc chạy đi lọt:
    `portal_base` (L3a) gọi `_is_within_order_window` của `wujia_order_window` (L2, cấm thêm depend) và
    `portal_layout` (khung) gọi `_get_accessible_franchise_ids` của `wujia_franchise`
    (nghiệp vụ) — cài module một mình là `AttributeError` → 500. Không cấm gọi (thêm
    depend mới là vi phạm R2/R5 thật sự), chỉ đòi `hasattr`/`getattr` bọc quanh.
    """
    owners, core_cache, out = _method_owners(), {}, []
    for mod in sorted(deps):
        allowed = closure(mod, deps) | {mod}
        for f in _py_files(mod):
            src = f.read_text(encoding='utf-8')
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            guards = {m.group(1) for m in re.finditer(r"(?:hasattr|getattr)\([^,]+,\s*'(_[A-Za-z0-9_]+)'", src)}
            for n in ast.walk(tree):
                if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
                    continue
                name = n.func.attr
                if not name.startswith('_') or name in guards:
                    continue
                foreign = owners.get(name, set()) - allowed
                if not foreign or (owners.get(name, set()) & allowed):
                    continue
                if name not in core_cache:
                    core_cache[name] = _in_odoo_core(name)
                if core_cache[name]:
                    continue
                out.append({'module': mod, 'file': str(f.relative_to(ROOT)), 'line': n.lineno,
                            'method': name, 'owner_module': ', '.join(sorted(foreign))})
    return out


def check(deps):
    violations, unknown = [], []
    for mod, direct in deps.items():
        lay = layer_of(mod)
        if mod in DEPRECATED:
            continue
        if lay is None:
            unknown.append(mod)
            continue
        wj = [d for d in direct if d in deps]
        for d in wj:
            dl = layer_of(d)
            rule = None
            if lay in (CORE, BIZ) and dl in (FRAME, BASE, CHANNEL):
                rule = 'R1 nghiệp vụ/core không depend khung hay module ghép'
            elif lay == FRAME and dl in (BIZ, BASE, CHANNEL):
                rule = 'R2 khung không depend nghiệp vụ/ghép'
            elif lay == FRAME and dl == FRAME:
                rule = 'R3 hai khung kênh không depend nhau'
            elif lay in (BASE, CHANNEL) and channel_of(mod) and channel_of(d) and channel_of(mod) != channel_of(d):
                rule = 'R3 portal_* ↔ mobile_* không depend chéo'
            elif lay == BASE and dl == CHANNEL:
                rule = 'R5 portal_base không depend portal_<x>'
            if rule:
                violations.append({'module': mod, 'depends': d, 'rule': rule})
        if lay == CHANNEL and channel_of(mod) == 'portal' and 'wujia_portal_base' not in closure(mod, deps):
            violations.append({'module': mod, 'depends': '(thiếu) wujia_portal_base', 'rule': 'R4 mọi portal_<x> depend portal_base'})
    for v in violations:
        v['owner'] = 'Thái' if v['module'] in THAI or v['module'].startswith('wujia_mobile_') or v['depends'] == 'wujia_mobile_core' else 'Dev portal'
        v['note'] = 'chờ tách F8–F13' if v['module'] in PENDING_SPLIT else ('mục D, chờ chốt với anh Thái' if v['depends'] == 'wujia_mobile_core' else '')
    return violations, unknown


def check_folders(deps):
    """R8 — folder khớp tầng (ADR-028): L1 + khung ở base/, module ghép ở portal/ | mobile/, nghiệp vụ ở folder miền."""
    out = []
    for mod in deps:
        lay, folder = layer_of(mod), wj_paths.folder_of(mod)
        if lay is None:
            continue
        if lay in (CORE, FRAME):
            want = folder == 'base'
        elif lay in (BASE, CHANNEL):
            want = folder == channel_of(mod)
        else:
            want = folder in wj_paths.WUJIA_DIRS and folder not in ('base', 'portal', 'mobile')
        if not want:
            out.append({'module': mod, 'folder': folder, 'layer': lay})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--json')
    ap.add_argument('--strict', action='store_true')
    args = ap.parse_args()

    deps = load_manifests()
    violations, unknown = check(deps)

    print(f'# check_layers — {len(deps)} module wujia_*, {len(violations)} vi phạm\n')
    for lay in (CORE, BIZ, FRAME, BASE, CHANNEL):
        mods = [m for m in deps if layer_of(m) == lay]
        print(f'{lay:16} {len(mods):2}  ' + ', '.join(mods))
    if unknown:
        print(f'\nchưa phân tầng: {", ".join(unknown)}')
    shells = sorted(DEPRECATED & set(deps))
    if shells:
        print(f'vỏ chờ gỡ (không xét luật): {", ".join(shells)}')
    print('\n| Module | Depend | Luật | Chủ code | Ghi chú |\n|---|---|---|---|---|')
    for v in violations:
        print(f"| `{v['module']}` | `{v['depends']}` | {v['rule']} | {v['owner']} | {v['note']} |")
    frame = check_frame_routes()
    print(f'\n# R6 — khung {FRAME_MODULE} biết route Wujia: {len(frame)} vi phạm')
    if frame:
        print('\n| File | Dòng | Route |\n|---|---|---|')
        for v in frame:
            print(f"| `{v['file']}` | {v['line']} | `{v['route']}` |")

    calls = check_runtime_calls(deps)
    print(f'\n# R7 — gọi method module không depend mà KHÔNG có guard: {len(calls)} vi phạm')
    if calls:
        print('\n| Module | File:dòng | Method | Chủ method |\n|---|---|---|---|')
        for v in calls:
            print(f"| `{v['module']}` | `{v['file']}`:{v['line']} | `{v['method']}` | `{v['owner_module']}` |")

    folders = check_folders(deps)
    print(f'\n# R8 — module nằm sai folder so với tầng: {len(folders)} vi phạm')
    for v in folders:
        print(f"- `{v['module']}` ({v['layer']}) đang ở `{v['folder']}/`")

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(
            {'violations': violations, 'unknown': unknown, 'frame_routes': frame,
             'runtime_calls': calls, 'folders': folders},
            ensure_ascii=False, indent=2))
    return 1 if args.strict and (violations or unknown or frame or calls or folders) else 0


if __name__ == '__main__':
    sys.exit(main())
