# WujiaTea — Compact summary

**Mục đích:** context inject vào mọi session. Mỗi §section search-able qua `/recall`. History chi tiết → `chapters/*.tex` + git log.

**Cập nhật:** 2026-10-14 · **K2 XONG** — #182 Shared Form Validation trên 6 form (Hỗ trợ, Bù hàng, Khắc phục, Cập nhật thông tin, Đổi mật khẩu, Đăng ký thi) lên UAT `e61baf83` (`docs/k2-uat-measure.md`); API `window.wjFormValidate.check/reset` + luật `data-wj-match` cho khối không có `<form>`; phiên kế **S0** (#185 thiết kế bán theo tồn). · **K1 XONG** — #187 + #188 + #186 form + chi tiết Hỗ trợ lên UAT `00e9443f` (`docs/k1-uat-measure.md`); hạt giống Shared Form Validation ở khung (`wj_form_validate.js` + partial `wj_field_error`, bật bằng `data-wj-validate`) — K2 đã mở rộng. · **K0 XONG** — #139 + #73 + #37 lên UAT `319a16fb`, sheet `Ready for Retest` (`docs/k0-uat-measure.md`); phiên kế **K1**. · **CHIA CỤM K** — 15 issue `Ready for Dev` còn lại + 2 tính năng (#185 bán theo tồn, #181 portal Vận hành): `docs/next-session-clusters-K.md`. · 2026-10-12 · **HẠ TẦNG MỚI** — UAT `https://dev.wujiatea.com.vn` thay máy `113.161.187.126:8019`, repo `huynhngoanhthai/WujiaTea-ERP-internal`, aaPanel + Metabase (`docs/CREDENTIALS.md`); đổi repo + mô hình nhánh: `docs/next-session-repo-migration.md`. · 2026-10-10 · **END-SPRINT 67 — CỤM I (21 issue Issue List) + ★IR XONG, ĐÃ LÊN UAT ĐỦ** (chapter **81**; báo cáo `docs/i-review.md`). Việc kế: cụm H / Phần O cụm J (chờ BA). Tồn đọng: **`docs/pending-backlog.md`**. Lịch sử State/batch cũ: **`docs/archive/compact-summary-history.md`** (không cần đọc mỗi phiên).

---

## §1 wujia-overview

**Project:** Odoo 19 ERP + custom Vuexy portal cho chuỗi nhượng quyền trà sữa (~1500 portal user). Migrate v14 → v19.

**Dir:**
- `WujiaTea/odoo19/` Odoo 19 Community (read-only; script dò `WUJIA_ODOO` → `../Odoo19C` → `./odoo19`) · module chia folder theo miền (ADR-028, §2): `base/ franchise/ sales/ logistics/ account/ academy/ service/ portal/ mobile/ bi/` (Wujia) · `tools/ themes/ third_party/{oca,oca_queue,om,misc}/` (bên ngoài) · `addons/` (rỗng ở core, module riêng từng bản clone). **Không còn `custom/`.** Tìm module: `python3 scripts/wj_paths.py --where <mod>` · `data/` seed · `scripts/` seed+deploy · `docs/` (`wujia-tea-doc.tex` master + `chapters/` + `wujia-design-system.md` + `0[1-3]_*` chuẩn QA/Task/OAuth).
- v14 reference: `/home/huyban/odoo-dev/wujia_tea_odoo14` — template ref, **không sửa**.

**BA spec = Google Sheet "Internal ERP Master Plan_Update"** online (§7 tab/gid). Xlsm local = legacy fallback.

**Figma (BA design, READ-ONLY):** file key = **BẢN COPY** `aoeiDYlg6vlhJZg2w6Q7o5` ("Wujia (Copy)"); gốc `vfVcqN5zPJvlcjZU4NYim0` bị throttle, không dùng. BA CHƯA xong Figma → **ưu tiên code chuẩn > Figma > xlsm (lag)**. Cách kết nối MCP + xử lý Figma phẳng: `docs/figma-mcp-setup.md`. Token/component: `docs/wujia-design-system.md`.

**Local dev:**
- Scripts: `init-db.sh` fresh · `start.sh` hot-reload · `upgrade.sh <mod>` giữ data · `reseed_full.sh` 1-shot.
- DB `wujia_tea_19`, user `odoo19/1`, `127.0.0.1:5432`.
- Log `logs/odoo.log` · config `config/odoo.conf` · python `/home/huyban/miniconda3/envs/odoo/bin/python3`.

**UAT:** → §12 (`https://dev.wujiatea.com.vn/`, `admin` / `Wujia@2026` — kiểm đăng nhập được 12/10; máy cũ `113.161.187.126:8019` ngừng dùng 12/10).

**Deploy:** → §6 (máy mới, quy trình chờ phiên repo; module mới cần `-i`).

---

## §2 wujia-modules (21 active + `wujia_order_window` từ F7 + `wujia_info_request` từ F8 + `wujia_knowledge` từ F9 + `wujia_support` từ F10 + `wujia_notification` từ F11 + `wujia_exam` từ F12 + `wujia_return` từ F13)

**Folder (ADR-028, `python3 scripts/wj_paths.py --list`):** `base/` core · portal_layout · mobile_core · i18n · audit │ `franchise/` franchise · _contract · _inspection · _operations · info_request │ `sales/` sale · order_window · return │ `logistics/` fleet · delivery │ `account/` account │ `academy/` knowledge · exam │ `service/` support · notification │ `portal/` portal_base + 12 `portal_<x>` │ `mobile/` 7 `mobile_<x>` │ `bi/` metabase_connector · 2 dashboard ninja │ `tools/` mcp · login_as · fields_value │ `themes/` MuK · Legion │ `third_party/` oca (4) · oca_queue (8) · om (8) · misc (5). 81 module, 17 mục `addons_path`. `portal_<x>` luôn ở `portal/`, `mobile_<x>` luôn ở `mobile/`; folder mới ⇒ thêm vào `ADDON_DIRS` (`scripts/wj_paths.py`).

| Module | Vai trò |
|---|---|
| `wujia_core` | `res.area`, `res.ward` master data |
| `wujia_franchise` | `wujia.franchise.management` + `wujia.franchise.member` (có icon) |
| `wujia_sale` | `sale.order` ext + product portal fields + `wujia.product.category` |
| `wujia_fleet` | Nhà xe / loại xe / xe / bảng giá (có icon) |
| `wujia_delivery` | `stock.picking/batch` ext + cước vận chuyển |
| `wujia_portal_layout` | Vuexy shell + CSS vars + Inter + responsive + utility class |
| `wujia_portal_base` | `/portal` dashboard + `bus.bus` realtime + franchise switch |
| `wujia_portal_sale` | `/portal/order` catalog + cart (`wujia.portal.cart(.line)`) |
| `wujia_portal_purchase_history` | `/portal/purchase-history` |
| `wujia_portal_delivery` | `/portal/delivery` |
| `wujia_return` | (F13, L2) `wujia.return.request` + loại lỗi + `wujia.compensation.allocation` + wizard SO 0đ FIFO + kế thừa SO/picking/product (Sprint K) + 2 nhóm quyền + 2 sequence (`RTN/`, `CA/`); luật portal `_portal_eligible_order_domain` (10 ngày) / `_portal_check_product_config` / `_portal_check_evidence` / `create_from_portal` (savepoint) / `_portal_status_key` + `_portal_status_domain` / `_portal_open_domain` + `_portal_recent_domain` / `_portal_compensation_view` |
| `wujia_portal_return` | `/portal/return` (controller + 3 QWeb + 2 nav, nghiệp vụ ở `wujia_return`); nhãn trạng thái một nguồn `RETURN_STATUS_LABELS` ở `portal_base/controllers/utils.py` |
| `wujia_notification` | (F11, L2) 3 model thông báo/loại/đã đọc + 2 nhóm quyền + rule + sequence `ANN/` + backend quản trị (vòng đời draft/published/archived, thống kê đọc, Sprint 41); `_portal_history_domain` / `_portal_effective_domain` (dùng chung màn Thông báo + chuông + Home) / `_portal_unread_count` (theo cửa hàng) / `_portal_get_attachment` / `wujia.notification.read._mark_read` |
| `wujia_portal_notification` | `/portal/notification` + chuông header + nav (controller + 4 QWeb, nghiệp vụ ở `wujia_notification`) |
| `wujia_exam` | (F12, L2) 5 model khoá/kỳ thi/ca giờ/phiếu/thí sinh + 2 nhóm quyền + 2 rule + 3 sequence + backend Đăng ký thi (Sprint M); `_effective_max_per_registration` (một nguồn: ca, trống thì khoá — hướng dẫn + chặn portal + constraint) / `_portal_slot_status` / `_portal_day_states` / `_portal_booking_meta` / `_portal_scope_domain` / `register_from_portal` (`ExamPortalError(kind)`) |
| `wujia_portal_exam` | `/portal/exam` (controller + 3 QWeb + 2 nav, nghiệp vụ ở `wujia_exam`) |
| `wujia_knowledge` | (F9, L2) 3 model bài/danh mục/tag + backend HQ + cron hạ bài hết hạn + sequence KNW-; `_portal_visible_domain` (dùng chung màn Kiến thức + Home) / `_portal_search_domain` / `_portal_get_attachment` |
| `wujia_portal_knowledge` | `/portal/knowledge` (controller + 3 QWeb + 2 nav, nghiệp vụ ở `wujia_knowledge`) |
| `wujia_portal_report` | `/portal/reports/orders` |
| `wujia_support` | (F10, L2) ticket hỗ trợ + danh mục + backend HQ + sequence `WJ-TK/`; `_portal_scope_domain` (theo người tạo) / `create_from_portal` (một savepoint, trả mã lỗi form) / `_portal_reply` / `_portal_get_attachment` |
| `wujia_portal_support` | `/portal/support` (controller + 3 QWeb + 2 nav + bảng badge mobile, nghiệp vụ ở `wujia_support`) |
| `wujia_info_request` | (F8, L2) model `wujia.info.update.request` + backend HQ duyệt + ACL/rule/sequence INF-; `create_from_portal` / `_portal_can_request` / `_portal_scope_domain` |
| `wujia_portal_info_request` | `/portal/info-request` (controller + 3 QWeb, nghiệp vụ ở `wujia_info_request`) |
| `wujia_order_window` | **(F7, nghiệp vụ L2)** Khung giờ đặt hàng per-area + global fallback + chặn đơn portal ngoài giờ (`OrderWindowClosed`) |
| ~~`wujia_portal_order_window`~~ | **Đã gỡ** (UAT 26/09, thư mục xoá ở FR-P) — nghiệp vụ nằm ở `wujia_order_window`; hook đổi chủ dùng chung: `wujia_core/tools/module_split.py` |
| `wujia_portal_debt` | `/portal/debt` (+ `/payment-history`, `/pay`) — 7 màn mobile Figma `5013:*` (S43) + **PC 1920 Figma v1.1 `5077:*`** (S49, khối `.wj-debt-pc`). Dữ liệu THẬT từ S48 qua seam `models.AbstractModel` `wujia.portal.debt` (không bảng/không migration); guard Owner/Manager |

