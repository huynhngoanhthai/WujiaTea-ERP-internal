#!/usr/bin/env python3
"""Quét chuỗi tiếng Việt viết cứng trong source custom Wujia (không tính comment, docstring, i18n/).

    python3 scripts/qa/vn_hardcode_scan.py                 # in bảng tóm tắt
    python3 scripts/qa/vn_hardcode_scan.py --csv out.csv   # + danh sách từng chuỗi
    python3 scripts/qa/vn_hardcode_scan.py --module wujia_portal_layout --fail-on-any
                                                           # nghiệm thu 1 phiên V: exit 1 nếu còn chuỗi (trừ test)

Loại (category):
  qweb_text    chữ trong template/view XML (text node)
  qweb_attr    thuộc tính hiển thị: string, placeholder, title, aria-label, alt, help, confirm…
  qweb_expr    chuỗi VN nằm trong biểu thức t-*/attrs (vd t-out="x or 'Chưa có'")
  data_record  field của bản ghi data XML (mail template, menu, cron…)
  py_gettext   _('…VN…') / _lt — msgid là tiếng Việt
  py_field     string=/help=/selection của field
  py_literal   hằng / dict nhãn / thông báo khác trong Python
  js_gettext   _t('…VN…')
  js_literal   chuỗi VN khác trong JS
  css          content: '…VN…'
  test         chuỗi VN trong tests/ (đổi theo khi sửa nguồn)
"""
import argparse
import ast
import csv
import os
import re
import sys
from collections import Counter, defaultdict

from lxml import etree

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wj_paths  # noqa: E402
VN = re.compile('[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]', re.I)
THAI = {
    'wujia_franchise', 'wujia_franchise_contract', 'wujia_franchise_inspection', 'wujia_franchise_operations',
    'wujia_portal_inspection', 'wujia_fields_value',
}
DISPLAY_ATTRS = {'string', 'placeholder', 'title', 'aria-label', 'alt', 'help', 'confirm', 'sum', 'data-tooltip',
                 'data-bs-original-title', 'value', 'label'}


def owner(module):
    return 'Thái' if module in THAI or module.startswith('wujia_mobile') else 'team'


def modules():
    for p in wj_paths.iter_modules():
        if p.name.startswith(('wujia_', 'wj_')):
            yield p.name


def clip(text):
    return ' '.join(text.split())[:140]


def scan_python(path, is_test):
    try:
        tree = ast.parse(open(path, encoding='utf-8').read())
    except SyntaxError:
        return
    parents = {}
    docstrings = set()
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docstrings.add(first.value)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)) or node in docstrings:
            continue
        if not VN.search(node.value):
            continue
        if is_test:
            yield 'test', node.lineno, node.value
            continue
        cat = 'py_literal'
        cur = node
        while cur in parents:
            par = parents[cur]
            if isinstance(par, ast.Call):
                fn = par.func
                fname = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else '')
                if fname in ('_', '_lt') and cur in par.args:
                    cat = 'py_gettext'
                    break
                if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == 'fields':
                    cat = 'py_field'
                    break
            if isinstance(par, ast.keyword) and par.arg in ('string', 'help', 'selection'):
                cat = 'py_field'
                break
            if isinstance(par, (ast.FunctionDef, ast.ClassDef)):
                break
            cur = par
        yield cat, node.lineno, node.value


STR_RE = re.compile(r"""(_t\(\s*)?('(?:\\.|[^'\\\n])*'|"(?:\\.|[^"\\\n])*"|`(?:\\.|[^`\\])*`)""", re.S)


def strip_js_comments(src):
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c in '\'"`':
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == '\\' else 1
            out.append(src[i:j + 1]); i = j + 1
        elif src.startswith('//', i):
            j = src.find('\n', i); j = n if j < 0 else j
            out.append(' ' * (j - i)); i = j
        elif src.startswith('/*', i):
            j = src.find('*/', i + 2); j = n if j < 0 else j + 2
            out.append(re.sub(r'[^\n]', ' ', src[i:j])); i = j
        else:
            out.append(c); i += 1
    return ''.join(out)


def scan_js(path, is_test):
    src = strip_js_comments(open(path, encoding='utf-8', errors='replace').read())
    for m in STR_RE.finditer(src):
        if VN.search(m.group(2)):
            line = src.count('\n', 0, m.start()) + 1
            cat = 'test' if is_test else ('js_gettext' if m.group(1) else 'js_literal')
            yield cat, line, m.group(2)[1:-1]


CSS_CONTENT = re.compile(r"""content\s*:\s*(['"])(.*?)\1""")


def scan_css(path, is_test):
    src = open(path, encoding='utf-8', errors='replace').read()
    src = re.sub(r'/\*.*?\*/', lambda m: re.sub(r'[^\n]', ' ', m.group(0)), src, flags=re.S)
    for m in CSS_CONTENT.finditer(src):
        if VN.search(m.group(2)):
            yield 'css', src.count('\n', 0, m.start()) + 1, m.group(2)


def scan_xml(path, is_test):
    try:
        tree = etree.parse(path, etree.XMLParser(recover=True, remove_comments=True))
    except etree.XMLSyntaxError:
        return
    for el in tree.iter():
        if not isinstance(el.tag, str):
            continue
        rec = next((a for a in el.iterancestors('record')), None)
        in_arch = any(a.tag == 'field' and a.get('name') in ('arch', 'arch_db') for a in el.iterancestors()) \
            or any(a.tag == 'template' for a in el.iterancestors()) or el.tag == 'template'
        data_rec = rec is not None and not in_arch
        for txt in (el.text, el.tail):
            if txt and VN.search(txt):
                if 'test' in path.split(os.sep) and is_test:
                    yield 'test', el.sourceline, txt
                else:
                    yield ('data_record' if data_rec else 'qweb_text'), el.sourceline, txt
        for att, val in el.attrib.items():
            if not VN.search(val):
                continue
            if att.startswith('t-') or att in ('invisible', 'readonly', 'required', 'domain', 'context', 'eval'):
                cat = 'qweb_expr'
            elif att in DISPLAY_ATTRS or att.startswith('data-') or att.startswith('aria-'):
                cat = 'data_record' if data_rec else 'qweb_attr'
            else:
                cat = 'qweb_attr'
            yield cat, el.sourceline, f'{att}="{val}"'


