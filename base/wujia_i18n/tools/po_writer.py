# -*- coding: utf-8 -*-
"""Đọc/ghi glossary CSV + .po dùng chung cho module wujia_i18n và scripts/sync_translations.py.

Chỉ phụ thuộc babel + thư viện chuẩn (KHÔNG import odoo) ⇒ script ngoài nạp được file này theo đường dẫn.
Luật giữ từ sync_translations.py: không bao giờ lấy msgid làm msgstr; .po ghi bằng babel; ô glossary chép lại
chính chuỗi nguồn không phải bản dịch.
"""

import csv
import io
import os
import re
import shutil
import subprocess
import tempfile

from babel.messages.pofile import read_po, write_po

# Cột glossary ↔ mã ngôn ngữ Odoo (định dạng của Thái: key,option,VN,CN,TH)
LANG_COLUMN = {'vi_VN': 'VN', 'zh_CN': 'CN', 'th_TH': 'TH', 'en_US': 'EN'}
COLUMN_LANG = {'VN': 'vi_VN', 'CN': 'zh_CN', 'TH': 'th_TH'}
CSV_KINDS = ('model', 'model_terms', 'code')
# Module của anh Thái: không ghi đè source, dịch máy không chọn sẵn (cụm J §0). Giữ trùng scripts/i18n_tool.py
# (script chạy bằng python hệ thống không có babel nên không nạp được file này).
THAI_PREFIXES = ('wujia_franchise', 'wujia_portal_inspection', 'wujia_mobile_', 'wujia_fields_value',
                 'dynamic_dashboard_ai_nexgen')

TAG_SPLIT = re.compile(r'(<[^>]+>)')


def load_glossary(path):
    """{msgid_hoặc_key: {'VN': ..., 'CN': ..., 'TH': ...}} — map cả 2 chiều key và VN."""
    if not os.path.exists(path):
        print(f"  (no glossary {path}: only .po/.pot skeleton, existing msgstr kept)")
        return {}
    out = {}
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            vals = {c: (row.get(c) or '').strip() for c in ('VN', 'CN', 'TH', 'EN')}
            for k in ((row.get('key') or '').strip(), vals['VN']):
                if k:
                    out.setdefault(k, {}).update({c: v for c, v in vals.items() if v})
    return out


def existing_msgstr(po_path):
    """msgid → msgstr đã dịch của file .po hiện có (nguồn để KHÔNG đạp bản dịch cũ)."""
    if not po_path or not os.path.exists(po_path):
        return {}
    with open(po_path, 'rb') as f:
        cat = read_po(f)
    return {m.id: m.string for m in cat if m.id and m.string}


def _write_catalog(cat, target):
    write_po(target, cat, width=79, omit_header=False)


def build_po(pot_path, po_path, glossary, lang, bridge=None):
    """Ghi .po cho `lang`. Ưu tiên: glossary > msgstr cũ > rỗng. KHÔNG bao giờ dùng msgid.

    `bridge` = {msgid tiếng Anh: bản dịch tiếng Việt}. Glossary của BA đánh khoá theo
    tiếng Việt, nhưng từ S44 msgid trong code là tiếng Anh ⇒ phải bắc cầu qua vi_VN.po,
    không thì mọi nhãn field/menu tiếng Anh đều trượt glossary.
    """
    col = LANG_COLUMN.get(lang)
    keep = existing_msgstr(po_path)
    bridge = bridge or {}
    with open(pot_path, 'rb') as f:
        cat = read_po(f, locale=lang)
    cat.locale = lang

    def lookup(text):
        entry = (glossary.get(text) or glossary.get(text.strip())
                 or glossary.get(bridge.get(text, '')) or {})
        v = entry.get(col, '') if col else ''
        # glossary cũ có nhiều ô chép lại chính chuỗi nguồn — đó không phải bản dịch
        return '' if v == text else v

    n_gloss = n_keep = n_markup = 0
    for msg in cat:
        if not msg.id or not isinstance(msg.id, str):
            continue
        val = lookup(msg.id) if col else ''
        if not val and col:
            val = translate_markup(msg.id, lookup)
            n_markup += 1 if val else 0
        if val:
            n_gloss += 1
        elif keep.get(msg.id):
            val, n_keep = keep[msg.id], n_keep + 1
        msg.string = val

    os.makedirs(os.path.dirname(po_path), exist_ok=True)
    with open(po_path, 'wb') as f:
        _write_catalog(cat, f)
    return n_gloss, n_keep, sum(1 for m in cat if m.id)


def fill_po(pot_bytes, lang, lookup):
    """.po (bytes) cho `lang` từ nội dung .pot; msgstr = lookup(msgid) hoặc rỗng (lookup tự lo luật không lấy msgid)."""
    cat = read_po(io.BytesIO(pot_bytes), locale=lang)
    cat.locale = lang
    for msg in cat:
        if msg.id and isinstance(msg.id, str):
            msg.string = lookup(msg.id) or ''
    buf = io.BytesIO()
    _write_catalog(cat, buf)
    return buf.getvalue()