| `wujia_portal_inspection` | `/portal/inspection` — xem phiếu khảo sát/chấm điểm cửa hàng + gửi khắc phục (merge nhánh `thai` 19/08) |
| ~~`wujia_portal_remediation`~~ | ❌ **ĐÃ GỠ** — anh Thái tự xoá code (`f789a56`), phiên 20/08 gỡ khỏi DB bằng script, UAT `uninstalled`. **Không `-u`, không `-i`** module này. |

> Backend giám sát nằm TRONG `wujia_franchise` (8 model: `wujia.franchise.inspection[.line]` · `.inspection.grade/.question/.template[.line]/.category/.exam.line` · `wujia.supervision.schedule`) + 2 group `group_supervision_inspector/admin`.

> Dashboard workstream riêng: `wj_ks_dashboard_ninja` + `wj_ks_dn_advance` (state = `docs/dashboard-migration-plan.md`). Chi tiết: `wujia-tea-doc.tex` §1.3/§1.5.

---

## §3 wujia-adr-summary (ADR-001…028 — số 017–026 nằm rải trong chapter sprint 6/8–12)

ADR-001 odoo19 source độc lập / 002 venv conda `odoo` py3.10 / 003 PG role `odoo19` / 004 custom portal Vuexy thay `/my` / 005 `wujia.franchise.member` / 006 realtime `bus.bus` native / 007 tách Order+History / 008 URL kebab + 301 redirect / 009 block feature→defer / 010 3 field địa chỉ / 011 branch picker TẠI LOGIN / 012 *overruled by 015* / 013 `res.area`/`res.ward` ở `wujia_core` / 014 member UI độc lập / 015 gộp `wujia_franchise_management`→`wujia_franchise` / 016 dùng `mail.message` via `message_post()`.

**ADR-027 (đề xuất 17/09, ✅ ĐÃ CHỐT 26/09 — đã áp khối A F7–F13; bổ sung 3 ý ở chapter 74 §addendum: portal chia theo CHỨC NĂNG / mobile theo module backend · mobile kế thừa view chỉ extension+xpath, cấm `mode=primary`/`replace` · `auto_install` chỉ module ghép thuần — GHI, CHƯA ÁP)** tầng module (**4 tầng, chỉnh lại cùng ngày**): L0 Odoo → L1 `wujia_core` (+ `ui_core`/platform `*_core` chỉ tạo khi cần) → L2 **nghiệp vụ CÙNG CẤP khung kênh** (`wujia_portal_layout` | `wujia_mobile_core` = `web`+`muk_web_theme`, chỉ `assets_backend`; hai nhóm không depend nhau) → L3 module ghép `wujia_portal_base`→`wujia_portal_<x>` | `wujia_mobile_<x>` (`auto_install`, chỉ tạo khi có view riêng). `portal_base` = **L3a** nền ghép portal ("tầng 2.5"; luật: mọi `portal_<x>` depend nó, nó không depend `portal_<x>`), `portal_<x>`/`mobile_<x>` = L3b; giữ depend franchise+sale, **cấm thêm depend**, KHÔNG tách Home. Giữ tên `mobile_core` (khớp BA). 4 luật: nghiệp vụ không depend khung/ghép · khung không depend nghiệp vụ · hai kênh không depend chéo · module ghép không model nghiệp vụ. L1 thêm `wujia_ui_core` + platform `*_core` (theo bảng BA, chỉ tạo khi ≥2 phân hệ cần). Tách 7 phân hệ khỏi `wujia_portal_*` từng phiên: order_window → info_request → knowledge → support → notification (từ portal_notification, giữ tên `wujia_notification`) → exam → return (khuôn `pre_init_hook` đổi chủ `ir_model_data` như `wujia_franchise_inspection/hooks.py`). Doc: `docs/adr-027-module-layering.pdf` + chapter 74.

**ADR-028 (chốt + áp 12/10, chapter 82)** bố cục source theo miền kiểu Beesuite: folder = miền, tầng vẫn theo ADR-027; Wujia là core, mỗi nước/bên nhượng quyền = một bản clone + module riêng trong `addons/`; `third_party/` + `themes/` là code ngoài (đổi hành vi thì kế thừa); `scripts/wj_paths.py` là nguồn duy nhất của bố cục (`--addons-path`, `--where`, `--list`, `--changed-modules`); `check_layers.py` thêm luật R8 (module đúng folder của tầng). Tên module không đổi ⇒ 0 migration, chỉ đổi `addons_path`.

→ Chi tiết: `wujia-tea-doc.tex` chap 2 + 13.

---

## §4 wujia-sprint-history (compact — chi tiết ở `chapters/`)

| Sprint | Date | Outcome (1 dòng) |
|---|---|---|
| 67 | 10-08..10-10 | **Cụm I — 21 issue Issue List theo luật "một cửa hàng đang chọn" + role theo cửa hàng** (I1→I13 + ★IR). Helper scope/role một nguồn ở `portal_base`; khung giờ nhiều khu vực + múi giờ cửa hàng; đã đọc thông báo theo phạm vi; tương phản ≥4.5. ★IR đo UAT 274 ô ma trận + 44 kiểm từng issue; vá `afc42869`. 21 dòng → Ready for Retest. → `chapters/81-sprint67-cluster-i-issue-list.tex` |
| 66 | 10-04..10-07 | **Cụm J Phần B + T — thương hiệu cấu hình được + tool Bản dịch** (J-B1 `de64704c` → J-B2 `12c2baa9`+`3aa974ac` → J-T1+T2 `ba08698e` → J-T4 `ca198ace` → J-T5 `78a68ea5` → J-T5b smoke DeepL thật): tên/màu/logo/favicon/nền login trong Settings, mặc định 0 lệch pixel, HTML −36 %; app Translation Tool sửa + Áp dụng không restart, giữ bản sửa qua `-u`, nhập/xuất CSV + `.po`, dịch máy DeepL theo lô (không đè bản sửa tay). Tất cả đã lên UAT. Phần O pend theo BA. → ch.80 |
| 65 | 10-05..10-07 | **Cụm J Phần V — Việt hoá source** (V0 → V1…V8b → ★VR): câu gốc code team 2 375 chuỗi tiếng Việt → tiếng Anh, vi_VN qua glossary ⇒ user vi thấy y cũ, en/th/zh hết lẫn tiếng Việt; V3–V8b đã lên UAT; ★VR bỏ nhánh tra ngược badge VN, danh sách BA/Thái `docs/i18n-review/`. → ch.79 |
| 64 | 09-26..09-30 | **Cụm G — Issue List lứa 140–151** (G1 → G2 → G3a/b → H150/151 → review UAT → G5 → G6; G4 ⏸): mật độ mobile 143/145/144 `fcce811` · dải cửa hàng + top bar PC 141/140 `6745671` · Home PC V4 142 `160d13e`+`d8f89bf` · Home giống Lịch sử 150/151 `0cd1f0a` · hộp xác nhận gửi đơn 148 + lọc gửi lại 11 màn 147 `887da0a` · Ngày xác nhận 149 `9efa67f`. Mỗi lượt deploy UAT + đo chỉ-đọc, 11 ID → Ready for Retest. Chapter 78. |
| 63 | 09-25..09-26 | **Cụm F khối A — tách 7 phân hệ khỏi `wujia_portal_*` thành module nghiệp vụ L2 + controller mỏng** (F6 → F7 → ★FR-P → F8–F13 → ★FR-A), mỗi phiên 1 deploy UAT, 0 lệch dữ liệu: `wujia_order_window` · `_info_request` · `_knowledge` · `_support` · `_notification` · `_exam` · `_return`; luật portal một nguồn ở model (Home dùng chung); hook đổi chủ `wujia_core/tools/module_split.py`; `check_layers` 0 vi phạm Dev; query Δ0; suite 822 → **914/0/0**. **ADR-027 chốt.** → ch.77 |
| 62 | 09-17..09-18 | **Cổng F chuẩn hoá kiến trúc portal** (F0 → F1 → F2 → F3 → F4 → ★FR-B → F5a → F5b → ★FR-A3), 0 tính năng, gần như 0 pixel. CSS 1 màn ở `portal_layout` 193 → 26 · rule đổi dáng 41 → 8 · 24 mục điều hướng về module sở hữu route · test cross-module của khung 236 → 0 · DB trắng chỉ cài khung chạy được 129/129 · `check_layers` thêm R6/R7 · vá 2 lỗi tầng 500 có từ trước. FR-A3 kết luận **mở lại Issue List**. → ch.76 |
| 61 | 09-12..09-25 | **Cụm E — 10 issue component/backend (STT 128–139) → Ready for Retest + đã lên UAT**: E1 KPI Công nợ · E9a view Đơn hàng Ngô Gia · E9b hợp đồng nhiều kỳ · E2 StatusBadge · E3 Pagination · E4 FilterBar · E5 ListCard · E6 Button · E7 PageContainer · E8 Sidebar; kèm nhịp dọc mobile, G2 header 104→72, DOC-CTRL/-2. Suite 339 → 801, 0 đỏ. → ch.75 |
| 59 | 09-06..09-08 | **Cụm D5 DataList `CMP-DL-001`** (8 lượt D5a…D5h.1) — 33 call site về một khuôn: bảng PC (`th[scope]` 0/21 → 100%, header 44, đệm `10px 16px`, row ≥52 mềm) + thẻ mobile (compact-row 64–76 · detail-card 96–120 · gap 8 · radius 12). Kiến trúc HAI TẦNG (dáng ở `.wj-data-item`, layout ở từng họ); giao cắt D4 thắng bằng độ đặc hiệu, `_components.css` của D4 không đổi byte nào. Guard bắt **2 lỗi nghiệp vụ thật**: pager giả 3 `<span>` cứng ở franchise-information + nút trang hiện với 1 trang ở Thi/Công nợ. 68 test, 17 mutation đỏ đúng 1 test. 2 call site Khảo sát **defer**. → ch.72 |
| 58 | 09-04..09-06 | **Cụm D4 SurfaceCard `CMP-SC-001`** (7 lượt D4b…D4h) — 151/377 token khung về một chủ sở hữu; `.card` của Bootstrap/Odoo hiện = 0 trên 25 route × 5 khổ, 0 rule dáng ngoài `_components.css`. Bẫy đắt nhất: **UAT không phải git** (deploy 'D4f' thật ra chỉ có D4d vì nhánh chưa fetch) + 4 file CSS không bump `?v=` + 13/14 module không bump version. → ch.71 |
| 1–57 | 04..09-04 | Xem `docs/archive/compact-summary-history.md` §4 (cũ) + `chapters/`. |

