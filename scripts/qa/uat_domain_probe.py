#!/usr/bin/env python3
"""Đếm bản ghi THẬT trên UAT cho từng điều kiện lọc trong tài liệu BA — CHỈ ĐỌC.

    python3 scripts/qa/uat_domain_probe.py --count product.product "[('is_public_portal','=',True)]"
    python3 scripts/qa/uat_domain_probe.py --file docs/controller-spec/probes.json \
            --json docs/controller-spec/uat_counts.json
    python3 scripts/qa/uat_domain_probe.py --fields product.product is_public_portal

An toàn: chỉ cho phép method đọc (search_count/search_read/read/fields_get/read_group).
Mọi method ghi bị chặn ngay trong script — phiên tài liệu không được đụng dữ liệu UAT.

probes.json = [{"key","model","domain","label","note"}...]; `domain` là chuỗi Python.
"""
import argparse
import ast
import datetime
import json
import os
import pathlib
import sys
import xmlrpc.client

ROOT = pathlib.Path(__file__).resolve().parents[2]
URL = os.environ.get('WJ_UAT_URL', 'https://dev.wujiatea.com.vn')
DB = os.environ.get('WJ_UAT_DB', 'wujia_tea_19')      # bẫy DOC-CTRL: KHÔNG phải wujia_tea
USER = os.environ.get('WJ_UAT_USER', 'admin')
PWD = os.environ.get('WJ_UAT_PWD', 'Wujia@2026')

READ_ONLY = {'search_count', 'search_read', 'read', 'fields_get', 'read_group',
             'search', 'default_get', 'name_search'}


class UAT:
    def __init__(self):
        common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
        self.uid = common.authenticate(DB, USER, PWD, {})
        if not self.uid:
            raise SystemExit(f'Không đăng nhập được {DB}@{URL}')
        self.models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')

    def call(self, model, method, *args, **kw):
        if method not in READ_ONLY:
            raise SystemExit(f'CHẶN: {method} không phải method đọc')
        return self.models.execute_kw(DB, self.uid, PWD, model, method, list(args), kw)

    def count(self, model, domain):
        return self.call(model, 'search_count', domain)


def parse_domain(text):
    if isinstance(text, list):
        return text
    return ast.literal_eval(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--count', nargs=2, metavar=('MODEL', 'DOMAIN'))
    ap.add_argument('--fields', nargs='+', metavar='MODEL FIELD',
                    help='mô tả field: MODEL f1 f2 ...')
    ap.add_argument('--file', help='JSON danh sách probe')
    ap.add_argument('--json', dest='out', help='ghi kết quả ra file')
    args = ap.parse_args()

    uat = UAT()
    stamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

    if args.count:
        model, dom = args.count
        print(uat.count(model, parse_domain(dom)))
        return 0

    if args.fields:
        model, fields = args.fields[0], args.fields[1:]
        meta = uat.call(model, 'fields_get', fields or [],
                        attributes=['string', 'type', 'selection', 'store', 'relation'])
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        return 0

    if not args.file:
        ap.error('cần --count, --fields hoặc --file')

    path = pathlib.Path(args.file)
    if not path.is_absolute():
        path = ROOT / path
    probes = json.loads(path.read_text(encoding='utf-8'))
    out = []
    for p in probes:
        row = dict(p)
        try:
            row['count'] = uat.count(p['model'], parse_domain(p['domain']))
        except Exception as exc:                      # model chưa cài / field đổi tên
            row['count'] = None
            row['error'] = str(exc).splitlines()[-1][:200]
        out.append(row)
        print(f"{str(row['count']):>8}  {p['key']:38s} {p['model']}")

    data = {'url': URL, 'db': DB, 'measured_at': stamp, 'probes': out}
    if args.out:
        o = pathlib.Path(args.out)
        if not o.is_absolute():
            o = ROOT / o
        o.parent.mkdir(parents=True, exist_ok=True)
        o.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'→ {o}  ({len(out)} phép đếm, {stamp})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
