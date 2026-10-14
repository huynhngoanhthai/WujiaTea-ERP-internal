# Cụm J — Branding cấu hình được · Tool dịch backend · Portal Vận hành nhượng quyền (lập 04/10/2026)

> Chủ dự án chốt 04/10: **3 việc này làm TRƯỚC Issue List** (15 Ready for Dev — cụm I trong `next-session-clusters-H.md`
> + 10 issue mới 156–167 chưa phân cụm — chờ tới sau ★JR-O). Thứ tự trong cụm: Branding → Dịch → Vận hành.
> Chi tiết Phần T + Phần O: §5 Phụ lục cuối file. **05/10: gộp còn 7 phiên** (T1+T2 gộp, bỏ T3, O3+O4 gộp).
> **05/10 (sau T1+T2): thêm Phần V — Việt hoá source (V0–V8 + ★VR), làm TRƯỚC J-T4** (chủ dự án: "ưu tiên xử lý trước").
> Thứ tự: V0 → V1…V8 → ★VR → J-T4 → J-O0…O4 → ★JR → Issue List. Tồn đọng toàn dự án: `docs/pending-backlog.md`.
> **07/10 — END-SPRINT 66: Phần B + T + V XONG, đã lên UAT (chapter 79 + 80). Phần O (J-O0…★JR) TẠM DỪNG theo ý BA**
> (chờ BA trả lời câu hỏi Vận hành, `pending-backlog.md` §3) ⇒ việc kế là Issue List cụm I mở rộng (`next-session-clusters-H.md`).
> **14/10 — Phần O MỞ LẠI**: BA xác nhận 11/10 bằng issue #181 WJ-OPS-001 (14 màn, 2 gói mockup FINAL ở cột F của issue).
> Chủ dự án chốt mình làm. Xếp chung thứ tự với cụm K: `next-session-clusters-K.md` §2.

## 0. Luật áp suốt cụm

- **Không sửa code đang có của Thái**: `wujia_franchise*` (gồm `wujia_franchise_operations`), `wujia_mobile_*`,
  `wujia_portal_inspection`, `wujia_fields_value`, `dynamic_dashboard_ai_nexgen`. Chỉ **thêm file mới** khi đã được phép (J-O1).
- ADR-027: `wujia_core` = L1; `wujia_i18n` = L1 platform (portal + backend + mobile cùng cần); `wujia_portal_operations` = L3b.
- Test luôn kèm `-u`. ⚠️ **KHÔNG `-u wujia_core --test-enable`** trên DB đủ module: test `wujia_franchise` của Thái import
  file đã xoá ⇒ registry chết. Test `wujia_core` chạy trên **DB trắng** `-i wujia_core --test-enable --test-tags /wujia_core`;
  DB copy đủ module chỉ `-u` không test.
- Log: `wujia_core` đổi logfile sang `<thư mục logfile>/<năm>/<tháng>/<ngày>.log` ⇒ chạy tay thì đặt `--logfile=<scratchpad>/x.log`
  rồi đọc `<scratchpad>/2026/10/*.log`.
- Dịch: code tiếng Anh, thêm dòng VN vào `docs/i18n-glossary.csv`, sinh `.po` + `.pot` bằng `scripts/sync_translations.py`.
  Script **ưu tiên glossary hơn bản dịch cũ** ⇒ so bằng babel trước/sau, trả lại dòng cũ bị đổi ngoài ý muốn.
- Không commit/push/deploy khi chưa có lệnh. Mỗi phiên ghi `docs/f-progress.md` + ✅ bảng §2.

## 1. Hiện trạng đã đo (04/10)

**Branding**: logo PC đã lấy `res.company.logo_web`, nhưng nhúng **base64 vào mọi trang** (3 chỗ) ⇒ HTML nặng; title `'Portal'`,
`<meta author="Cloudmedia">`, favicon (= `company.logo`; head auth ghi sai `t-attf-src` trên `<link>`) hardcode ở
`wujia_portal_layout/views/layouts.xml` (2 head), `login_page.xml`, `mobile_header.xml`. Màu `#28A9DF` + token ở
`_variables.css`; hex cứng thật còn ~10 dòng: `store_picker.css:179`, `portal_delivery.css:140-141`, `portal_exam.css:542`,
`_wujia_theme.css:212`, `_components.css:478/657/715`, `portal_order.css:693`, `portal_notification.css:185`
(còn lại là chú thích; `portal_report_charts.js:39` đã đọc CSS var).

**Dịch — vì sao "lâu lâu không ăn"** (`odoo19/odoo/tools/translate.py`): (1) `-u` mặc định không ghi đè bản dịch đã có;
(2) chuỗi Python/JS chỉ đọc từ file `.po`, cache RAM theo worker (`CodeTranslations` dòng 1813) ⇒ phải restart;
(3) thiếu `.pot`/sai dạng ref ⇒ bỏ qua im lặng (L16); (4) sửa câu trong template ⇒ term đổi ⇒ mất bản dịch.
Tool của Thái: glossary CSV `key,option,VN,CN,TH` (`custom/wujia_franchise/data/wujia_franchise_export.csv`) + controller
Khảo sát đọc `.po` lúc chạy (`wujia_franchise_inspection/controllers/main.py:81` `get_survey_translations`, so khớp
`_SmartTranslationDict` không phân biệt hoa thường/`&amp;`). Bản chuẩn hoá: `docs/i18n-glossary.csv` + `scripts/sync_translations.py`.

**Vận hành**: backend Thái `wujia_franchise_operations` 19.0.1.0.0 — 6 model `wujia.franchise.employee` ·
`.employee.assignment` (job_position, date_from/to, state) · `.shift.template` · `.work.schedule` (phẳng: 1 dòng = 1 NV × 1 ngày × 1 ca,
draft/confirmed/cancelled) · `.expense` (+category, draft/confirmed/cancelled) · `.revenue` (manual/import, 1 bản/ngày/cửa hàng);
2 nhóm User/Manager; ir.rule toàn cục `[(1,'=',1)]`; **không có liên kết nhân viên ↔ tài khoản portal**. Spec BA tab Model Field mục G
(`wujia.franchise.store.*`: lịch header/dòng, chấm công, nghỉ phép, `member_id`) **lệch** backend; tab Controller CT-059…067
("Vận hành nội bộ NQ") nhiều dòng "cần chốt"; tab FE-Portal chưa có màn nào; chưa có Figma.

## 2. Bảng trạng thái