def translate_markup(msgid, lookup):
    """Chuỗi QWeb hay dính cả thẻ (`<i class="fa"/> Back`) nên tra thẳng là trượt.
    Dịch từng đoạn CHỮ giữa các thẻ, đoạn nào không có trong glossary thì giữ nguyên."""
    parts = TAG_SPLIT.split(msgid)
    if len(parts) == 1:
        return ''
    out, hit = [], False
    for p in parts:
        text = p.strip()
        val = lookup(text) if text and not p.startswith('<') else ''
        if val:
            hit = True
            out.append(p.replace(text, val, 1))
        else:
            out.append(p)
    return ''.join(out) if hit else ''


def msgfmt_errors(path):
    """Lỗi cú pháp của file .po theo `msgfmt -c` (bỏ warning). None = máy không có msgfmt."""
    if not shutil.which('msgfmt'):
        return None
    res = subprocess.run(['msgfmt', '-c', '-o', os.devnull, path], capture_output=True, text=True)
    errs = [line for line in res.stderr.splitlines() if ': warning:' not in line]
    if res.returncode != 0 and not errs:
        errs = [f'msgfmt exit {res.returncode}']
    return errs


def msgfmt_bytes_errors(data):
    with tempfile.NamedTemporaryFile(suffix='.po') as tmp:
        tmp.write(data)
        tmp.flush()
        return msgfmt_errors(tmp.name)


def msgfmt_ok(path):
    errs = msgfmt_errors(path)
    if errs is None:
        print("  (msgfmt not found: syntax check skipped)")
        return True
    if errs:
        print(f"  ✗ {os.path.basename(path)} syntax error:\n    " + "\n    ".join(errs[:8]))
        return False
    return True


# ---------------------------------------------------------------------------
# Glossary CSV (định dạng Thái `key,option,VN,CN,TH`; `docs/i18n-glossary.csv` không có cột option)
# ---------------------------------------------------------------------------

def column_lang(column):
    """Cột → mã ngôn ngữ: VN/CN/TH, hoặc cột đặt thẳng mã Odoo (ja_JP…)."""
    column = (column or '').strip()
    if column in COLUMN_LANG:
        return COLUMN_LANG[column]
    return column if re.fullmatch(r'[a-z]{2,3}(_[A-Z]{2})?(@\w+)?', column) else None


def lang_column(lang):
    return LANG_COLUMN.get(lang) if lang != 'en_US' else lang


def read_glossary_rows(data):
    """bytes/str CSV → [{'key', 'option', 'values': {lang: value}}]. Ô rỗng hoặc chép lại key bị bỏ."""
    if isinstance(data, bytes):
        data = data.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(data))
    if not reader.fieldnames or 'key' not in [f.strip() for f in reader.fieldnames]:
        raise ValueError('CSV must have a "key" column (key,option,VN,CN,TH).')
    lang_cols = {f: column_lang(f) for f in reader.fieldnames if f.strip() not in ('key', 'option') and column_lang(f)}
    rows = []
    for row in reader:
        key = row.get('key') or ''
        if not key.strip():
            continue
        values = {}
        for col, lang in lang_cols.items():
            v = (row.get(col) or '').strip()
            if v and v != key.strip():
                values[lang] = v
        rows.append({'key': key, 'option': (row.get('option') or '').strip(), 'values': values})
    return rows


def write_glossary_csv(rows, langs):
    """rows = [(key, option, {lang: value})] → bytes CSV `key,option,<cột ngôn ngữ>` (UTF-8, LF như file Thái)."""
    cols = [lang_column(lang) or lang for lang in langs]
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator='\n')
    writer.writerow(['key', 'option'] + cols)
    for key, option, values in rows:
        writer.writerow([key, option] + [values.get(lang, '') for lang in langs])
    return buf.getvalue().encode('utf-8')


def parse_option(option):
    """`model:<model,field>:<xmlid>` · `model_terms:<model,field>:<xmlid>` · `code:<path>[:<line>]`
    → (kind, name, res_id) theo đúng cách `wujia.i18n.term` lưu; chuỗi code: name = path, res_id = path:line."""
    option = (option or '').strip()
    kind, sep, rest = option.partition(':')
    if not sep or kind not in CSV_KINDS or not rest:
        return None
    if kind == 'code':
        path, _sep, line = rest.rpartition(':')
        if not path or not line.isdigit():
            path = rest
        return kind, path, rest
    name, _sep, xmlid = rest.partition(':')
    if not name or not xmlid:
        return None
    return kind, name, xmlid


def format_option(kind, name, res_id):
    if kind.startswith('code'):
        return f'code:{res_id or name}'
    return f'{kind}:{name}:{res_id}'
