#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đồng bộ bản dịch .po/.pot cho module custom WujiaTea.

Luồng (giữ nguyên thiết kế gốc của anh Thái — phần này đúng):
    odoo-bin i18n export -l pot   → lấy .pot THẬT từ DB (có cả model_terms:ir.ui.view
                                     nên dịch được cả chữ trong template QWeb)
    → điền msgstr từ glossary CSV → ghi .po + .pot vào <mod>/i18n/
    → odoo-bin i18n import -w     → nạp vào DB

Khác bản gốc ở 4 chỗ QUAN TRỌNG:
  1. Không hard-code module/ngôn ngữ/đường dẫn python — tất cả là tham số.
  2. KHÔNG bao giờ lấy msgid làm msgstr. Không có trong glossary thì GIỮ msgstr cũ
     của file .po hiện có (bản gốc ghi đè sạch vi_VN.po bằng chính msgid).
  3. Dùng babel đọc/ghi .po thay cho regex tự chế (regex cắt chuỗi tại dấu \\" và
     chèn xuống dòng thật vào trong chuỗi ⇒ .po không parse được).
  4. Luôn ghi .pot cùng lượt với .po, và chạy msgfmt -c trước khi import.

Ví dụ:
    python3 scripts/sync_translations.py --modules wujia_franchise --langs zh_CN --dry-run
    python3 scripts/sync_translations.py --modules wujia_franchise,wujia_core \\
        --langs vi_VN,zh_CN,th_TH --db wujia_tea_19 --import
