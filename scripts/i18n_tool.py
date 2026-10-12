#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nhập/xuất bản dịch từ terminal — gọi lại đúng code của module wujia_i18n (model `wujia.i18n.transfer`)
qua `odoo-bin shell`, không có bản logic thứ hai. Module phải đã cài trên DB; nên quét chuỗi trước (`--scan`).

Lệnh:
    import-csv FILE      nạp glossary CSV (key,option,VN,CN,TH) vào tool, áp ngay nhãn/menu/view
    export-csv           xuất CSV cùng định dạng
    export-po            xuất zip .po + .pot từng module (hoặc --write-source ghi thẳng vào <mod>/i18n/)

Ví dụ:
    python3 scripts/i18n_tool.py import-csv docs/i18n-glossary.csv --db wujia_x --scan
    python3 scripts/i18n_tool.py export-csv --modules wujia_portal_exam --langs zh_CN -o /tmp/exam.csv
    python3 scripts/i18n_tool.py export-po --modules wujia_portal_exam --langs vi_VN,zh_CN --write-source
"""

import argparse
import base64
import configparser
import io
import json
import os
import subprocess
import sys
import zipfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wj_paths  # noqa: E402

ODOO_BIN = str(wj_paths.odoo_dir() / 'odoo-bin')
DEFAULT_CONFIG = os.path.join(BASE_DIR, 'config', 'odoo.conf')
# Module của anh Thái: không ghi đè source (cụm J §0).
THAI_PREFIXES = ('wujia_franchise', 'wujia_portal_inspection', 'wujia_mobile_', 'wujia_fields_value',
                 'dynamic_dashboard_ai_nexgen')
MARK = 'WJ_I18N_RESULT:'

SHELL_CODE = r'''
import base64, json
args = json.loads(%r)
T = env['wujia.i18n.transfer']
modules = args['modules'] or env['wujia.i18n.scan.wizard']._default_modules().mapped('name')
langs = args['langs'] or [c for c, _n in env['res.lang'].get_installed() if c != 'en_US']
out = {'modules': modules, 'langs': langs}
if args['scan']:
    out['scan'] = env['wujia.i18n.term']._wj_scan(modules, langs)
if args['cmd'] == 'import-csv':
    with open(args['file'], 'rb') as f:
        out['import'] = T._wj_import_csv(f.read(), overwrite_edited=args['overwrite_edited'],
                                         apply=args['apply'], src_mode=args['src_mode'])
elif args['cmd'] == 'export-csv':
    data = T._wj_export_csv(modules, langs, only_edited=args['only_edited'])
    out['data'] = base64.b64encode(data).decode()
elif args['cmd'] == 'export-po':
    data, notes = T._wj_export_po_zip(modules, langs)
    out['data'], out['notes'] = base64.b64encode(data).decode(), notes
env.cr.commit()
print(%r + json.dumps(out, ensure_ascii=False))
'''


def die(msg):
    print(f"LỖI: {msg}", file=sys.stderr)
    sys.exit(1)


def split(value):
    return [v.strip() for v in (value or '').split(',') if v.strip()]


def is_thai(module):
    return module.startswith(THAI_PREFIXES)


def run_shell(args, payload):
    cmd = [args.python, ODOO_BIN, 'shell', '-c', args.config, '-d', args.db, '--no-http']
    if args.logfile:
        cmd.append(f'--logfile={args.logfile}')
    res = subprocess.run(cmd, input=SHELL_CODE % (json.dumps(payload), MARK), capture_output=True, text=True)
    for line in res.stdout.splitlines():
        if line.startswith(MARK):
            return json.loads(line[len(MARK):])
    die(f"odoo shell không trả kết quả (exit {res.returncode}):\n{(res.stderr or res.stdout)[-2000:]}")


def write_source(zip_bytes):
    """Giải zip vào <mod>/i18n/; bỏ module không có trong repo hoặc của Thái."""
    written, skipped = [], set()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            parts = name.split('/')
            if len(parts) != 3 or parts[1] != 'i18n':
                continue
            module = parts[0]
            mod_dir = wj_paths.module_path(module)
            if is_thai(module) or not mod_dir:
                skipped.add(module)
                continue
            path = os.path.join(str(mod_dir), 'i18n', parts[2])
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(zf.read(name))
            written.append(os.path.relpath(path, BASE_DIR))
    return written, sorted(skipped)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['import-csv', 'export-csv', 'export-po'])
    ap.add_argument('file', nargs='?', help='file CSV (import-csv)')
    ap.add_argument('--modules', help='phẩy ngăn cách; mặc định module wujia_%%/wj_%% đã cài')
    ap.add_argument('--langs', help='phẩy ngăn cách; mặc định mọi ngôn ngữ đã bật trừ en_US')
    ap.add_argument('--db', help='mặc định db_name trong odoo.conf')
    ap.add_argument('--config', default=DEFAULT_CONFIG)
    ap.add_argument('--python', default=sys.executable, help='python chạy odoo-bin')
    ap.add_argument('--logfile', help='log odoo (mặc định theo odoo.conf)')
    ap.add_argument('--scan', action='store_true', help='quét chuỗi các module trước khi chạy')
    ap.add_argument('--overwrite-edited', action='store_true', help='import: đè cả bản đã sửa tay trong tool')
    ap.add_argument('--update-all-matches', action='store_true',
                    help='import: dòng chỉ khớp theo câu nguồn cũng đè bản đã dịch (mặc định chỉ điền chỗ trống)')
    ap.add_argument('--no-apply', action='store_true', help='import: chỉ ghi vào tool, chưa áp vào DB')
    ap.add_argument('--only-edited', action='store_true', help='export-csv: chỉ term có bản sửa tay')
    ap.add_argument('-o', '--output', help='file ra (export-csv / export-po)')
    ap.add_argument('--write-source', action='store_true',
                    help='export-po: ghi thẳng .po/.pot vào <mod>/i18n/ (từ chối module của Thái)')
    args = ap.parse_args()

    cp = configparser.ConfigParser()
    cp.read(args.config)
    args.db = args.db or (cp['options'].get('db_name') if cp.has_section('options') else None)
    if not args.db:
        die('không xác định được DB — truyền --db')
    modules = split(args.modules)
    if args.cmd == 'import-csv':
        if not args.file or not os.path.isfile(args.file):
            die('import-csv cần đường dẫn file CSV')
    elif args.cmd == 'export-po' and args.write_source:
        thai = [m for m in modules if is_thai(m)]
        if thai:
            die(f"không ghi source module của Thái: {', '.join(thai)}")
    elif not args.output and not args.write_source:
        die('cần -o FILE (hoặc --write-source cho export-po)')

    payload = {
        'cmd': args.cmd, 'file': os.path.abspath(args.file) if args.file else None,
        'modules': modules, 'langs': split(args.langs), 'scan': args.scan,
        'overwrite_edited': args.overwrite_edited, 'apply': not args.no_apply,
        'src_mode': 'all' if args.update_all_matches else 'missing', 'only_edited': args.only_edited,
    }
    res = run_shell(args, payload)
    print(f"DB={args.db} · {len(res['modules'])} module · {', '.join(res['langs'])}")
    if 'scan' in res:
        print(f"  quét: {res['scan']}")
    if args.cmd == 'import-csv':
        st = res['import']
        print(f"  {st['rows']} dòng: {st.get('matched_by_ref', 0)} khớp ref, {st.get('matched_by_source', 0)} khớp câu nguồn, "
              f"{st.get('unmatched', 0)} không thấy")
        print(f"  {st.get('updated', 0)} bản dịch đổi ({st.get('applied', 0)} đã áp), {st.get('unchanged', 0)} giống sẵn, "
              f"{st.get('kept_edited', 0)} giữ bản sửa tay, {st.get('kept_translated', 0)} giữ bản đã dịch, "
              f"{st.get('code_waiting_export', 0)} chuỗi code chờ export-po · {st['seconds']}s")
        if st.get('unmatched_samples'):
            print('  ví dụ không thấy: ' + ' | '.join(s[:60] for s in st['unmatched_samples'][:5]))
        return
    data = base64.b64decode(res['data'])
    for note in res.get('notes') or []:
        print(f"  ! {note}")
    if args.output:
        with open(args.output, 'wb') as f:
            f.write(data)
        print(f"  → {args.output} ({len(data)} byte)")
    if args.write_source:
        written, skipped = write_source(data)
        print(f"  → ghi {len(written)} file vào thư mục module")
        if skipped:
            print(f"  bỏ qua (không có trong repo hoặc module Thái): {', '.join(skipped)}")


if __name__ == '__main__':
    main()