---

## §5 wujia-current-status

**State (2026-10-10 · END-SPRINT 67) — CỤM I + ★IR CHỐT SỔ.** 21 issue (STT 62, 152–174) code xong I1→I13, chủ dự án deploy UAT 09/10 (lần đầu 2 tiến trình `-u` cùng lúc khoá DB, chạy lại theo danh sách module ⇒ 0 lệch). ★IR đo chỉ đọc trên UAT: ma trận role × cửa hàng × route `scripts/qa/wj_ir_matrix.py` 274 ô (0 HTTP ≥500, 0 lỗi JS, 0 tràn; 22 ô lệch = kỳ vọng script), `wj_ir_checks.py` 44 kiểm đạt đủ 21 issue, quét admin chưa chọn cửa hàng 0 lộ chứng từ. #170 trên UAT lộ 32 cặp <4.5 (chip Giao hàng chỉ hiện khi có dữ liệu, số Đã thanh toán Công nợ, placeholder bị `.form-control::placeholder` của bundle website đè) ⇒ vá `afc42869` (layout 19.0.60.10.1 · delivery 19.0.4.2.1 · debt 19.0.5.2.1, `?v=1336`, test 736/736). Sheet: 20 dòng Ready for Retest + #156 Done (BA đóng 10/10); `issue_queue --dev` chỉ còn #142. Ledger: 19 "ĐÃ DEPLOY UAT 09/10/2026", #160 đã có, #170 "CHƯA lên UAT (phần bổ sung)". Chapter 81. Báo cáo `docs/i-review.md`.

