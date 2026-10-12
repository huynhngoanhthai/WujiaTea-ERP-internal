# WujiaTea ERP — core

Odoo 19 Community + portal Vuexy cho chuỗi nhượng quyền trà sữa. Repo này là **core**: mỗi quốc gia / bên nhượng quyền
triển khai bằng một bản clone, phần riêng đặt trong `addons/`.

## Bố cục

```
Odoo19C/            Odoo 19 Community — ngoài repo (hoặc odoo19/ trong repo, gitignore)
WujiaTea/
├─ config/          odoo.conf.example, nginx
├─ docs/            tài liệu, chapters/, design/
├─ scripts/         wj_paths.py, start/upgrade, qa/
├─ base/            nền: wujia_core, khung portal + khung mobile, i18n, audit
├─ franchise/       cửa hàng, hợp đồng, khảo sát, vận hành, yêu cầu cập nhật thông tin
├─ sales/           bán hàng, khung giờ đặt hàng, đổi trả
├─ logistics/       nhà xe, giao hàng
├─ account/         công nợ theo cửa hàng
├─ academy/         kiến thức, đăng ký thi
├─ service/         hỗ trợ, thông báo
├─ portal/          wujia_portal_base + wujia_portal_<chức năng> (controller mỏng + QWeb)
├─ mobile/          wujia_mobile_<x> (giao diện backend trên điện thoại)
├─ bi/              Metabase, Dashboard Ninja
├─ tools/           tiện ích kỹ thuật (MCP, login-as, xem giá trị field)
├─ themes/          theme backend (MuK, Legion)
├─ third_party/     module bên ngoài: oca/, oca_queue/, om/, misc/
└─ addons/          rỗng ở core — module riêng của từng bản triển khai
```

Tên kỹ thuật module không phụ thuộc folder. Tìm một module: `python3 scripts/wj_paths.py --where wujia_exam`.

## Module mới đặt ở đâu

1. Folder là **miền nghiệp vụ**; tầng module theo ADR-027 (`docs/chapters/74-adr027-module-layering.tex`).
   `base/` = nền + khung kênh, `portal/` và `mobile/` = module ghép, còn lại = nghiệp vụ.
2. `wujia_portal_<x>` luôn ở `portal/`, `wujia_mobile_<x>` luôn ở `mobile/`, dù nghiệp vụ của nó ở folder nào.
3. `third_party/` và `themes/` là code bên ngoài: muốn đổi hành vi thì kế thừa ở module Wujia. Buộc phải vá tại chỗ
   (lỗi bảo mật) thì ghi rõ trong commit.
4. Module chỉ dùng cho một bản triển khai đặt ở `addons/`; không sửa folder core trong bản clone.
5. Thêm **folder** mới: thêm vào `ADDON_DIRS` trong `scripts/wj_paths.py`, rồi sinh lại `addons_path` ở mọi máy.

Kiểm luật: `python3 scripts/qa/check_layers.py` (tầng + folder).

Test đọc file của module khác: dùng `odoo.addons.wujia_portal_layout.tests.src_paths` (`src`, `src_modules`,
`src_walk`, `src_rel`), không ghép đường dẫn từ thư mục cha.

## Chạy local

```
cp config/odoo.conf.example config/odoo.conf      # sửa đường dẫn + mật khẩu
python3 scripts/wj_paths.py --addons-path         # dán kết quả vào addons_path
scripts/start.sh                                  # dev, hot-reload
scripts/upgrade.sh wujia_portal_base              # -u một module
```

Odoo core được dò theo thứ tự: biến `WUJIA_ODOO` → `../Odoo19C` → `./odoo19`.

## Deploy

Máy chạy chỉ cần đúng `addons_path` (lệnh trên) rồi khởi động lại; đổi folder không cần migrate DB.
Module cần `-u` giữa hai commit: `python3 scripts/wj_paths.py --changed-modules <cũ> <mới>` (file chỉ đổi chỗ
không tính). Hiện trạng máy UAT và thứ tự thao tác: ADR-028 §Máy chủ.

## Tài liệu

- Trạng thái dự án, quy ước: `docs/wujia-compact-summary.md`
- Kiến trúc tầng module: ADR-027 (chapter 74) · bố cục source: ADR-028 (chapter 82)
- Nhánh + deploy: `docs/next-session-repo-migration.md`