"""

import argparse
import configparser
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wj_paths  # noqa: E402

ODOO_BIN = str(wj_paths.odoo_dir() / 'odoo-bin')
DEFAULT_CONFIG = os.path.join(BASE_DIR, 'config', 'odoo.conf')
DEFAULT_GLOSSARY = os.path.join(BASE_DIR, 'docs', 'i18n-glossary.csv')

# Đọc glossary / ghi .po dùng chung với module wujia_i18n (J-T4) — một bản code duy nhất.
# Nạp theo đường dẫn để không kéo theo odoo (wujia_i18n/__init__.py import models).
_spec = importlib.util.spec_from_file_location(
    'wj_po_writer', str(wj_paths.module_path('wujia_i18n') / 'tools' / 'po_writer.py'))
po_writer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(po_writer)
LANG_COLUMN = po_writer.LANG_COLUMN
load_glossary = po_writer.load_glossary
existing_msgstr = po_writer.existing_msgstr
build_po = po_writer.build_po
msgfmt_ok = po_writer.msgfmt_ok


def die(msg):
    print(f"LỖI: {msg}", file=sys.stderr)
    sys.exit(1)


def read_conf(path):
    cp = configparser.ConfigParser()
    cp.read(path)
    return cp['options'] if cp.has_section('options') else {}


def all_custom_modules():
    dirs = [d for d in wj_paths.ADDON_DIRS if d not in ('themes', 'third_party/oca_queue')]
    return [p.name for p in wj_paths.iter_modules(dirs=dirs)]


def export_pot(module, python, config, db, out_path):
    cmd = [python, ODOO_BIN, 'i18n', 'export', '-c', config, '-d', db,
           '-l', 'pot', '-o', out_path, module]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(out_path):
        die(f"export .pot cho {module} thất bại:\n{res.stderr[-2000:]}")
    return out_path


def ensure_langs(langs, python, config, db):
    """Bật ngôn ngữ chưa cài — `i18n import` từ chối lang chưa active."""
    code = ("installed = {c for c, _n in env['res.lang'].get_installed()}\n"
            "missing = [l for l in %r if l not in installed]\n"
            "for l in missing:\n"
            "    env['res.lang']._activate_lang(l) or env['res.lang']._create_lang(l)\n"
            "env.cr.commit()\n"
            "print('WJ_ACTIVATED:' + ','.join(missing))\n" % (langs,))
    res = subprocess.run([python, ODOO_BIN, 'shell', '-c', config, '-d', db, '--no-http'],
                         input=code, capture_output=True, text=True)
    for line in res.stdout.splitlines():
        if line.startswith('WJ_ACTIVATED:'):
            new = [c for c in line.split(':', 1)[1].split(',') if c]
            if new:
                print(f"  đã bật ngôn ngữ: {', '.join(new)}")
            return True
    print(f"  ✗ không bật được ngôn ngữ: {res.stderr[-500:]}")
    return False


def import_po(po_path, lang, python, config, db):
    cmd = [python, ODOO_BIN, 'i18n', 'import', '-c', config, '-d', db,
           '-l', lang, '-w', po_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  ✗ nạp {lang} vào DB thất bại: {res.stderr[-800:]}")
        return False
    print(f"  → đã nạp {lang} vào DB {db}")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--modules', help="danh sách module, phẩy ngăn cách. 'all' = mọi module custom")
    ap.add_argument('--langs', default='vi_VN', help='mã ngôn ngữ Odoo, phẩy ngăn cách')
    ap.add_argument('--db', help='tên DB (mặc định lấy db_name trong odoo.conf)')
    ap.add_argument('--config', default=DEFAULT_CONFIG)
    ap.add_argument('--glossary', default=DEFAULT_GLOSSARY)
    ap.add_argument('--python', default=sys.executable, help='python chạy odoo-bin')
    ap.add_argument('--dry-run', action='store_true', help='ghi ra /tmp, không đụng repo')
    ap.add_argument('--import', dest='do_import', action='store_true',
                    help='nạp .po vào DB sau khi sinh (mặc định KHÔNG)')
    args = ap.parse_args()

    if not args.modules:
        die("phải truyền --modules tường minh (dùng --modules all nếu thật sự muốn chạy diện rộng)")

    conf = read_conf(args.config)
    db = args.db or conf.get('db_name')
    if not db:
        die('không xác định được DB — truyền --db hoặc đặt db_name trong odoo.conf')

    modules = all_custom_modules() if args.modules == 'all' else \
        [m.strip() for m in args.modules.split(',') if m.strip()]
    langs = [l.strip() for l in args.langs.split(',') if l.strip()]
    unknown = [l for l in langs if l not in LANG_COLUMN]
    if unknown:
        print(f"Cảnh báo: {', '.join(unknown)} chưa có cột trong glossary — "
              f"chỉ giữ msgstr cũ, không điền mới.")

    glossary = load_glossary(args.glossary)
    print(f"DB={db} · {len(modules)} module · ngôn ngữ {', '.join(langs)} · "
          f"{len(glossary)} khoá glossary" + (' · DRY-RUN' if args.dry_run else ''))

    tmp = tempfile.mkdtemp(prefix='wj_i18n_')
    written, failed = [], []
    try:
        for mod in modules:
            mod_dir = wj_paths.module_path(mod)
            if not mod_dir:
                die(f"không có module {mod}")
            mod_dir = str(mod_dir)
            print(f"\n[{mod}]")
            pot_tmp = export_pot(mod, args.python, args.config, db,
                                 os.path.join(tmp, f'{mod}.pot'))

            i18n_dir = os.path.join(tmp, mod) if args.dry_run else os.path.join(mod_dir, 'i18n')
            os.makedirs(i18n_dir, exist_ok=True)

            # .pot phải đi cùng .po — .pot cũ làm msgid mới thành obsolete, im lặng (L8/3)
            pot_out = os.path.join(i18n_dir, f'{mod}.pot')
            shutil.copyfile(pot_tmp, pot_out)
            written.append(pot_out)

            # vi_VN của module = cầu nối msgid tiếng Anh → khoá tiếng Việt của glossary
            bridge = existing_msgstr(os.path.join(mod_dir, 'i18n', 'vi_VN.po'))

            for lang in langs:
                po_out = os.path.join(i18n_dir, f'{lang}.po')
                src_po = po_out if args.dry_run is False else os.path.join(mod_dir, 'i18n', f'{lang}.po')
                if args.dry_run and os.path.exists(src_po):
                    shutil.copyfile(src_po, po_out)
                g, k, tot = build_po(pot_tmp, po_out, glossary, lang, bridge)
                print(f"  {lang}: {tot} chuỗi — {g} từ glossary, {k} giữ bản dịch cũ, "
                      f"{tot - g - k} chưa dịch")
                if msgfmt_ok(po_out):
                    written.append(po_out)
                else:
                    failed.append(po_out)

        if failed:
            die(f"{len(failed)} file .po hỏng cú pháp — KHÔNG nạp vào DB. "
                f"Sửa script/glossary rồi chạy lại.")

        if args.do_import and not args.dry_run:
            print()
            ensure_langs(langs, args.python, args.config, db)
            for path in written:
                if path.endswith('.pot'):
                    continue
                import_po(path, os.path.basename(path)[:-3], args.python, args.config, db)

        print(f"\nXong: {len(written)} file"
              + (f" (dry-run, nằm ở {tmp})" if args.dry_run else ""))
    finally:
        if not args.dry_run:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