**Pending sống (hàng đợi):**
- ✅ **[10/10] `afc42869` ĐÃ DEPLOY UAT** (version khớp XML-RPC) · `wj_contrast` trên UAT 32 → **0** cặp <4.5 (56 trang, 4.001 mẫu) · sheet #170 ghi ĐÃ DEPLOY. Hàng đợi deploy: TRỐNG. DB `wujia_i1…i13` (+`i4b`) + filestore đã xoá.
- ✅ **[10/10] #142 UI-PC-HOME-REDESIGN-001 → Ready for Retest** kèm phản hồi BA (LIMIT): lỗi `$` do dữ liệu — bảng giá duy nhất "Default" trên UAT là USD (76/77 đơn USD), code in đúng tiền tệ đơn, PC = mobile. BA đổi bảng giá sang VND rồi đặt đơn mới để retest.
- ✅ **[10/10] Chỉnh UI header (chủ dự án yêu cầu, không Issue ID)** — badge đỏ `--wujia-danger-fill` #DC2626; topbar PC thẻ trắng (khối cửa hàng ôm nội dung ≤430, tài khoản cao 48, cụm phải áp từ 992). **Lệch Figma UI-01/UI-03 do chủ dự án chốt.** layout 19.0.60.11.0 · base 19.0.7.47.0 · `?v=1337` · test 637/637. Lần 1 thẻ trắng (`c592558c`), cùng ngày **chủ dự án đổi sang kính mờ + chữ trắng đúng Figma** — **ĐÃ DEPLOY UAT 10/10** (`8f72a740`, layout 19.0.60.12.0 · base 19.0.7.48.0 · `?v=1338`, test 637/637, đo UAT đạt). ⚠️ Ngoại lệ #170: chữ topbar PC 1.77–2.24:1, phải báo BA.
- ✅ **[10/10] Thông báo giỏ hàng (BA gửi ảnh, không Issue ID)** — thẻ báo dùng chung `window.wjToast` (khung, `wj_toast.js` + `.wj-toast*`): nền trắng, mobile ngay dưới header, PC góc phải dưới thanh trên, tự tắt 3 giây; giỏ + đặt hàng + thông báo PC cùng gọi. Thùng rác hỏi bằng hộp portal `#wjCartRemove` (thay `window.confirm`), `/cart/remove` trả `removed`. layout 19.0.60.13.0 · sale 19.0.5.5.0 · notification 19.0.5.2.0 · `?v=1339` · test 761/761 · bấm thật 390/1440/1100 đạt. **ĐÃ DEPLOY UAT 10/10** (`841f329e`), đo UAT chỉ xem đạt; BA cần retest xoá thật.
- **[12/10] Hạ tầng mới ĐÃ ÁP một phần**: `origin` của repo chính = `huynhngoanhthai/WujiaTea-ERP-internal` (repo cũ còn là remote `old`); trên origin đã có `deploy/production` (= `main`) và `deploy/staging` (nhánh làm việc, máy UAT chạy nhánh này). Làm việc: tách `feature/*` từ `deploy/staging`, PR về `deploy/staging`. Merge rồi deploy thế nào: §6 (từ 13/10 có job CI gọi webhook, chưa xác nhận có `-u`). Còn treo: tài khoản UAT mới · `~/wujia-devkit` vẫn trỏ repo cũ, có file sửa chưa commit.
- **[12/10] ADR-028 dời source theo miền — ✅ ĐÃ LÊN UAT**: PR #7 merge vào `deploy/staging` (`f3107562`), deploy 22:23 12/10 bằng nút *Deploy latest* trong aaPanel. Module nằm ở `base/ franchise/ sales/ … third_party/ addons/` (§2). Nhánh đang mở khác phải merge `deploy/staging` về; file MỚI thêm vào `custom/` phải dời tay. Còn nợ trên máy chủ: §6.
- ✅ **[14/10] K0 `319a16fb` ĐÃ DEPLOY UAT** (9/9 module khớp XML-RPC, CI tự deploy kèm `-u`) · #139 Enter ca đặc biệt 3/9 → 9/9 + ngày ngược có khối nhắc riêng ở 6 màn (`wj_filter_invalid`) · #73 H1 `payment-history` một tên · #37 `portal_product_name()` bỏ mã nội bộ (8 lượt xem → 0) · sheet 3 dòng `Ready for Retest`. Issue List còn 15 `Ready for Dev` (BA thêm #189 `UI-FILTERCHIP-001`, chưa xếp phiên). Chờ BA: câu chữ khối nhắc, ô ngày Thông báo mobile, tên trang `/portal/info-request`. DB `wujia_k0` + filestore đã xoá.
- **[14/10] Issue List có 17 `Ready for Dev` — đã chia cụm K** (`docs/next-session-clusters-K.md`): K0 #139 + #73 + #37 (**BA mở lại sau retest fail 11–12/10**, phải code, không phải chỉ sync) → K1 #187 + #188 + #186 (form Hỗ trợ) → K2 #182 (Shared Form Validation) → K3 #175 → K4 #178 → K5 #177 + #176 → K6 #179 + #180 → K7 #183 + #184 → ★KR. Tính năng: #185 WJ-ORD-033 (S0 thiết kế → S1 → S2 → ★SR) và #181 WJ-OPS-001 (Phần O cụm J).
- **Cụm H** chuẩn hoá component (`docs/next-session-clusters-H.md`): H-A (H0 → H1 → H3 → ★HR-1) không cần BA; H-B chờ BA duyệt spec.
- **Phần O cụm J** (portal Vận hành nhượng quyền) — **mở lại 14/10** theo #181 (BA xác nhận 11/10, 14 màn, mockup FINAL); chủ dự án chốt mình làm; phạm vi mới ghi ở `docs/next-session-clusters-J.md` §5 Phần O.
- **[14/10] Bố cục core trên máy UAT — anh Thái quyết và làm**: anh Thái muốn `wwwroot` chỉ chứa folder domain. Theo khảo sát 12/10, `odoo19/` đang nằm trong folder domain (= gốc repo, gitignore) nên đã đúng; chỗ lệch là `README.md` + `scripts/wj_paths.py` ưu tiên `../Odoo19C` (trên máy chủ = `/www/wwwroot/Odoo19C`). Chi tiết §6. Chưa đo lại 14/10.
- **ADR-027**: 7 câu hỏi BA (chapter 74) + áp `auto_install` đồng loạt 1 phiên + nợ ch.77 (portal_sale write, `_sql_constraints`, bàn giao Thái).
- **i18n defer**: 11 finding dịch chờ BA chốt từ vựng · BA rà dịch máy zh/th · nhãn `member.role` tiếng Việt trong `display_name`.
- **Thông báo NOTI-02 bước 2**: row `franchise_id` NULL (gán hay xoá — chủ dự án quyết) rồi mới `required=True`.
- **Nợ cụm I**: `wj_ir_matrix.py` `expect()` sửa cho màn `no_store`/khối nhắc cố ý + cắt route `/portal/reports/orders`; kịch bản ghi dữ liệu (#154, #155) chỉ đo ở DB copy.
- **Dashboard** workstream riêng (Step 2b/3, `docs/dashboard-migration-plan.md`) · **Bù hàng K** (b)(d) · legacy desktop `pc_source_ui_v1_4`.
- Lịch sử đầy đủ mọi State + pending cũ (C1–C10, D, merge Thái, E, F, G, J): `docs/archive/compact-summary-history.md`.

⚠️ **DB local chính `wujia_tea_19` vẫn ở `wujia_sale 19.0.4.1.0`** — pre-migrate S52 chưa từng chạy trên local (UAT đã chạy), nên `-u` module nào kéo theo `wujia_portal_return` sẽ đỏ cho tới khi chạy `-u wujia_sale` trên local.

⚠️ **UAT có cài `website_sale` + 5 module `website_sale_*`** (không module custom nào depend — cài tay). Đây là nguồn của WJ-PROD-001. **Rule: field custom PHẢI có tiền tố `wujia_`** (L10).

**Phase 2 (future):** account.move Công nợ (CT-014) / Employee Mgmt / Payment History / Training Reports / User Invitations.

**Non-negotiable rules (mọi session):**
- ⚠️ **ĐỌC SOURCE TRƯỚC KHI SỬA — KHÔNG ĐOÁN model/field/method.** `grep -rn "_name = '" $(python3 scripts/wj_paths.py --where <mod>)/models/`. `wujia.franchise.management` (NOT `res.franchise`) — tên thực → §11 đầy đủ. Helper portal → §11.
- ⚠️ **REGRESSION CHECK trước khi sửa CSS/token/template**: `git grep -n "<selector|token>" -- base portal` xem blast radius (token global `--wujia-*` ảnh hưởng MỌI page); sau ship smoke 3-5 page khác.
- CSS bắt buộc `var(--wujia-*)` + class share `_components.css`. Không hex cứng.
- Demo data KHÔNG vào manifest XML → `scripts/seed_*.py` local-only.
- Odoo 19 view: không `attrs=`, không `decoration-secondary`, `_sql_constraints`→`models.Constraint`, search group `name="group_by"`, bỏ `expand="0"`.
- Commit English Conventional Commits, KHÔNG `--no-verify`. Comment GỌN (1 dòng đủ ý).
- Field rename: pre-migrate trước `-u`. i18n: code English, BA dịch `vi_VN.po`.
- ⚠️ **Field custom PHẢI tiền tố `wujia_`** (S52/L10) — trùng tên field core (`description_ecommerce` của `website_sale`…) làm đổi kiểu cột ở DB có cài app đó, local không cài thì không bao giờ lộ. Datetime portal: dùng `fmt_local_dt`/`wj_dt` (§11), KHÔNG `.strftime()` thẳng.

→ Chi tiết: `wujia-tea-doc.tex` §1.4.

---

## §6 wujia-deploy

**UAT = `https://dev.wujiatea.com.vn`** (máy 115.74.247.189, aaPanel; khảo sát chỉ đọc 12/10). Source `/www/wwwroot/dev.wujiatea.com.vn` nhánh `deploy/staging` · systemd `odoo-dev` (user `www`, cổng 8019/8020, nginx đứng trước) · config `config/odoo.conf` (ngoài git) · DB `wujia_tea_19`. Cùng máy còn `odoo-uat` (`wujia_mn`, cổng 8029, repo khác, thư mục `odoo_modules`) và `odoo-huipeng` (`huipeng_db`, cổng 8059, repo `huifeng.erp.staging`, clone bố cục cũ) — ba tiến trình riêng, restart `odoo-dev` không đụng hai cái kia.

**Deploy máy UAT (đo 12/10).** Merge vào `deploy/staging` **không tự deploy** (aaPanel *Automatic deployment: Off*, webhook của site chưa từng được gọi). Deploy = aaPanel → Website → `dev.wujiatea.com.vn` → Conf → Git Manager → *Deploy latest* (có hỏi một phép tính). Panel checkout nhánh rồi pull ⇒ hook `post-merge` gọi `deploy.sh --no-pull`. ⚠️ Ở đường này `OLD_HEAD = NEW_HEAD` và commit đầu là merge commit ⇒ `deploy.sh` **không dò ra module nào, chỉ restart, không `-u`**. PR có đổi view/data/security/migration thì phải `-u` tay. ADR-028 đã áp: `addons_path` trong `config/odoo.conf` = 17 folder của bố cục mới + 3 mục cũ ở cuối (`themes/oca_queue`, `custom`, `/www/wwwroot/wujia-uat.tipscode.io/odoo_modules`); `deploy.sh` dòng 222 = `CHANGED_MODULES=$("$PYTHON_BIN" scripts/wj_paths.py --changed-modules "$OLD_HEAD" "$NEW_HEAD")`; bản gốc hai file: đuôi `.bak-adr028`. Nợ: `custom/` và `themes/oca_queue` trên máy chủ chỉ còn vỏ `__pycache__` (xoá được, rồi bỏ hai mục đó khỏi `addons_path`); `latest_version` trong DB của `wujia_portal_layout`/`wujia_portal_base` còn `.0` (PR #7 chỉ đổi Python + `.po`, không cần `-u`).

**Sửa ở đâu (ADR-028, chốt 12/10).**

| Muốn | Sửa / chạy ở đâu |
|---|---|
| Thêm hoặc đổi **thư mục** module | `scripts/wj_paths.py` → `ADDON_DIRS` (nguồn duy nhất), rồi sinh lại `addons_path` ở mọi máy |
| Module mới đặt thư mục nào | `README.md` §Module mới đặt ở đâu · kiểm `python3 scripts/qa/check_layers.py` (luật R8) |
| Tìm một module | `python3 scripts/wj_paths.py --where <module>` · cả cây: `--list` |
| `addons_path` máy local | `config/odoo.conf` (gitignore) ← `python3 scripts/wj_paths.py --addons-path` · mẫu: `config/odoo.conf.example` |
| `addons_path` máy UAT | `/www/wwwroot/dev.wujiatea.com.vn/config/odoo.conf` (ngoài git) — sửa qua aaPanel → Files, rồi restart `odoo-dev` |
| Cách deploy dò module cần `-u` | `/www/wwwroot/dev.wujiatea.com.vn/deploy.sh` dòng 222 (ngoài git) → gọi `scripts/wj_paths.py --changed-modules` |
| Git hook gọi deploy | `/www/server/git_hooks/dev.wujiatea.com.vn/post-merge` + `post-checkout` |
| Bấm deploy | aaPanel → Website → `dev.wujiatea.com.vn` → Conf → Git Manager → *Deploy latest* |
| Đọc log máy UAT | `/www/wwwroot/dev.wujiatea.com.vn/logs/<năm>/<tháng>/<năm-tháng-ngày>.log`, giờ **UTC** (`logs/odoo.log` chỉ còn dòng chuyển hướng) |
| Lùi cấu hình máy UAT về trước ADR-028 | `config/odoo.conf.bak-adr028` + `deploy.sh.bak-adr028` (nằm cạnh file gốc) |
| Test cần đọc file của module khác | `base/wujia_portal_layout/tests/src_paths.py` (`src`, `src_modules`, `src_walk`, `src_rel`) |
| Phân trang / giới hạn tần suất của portal | `base/wujia_portal_layout/controllers/utils.py` (`portal_base` chỉ import lại tên) |
| Lệnh `/wujia-*` | `~/wujia-devkit/commands/*.md` (`~/.claude/commands/` là symlink tới đó) |
| Lý do + bảng 81 module → thư mục | `docs/chapters/82-adr028-source-layout.tex` |

- CSS change → bump `?v=NNNN` (§9 gotcha #1).
- **Module mới không tự cài**: restart chỉ load module đã cài + upgrade module bump version; module hoàn toàn mới phải `-i` một lần.
- **Sau deploy**: kiểm version qua XML-RPC chỉ-đọc (repo manifest = `ir.module.module.latest_version`, 0 lệch) **trước** khi đo/ghi sheet.
- **[14/10, chủ dự án chốt] Merge vào `deploy/staging` = deploy ⇒ test browser luôn**: merge xong chờ job "Triển khai Staging" đạt, kiểm version, rồi đo bằng trình duyệt trên UAT (Playwright, chỉ đọc) ngay trong phiên — không dừng ở "đã merge".
- **[14/10] Job CI gọi webhook deploy.** Commit `f878ed65` (13/10) sửa `.github/workflows/deploy.yml`: kiểm cú pháp Python/XML/manifest ở mọi PR, và khi push `deploy/staging` thì gọi webhook aaPanel của site rồi chờ `/web/login` trả 200. **Đã xác nhận 14/10 (K0, run `38509363758`)**: merge PR #10 xong ~1 phút thì 9/9 module đụng tới đã ở version mới mà không bấm *Deploy latest* ⇒ đường webhook **có `-u`**. Vẫn kiểm version qua XML-RPC sau mỗi merge trước khi đo/ghi sheet; câu "merge không tự deploy" trong `/wujia-start` đã cũ. URL webhook kèm khoá truy cập đang viết thẳng trong file workflow ⇒ nên chuyển sang secret của repo và đổi khoá (việc của anh Thái).
- **[14/10] Bố cục core (anh Thái quyết).** Hiện tại: `/www/wwwroot/dev.wujiatea.com.vn` = gốc repo, `odoo19/` nằm trong (gitignore). Nếu đổi sang folder cha (`<domain>/Odoo19C` + `<domain>/WujiaTea`): repo và lịch sử git không đổi, `wj_paths.py` tự dò `../Odoo19C`; phải trỏ lại Git Manager + webhook của site, hai git hook, `deploy.sh`, unit systemd `odoo-dev`, `addons_path`, đường log. Core nằm trong working tree thì `git clean -fdx` xoá mất nó.
- **Không chạy hai tiến trình `-u` cùng lúc** — khoá DB, nâng cấp dừng giữa chừng mà không báo lỗi (sự cố 09/10: 16 module cụm I kẹt bản cũ).

---

## §7 wujia-start-instruction

- v19 active `/home/huyban/odoo-dev/WujiaTea`; v14 ref → §1.
- **BA spec = Google Sheet** `1HRiRLAZ9FlErRTLvwMaGhsOlYNPJHdf5AEMPvdLkQNE` (owner `huyhunggnguyen@gmail.com`, anyone-view, BA edit trực tiếp). Đọc tab qua CSV public: `curl -sL "https://docs.google.com/spreadsheets/d/1HRiRLAZ9FlErRTLvwMaGhsOlYNPJHdf5AEMPvdLkQNE/gviz/tq?tqx=out:csv&gid=<gid>"`.
- **Tab + gid:** `Tasks` (by name) · `MILESTONE` `1864615110` · `FEATURE CHECKLIST` `729461563` · `1.Model/Field` `2041118658` · `2.FE-Portal` `1002946158` · `3.Controller` `643561224` · `4.BE-Workflow` `1703696097` · **`5.Issue List`** `335593633` · `WORK LOG` `1388773997`. (Lấy gid: `curl .../htmlview | grep gid`.)
- Issue List: BA cập nhật mỗi ngày (đánh số hiện hành UI-01…06 = GLOBAL SHELL, khác `WJ_PageHeader` Sprint 9). Trạng thái → §5 + §12.
- ⚠️ **ƯU TIÊN SỐ 1 MỌI PHIÊN — `Tasks!STT1` "Fix lỗi issue list"** (task thường trực, trỏ tab `5. Issue List`). Đầu mỗi session PHẢI chạy `cd scripts/ba_spec && python3 issue_queue.py --dev`; có issue `Ready for Dev`/`Retest Failed` thì đề xuất làm trước mọi task khác. **Reconcile code↔sheet trước khi nhận** (`git log --all -S"<ID>"`) — issue có thể đã fix mà sheet chưa sync. **Không làm hết một lượt**: bám bảng batch §13, mỗi session một batch. Xong 1 issue phải đối chiếu acceptance BA ≥90% (§13) rồi mới ghi ledger.
- **Controller task (S32+):** BA gửi spec qua chat GPT share → `scripts/ba_spec/fetch_ba_chat.py <url>` + `read_xlsm.py <sheet> <kw>`, đối chiếu source model THẬT (BA hay đặt tên lý tưởng hoá ≠ thật), hỏi ở fork. Toolchain gitignored, KHÔNG lên server (`scripts/ba_spec/README.md`).
- **QA/Task workflow (2026-07-21):** xem §12.
- Sprint log `wujia-tea-doc.pdf` (compile `chapters/*.tex` qua `scripts/build-doc.sh`).
- **UI-only** (button chưa cần wire, miễn layout đúng BA). **Perf-first 1500 user** (ormcache, store+index, cron). **Ask-don't-assume + Read-before-write.**
- 🔴 **KHÔNG đụng hai module Khảo sát của anh Thái** (`wujia_portal_inspection`, `wujia_franchise_inspection`, merge từ nhánh `thai` 19/08) — lối code khác hẳn portal (Bootstrap thô, inline style, `sudo()` ở đường ghi). Mọi cụm UI/refactor **bỏ qua**, ghi `defer` kèm lý do vào bảng nghiệm thu thay vì sửa. Chỉ đụng khi chủ dự án nói rõ. (Quyết định 08/09/2026, lượt D5h; luật cũng đã ghi trong skill `wujia-start`.)
- End session: `/wujia-end-sprint` (test → doc → PDF → ledger/qa_sync → commit → push).

Slash: `/wujia-start` `/wujia-load-feature <letters>` `/wujia-save-insight` `/wujia-end-sprint` `/wujia-dashboard`.

---

## §8 wujia-session-template

```
Session này em làm <1 câu>.
1. Ref: v14 <path>, BA <Sheet!Section>, chapter <XX>.
2. Task A/B: <mô tả>.  3. Out-of-scope: <không làm>.
Discovery → plan → user approve → code → upgrade RC=0 → screenshot → commit.
Perf: <lưu ý query 1500 user>.  Xong: /wujia-end-sprint.
```

---

## §9 wujia-sprint9-history + gotchas

**Sprint 9 (24 sub-sprint UI-01..18 + empty state + cleanup)** = DONE 2026-06-04, chi tiết → `chapters/18-*.tex`. Issue table + file-touched table đã gỡ khỏi summary (giữ trong chapter 18 + git).

**Gotchas còn tái dùng (đọc kỹ trước khi sửa UI/UoM):**
1. **Cache 7 ngày** — Odoo static `Cache-Control: max-age=604800`. CSS change PHẢI bump `?v=NNNN` trong `assets.xml` (chỉ file load qua manual `<link>`; `web.assets_frontend` auto-bundle không cần). Bump cao hơn lần user thấy cuối.
2. **CSS/màu = FILE TRÊN ĐĨA, KHÔNG ở DB.** "local khác server" về CSS = CACHE (browser / `?v=` chưa `-u` / proxy), KHÔNG bao giờ là data → **đừng drop/copy DB để sửa CSS**. Debug: `curl .../file.css` + view-source `?v=` + check proxy.
3. **Global heading `!important` đè class** (`h1,.wujia-h1{...!important}`) ép mọi `<h1>/<h2>` bare → 32/24px, đè cả class đơn. Fix: scope 2 lớp `.wujia-mpage .wujia-mxxx-h1` **+ `!important`**. Server không `--dev` → sửa CSS xong phải `-u`/`--dev=all` regen bundle.
4. **Vuexy navbar `.badge` cascade** — cùng specificity base `.badge` → env flaky (local đỏ, server tím). Fix: scope `.header-navbar … .wujia-header-badge` + `!important` bg+color, digit `inline-flex` center.
5. **Odoo 19 UoM (Sprint K)** — `uom.uom` bỏ `category_id` → cây `relative_uom_id`. `_compute_quantity(...,'UP')` không kiểm nhóm → kết quả vô nghĩa nếu khác nhóm; kiểm nhóm = so gốc cây. Chiều ngược dùng `'DOWN'` (tránh double-UP). `sale.order.line` ĐVT = `product_uom_id`; `stock.move` đã giao = `move.quantity`; backorder tạo trong `_action_done`.
6. **BA hex typo** lệch ≤4 ký tự (`#28A9DF` vs `#22A9DE`) → coi typo, dùng token; lệch nhiều → hỏi.

---

## §10 wujia-lessons (12 lesson cốt lõi)

Postmortem chi tiết → `chapters/18-*.tex`.
- **L1 — Extract full images từ xlsm + MAP image→cell** qua openpyxl `img.anchor._from.row/col` (KHÔNG cherry-pick theo số file). Annotation BA: khoanh đỏ=target / gạch chéo=xóa / gạch chân=highlight.
- **L2 — Check v14 trước khi build mới**: `grep -rln <kw> /home/huyban/odoo-dev/wujia_tea_odoo14/modules/`. Có → adapt; không → ghi rõ "v14 KHÔNG có X" + build từ đầu.
- **L3 — Visual design hỏi explicit 4 câu** trước khi code: bg color? text color? layout (inline/stacked)? icon (feather name)? KHÔNG assume hex từ ảnh.
- **L4 (S39) — Dựng Figma xong PHẢI đo computed-style, đừng nhìn ảnh.** Shell Vuexy có 4 rule **tag-level + `!important`** thắng mọi class: `_components.css` `h1/h2 {font-size !important}` · `style.css` `table th {font-size:16px !important}` · `dashboard.css` `select {width:100%;padding:5px !important}` · `bootstrap-extended` `label {padding-left:.2rem}`. Cách phát hiện: Playwright duyệt `document.styleSheets`, `el.matches(rule.selectorText)`, in ra mọi declaration + cờ `!important`. Trung hoà trong **scope component**, KHÔNG sửa 4 file shared (blast radius = toàn portal). Đồng cấp specificity thì **thứ tự source quyết định** — modifier `--sm` phải đặt sau base, và `.x .y` (0,2,0) sẽ đè `.z` (0,1,0) dù `.z` mang ý nghĩa cụ thể hơn.
- **L5 (S41) — Schema change trên bảng ĐANG có dữ liệu, 3 bẫy.** (1) `unique(a,b,c)` **không chặn gì** ở nhánh `c IS NULL` (Postgres coi mọi NULL khác nhau) → thêm `models.UniqueIndex('(a,b) WHERE c IS NULL')`. (2) Field mới có `default` + `unique` = Odoo backfill cùng một giá trị rồi constraint vỡ → bỏ default, để pre-migrate lấp giá trị phân biệt TRƯỚC khi ORM tạo constraint. (3) Rename field Python nhưng **giữ key JSON** trả client ⇒ 0 dòng JS phải sửa.
- **L7 (S43) — Harness đo Figma: chân lý là NODE JSON, không phải kỳ vọng mình gõ ra; harness sai thì sửa harness.** 2/7 phát hiện là báo động giả (nút back 40 vs 42 = `border-box`; gap 8 vs 12 = header kết ở y=202). Chỗ Figma **cố ý** lệch thì khai báo miễn trừ cho đúng element, đừng nới ngưỡng cả trang; chỗ Figma tự mâu thuẫn thì giữ nguyên + ghi lý do. 5 lỗi số đo thật đều do **shell tag-level đè** (`body{letter-spacing}`, `line-height:1.8`, `form{margin-bottom}`) → trung hoà trong scope component. Sửa CSS không thấy đổi ⇒ **nghi cache `ir.attachment` của bundle trước khi nghi selector**. Và **tiêu đề rỗng trong spec BA là một câu trả lời** ('chưa quyết') → dựng UI-only + chừa MỘT seam đổi nguồn.
- **L6 (S42) — Muốn "chọn theo tiêu chí" mà không phá tầng phân quyền: tiêu chí là CÁCH CHỌN, M2M là KẾT QUẢ.** Lưu domain-string rồi eval lúc đọc thì `ir.rule` (vốn là domain ORM) không diễn đạt nổi "thông báo có domain khớp cửa hàng tôi" → phải lọc Python, mất index, chết ở 1500 user; và chạy lại tiêu chí trên dữ liệu đã đổi cho kết quả khác lúc gửi. Giải: `target_mode` all/filter/manual, tiêu chí resolve **1 lần tại `action_publish`** rồi `Command.set` vào M2M sẵn có → portal/ir.rule/controller/index **không đụng dòng nào**, có snapshot để audit. Đánh đổi phải hỏi chủ dự án và ghi vào spec: cửa hàng mở sau ngày gửi KHÔNG nhận thông báo cũ (có nút *Cập nhật danh sách nhận* khi cần). Kèm bài học giao tiếp: user nói **"khó hiểu quá"** = lỗi ở người giải thích — bỏ tên field/thuật ngữ, kể bằng thao tác thật ("chọn Miền Bắc → Xem thử → 137 cửa hàng → Gửi") và gom về **một** câu hỏi nghiệp vụ.
- **L8 (S44) — Dịch nhãn hàng loạt: 5 bẫy, cái nào cũng PASS im lặng.** (1) Một từ Việt = hai từ Anh: nút = **động từ**, state/filter = **tính từ** (`Reject`/`Rejected`); `.po` không cấm 2 msgid → 1 msgstr nên chiều `vi_VN` giữ nguyên. (2) Template portal không chứa chữ Anh vẫn rò tiếng Anh — chỗ hở là `_fields[].selection` đọc từ model ⇒ **pin hằng nhãn VN trong controller portal**. (3) ⚠️ Odoo **tự merge `<module>.pot`** khi nạp `.po` ⇒ `.pot` cũ làm msgid mới thành obsolete, DB không đổi mà không lỗi không warning — **sinh `.po` phải sinh `.pot` cùng lúc**. (4) Lọc chuỗi Việt theo DẤU bỏ sót tiếng Việt không dấu ('Ca thi', 'Xe'). (5) Assert bằng `in` là assert rỗng khi chuỗi này là con chuỗi kia. Kèm: overlay che trang làm mọi assert pass rỗng; `pkill -f 'odoo[-]bin'` gộp chung dòng với lệnh chạy server thì **shell tự giết chính nó** (exit 144).

- **L9 (S50) — Đọc mockup BA dạng SVG + dựng empty-state chung: 6 bẫy.** (1) **Đính kèm của BA nằm ở HYPERLINK của ô**, `export?format=csv` mất hyperlink ⇒ tải `xlsx` rồi openpyxl đọc `cell.hyperlink.target`. (2) SVG Figma là **outline path, không có `<text>`** ⇒ nhúng inline vào HTML rồi Playwright `getBBox()`, tự parse path cho bbox sai hoàn toàn. (3) **Comment XML không được chứa `--`** (dán tên class modifier vào comment làm hỏng file). (4) Icon trong flexbox phải pin `flex: 0 0 <size>`, chỉ có `width` sẽ bị bóp. (5) Harness sai thì sửa harness (nhãn bị `text-transform:uppercase` nên so chuỗi trượt). (6) 'Rỗng' của Home không rỗng theo cửa hàng — Thông báo + Kiến thức là nguồn toàn hệ thống. Kèm: `\text{}` thiếu trong preamble và `language=CSS` không tồn tại làm `build-doc.sh` **RC=0 nhưng PDF cụt giữa chương** ⇒ phải grep `^! ` trong `.log` + `pdftotext` kiểm.

- **L10 (S52) — Trùng tên field với core là bom hẹn giờ chỉ nổ ở server.** (1) **Field custom PHẢI có tiền tố `wujia_`** — `description_ecommerce` trùng field Html của `website_sale` ⇒ DB nào cài app đó thì cột thành **jsonb** trong khi ORM ghi varchar; local không cài nên **không bao giờ lộ** ('local chạy ngon' không chứng minh gì về UAT). (2) **Đọc kiểu cột của server không cần quyền SQL**: `search([('field','=','__probe__')])` qua XML-RPC, cột jsonb trả `InvalidTextRepresentation`. (3) Không tái hiện được NGUYÊN NHÂN thì nói thẳng — tái hiện TRIỆU CHỨNG là đủ để chứng minh fix. (4) Migration đổi tên phải **phân nhánh theo `information_schema.columns`** và test cả hai nhánh, kiểm dữ liệu còn nguyên chứ không chỉ RC=0.
- **L11 (S54) — 3 bẫy "đúng cú pháp nhưng chết im lặng" ở tầng portal.** (1) **KHÔNG dùng `&&`/`<`/`>` trong `<script>` inline của QWeb**: lxml serialize template ra HTML thành thực thể (`&amp;&amp;`), mà HTML5 **không giải mã thực thể bên trong `<script>`** ⇒ **cả khối JS chết, không log, không đỏ build** — `//<![CDATA[` KHÔNG cứu được (serializer gỡ marker). Viết `if` lồng hoặc đưa hẳn ra `static/src/js/`. Quét bằng script tìm thực thể *nằm trong* `<script>`, đừng grep `&amp;` trần (trong **thuộc tính** thì `&amp;` là đúng). (2) **Validate redirect phải nghĩ tới bước chuẩn hoá của trình duyệt**: kiểm tiền tố `/portal/` là chưa đủ — `?return_url=/portal/../web` qua được rồi bị normalize thành `/web`; cấm segment `..` **trước** khi xét tiền tố. (3) **Blast radius lớn thì tìm seam, đừng sửa N chỗ**: `ph_variant='back'` gọi ở 31 chỗ/14 file ⇒ 1 helper trên `ir.http` gọi từ `t-att-href` cho toàn bộ hưởng hành vi mới, 0 dòng controller, 0 chỗ để quên. (4) **A11y: đo để chứng minh, đừng code mò** — 2 variant ẩn bằng `d-none` vốn đã ngoài accessibility tree, đếm ra 1 link rồi mới kết luận, không thêm `aria-hidden` thừa.

- **L12 (C1) — Chuyển field thường thành stored compute KHÔNG tự sửa dữ liệu cũ.** Đo thật sau `-u`: bản ghi cũ y nguyên (9 SO trống vẫn trống, bản ghi lệch vẫn lệch) — Odoo chỉ mark-to-compute cho field MỚI. Muốn sửa dữ liệu cũ phải viết post-migrate, và nên **chỉ điền bản ghi TRỐNG**, đừng ghi đè giá trị người dùng đã chọn. Kèm: chặn nghiệp vụ nên đặt ở **method hành động** (`action_confirm`/`button_validate`/`action_post`) chứ không `@api.constrains` — constrains khoá luôn chứng từ cũ đã xác nhận, chỉ sửa ghi chú cũng bị chặn. Và harness Playwright: dropdown Many2one hiện **danh sách mặc định trước khi lọc xong** ⇒ click `li:first-child` bắt nhầm bản ghi; Odoo 19 **tự lưu bản nháp khi rời form** ⇒ mở form 'chỉ để xem' trên UAT vẫn đẻ bản ghi, phải kiểm và dọn.

- **L13 (C3) — Thêm một `<div>` slot là đủ để giết `gap` của cả trang.** `wj_ajax_list` (S49) bọc vùng lọc-không-reload bằng `<div id=...>` thường; `.wj-debt` là flex column `gap:12` nên gap chỉ áp cho **con trực tiếp** ⇒ mọi section bên trong slot dính 0px (WJ-DEBT-009, BA đo đúng). Sửa ở **wrapper** (cho slot cùng `display:flex` + gap), đừng vá `margin` từng khối. Kèm: (1) trước khi tin "trang X vỡ ở 500px", **đo lại** — sidebar Vuexy vốn off-canvas ở mọi bề rộng mobile, cái sai thật là trang pay dựng markup mobile ở MỌI bề rộng vì thiếu `d-lg-none`; (2) `bank` rỗng thì trả **cờ `configured`**, đừng để template đoán bằng chuỗi rỗng — và đừng nhét câu thông báo vào field dữ liệu (`name`), UI là việc của template; (3) harness Playwright login được cả khi form login bị `d-none`: `POST /web/session/authenticate` rồi gắn cookie `session_id` vào context.

- **L15 (merge `thai`) — Nhận code của dev khác: 4 lớp lỗi chỉ lộ khi CHẠY, không lộ khi đọc diff.** (1) **`group_id` để TRỐNG trong `ir.model.access.csv` = áp cho MỌI user**, không phải "chưa gán ai" — kèm `1,1,1,1` là mở cửa write/unlink cho 1500 portal user; đọc diff chỉ thấy "gọn hơn 6 dòng". (2) **`init()` KHÔNG phải chỗ seed dữ liệu** (chạy giữa lúc Odoo dựng bảng theo thứ tự từng model ⇒ `create()` sang model khác = `UndefinedTable`), **nhưng `<odoo noupdate="1">` cũng sai** vì chỉ chạy lần cài đầu ⇒ DB đã cài sẵn (UAT) thì `-u` không seed, tính năng lên server với 0 dữ liệu cấu hình. Đúng = data XML **không** `noupdate` + hàm seed idempotent. ⚠️ Phải đo trên DB **đã cài sẵn module**; `-i` trên DB trắng thì cả hai cách đều xanh. (3) **Fail-open đọc rất giống fail-safe**: `if ids and x not in ids` — `ids` rỗng thì `and` ngắt mạch **bỏ qua kiểm tra**, mà rỗng chính là ca nguy hiểm nhất (user không thuộc cửa hàng nào). Viết `x not in (ids or ())`. Cùng họ: `try: import ... except ImportError: return []` biến lỗi import thành **tắt im lặng phân quyền**. (4) **Chỉ đổi `_order` khi model không dùng chung** — `_order` đổi thứ tự ở MỌI màn; muốn sắp riêng thì `default_order` trên view. Kèm 2 bài học vận hành: đường dẫn máy cá nhân lọt vào `scripts/*.sh` dùng chung (+ `chmod` 755→644) ⇒ tách config khỏi script; handler log tự chế **gỡ hẳn** handler theo `logfile` ⇒ file trong `odoo.conf` rỗng, người debug tưởng server chết — chuyển hướng log phải để lại một dòng chỉ đường. Và về i18n: **glossary đánh khoá tiếng Việt + msgid tiếng Anh (sau S44) = trượt sạch** ⇒ bắc cầu qua chính `vi_VN.po`; sinh `.po` bằng regex tự chế thì cắt chuỗi tại `\"` và chèn xuống dòng thật vào giữa chuỗi — **dùng `babel.messages.pofile`**, và luôn `msgfmt -c` trước khi nạp DB.
- **L14 (C6) — CSS: thắng bằng specificity, và đừng tin cascade của local.** (1) `web.assets_frontend` nạp **SAU** mọi `<link>` custom ⇒ hoà specificity là Odoo thắng; muốn đè `a:hover{text-decoration:underline}` (0,1,1) thì rule phải ≥(0,2,1), muốn đè descendant rule Vuexy `.list-group .list-group-item-action:focus{outline:0}` (0,3,0) phải bám **cùng tổ tiên** hoặc leo `:not()` — **đo `c6_why.py` rồi mới leo**, đừng rải `!important`. (2) Blast radius toàn portal thì **một layer nạp cuối** rẻ hơn vá N chỗ, và revert được bằng 1 file. (3) **L10 lặp lại**: DB local KHÔNG có `website_sale` nên **không tái hiện được** lỗi underline của UAT — bằng chứng phải lấy bằng `page.add_style_tag` nhúng CSS vào **chính UAT**; nhúng thì phải nhúng **cả `_variables.css`**, thiếu token thì `outline: var(--…)` invalid và **xoá luôn ring đang có** (tưởng fix hoá ra tệ hơn). Nhúng lặp file token cũng tự đẻ lệch chiều cao ⇒ phải có **run đối chứng chỉ nhúng token** mới biết lệch đó không phải do mình. (4) Ép trạng thái bằng CDP `CSS.forcePseudoState` chứ đừng `page.hover()` (overlay/actionability chặn), nhưng **trạng thái ép rò sang node kế** ⇒ sau mỗi element phải reset **rồi đọc lại và so** với default, lệch thì báo `leak`. (5) Chốt cuối cùng phải là **đi Tab thật**, không chỉ ép pseudo-class.

- **L16 (S57) — i18n Odoo 19: ba bẫy, cả ba PASS im lặng.** Dịch màn onboarding sang tiếng Việt mất 3 lượt mới ăn, mỗi lượt hỏng theo một kiểu **không lỗi, không cảnh báo, chỉ là nhãn vẫn tiếng Anh**. (1) **Odoo ghép `.po` với `.pot` cùng thư mục lúc nạp** ⇒ chuỗi có trong `.po` mà **thiếu trong `.pot`** bị **bỏ qua im lặng**; sinh `.po` phải sinh `.pot` cùng lúc — **tái phát của L8(3)** từ S44, cùng gốc, khác triệu chứng. (2) **Dạng tham chiếu menu đã đổi**: `#: menu:<mod>.<xmlid>` **không còn hợp lệ**, phải là `#: model:ir.ui.menu,name:<mod>.<xmlid>`; hai dạng cùng tồn tại trong `wujia_franchise/i18n/vi_VN.po` và chỉ dạng sau ăn. (3) **Chuỗi trong code cần CHÚ THÍCH ĐÁNH DẤU, không phải chỉ cần tham chiếu**: thiếu dòng `#. odoo-python` thì `#: code:addons/...` là vô nghĩa ⇒ tiêu đề hộp thoại và **mọi** `UserError` vẫn tiếng Anh (`7568711` vá 27 entry). ⇒ **Không được coi "RC=0, cài sạch" là bằng chứng đã dịch xong** — cách duy nhất là mở đúng màn ở đúng ngôn ngữ mà nhìn, hoặc đọc chỉ-đọc từng nhãn qua XML-RPC với `context={'lang':'vi_VN'}`; và **chuỗi dựng từ Python phải đo riêng** (gọi method trả action rồi đọc `name`), vì nhãn trường/menu tiếng Việt hết mà chuỗi code vẫn Anh là ca có thật. Kèm: bản dịch sửa tay trên giao diện nằm **trong database** — dựng lại DB là mất sạch, phải đưa vào `i18n/*.po` trong mã nguồn.
- **L17 (D4g/D4h) — Trước khi nói "đã lên main/UAT": `git fetch` + đo phiên bản module trên máy chủ, đừng tin git local.** Máy Linux code D4e1/e2/f 2 ngày trên nhánh mà chưa fetch; máy Mac đã merge D4d + vá deploy vào `main` ⇒ chủ dự án deploy "D4f" mà UAT chỉ có D4d — lộ ra **chỉ vì** XML-RPC `ir.module.module` + md5 CSS. Gỡ bằng `merge` (không rebase nhánh đã push), quy ước **lấy số lớn hơn rồi bump patch +1 cho mọi module đụng**. Kèm hai bẫy nhỏ: (1) module **uninstalled** trên DB dev thì kiểm kê tĩnh sai cả hai chiều — đếm nhầm lớp không tồn tại và **bỏ sót dáng khai bằng `style=""`** tại call site; phải cài lên copy rồi đếm token lúc chạy. (2) Harness bọc `exec` đổi `ns["X"]` **không** đổi được tham số mặc định đã bind lúc `def` — truyền tường minh.

---

## §11 wujia-shared-utils-cheatsheet

**CSS class chung** (`_components.css`): `.wujia-btn[-primary/-secondary]` (h42/h38) · `.wujia-badge[-success/warning/danger/info/muted]` · `.wujia-empty-state` · `.wujia-two-pane` · `.wujia-kpi-card[+ -icon-*/-separator]` · `.wujia-content-card[-header/-body/-row/-table/-empty]` · `.wujia-container/-grid-responsive/-stack-mobile`. Canonical: `wj-filter-chip[--soft/--wrap/--clear]` · `wj-count-meta[--bold/--primary]` · `wj-empty-state[--card/--compact/--rich]` · `wj_page_header` (title/back/create) · `wj-pc-*` (PC components).

**Token** (`_variables.css`): `--wujia-primary #28A9DF` (BA CẤM #22A9DE) · `--wujia-bg-page #F3F6F8` · `--wujia-text-primary #111827` · `--wujia-text-secondary #374151` · `--wujia-text-subtitle #6B7280` · `--wujia-border #E5E7EB` · danger `#EF4444` · success `#16A34A` · `--wujia-text-muted #8A939E` · `--wujia-card-radius 16px` · `--wujia-btn-height 42px`. Font Inter self-host (weight 700).

**Datetime portal (BẮT BUỘC dùng, đừng `.strftime()` thẳng):** `portal_tz()` / `to_local_dt(dt, tz)` / `local_day_range_utc(d1, d2, tz)` / **`fmt_local_dt(dt, fmt, tz=None)`** (S52) ở `wujia_portal_base/controllers/utils.py`. Template lấy qua key qcontext **`wj_dt`** — controller nào render datetime phải tự inject `'wj_dt': fmt_local_dt`. Odoo lưu naive UTC ⇒ in thẳng = lệch −7h (WJ-NOTI-001, WJ-PH-002).

**Python helper (portal):** `get_active_franchise_id()` / `get_active_franchise_ids_filter()` ở `wujia_portal_base/controllers/portal.py` (KHÔNG `utils.py`) · `wujia.franchise.member.find_active_membership(user_id, franchise_id)` → membership record (hay `False` nếu không có); để lấy role dùng `.role` trên record trả về · `res.config.settings._is_within_order_window(area_id)` (dùng qua `self.env['res.config.settings']._is_within_order_window(area_id=...)`) · `rate_limit` + `attach_files_to_record` ở `controllers/utils.py`.

**Pager + rate limit:** `build_pager` / `page_numbers` / `rate_limit` nằm ở khung `wujia_portal_layout/controllers/utils.py` (ADR-028); `wujia_portal_base/controllers/utils.py` import lại nên controller cứ import từ `portal_base` như cũ. `parse_page_size` vẫn ở `portal_base`.

**Test đọc file module khác:** `from odoo.addons.wujia_portal_layout.tests.src_paths import src, src_modules, src_walk, src_rel` (hoặc qua `wujia_portal_base.tests.css_probe`). KHÔNG ghép đường dẫn từ thư mục cha của module — module nằm ở nhiều folder.

**Model names thực:** `wujia.franchise.management` / `.member` / `wujia.order.window` / `wujia.notification` / `wujia.notification.type` / `wujia.notification.read` / `wujia.knowledge.article` / `wujia.support.ticket` / `wujia.info.update.request` / `wujia.compensation.allocation` / `wujia.exam.*` / `wujia.portal.cart[.line]` / `res.area` / `res.ward`.

---

## §12 wujia-qa-uat-nightly

**QA Operating Standard** = `docs/01_NGO_GIA_QA_OPERATING_STANDARD.md`. Luồng: `New → Ready for Dev → Dev In Progress → Ready for Retest → BA Retesting → Done`. **Dev KHÔNG tự đóng `Done`** — tối đa `Ready for Retest`. Fork/thiếu spec → `Need Clarification` (owner BA), KHÔNG đoán.

**UAT** `https://dev.wujiatea.com.vn/` (từ 12/10/2026; IP 115.74.247.189, DB `wujia_tea_19`, cùng máy có `wujia_mn` + `huipeng_db`; tài khoản `admin` / `Wujia@2026`, kiểm đăng nhập được 12/10; máy cũ `113.161.187.126:8019` đã ngừng dùng) — tự smoke-test được. aaPanel (quản lý máy chủ) + Metabase: `docs/CREDENTIALS.md`. Giới hạn: không tạo đơn/hoá đơn/email thật, không đổi quyền, không drop data. Server info: `docs/CREDENTIALS.md`.

**Sheet tabs BA log:** → §7 (Tasks + 5.Issue List gid=335593633). Chuẩn lên task cho AI = `docs/02_TASKS_INTAKE_SPEC_FOR_GPT.md` (đã gửi BA/GPT).

**Ghi ngược sheet (dev-only, `scripts/ba_spec/`, gitignored):** ĐỌC = CSV công khai (không auth). GHI = POST tới **Apps Script bridge** chạy as editor (Google chặn OAuth scope Sheets nên KHÔNG dùng gcloud/token). `sheet_io.py` đọc CSV + ghi qua `sheet_endpoint.json` (webapp_url+secret).
- Setup 1 lần: deploy `qa_nightly/WujiaSheetBridge.gs` (Extensions→Apps Script→Web app, execute as editor) → dán URL vào `sheet_endpoint.json`. Chi tiết `docs/03_OAUTH_SHEET_SETUP.md`.
- **Làm xong 1 issue** → thêm entry vào `docs/qa-issue-ledger.yaml` (chỉ khi code khớp expected HIỆN TẠI) → `cd scripts/ba_spec && python3 qa_sync.py --dry-run` (xem) → `--apply` (set `Ready for Retest` + Build/Deploy + FIX/IMPACT/RETEST/LIMIT + Odoo Fit + dòng `7. ISSUE HISTORY`). Idempotent; tự SKIP issue `Need BA Confirm=Yes`/`Need Clarification`.
- `task_sync.py --list` (task Ready-for-AI) / `--row N --status/--question/--result` (ghi O/P/Q/R).

**Nightly agent — INTERACTIVE trong tmux (default 2026-07-22).** Cron `0 22` → `cron-tmux-launch.sh` mở session `wujia-nightly` chạy `run-interactive.sh` (claude opus/xhigh/acceptEdits, seed `agent_prompt_interactive.md`). Trực: `tmux attach -t wujia-nightly`.

Phạm vi: Dev-actionable (`issue_queue.py --dev`) + review `Ready for Retest`; mỗi issue 1 branch, `-u` RC=0. Agent **hỏi trước push main** (1=push, 2=lặp); xong → ledger + `qa_sync --apply`.

Giới hạn: KHÔNG tự `Done` / force / no-verify / drop-DB. Fallback headless: `run.sh` (không còn cron default). Chi tiết phím tmux → `scripts/ba_spec/qa_nightly/USAGE.md`.

**Self-verify Issue List bằng headless Chromium (2026-07-23).** Env `odoo` có sẵn `playwright` + chromium → ĐO computed-style/bounding-box y như BA thay vì đoán/ghi LIMIT "không verify headless". Tool: `scripts/ba_spec/qa_visual_check.py` (login admin/UAT, `--url --w --h --measure "sel:prop" --inject "css"`). **Gotcha:** (1) portal có long-poll bus.bus → dùng `wait_until="load"` KHÔNG `networkidle`; (2) login submit bằng Enter (nút login trùng nút Search); (3) nếu inject `!important` ultra-spec mà computed KHÔNG đổi → element bị JS/plugin Vuexy điều khiển (sidebar `.main-menu` width, nút `.btn-primary.waves-effect`), CSS bất lực → defer, đừng cố. **Kinh nghiệm 07-23:** đa số "Retest Failed" của BA thực ra ĐÃ đúng trên server — BA test build cũ trước deploy; luôn đo lại server hiện tại trước khi kết luận.

**⚠️ Gotcha ghi sheet — filter ẩn Done làm LỆCH ROW (07-23, đã fix).** `sheet_io.read_values` cũ đọc bằng gviz/tq **tôn trọng filter** của BA (ẩn "Done") → trả THIẾU dòng → `find_row` đánh số theo view lọc, nhưng bridge Apps Script ghi theo **ROW TUYỆT ĐỐI** → ghi Done NHẦM sang dòng khác (đã từng hỏng UI-06/UI-PC-SHELL-001/UI-MOB-SHELL-002, khôi phục xong). ĐÃ SỬA: `read_values` cho tab có gid dùng `export?format=csv` (bỏ qua filter, row khớp tuyệt đối). Sau mọi lần ghi sheet PHẢI verify lại bằng `export?format=csv` (không dùng gviz để verify). Set Done: `scripts/ba_spec/qa_done.py` (override rule chỉ khi chủ dự án duyệt).

**🔴🔴 Gotcha row-offset TÁI PHÁT 04/09/2026 — đã ghi đè NHẦM một issue.** Bản vá 07-23 chỉ đúng khi caller gõ **đúng key trong `KNOWN_GID`**. `read_values("5. Issue List")` (tên THẬT của tab) không khớp key `"issue list"` ⇒ rơi xuống gviz ⇒ tôn trọng filter ẩn Done ⇒ `find_row` trả **dòng 10 của view** trong khi dòng tuyệt đối là **118** ⇒ bridge ghi đè `RESP-MOB-HOME-003` (đang Done). Đã khôi phục từ `qa-issue-ledger.yaml` + log nightly, và thêm alias `"5. issue list"` vào `KNOWN_GID`. **Quy tắc từ nay: sau MỌI lần ghi sheet phải verify bằng `export?format=csv` và đối chiếu cột ID của chính dòng vừa ghi** — không chỉ đọc lại giá trị (giá trị đúng vẫn có thể nằm sai dòng, đó chính là cách tôi suýt bỏ lọt).

**⚠️ Gotcha TÊN TAB — đừng lấy tên từ `export?format=xlsx` (07-31).** Excel cấm `/` trong tên sheet nên Google **sanitize khi export**: tab thật `1. Model/ Field` ra thành `1. Model Field`; gửi tên đó cho bridge → `Error: Không tìm thấy tab`. Cũng đừng dò bằng gviz `sheet=<name>` — sai tên nó **im lặng trả tab đầu tiên** (MILESTONE), tưởng đúng mà đọc nhầm sạch. Cách đúng: `sheet_io._post({'action':'ping','sheet':'1. Model'})` → bridge trả `sheet.getName()` là tên THẬT (`_resolve` có fallback substring nên gõ một phần là đủ). `KNOWN_GID` đã có cả 2 key (thật + alias xlsx). gid: Tasks `1936593712` · `1. Model/ Field` `2041118658` · `3. Controller` `643561224`.

**⚠️ Gotcha — `Ready for Dev` KHÔNG có nghĩa là chưa làm (08-10).** WJ-ORD-023 (FilterBar PC 1 hàng) đã fix commit `63dc4bc` ngày 08-04 nhưng sheet vẫn `Ready for Dev` tới 08-10 vì không ai chạy `qa_sync.py` sau khi code. Ngược lại BA cũng hay retest build cũ (§12 kinh nghiệm 07-23). ⇒ **Nhận issue nào cũng reconcile trước**: `git log --all -S"<ISSUE-ID>"` + `grep -rn "<ISSUE-ID>" custom/` + đo lại UAT hiện tại. Đã fix rồi thì chỉ ledger + `qa_sync.py`, KHÔNG code lại.

**Spec F ↔ source (Sprint 41, 07-31).** Đồng bộ tên bằng `scripts/ba_spec/spec_f_sync.py` (dry-run → `--apply`) + `task_s41_rewrite.py` (P3/Q3 có dấu). Nguyên tắc user chốt: **chỉ đổi TÊN model/field — KHÔNG ghi thêm bất cứ thứ gì vào tài liệu BA.** Dev từng thêm cột ghi chú rồi phải xoá (`spec_f_wipe_notes.py`), xem §5. Việc tồn + prompt session sau: `docs/next-session-tasks-notification.md`. Ghi lên sheet thì ghi ít, đúng cái BA cần; phần còn lại để file task local.

---

## §13 wujia-ui-component-standard (tab `UI Component`, gid `488333015`)

**Tab này là chuẩn component dùng chung toàn portal** — mục tiêu: mọi page dùng CÙNG một component, một form. Sheet có **2 khối**: khối trên (dòng 1–23) = danh mục 23 component (ID · Nhóm · Nhận diện · Boundary · Ví dụ); khối dưới (từ dòng 29) = spec đầy đủ (Mục tiêu · Hiện trạng · Spec chuẩn hoá · Variants · Màn hình áp dụng · Acceptance · Out-of-scope · Priority · Status).

**Liên hệ với `5. Issue List`:** tab UI Component = **chuẩn**; Issue List = **kênh triển khai + retest**, nối bằng cột `Related Feature ID`.

**23 component** (Nhóm — ID — tên): Global Shell: `CMP-GH-001` GlobalHeader · `CMP-SCB-001` StoreContextBar. Navigation: `CMP-SN-001` SidebarNavigation (chỉ desktop) · `CMP-BN-001` BottomNavigation (chỉ mobile) · `CMP-BPH-001` BackPageHeader · `CMP-PGN-001` Pagination. Page Structure: `CMP-PC-001` PageContainer · `CMP-PG-001` PageHeader · `CMP-CM-001` CountMeta · `CMP-SH-001` SectionHeader. Container: `CMP-SC-001` SurfaceCard. Filter: `CMP-FB-001` FilterBar · `CMP-SF-001` SearchField · `CMP-FC-001` FilterChipGroup. Detail: `CMP-DS-001` DetailSummary. Status: `CMP-SB-001` StatusBadge. Data Display: `CMP-DL-001` DataList · `CMP-KPI-001` StatCard · `CMP-LC-001` ListCard. Feedback: `CMP-ES-001` EmptyState · `CMP-IB-001` InfoBanner. Action: `CMP-BTN-001` Button. Domain/Order: `CMP-PRD-001` ProductCard.

⚠️ **Mới 3/23 component có spec đầy đủ** — `CMP-PG-001` PageHeader, `CMP-BPH-001` BackPageHeader và **`CMP-SH-001` SectionHeader** (dòng 33, Status `BA Confirmed` 11/08). **20 cái còn lại chỉ có 1 dòng mô tả ⇒ CHỜ BA viết spec, KHÔNG tự đoán px/màu** (chủ dự án chốt 08-10, đúng rule Ask-don't-assume).

`CMP-SH-001` tóm tắt (để khỏi mở sheet): PC title 22/30/800, meta-action 14/20/700, section trước→header 20, header→content 12, cách right slot ≥16; mobile 20/28/800, spacing 16/8, cách ≥12, action tap ≥44. Màu title `#111827` · meta `#6B7280` · action `#28A9DF`. Variant default/meta/action/control — **tối đa MỘT right slot**. Title là **heading thật** (không `<span>`), mỗi màn truyền headingLevel riêng, wrap ≤2 dòng, right slot không wrap (thiếu chỗ thì xuống dòng căn phải, **không tự ẩn**). Count hiện cả khi = 0 và dùng **từ đầy đủ** "5 sản phẩm" (không "5 SP"). Heading **nằm trong card = CardHeader**, không phải SectionHeader. `/portal/delivery` "Danh sách chuyến giao" dùng variant `meta`.

Bảng batch/cụm cũ (B0–B4, C1–C10, E, G, I) → `docs/archive/compact-summary-history.md` §13 (cũ); kế hoạch cụm hiện hành ở `docs/next-session-clusters-H.md`.

### Chuẩn nghiệm thu mỗi issue — khớp ≥90% acceptance BA (chủ dự án yêu cầu 08-10)

Xong code **chưa phải xong**. Trước khi ghi ledger phải đối chiếu **từng gạch đầu dòng** cột `Kết quả mong muốn` của chính issue đó:
1. Build sạch `-u <mod> --stop-after-init` trên **DB copy cô lập** (port riêng, KHÔNG đụng `wujia_tea_19`/8019) — RC=0, 0 ERROR/Traceback.
2. **Đo bằng máy, không nhìn ảnh** — `scripts/ba_spec/qa_visual_check.py` (Playwright+chromium có sẵn env `odoo`), 391×844 / 1920×1080. Gotcha §12: `wait_until="load"`, login submit bằng Enter, set sẵn cookie `wujia_active_franchise_id` (overlay che ⇒ assert **pass rỗng**).
3. Bảng đối chiếu `Yêu cầu | Đo được | Pass/Fail`; **ngưỡng ≥90% Pass**, dòng Fail phải sửa hoặc ghi **LIMIT tường minh**.
4. Regression ≥3 trang khác × 2 viewport: 200, overflow ngang 0, 0 JS pageerror.
5. Harness sai thì sửa harness (L7/L9) — chân lý là spec BA/mockup, không phải kỳ vọng gõ tay.
6. Đạt rồi mới ledger → `qa_sync.py --dry-run` → `--apply` (`Ready for Retest`, **Dev không tự Done**), verify `export?format=csv`.

### Quy ước code khi fix (chủ dự án 08-10: "code hơi phình, ít comment thôi")

- 🔴🔴 **NHẮC LẠI 04/09/2026 (chủ dự án nói thẳng lần 2): HẠN CHẾ COMMENT TRONG CODE.** Lần đầu chốt
  15/08, phiên D3 vẫn viết comment dài (khối 4 dòng giải thích bẫy đặc hiệu trong `portal_exam.css`,
  chú thích tại chỗ khi xoá CSS chết). Chuẩn từ nay: **tối đa 1 dòng**, chỉ ở chỗ người sau chắc chắn
  đoán sai; cấm comment kể lịch sử sprint / dẫn số hiệu issue / chép lại nội dung doc. Chỗ cần dài
  thì viết vào `docs/`, không nhét vào file code. Áp cho cả docstring của test và script `scratchpad/`.

- 🔴 **Chốt 15/08/2026 — KHÔNG để phình code.** Fix bug là sửa **đúng chỗ gốc**, không copy-paste 3 bản cho 3 model — tách một helper dùng chung. Không viết thêm field/model/file khi cái sẵn có đủ dùng. Không đẻ file doc/harness rác trong repo (harness đo để `scratchpad/`). Comment **ít thôi**: chỉ ghi *tại sao* ở chỗ thật sự khó đoán, không ghi *cái gì* (code tự nói), không docstring dài lê thê, không comment kể lịch sử sprint.
- **Tái dùng trước khi viết mới**: `to_local_dt`/`portal_tz` (§11), regex phone PC, `wj_page_header`, `store_picker_modal`, `wj_ajax_list`.
- Comment **1 dòng đủ ý**; xoá comment kể lịch sử sprint (vd `store_picker_navbar.xml` đang có block 10 dòng).
- Không thêm CSS mới khi modifier hiện có đủ; không hex cứng, dùng `var(--wujia-*)`.