| Phiên | Nội dung | Module | Trạng thái |
|---|---|---|---|
| J-B1 | Nguồn brand trong `wujia_core` (res.company + Settings + palette + route ảnh) | wujia_core | ✅ 04/10 — `de64704` |
| J-B2 | Áp brand vào portal (head, logo, CSS var) + backend (favicon, title tab) | portal_layout, core (+ ~7 CSS module màn) | ✅ 04/10 — chưa deploy |
| J-T1+T2 | `wujia_i18n`: danh mục chuỗi + màn sửa + quét + Áp dụng ngay + áp lại sau `-u` (gộp 05/10) | wujia_i18n (mới) | ✅ 05/10 — chưa commit |
| ~~J-T3~~ | ~~Lớp phủ chuỗi Python/JS không restart~~ — **bỏ** (chủ dự án 05/10: chuỗi code đổi ⇒ xuất `.po` + restart) | — | ✗ |
| J-V0 | Chốt quy ước + công cụ Việt hoá source (xem §6) + khách portal mặc định vi_VN + bật zh_CN | docs, scripts, i18n, portal_layout | ✅ 05/10 — chưa commit |
| J-V1 | `wujia_portal_layout` (259) + helper `wjMsg` + khối `#wj-msgs` + xoá `lang.js` chết | portal_layout | ✅ 05/10 — chưa commit |
| J-V2 | `wujia_portal_base` (382) + màu badge theo EN/lazy/VN cũ + nhãn theo `record.env` | portal_base | ✅ 05/10 — đã push, chờ deploy |
| J-V3 | `wujia_portal_exam` (345) + `wujia_exam` (63) + khối `_ex_msgs` câu JS | exam ×2 | ✅ 06/10 — `baa5b547`, đã lên UAT |
| J-V4 | `wujia_portal_sale` (201) + `wujia_sale` (16) + `wujia_order_window` (8) + template `cart_sync_root` câu JS | sale ×3 | ✅ 06/10 — `359fe36c` đã lên UAT; sửa sau UAT `6129ca59` đã push, chờ deploy |
| J-V5 | `wujia_portal_debt` (196) + `wujia_account` (4) + khối `_debt_copy_msgs` câu JS + đơn vị số rút gọn theo ngôn ngữ | debt | ✅ 06/10 — `2f9f5695` đã push, chờ deploy |
| J-V6 | `wujia_portal_return` (168) + `wujia_return` (69) + `_ret_line_msgs` câu JS + migration seed loại lỗi | return ×2 | ✅ 06/10 — `b78c4568` đã push, chờ deploy |
| J-V7 | support (112+2) + knowledge (46+2) + notification (86+27) + migration seed loại thông báo + WJ-SUPPORT-003 | 6 module | ✅ 07/10 — `351932a8` đã push, chờ deploy |
| J-V8a | purchase_history (99) + portal_delivery (93) + delivery (15) + fleet (11) — chủ dự án tách J-V8 làm đôi 07/10 | 4 module | ✅ 07/10 — `dbd4335b` đã lên UAT 07/10 |
| J-V8b | info_request (85+7) + report (69) + core (9) + metabase (1). `wujia_core` sửa câu **không bump version** (tránh `-u wujia_core` kéo dây chuyền module Thái); `DEFAULT_BRAND_NAME = 'Ngô Gia'` giữ + khai miễn quét | 5 module | ✅ 07/10 — `02e363fc` đã lên UAT 07/10 |
| ★J-VR | Review Phần V: quét = 0, vi_VN 0 lệch, en/th 156 trang sạch, bỏ nhánh tra ngược badge VN, danh sách BA (1 361 cặp) + Thái (284) ở `docs/i18n-review/`, chapter 79 | portal_base, sale, purchase_history, delivery | ✅ 07/10 — `457ff953` đã lên UAT 07/10 |
| J-T4 | Nhập/xuất CSV kiểu Thái + zip `.po`/`.pot`; `po_writer` dùng chung + CLI `scripts/i18n_tool.py`; dòng chỉ khớp câu nguồn chỉ điền chỗ trống (chủ dự án 07/10) | wujia_i18n, scripts | ✅ 07/10 — `ca198ace` đã lên UAT (cùng 19.0.1.3.0) |
| J-T5 | Dịch tự động (DeepL): wizard chọn ngôn ngữ → hàng đợi + cron theo lô → state `machine` áp ngay, rà sau · bảng thuật ngữ · khoá ở Settings (chủ dự án 07/10: chưa có key ⇒ giả lập) | wujia_i18n | ✅ 07/10 — `78a68ea5` đã lên UAT 07/10 |
| J-O0 | Bảng đối chiếu 2 gói mockup FINAL (14 màn) + CT-059…067 ↔ backend + câu hỏi còn lại (0 code) | docs | ☐ mở lại 14/10 (#181) |
| J-O1 | Luật portal ở L2 (file mới `portal_rules.py`, báo Thái) | franchise_operations (thêm file) | ☐ mở lại 14/10 |
| J-O2 | Home vận hành + Nhân viên (danh sách, thêm, hồ sơ, sửa; CCCD bắt buộc, ảnh) | wujia_portal_operations (mới) | ☐ mở lại 14/10 |
| J-O3 | Lịch làm việc (một ca chọn nhiều nhân viên, MVP không chặn trùng lịch) | portal_operations | ☐ mở lại 14/10 |
| J-O4 | Chi phí + Doanh thu: danh sách, tạo, chi tiết; chỉ Xác nhận/Hủy, không hiện Nháp, mã backend, nguồn | portal_operations | ☐ mở lại 14/10 |
| ★JR | Review: ma trận role × cửa hàng × route, ảnh, query, mutation, quét chuỗi mới vào tool dịch | — | ☐ mở lại 14/10 |

## 3. Đã làm ở J-B1 (để B2 dùng)

- `wujia_core` **19.0.2.0.0**, depends thêm `web`. Field `res.company`: `wj_brand_name`, `wj_primary_color` (mặc định `#28A9DF`,
  chuẩn hoá in hoa, constraint `#RRGGBB`), `wj_logo_mobile`, `wj_favicon`, `wj_login_background`. Logo PC = `logo` sẵn có.
- Settings: tab **"Thương hiệu"** (`views/res_config_settings_views.xml`, related `company_id.*`).
- `res.company._wj_brand_info()` (ormcache theo công ty; `write` chạm field brand ⇒ `registry.clear_cache()`) trả
  `name, primary, palette, css, has_logo_mobile, has_favicon, has_login_background, version`.
  `_wj_brand_url(kind, width=0)` ⇒ `/wj/brand/<cid>/<kind>?v=<version>[&width=]`.
- `tools/brand_palette.py`: màu mặc định ⇒ **đúng bộ token BA, `css` rỗng** (0 pixel đổi); màu khác ⇒ sinh HSL (lệch bộ BA ≤4/kênh khi
  thử với #28A9DF), CTA làm đậm tới chữ trắng ≥4.5:1. Key = tên biến `--wujia-<key>`; thêm `primary-rgb` (`"40 169 223"`) cho
  `rgb(var(--wujia-primary-rgb) / .04)`.
- Route `/wj/brand/<cid>/<kind>` (`auth=public`, readonly): kind `logo | logo_mobile | favicon | login_background`; mobile/favicon
  trống ⇒ rơi về `logo`; `login_background` trống ⇒ 404 (trang tự dùng ảnh mặc định); width chỉ `0/32/64/180/192/512`;
  có `?v=` ⇒ `Cache-Control immutable`. ⚠️ Công ty **không có logo** ⇒ logo/favicon 404 — B2 phải chỉ in `<link>/<img>` khi có ảnh.
- Test `tests/test_brand.py` tag `wujia_brand`: 10 test, DB trắng 0 failed; mutation 5/5 đỏ đúng.
- `vi_VN.po` + `wujia_core.pot` (mới) sinh lại; 17 dòng VN mới trong glossary; nhãn Settings + lỗi Python đọc lại tiếng Việt OK.
- DB nháp: `wujia_b1` (copy `wujia_g5s`, đã `-u wujia_core`, bật vi_VN, admin/admin) · `wujia_b1t` (DB trắng test) — xoá được.

## 3b. Đã làm ở J-T1+T2 (05/10, để T4/JR dùng)

- `wujia_i18n` 19.0.1.0.0 (L1, depends `base`,`web`; app menu "Bản dịch", nhóm `group_wujia_translator`, admin implied).
- `wujia.i18n.term` (module, kind `model|model_terms|code_python|code_js`, name, res_id, src, `key_hash` md5, active) — khoá:
  chuỗi DB theo (kind, model,field, xmlid, src); chuỗi code theo (kind, src) vì Odoo tra code theo msgid/module.
  `_wj_scan(modules, langs)` = `TranslationModuleReader` mỗi ngôn ngữ 1 lượt; upsert, **không đè `override`**, term mất ⇒ archive.
- `wujia.i18n.value` (term × lang, value, state `synced|override|missing`, `pending`); sửa tay ⇒ override + pending.
  `action_apply` ⇒ `TranslationImporter._load` + `save(overwrite=True, force_overwrite=True)` + xoá cache `default` (+`templates`
  nếu view, +`stable` nếu nhãn field). Chuỗi code không áp (chờ T4 xuất `.po` + restart).
- `ir.module.module._update_translations` override ⇒ áp lại `override` của module vừa nạp (mọi `-u`, bật ngôn ngữ).
- `wujia.i18n.coverage` (SQL view) module × lang. Wizard quét: mặc định module `wujia_%`/`wj_%` × ngôn ngữ active ≠ en_US.
- Số đo DB copy (29 module × 3 ngôn ngữ): 4 839 term / 14 517 dòng, quét 3,1 s (lại 1,8 s) ⇒ chạy đồng bộ, không cần cron.
- ⚠️ Cho T4/JR: **90% câu gốc portal (1 384/1 533) viết cứng tiếng Việt**, module portal không có `i18n/` ⇒ độ phủ portal ≈0%
  ở cả 3 tiếng; vi_VN "chưa dịch" nhưng hiển thị đúng (câu gốc đã là VN). zh/th phải dịch từ câu VN. Cân nhắc ở T4: coi
  vi_VN = câu gốc khi src có dấu tiếng Việt (để độ phủ không báo sai).

## 4. Prompt từng phiên

Dán **sau `/wujia-start`**. Áp mọi phiên: `git pull` · đọc §0–§3 file này · đo trước/sau · ghi f-progress + ✅ §2.

### J-B2 — Áp brand vào portal + backend
```text
Làm phiên J-B2 (docs/next-session-clusters-J.md §3). Đọc §3 trước.
1. wujia_portal_layout: depends thêm wujia_core; layouts.xml 2 head: <title> = "<title> · <brand>", meta author = brand,
   favicon/apple-touch-icon href = company._wj_brand_url('favicon', 32/180) — CHỈ khi company có logo/favicon; sửa t-attf-src
   sai trên <link>; chèn <style> brand.css SAU asset_frontend khi css != ''.
2. Logo sidebar/navbar mobile/mobile_header/login: data: base64 → _wj_brand_url('logo'|'logo_mobile'); alt = brand.
   Login: nền dùng login_background nếu has_login_background, không thì ảnh cũ.
3. CSS: ~10 dòng hex cứng (§1) → var(--wujia-primary*) / rgb(var(--wujia-primary-rgb) / a). Bump version + ?v=.
4. Backend: favicon + title tab theo brand (inherit web.layout / patch title service), KHÔNG đụng MuK/mobile_core.
Nghiệm thu: wj_measure trước/sau 23 route × 5 khổ ở cấu hình mặc định = 0 lệch; đổi thử #E4572E + logo khác trên wujia_b1
⇒ ảnh PC/mobile/login đổi theo; HTML /portal nhẹ đi (đo byte); suite portal_layout + base 0 đỏ mới.
```

### J-T1 → J-T4, J-O0 → J-O4, ★JR
Nội dung từng phiên = dòng tương ứng ở bảng §2 + chi tiết ở §5 Phụ lục. Điểm phải hỏi chủ dự án khi tới:
- J-T3: nếu spike lớp phủ Python/JS không ổn trên Windows/nhiều worker ⇒ báo, dùng đường lùi (xuất `.po` + restart).
- J-O1: xin phép **thêm file** `wujia_franchise_operations/models/portal_rules.py` + báo Thái trước khi code.
- J-O0: gửi BA câu hỏi chấm công / nghỉ phép / duyệt ca / Staff thấy gì / gắn nhân viên ↔ member — không tự quyết.
- Portal Vận hành dùng luật **một cửa hàng đang chọn** (`get_active_franchise_id()`, không fallback mọi cửa hàng) + **role tại
  cửa hàng đó** (`get_max_role_in_franchises((fid,))`) — đúng hướng #152/#153; chỉ Owner/Manager; Staff ⇒ trang không quyền.

---

## 5. Phụ lục — plan chi tiết (chép nguyên từ phiên lập 04/10)

## Phần T — Tool dịch trong backend, module mới `wujia_i18n` (4 phiên)

Tầng L1 platform (ADR-027 cho phép vì portal + backend + mobile đều cần). Depends `base`, `web`. Nhóm quyền `group_wujia_translator` (sửa) + admin.

**T1 — Danh mục chuỗi + màn sửa**
- `wujia.i18n.term`: `module`, `kind` (`model` · `model_terms` · `code_python` · `code_js`), `name` (ref kiểu `model_terms:ir.ui.view,arch_db:<xmlid>`), `res_id`, `src`. Unique (`module`,`name`,`res_id`,`src`).
- `wujia.i18n.value`: `term_id`, `lang`, `value`, `state` (`synced` · `override` · `missing`). Unique (`term_id`,`lang`), index (`lang`,`state`).
- Wizard **"Quét chuỗi"**: chọn module + ngôn ngữ, dùng `odoo.tools.translate.TranslationModuleReader(cr, modules, lang)`, đúng nguồn mà lệnh export `.pot` đang dùng (kế thừa thiết kế của Thái trong `sync_translations.py`). Chỉ upsert, không xoá bản sửa tay.
- Màn danh sách sửa tại chỗ, mỗi dòng là term × ngôn ngữ (giống `ir.translation` v13). Lọc: module, ngôn ngữ, "Chưa dịch", "Đã sửa tay", theo loại. Có form một term, các ngôn ngữ đặt cạnh nhau. Có bảng độ phủ % theo module × ngôn ngữ.
- Chuẩn hoá khi so khớp: dùng lại ý `_SmartTranslationDict` của Thái (`&amp;`/`&`, khoảng trắng) để nhận đúng term QWeb có thẻ HTML.

**T2 — Áp ngay + bền qua `-u`**
- Nút **"Áp dụng"**: `kind` = `model`/`model_terms` thì ghi qua `TranslationImporter.load_rows` → `save(overwrite=True, force_overwrite=True)`, là đúng đường Odoo import `.po`, rồi xoá cache `templates`. Hiệu lực ngay, không restart.
- Bền qua `-u`: override `ir.module.module._update_translations` (kiểm signature trong `odoo19/odoo/addons/base/models/ir_module.py` khi code): gọi super xong thì **áp lại** mọi `state=override` của các module vừa nạp. Đây là cách xử lý gốc của chuyện "lâu lâu không ăn".

**T3 — Lớp phủ chuỗi Python/JS (spike trước, có đường lùi)**
- Tool ghi bản sửa của chuỗi code ra file `.po` sinh tự động trong `data_dir/wujia_i18n/<db>/<module>/<lang>.po`. Thêm `post_load` hook nối đường dẫn này vào `odoo.tools.translate.get_po_paths`, để Odoo tự đọc bằng chính bộ lọc `#. odoo-python` / `odoo-javascript` của nó.
- Lưu xong thì xoá `code_translations.python_translations/web_translations` ở worker hiện tại và `registry.clear_cache()` để báo các worker khác. Patch `Registry` khi nhận tín hiệu cũng xoá 2 dict đó. Đổi hash `/web/webclient/translations` để trình duyệt tải lại.
- Đường lùi nếu spike không ổn trên Windows/nhiều worker: chuỗi code vẫn đi bằng nút xuất `.po` (T4) + restart, ghi rõ vào màn hình.

**T4 — Nhập/xuất**
- Nhập CSV glossary đúng định dạng của Thái (`key,option,VN,CN,TH`; `option` = ref). Khớp theo (ref, src), không có thì khớp theo src. Nạp được ngay `docs/i18n-glossary.csv` + `custom/wujia_franchise/data/wujia_franchise_export.csv`.
- Xuất: CSV cùng định dạng + **zip `.po` + `.pot` từng module** để dev commit vào source (L16: bản dịch chỉ nằm trong DB thì dựng lại DB là mất). Phần ghi `.po` tách từ `scripts/sync_translations.py` thành `wujia_i18n/tools/po_writer.py`: babel, `.pot` sinh cùng lượt, có `#. odoo-python`, dạng ref menu `model:ir.ui.menu,name:`. Script CLI gọi lại chính module này để khỏi có hai bản.
- Nghiệm thu: sửa 1 chuỗi QWeb portal + 1 nhãn field + 1 chuỗi `_()` + 1 chuỗi JS ở `zh_CN`. Mở màn đúng ngôn ngữ thấy đổi **không restart** (T3 đạt) hoặc sau restart (đường lùi). Chạy `-u` module đó thì bản sửa vẫn còn. Đọc chỉ-đọc qua XML-RPC `context={'lang':…}` theo L16.

Ngoài phạm vi (ghi lại để khỏi mở lại): các hằng nhãn portal đang để cứng tiếng Việt (`ROLE_LABELS`, `RETURN_STATUS_LABELS`, `SALE_STATE_META`) thì tool không dịch được. Chuyển sang `_lt()` là một đợt riêng, sau T4.

---

## Phần O — Portal Vận hành, module mới `wujia_portal_operations` (4–5 phiên)

L3b, depends `wujia_portal_base` + `wujia_franchise_operations`. Chia theo **chức năng** (ADR-027 addendum). Không model nghiệp vụ.

> **Phạm vi mới theo #181 (14/10) — thay các chỗ lệch bên dưới.** 14 màn PC + mobile: Home, Nhân viên (danh sách, thêm,
> hồ sơ, sửa), Lịch làm việc, Chi phí, Doanh thu, điều hướng. Nhân viên chỉ thuộc cửa hàng đang chọn, không hiện mã nhân
> viên, CCCD bắt buộc, có ảnh, hồ sơ một nút Sửa. Một ca chọn nhiều nhân viên, MVP không chặn trùng lịch. Chi phí/doanh
> thu không hiện mã backend, nguồn, trạng thái Nháp; chỉ Xác nhận/Hủy. Khổ nghiệm thu: mobile 360/390/430, PC từ 992.
> Vậy O2 không còn "chỉ đọc" và O3/O4 không còn "khai nháp". Mockup nằm ở **hyperlink** cột F của issue: tải `xlsx`
> rồi đọc `cell.hyperlink` (bài học L9), `export?format=csv` làm mất link. J-O0 phải soi lại từng field với backend
> anh Thái (backend đang có `draft/confirmed/cancelled` và lịch phẳng một dòng = một nhân viên × một ngày × một ca).

**O0 — Bảng đối chiếu + màn (0 code)**: `docs/operations-portal-spec.md` gồm CT-059…067 ↔ model/field thật của Thái, danh sách màn PC + mobile dựng từ component chuẩn (`portal-component-standard.pdf`: PageHeader, FilterBar, DataList/ListCard, StatusBadge, EmptyState, Pagination) và câu hỏi gửi BA (chấm công, nghỉ phép, duyệt ca, Staff có thấy gì không, gắn nhân viên ↔ member). Chưa có Figma thì bám chuẩn component.

**O1 — Luật portal ở L2** (thêm **file mới** `wujia_franchise_operations/models/portal_rules.py`, không sửa file cũ của Thái; báo Thái): `_portal_scope_domain(franchise_id)`, `_portal_can_manage(role)`, `_portal_week_schedule(fid, week)` (1 `search_read` + 1 `_read_group`), `create_from_portal` cho chi phí + doanh thu (luôn `draft`, có savepoint, trả mã lỗi form; dùng constraint có sẵn như doanh thu một bản/ngày), KPI tháng bằng `_read_group`. Test model.
- Luật phạm vi theo hướng #152/#153 ngay từ đầu: **một cửa hàng đang chọn** (`get_active_franchise_id()`, không dùng fallback "mọi cửa hàng") + **role tại cửa hàng đó** (`get_max_role_in_franchises((fid,))`). Chỉ Owner/Manager. Staff thấy trang "Không có quyền xem" như Công nợ. Chưa chọn cửa hàng thì hiện EmptyState "Chọn cửa hàng".

**O2 — Hub + Nhân viên + Lịch ca (chỉ đọc)**: `/portal/operations` có 4 KPI (NV đang làm · ca tuần này · chi phí tháng · doanh thu tháng) và lối vào các màn. `/portal/operations/employees` là danh sách + chi tiết, lọc theo vị trí/trạng thái. `/portal/operations/schedule` xem theo tuần (PC bảng ngày × ca, mobile thẻ theo ngày). Mục nav sidebar PC + sheet "Thêm" mobile chỉ hiện khi đủ role.

**O3 — Chi phí**: `/portal/operations/expenses` gồm danh sách (lọc tháng/loại/trạng thái, nhãn trạng thái một nguồn) + form tạo nháp + chi tiết. HQ xác nhận ở backend.

**O4 — Doanh thu ngày**: `/portal/operations/revenue` gồm danh sách + khai doanh thu ngày (nháp, chặn trùng ngày, thông báo tiếng Việt).

**★OR — Review**: ma trận role × cửa hàng × route bằng máy (truy cập ID cửa hàng khác thì 404), ảnh PC/mobile, `check_layers.py` 0 vi phạm, đếm query mỗi trang (danh sách ≤ hằng số, không N+1), mutation cho luật scope/role. Chuỗi mới quét vào tool dịch (Phần T).

---


---

## 6. Phần V — Việt hoá source (lập 05/10, ưu tiên trước J-T4)

**Vì sao**: quét `scripts/qa/vn_hardcode_scan.py` ra **2 659 chuỗi tiếng Việt viết cứng** (code team ≈ 2 375, Thái 284) + 945 trong
test — chi tiết `docs/vn-hardcode-inventory.{md,csv}`. Odoo chỉ dịch khi câu gốc là tiếng Anh ⇒ portal EN/ZH/TH vẫn hiện tiếng
Việt dù có tool dịch. Tool `wujia_i18n` (T1+T2) đã sẵn để kiểm độ phủ sau mỗi phiên V.

**Quy ước mỗi phiên V1–V8** (chốt ở V0):
1. Câu gốc trong QWeb/Python/JS → tiếng Anh (ngắn, rõ; không dịch máy câu dài — giữ nghĩa nghiệp vụ).
2. Dòng glossary `key=<EN>, VN=<câu cũ>` ⇒ `sync_translations.py` sinh `vi_VN.po` + `.pot` ⇒ **user vi_VN thấy y như cũ**.
3. Hằng nhãn Python (`ROLE_LABELS`, `RETURN_STATUS_LABELS`, `SALE_STATE_META`…) → `_lt()`; thông báo controller → `_()`.
4. Câu trong biểu thức `t-out="… or 'Chưa có'"` → tách `<t t-set>` (dịch được) hoặc truyền từ controller.
5. Test assert theo nhãn VN: chạy với `lang=vi_VN` (có `.po`) hoặc assert theo key; không xoá assert.
6. Nghiệm thu: quét lại module = 0 · probe text 26 route × vi_VN **0 lệch chữ** + ảnh 0 lệch · en_US/th_TH chụp ảnh không vỡ
   layout (câu tiếng Anh/Thái dài hơn) · suite module 0 đỏ mới · độ phủ trong app "Bản dịch" vi_VN ≈100%.

**J-V0 — ✅ 05/10: quy ước đã chốt + công cụ** (chủ dự án trả lời 4 câu):

| # | Câu | Chốt |
|---|---|---|
| a | JS portal (Vuexy, không có `_t`) dịch bằng gì | Chuỗi đi từ QWeb sang JS qua `data-wj-msg-*` ⇒ dịch bằng `.po` như QWeb |
| b | User `en_US` | EN thấy EN, VN thấy VN. **Mặc định vi_VN**: user portal mới (đã có, `portal_base/res_users.py`) + **khách chưa đăng nhập trên `/portal`** (mới, không theo ngôn ngữ trình duyệt). Không đổi user đã chọn en_US |
| c | Ngôn ngữ | **Bật hết** vi/en/th/**zh_CN** (`wujia_i18n` tự bật lúc `-i`); thêm ngôn ngữ ở Settings là bộ chọn portal có ngay cho mọi người (WJ-LANG-001) |
| d | BA duyệt câu EN? | **Không.** EN do dev đặt; ZH/TH dịch bằng DeepL (J-T5). Câu cần sửa gom **1 danh sách gửi BA 1 lần ở ★VR** |

**Quy ước JS (a)** — Odoo 19 chỉ dịch attribute trong `TRANSLATED_ATTRS` (`odoo/tools/translate.py:74`: `title`, `placeholder`,
`aria-label`, `alt`, `data-tooltip`…); `data-*` tuỳ ý **không** dịch. Vì vậy câu đặt trong text node `<t t-set>` (dịch được, như mẫu
`wj_txt` của J-B2) rồi gắn vào attribute:
```xml
<t t-set="wj_msg_upload_failed">Upload failed. Please try again.</t>
<form class="wj-avatar-form" t-att-data-wj-msg-upload-failed="wj_msg_upload_failed"> … </form>
```
```js
// helper đặt ở wujia_portal_layout (làm ở V1): tìm attr gần nhất từ el lên tổ tiên, rồi khối chung #wj-msgs, cuối cùng fallback.
wjMsg(el, 'upload-failed', 'Upload failed. Please try again.')
```
Câu dùng chung nhiều màn (lỗi mạng, "Có lỗi xảy ra") đặt 1 lần trong `<div id="wj-msgs" hidden …>` ở layout. Fallback trong JS là
câu tiếng Anh (không còn tiếng Việt trong `.js`).

**J-V1 — ✅ 05/10: helper JS + bài học cho V2–V8**
- `wjMsg(el, key, fallbackEN)` ở `wujia_portal_layout/static/assets/js/wj_msg.js`, nạp trong `asset_frontend_js` (layout đăng nhập
  KHÔNG nạp bundle `web.assets_frontend` ⇒ không đặt helper trong bundle). Khối chung `wujia_portal_layout.wj_msgs` (`#wj-msgs`,
  gọi ở cả 2 layout): `unsaved-changes`, `show`, `hide`. Câu riêng 1 màn ⇒ `data-wj-msg-*` trên phần tử gần nhất. Caller giữ fallback
  `window.wjMsg ? … : 'EN'`.
- Nhãn mặc định trong component: `<t t-set="_fb_t_search">Search</t>` rồi `x or _fb_t_search` (đặt tên `_<tiền tố>_t_*`).
- Logic dò chữ trong câu lỗi (`'không khớp' in error`) phải đổi sang mã (`error_field`) — câu đã dịch thì dò chữ hỏng ở ngôn ngữ khác.
- ⚠️ `vn_hardcode_scan.py` nhận tiếng Việt qua **dấu** ⇒ sót chữ không dấu (`Trang`, `Trang sau`, `/ trang`, `Xem`). Sau `sync_translations`
  luôn liệt kê msgid chưa dịch của `.po` ⇒ bắt được nhóm này.
- Odoo gom phần tử inline thành 1 term (`<span>A &amp; B</span>`, `<span class=…>Login</span>`) ⇒ glossary phải có đúng msgid dạng đó.
- Chuỗi tiếng Anh có sẵn từ trước mà user thấy (`Wrong login/password`, nhãn `Login`, alt `avatar`, aria `Breadcrumb`) ⇒ dịch luôn
  (đúng chốt b "VN thấy VN"); `_()` của module KHÔNG dùng bản dịch của Odoo core.
- Test assert nhãn VN: `tests/common.py::load_vi(env)` (bật vi_VN + nạp `.po` của khung, trả env `lang=vi_VN`); user HttpCase
  tạo với `'lang': 'vi_VN'`. V2+ chép mẫu này cho module mình (nạp `.po` của chính module).

**J-V2 — ✅ 05/10: bài học cho V3–V8**
- **Màu badge**: `portal_base.controllers.utils.STATUS_VARIANT_BY_LABEL` khoá theo câu **EN**. Module V3–V8 đổi nhãn sang `_lt('EN')`
  rồi gọi `status_badge_for(lazy)` (tra `_source`); câu EN mới phải **thêm vào** `_STATUS_TERMS_BY_VARIANT` (đúng nhóm màu) + glossary.
  Nhánh nhãn VN cũ (`_legacy_vn_status_labels`, đọc ngược `vi_VN.po`) chỉ để module chưa đổi vẫn đúng màu ⇒ ★VR xoá.
- `.pot`: `('key', _lt('X'))` trong tuple ⇒ trình trích lấy `'key'` làm msgid (sai) ⇒ dùng dict `{'key': _lt('X')}`.
  `_lt(biến)` không được trích ⇒ chỉ `_lt('literal')`.
- Hàm nhận bản ghi ⇒ `record.env._(lazy)` (không `str(lazy)`: không có request ⇒ ra EN — cron, test, mail).
- Test module phụ thuộc so câu thông báo: `self.env(context=dict(lang=user.lang))._(ERR_X)` thay vì so lazy (`in` với lazy ⇒ TypeError);
  test chạy không request mà assert nhãn VN ⇒ `setUpClass` bật vi_VN + `cls.env = cls.env(context=dict(cls.env.context, lang='vi_VN'))`.
- Dữ liệu mẫu (`data/*sample*.xml`, `noupdate`) giữ tiếng Việt ⇒ thêm vào `DATA_FILES` của `vn_hardcode_scan.py`.
- Đo: DB copy phải thuộc user `odoo19` (`ALTER DATABASE … OWNER TO odoo19`) và chép filestore (`rsync -a --ignore-existing`), nếu không
  `/portal` 404 / mất logo ⇒ lệch giả. Mốc vi_VN hiện tại = sau V2.

**J-V3 — ✅ 06/10: bài học cho V4–V8**
- Trình trích `.pot` lấy MỌI literal nằm trong lời gọi `_(...)` ⇒ `env._(X['published'][0])` đẻ msgid rác "published" ⇒ gán biến trước
  (`label = X[k][0]; env._(label)`).
- `docs/i18n-glossary.csv` chỉ được **nối thêm** (CRLF, giữ nguyên byte dòng cũ) — ghi lại cả file bằng csv writer đổi quote/CRLF 68 dòng.
- Không round-trip `.po` qua babel `write_po` (mất dòng `#:`); sửa `.po` bằng text.
- Glossary dùng chung **ghi đè msgstr cũ** của module (V3: 10 câu `wujia_exam`) ⇒ sau `sync` so `.po` cũ/mới bằng babel, khôi phục câu
  không chủ ý bằng sửa text; câu khác nghĩa theo màn giữ riêng từng module (`Time slot` = "Ca thi" backend / "Khung giờ" portal).
- Nhiều câu JS: 1 `<t t-set>` mỗi câu + 1 dict `{'data-wj-msg-key': biến}` rồi `t-att="dict"` lên mọi root dùng (PC + mobile) —
  không lặp 45 thuộc tính ở 2 nơi. Helper `m(key, 'EN', arg)` trong `init(root)`; cẩn thận `var m` cục bộ che helper.
- Chữ không dấu (T2…CN, `Mo`…) máy quét không bắt ⇒ đọc msgid chưa dịch sau `sync`; Odoo gom `<span>` inline thành 1 term ⇒ glossary
  phải đúng msgid gộp (cả `&amp;`, khoảng trắng).
- Test fixture dùng chung nhiều module: cờ lớp `_vi_modules` cho module con nạp thêm `.po` của mình; module nghiệp vụ L2 không phụ thuộc
  `portal_base` ⇒ `load_vi(env, modules)` riêng ở `wujia_exam/tests/common.py`.
- Test chống lùi badge: bảng nhãn VN viết cứng TRƯỚC phiên ⇒ assert `env_vi._(lazy) == vn_cũ` và `status_badge_for(lazy) ==
  status_badge_for(vn_cũ)` (nhãn vốn trung tính thì miễn kiểm "khác neutral").
- DB trắng `-i X --test-enable` gãy vì test `wujia_franchise` (Thái) import file đã xoá ⇒ `-i` không test rồi `-u --test-enable`.

**J-V4 — ✅ 06/10: bài học cho V5–V8**
- Bảng câu thông báo tra theo mã (`X[code]`) ⇒ helper `_x_message(code)` gán `msg = X[code]` rồi `request.env._(msg)`; viết thẳng
  `env._(X[code])` đẻ msgid rác (`QTY_ABOVE_MAX`, `message`). Câu có `{brand}` ⇒ dịch trước, `_wj_brand_text` sau (hàm chỉ `.replace`).
- Câu JS của 1 cụm màn dùng chung root (`#wj-cart-sync`) ⇒ 1 template riêng (`cart_sync_root`: `<t t-set>` + dict `t-att`) rồi `t-call`
  ở mọi trang — không chép khối câu vào từng trang; test kiểm mọi key `m("…")`/`this.msg("…")` có `data-wj-msg-*` + mọi trang gọi template.
- Chữ không dấu máy quét sót kiểu viết tắt: `SL`, `SP`, `. Khung:` ⇒ đọc msgid chưa dịch + grep viết tắt quen (`SL`, `SP`, `ĐVT`, `KH`).
- **Bản dịch `model:` (field/help/selection) gắn theo xmlid**, không cần msgid khớp source ⇒ `.po` sinh lại có thể làm trống msgstr mà DB cũ
  vẫn hiện VN (DB cài mới sẽ ra EN). Sau `sync` so giá trị vi_VN trong DB HEAD ↔ DB mới (bảng `ir_model_fields`/`_selection`/`ir_model`/
  menu/action/arch view theo `ir_model_data.module`): phải 0 chỗ VN → EN.
- Module khác assert chữ trong arch của module đang Việt hoá (`portal_base` c8 đọc arch sale) ⇒ `-u` mỗi module V không chạy test module
  phụ thuộc: luôn `-u` cả danh sách module phụ thuộc (V4: 9 module) và so số test với HEAD (worktree + DB copy riêng).
- Test so chữ VN theo `env._` cùng ngôn ngữ + DB đo đã nạp `.po` ⇒ mutation "bỏ `load_vi`" có thể vẫn xanh; chốt chặn là test bảng VN
  viết cứng TRƯỚC phiên (`test_jv4_i18n.test_messages_vi_unchanged`).
- Trang có kết nối nền (bus/polling) không bao giờ `networkidle` ⇒ script Playwright chờ `load` + 700 ms.
- Stub chặn thư viện vendor (Vuexy `i18next`) phải chạy TRƯỚC lời gọi; `core/app.js` gọi ngay lúc nạp ⇒ sửa tại nguồn (stub nạp sau = vô
  tác dụng, 404 locale tồn tại từ Sprint 4.2). Đo `response.status >= 400` trong Playwright, không chỉ `pageerror`.
- Model báo cáo SQL view (`_auto = False`) không khai `_depends` ⇒ test tạo dữ liệu rồi search phải `env.flush_all()` trước.

**J-V5 — ✅ 06/10: bài học cho V6–V8**
- `env._(lazy)` dịch theo module CỦA lazy (`_lt` khai ở file nào thì msgid thuộc module đó) + `env.lang` ⇒ hằng nhãn module-level là `_lt`,
  dịch lúc render bằng env người xem (`translated_badges(env, X)`), không `str(lazy)`.
- `LazyGettext.__eq__`/`__hash__` ném `NotImplementedError` ⇒ test so `lazy._source`, không `==` thẳng.
- Đơn vị số rút gọn (`tỷ`/`tr`/`k`, chữ không dấu máy quét sót) ⇒ msgid có placeholder `%sB`/`%sM`/`%sK` + dấu thập phân lấy từ
  `res.lang._get_data(code=env.lang).decimal_point`; hàm nhận `env` (Home KPI gọi cùng hàm).
- Số ít/số nhiều EN: `<t t-if="n == 1">invoice</t><t t-else="">invoices</t>` — 2 term, vi_VN cùng trỏ chữ cũ; HttpCase dữ liệu đúng 1
  bản ghi để bắt "1 invoices".
- Glossary phải khớp đúng msgid sau khi Odoo gom term, gồm cả `&amp;` (`Debts &amp; payments`, `<span>Debts &amp; payments</span>`).
- `sync_translations.py` không ghi msgstr == msgid ⇒ `PDF`, `ID`, chip `i` luôn "chưa dịch" — không phải lùi.
- Test so arch theo ngôn ngữ: bỏ comment XML trước khi `assertNotIn` (comment dev tiếng Việt không dịch); test tìm thẻ theo chuỗi mở
  nguyên (`<section class="x">`) gãy khi thêm `t-att` ⇒ khớp phần `<section class="x"`.
- Trang chỉ có nội dung khi có dữ liệu (công nợ) mà user đo không có ⇒ probe/Playwright chỉ thấy trạng thái rỗng; phủ bằng HttpCase tạo
  dữ liệu riêng, ghi LIMIT.

**J-V6 — ✅ 06/10: bài học cho V7–V8**
- `sync_translations.py` giữ msgstr cũ NHƯNG glossary chung thắng ⇒ msgid trùng câu glossary (Active, Complete, In progress…) bị đổi chữ
  vi. So `.po` cũ/mới bằng babel (chỉ đọc), khôi phục bằng sửa text `.po` + `odoo-bin i18n import -l vi_VN -w` — không `write_po`.
- Nhãn mới trùng nhãn field có sẵn mà bản vi khác (`_('SO bù hàng')` vs field "Compensation SO" = "SO bù") ⇒ đổi câu EN cho khác
  ("Compensation sales order"); `vn_to_en_pairs check` không bắt vì so trong glossary, không so `.po` hiện có.
- `models.Constraint(def, 'msg')` dịch qua `ir.model.constraint.message` (`model:` term trong `.pot`), không qua `_()`; test đọc
  `cons.with_env(env_vi).message`.
- Seed `noupdate` có field dịch: XML → EN + migration chỉ đụng bản ghi `en_US` còn ĐÚNG câu VN cũ (HQ sửa tay giữ), `vi_VN` chỉ thêm khi
  chưa có; bảng VN cũ để ở file riêng (`legacy_seed.py`) khai `DATA_FILES` của máy quét; test tạo trạng thái cũ bằng SQL jsonb.
- Test cũ cấm tên recordset trong `t-if` (d3 "count not hidden when zero") ⇒ số ít/số nhiều dùng biến đếm `<t t-set="_n" t-value="len(x)"/>`.
- Khối chỉ hiện khi có dữ liệu (ảnh đính kèm) ⇒ HttpCase phải tạo đúng 1 bản ghi con để thấy cả khối lẫn số ít.
- Code translations của module KHÁC: `odoo.tools.translate.code_translations.get_python_translations(module, lang)` (`env._` lấy module
  của file gọi).
- Probe vi_VN thêm `data-wj-msg-*` mới là lệch có chủ đích (chữ JS cũ nay thành attr) — ghi rõ, không cập nhật mốc.

**J-V7 — ✅ 07/10: bài học cho V8**
- Máy quét `vn_hardcode_scan` bỏ sót tiếng Việt KHÔNG dấu ("Xem", "Xem ticket" ở `aria-label`/`title`) ⇒ sau `sync` liệt kê msgid chưa
  dịch + grep chữ không dấu quen (Xem, Tim kiem…) rồi thêm tay vào pairs.
- Field computed không lưu trả nhãn dịch phải có `@api.depends_context('lang')`, nếu không cache ngôn ngữ trước trả cho ngôn ngữ sau.
- Key glossary EN chung chung ("General") dễ đụng phân hệ sau ⇒ đặt cụ thể ("General notice"); đổi key thì đổi đồng loạt XML seed,
  `legacy_seed.py`, pairs, `.po`.
- KHÔNG backup nhiều file cùng basename (`controllers/portal.py`) vào một thư mục phẳng ⇒ giữ đường dẫn (`cp --parents` / `git stash`)
  — phiên này đè nhầm controller support, phải viết lại.
- Câu JS của nút hàng loạt nằm ở template con (`portal_notification_results_part`), không phải template trang ⇒ đặt t-set + attr ở
  template chứa nút, test arch đọc đúng template đó.
- HttpCase đổi `user.lang` giữa test ⇒ `authenticate` lại (ngôn ngữ phiên cố định lúc đăng nhập).
- Lệch PC/mobile do một bên đọc `_fields[x].selection` thô (WJ-SUPPORT-003) ⇒ mọi nhãn selection ở portal đi qua một dict `_lt` chung
  cho PC + mobile; test arch cấm `_fields['…'].selection` trong template.

**J-V8a — ✅ 07/10: bài học cho V8b**
- Key EN mới có thể trùng msgid field backend của module KHÁC (vd "Delivery status" ở `wujia_delivery`) ⇒ `sync` ghi đè msgstr
  backend. Trước `apply`: grep mọi key EN mới trong `custom/*/i18n/vi_VN.po`; trùng mà nghĩa khác ⇒ đặt key cụ thể hơn
  ("Shipping status", "Vehicle trip", "Departs at", "Total drop").
- `odoo-bin i18n import` KHÔNG nhận `--logfile`.
- Test gọi `_lt('x')` / `_('x')` bằng literal ⇒ extractor kéo file test vào `#:` của `.po`/`.pot` ⇒ trong test gán biến trước.
- Regex kiểm "câu dự phòng còn trong biểu thức" phải bắt chữ CÓ DẤU tiếng Việt, không bắt mọi ký tự ngoài ASCII (`or '—'` hợp lệ).
- Mutation làm trên bản snapshot (`rsync custom/ → snap/`) rồi rsync lại ⇒ code thật không bao giờ bị đụng, khỏi backup.
- Playwright chặn POST ⇒ 2 lỗi console `ERR_FAILED` mỗi trang (đếm chuông/giỏ) là do script; ghi URL bị chặn và lọc riêng.
- Ghép nhãn + giá trị có sẵn động từ ("Ordered by" + "Created by {brand}") ra câu lủng củng ở en ⇒ soát chỗ dùng hằng trước khi chọn câu EN.

**J-V8b — ✅ 07/10: bài học cho ★VR / J-T**
- Constraint `models.Constraint` dịch qua `ir.model.constraint.message` (field translate), `.po` không cần dòng `#: model:` ⇒ kiểm bằng
  `_sql_error_to_message(exc)` trong `savepoint()` (IntegrityError không tự đổi thành ValidationError ngoài RPC).
- Màu badge tính theo nhãn ⇒ test so `css == status_badge_for(nhãn VN cũ)` bắt được đổi câu EN làm lệch màu.
- File xuất (XLSX) cũng là chữ người dùng thấy ⇒ header `_lt` dịch theo ngôn ngữ người xuất; test mở file bằng `openpyxl`.
- `wj_text_probe` chỉ đo trang chi tiết khi user đo có bản ghi ⇒ tạo cùng 1 bản ghi nháp trên cả 2 DB đo, rồi chuẩn hoá id trong key
  trang trước khi `--diff`.
- Log của `wujia_core` dời vào `<logfile dir>/<năm>/<tháng>/<ngày>.log` ⇒ đọc kết quả test ở đó, `--logfile=/dev/stderr` làm vỡ
  `odoo-bin shell`; zsh không tách từ `$var` trong vòng `for` ⇒ gọi tường minh.
- DB đo cài thêm module (metabase) ⇒ số test lệch mốc HEAD; luôn đối chiếu danh sách test chứ không chỉ tổng.

**★J-VR — ✅ 07/10: bài học cho J-T / ★JR**
- Hàm tô màu theo nhãn (`status_badge_for`) chỉ nhận `_lt`/câu EN. Caller nào trả `(nhãn đã dịch, màu)` phải tính màu từ `_lt`
  (`portal_order_badge`, `portal_order_state_badge`). Nhánh tra ngược vi_VN.po đã bỏ; đáp án màu cũ cho test = `tests/common.py::legacy_vn_badge`.
- Grep viết tắt không dấu bắt được chỗ máy quét sót ("SL" ở chi tiết chuyến mobile); Odoo gộp 3 `<span>` thành 1 term nên `.po` vẫn có
  bản vi nhưng en hiện "SL" ⇒ liệt kê msgid chưa dịch KHÔNG đủ, phải grep source.
- msgid chưa dịch phải so với trước Phần V (`git show <mốc>:…/vi_VN.po`), nếu không 463 dòng backend tiếng Anh có từ trước che mất chỗ lùi thật.
- DB đo chép từ DB đã từng quét bằng `wujia_i18n` ⇒ `test_scan_reads_db_and_code_terms` đỏ (đếm cả kết quả quét cũ) — không phải lỗi code.
- Mốc `docs/i18n-baseline/vi_VN.json` cập nhật sau Phần V (54 trang, DB `wujia_vr`).

**J-T4 — ✅ 07/10: bài học cho J-T5 / ★JR**
- Glossary chung khớp theo câu nguồn ở MỌI module sẽ đè bản vi_VN đã chốt riêng (đo: glossary 90, file Thái 162 bản đổi, vd exam
  "Ca thi" → "Khung giờ") ⇒ dòng không ref/ref cũ chỉ điền chỗ trống; J-T5 (dịch máy) cũng phải theo luật này.
- File glossary của Thái đã cũ: 773/1 004 ref `wujia_franchise.*` đã chuyển sang `wujia_franchise_inspection` ⇒ khớp theo ref chỉ
  211; đừng coi "khớp ref" là thước đo độ đúng của file đó.
- Code ghi `.po` để trong module phải tránh `import odoo` ở đầu file (script ngoài nạp theo đường dẫn) và tránh chữ Việt trong
  `print` (quét Phần V tính cả `tools/`).
- `.pot` lấy từ `trans_export(None, …)` (polib) = đúng file `odoo-bin i18n export`; `.po` qua babel ⇒ module chưa sửa xuất ra trùng
  repo (exam 0 dòng, core chỉ thêm 3 bản dịch DB đang có). Module lõi (`web`) xuất ra lệch nhẹ vì ưu tiên "bản đang chạy" ⇒ chỉ commit
  zip của module team.
- `dict(defaultdict)` mất giá trị mặc định ⇒ thống kê phải khởi tạo đủ khoá (test wizard bắt được KeyError).
- Runner mutation đọc log: `wujia_core` ghi log vào `<dir>/<năm>/<tháng>/<ngày>.log`, DB trắng thì ghi đúng `--logfile` ⇒ gom mọi
  file `*.log` và kiểm đường dẫn snapshot có trong log, nếu không mọi đột biến "sống" giả.

**J-T5 — ✅ 07/10: bài học cho ★JR / lần nhập key thật**
- Nhiều dòng cùng câu nguồn (menu + action + view "Terms") ⇒ test "người sửa giữa chừng" phải chọn dòng có câu nguồn duy nhất,
  nếu không hook chạy ở lô khác, dòng đã rời hàng đợi ⇒ đột biến sống.
- Quét lại chỉ làm lộ lỗi "đè bản máy" ở **chuỗi code** (DB không lưu bản dịch code ⇒ quét đọc ra rỗng); nhãn/menu thì DB đã
  chứa đúng bản máy nên không lộ ⇒ test phải kiểm chuỗi code.
- 2 lớp bảo vệ (lọc theo state lúc xếp hàng + đọc lại state lúc ghi) ⇒ test từng lớp riêng (`queued` không chứa dòng `override`).
- `ir.actions.act_window.target` Odoo 19 không còn `inline` ⇒ action Settings dùng `current`.
- Người dịch không phải admin **không đọc được `ir.module.module`** ⇒ wizard có ô Module lỗi quyền (wizard Quét/Xuất từ T1–T4 cũng
  dính, test cũ không bắt vì chỉ thử model value) ⇒ thêm quyền chỉ-đọc cho nhóm Translator.
- `_commit_progress` ngoài cron = commit thật ⇒ chỉ gọi khi context có `cron_id` (TransactionCase cấm commit).
- Portal chọn ngôn ngữ qua `/portal/set-lang/<code>`, không theo `res.users.lang`; Playwright backend không dùng `networkidle` (bus longpoll).
- `scripts/i18n_tool.py` chạy bằng python hệ thống (không có babel) ⇒ không nạp được `po_writer`; hằng `THAI_PREFIXES` để trùng 2 nơi.

**Công cụ (V0)** — quy trình 1 phiên V: `scripts/qa/README.md` §Phần V.
- `vn_hardcode_scan.py --module X --fail-on-any` ⇒ exit 1 khi còn chuỗi (trừ test).
- `vn_to_en_pairs.py draft|check|apply --module X` ⇒ `docs/i18n-pairs/X.csv` (cột `en` lấy sẵn từ glossary nếu VN đã có); `check`
  bắt EN trống, còn dấu tiếng Việt, placeholder/thẻ lệch, 1 EN cho nhiều VN (msgid trùng = 1 bản dịch), đụng glossary; `apply` thay
  QWeb text/attr dịch được + `_()`/`string=`, thêm glossary, in danh sách sửa tay. Chạy thử V0 trên bản copy `wujia_portal_layout`:
  thay 204/205 (1 chuỗi Python nối nhiều literal ⇒ sửa tay), XML/Python hợp lệ, phần còn lại đúng nhóm sửa tay (JS 30 · `t-*` 17 ·
  hằng Python 4 · attr không dịch 3).
- `wj_text_probe.py` ⇒ mọi text node (cả modal ẩn) + attr dịch được + `data-wj-msg-*`, số che `#`; 52 trang (21 route + 4 chi tiết +
  login khách × 1440/390). Mốc vi_VN trên DB `wujia_t1`: `docs/i18n-baseline/vi_VN.json` (2 lần đo 0/52 lệch).
- `docs/i18n-pairs/wujia_portal_layout.csv` đã draft (259 dòng: auto 205 · sửa tay 54) cho V1.

## 6b. J-T5 — Dịch tự động (chủ dự án 05/10: "chọn ngôn ngữ rồi dịch add ào")

Mục tiêu: thêm ngôn ngữ mới = chọn ngôn ngữ → bấm dịch → rà → Áp dụng, không cần dev. Làm sau J-T4 (câu nguồn EN sạch sau Phần V
thì dịch máy mới chuẩn; chuỗi code dịch xong vẫn đi đường xuất `.po` + restart của J-T4).
- **Nhà cung cấp cắm được**: lớp provider chung, DeepL trước; API key + gói (Free/Pro) trong Settings (`ir.config_parameter`,
  chỉ admin). Ngôn ngữ DeepL không hỗ trợ ⇒ báo rõ trên wizard (kiểm danh sách ngôn ngữ DeepL lúc code), chừa chỗ provider khác.
- **Wizard**: chọn ngôn ngữ đích (chưa active ⇒ bật + quét), module, phạm vi (chỉ "Chưa dịch" / cả "Đã dịch" chưa sửa tay);
  ước số ký tự trước khi gửi; chạy nền theo lô (cron + `_trigger`), không treo request.
- **Giữ nguyên định dạng**: `%s`, `%(x)s`, `{x}`, thẻ HTML/QWeb (`tag_handling=xml`), khoảng trắng đầu/cuối; kiểm lại sau dịch,
  lệch placeholder ⇒ không nhận, đánh dấu lỗi.
- **Glossary thuật ngữ** (trà sữa, nhượng quyền, tên sản phẩm) gửi kèm DeepL glossary; không bao giờ đè bản `override`.
- **Trạng thái mới `machine`** (dịch máy, chờ rà): lọc riêng, BA/người bản xứ duyệt ⇒ `synced`/`override` rồi Áp dụng; độ phủ
  tách "dịch máy" với "đã duyệt".
- Câu hỏi chủ dự án/BA: tài khoản DeepL (Free 500k ký tự/tháng hay Pro — kiểm hạn mức lúc code), đồng ý gửi chuỗi giao diện ra
  DeepL, ai rà từng ngôn ngữ.

**Code của Thái** (`wujia_portal_inspection` 178 · `wujia_franchise_inspection` 94 · `wujia_franchise` 7 · `_contract` 3 ·
`_operations` 2): KHÔNG sửa; ★VR gửi Thái danh sách (lọc CSV cột `owner=Thái`).