# File thư viện bên thứ ba nằm ngoài vendors/ — chữ có dấu không phải tiếng Việt (J-V1: locale tiếng Pháp mẫu
# của pickadate, "Février"/"Décembre"). Đường dẫn tính từ gốc module.
VENDOR_FILES = {
    'static/assets/js/scripts/pickers/dateTime/pick-a-datetime.js',
}

# Dữ liệu mẫu `noupdate` là tên riêng (cửa hàng, người, địa chỉ) — dữ liệu chứ không phải chữ giao diện,
# không dịch (J-V2). Đường dẫn tính từ thư mục chứa module.
DATA_FILES = {
    'wujia_portal_base/data/sample_data.xml',
    'wujia_return/legacy_seed.py',  # J-V6: câu VN cũ của seed loại lỗi để migration đối chiếu
    'wujia_notification/legacy_seed.py',  # J-V7: câu VN cũ của seed loại thông báo
}

# Hằng tên riêng trong code (không phải chữ giao diện): (đường dẫn từ thư mục chứa module, câu). J-V8b: thương hiệu mặc định.
LITERAL_EXEMPT = {
    ('wujia_core/models/res_company.py', 'Ngô Gia'),
    # J-T5: thuật ngữ "giữ nguyên" của dịch máy + bảng chữ nhận diện câu nguồn tiếng Việt (không phải chữ giao diện).
    ('wujia_i18n/data/glossary_data.xml', 'Ngô Gia'),
    ('wujia_i18n/tools/mt_deepl.py', '[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]'),
}

SCANNERS = {'.py': scan_python, '.js': scan_js, '.xml': scan_xml, '.css': scan_css, '.scss': scan_css}


def scan(only=None, raw=False):
    """Yield (module, owner, category, file, line, text). `raw=True` giữ nguyên câu (không cắt/gộp khoảng trắng)."""
    for mod in modules():
        if only and mod not in only:
            continue
        root = str(wj_paths.module_path(mod))
        parent = os.path.dirname(root)
        for dirpath, dirnames, files in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in ('i18n', '__pycache__', 'lib', 'node_modules', 'vendors', 'vendor')]
            rel_dir = os.path.relpath(dirpath, root)
            is_test = rel_dir.split(os.sep)[0] in ('tests', 'test') or '/tests' in dirpath
            for f in files:
                ext = os.path.splitext(f)[1]
                if ext not in SCANNERS or f.endswith('.min.js'):
                    continue
                path = os.path.join(dirpath, f)
                if os.path.relpath(path, root).replace(os.sep, '/') in VENDOR_FILES:
                    continue
                if os.path.relpath(path, parent).replace(os.sep, '/') in DATA_FILES:
                    continue
                rel_custom = os.path.relpath(path, parent).replace(os.sep, '/')
                for cat, line, text in SCANNERS[ext](path, is_test):
                    if (rel_custom, text) in LITERAL_EXEMPT:
                        continue
                    yield mod, owner(mod), cat, os.path.relpath(path, BASE), line, (text if raw else clip(text))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv')
    ap.add_argument('--module', help='chỉ quét các module này (phẩy ngăn cách)')
    ap.add_argument('--fail-on-any', action='store_true', help='exit 1 nếu còn chuỗi ngoài tests/ (thước nghiệm thu phiên V)')
    a = ap.parse_args()
    only = {m.strip() for m in a.module.split(',') if m.strip()} if a.module else None
    if only and (unknown := only - set(modules())):
        ap.error('không có module: %s' % ', '.join(sorted(unknown)))
    rows = list(scan(only))
    if a.csv:
        with open(a.csv, 'w', encoding='utf-8', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['module', 'owner', 'category', 'file', 'line', 'text'])
            w.writerows(rows)
    by_mod = defaultdict(Counter)
    for mod, own, cat, *_ in rows:
        by_mod[(own, mod)][cat] += 1
    cats = ['qweb_text', 'qweb_attr', 'qweb_expr', 'data_record', 'py_gettext', 'py_field', 'py_literal',
            'js_gettext', 'js_literal', 'css', 'test']
    print('| Chủ | Module | ' + ' | '.join(cats) + ' | Tổng (trừ test) |')
    print('|' + '---|' * (len(cats) + 3))
    for (own, mod), c in sorted(by_mod.items(), key=lambda kv: (kv[0][0] != 'team', -sum(v for k, v in kv[1].items() if k != 'test'))):
        total = sum(v for k, v in c.items() if k != 'test')
        print(f'| {own} | `{mod}` | ' + ' | '.join(str(c.get(k, '')) for k in cats) + f' | **{total}** |')
    tot = Counter()
    for c in by_mod.values():
        tot.update(c)
    print(f'| | **Tổng** | ' + ' | '.join(str(tot.get(k, '')) for k in cats) +
          f' | **{sum(v for k, v in tot.items() if k != "test")}** |')
    remaining = sum(v for k, v in tot.items() if k != 'test')
    if a.fail_on_any and remaining:
        print(f'\nCòn {remaining} chuỗi tiếng Việt viết cứng (trừ test).', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
