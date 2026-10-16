# Cụm F — Nhật ký tiến độ

Mỗi phiên F / FR **bắt buộc** ghi 1 mục ở cuối file này trước khi kết thúc (mới nhất ở dưới),
rồi đánh ✅ ở bảng Trạng thái §2 `docs/next-session-clusters-F.md`. `/wujia-start` đọc mục cuối
để biết phiên kế và việc dở dang. Phiên dừng giữa chừng vẫn ghi, Trạng thái để `◐`.

## Mẫu

```
## <Fx> — <tên phiên> · <dd/mm/yyyy> · <máy: Mac/Linux>
- Kết quả: ✅ xong | ◐ dở (dừng ở bước …) | ⛔ chặn (lý do …)
- Đã làm: <gạch đầu dòng ngắn, theo nghiệp vụ>
- Commit: <hash — message> | chưa commit
- Deploy: chưa | UAT <version> — lệnh cho chủ dự án (compact summary §6, -u đủ module đã bump):
  `nssm stop Odoo; python D:\wujia-tea\odoo19\odoo-bin -c D:\wujia-tea\config\odoo-server.conf -d wujia_tea_19 --addons-path "D:\wujia-tea\custom,D:\wujia-tea\odoo19\addons" -u <mods> --stop-after-init; nssm start Odoo`
- Số đo: <test x/y, B4 x/286, check_layers n vi phạm, wj_measure diff …>
- Lệch plan / quyết định mới: <… hoặc "không">
- Nợ để lại: <… hoặc "không">
- Phiên kế: <Fy> — việc cần biết trước: <…>
```

---

## Nhật ký

## Lập plan — review + plan cụm F · 17/09/2026 · Mac
- Kết quả: ✅ xong
- Đã làm: chốt ADR-027 (4 tầng, L3a portal_base); review source (A/B/C/D); plan + prompt F0–F13, FR-*.
- Commit: `b33723e` — docs: ADR-027 kiến trúc tầng module + plan cụm F chuẩn hoá portal
- Deploy: chưa
- Số đo: xem §1 plan (176/380 nhóm class ở layout, 30 rule đổi dáng, 89 route)
- Lệch plan / quyết định mới: Issue List tạm dừng đến FR-A3; không đụng module anh Thái
- Nợ để lại: mục D (wujia_mobile_core bị nghiệp vụ depend) chờ chủ dự án + anh Thái chốt
- Phiên kế: F0 — cần DB copy giống UAT (có cài inspection) chạy port riêng

## F0 — Công cụ đo + mốc trước chuẩn hoá · 17/09/2026 · Mac
- Kết quả: ✅ xong
- Đã làm: 2 script mới `scripts/qa/css_owner.py` (CSS nào của màn nào đang nằm trong layout; rule module nào
  đè dáng component) + `scripts/qa/check_layers.py` (luật tầng ADR-027, report-only); dựng DB `wujia_f0`
  giống UAT (25/25 phiên bản module, có Khảo sát + mobile_core + MuK, vi_VN/th_TH, 14 seed); chụp mốc
  205 ô × 2 tài khoản; thay Phụ lục A/B bằng số script → `docs/f0-baseline.md`, `docs/f0-baseline/`.
- Commit: chưa commit
- Deploy: chưa (không có gì để deploy — 0 dòng code module)
- Số đo: test 520/520 · B4 286/286 · wj_measure anh 130 ô / em 75 ô, 0 tràn, 0 lỗi JS (3 HIERARCHY
  notification/1 PC + 10 redirect `/vi/portal/inspection` là có sẵn) · css_owner 193 nhóm CSS màn / 41 rule
  đổi dáng · check_layers 4 vi phạm (3 mục D + order_window thiếu portal_base)
- Lệch plan / quyết định mới: chủ dự án chốt dùng số script (A 176→193, B 30→41; F4 duyệt 41 rule). Tên
  script mới KHÔNG tiền tố `wj_` (chủ dự án yêu cầu) ⇒ `css_owner.py`; script cũ giữ tên.
- Nợ để lại: env Mac cần `PyJWT` (đã cài tay, chưa ghi requirements); DB `wujia_tea_19` local cũ + mật khẩu
  demo sai — dùng `wujia_f0` cho mọi phiên F; B4 viết cứng ID chi tiết (`/delivery/3`, `/support/40`…) chỉ
  đúng trên DB đã seed.
- Phiên kế: F1 — bật server `wujia_f0` port 8099 (lệnh ở `docs/f0-baseline.md` §1), suite đối chứng = 520/520;
  so ảnh/số bằng `wj_measure --diff docs/f0-baseline/measure_anh.json after.json`.

## F1 — Controller: vá an toàn + gọi đúng workflow · 17/09/2026 · Mac
- Kết quả: ✅ xong
- Đã làm: gửi hỗ trợ không còn lỗi 500 khi id rác, không nhận danh mục đã lưu trữ, đính kèm chỉ nhận ảnh/PDF ≤5MB ≤6 tệp
  (lỗi thì không tạo ticket); đổi cửa hàng + đổi ngôn ngữ không redirect ra site ngoài (helper `safe_local_path` ở
  `portal_layout/controllers/utils.py`, base import); yêu cầu cập nhật thông tin không lộ lỗi nội bộ; thông báo lỗi trong
  query string được encode (info_request cancel, hồ sơ); phiếu đổi trả gửi từ portal đi qua `action_submit()` ⇒ có dòng
  chatter "Yêu cầu đã được gửi", số ảnh tối thiểu 1 nguồn `MIN_IMAGES_BEFORE_SEND` (vẫn kiểm trước khi tạo).
- Commit: chưa commit
- Deploy: chưa — cần `-u wujia_portal_layout,wujia_portal_base,wujia_portal_support,wujia_portal_info_request,wujia_portal_return`
  (layout 19.0.51.0.1 · base 19.0.7.17.1 · support 19.0.3.21.1 · info_request 19.0.1.10.1 · return 19.0.3.3.1)
- Số đo: test 12 module portal **534/534** (520 đối chứng F0 + 14 mới, tag `wujia_f1`) · mutation **11/11** đỏ (M2b ban đầu
  sống — thêm case cùng host `//evil.com`) · wj_measure diff anh 130 ô / em 75 ô = 0 thay đổi, 0 ô mất record · B4 286/286 ·
  check_layers 1 vi phạm (order_window R4).
- Lệch plan / quyết định mới: helper redirect đặt ở layout (không phải portal_base/utils) vì layout không depend base — chủ
  dự án duyệt; giữ kiểm ≥3 ảnh trước create. Đối chứng dùng run F0 520/520: merge `c80a6e2` (sau mốc `355cae0`) không đụng
  module portal. check_layers 4→1: merge `c80a6e2` của anh Thái đã chuyển mobile ra `wujia_mobile_*` ⇒ **mục D đã xử lý**.
- Nợ để lại: (1) chatter đổi trả chỉ chứng minh bằng test HTTP — `wujia_f0` không có đơn xác nhận ≤10 ngày để gửi tay; (2)
  `attach_files_to_record` kiểm MIME theo header client (return tự sniff), support dùng header; (3) support tạo-rồi-xoá khi
  đính kèm lỗi làm hụt 1 số sequence (cùng khuôn info_request/return); (4) màn support PC không hiện khối lỗi (chỉ mobile có,
  có sẵn); (5) **code anh Thái**: `wujia_franchise/tests/__init__.py` còn import `test_wujia_franchise_mobile` đã xoá ⇒ chạy
  test không `-u` chết import — chỉ báo.
- Cập nhật sau phiên: mục D ghi ✅ ở `next-session-clusters-F.md` §1.D + skill `/wujia-start` (F7 hết bị chặn); báo Thái 2 lệch nhỏ.
- Phiên kế: F2 — CSS 8 màn nhỏ ra khỏi layout; DB `wujia_f0` đã `-u` 5 module F1 (mốc wj_measure không đổi, dùng tiếp baseline F0).

## F2 — CSS 8 màn nhỏ ra khỏi `portal_layout` · 17/09/2026 · Mac
- Kết quả: ✅ xong
- Đã làm: F1 commit+push `aebcd56`. Dời 70 rule (Kiến thức 34 · Lịch sử 21 · Hỗ trợ 14 · `wj-pc-noti-head-actions` 1) từ
  `_components.css`/`_pc_components.css` lên đầu file CSS module (module đã có file trong `web.assets_frontend`, nạp sau layout);
  dọn comment mồ côi; 4 guard test đọc thẳng `_components.css` trỏ sang file module (d3 DEAD_CSS, d4, d5). Bộ công cụ
  `scripts/qa/css_move/` (plan/apply/semdiff/cstyle/cdiff).
- Commit: `dab6f4c` (đã push — ghi chú sửa ở phiên F3)
- Deploy: chưa — `-u wujia_portal_layout,wujia_portal_knowledge,wujia_portal_purchase_history,wujia_portal_support,wujia_portal_notification`
  (layout 19.0.51.0.2 · knowledge 19.0.3.14.1 · purchase_history 19.0.3.12.1 · support 19.0.3.21.2 · notification 19.0.2.14.1; `?v=1294`)
- Số đo: semdiff 309/309 khớp · cstyle full computed style + ép :hover/:active/:focus 2550 phần tử × 28 lượt (2 tài khoản × 390/1440)
  = 0 khác · wj_measure anh 0 lệch, em 2 route lệch = dữ liệu (đối chứng CSS HEAD y hệt) · 0 ô mất record · ảnh 390/1440 chỉ lệch
  dữ liệu (lượt xem, nhãn dịch) · B4 286/286 · suite 12 module 534/534 · css_owner 380→335 nhóm.
- Lệch plan / quyết định mới: (1) KHÔNG tách class khỏi `:is()` ở `_interaction.css` — đặc hiệu :is() = đối số mạnh nhất (0,4,0),
  tách ra tụt ⇒ hover hàng compact-row đổi `primary-soft` → rgba .04; chủ dự án đồng ý để F4. ⇒ debt/exam/return/delivery (chỉ có
  mặt trong :is()) = 0 rule dời. (2) `.wujia-mknow-article > .wj-card-header{margin-top:16px}` giữ layout: đang thua
  `.wj-card-header--any.wj-card-header--compact{margin:0 0 8px}` (sau, cùng 0,2,0), dời xuống là thắng ⇒ card +16px (cstyle bắt).
  (3) `wujia-msheet-open` (JS bottom sheet layout) + `wj-filter-select` (FilterBar layout) là component — css_owner gán nhầm.
  (4) Luật `auto_install: True` cho module ghép thuần (Thái hỏi) — ghi skill mục "chưa ghi ADR".
- Nợ để lại: 22 nhóm mang tên 8 màn còn ở layout, đều giải trình (18 trong :is(), 1 rule chết, 2 component, +inspection) → F4.
  Bẫy môi trường: bundle cache cũ sau sửa CSS ⇒ xoá `ir_attachment` `/web/assets/%` + restart; deploy UAT `-u` + restart là đủ.
  Mốc F0 em.hcm `/portal` + `/portal/order` đã trôi — F3 lấy mốc mới đầu phiên.
- Phiên kế: F3 — prompt đã viết lại ở `next-session-clusters-F.md` §3 (quy trình cstyle đo cascade bắt buộc).

## F3 — CSS Đặt hàng + Home ra khỏi `portal_layout` · 17/09/2026 · Mac
- Kết quả: ✅ xong
- Đã làm: dời 160 rule từ `_components.css` lên đầu file CSS module — Đặt hàng 111 (+ `@keyframes wujia-msubmit-spin`)
  → `wujia_portal_sale/static/src/css/portal_order.css`, Home 49 → `wujia_portal_base/static/src/css/portal_dashboard.css`;
  gỡ 3 `@media {}` rỗng + comment mồ côi do chính lượt dời để lại (2 `@media` rỗng có từ trước giữ nguyên). 5 chỗ
  `test_d4_surface_card.py` đọc CSS trỏ sang file module. Bộ `scripts/qa/css_move/` nhận cấu hình `CSSMOVE_CFG` (TARGET/KEEP/
  MODCSS/ACC/PREF/SETUP), `cstyle` chịu được trang long-polling (Đặt hàng không bao giờ `networkidle`), `cdiff` có
  `CDIFF_IGNORE` cho hình học chạy theo đồng hồ (thanh tiến độ khung giờ).
- Commit: chưa commit
- Deploy: chưa — `-u wujia_portal_layout,wujia_portal_sale,wujia_portal_base`
  (layout 19.0.51.0.3 · sale 19.0.4.17.1 · base 19.0.7.17.2; `_components.css?v=1295`)
- Số đo: semdiff 711/711 khớp · cstyle 7030 phần tử × 20 lượt (2 tài khoản × 390/1440 × `/portal`, `/portal/order`, giỏ có 2 dòng,
  `/portal/order/submitted/<id>`, `/portal/order/rejected`) + ép hover/active/focus = **0 khác** (2 lượt sau) · wj_measure
  anh 130 ô 0 lệch, em 1 ô `/portal`@360 −25 = đồng hồ (cùng code đo lại 3 lần ra 2772 = mốc) · 0 mất record · 0 tràn · 0 lỗi JS ·
  ảnh chỉ lệch đồng hồ khung giờ/shimmer logo/thanh tải · B4 286/286 · suite 12 module 534/534 · css_owner nhóm 1 màn 149→46
  (sale 78→7, base 49→17).
- Lệch plan / quyết định mới: GIỮ ở layout, có giải trình — `wj-pc-acct-*` + `wujia-maccount-*` (view layout profile/đổi mật khẩu
  dùng chung), `wj-empty-state-body` (biến thể `--row` của EmptyState), `wujia-content-card-empty` (họ content-card),
  `.content-wrapper > .wujia-mhome` (`_wujia_theme.css`), 10 nhóm chỉ còn trong `:is()` `_interaction.css` → F4. Mốc wj_measure
  lấy mới đầu phiên (F0 đã trôi ở `/portal` + `/portal/order` trên code chưa sửa). Luồng giỏ đo bằng dựng giỏ qua
  `/portal/order/cart/add` + trang kết quả của đơn có sẵn — KHÔNG gửi đơn thật để giữ dữ liệu mốc.
- Nợ để lại: comment trong module mới chỉ ghi nguồn dời (comment nghiệp vụ gốc không đi theo rule — như F2); chưa chạy
  mutation cho 5 guard D4 đã trỏ lại; log test do `wujia_core` chuyển vào `<logfile dir>/<năm>/<tháng>/`.
- Phiên kế: F4 — duyệt 41 rule đổi dáng + danh sách `:is()` (dừng giữa phiên xin duyệt).


## F4 — Duyệt rule module viết đè component chung · 17/09/2026 · Mac
- Kết quả: ✅ xong
- Đã làm: bước 1 lập `docs/f4-override-review.md` (44 rule, tắt từng rule trong trình duyệt + 30 ảnh `docs/f4-img/`), chủ dự
  án duyệt: (b) theo đề xuất không cần báo BA · hover một màu primary-soft · dọn toàn bộ `:is()` · eyebrow. Bước 2: xoá 13 rule
  chết + rule chết mknow + 14 rule lệch về chuẩn; biến thể layout mới `wujia-badge--sm`, `wj-pc-badge--sm`,
  `wj-card-header--eyebrow`; sửa component (tiêu đề trang PC 800 thật sự áp, con trỏ select lọc, màu chữ hàng `<a>`
  detail-card); Công nợ "THÔNG TIN CHUYỂN KHOẢN" SectionHeader → CardHeader eyebrow; `_interaction.css` liệt kê theo
  component + class đánh dấu `wj-state-surface` ở XML (không còn tên màn), nhóm Khảo sát tách rule riêng, gạch chân dùng
  `wj-richtext`; bỏ hover rgba .04 của compact-row. 8 rule giữ có comment `F4(c)`.
- Commit: xem git log — refactor(F4)
- Deploy: chưa — `-u wujia_portal_layout,wujia_portal_base,wujia_portal_debt,wujia_portal_delivery,wujia_portal_exam,
  wujia_portal_knowledge,wujia_portal_notification,wujia_portal_purchase_history,wujia_portal_report,wujia_portal_return,
  wujia_portal_sale,wujia_portal_support` (layout 19.0.51.0.4 · `?v=` components 1296 / pc_components 1295 / interaction 1293;
  11 module còn lại +1 patch)
- Số đo: css_owner --overrides đổi dáng **44 → 9** (cả 9 là loại giữ có ghi chú) · cstyle mốc 2 lượt ổn định (A: 1 dòng
  Kiến thức lệch 0.36px đồng hồ; B: 0) → sau sửa chỉ khác đúng bảng §8 review · hover/active ép trên MỌI phần tử ứng viên
  (script mới `scratchpad hovall.py`): 0 mất/thừa, chỉ `wj-debt-inv` + `wujia-mexam-rrow` (div không bấm được) mất hover ·
  B4 286/286 · suite 12 module **540/540** (có 6 test mới `wujia_f4`; số 537 ghi ở phiên F4 là sai, FR-B đếm lại: 534 trước F4 + 6 = 540).
- Lệch plan / quyết định mới: **exam727 (a) → (c) nợ FR-B** — Vuexy `table th{16px !important}` thắng cỡ 14 của component ở
  mọi bảng PC 8 màn (kể cả Khảo sát); sửa ở component = đổi 8 màn, chưa duyệt. Sửa component tiêu đề trang PC làm **Khảo
  sát PC** tiêu đề 700→800 (đúng số component). Hàng `<a>` Đổi trả + thẻ Thi mobile chữ thừa kế #243742→#111827. Nhãn chuyển
  khoản cao +2.5px (thẻ vẫn 150px). cstyle khoá phần tử theo class ⇒ thêm class marker phải chuẩn hoá khoá khi so (cd2.py).
  7 guard cũ (C8/D3/D5) sửa theo rule/call site đã xoá.
- Nợ để lại (FR-B): (1) cỡ đầu bảng PC 16 vs 14; (2) bề mặt không bấm được vẫn có hover qua marker để giữ 0 khác —
  `wujia-mdash-card` ×33 (card thông tin), hàng `div.wujia-mdash-row` Home/Hỗ trợ/Thông tin cửa hàng, skeleton giao hàng,
  `div.wujia-mhome-kpi`.
- Phiên kế: ★FR-B — review toàn khối B (F2+F3+F4), prompt §3 "Prompt phiên review ★".

## ★FR-B — Review toàn khối B (F2+F3+F4) · 18/09/2026 · Mac
- Kết quả: ✅ xong — khối B đạt (0 lỗi mới), **và sửa luôn 2 khoản nợ F4** theo chốt của chủ dự án.
- Đã làm:
  - Đo **đi suốt F0 → `52c7650`** lần đầu; xem **205 cặp ảnh** trước/sau bằng mắt.
  - Chứng minh độc lập "dời CSS là phép giữ nguyên": nguyên tử CSS 282 file, F2+F3 **121902 → 121902, 0/0**.
  - **Trả nợ F3**: mutation 5 guard D4 → **5/5 đỏ**.
  - **Nợ (a)** — tìm ra gốc rễ khác chẩn đoán của F4: không phải Vuexy mà là `table th{16px!important}`
    trong `style.css`, **có từ commit đầu dự án**. Gỡ hẳn luật đó; Đặt hàng 13→14; bảng thô Đổi trả cho
    class riêng `wj-return-ptable` + 14px; **xoá 4 rule `!important` của F4(c)** ở màn Thi (chỉ tồn tại để
    chống luật chung). Kết quả **16/17 bảng = 14px** (bảng kết quả Thi vốn 13px, cố ý).
  - **Nợ (b)** — rút luật từ template `wj_surface_card` (có `sc_href` ⇒ `<a>`; không ⇒ `<div>` thuần)
    rồi **gỡ marker ở 40 chỗ** (27 qua `sc_class` + 13 trên `<div>`), 0 dòng CSS bị đụng.
  - **Nợ (c)** — ép hiện trạng thái rỗng Công nợ bằng `?q=zzzkhongcogi`: sau F4 **khớp chuẩn component,
    không phải lỗi**; chỉ cần BA biết khi retest.
  - Thêm **3 guard mới** + mutation từng cái (3/3 đỏ, hoàn tác xanh): cấm marker ở `sc_class`, cấm marker
    trên thẻ không bấm được, cấm luật quét theo thẻ cho đầu bảng.
  - Dọn 3 việc nhỏ: sửa 537→540 trong doc F4 · bỏ số dòng đã lệch ở 12 comment "dời từ" · xoá 2 `@media`
    rỗng + 5 comment mồ côi (chứng minh **0 nguyên tử CSS thay đổi**).
- Commit: **chưa commit** (không được yêu cầu).
- Deploy: chưa — `-u wujia_portal_layout,wujia_portal_base,wujia_portal_sale,wujia_portal_return,
  wujia_portal_delivery,wujia_portal_support,wujia_portal_exam,wujia_portal_notification,
  wujia_portal_purchase_history,wujia_portal_knowledge` (layout `19.0.51.0.7`, `?v=` `_components.css`
  **1297** · `style.css` **1300**).
- Số đo: suite **543/543** (540 + 3 guard mới), 0 failed 0 error · B4 **286/286** · `css_owner
  --layout-domain` 20 nhóm cả 20 trong danh sách giữ · `--overrides` 9 rule cả 9 có `F4(c)` ·
  `check_layers` 1 vi phạm đã biết (order_window, F7) · hover: **0 chỗ không bấm được còn marker**,
  110 chỗ mất hover **100% là `<div>`**, 0 chỗ bấm được bị mất, 0 chỗ thừa · đầu bảng PC **16/17 = 14px** ·
  `wj_measure` vs F0: 8 ô lệch, **cả 8 là hệ quả của sửa 14px**, chứng minh bằng A/B tiêm lại luật cũ
  (Hỗ trợ @992 hàng 89→72px × 20 hàng = −340px; Yêu cầu thông tin −51px = 3 hàng × 17px) · bump
  version/`?v=` 0 sót · 0 selector đụng Khảo sát ngoài ca đã duyệt.
- Lệch plan / quyết định mới:
  - **Bắt 3 con số sai trong nhật ký F4**: suite 537 → **540**; nợ (a) "8 màn" → **14/17 bảng**;
    nợ (b) "×33" → **40 chỗ trong XML** (`wujia-mhome-kpi` phần lớn là `<a>` bấm được).
  - Chủ dự án chốt (a) = **14px theo chuẩn thiết kế**, (b) = **gỡ hết**.
  - 2 guard cũ phải sửa theo: `test_screen_surfaces_carry_the_marker` 4→3 (ô KPI Công nợ là `<div>`);
    `test_d3_card_header.test_store_name_became_subtitle...` bỏ chuỗi marker khỏi xpath.
- Nợ để lại:
  - **Bổ sung `/portal/franchise-information` (và rà toàn bộ `@http.route`) vào danh sách route đo** —
    màn này KHÔNG có trong mốc F0 nên 4 chỗ hover sai lọt qua cả F4 lẫn vòng soi tay của FR-B.
  - Mỗi màn cần **1 route ép ra trạng thái rỗng** trong danh sách đo (bài học từ nợ (c)).
  - Bảng kết quả Thi giữ 13px (cố ý) — BA xác nhận khi retest nếu muốn đồng bộ 14.
- Phiên kế: **F5** — khung thuần (menu, test, redirect). Cần biết trước: (1) rà danh sách route đo
  trước khi đo gì; (2) phiên nào đổi đường dẫn/nội dung guard đọc CSS-XML thì **cùng phiên** chạy
  mutation; (3) zsh dùng `${=R}` tách route; (4) sửa file bằng script Python phải mở `newline=''`.

---

## F5a — Khung `portal_layout` thuần: menu về module + redirect + vá điểm mù mốc đo (18/09/2026)

- Phạm vi: mục 0 (mốc đo) + mục 1 (menu) + mục 3 (redirect) của phiên F5. **Mục 2 (dời 94 test
  cross-module / 215 assert của layout về module) tách sang F5b** — chốt với chủ dự án đầu phiên.
- Làm được:
  - **Vá điểm mù mốc đo trước khi sửa dòng code nào**: kiểm kê **97 `@http.route`/13 module** bằng máy
    (`docs/f5-route-inventory.md`), mốc F0 chỉ đo 30 route → mốc F5a đo **46 (anh.owner) + 28 (em.hcm)**,
    thêm `/portal/franchise-information` + **11 route ép trạng thái rỗng** (đọc controller tìm tham số
    chắc ra rỗng, không đoán `?q=`). Mốc mới lộ ngay **4 lỗi HIERARCHY cũ chỉ thấy ở trạng thái rỗng**
    + 1 ở `/portal/exam/register` (tồn tại từ trước F5a, ghi nợ, không sửa trong phiên này).
  - **Công cụ mới `scripts/qa/nav_dump.py`**: đổ ra danh sách CÓ THỨ TỰ của mọi link điều hướng
    (sidebar PC · bottom-nav · sheet "Thêm" · header mobile · navbar PC) theo route × khổ × tài khoản —
    thứ `wj_measure` không đo được. Đây là bằng chứng chính của mục 1.
  - **Menu về đúng module sở hữu route**: xoá `pc_sidenav.xml` (`layout_sidenav_figma` priority 99
    `position="replace"` — 10 link cứng); khung còn `<ul>` + 2 tiêu đề nhóm có `id` làm neo + mục
    Tài khoản (route của chính khung). 9 module khai mục sidebar, 4 tab + 7 dòng sheet, 2 mục header
    mobile, 2 mục PC (navbar dropdown + shell Tài khoản) — tổng **24 mục điều hướng đổi chủ**.
  - **Redirect legacy** 3 route v14 về đúng module đích (301 giữ nguyên); `redirects.py` của khung xoá.
  - **Guard mới + mutation**: `check_layers.py` thêm **R6 "khung không biết route Wujia"**;
    `test_f5_frame_routes` (arch trong DB), `test_f5_menu_ownership` (danh sách vàng 11 mục + quyền sở
    hữu qua `ir.model.data` + active theo route + nút "Thêm"), 9 test module, 3 test 301 → **+28 test**.
- Commit: **chưa commit** (không được yêu cầu). Deploy: chưa.
- Số đo: `nav_dump` **0 lệch** về href/nhãn/icon/active/thứ tự (chỉ thêm thuộc tính `id` cho 2 tiêu đề
  nhóm làm neo) · `wj_measure` **0 ô lệch, 0 ô mất record** · ảnh **136/148 giống hệt**, 12 ảnh còn lại
  là đồng hồ đếm ngược / lượt xem / pha hoạt hình biểu đồ · suite **571/571** (543 + 28), 0 failed 0 error ·
  B4 **286/286** · `check_layers` R6 **0**, vi phạm cũ vẫn đúng 1 (order_window, F7) · mutation **5/5 đỏ,
  hoàn tác xanh** · `ir.ui.view` mồ côi sau `-u`: **0** · bump version **13 module**, 0 sót (không sửa CSS
  ⇒ không đụng `?v=`). Chi tiết: `docs/f5a-acceptance-matrix.md`.
- Lệch plan / quyết định mới:
  - **Đính chính plan §1.A3**: `pc_sidenav_inspection` của anh Thái có priority **101** > 99 nên mục
    "Khảo sát" VẪN hiện — sidebar PC thật đang có **11 mục**, không phải 10. Câu hỏi "cho hiện mục Khảo
    sát?" hoá ra vô nghĩa (nó đang hiện sẵn) ⇒ nghiệm thu chặt hơn: diff = 0 kể cả mục đó.
  - **`<li>` phải nằm trong ARCH, không sinh lúc render**: bản đầu dùng component sinh cả `<li>` bằng
    `t-att-id` ⇒ neo `//li[@id='nav_item_exam']` của anh Thái không tìm thấy gì, mọi trang 500. Khuôn
    cuối: module viết thẳng `<li id=... t-attf-class=...>`, thân mục gọi component của khung.
  - **Nút "Thêm" phải dùng CỜ, không dùng danh sách tiền tố**: tab Trang chủ khớp tuyệt đối `/portal`,
    nếu góp `/portal` vào danh sách tiền tố thì mọi route con đều "khớp" ⇒ "Thêm" không bao giờ sáng.
  - **Xoá view khỏi data file là chưa đủ**: Odoo dọn record mồ côi ở CUỐI lượt nạp nên 6 view chết vẫn
    bị validate giữa chừng và làm **gãy `-u`**. Phải xoá bằng `migrations/<version>/pre-*.py` (5 module).
  - Sửa nhỏ kèm đo lại: `pc_preview.xml` trỏ form về route không tồn tại `/portal/pc-preview`
    (route thật `/portal/_pc-preview`).
  - Không đụng 1 dòng code anh Thái; 2 inherit của anh (sidebar Khảo sát, dòng sheet Khảo sát) còn
    nguyên vị trí, chứng minh bằng `nav_dump`.
- Nợ để lại:
  - **F5b**: dời test cross-module của `wujia_portal_layout` về module sở hữu màn; guard nhiều module
    về `wujia_portal_base`; tổng số assert không được giảm.
  - **4 lỗi HIERARCHY ở trạng thái rỗng + 1 ở `/portal/exam/register`** (có từ trước F5a) — vá ở phiên
    dọn màn tương ứng hoặc gộp vào cụm EmptyState.
  - Bẫy đã cắn, ghi lại cho phiên sau: (1) **không `git checkout <file>`** để hoàn tác mutation khi cây
    còn thay đổi chưa commit — mất sạch sửa trong file đó; (2) khôi phục `.py` bằng `mv/cp` giữ `mtime`
    ⇒ Python dùng lại `__pycache__` của bản đã phá, phải `rm -rf __pycache__` trước khi chạy lại.
- Phiên kế: **F5b** — dời test cross-module (prompt ở `docs/next-session-clusters-F.md` §3).

---

## F5b — Test của khung về đúng chủ: `portal_layout` hết biết màn nghiệp vụ (18/09/2026)

- Phạm vi: mục 2 của phiên F5 (tách ra từ F5a). **Không tính năng mới, không đổi 1 pixel.**
- Làm được:
  - **Kiểm kê bằng máy trước khi dời** — công cụ mới `scripts/qa/test_ownership.py` (AST): mỗi hàm test
    → file · class · số assert · module bị đọc · đọc DB hay đọc đĩa. Kết quả: khung có **329 test /
    711 assert**, trong đó **236 test / 517 assert** là cross-module (94 đọc thẳng trong thân hàm +
    142 thừa kế hằng cấp class như `CALL_SITES`). Bảng đầy đủ: `docs/f5b-test-inventory.md`.
  - **Phân loại từng TEST (không phải từng class)** thành a/b/c + nhóm bàn giao, rồi dời thật:
    **a** 40 test ở lại khung nhưng đổi sang **fixture dựng trong chính tests của khung** ·
    **b** 24 test về module sở hữu màn (Công nợ, Đăng ký thi, Home) ·
    **c** 155 test quét-nhiều-module về `wujia_portal_base` (L3a), **giữ nguyên một hàm, không cắt thành 12** ·
    **BG** 17 test của màn Khảo sát gom vào `portal_base/tests/test_handover_inspection.py` để nhóm Khảo
    sát dời về — không ghi một dòng nào vào code anh Thái (chủ dự án chốt: *"cái nào của Khảo sát thì bên
    Khảo sát tự sửa"*).
  - **Helper dùng chung `portal_base/tests/css_probe.py`** thay vì chép ba bản cho debt/exam.
  - **Khung nay cài được một mình**: `wujia_portal_layout` thêm `depends` thiếu `http_routing`.
- Commit: F5a + F5b (tách 2 commit), push `main`. Deploy UAT: **không** (chưa được yêu cầu).
- Số đo (chi tiết `docs/f5b-acceptance-matrix.md`):
  - **Phép đo quyết định — DB `wujia_f5b` tạo mới, CHỈ cài `wujia_portal_layout`: 0 failed, 0 error /
    129 test.** Trước phiên này con số đó là *không chạy nổi*.
  - Suite 15 module portal trên `wujia_f0` kèm `-u`: **572/572**, 0 failed 0 error (F5a 571 + 1).
  - Assert **không giảm**: toàn hệ 1548 → **1549** (khung 711 → 261; 15 file mới giữ 451).
    Khung: **cross-module 236 → 0**.
  - B4 **286/286** · `check_layers` R1–R5 đúng 1 vi phạm cũ (`order_window`, chờ F7), **R6 = 0**.
  - `wj_measure --diff` **0 lệch, 0 ô mất record**; `nav_dump --diff` chỉ còn dư âm F5a (thuộc tính `id`
    của 2 `<li>` tiêu đề menu), href/nhãn/thứ tự/active/badge khớp tuyệt đối.
  - Mutation **5/5** đỏ khi phá, xanh khi hoàn tác. Bump version 4 module, 0 sót.
- Lệch plan / quyết định mới:
  - **Số cross thật là 236, không phải 94**: plan đếm hẹp (chỉ thân hàm). Một test nằm trong class có
    `CALL_SITES` liệt kê 12 module cũng là cross. Đếm lại bằng máy mới ra đúng.
  - **Công cụ đếm phải bỏ docstring**: sau khi dời, khung vẫn báo 115 test cross — vì câu *"đã dời sang
    `wujia_portal_base`"* trong mô tả bị tính là phụ thuộc. Đếm cả docstring là tự lừa mình.
  - **Phép đo quyết định bắt được 2 lỗi thật** mà suite 572 test trên `wujia_f0` không bao giờ thấy:
    (1) khung inherit `http_routing.404` mà không khai `http_routing` — trên DB đủ module nó có sẵn nhờ
    module khác; (2) `test_c10_lang` giả định `vi_VN` bật sẵn ⇒ nay tự `_activate_lang` trong `setUp`.
  - **Test khung không được import `portal_base`**: bản phân trang cũ mượn `build_pager` — thay bằng
    fixture dict viết trong chính tests của khung, và mutation M5 (phá `aria-label` của template) chứng
    minh fixture thật sự render template chứ không assert vào không khí.
  - Guard màn Khảo sát **không mutation** (phải sửa CSS của anh Thái mới phá được — luật cụm F cấm);
    thay bằng kiểm dương 14/14 đường dẫn tĩnh trỏ tới file có thật.
- Nợ để lại:
  - `portal_base/tests/test_handover_inspection.py` — **anh Thái dời trọn file về
    `wujia_portal_inspection/tests/`**, nội dung assert giữ nguyên.
  - 4 lỗi HIERARCHY ở trạng thái rỗng + 1 ở `/portal/exam/register` (từ trước F5a) — vẫn còn.
  - Dư âm F5a trong mốc đo: 2 thuộc tính `id` trên tiêu đề menu ⇒ nên chụp lại baseline ở phiên FR-A3.
- Phiên kế: **FR-A3** — review cổng khối A/B, kết luận có mở lại Issue List hay không.

## ★FR-A3 — Review cổng cụm F (F0→F5b): mở lại Issue List (18/09/2026 · Mac)

- Mục tiêu: lần ĐẦU đo đi suốt **mốc F0 → HEAD `33240c0`** (FR-B mới đo tới `52c7650`; F5a/F5b đo bằng
  mốc F5 riêng) rồi kết luận có mở lại Issue List hay không. Không làm tính năng.
- Chốt đầu phiên của chủ dự án: commit + push, **KHÔNG deploy UAT** · sửa lỗi HIERARCHY trạng thái rỗng
  nếu < 30 dòng · độ phủ đo **đầy đủ** (bộ F0 26+15 route × 5 khổ + bộ F5 46+28 route × 2 khổ + ảnh).
- **Kết luận: cổng ĐẠT — mở lại Issue List**, thứ tự E4b → E4c → E5 → E6 → E7 → E8.
- Làm được:
  - **25 phép đo Pass** (`docs/f-review-A3.md` §2). Suite **574/574** · phép đo quyết định (DB trắng chỉ
    cài khung) **129/129** · B4 **286/286** · `wj_measure` mốc F5 → HEAD **0 lệch** · ảnh 148 cặp **0
    khác biệt chưa duyệt** · `nav_dump` chỉ còn dư âm `id` (184+112, **100%**) và **đã chụp lại mốc**.
  - **Mutation xuyên khối 10/10** — trả nợ mutation cho F1 (3 guard an toàn, chưa phá lại từ 17/09),
    FR-B (2), F5a (2), F5b (1) + 2 guard mới của phiên.
  - **Bắt được 2 lỗi TẦNG thật, có từ trước cụm F, chưa công cụ nào thấy**: `portal_base` (L3a) gọi
    `_is_within_order_window`/`_user_now_hours` của `portal_order_window` (L3b) ⇒ Home **500** khi cài
    riêng; `portal_layout` (khung) gọi `_get_accessible_franchise_ids` của `wujia_franchise` (nghiệp vụ)
    ⇒ ACL ảnh **500**. Vá bằng **guard `hasattr`/`getattr`** (không thêm depend — thêm là vi phạm R2/R5
    thật), + 2 test giả lập module tắt bằng descriptor ném `AttributeError`.
  - **`check_layers` có luật R7 mới**: quét AST tìm lời gọi method của module không depend mà không có
    guard. Đây là vá cho chỗ mù của chính công cụ (R1–R5 chỉ đọc manifest). Chạy 2,5s.
  - **5/6 "lỗi" HIERARCHY trạng thái rỗng là thước đo báo nhầm**: khối rỗng căn giữa (icon + tiêu đề) và
    tiêu đề bản ghi ở trang chi tiết không phải "nhãn phụ". Chứng minh bằng ảnh, ghi vào bảng đã duyệt,
    **không sửa pixel**. Chỉ 1 lỗi thật: `wj-exam-pc-sectitle--sm` 18 → **16px** (áp chốt 04/09 "khối con
    trong card = 16px" — 3 anh em của nó đã 16px từ F4, sót đúng chỗ này).
  - Mốc mới `docs/fra3-baseline/` (4 measure + 2 nav + 4 route + check_layers) — sạch, hết dư âm F5a.
- Lệch số so với nhật ký (đếm lại bằng máy — bài học #2 của FR-B):

  | Nhật ký | Máy |
  |---|---|
  | `check_layers` 1 vi phạm | **2** (thêm R3 chéo kênh `wujia_mobile_portal_info_request`) |
  | css_owner nhóm 1 màn ở layout: 20 | **26** (F5a dời markup menu ⇒ đổi quy kết, KHÔNG có CSS mới) |
  | css_owner rule đổi dáng: 9 | **8** (FR-B đã xoá 1) |
  | EmptyState "~124 chỗ viết tay" | **92 viết tay / 124 đã dùng component** |

- Nợ để lại:
  - **`wujia_portal_base` không tự test được một mình** (41 failed / 81 error trên DB chỉ có base): 6 file
    test quét cả cổng, 2 trong số đó có **từ trước cụm F** ⇒ đúng thiết kế, không phải F5b gây ra. Cần
    gắn nhãn `portal_suite` hoặc tự bỏ qua khi module chủ chưa cài ⇒ **F6**, > 30 dòng.
  - **148 dòng comment nhắc mã phiên** trong 14 module portal (chủ dự án đã nhắc 2 lần về việc hạn chế
    comment). Đề xuất luật: *comment nói VÌ SAO, không nói PHIÊN NÀO*.
  - Cụm **EmptyState**: 92 chỗ viết tay, 6 họ class, **3 cỡ tiêu đề** (28/20/18) — đã soạn 3 câu hỏi
    chốt cho BA trong `docs/f-review-A3.md` §7.
  - Báo anh Thái 8 mục (§8): test `__init__` import file đã xoá · file bàn giao màn Khảo sát · R3 chéo
    kênh · `auto_install` · **R7: `_wj_ensure_contract` 2 chỗ** · view `res.config.settings` cũ gây
    `ParseError` khi deploy · `wujia_metabase_connector` chưa phân tầng · `origin/thai` 2 commit chưa merge.
- Bài học:
  - **Chỗ mù của công cụ là chỗ lỗi trốn.** 2 lỗi 500 sống qua 7 phiên vì `check_layers` chỉ đọc manifest.
  - **Cài module một mình** là phép đo rẻ nhất mà mạnh nhất — 2 lỗi tầng + 1 khoản nợ đều từ 1 lệnh.
  - **Máy báo lỗi ≠ có lỗi**: tin 5 ô HIERARCHY mà sửa là phá một thiết kế Figma đã duyệt.
  - **Tên module trong chuỗi thông báo lỗi cũng bị tính là phụ thuộc chéo** — `test_ownership` bắt ngay;
    đưa tên module vào docstring, đừng đưa vào code.
- Phiên kế: **E4b** — phủ hết call site FilterBar (`UI-FILTER-001`, E4a đã làm nền ở `12750a2`).

## Nhịp dọc mobile — nén khoảng cách + gom về một token · 18/09/2026 · Mac
- Kết quả: ◐ dở — **phần chuẩn hoá xong**, **chỉ tiêu −30…35% KHÔNG đạt (−8%)**, dừng theo chốt của
  chủ dự án (hết giờ) để làm tiếp ở phiên sau.
- Ngoài lộ trình cụm F: việc BA/chủ dự án giao trực tiếp từ ảnh chụp Home mobile ("khoảng trống giữa
  các thành phần quá lớn"). Không đụng Issue List.
- Đã làm:
  - Nhịp dọc mobile nay khai ở **đúng một chỗ** (khối `:root` trong `@media (max-width:991.98px)` của
    `_variables.css`): gap 14→**8**, mép trên 16→**10**, tiêu đề nhóm 16/8→**6/4** qua token mới
    `--wujia-m-sechead-mt/mb`.
  - Kéo **8 trang lạc chuẩn** về một rule chung: Home (gap 18) · Công nợ (12) · Báo cáo (12) ·
    Đặt hàng/Giỏ/Lịch sử (dàn con bằng `margin-bottom` 10/14/16 — gỡ 5 margin).
  - **Gỡ 3 rule bù trừ âm** cho PageHeader (−6 mpage, −4 công nợ, −4 báo cáo): gap chung nay đúng 8px
    của CMP-PG-001 nên chúng hết lý do tồn tại. Đo lại: **7/7 route ra đúng 8px**.
  - Guard mới `wujia_portal_base/tests/test_mobile_rhythm.py` (5 test) + sửa 1 guard D4d đã lỗi thời.
- Commit: `<điền sau khi commit>`
- Deploy: chưa (theo chốt: commit + push `main`, KHÔNG deploy UAT)
- Số đo: Home @390 **2613→2405 (−8,0%)** · @360 −7,9% · khoảng trắng trước tiêu đề nhóm **34→14px**
  · khối thấy trọn màn đầu 3→**4**, dòng 1→**2** (Thông báo 4→**5**) · **0 ô mất record** ·
  PC 1440/1024/992 **0 ô lệch** · 0 tràn ngang · 0 lỗi JS · suite **579/579** (574+5 mới) ·
  mutation **5/5 đỏ** · `check_layers` 2 vi phạm R7 **có sẵn** (của anh Thái, FR-A3 đã ghi).
- Lệch plan / quyết định mới:
  - **Chỉ tiêu −30…35% là bất khả thi bằng khoảng trắng** — chứng minh bằng thực nghiệm tiêm CSS:
    ép cả đệm thẻ, gap mục, `min-height` dòng xuống 48 (phá chuẩn D5) cũng chỉ ra **−12,9%**.
    Gốc: 8 dòng danh sách trên Home cao tổng **698px**, từng dòng 66/67/86/94/113 ⇒ **cao vì 2–3 dòng
    CHỮ, không vì đệm**. Trang dài do nội dung.
  - Rule chung **chỉ cấp nhịp, KHÔNG cấp padding**: trang dựng trong `.content-wrapper` đã được wrapper
    cấp pad-top (gom vào là cộng dồn), Home còn mất lề ngang vì `.wujia-home-wrapper` cố ý bỏ pad ngang.
  - Lệch Figma RESP-MOB-SHELL-003 — chủ dự án chốt "BA kêu mà, Figma tương đối thôi", chỉ cần 1 dòng FYI.
- Nợ để lại:
  - **Chưa gửi BA dòng FYI** về lệch Figma (gap 14→8, top 16→10, tiêu đề nhóm 16/8→6/4).
  - **1 error trên DB trắng chỉ cài khung** (`test_fra3_layer_guard`, 130 test) — đã chạy đối chứng
    `git stash`: **có sẵn từ FR-A3**, không phải phiên này. Cần xử ở F6 cùng nợ `portal_base`.
  - Hai cần gạt để thật sự tới −30%, **chưa làm, chờ chốt** (chi tiết + số ước tính ở
    `docs/mobile-rhythm-acceptance.md` §4):
    **G1** dòng danh sách 2–3 dòng → 1 dòng (−250…350px Home, ăn theo mọi màn danh sách, lệch Figma nhiều);
    **G2** khung cố định đang chiếm **235px = 26% màn hình** (header 104 + dải cửa hàng 48 + thanh dưới 83)
    → hạ header 104→72 và/hoặc ẩn header khi cuộn, lấy lại 30–50px MỖI MÀN cho mọi trang.
    **G3** cỡ chữ/line-height (rẻ nhưng chạm accessibility).
- **VIỆC CHỐT CHO PHIÊN SAU (chủ dự án giao cuối phiên 18/09, kèm ảnh header mobile):**
  **G2 — hạ chiều cao thanh điều hướng trên cùng của mobile.** Nguyên văn: *"cái navigation này phải
  hẹp cái height lại"*. Hiện `--wujia-mheader-height: 104px` (`_variables.css`), cộng dải cửa hàng 48
  + thanh dưới 83 = **235px = 26% màn hình 900px** không dùng để hiển thị nội dung. Việc cần làm:
  hạ header 104→~72 (logo 116×44 và 3 nút tròn 38 phải co theo, kiểm vùng chạm ≥44), cân nhắc ẩn
  header khi cuộn xuống. Lấy lại 30–50px MỖI MÀN cho **mọi trang**, không đụng nội dung.
  Lệch Figma "Mobile Shell FINAL (header 104 / strip 48 / footer 83)" ⇒ ghi FYI cho BA cùng dòng
  lệch nhịp dọc của phiên này. Mốc đo trước/sau: `wj_measure` + đếm "khối/dòng thấy trọn màn đầu"
  (script đã dùng ở phiên này, chép lại từ `docs/mobile-rhythm-acceptance.md` §2 phép đo 5–6).
- Phiên kế: **G2** (theo yêu cầu trên). Sau G2 mới quay lại **E4b** của Issue List; G1 (rút dòng danh
  sách về 1 dòng) chỉ làm khi BA đồng ý vì đổi cấu trúc dòng.

## G2 — Hạ chiều cao header mobile 104 → 72 · 18/09/2026 · Mac
- Kết quả: ✅ đạt. Việc chủ dự án giao trực tiếp cuối phiên trước (*"cái navigation này phải hẹp cái
  height lại"*), ngoài lộ trình cụm F. Phạm vi chốt: CHỈ header; dải cửa hàng 48 và thanh dưới 83 để sau.
- Đã làm:
  - `--wujia-mheader-height` **104 → 72**, khai trong khối `@media (max-width:991.98px)` của
    `_variables.css` (PC không đọc tới ⇒ khỏi phải chứng minh bất biến).
  - Gỡ neo tuyệt đối `.wujia-mheader-actions { align-self: flex-start; margin-top: 39px }` — con số 39
    chỉ đúng với header 104, giữ lại là cụm nút tràn khỏi header.
  - Trả nợ cũ tiện thể: vùng chạm 3 nút header **38 → 44** bằng `::before` 44×44, hộp nhìn thấy vẫn 38.
  - Guard mới `wujia_portal_layout/tests/test_g2_mobile_header.py` (7 test) — đặt ở KHUNG, không ở
    `portal_base`: header là component của chính khung và sau F5b khung phải tự chạy một mình.
- Commit: `7873175`
- Deploy: **ĐÃ DEPLOY UAT 18/09/2026** — chủ dự án deploy; `wujia_portal_layout` trên UAT ra đúng
  **19.0.51.0.12** và view mang `?v=1294`/`1299` ⇒ restart tự upgrade, không cần `-u`. Đo lại chỉ-đọc
  trên chính máy chủ: header **72** cả 10 ô, dải 48, mốc nội dung **120**, chạm **44**, bấm thật 3/3,
  0 tràn ngang, 0 lỗi JS. Bẫy khi đo: 3 nút báo "BỊ CHE" là do popup chọn cửa hàng của tài khoản
  admin (`#wujiaStoreOverlay`), không liên quan G2.
- Số đo: header 72 cả 10 ô · mốc đầu nội dung **152 → 120** · `wj_measure` mobile **−32,0px × 16 ô**,
  PC **0 ô lệch**, 0 ô mất record (Báo cáo 14 → 16 record) · dòng thấy trọn màn đầu Kiến thức @390
  3 → 4 · bấm thật 4/4 (bấm cao hơn hộp 38 đúng 2px vẫn mở dropdown ⇒ pseudo ăn thật) · 0 tràn ngang ·
  0 lỗi JS · HIERARCHY 3 → 3 · suite **586/586** · DB trắng chỉ cài khung **0 failed / 1 error** (`test_fra3_layer_guard`, **nợ có sẵn thuộc F6**, không phải do phiên nào trong cụm gây ra)
  · mutation **5/5 đỏ** · `check_layers` 2 R7 có sẵn.
- Bẫy gặp:
  - **`::after` của nút header đã bị dành để tắt caret Bootstrap** (`.dropdown-toggle::after{display:none}`).
    Viết vùng chạm vào `::after` là mất vùng chạm ở đúng 2/3 nút, im lặng. Đã chuyển sang `::before` và
    có guard riêng khoá bẫy này.
  - **Bộ đo của chính mình cũng phải soi**: probe đầu đọc mỗi `::after` nên báo "chạm 38" trong khi code
    đã đúng — suýt đi sửa code lành.
- Đính chính số của phiên trước (đã sửa thẳng vào `mobile-rhythm-acceptance.md` §4): **chỉ thanh dưới
  83 mới thật sự `position: fixed`**; header + dải cửa hàng nằm TRONG luồng, chiếm 152px ở đầu trang
  rồi trôi đi khi cuộn. Không có "235px khoá cứng mỗi màn". Đổi lại, hạ header LÀ làm ngắn trang thật
  32px, và không phải vá mốc đầu nội dung (`--wujia-mcontent-top` giữ 10, y=120 = 72+48+10 tự ra).
- Nợ để lại:
  - **Chưa gửi BA dòng FYI** — gộp 2 khoản: header 104→72 và nhịp dọc của phiên trước (gap 14→8,
    mép trên 16→10, tiêu đề nhóm 16/8→6/4), đều lệch Figma *Mobile Shell FINAL* / RESP-MOB-SHELL-003.
  - **G1** (dòng danh sách 2–3 dòng → 1 dòng) và **G3** (cỡ chữ/line-height) chờ BA.
  - Muốn lấy thêm chỗ ở MỌI vị trí cuộn thì phải đụng **thanh dưới 83** — thứ duy nhất thật sự cố định.
- Phiên kế: **E4b** — phủ hết call site FilterBar (`UI-FILTER-001`, E4a đã làm nền `12750a2`), quay lại
  hàng đợi Issue List đã mở lại sau FR-A3.

## E4b1 — FilterBar `CMP-FB-001`: phủ hết call site PC · 19/09/2026 · Mac
- Kết quả: ✅ đạt **16/16** tiêu chí. Lượt đầu quay lại hàng đợi **Issue List** sau cổng ★FR-A3.
  `UI-FILTER-001` (STT 139) **CHƯA đóng** — đóng ở E4c; không chạy `qa_sync.py`, không đổi sheet.
  Chủ dự án chốt 2 việc đầu phiên: (1) **cắt đôi E4b** → E4b1 PC / E4b2 mobile; (2) 5 màn "nhóm 2"
  (giao hàng · thông báo · thi · báo cáo · đặt hàng) **migrate hẳn vào component**, không chỉ căn lề.
- Đã làm:
  - **9 call site PC** về `wujia_portal_layout.wj_filter_bar`: support · knowledge · return ·
    info_request (4 màn Bootstrap `row g-2`) + delivery · notification · exam · report · order.
  - Component thêm đúng **một** knob: `fb_dates={'kind':'text'}` — màn Thi còn ô ngày dạng chữ,
    E4c mới wire; ép `type=date` sớm là tự sửa lỗi BA nêu bằng cách giấu nó.
  - Biến thể `--dense` (flex-basis hẹp hơn) cho 2 thanh **5–6 control** (notification · exam) —
    không có nó thì notification 88 → 142 ở 1440, tức là lượt chuẩn hoá làm xấu đi màn đang đạt.
  - Dọn CSS bản địa 4 module (`portal_notification`/`portal_report`/`portal_exam`/`portal_order`);
    2 họ class mà **Khảo sát của anh Thái còn dùng** thì **thu hẹp vào `.wj-inspection-pc`**, không
    xoá (bẫy E3c), kèm test chặn.
  - **Dựng lại + commit công cụ kiểm kê**: `scripts/qa/wj_filterbar_inventory.py` (bản E4a để ở
    `scratchpad/e4/`, thư mục đã mất). Thêm **chế độ render** đọc DOM thật — sau migrate thì quét
    `lxml` không còn đọc được điều kiện nằm trong component, bản tĩnh một mình là **mù**.
  - **Công nợ PC không sửa byte nào**: đo ra đã đúng chuẩn (42px, nhãn `Xem`/`Tìm kiếm` hợp
    FB-02/FB-09 item 9). Ghi rõ trong matrix thay vì sửa cho có.
  - 21 test mới (16 `portal_base` quét chéo module + 5 `portal_layout` hợp đồng component) — đúng
    luật sở hữu F5b.
- Commit: `131d948`
- Deploy: **chưa** — không tự deploy UAT. Lệnh `-u` gộp ghi ở `docs/e4b1-acceptance-matrix.md` §5.
- Số đo: **FB-10 0/48 ô lệch bộ điều kiện** (12 route × 4 khổ, chế độ render) · control PC
  **26.7–28.1 → 42** ở 4 màn nhóm 1, **50 → 42** ở báo cáo, baseline `2 → 1` ở return + exam ·
  card 88 ở cả 9 màn (delivery **142 → 88**, exam **144 → 88**) · `wj_formcontrol --scope body`
  **101 control / vi phạm 88 → 75** · `wj_measure` 13 route × 5 khổ **0 tràn ngang · 0 lỗi JS ·
  0 redirect** · suite **0 failed / 0 error / 601 test** · DB trắng **0 failed / 1 error**
  (`test_fra3_layer_guard`, nợ F6) · mutation **11/11 đỏ đúng guard** · `check_layers` 3 R1–R5 +
  2 R7 **có sẵn**, không thêm.
- Bẫy gặp:
  - **`log_level=warn` nuốt dòng tổng kết test.** `odoo.tests.result` chỉ ghi ERROR khi CÓ lỗi; suite
    xanh thì dòng "0 failed…" là INFO nên biến mất ⇒ mất 3 lần chạy lại vì tưởng test không chạy.
    Luôn thêm `--log-handler "odoo.tests.result:INFO"`.
  - **Harness mutation đọc stdout là đọc nhầm chỗ**: Odoo ghi `FAIL:` vào logfile, mà `wujia_core`
    còn dời logfile sang `<thư mục>/<năm>/<tháng>/<ngày>.log`. Phải đọc theo glob + chặn cứng
    "không thấy dòng tổng kết ⇒ run hỏng, KHÔNG phải 0 đỏ".
  - **Tách tên test cắt trước `test_`** bắt trúng tên logger (`tests.test_scan_e4_filter_bar`) nên
    11/11 mũi báo "SAI" oan. Phải cắt **sau** nhãn `FAIL:`/`ERROR:`.
  - **Cắt XML theo chỉ số anchor** làm hỏng `portal_order_catalog.xml` (chuỗi kết thúc lặp lại) —
    phải `git checkout` rồi cắt lại theo dòng tường minh.
- Nợ / phải nói với BA:
  - **Kiến thức PC mất 1 record trong khung** (30→29 @1440) và cao thêm 42px; Báo cáo 80 → 88. Lý do:
    thanh lọc cũ của Kiến thức chỉ cao 39px, nay về chuẩn control 42 / card 88 của chính BA. Muốn giữ
    record thì phải đổi **chuẩn**, không phải đổi riêng màn.
  - **Nút "Xóa lọc" của Thông báo** chuyển từ reload cả trang sang link `data-wj-nav` (AJAX) — cùng
    URL đích, cố ý thống nhất theo component.
  - 3 màn (exam · notification · return) **đổi thứ tự hiển thị** ô lọc sang chuẩn search → ngày →
    select; bộ điều kiện y nguyên. Ghi ra để retest không tưởng là mất/thêm ô.
- Phiên kế: **E4b2** — toàn bộ thanh lọc mobile. Prompt sẵn: `docs/prompt-e4b2.md` (đã ghi rõ G2 hạ
  header mobile 104→72 nên mốc cao trang mobile phải chụp lại, kèm bảng mốc sau E4b1).

## E4b2 — FilterBar `CMP-FB-001`: phủ hết call site **mobile** · 19/09/2026 · Mac
- Kết quả: ✅ xong — **13/13 tiêu chí**. `UI-FILTER-001` (STT 139) **CHƯA đóng** (đóng ở E4c);
  không chạy `qa_sync.py`, không đổi sheet, không tự deploy UAT.
- Đã làm:
  - **6 thanh lọc mobile vào component**: Lịch sử · Thông báo · Hỗ trợ · Kiến thức · Đổi trả ·
    **Báo cáo** (Báo cáo vào hẳn component theo chốt "làm chuẩn chỉ hẳn" của chủ dự án).
  - **Biến thể BA 04-DateRangeOnly** thêm vào component: màn **chỉ có ngày** thì nút tìm nằm **cùng
    hàng** với 2 ô ngày. Không có nó thì thẻ Báo cáo phình 72 → 116 (thêm hẳn một hàng nút).
  - **Đặt hàng mobile** giữ dáng hàng trần (bọc card là đổi thiết kế màn) nhưng kéo hình học về
    chuẩn: ô tìm + nút **44/r12 → 38/r10**, vùng chạm giữ 44 (ô tìm bọc `<label>`, nút `::before`).
  - **Công nợ mobile 0 byte** — component riêng đã duyệt Figma v31 (FB-09 item 9), đo lại để chứng
    minh không hồi quy.
  - **Màn Thi mobile cố ý để nguyên**: chủ dự án chốt *"làm chuẩn, phiên này không ổn thì phiên sau,
    miễn giải quyết tới nơi"* ⇒ E4c **migrate + wire ngày một thể**, không đẻ knob tạm trong
    component. Có test ghi nợ.
  - Dọn CSS: xoá họ `.wj-rep-mfilter*` (52 dòng) · **thu hẹp** khối 44px của D6c về `.wujia-mexam`
    (màn Thi còn dùng — xoá là đẻ vi phạm vùng chạm ở chính màn ta không đụng) · giữ `.wj-mform` 48
    (chuẩn form BH-009, khác chuẩn ô lọc).
  - 20 test mới (13 `portal_base` quét chéo + 7 `portal_layout` hợp đồng component — đúng F5b).
- Commit: `c6e2946`
- Deploy: **chưa** — lệnh `-u` gộp 9 module ghi ở `docs/e4b2-acceptance-matrix.md` §9.
- Số đo: **FB-10 render-diff 13 route × 6 khổ = 78 ô, 0 lệch** · ô lọc mobile **38 nhìn thấy /
  44 vùng chạm** ở cả 3 loại control, thẻ **r14 / p12 / gap 8** ở 6/6 màn · **0 tràn ngang**
  @360/390/430 · `wj_formcontrol --scope body` **82 control · vi phạm 14 → 4** (4 ô còn lại là
  select PC 42 của info-request, **có y hệt ở run đối chứng**) · `wj_measure --diff` 13 route × 5 khổ
  **0 tràn ngang · 0 lỗi JS · 0 mất record**, đúng **1 ô lệch** (Báo cáo mobile **+14**) · **PC không
  đổi 1 pixel** · suite **0 failed / 0 error / 621 test** · DB trắng **0 failed / 1 error / 149**
  (`test_fra3_layer_guard`, nợ F6) · mutation **20/20 đỏ đúng guard** · `check_layers` 3 R1–R5 +
  2 R7 **có sẵn**.
- Bẫy gặp:
  - **Harness mutation bị dừng giữa chừng để lại file đã phá trong cây mã** (`wj-sup-mchips2`), suite
    lần sau đỏ. Đã vá: `atexit` + `SIGTERM`/`SIGINT` phục hồi. **Không bắt `SIGHUP`** — `nohup` đang
    vô hiệu nó, bắt lại là tự chết khi shell thoát (dính đúng một lần).
  - **Mũi phá `str.replace(old, new, 1)` ăn vào call site PC** (PC và mobile cùng file) ⇒ 3 mũi đỏ
    nhầm test của lượt trước. Thêm cờ `[m]` → thay ở lần xuất hiện **cuối**.
  - **Mũi phá phải giữ XML hợp lệ**: đổi `<label>` thành `<div>` làm lệch thẻ đóng ⇒ `-u` fail, không
    có dòng tổng kết, harness báo "run hỏng" (đúng như thiết kế).
  - **`closest('a, b, c')` trả tổ tiên gần nhất khớp BẤT KỲ selector nào — và khớp cả chính nó** ⇒
    hai công cụ đo báo vùng chạm 38 thay vì 44. Vá cả `wj_filterbar_inventory.py` lẫn
    `wj_formcontrol.py`; nếu tin máy thì đã đi "sửa" đúng chỗ vừa làm đúng.
  - **zsh không tách từ khi expand biến** ⇒ `--routes $R` gửi một chuỗi khổng lồ, script vẫn chạy
    "xong" với 1 route giả. Dùng mảng `R=(…)` + `"${R[@]}"`, luôn đếm route trong JSON trước khi tin.
  - **`-u` cả `wujia_core`/`wujia_franchise` làm suite chết ngay khi nạp test** (`wujia_franchise/
    tests/__init__.py` import file đã xoá — nợ phía anh Thái). Suite của lượt chạy trên 9 module đụng.
- Nợ / phải nói với BA:
  - **Báo cáo mobile cao thêm 14px**: thẻ lọc thấp đi 2 (72 → 70) nhưng thẻ chuẩn có
    `margin-bottom: 16px` còn thanh cũ cố ý để 0 ⇒ −2 + 16 = +14. Giá của việc dùng **chung một vỏ**.
  - **Nợ nhịp G2**: `.wj-filter-card` cộng 16px lên trên `gap` 8px của khung trang ⇒ *lọc → danh
    sách* thành 24px ở **cả 7 màn**. Nợ có từ **E4a**, gỡ là đổi nhịp 7 màn cùng lúc ⇒ để **cụm nhịp
    E5**, đã ghi vào `docs/prompt-e4c.md`.
  - **Đổi trả đổi thứ tự** ô lọc sang chuẩn tìm → ngày → select (bộ điều kiện y nguyên);
    **Báo cáo** đổi nhãn `Tìm` thành nút kính lúp có `aria-label="Tìm kiếm"`; **Đặt hàng** ô tìm nhỏ
    lại còn 38 nhưng vùng bấm vẫn 44.
- Phiên kế: **E4c** — wiring ngày + màn Thi mobile (migrate **và** wire một thể) + guard + **đóng
  issue**. Prompt sẵn: `docs/prompt-e4c.md`.

## E4c — FilterBar `CMP-FB-001`: hành vi lọc + ĐÓNG `UI-FILTER-001` (19/09/2026 · Mac)

- Mục tiêu: lượt cuối cụm E4. E4a/E4b1/E4b2 lo **dáng**; E4c lo **hành vi lọc** rồi đưa issue về
  `Ready for Retest` (Dev không đặt `Done`). Chốt đầu phiên của chủ dự án: làm xong viết luôn
  `docs/prompt-e5.md`, commit + push `main`, **không tự deploy UAT**.
- **Đo trước khi đọc mã** (guard mới `scripts/qa/wj_filterbar.py`) và bảng trong prompt hoá ra **sai**:
  Thông báo ghi ✅ nhưng thật ra tính `date_error` rồi **không view nào in ra**, và vẫn trả **toàn bộ**
  danh sách (10 bản ghi) khi ngày ngược; Đổi trả báo ở **banner đầu trang**, gộp chung với lỗi sai định
  dạng. **5/6 màn im lặng**.
- Làm được:
  - **Một nguồn duy nhất** `ERR_DATE_RANGE` + `date_range_error()` ở `wujia_portal_base` (L3a, không
    thêm depend); 6 màn cùng gọi. Trước đó 2 câu chữ khác nhau cho cùng một lỗi.
  - **Một khuôn hiển thị**: `<p class="wj-filter-error" role="alert">` qua slot `fb_error`, id nằm
    trong `wjl_slots`, màn có fragment in cả 2 mảnh. CSS dời về `wujia_portal_layout` (`?v=1303`).
  - **Màn Thi mobile**: khối dựng tay (2 ô ngày **không có `name`**) → component, **migrate + wire một
    thể** đúng chốt 19/09. Đo ra lọc thật: 10 → 0 bản ghi theo khoảng.
  - **Báo cáo** bỏ tự kẹp im lặng; ngày ngược ⇒ KPI 0 + chart rỗng **cùng bộ khoá** với nhánh thường
    (thiếu khoá là JS biểu đồ vẽ hỏng im lặng).
  - Gỡ **2 knob mồ côi** của component: `kind='text'` và **`clamp`** (xem bẫy dưới).
  - Guard 4 mục + **12 mũi mutation**; 6 file test mới (5 module + quét chéo `portal_base`).
- Số đo: FB-10 render 78 ô ⇒ **3 ô lệch, đều là màn Thi mobile cố ý** · ngày ngược **6/6 báo, 0 im
  lặng** · về trang 1 **5/5** · sang trang giữ lọc **5/5 (6/6 link)** · ngày lọc thật **5 màn có số
  đổi** · `wj_measure` 65 ô **0 lệch** · suite **648/0** · `check_layers` 3 R1–R5 + 2 R7 **có sẵn**.
- Bẫy gặp:
  - **`clamp` chặn IM LẶNG cú dời khoảng ngày về trước.** Guard bắt màn Báo cáo "gửi đi không có
    ngày"; truy ra `min`/`max` do `clamp` sinh ra làm trình duyệt **từ chối submit** khi người dùng
    chọn khoảng sớm hơn khoảng đang lọc — không request, không thông điệp. Có ở **mọi** màn ngay khi
    đã lọc một lần. Đã gỡ `clamp` khỏi component + 6 call site; 2 test cũ khẳng định `clamp` đổi
    thành test khẳng định **không màn nào kẹp lại**.
  - **DB đo có 0 phiếu thi, 0 chuyến giao** ⇒ mục "ngày hợp lệ lọc đúng" không chứng minh được. Phải
    gieo (`scripts/seed_e4c_dates_demo.py`) rồi mới đo — nếu không lại là một bảng "Pass rỗng".
  - **`cls.session` trong `HttpCase` đè phiên HTTP** ⇒ `authenticate()` nổ `'... has no attribute
    sid'`. Đặt tên `cls.exam_session`.
  - **`--routes`/`--widths` phải khớp hệt lúc chụp mốc**, nếu không `--diff` in ra 31 "lệch" toàn là
    ô không đo (`sau=None`) — suýt tưởng hồi quy.
  - Mũi phá phải khớp **đúng thụt lề** của file đích; sai một dấu cách là harness báo "phép phá không
    ăn" (đúng như thiết kế, nhưng tốn một vòng chạy).
- Nợ mang sang: **nhịp G2** (`.wj-filter-card` +16px chồng `gap` 8 ⇒ *lọc → danh sách* 24px ở 7 màn)
  — đã ghi thành việc bắt buộc của **E5** trong `docs/prompt-e5.md`.
- Phiên kế: **E5** — ListCard `CMP-LC-001` (`UI-LISTCARD-001`, STT 136, dòng tuyệt đối 129).
  Prompt sẵn: `docs/prompt-e5.md`.
- Chốt phiên: commit **`faa76f5`** đã push `main`; ledger `UI-FILTER-001` + `qa_sync --apply` ⇒ sheet
  dòng tuyệt đối **132** (STT 139) về **`Ready for Retest`**, Owner `BA/Tester`, cột Build ghi rõ
  **CHƯA lên UAT** (chủ dự án tự deploy). Lệnh `-u` gộp 12 module nằm ở `docs/e4c-acceptance-matrix.md` §8.

## E5a — ListCard `CMP-LC-001`: component + 2 route mẫu (19/09/2026 · Mac)

- Chốt đầu phiên của chủ dự án: **chẻ E5 thành E5a / E5b / E5c** (như E4 chẻ a/b1/b2/c), và
  **LC-22 ProductCard token-only "fix luôn"** — xếp vào E5c, chụp mốc `wj_measure` riêng cho
  `/portal/order` để lùi được độc lập. E5a = inventory + component + 2 route mẫu + guard.
- **Đo trước khi đụng mã**, và hiện trạng tệ hơn bảng trong prompt: **22 call site** thật, **14 họ
  class item** khác nhau, mỗi module tự dựng ruột. D5 đã chuẩn hoá **dáng NGOÀI** (`.wj-data-item`),
  cái chưa ai làm là **anatomy BÊN TRONG** — đúng phạm vi E5.
- Làm được:
  - **Component** `wujia_portal_layout/views/wj_list_card.xml` — 2 template (`wj_list_card` +
    `wj_list_card_row`), dùng lại khuôn slot của `wj_data_list.xml`, **không JS mới**. Thẻ item vẫn ở
    call site vì QWeb **không có** directive đổi tên thẻ động (`ir_qweb.py:1705`) ⇒ `<a>`/href từng
    route giữ nguyên.
  - **Badge 12px = modifier DÙNG CHUNG** `.wj-status-badge--compact` (chỉ khai `font-size`), **không**
    CSS theo route; guard E2 nới đúng một khe hẹp cho modifier này, kèm chú thích LC-25.
  - **2 route mẫu**: history (`wujia-mhist-row`, 6 rule) và delivery (`wujia-mdelivery-row`, 9 rule)
    về `.wj-lc`; bỏ nhãn thừa "Chuyến xe" + divider nội bộ (LC-14), thêm nhãn "Ngày đặt"/"Tổng tiền"
    (LC-13). **Giá trị mất/thêm = 0/0** ở cả hai.
  - **2 công cụ mới**: `wj_listcard_inventory.py` (kiểm kê trường, `--diff` **tách nhãn khỏi giá trị**
    nên đổi nhãn theo BA không bị đếm nhầm là "thêm trường") và `wj_listcard.py` (guard anatomy
    LC-01/03/04/07/10).
  - **18 test mới**: 12 hợp đồng component ở `portal_layout`, 6 quét chéo ở `portal_base` theo sổ
    đăng ký `MIGRATED`/`GIU_NGUYEN` — thêm route ở E5b chỉ cần thêm một dòng vào sổ.
- Số đo: guard **0/10 ô** có vi phạm trên 2 route × 5 khổ · **đỏ đúng 7/7** route chưa migrate ·
  `wj_nesting` **0** khung lồng khung · `wj_datalist` **0** vi phạm · Home chữ ký DOM **trước = sau**
  (`fd881c9f4245`) · suite **433 tests, 0 failed, 0 error** · `check_layers` 3 R1–R5 + 2 R7 **có sẵn**.
- Bẫy gặp:
  - **Đo nhịp sai mốc**: *lọc → danh sách* ra 52/55/70 vì count-meta/section-header xen giữa. Đổi sang
    *lọc → phần tử anh em kế tiếp nhìn thấy được* mới lộ đúng **24px ở 7 route** — nợ G2 vẫn nguyên,
    trả ở E5c.
  - **3 công cụ QA mặc định `--base 127.0.0.1:8019`** (`wj_nesting`, `wj_datalist`, `wj_measure`) —
    đúng cổng bị cấm đụng, và lần chạy đầu đã lấy số từ **DB khác** (delivery item=0 trong khi thật là
    20). Đổi mặc định cả 3 về **8090**. Ai đọc số cũ của các cụm trước nên soi lại cột `base` trong JSON.
  - **Guard sạch ngay lần đầu** ⇒ phải chứng minh nó cắn: 11/11 ca `judge()` tổng hợp + mũi CSS thật
    (badge 12→13px ⇒ **20 vi phạm**, hoàn nguyên ⇒ **0**).
  - **Đổi ruột làm card cao lên 80 → 104px** ⇒ khai `compact-row` (64–76) thành **khai sai dáng**,
    guard D5 đỏ đúng. Chuyển call site sang `detail-card` và sửa bảng trong `test_scan_d5_data_list.py`.
  - **Skeleton hợp lệ viết tay `wj-lc__row`** (thanh xám, không nhãn/giá trị) ⇒ luật "cấm hàng phụ viết
    tay" phải hạ xuống "cấm **nhãn/giá trị** viết tay".
  - Test đọc CSS bằng `selector + ' {'` trượt vì rule canh cột → regex `\s*\{`.
- Nợ mang sang: **nhịp G2** 24→16 ở 7 route (E5c) · **padding item `12px 14px`** vs LC-07 ghi 12, đi
  chung món gutter LC-08 (E5c, **không** sửa lẻ) · **mẫu mỏng** `/portal/debt` 1 và
  `/portal/exam/register` 1 ⇒ phải gieo trước khi kết luận (E5b) · **LC-20 defer vĩnh viễn** (code anh
  Thái) · **LC-27** lệch dữ liệu — chỉ ghi nhận, không tự sửa mapping.
- Phiên kế: **E5b** — phủ 9 call site còn lại theo thứ tự rủi ro tăng dần: thông báo (LC-16) → hỗ trợ
  (LC-18) → đổi trả (LC-15) → kiến thức ×2 (LC-17) → thông tin nhượng quyền → thi ×3 (LC-19) → công nợ
  ×2 (LC-21, retest bằng role được phép). Chi tiết: `docs/e5a-acceptance-matrix.md` + kế hoạch cụm E5.
- Chốt phiên: **issue CHƯA đóng** — `UI-LISTCARD-001` chỉ ghi ledger + `Ready for Retest` ở **cuối
  E5c**, khi đủ 22 call site + regression 8 khổ. **Không tự deploy UAT.**

## E5b1 — ListCard `CMP-LC-001`: 6 call site rủi ro thấp (19/09/2026 · Mac)

- Chốt đầu phiên của chủ dự án: **chẻ E5b thành E5b1 / E5b2** (tiền lệ E4b1/E4b2) · **Kiến thức
  migrate cả PC lẫn mobile** ("cải tiến hết", PC riêng mobile riêng) · **CardHeader lồng trong item
  Thi sẽ thay bằng đầu ListCard** (ghi sẵn cho E5b2) · **giữ icon trang trí, đưa vào slot `lc_prefix`**
  chứ không tự xoá thứ BA đang thấy — kèm một câu hỏi cho BA ở cuối phiên.
- Sửa lại con số của nhật ký E5a: còn **11 call site** chứ không phải 9 (đếm theo call site, không
  theo route); Kiến thức ở PC là **card list**, không phải bảng ⇒ không vướng luật "bảng PC 0 byte DOM".
- Làm được:
  - **6 call site** về `.wj-lc`: Thông báo (LC-16, giữ dấu chưa đọc) · Hỗ trợ (LC-18) · Bù hàng
    (LC-15, **"Ngày yêu cầu" đủ năm**, bỏ divider + chevron) · Kiến thức **mobile + PC** (LC-17) ·
    Thành viên cửa hàng (LC-18).
  - **Khung học được 3 điều mới** (`_components.css` `?v=1306 → 1311`): tên card `flex: 1 1 0` + clamp
    2 dòng · thân card thành **lưới 2 cột** `minmax(0,1fr) auto` để "trường ngắn cùng hàng" mà không
    đẻ slot mới (dùng lại `lcr_class`) · `tabular-nums` cho giá trị.
  - **Sổ `MIGRATED` có khái niệm "họ dùng chung"**: `wujia-mdash-row` (Home 50 chỗ) và
    `wujia-content-card-row` (Home) **không được** xoá khỏi CSS ⇒ luật thu hẹp thành *"không còn nằm
    trong cây con của item đã migrate"*.
  - Test mới/đổi chủ: `test_e5b_list_card_read_state.py` ở **chính module Thông báo** (dấu chưa đọc là
    hành vi riêng) · D6b/BH-007/BH-008 của Bù hàng neo lại vào anatomy ListCard + `test_nhan_ngay_
    yeu_cau_du_nam` · D5e còn 5 call site Home, D5f bỏ sổ họ riêng · E2b đo "chip không bị kéo cao"
    ở khung thay vì ở màn.
- Số đo: inventory DIFF 13 route × 2 khổ = **3 dòng, cả 3 là món LC-15 của Bù hàng**, 5 route kia
  **0/0** · guard `wj_listcard` **0 vi phạm** (7 route × 5 khổ, +1440 cho Kiến thức) · **10/10 mũi
  mutation đỏ đúng guard của nó** · `wj_returncard` **0 vi phạm**, 1 bố cục metadata (trước khi có
  `tabular-nums` là **5**) · `wj_nesting` **0** · `wj_measure` 0 tràn/0 lỗi JS/0 redirect · Home chữ
  ký DOM **trước = sau** ở cả @390 lẫn @1440 · suite **567 tests, 0 failed, 0 error** ·
  `check_layers` 3 R1–R5 + 2 R7 **có sẵn**.
- Bẫy gặp:
  - **Card phình 100 → 150px** không phải do nội dung mà do `.wj-lc__name` **rớt xuống dòng dưới ô
    icon** (lead `flex-wrap`). Sửa ở khung một chỗ, 3 màn cùng thấp lại.
  - **Gỡ CSS theo họ làm chết markup khác**: bài Nổi bật + trang chi tiết Kiến thức dùng chung
    `.wujia-mknow-row-title` / `.wujia-mknow-date` với danh sách. Bắt được bằng một lượt quét *"class
    còn trong view mà không còn rule CSS"* — **nên làm mặc định sau mỗi lượt gỡ CSS**.
  - **`wj_returncard.py` Pass rỗng**: 51/51 phiếu trong DB đo có `resolution_type` rỗng ⇒ nhánh "Tiến
    độ bù" không bao giờ render. Gieo `seed_d6_return_demo.py` + đo bằng `anh.owner` mới có 5 cặp badge.
  - **Cột phải của lưới lệch 1–7px giữa các card** vì chữ số không cùng bề rộng — guard bắt đúng
    (5 bố cục metadata), `tabular-nums` mới về 1.
  - Hai lớp hook chết (`wujia-mnoti-list`, `wujia-mknow-list`): gap nay là việc của DataList ⇒ bỏ
    `dl_class` thay vì để tên lớp không có rule.
- Nợ mang sang: **E5b2** Thi ×3 + Công nợ ×2 (gieo trước, thay CardHeader lồng, giữ JS hook
  `data-exam-*`) · **nhịp G2** 24→16 ở 7 route (E5c) · **padding item `12px 14px`** vs LC-07 (E5c, đi
  chung gutter LC-08) · **LC-20 defer vĩnh viễn** · **LC-27** lệch dữ liệu · **mẫu một chiều**: cả 10
  thông báo của `em.hcm` đều chưa đọc ⇒ chưa đối chiếu được card đã đọc bằng trình duyệt.
- Hỏi BA (ghi trong `docs/e5b1-acceptance-matrix.md`): (1) ô icon phân loại 32×32 trong card — giữ hay
  bỏ theo đúng chữ LC-06/LC-07? (2) dải cao `detail-card` 96–120 — bản ghi Bù hàng có tiến độ bù +
  tên 2 dòng đo **122–156px**, siết trường hay công nhận dải rộng hơn?
- Phiên kế: **E5b2** — Thi ×3 (LC-19) + Công nợ ×2 (LC-21). Chi tiết:
  `docs/e5b1-acceptance-matrix.md` §"Còn treo".
- Chốt phiên: **issue CHƯA đóng** — `UI-LISTCARD-001` ghi ledger + `Ready for Retest` ở **cuối E5c**.
  **Không tự deploy UAT.**

## DOC-CTRL — Kiểm kê controller cho BA (19/09/2026 · Mac)

- Phiên **tài liệu**, không phải phiên F. **0 dòng code nghiệp vụ**: `git status` chỉ có `docs/` +
  `scripts/qa/`, **0 file dưới `custom/`**.
- Yêu cầu gốc (chủ dự án chuyển từ BA): *"cần check code và server xem đã có những controller nào,
  ở phân hệ nào, chức năng gì — để BA còn lên task tiếp"*, ra **`.tex` → PDF**. Chốt thêm:
  phạm vi `wujia_*`, **có** đối chiếu UAT (chỉ-đọc), PDF **độc lập** (không nhét vào master 300
  trang), và **ghi mỗi controller ứng với mục `CT-0xx` nào** + mục CT nào chưa có code.
- Làm:
  - `scripts/qa/controller_inventory.py` (**mới**, không tiền tố `wj_` theo luật F0) — duyệt **AST**,
    không grep. Mỗi hàm có `@http.route` xuất: module · file · dòng · class · bases · method · paths ·
    type · auth · methods · csrf · website/sitemap · docstring dòng đầu · model `env[...]` dùng trong
    thân. Ra `docs/controller-inventory/routes.json`.
  - Đọc UAT **chỉ-đọc** qua XML-RPC (`ir.module.module`) → cột "Trên UAT".
  - Đọc tab `3. Controller` bằng `sheet_io.read_values` → `docs/controller-inventory/ba_ct.json`.
  - Đọc tay 21 file controller để viết cột **chức năng nghiệp vụ** (máy sinh metadata, không sinh
    được nghiệp vụ).
  - `docs/controller-inventory.tex` → `controller-inventory.pdf` (**20 trang**, `lualatex` ×2,
    **không** qua `build-doc.sh`).
- Số đo chốt: **103 route · 106 path · 21 class · 23 file** (21 có route + 2 helper) · **16 module**
  có controller. CT: **71 mục thật** (CT-001…CT-071) = **56 ĐÃ CÓ · 6 MỘT PHẦN · 9 CHƯA CÓ**.
- Bẫy gặp:
  - **Đếm class sai 19 vs 20**: `WujiaPortal(CustomerPortal)` và `WujiaAuthController(AuthSignupHome)`
    có base **không chứa chữ "Controller"**. Sửa: nhận diện controller bằng **"có route"**, không bằng
    tên base ⇒ **21 class**. (Số route chưa bao giờ sai — chỉ class.)
  - **DB trên UAT là `wujia_tea_19`**, không phải `wujia_tea` — xác minh bằng `/xmlrpc/2/db` `list()`
    sau khi authenticate báo `database does not exist`. Traceback cũng lộ UAT chạy **Windows**
    (`D:\wujia-tea\odoo19`).
  - **Plan đếm bằng mắt sai**: plan ghi 17 file / 15 module / 20 class / 73 CT; máy đếm ra
    **23 / 16 / 21 / 71**. Hai dòng `CT-024.`/`CT-025.` cuối tab là **chữ thừa dưới bảng**, không
    phải mục.
  - Macro `\part` **trùng lệnh sectioning của LaTeX** ⇒ 100 lỗi `Misplaced \cr`. Đổi thành `\pt`.
  - Font **Lato không có trên máy này** ⇒ preamble ADR-027 chép sang phải đổi `\setmainfont`
    sang **Noto Sans**.
- Việc có ích cho BA (chương 6 của PDF): 8 module đang **lệch repo↔UAT** = E5a + E5b1 chưa deploy
  (chỉ giao diện, không mất chức năng) · **7 điểm cần BA xác nhận** (nguồn dữ liệu công nợ chưa nối
  `account.move` · ticket lọc theo **người tạo** chứ không theo cửa hàng · thành viên: Nhân viên có
  được xem không · cửa hàng lưu bằng **cookie** không phải session · đổi trả **1 sản phẩm/yêu cầu** ·
  QR thanh toán · 2 dòng thừa cuối tab) · **CT-061…CT-067** (ca làm, chấm công, nghỉ phép, chi phí)
  **chưa có dòng code nào** · **F6–F13 sẽ dời controller sang module khác nhưng URL không đổi** ⇒ BA
  **đừng lên task viết lại** các controller đó.
- Nợ mang sang: **11 nhóm route đã có code mà tab CT chưa mô tả** (quên/đặt lại mật khẩu, đổi ngôn
  ngữ, PDF đơn hàng, `.ics` giao hàng, 6 nhánh `.../results`, đồng bộ giỏ, 2 ảnh, 9 redirect 301, 12
  route Khảo sát, 2 route Metabase) — chờ BA bổ sung spec.
- Phiên kế: **E5b2** — Thi ×3 (LC-19) + Công nợ ×2 (LC-21), không đổi (phiên này không lấn lộ trình F).
- Chốt phiên: **không deploy**, **không đụng Issue List**, **không ghi sheet**.

## E5b2 — ListCard `CMP-LC-001`: 5 call site cuối, khép cụm E5b (19/09/2026 · Mac)

- Chốt đầu phiên của chủ dự án: **wizard "Chọn khóa thi" có migrate**, nút "Chọn" vào slot
  `lc_actions` · **tiền tách nhãn** ra `lcr_label` (`Còn lại` / `Đã trả` / `Được trừ`), số là giá trị
  đậm · chốt lượt **commit + push `main`, KHÔNG deploy UAT, issue vẫn mở** (đóng ở E5c).
- Làm được:
  - **5 call site cuối** về `.wj-lc`: `/portal/exam` · `/portal/exam/register` bước 1 ·
    `/portal/exam/registration/<id>` · `/portal/debt` · `/portal/debt/payment-history`.
    ⇒ **22/22 call site** của `UI-LISTCARD-001` đã về component, khép **E5b**.
  - Gỡ **100 dòng CSS** anatomy theo màn (Thi 70 · Công nợ 30). Giữ có chủ đích
    `wujia-mexam-card-top`/`-card-line` (khối tóm tắt phiếu, **không phải** danh sách); thu hẹp
    `portal_debt.css` còn **2 rule màu** bám đúng `.wj-lc__value--strong`.
  - Khung chỉ thêm **1 rule** `.wj-lc__link` (`?v=1311 → 1312`) — không màn nào khai `.wj-lc*` riêng.
  - **Gieo dữ liệu trước khi đo** (`scripts/seed_e5b2_demo.py`, LOCAL-ONLY, idempotent): 2 khoá thi
    Còn lịch/Đã đóng · phiếu đã công bố có Đạt + Không đạt + ghi chú · tuần mặc định có quá hạn/giấy
    báo có/đã trả · 3 thông báo **đã đọc** (trả nợ "mẫu một chiều" của E5b1).
  - Test: 2 file **mới** đúng chủ (`wujia_portal_exam/tests/test_list_card_e5b2.py` 6 test ·
    `wujia_portal_debt/tests/test_list_card_e5b2.py` 5 test); sổ `MIGRATED` 7 → **9**; **đảo chiều**
    2 test layout D5g/D5h (bố cục trong item nay là của ListCard ⇒ **cấm** màn khai lại).
- Số đo: inventory DIFF 14 route × 2 khổ = **13 dòng, tất cả là món tách nhãn đã chốt**, 0 lệch số
  record · `wj_listcard` **12 route × 5 khổ, 0 vi phạm** · `wj_nesting` 0 · `wj_datalist` 0 ·
  `wj_measure` 0 tràn/0 lỗi JS/0 redirect · Home + 7 route chưa migrate + **bảng PC của cả 5 màn vừa
  sửa** giữ **nguyên chữ ký DOM** · wizard 4 bước chạy thật PASS · **14/14 mũi mutation** · suite
  **653 tests, 0 failed, 0 error** · `check_layers` 3 R1–R5 + 2 R7 **có sẵn**.
- Ba bài học ghi lại:
  1. **Guard markup không thay được chạy thật**: JS wizard đọc `.wj-card-header__title` của card khoá
     thi — sau migrate card không còn header nên bước 2 hiện **tiêu đề rỗng**. Phép đo trình duyệt
     bắt được; test D3d của màn cũng đỏ đúng chỗ.
  2. **Sổ đăng ký đếm "có ít nhất một" là guard yếu**: mũi M1 bỏ `wj-lc` ở một trong ba call site của
     Thi mà sổ vẫn xanh ⇒ siết thành **đếm >= số call site**.
  3. **Bẫy tên con BEM lại xuất hiện**: `assertNotIn('wujia-mexam-card', view)` khớp
     `wujia-mexam-card-top`; so theo **token** (`(?![-\w])`) mới đúng.
- Còn treo → `docs/e5b2-acceptance-matrix.md` §"Còn treo sang E5c" + **2 câu hỏi BA** (ô icon
  `.wj-lc__tile`; **dải cao hai variant không còn phủ hết thực tế**: nhân sự có ghi chú **146px**,
  hoá đơn 2 hàng phụ **80px** — rơi vào khe giữa 76 và 96).
- Chốt phiên: **issue CHƯA đóng** — `UI-LISTCARD-001` ghi ledger + `Ready for Retest` ở **cuối E5c**.
  **Không tự deploy UAT.** Prompt phiên kế: `docs/prompt-e5c.md`.

## E5c — ListCard `CMP-LC-001`: nhịp + bề ngang, regression 8 khổ, **đóng issue** (19/09/2026 · Mac)
- Kết quả: ✅ xong — `UI-LISTCARD-001` (STT 136, dòng 129) → **Ready for Retest**, khép cụm **E5**.
- Chốt đầu phiên của chủ dự án: **Dev tự quyết, ít hỏi BA lại, làm nốt cho chuẩn chỉnh mọi màn** ·
  2 câu hỏi BA treo giải theo đề xuất của chủ dự án · codex-review phạm vi **toàn cụm E5**.
- Đã làm:
  - **Nhịp *thanh lọc → nội dung* 24 → 16** ở **8 route** (7 route theo prompt + `/portal/reports/orders`),
    sửa **một chỗ** ở khung và khai bằng **token** (`margin-bottom: var(--wujia-mshell-content-gap)`)
    nên 8 + 8 = 16 không còn là hai con số nằm hai nơi.
  - **Đệm item `12px 14px` → `12px`** (LC-07) và **gutter trang 16 → 12** (LC-08, BA Q2) bằng token
    `--wujia-mshell-content-pad-x`, không vá theo màn.
  - **Vá lệch 5px giữa hai họ màn**: `/portal/purchase-history`, `/portal/order` render trong
    `.content-wrapper` của Vuexy (16,8px) còn màn BlankShell ăn token ⇒ thêm **1 rule ở khung** cho
    wrapper lấy chính token đó (không `!important` để Home còn tự bỏ lề được). Sau đó **mọi** màn
    mobile — kể cả `/portal/inspection` của anh Thái — đo đúng **12/12**, 0 tràn ngang.
  - **Vùng chạm nút “Chọn”** (màn đăng ký thi) 37×21 → **45×45** bằng cặp đệm + lề âm nên **card
    không cao thêm một pixel**. Đã chứng minh lỗi **có từ E5b2**, không do phiên này.
  - **Vá mốc đóng băng rỗng** `/portal/order`: route không có vùng danh sách nay lấy chữ ký **cả
    trang** (loại canvas/ApexCharts/`.resize-triggers`/đồng hồ) + báo `MỐC RỖNG`; khớp route đóng
    băng đổi từ tiền tố sang **khớp đúng**.
  - **Guard mạnh thêm**: `wj_listcard.py` đọc **variant** và kiểm dải cao theo variant; ở ≥992 đếm
    DOM thật thay vì báo sai “CHƯA MIGRATE” (**33 báo sai** biến mất).
- Số đo: `wj_listcard` **12 route × 8 khổ = 96 ô, 0 vi phạm** · inventory **16 route × 2 khổ, 194
  record, 0 vấn đề** (kể cả chữ ký đóng băng) · `wj_nesting` 0 · `wj_datalist` gap 8 đúng chuẩn ·
  `wj_measure` **0 HIERARCHY / 0 tràn / 0 lỗi JS / 0 redirect** · suite **686 tests, 0 failed,
  0 error** · mutation **10/10** (+2 mũi cấp công cụ) · `check_layers` **3 R1–R5 + 2 R7 có sẵn**.
- Commit: xem cuối phiên (1 commit code+test, 1 commit docs).
- Deploy: **chưa** — anh Huy deploy UAT.
- Lệch plan / quyết định mới:
  - Dải cao variant **không** lấy số đề xuất E5b2 (64–84 / 96–150) mà lấy **số đo thật 96 ô**:
    `compact-row` **64–112** · `detail-card` **96–156**. Hai dải nay **chồng nhau** ⇒ chiều cao
    không còn phân biệt variant, phân biệt bằng class. FYI cho BA.
  - **GIỮ** ô icon `.wj-lc__tile` 32×32 (ngoại lệ có chủ đích với LC-06/LC-07): nó là ô **tín hiệu
    trạng thái**, bỏ thì Thông báo mất màu theo loại.
  - `/portal/franchise-information` đo gutter **27** = 12 (trang) + 14 (đệm trong SurfaceCard) + 1
    (viền) — phạm vi `UI-SURFACECARD-001`, ghi nhận, không sửa ở E5c.
- Nợ để lại: `LC-20` Khảo sát defer vĩnh viễn (code anh Thái) · `LC-27` chỉ ghi nhận · `LC-23` Home
  preview giữ grouped rows · `/portal/debt` còn 1 dấu hiệu **có từ trước**: card cuối chạm mép thanh
  cố định (còn 125px đuôi cuộn nên chưa che bản ghi) — để cụm sticky/EmptyState xử.
- Phiên kế: theo `docs/next-session-clusters-F.md` §2 — **E6 · E7 · E8** + đề xuất cụm EmptyState;
  việc cần biết trước: cụm E5 đã khép, ListCard là nguồn chuẩn cho mọi danh sách mobile.
- Soi mã đối kháng (Codex, toàn cụm E5 `cf6d2b0^..HEAD`) cuối phiên: **4 finding, 4 đều THẬT** —
  (1) lệnh deploy thiếu 8 mô đun có view nằm trong DB ⇒ sửa ledger + ô Build/Deploy thành **10 mô
  đun**; (2) chấm "chưa đọc" màn Thông báo là span inline nên **đo 0px, chưa từng hiện** kể từ E5b1
  ⇒ vá + test + bump `wujia_portal_notification` 19.0.2.18.0; (3) nhánh LC-02 của guard chỉ có
  `pass` ⇒ thay bằng dấu hiệu thật `scrollHeight > clientHeight`; (4) inventory không kiểm
  `final_url` ⇒ thêm cờ `CHUYỂN HƯỚNG`. Cả 4 đều đã chứng minh bằng phép phá có kiểm soát.
  Suite sau khi vá: **687 tests, 0 đỏ**; `wj_listcard` vẫn **0 vi phạm**.

## E6a — Button `CMP-BTN-001`: atom + thước đo + 3 route mẫu (20/09/2026 · Mac)
- Kết quả: ✅ xong lượt E6a — `UI-BUTTON-001` (STT 132, dòng 125) **vẫn mở**, đóng ở E6c.
- Chốt đầu phiên của chủ dự án: chia **3 lượt** E6a → E6b → E6c · **màn auth migrate luôn cho đồng
  bộ** (lệch scope BA vốn chỉ liệt 13 route portal, làm ở E6b, ghi IMPACT) · cuối phiên **commit +
  push `main`, KHÔNG deploy UAT, issue vẫn mở**.
- Đã làm:
  - **Atom `wj-btn` / `wj-iconbtn`** ở khung: 5 variant + 3 bậc size, số lấy nguyên văn spec BA
    (PC 32/40/46 · mobile 36/44/48 · radius 8/12 · typo 13/18/600 · 14/20/700 · 15/22/700), khai
    bằng token `--wj-btn-*` nên PC/mobile chỉ là một khối `@media`. Vùng chạm 44 của bậc `sm` làm
    bằng **pseudo-element** nên visual vẫn 36 (khuôn đã dùng ở E4a cho ô lọc).
  - **Template `wj_button` + `wj_icon_button`** (2 nhánh vì QWeb 19 không đặt được tên thẻ động):
    có `btn_href` ⇒ `<a>`, không ⇒ `<button>`; `wj_icon_button` gắn `aria-label` **và** `title`.
  - **`wujia_button_loading.js`**: bắt `submit` ở pha capture, khoá form, gắn `is-loading` cho nút
    vừa bấm và `is-disabled` cho nút anh em, dọn lại khi `pageshow` (bfcache).
  - **21 call site / 5 file / 3 module** về atom (Hỗ trợ · Bù hàng · Thông báo) — phủ đủ **3 họ cũ**
    (`wj-pc-btn`, Bootstrap `btn*`, class lẻ `wujia-mreturn-btn-*`) đúng mục đích "3 route mẫu".
  - **Thước đo mới `scripts/qa/wj_button.py`**: mỗi route × khổ đo computed size/radius/typo, hộp
    chạm **kể cả pseudo**, variant, đếm Primary theo vùng hành động, **tab-walk thật** + focus ring,
    `disabled` không được nhận focus, và `is-loading` không được đổi bề rộng.
- Số đo: guard **9 route × 5 khổ = 45 ô, 0 vi phạm · 0 lỗi JS**; zoom 200% (khổ CSS 720/512) **10 ô,
  0 vi phạm**; **144 atom** đo được đúng 6 con số của BA, hộp chạm nhỏ nhất **72×48**; tab-walk 144
  nút **0 thiếu ring / 0 disabled còn focus**; 24 nút loading giữ **nguyên** bề rộng · `wj_measure`
  **0 tràn / 0 lỗi JS / 0 redirect / 0 HIERARCHY** · `wj_listcard` 0 · `wj_nesting` 0 · `wj_datalist`
  gap 8 · `b4_regression` **286/286** · suite **708 tests, 0 đỏ** (mốc E5c 687, +21 test mới) ·
  mutation **7/7** · `check_layers` **3 R1–R5 + 2 R7 có sẵn**.
- Commit: xem cuối phiên. Deploy: **chưa** (E6c gộp một lần).
- Lệch plan / quyết định mới:
  - **Nút của FilterBar là boundary**, không phải họ cũ: FB-08 cho Filter giữ 42/38/32 và **ưu tiên
    hơn** size mặc định của CMP-BTN-001 ⇒ thước đo loại cả `wj-filter*`/`wj-pc-filterbar*` (trước khi
    sửa là 18 báo nhầm).
  - **Hover viền theo WJ-PORTAL-UI-001 (`#28A9DF`)**, không theo `#BFE8F7` của BA — C6 đã chốt
    interaction state dùng chung. `--ghost` cố ý không nằm trong danh sách bề mặt của
    `_interaction.css` để không khai hai nơi cùng độ đặc hiệu.
  - **Test quét call site đặt ở `wujia_portal_base`** (khuôn mọi `test_scan_*` có sẵn, một sổ
    `MIGRATED` dùng chung) thay vì 3 file rời từng module như plan ghi — để E6b khỏi nhân bản logic
    đếm/so token 13 lần.
  - Hai màn danh sách trước dùng hai variant khác nhau cho **cùng vai trò** nút xem hàng
    (`--outline` vs `--secondary`) ⇒ thống nhất `--secondary`.
- Bẫy trong phiên:
  - Thước đo đọc variant chỉ theo `wj-btn--` nên **120 icon button ra `null`** ⇒ luật "≤1 Primary"
    hụt đúng nhóm đông nhất; đã dò cả `wj-iconbtn--` và thêm mã `VARIANT` cho atom không variant.
  - Regex `([^{}]+)\{([^}]*)\}` **nuốt cả rule con** nên rule trong `@media` không bao giờ được thấy
    (test vùng chạm xanh giả) ⇒ phải cấm luôn `{` trong thân.
  - Helper `_block()` của E5 tìm theo `selector + "{"`, **không thấy selector nằm trong danh sách**
    (`.wj-btn, .wj-iconbtn { … }`) ⇒ viết lại theo token đã tách dấu phẩy.
  - Cờ "Pass rỗng" ban đầu kêu cả khi màn **vốn không có nút hành động** ở khổ hẹp ⇒ siết lại: chỉ
    kêu khi có action mà 0 atom; đã chứng minh cờ vẫn bắt được bằng cách thêm `/portal/delivery`
    (chưa migrate) vào sổ `MIGRATED`.
  - **16 ô `b4_regression` đỏ là id cố định đã cũ**, không phải hồi quy: 4 route chi tiết redirect
    về danh sách vì `anh.owner` không còn thấy bản ghi (cả route của module E6a **không** đụng tới);
    đo lại bằng id có thật của `em.hcm` ⇒ **286/286**.
- Nợ để lại: gạch 12 của BA (retest 13 route, nhãn dài, submit lặp trên máy chủ) · **112 call site**
  còn lại (E6b 10 route + màn auth · E6c màn Thi + nút dựng bằng JS) · nút icon của header shell
  (`wujia-header-icon-btn`, 40×40, mọi route) để E6b làm một lần · `.wj-pc-btn` giữ cho Khảo sát =
  **LIMIT** (có test canh chiều ngược lại).
- Phiên kế: **E6b** — 10 route portal còn lại + màn auth (login/đổi mật khẩu/quên mật khẩu); việc
  cần biết trước: ma trận nghiệm thu `docs/e6a-acceptance-matrix.md`, sổ `MIGRATED` ở
  `custom/wujia_portal_base/tests/test_scan_e6_button.py`, và màn danh sách mobile **vốn 0 nút hành
  động** nên đừng đọc con số "mobile 40 action" của BA theo nghĩa đen.

## DOC-CTRL-2 — Đặc tả chi tiết controller cho BA (20/09/2026 · Mac)
- Kết quả: ✅ xong — `docs/controller-spec-detail.pdf` **110 trang / 10 chương**, mô tả **104/104
  đường dẫn** của **16 mô-đun**, gom thành **67 phiếu màn**. Phiên tài liệu: **0 file dưới
  `custom/`**, **0 lệnh ghi lên UAT**.
- Gốc yêu cầu: BA phản hồi bản kiểm kê 20 trang (DOC-CTRL 19/09) là "còn chung chung" — cần biết
  *màn sản phẩm đang lọc điều kiện gì, nút Đặt hàng đang check gì, danh mục portal lấy theo field
  nào*. Chủ dự án chốt: **cả 16 module có controller** (gồm Khảo sát của anh Thái + Metabase, chỉ
  ĐỌC) · **có** số thật trên UAT theo từng điều kiện lọc · tài liệu **MỚI** chia chương theo phân
  hệ · có mục **"ai xem được gì"** mỗi màn · **viết hết rồi giao một lần** · **không dán code Python
  vào file BA**.
- Đã làm:
  - **Khuôn "phiếu màn" 7 mục khoá từ chương 3**, không màn nào được thiếu: vào màn bằng đâu · ai
    xem được gì · màn hiện gì (bảng: khối · bảng dữ liệu · điều kiện lọc · sắp xếp · **thực tế
    UAT**) · người dùng lọc/nhập được gì · bấm nút thì kiểm gì (bảng **đúng thứ tự mã chạy**) · ghi
    gì vào hệ thống · điểm cần BA xác nhận (khung vàng).
  - **10 chương**: 1 cách đọc + bản đồ chương · 2 bản đồ 104 đường dẫn (máy sinh) · 3 Đặt hàng ·
    4 Khung portal + Trang chủ + quy ước dùng chung · 5 Lịch sử mua · Giao hàng · Báo cáo ·
    6 Công nợ · Đổi trả · 7 Hỗ trợ · Yêu cầu thông tin · Kiến thức · Thông báo · 8 Đăng ký thi ·
    9 Khảo sát (Thái) + Metabase · **10 Tổng hợp**.
  - **Chương 10** là thứ BA cần nhất: đối chiếu CT-001…CT-071 cập nhật (**56 ĐÃ CÓ · 6 MỘT PHẦN ·
    9 CHƯA CÓ**, nói rõ "một phần" thiếu luật nào) · 12 nhóm route có mã mà tab CT chưa mô tả ·
    **bảng 157 điểm cần BA chốt** gom từ mục 7 của mọi màn, phân 7 nhóm (PV/VT/NC/SL/DL/TB/CH) ·
    mục "BA đừng lên task viết lại".
  - **Bộ công cụ `scripts/qa/`** (đọc AST, không grep): `controller_spec.py` trích domain/ORM
    call/template/redirect/chuỗi kiểm · `uat_domain_probe.py` đếm thật qua XML-RPC **chặn cứng mọi
    method ghi** · `controller_spec_tex.py` sinh chương 2 · **`controller_spec_check.py` mới** kiểm
    chứng trước khi giao.
- Số đo: **147 phép đếm** trên UAT `wujia_tea_19` (chụp 20/09 01:18) · kiểm chứng
  `controller_spec_check.py`: phủ đường dẫn **104/104**, khuôn phiếu màn **67/67 đủ 7 khối**,
  **245 chỗ** dùng số UAT · build `lualatex` ×2: **110 trang, 0 hộp tràn, 0 ký tự thiếu**.
- Ba đính chính so với bản 19/09 (đã ghi ngay đầu chương 10):
  - **"Công nợ chưa nối `account.move`" KHÔNG còn đúng** — màn đang đọc hoá đơn và phiếu thu thật;
    điều cần chốt bây giờ là **cách tính kỳ và quy đổi tiền**, không phải nối dữ liệu.
  - **"Chưa dùng chung một hàm tải tệp" đúng một nửa** — thực tế **ba mức**: Đổi trả đọc nội dung
    thật của tệp · Hỗ trợ + Yêu cầu thông tin dùng chung một hàm nhưng chỉ tin lời khai trình duyệt ·
    Khắc phục khảo sát **không kiểm gì**.
  - **104 đường dẫn, không phải 103** — 2 đường dẫn có hai hàm (`/portal/exam/register`,
    `/portal/support/new`).
- Phát hiện đáng giá nhất (đều có số UAT kèm theo):
  - **Bốn cách hiểu "cửa hàng đang xem"** cùng tồn tại trong portal (bắt buộc chọn · cộng tất cả khi
    chưa chọn · luôn gộp · không phân biệt) và **ba cách chặn vai trò** khác nhau ⇒ gom thành **2
    quyết định** cho BA thay vì 25 câu hỏi lẻ.
  - **Ba phân hệ hiện không dùng được trên UAT vì thiếu dữ liệu**: Đổi trả **0 đơn** lọt cửa sổ 10
    ngày · Đăng ký thi **0 kỳ** đăng ký được (2 kỳ mở đều đã qua ngày thi) · Hỗ trợ **0 phiếu** do
    tài khoản cửa hàng thật tạo.
  - Công nợ: Home và màn Công nợ là **hai phép tính khác nhau** (ô tổng lưu sẵn, tiền công ty, mọi
    thời điểm ↔ tiền gốc chứng từ, một tuần) — giống nhau trên UAT chỉ vì **chưa cấu hình tỉ giá**.
  - Đổi trả: phiếu nháp là **ngõ cụt** (lưu được, không đường dẫn nào gửi được — 3 phiếu kẹt trên
    UAT) · **video tải lên không bao giờ hiện lại**.
  - `/portal/info-request/franchise/<id>/values` với loại "Khác" trả về **bất kỳ trường nào** của hồ
    sơ cửa hàng và **không kiểm vai trò** ⇒ Nhân viên đọc được số mà màn Công nợ đã chặn họ.
  - Chương 9 (mã anh Thái): **gửi khắc phục và lưu bài khảo sát không kiểm người gửi**; bảng
    Metabase **không khai nhóm quyền** nên ai đăng nhập cũng xem được.
- Lệch plan / quyết định mới:
  - Plan ước 110–140 trang, ra **110** — vì viết bằng lời nghiệp vụ, không dán mã.
  - Thêm chương kiểm chứng `controller_spec_check.py` (plan chưa có) để phép kiểm "phủ route" và
    "đủ 7 mục" chạy được bằng máy thay vì đếm tay.
  - Chương 2 (bản đồ route) **máy sinh lại mỗi lần thêm nhãn** — đã chạy lại 4 lần trong phiên.
- Bẫy trong phiên:
  - `probes.json` **trùng khoá** (`tb_toanhe`, `tb_daxem`, `kt_congbo`… đã có từ lượt Trang chủ) ⇒
    script dừng trước khi ghi, không để lại trạng thái dở; phải bỏ khoá trùng rồi chạy lại.
  - Chữ **`đ` đặt trong công thức toán** của LaTeX ⇒ lỗi build; phải viết "ký hiệu đồng Việt Nam".
  - Mục lục có **số trang 3 chữ số** ⇒ 9 hộp tràn; nới `\@pnumwidth`.
  - `execute_kw` của Odoo 19 nhận **`args = [domain]`**, truyền lồng thêm một lớp là
    `Domain() invalid item`.
- Nợ để lại: bản `controller-inventory.pdf` 20 trang **giữ nguyên** làm mục lục tổng · 4 con số UAT
  đo riêng (47 đơn · 60 ngày cửa sổ · 65 lượt xem · 86 điểm khảo sát) không nằm trong bảng đếm nên
  script chỉ cảnh báo, kiểm bằng mắt · **Q144/Q145/Q148/Q149/Q156** (mã anh Thái) dev phải trao đổi
  trực tiếp, chưa nói.
- Phiên kế: theo bảng §2 `docs/next-session-clusters-F.md` — cụm F tiếp tục. Việc cần biết trước:
  42 điểm nhóm **CH** trong chương 10 chính là danh sách chuẩn hoá cụm F đã có bằng chứng số, dùng
  thẳng được làm đầu vào; và **BA không lên task cho nhóm CH**.

## E6b1 — Button `CMP-BTN-001`: nghiệp vụ còn lại + Công nợ + luật ranh giới thanh lọc (20/09/2026 · Mac)
- Kết quả: ✅ xong lượt E6b1 — `UI-BUTTON-001` (STT 132, dòng 125) **vẫn mở**, đóng ở E6c.
- Chốt đầu phiên của chủ dự án: chia E6b thành **E6b1** (nghiệp vụ + Công nợ) → **E6b2** (Đặt hàng/giỏ
  + màn auth, submit 50→46) · nhóm "nửa boundary" **xử lý nhiều nhất có thể** · atom Primary đổi sang
  **#0F7CA8** thay vì #28A9DF của BA (giữ chuẩn a11y, sửa một chỗ) · cuối phiên **commit + push `main`,
  KHÔNG deploy UAT**, issue vẫn mở.
- Đã làm:
  - **32 call site / 11 file / 7 module** về atom: Giao hàng 6 · Thư viện 3 · Yêu cầu thông tin 5 ·
    Lịch sử mua 2 · Nền portal 5 (store picker, danh sách/hồ sơ cửa hàng) · **Công nợ 10**.
  - **Luật ranh giới thanh lọc** — trả lời câu "làm sao đồng bộ": cùng file `portal_debt.xml`, cùng
    class `wj-pc-btn--primary` vừa là nút lọc (giữ 42 theo FB-08) vừa là nút hành động (về 40 theo
    CMP-BTN-001) ⇒ đồng bộ theo **ngữ cảnh** ở 4 tầng: token hoá 42/38/32 · CSS khai theo ngữ cảnh
    (`.wj-debt-pc-filter .wj-pc-btn`) · thước đo nhận diện theo **tổ tiên DOM** thay vì tiền tố class ·
    **test bắt chéo hai chiều** (không nút lọc nào được mang atom · từng khối CSS nút lọc phải đọc token).
  - **Vá 8 lỗi a11y thật**: 4 nút sao chép công nợ, 2 nút đóng modal, 2 nút xem chi tiết nay có
    `aria-label` tiếng Việt; 2 nút icon navbar (chuông, giỏ) cũng được đặt tên dù giữ boundary.
  - **Sửa bẫy "Pass rỗng" của chính thước đo** (phần nặng nhất phiên): lần đo đầu xanh nhưng **6/9
    route trong sổ ra 0 nút** — sổ ghi sai route (`/portal/franchise-information` render template
    khác), nút chỉ dựng ở khối rỗng, bảng yêu cầu **0 bản ghi**, màn lịch sử thanh toán vốn không có
    nút. Sửa cả sổ lẫn luật: route trong sổ mà không dựng nổi nút nào ⇒ **vi phạm**; so route bằng
    chuỗi đầy đủ; so URL sau khi giải mã `%`; **màn chi tiết dò lúc chạy** từ trang danh sách.
  - **`scratchpad/e6b1/overlay_probe.py`**: 5 call site nằm trong lớp phủ (store picker, modal thanh
    toán) không route nào thấy vì mặc định ẩn ⇒ probe mở lớp phủ rồi đo bằng đúng PROBE của thước đo.
- Số đo: thước đo **18 route × 5 khổ, 0 vi phạm · 0 lỗi JS**, **278 ô atom** đúng 6 con số BA (PC 32/40,
  mobile 36/44/48, radius 8/12, chạm mobile nhỏ nhất 44); zoom 200% (720/512) **0 vi phạm**; lớp phủ
  **0 vi phạm** · suite **714 tests, 0 đỏ** (mốc E6a 708, +6 test mới) · mutation **8/8 mũi đỏ đúng
  guard** · `wj_filterbar` **ĐẠT** · `wj_measure` 0 tràn/0 lỗi JS/0 redirect/0 HIERARCHY · `wj_listcard`
  0 · `wj_nesting` 0 · `b4_regression` **286/286** · `check_layers` 3 R1–R5 + 2 R7 **có sẵn, không thêm**.
- Lệch plan / quyết định mới:
  - **LIMIT** nút icon navbar (chuông + giỏ) **là boundary** — plan định migrate, đo ra 96 vi phạm:
    `_pc_account.css` cố ý cho hai nút 40×40 bo 20 nền kính để thắng padding `.nav-link` của Vuexy.
    Cùng loại BottomNavigation mà BA đã liệt boundary ⇒ giữ nguyên, ghim bằng test.
  - **LIMIT** `/my/franchises` dùng khung `portal.portal_layout` của Odoo, CSS design system không nạp
    ở đó nên atom ra **nút trần** ⇒ trả lại Bootstrap; bản Vuexy `/portal/franchises` mới là atom.
  - **IMPACT** atom Primary `#28A9DF` → `#0F7CA8` (BA ghi màu trượt WCAG AA 2.68; #0F7CA8 = 4.7 và đã
    là CTA portal từ Sprint 38) — **ảnh hưởng ngược 21 call site của E6a**, đã chụp lại đối chiếu:
    chỉ màn có nút Primary đổi, 2 màn danh sách giống hệt từng byte.
  - Số call site **32** chứ không phải 34 của plan (trừ 2 nút navbar); Công nợ **10/13** chứ không 11.
  - `btn-outline-danger` → `wj-btn--danger` đặc (BA không có bậc outline-danger).
  - Sửa 2 sổ của cụm khác cho khớp: F4 bỏ dòng `wj-debt-pc-pdf wj-state-surface` (nút đã về
    `--secondary`, variant nằm sẵn trong danh sách bề mặt) · E4 đổi ghim `38px` cứng sang ghim **token**.
- Nợ để lại: **E6b2** Đặt hàng/giỏ (25 action) + màn auth (submit 50→46) · **E6c** màn Thi + gạch 12
  của BA + **một lần deploy UAT** rồi đóng issue · sổ thước đo còn 2 route phụ thuộc dữ liệu mẫu.
- Phiên kế: **E6b2** — việc cần biết trước: `/portal/order` có 25 action và **JS dựng nút giỏ**, phải
  grep `querySelector` trước khi đổi class; màn auth nằm ngoài vỏ portal nên kiểm CSS có nạp không
  (bài học `/my/franchises` phiên này).

## E6b2 — Button `CMP-BTN-001`: màn Đặt hàng/giỏ + toàn bộ màn auth (21/09/2026 · Mac)
- Kết quả: ✅ xong lượt E6b2 — `UI-BUTTON-001` (STT 132, dòng 125) **vẫn mở**, đóng ở E6c.
  Nghiệm thu đầy đủ: `docs/e6b2-acceptance-matrix.md`.
- Chốt đầu phiên của chủ dự án: **auth migrate hết, kể cả khối legacy tiếng Anh** · nút thêm-vào-giỏ
  theo hàng **là boundary** cùng thể với stepper · cuối phiên **commit + push `main`, KHÔNG deploy UAT**,
  issue vẫn mở (E6c gộp một lần deploy).
- Đã làm:
  - **19 call site / 6 file / 2 module** về atom: giỏ mobile 3 · panel giỏ PC 3 · chi tiết sản phẩm 2 ·
    `login_page.xml` 6 (đăng nhập · 2FA · quên MK · đặt lại MK · 2 nút khối đăng ký) · `forgot_pass.xml` 2 ·
    đổi mật khẩu 3. Plan ghi 20 — đếm nhầm cặp Hủy/Lưu PC.
  - **Xoá hẳn họ `wj-cta-btn`** (31 dòng `_components.css`): sau E6b1 chỉ còn đúng một người dùng.
  - **Luật móc JS** (kế thừa E6b1): grep ra đúng **2** tên JS bám (`btn-add-cart-detail`,
    `wujia-mcart-submit`) ⇒ giữ tên, **gỡ sạch khai dáng**; 4 tên còn lại không ai bắt ⇒ chỉ giữ bố cục.
    Test ghim cả hai vế: móc còn đủ hai phía **và** móc không được khai `height/radius/background/font-*`.
  - **Thước đo đo được màn chưa đăng nhập**: thêm danh sách `ANON` chạy trong context trình duyệt sạch
    sau vòng chính (+ cờ `--no-anon`), và **in mã HTTP** khi trang không trả 200.
  - **Vá a11y**: 2 nút xóa dòng giỏ (mobile + PC) nay có `aria-label`/`title` tiếng Việt.
- Số đo: thước đo **29 route × 5 khổ, 0 vi phạm · 0 lỗi JS**, **338 ô atom** (PC 32×219 / 40×57 / 46×12;
  mobile 36×8 / 44×30 / 48×12; radius 8×227 / 12×111; chạm mobile nhỏ nhất **44**); zoom 200% (720/512)
  **0 vi phạm**; trạng thái giỏ rỗng đo riêng bằng `anh.owner` **4 action / 4 atom / 0 vi phạm** · suite
  **722 tests, 0 đỏ** (mốc E6b1 714, +8 test mới) · mutation **11/11 mũi đỏ đúng guard** · `wj_filterbar`
  **ĐẠT** · `wj_measure` 0 tràn/0 lỗi JS/0 HIERARCHY · `wj_listcard` 0 · `wj_nesting` 0 · `b4_regression`
  **286/286** · `check_layers` 3 R1–R5 + 2 R7 **có sẵn, không thêm**.
- Lệch plan / quyết định mới:
  - **IMPACT 1** submit màn auth PC **50 → 46** (bậc `lg` của BA), mobile giữ **48**. Nhịp dọc Figma S39
    giữ nguyên: `.wj-auth-submit` chỉ còn `margin-top` 21 / 20.5px.
  - **IMPACT 2** nút *Lưu mật khẩu* mobile **46 → 48** (46 là số PC dùng nhầm cho mobile).
  - **Cơ chế đã giữ nút auth ở 50px**: `_auth.css` nạp **SAU** `_components.css` nên mọi khai dáng sót lại
    đều thắng atom. Màn auth **có** nạp design system (`login_layout` → `asset_frontend`) ⇒ không phải
    bẫy `/my/franchises` của E6b1, không cần đụng asset bundle.
  - **LIMIT** ba template auth `signup`, `login_totp`, `forgot_pass_back` **không controller nào render** —
    vẫn migrate cho đồng bộ nhưng **không có bằng chứng đo bằng trình duyệt**; ghim bằng test: ngày nào
    có controller render, test đỏ để bắt đi đo thật.
  - **Variant `ghost` tự khai trạng thái nhấn**, không mượn marker `wj-state-surface` của F4 (danh sách bề
    mặt `_interaction.css` hover thêm viền + bóng, sai dáng nút icon trong hàng). F4 đếm marker ở 2 file giỏ
    **3 → 2**, đúng tiền lệ E6b1 với nút PDF công nợ.
  - **`/portal/forgot-pass` có `rate_limit` 10 lần/giờ theo IP** (`auth.py:89`) — đo lặp là **HTTP 429**, và
    thước đo cũ báo nhầm thành "không có nút hành động nào". Bộ đếm trong RAM, khởi động lại server là sạch.
  - **Bẫy "Pass rỗng" phiên bản trạng thái**: nút *Gửi đơn*/*Xóa dòng* chỉ có khi giỏ **có hàng**, CTA
    *Chọn sản phẩm* chỉ có khi giỏ **rỗng** ⇒ phải đo bằng **hai tài khoản**.
- **Phát hiện ngoài phạm vi (chưa sửa)**: `/portal/login` **tràn ngang 74px** ở khổ 390 (`scrollWidth` 464),
  do `.wj-auth__decor--1` (mép phải 479px) + cụm đổi ngôn ngữ. Ảnh **trước/sau giống hệt** ⇒ lỗi có sẵn,
  không do E6b2; cụm auth đang **KHÓA THIẾT KẾ S39** nên cần duyệt trước khi động.
- Nợ để lại: **E6c** màn Thi (30 nút XML + nút dựng bằng JS) + gạch **12** của BA + **một lần deploy UAT**
  rồi đóng issue, kèm quyết định về tràn ngang màn đăng nhập · 3 template auth chết · cụm **EmptyState**.
- Phiên kế: **E6c** — việc cần biết trước: màn Thi có nút **dựng bằng JS** (không grep XML là đủ);
  deploy UAT phải gộp `-u` của cả E6a + E6b1 + E6b2; trước khi đo lại màn auth trên máy chủ nhớ
  `rate_limit` 10 lần/giờ.

## E6c — Button `CMP-BTN-001`: màn Thi + gạch 12 + khép `UI-BUTTON-001` (23/09/2026 · Mac)
- Kết quả: ✅ xong lượt cuối cụm E6 — code + doc **đã push `main`**, **chờ chủ dự án deploy UAT** rồi mới
  `qa_sync` đưa `UI-BUTTON-001` (STT 132, dòng 125) sang Ready for Retest. Nghiệm thu: `docs/e6c-acceptance-matrix.md`.
- Chốt đầu phiên của chủ dự án: ô ngày/khung giờ/FAB/nút lùi wizard màn Thi **là boundary nhưng đọc token
  `--wj-btn-*`** (để sau này đổi token một chỗ là theo) · **vá tràn ngang màn đăng nhập** (IMPACT) ·
  **commit + push `main`, anh tự deploy**.
- Đã làm:
  - **30 call site màn Thi** về atom: 21 `.wj-btn` + 7 `.wj-iconbtn` trong `portal_exam.xml`, 2 `.wj-iconbtn`
    dựng bằng JS (sửa/xóa dòng người thi). Xoá hẳn họ `wujia-mexam-btn*`, `wj-exam-pc-navbtn`,
    `wj-exam-pc-iconbtn`, `wujia-mexam-cal-navbtn`, `wujia-mexam-person-del`.
  - **Boundary đọc token**: 5 khối CSS (ô ngày PC/mobile, ô khung giờ PC/mobile, FAB) bỏ số px cứng; trạng
    thái *đang chọn* dùng `--wujia-cta` như primary của atom.
  - Gửi đăng ký (PC + wizard mobile) dùng `setBusy()` = `.is-loading` của atom thay kiểu đổi chữ.
  - **Màn đăng nhập hết tràn ngang** 464 → 390: gốc là **tên ngôn ngữ** (thêm ở `WJ-LANG-001`) nhét vào pill 72px
    của Figma, bóp cờ còn 3px và đẩy chữ ra ngoài mép; ở điện thoại nay ẩn mắt tên ngôn ngữ (trình đọc màn hình
    vẫn đọc), cờ đủ 20px, bỏ caret Bootstrap trùng; `overflow-x` trên `.wj-auth` giữ làm lưới an toàn.
  - **Guard mới** `test_class_di_kem_atom_khong_gianh_dang` (sổ chung portal_base): class đứng cùng phần tử với
    atom cũng không được khai dáng — mũi M8 lần đầu lọt qua guard cũ.
  - Gạch 12: `scratchpad/e6c/bullet12.py` — 13 route × nhãn dài VI/EN/ZH × 3 khổ, submit lặp (form + fetch,
    không gửi thật), Enter/Space.
- Số đo: `wj_button` **32 route × 5 khổ, 0 vi phạm · 0 lỗi JS**, **358 ô atom** (PC 32×225 / 40×69 / 46×12;
  mobile 36×8 / 44×30 / 48×14; radius 8×233 / 12×125); zoom 200% **0 vi phạm**; từng trạng thái màn Thi
  (`exam_states.py`) **0 vi phạm** · suite **729 tests, 0 đỏ** (mốc E6b2 722, +7) · mutation **10/10** ·
  `wj_measure` trước/sau (stash) **0 dòng khác** · `wj_filterbar` **ĐẠT** · `wj_listcard` 0 · `wj_nesting` 0 ·
  `b4_regression` **286/286** · `check_layers` 2 R7 có sẵn, không thêm · gạch 12: submit lặp **1 request**
  giữ bề rộng (form 136,6px · fetch 174px), bàn phím **28/28**.
- Lệch plan / quyết định mới:
  - **2 LIMIT nhãn dài**: nút *Xem* trong dòng bảng PC (Giao hàng, Công nợ) làm bảng cuộn ngang **bên trong**
    khung bảng — hành vi DataTable, trang không cuộn; nhãn EN 44 ký tự ở nút full-width khổ 360 dư 6px — BA chốt
    "một dòng, không giảm font" nên đặt quy ước nhãn ≤ 40 ký tự Latin.
  - **IMPACT**: FAB `#28A9DF` → `#0F7CA8`; ô ngày mobile 38 → 36; ô ngày PC bo 6 → 8; ô khung giờ mobile ~51 → 48;
    nút đóng modal về ghost 32px (đồng bộ Công nợ/chọn cửa hàng); nút đổi tháng PC 32×28 → 32×32.
  - **LIMIT** nút lùi wizard mobile chạm 28×30 — thuộc BackPageHeader (`UI-BACKPAGEHEADER-001`), không đổi dáng ở E6.
- **Bài học môi trường đo**: `wj_filterbar` báo CHƯA ĐẠT, chạy lại trên HEAD (stash E6c) **y hệt** ⇒ không do E6c.
  Gốc: `wj_ajax_list.js` lọc bằng `fetch` + `pushState`, server đang `--dev=xml` nên một lượt lọc mất 3,1 giây,
  quá thời gian chờ của thước đo. **Đo giao diện luôn dùng server không `--dev=xml`** (cần nạp view thì `-u` rồi
  khởi động lại).
- **Retest UAT 24/09** (anh deploy; 12/12 module khớp `latest_version` qua XML-RPC chỉ-đọc). Chạy qua
  `scratchpad/e6c/uat_guard.py` (chặn mọi POST ngoài login + 4 route chỉ-đọc; **0 POST phải chặn**):
  `wj_button` **30 màn × 5 khổ + zoom 200%, 175 lượt atom, 0 vi phạm nút · 0 lỗi JS** (PC 32/40/46, mobile
  36/44/48, radius 8/12) · trạng thái màn Thi **0** · login 360/390/1440 hết cuộn ngang (3 route) · submit lặp
  1 request giữ bề rộng (136,5 / 174) · bàn phím **18/18** · nhãn dài: 5 ghi nhận đều thuộc 2 LIMIT cũ.
  Vi phạm tổng là môi trường: UAT chưa có `wujia.info.update.request` nào + em.hcm/anh.owner không có công nợ
  (màn chi tiết YC thông tin, `/portal/debt*` chỉ đo được local — ghi LIMIT); `/portal/forgot-pass` trả 429 vì
  chính các lượt đo chạm `rate_limit` 10/giờ. `wj_button` dò màn động hụt thì giữ placeholder ⇒ trên UAT phải
  truyền `--routes` bỏ placeholder đó. `qa_sync` UI-BUTTON-001 → **Ready for Retest**.
- Nợ để lại: nút lùi wizard 28×30 (BackPageHeader); cụm **EmptyState**; 3 template auth chết (E6b2).
- Phiên kế: sau khi UAT xác nhận E6 ⇒ **E7a** PageContainer `CMP-PC-001` (`UI-PAGECONTAINER-001`, STT 129).

## E7a — PageContainer `CMP-PC-001`: khung + gutter (24/09/2026 · Mac)
- Kết quả: ✅ xong lượt đầu cụm E7 — code + doc **commit local, chưa push**; `UI-PAGECONTAINER-001` (STT 129,
  dòng 122) **giữ Ready for Dev** tới E7b. Nghiệm thu: `docs/e7a-acceptance-matrix.md`.
- Chốt đầu phiên của chủ dự án: **E7a trước, phân cụm 140–145 sau E8** (143/145 đo lại trên khung mới) ·
  **sửa tối thiểu vỏ Khảo sát** (code anh Thái, chỉ vỏ, không logic) · **lề mobile: danh sách 12, còn lại 16**.
- Đã làm:
  - `app_layout` có **một** `<main class="wj-page-container">` bọc `t-out="0"`; Global Shell (header mobile,
    sidebar, bottom-nav) nằm ngoài. 4 token `--wj-page-gutter*` / `--wj-page-pad-bottom`.
  - `.content-wrapper` về 0 ở **mọi khổ** (mốc cũ 24px chỉ ở ≥1200 ⇒ 992–1199 rơi về Vuexy 30,8).
    Bỏ lề `.wujia-mpage`, `.wj-debt`, `.wujia-mhome`, `.wujia-home-wrapper`, đáy 96 của `.app-content`.
  - Biến thể `wj-page-container--list` (12) bật bằng `t-set pc_gutter='list'` ở **12 màn danh sách**.
  - **Gốc "tiêu đề lệch 16px" của BA**: rule không phạm vi `.wj-page-header {padding 16px !important}` trong
    `portal_inspection.css` (`ad7ffc3`, 07/08) đè PageHeader của **mọi** màn. Gỡ + guard.
  - Khảo sát: vỏ danh sách/chi tiết/khắc phục bỏ lề ngang + nền (`py-*` giữ nhịp dọc), bỏ max-width + `min-height:100vh`.
  - Thước đo mới `scripts/qa/wj_pagecontainer.py` (7 kiểm PC-1…PC-7, `--diff`, `--collapsed`).
  - Guard: `wujia_portal_layout/tests/test_e7_page_container.py` (11) + sổ chung
    `wujia_portal_base/tests/test_scan_e7_page_container.py` (6, gồm cấm class `p-*`/`px-*` trên vỏ route).
- Số đo: `wj_pagecontainer` 31 route × 6 khổ **707 → 0 vi phạm · 0 lỗi JS**; sidebar thu gọn **0**; zoom 200%
  **0** · suite **746 tests, 0 đỏ** (mốc E6c 729) · mutation **13/13** · `wj_measure` so E6c: 0 tràn/0 lỗi JS/
  0 redirect/0 HIERARCHY, **0 ô mất record**, chiều cao chỉ đổi trên trục đã duyệt · `wj_button` 0 ·
  `wj_listcard` 0 · `wj_filterbar` ĐẠT · `wj_nesting` 0 · `b4_regression` **286/286** (bản thay ID) ·
  `check_layers` 2 R7 có sẵn, không thêm.
- Lệch plan / quyết định mới:
  - **LIMIT** đệm đỉnh mobile 10 (token nhịp dọc 18/09), không phải 16 của spec — đổi một token nếu BA muốn.
  - **LIMIT** chưa có `bottomInset` cho sticky action (giỏ giữ đáy 150 riêng) ⇒ E7b.
  - Plan ghi "Khảo sát không đụng" ⇒ chủ dự án duyệt sửa tối thiểu; bàn giao anh Thái ở matrix.
  - `pc_account_layout` là partial trong `app_layout` ⇒ không cần vỏ riêng.
- **Bài học đo**: `b4_regression.py` dùng ID cứng — DB local đã mất `return/12`, `notification/41`, anh.owner
  hết giao hàng ⇒ báo 270/286 giả. Chạy lại bằng ID dò từ màn danh sách (`scratchpad/e7a/b4_local.py`).
  Thước đo gutter phải bỏ qua lề Bootstrap `.row`/`col-*` và cột phải của lưới, không thì báo nhầm.
- Nợ để lại: Khảo sát chi tiết/khắc phục chưa đo sống (DB local 0 phiếu) · sidebar overlay 992–1199 (E8) ·
  PC chi tiết Khảo sát có thể hiện hai tiêu đề (báo anh Thái).
- Phiên kế: **E7b** — width variant `fluid/standard 1440/narrow 960` + `bottomInset` + đo UAT chỉ-đọc ⇒ đóng
  `UI-PAGECONTAINER-001` (Ready for Retest). Cần deploy E7a+E7b cùng lượt.

## E7b — PageContainer `CMP-PC-001`: width variant + bottomInset (24–25/09/2026 · Mac)
- Kết quả: ✅ khép cụm E7 — `UI-PAGECONTAINER-001` (STT 129, dòng 122) **Ready for Retest** 25/09 sau đo UAT. Nghiệm thu: `docs/e7b-acceptance-matrix.md`.
- Đã làm:
  - `app_layout` thêm 2 công tắc cùng kiểu `pc_gutter`: `pc_width` (`standard` 1440 / `narrow` 960, fluid = không đặt) và
    `pc_bottom='sticky'`. Max-width đặt **trên chính `<main>`** (bề rộng trong + 2 gutter, căn giữa) ⇒ PageHeader cùng
    bề rộng nội dung, không thêm lớp DOM.
  - Cờ theo mapping BA ở **29 template**: narrow 4 (giỏ, tạo bù hàng, tạo hỗ trợ, tạo YC thông tin), standard 25
    (Bù hàng danh sách, Tài khoản, hồ sơ cửa hàng, mọi màn chi tiết, Khảo sát chi tiết/khắc phục…), còn lại fluid.
  - Đáy: gỡ đáy **chồng** của Đặt hàng (`.wujia-morder` 150) và giỏ (`.wujia-mcart` nav+116); container `--sticky`
    = nav + `--wj-sticky-action-h` (68 floatbar; giỏ khai 200 qua `:has(.wujia-mcart-summary)`) + gap 16.
  - Gỡ `.wj-pc-cart-standalone {max-width:760}` — bề rộng trang thuộc container.
  - Thước đo `wj_pagecontainer.py`: trục x đo từ **mép container** (narrow căn giữa), thêm **PC-8 WIDTH**, in biến thể.
  - Guard +10: `test_e7_page_container.py` (4) + sổ `test_scan_e7_page_container.py` (6: sổ width theo mapping, cấm
    narrow cho danh sách, cấm max-width ≥600 trong CSS route trừ 2 component, cấm route tự chừa đáy, sticky bật đúng màn).
- Số đo: `wj_pagecontainer` 31 route × **7 khổ (thêm 1920)** 0 vi phạm · 0 lỗi JS; sidebar thu gọn 0; zoom 200% 0 ·
  `--diff` **0 ô mật độ giảm** · narrow 960 @1024/1440/1920, standard 1440 chỉ @1920 · suite **756, 0 đỏ** (E7a 746) ·
  mutation **10/10** · `wj_measure` 0 ô mất record · `wj_button` 0 · `wj_listcard` 0 · `wj_filterbar` ĐẠT · `wj_nesting` 0 ·
  `b4` **286/286** · `check_layers` không thêm · `test_ownership` cross 0.
- IMPACT: giỏ PC 760 → 960 căn giữa; 3 form tạo mới thu về 960 căn giữa ở ≥1024; Đặt hàng mobile ngắn 79px.
- LIMIT: Khảo sát chi tiết chưa đo sống (0 phiếu local); chiều cao thanh sticky là token khai báo; `:has()` cần Safari 15.4+.
- Bài học: `b4_local.py` mặc định cổng 8055 — phải `--base http://127.0.0.1:8090`. Test chạy không `-u` chết ở
  `wujia_franchise/tests` (import file đã xoá) — luôn kèm `-u`. Log test bị `wujia_core` chuyển sang `<logdir>/<năm>/<tháng>/`.
- **UAT 25/09** (sau deploy, chỉ-đọc, 0 POST): 217 ô 0 vi phạm · thu gọn 0 · zoom 0 · **Khảo sát chi tiết/khắc phục đo sống
  0** (đóng LIMIT). Commit `419f9c9` (+`8ef3081`) đã push. Ledger + `qa_sync --apply` ⇒ `UI-PAGECONTAINER-001` **Ready for Retest**.
- Báo Thái: Khảo sát chi tiết PC có **2 tiêu đề** (`wj_page_header` + `.wj-pc-page-header` tự dựng, từ `2828171`) — thuộc PageHeader.
- Bài học: route `wujia_portal_inspection` trên UAT chuyển `/vi/…` ⇒ đo bằng `/vi/portal/inspection…`.
- Phiên kế: **E8** SidebarNavigation (`UI-SIDEBAR-001`).

## E8a — SidebarNavigation `CMP-SN-001`: đo hiện trạng, 0 code (25/09/2026 · Mac)
- Kết quả: ✅ xong lượt đo. `UI-SIDEBAR-001` (STT 131) **giữ Ready for Dev** tới E8b. Kiểm kê: `docs/e8a-sidebar-inventory.md`.
- Đã làm: đo local (`wujia_e4b1`, 8090) + UAT chỉ-đọc (`uat_guard`), `em.hcm`, 9 khổ, 32 route. **UAT khớp local tuyệt đối.**
  - **Width 264 chỉ cần CSS**: đổi token ⇒ `.main-menu` 264, content +36px (1140→1176), JS Vuexy không ghi đè
    (`$.app.menu.init/change` đã no-op ở `my_js.js`).
  - **Drawer 992–1199 kẹt mở**: gốc là `_wujiaForceMenuExpanded()` (`my_js.js:284`) ép `menu-open` ở ≥992 mỗi lần
    load/resize; hamburger nằm dưới drawer 260px nên không bấm được; toggle/Escape/bấm ngoài đều không đóng; 0 backdrop,
    2 `.sidenav-overlay` trùng.
  - **Q3**: sidebar PC **không có** mục Bù hàng (plan cũ ghi có `nav_item_return` là sai) ⇒ `/portal/return*`,
    `/portal/reports/orders`, `/portal/info-request*` không sáng mục nào; 29/32 route còn lại sáng đúng mục cha.
  - Item: cao 44 ✓, icon 20 ✓, focus ✓; lệch: đệm `10px 15px`, gap 26, bo 8/active 4, chữ 16/400, màu active `#28A9DF`,
    không rail, 0 `aria-current`. Brand 132px, logo 184×86. Hamburger 0 accessible name.
  - Chuông PC đạt (badge = unread thật, popup + "Xem tất cả", Escape); avatar dropdown 4/7 mục BA; tên gọi lệch PC↔mobile ở 3 route.
- Commit: chưa commit (chỉ doc).
- Deploy: không.
- Số đo: `sidebar_probe` 9 khổ × 2 môi trường 0 lệch · 0 lỗi JS · UAT 1 POST chặn (`/notification/recent`, do cú bấm chuông của thước đo).
- Lệch plan / quyết định mới: plan ghi 12 `sidenav_inherit`, thật **10** (F5a); Bù hàng/Báo cáo là **tạo mới** mục PC,
  không phải đổi nhãn. Dời Khảo sát xuống cuối nhóm bằng `position="move"` (Odoo 19 hỗ trợ), không sửa file anh Thái.
- Quyết định mới: chủ dự án chốt "chuẩn hoá bám BA hết" ⇒ 5 điểm tưởng là fork đều chốt theo câu BA (§4 kiểm kê):
  avatar đủ 7 mục + gỡ dropdown ngôn ngữ riêng (khối cửa hàng giữ cho STT 140) · quyền = điều kiện controller · info-request
  sáng "Hồ sơ cửa hàng" trong avatar · bỏ hover trượt · <992 `display:none`.
- Nợ để lại: báo BA `/portal/info-request` không có lối vào nào trong UI (ngoài E8, cần issue riêng).
- Phiên kế: **E8b** code theo §2–§3 kiểm kê. Test khoá sidebar phải sửa cùng lượt: `test_f5_nav_item.py` ×9,
  `test_f5_menu_ownership.py`, `test_f5_frame_routes.py`; chụp lại mốc `nav_dump`.

## E8b — SidebarNavigation `CMP-SN-001`: sidebar PC + drawer 992–1199 (25/09/2026 · Mac)
- Kết quả: ✅ xong lượt code. `UI-SIDEBAR-001` (STT 131) **giữ Ready for Dev** tới E8c. Nghiệm thu: `docs/e8b-acceptance-matrix.md`.
- Cụm E8 chia **3 phiên** (chủ dự án chốt 25/09): E8a đo · **E8b sidebar PC + drawer** · E8c avatar/mobile/UAT/ledger.
- Đã làm:
  - Khung `layout_sidenav` chỉ còn 4 neo (`nav_header_main` / `_finance` / `_ops` / `nav_end`) — 3 nhóm BA "Chức năng chính ·
    Tài chính & xử lý · Hỗ trợ vận hành". Gỡ nhóm Tiện ích + Tài khoản (về avatar), spacer, `mb-5`, logo 200×100, overlay trùng.
  - 10 module sở hữu route tự khai mục (`before` neo nhóm kế): Giao hàng lên trước Lịch sử · "Công nợ & thanh toán" ·
    **mới** "Đổi trả / Bù hàng" (return) + "Báo cáo" (report) · Thông báo rời sidebar (chuông). Quyền = điều kiện controller:
    Công nợ theo `_debt_access`, Báo cáo theo vai trò cao nhất owner/manager — `_nav_mgr_fids` tính 1 lần/trang ở `base`.
  - **Sửa tối thiểu file anh Thái** (`wujia_portal_inspection/views/sidenav_inherit.xml`, chủ dự án duyệt, tiền lệ E7a): neo
    `nav_end` + `wj_nav_item`; ghi bàn giao trong matrix.
  - `wj_nav_item` có `aria-current`. `_sidebar.css` mới giữ mọi dáng sidebar (264, brand 88, mục 44/10/12/15-22-500, bo 10 mọi
    state, active 700 `#EAF7FD`/`#168FC2` + rail 3, hover không trượt, nhóm rỗng tự ẩn, drawer, ẩn <992).
  - Drawer 992–1199: `my_js.js` chỉ ép mở ≥1200; `wujia_sidebar.js` mới (hamburger `<button>` đủ aria, nút Đóng, Escape,
    backdrop, focus vào/ra). Migration `pre-10` xoá view con của `layout_sidenav` (neo cũ mất ⇒ view cũ hỏng validate).
- Commit: local `feat(E8b)`, chưa push. Deploy: **không**.
- Số đo: `wj_sidebar` (mới, `scripts/qa/`) **0 vi phạm** × 4 vai trò, 9 khổ, 21/21 route sáng đúng + `aria-current`, 7 route
  ngoài sidebar sáng 0 · suite **779, 0 đỏ** (E7b 756) · mutation **14/14** · DB trắng chỉ cài khung 0 failed / 1 error (nợ F6
  có sẵn) · `wj_pagecontainer` 0 · `wj_button` 0 · `wj_listcard` 0 · `wj_filterbar` ĐẠT · `wj_nesting` 0 · `b4` 286/286 ·
  `check_layers` không thêm · `test_ownership` cross 0 (asserts 425 → 491) · `nav_dump` 9 route đổi mục sáng, đều chủ đích;
  mốc mới `docs/e8b-baseline/nav_em.json`.
- Lệch thước đo (không phải hồi quy): `wj_measure --diff` 26 ô "mất record" ở 360/390 = đúng 14 `li` sidebar cũ bị đếm
  khi còn nằm ngoài màn; `wj_button` thêm boundary `wj-menu-toggle`/`wj-sidebar` (hamburger nay là `<button>`).
- Bài học: đột biến ở module X mà guard ở `portal_base` ⇒ `-u X,wujia_portal_base`, không thì **0 test chạy** (Pass rỗng) ·
  test phải kèm `--db-filter='^wujia_e4b1$'` (config lọc `wujia_tea_19` ⇒ HttpCase rơi về trang login) · `style.css:96`
  đặt `.main-menu` z-index 1040 !important — drawer phải 1041 mới trên backdrop · focus vào drawer phải đợi hết transition.
- LIMIT: sheet "Thêm" mobile có Báo cáo không điều kiện vai trò (E8c) · ẩn nhóm rỗng cần Safari ≥ 15.4 (`:has`).
- Phiên kế: **E8c** — avatar dropdown 7 mục + gỡ dropdown ngôn ngữ topbar + `aria-expanded` chuông + avatar/sheet mobile
  + tên gọi PC↔mobile + deploy E8b+E8c + đo UAT chỉ-đọc (`wj_sidebar --base` UAT) + ledger/`qa_sync` ⇒ Ready for Retest.

## E8c — `UI-SIDEBAR-001` avatar dropdown · sheet "Thêm" mobile · chuông (25/09/2026 · Mac)
- Kết quả: ✅ **xong cụm E8**. Push `main` (`078dfeb`), chủ dự án deploy UAT (lượt 2 — lượt 1 `-u` khi máy chủ chưa có
  mã, 13/13 module vẫn bản E7b), đo UAT chỉ-đọc `em.hcm` 0 vi phạm, ledger + `qa_sync` ⇒ **`UI-SIDEBAR-001` Ready for Retest**
  (đã đọc lại CSV đúng dòng STT 131).
  Nghiệm thu: `docs/e8c-acceptance-matrix.md` (12/12 ý "Kết quả mong muốn").
- Chủ dự án chốt: ngôn ngữ **giữ trên header PC + mobile** (CMP-GH-001) **và** có nhóm trong avatar (huỷ chốt E8a gỡ
  dropdown topbar) · "Thông tin cửa hàng" → **"Hồ sơ cửa hàng"** ở menu + tiêu đề trang.
- Đã làm:
  - `wj_acct_menu_items` (mới, khung): thân menu avatar **dùng chung PC + mobile** — Thông tin tài khoản · Đổi mật khẩu ·
    Ngôn ngữ · neo `data-wj-anchor="acct_store_end"` · Đăng xuất. Nút avatar đủ aria.
  - `base`: một inherit chèn nhóm cửa hàng (mã/tên/chip vai trò · Đổi cửa hàng khi >1 · Hồ sơ cửa hàng sáng cả ở
    info-request); xoá `mheader_inherit.xml`. `_nav_mgr_fids` dời lên `app_layout` (1 lần/trang).
  - Sheet "Thêm": bỏ Hồ sơ cửa hàng + Tài khoản/Cài đặt; neo mới `msheet_end`; Công nợ + Báo cáo theo quyền như sidebar.
  - Chuông: `aria-controls`/`aria-expanded` + JS đồng bộ, Escape trả focus. Migration `19.0.58.0.0/pre-10`.
- Commit: `078dfeb feat(E8c)` đã push cùng E8a/E8b. Deploy UAT 25/09 09:06 (13 module đúng bản, `?v=1323`).
- Số đo: `wj_sidebar` +SN-10…14 **0 vi phạm × 4 vai trò** (avatar PC = mobile, sheet theo quyền, chuông, Đổi cửa hàng mở
  modal, bàn phím) · suite **801, 0 đỏ** (E8b 779, +22) · mutation **13/13** · DB trắng chỉ khung 225 tests, 0 failed, 1 error
  (nợ F6 có sẵn) · `wj_pagecontainer` 0 · `wj_button` 0 · `wj_listcard` 0 · `wj_filterbar` ĐẠT · `wj_nesting` 0 · `b4` 286/286 ·
  `check_layers` không thêm · `test_ownership` cross 0 · `nav_dump`: sidebar + bottom-nav 0 lệch, chỉ avatar/sheet đổi (chủ
  đích); mốc mới `docs/e8c-baseline/nav_em.json` · `wj_measure --diff` 0 mất record.
- Bài học: mutation làm module SAU không nạp được thì module TRƯỚC đã commit arch đột biến vào DB ⇒ mutation kế hỏng dây
  chuyền; `-u` lại bằng mã sạch. Harness nay `-u` mọi module trong `--test-tags`. · Menu mobile: `.dropdown .dropdown-menu`
  Vuexy (0,2,0) đè `min-width` ⇒ selector `.dropdown .wujia-mheader-menu`. · `<i>` trong `dropdown-item` có margin-right 7px
  Vuexy ⇒ chữ lệch với mục icon SVG.
- LIMIT: ngôn ngữ ở 2 chỗ (cố ý) · breadcrumb `/portal/franchise/<id>/profile` + thẻ Home "Thông tin cửa hàng" giữ tên ·
  báo BA: `/portal/info-request` không có lối vào UI.
- Bàn giao anh Thái: neo sheet mới `msheet_end`; dòng Khảo sát (`position="inside"`) không cần sửa, vẫn cuối.
- UAT: `wj_sidebar` SN-1…14 0 vi phạm · `wj_pagecontainer` 0 (Khảo sát đo qua `/vi/`) · `wj_button` 0 mới (6 dòng y hệt E6c) ·
  0 POST bị chặn · 0 lỗi JS. Staff/nhiều cửa hàng không đo trên UAT (mật khẩu khác seed, không reset).
- Phiên kế: theo `docs/next-session-clusters-F.md` (cụm E đã hết E4b→E8) — đề xuất cụm EmptyState hoặc F6 theo bảng §2.

## END-SPRINT 61/62 — chốt sổ cụm E + cổng F (25/09/2026 · Mac)
- Kết quả: ✅ xong. Phiên tài liệu, **0 file dưới `custom/`**, không deploy, không đụng sheet.
- Đã làm: chapter `docs/chapters/75-sprint61-cluster-e-components.tex` (Sprint 61 — cụm E: E1 · E9a · E9b · E2 · E3 ·
  E4 · E5 · E6 · E7 · E8 + phiên xen kẽ nhịp dọc / G2 / DOC-CTRL) và `76-sprint62-cluster-f-standardize.tex` (Sprint 62 —
  cổng F0 → ★FR-A3); `\include` sau ADR-027; PDF master **301 → 312 trang**, 0 lỗi LaTeX (trong PDF đánh số 74/75).
  Compact summary: dòng Cập nhật + §4 dòng 61/62 + §5 State mới, bỏ cảnh báo "§5 trễ". Skill `/wujia-start`: bỏ Step 2a
  (Issue List đã mở lại từ FR-A3), cụm F ghi "cổng đã qua, nhánh sau cổng xen kẽ Issue List".
- Commit: xem git log — `docs(multi): chapter cụm E + cụm F`
- Deploy: không.
- Số đo: `build-doc.sh` 312 trang · 0 `! ` trong log · 0 chữ Việt trong `\texttt` của 2 chapter mới (485 "Missing character"
  trong log là của chapter cũ, mono DejaVu thiếu dấu tiếng Việt — có từ trước).
- Còn treo: 7 issue mới STT 140–146 chưa phân cụm · EmptyState · nợ F6 (portal_base tự test + 1 error DB trắng).
- Phiên kế: **F6** — controller Đặt hàng mỏng (prompt `docs/next-session-clusters-F.md` §3 "Prompt F6"). Việc cần biết
  trước: gộp luôn nợ `portal_base` tự test một mình (nhãn `portal_suite` hoặc tự bỏ qua khi module chủ chưa cài).

## F6 — Controller Đặt hàng mỏng + nợ `portal_base` tự test · 25/09/2026 · Mac
- Kết quả: ✅ xong. Nghiệm thu: `docs/f6-acceptance-matrix.md` (11/11 ý).
- Issue List đầu phiên: 7 issue STT 140–146 `Ready for Dev`, chưa phân cụm, reconcile 0 code — chủ dự án chọn làm F6.
- Chủ dự án chốt: một savepoint cho cả khối gửi đơn (vá đơn mồ côi) · đúng 3 phần của prompt, báo số thật ·
  gộp nợ `portal_base`, làm sau phần sale.
- Đã làm:
  - Luật số lượng min/bước/max **một nguồn** `product._portal_qty_error` (`wujia_sale`) — thêm giỏ, sửa số lượng, dòng
    giỏ và constraint dòng đơn portal cùng gọi; mã lỗi + câu chữ giữ nguyên.
  - Giỏ về model `wujia.portal.cart(.line)`: thêm/tăng-giảm nguyên SQL cũ; **Gửi đơn** = `action_submit_order()` (khoá
    NOWAIT, khung giờ, dòng lỗi, huỷ báo giá cũ bằng write, tạo đơn, xoá giỏ trong **một savepoint**) → controller chỉ map
    mã lỗi sang redirect. Controller **1047 → 862 dòng (−185)**.
  - **Vá lỗi ẩn đơn mồ côi**: HEAD để lại đơn nháp khi tạo đơn lỗi sau khi đã insert (chứng minh bằng test đỏ trên HEAD).
  - Lưới test đặc tả 21 test (trước đó 0 test gọi cart/submit) + `scripts/qa/cart_race.py` đua 2 phiên thật.
  - Nợ `portal_base`: `tests/common.py` (`need`/`need_suite`/`find_view`) — test quét nhiều module tự skip khi module chủ
    chưa cài; `patch.object(…, create=True)` ở 2 file `test_fra3_layer_guard`.
- Commit: `feat(F6)` — xem git log (đã push `main`).
- Deploy: chưa. Lệnh khi được yêu cầu: `-u wujia_sale,wujia_portal_sale` (base/layout chỉ đổi test — không cần `-u`).
- Số đo: suite portal 15 module **822, 0 đỏ** (E8c 801, +21) · run đối chứng: test mới trên code HEAD chỉ đỏ test đơn mồ côi
  · `cart_race` HEAD = F6 (JSON y hệt, NOWAIT 5/5) · mutation **10/10** · HTML 4 route + fragment giống từng byte ·
  DB chỉ `portal_base` **39 failed + 82 error → 0/0** (274) · DB chỉ khung **225, 0 failed, 0 error** · `check_layers` không
  thêm · `test_ownership` cross 0.
- Lệch plan / quyết định mới: không dời `_cart_state` (chốt 2) nên −185 chứ không phải ~−240 · submit chưa có giỏ dựng giỏ
  ảo `new()` để giữ thứ tự `branch_locked` trước `CART_EMPTY` · constraint min = 0 vẫn chặn vượt max như HEAD.
- Bài học: server cũ phiên E4b2 còn nghe `127.0.0.1:8092` ⇒ HttpCase gửi nhầm server, 12 test đỏ giả (public/login).
  Kiểm port bằng `lsof` trước khi chạy; chưa tắt process đó (pid 23706, không phải của phiên này).
- Nợ để lại: 1 error có sẵn `test_wujia_supply_demand_report` (anh Thái `c64de50`) · mã `ORDER_TIME_CLOSED` lúc tạo đơn vẫn
  bắt theo chuỗi "khung giờ" (F7 thay) · bàn giao anh Thái 4 mục (xem matrix).
- Phiên kế: **F7** — pilot tách `order_window` khỏi `portal_sale` (luôn nhớ: `action_submit_order` gọi
  `_is_within_order_window(area_id=…)` và bắt ValidationError "khung giờ" — chỗ nối F7 phải thay) · hoặc phân cụm 7 issue
  STT 140–146 nếu chủ dự án ưu tiên Issue List.

## F7 — Pilot tách `order_window` → `wujia_order_window` · 25/09/2026 · Mac
- Kết quả: ✅ xong. Nghiệm thu: `docs/f7-acceptance-matrix.md` (10/10 ý + mutation 5/5).
- Chủ dự án chốt: module cũ = **vỏ rỗng** (depend mỗi `wujia_order_window`) → deploy, đo 0 xmlid → Uninstall trên Apps →
  FR-P xoá thư mục · **vá luôn nợ F6** (bắt lỗi khung giờ theo lớp).
- Đã làm:
  - Module nghiệp vụ mới `wujia_order_window` (L2, depend `wujia_sale`) nhận nguyên model khung giờ, cấu hình fallback,
    chặn đơn portal ngoài giờ, view/menu/ACL, bản dịch. `pre_init_hook` đổi chủ **toàn bộ** bản ghi của module cũ,
    cả `ir_model_constraint`/`ir_model_relation` (khuôn Khảo sát bỏ sót).
  - Lớp lỗi `OrderWindowClosed`; giỏ hàng bắt theo lớp → một lỗi khác có chữ "khung giờ" không còn bị báo nhầm
    "ngoài khung giờ".
  - 10 test cho khung giờ (trước đó 0 test tạo khung giờ) + 1 test portal_sale.
  - Công cụ `scripts/qa/split_snapshot.py` (chụp + diff có `--rename`) cho F8–F13.
  - Chapter 74 §Quy trình tách viết lại theo thực tế.
- Commit: `6b2938d` (đã push `main`).
- Deploy: UAT 25/09 (`-i wujia_order_window -u wujia_portal_order_window,wujia_portal_sale`). Đo chỉ-đọc qua RPC:
  3 version đúng · 36 xmlid + 6 ràng buộc thuộc module mới, vỏ 0 · 2 khung giờ, 3 tham số, 2 menu, 2 ACL, nhãn `vi_VN`
  giống trước deploy · form Settings + list/form khung giờ mở được · không module nào depend vỏ. **Chờ chủ dự án
  Uninstall vỏ trên Apps** rồi đo lần cuối.
- Số đo: 42 dòng đổi chủ (36 xmlid + 6 ràng buộc), **1 lệch có giải trình** (view Settings đổi `name` app/block), gỡ vỏ
  **0 lệch**, 0 ERROR · suite 15 module portal + `wujia_order_window` **833, 0 đỏ** (F6 822) · DB trắng chỉ module mới
  **10/10** · HTML 5 route HEAD ↔ F7 **giống từng byte**, bundle CSS/JS cùng md5 · mutation **5/5** · `check_layers`
  3 → 2 (R4 order_window hết; còn 2 R3 `wujia_mobile_portal_*` của anh Thái) · `test_ownership` cross 0.
- Lệch plan / quyết định mới: plan dự đoán "không đổi chủ constraint thì gỡ vỏ DROP CHECK" — đo mutation: **không DROP**,
  hậu quả thật là 2 dòng trùng + 6 dòng mồ côi. Hook chuyển TẤT CẢ thay vì danh sách tay (module cũ rút hết).
  Hook Khảo sát không còn được nối ở manifest (`ec6d380`).
- Nợ để lại: xoá thư mục vỏ ở FR-P (sau khi UAT gỡ) · bàn giao anh Thái 2 mục (hook Khảo sát không nối; 46 dòng
  ràng buộc Khảo sát vẫn ghi `wujia_franchise`) · 1 error có sẵn `test_wujia_supply_demand_report` (không chạy trong suite portal).
- Phiên kế: **★FR-P** — review pilot (prompt §3 "phiên review ★"): xác nhận vỏ đã Uninstall trên UAT (đo lại 36 xmlid +
  6 ràng buộc module mới), rà diff, xoá thư mục vỏ. Hoặc phân cụm 7 issue STT 140–146 nếu chủ dự án ưu tiên Issue List.

## ★FR-P — Review pilot F7 · 25–26/09/2026 · Mac
- Kết quả: ✅ xong — **ĐẠT, nhân quy trình sang F8 được** (điều kiện: chốt nợ `ref()` xmlid mobile Thái trước F8/F12).
  Review: `docs/f-review-FR-P.md`. Chủ dự án nhấn mạnh soi tuân thủ tầng nghiệp vụ–portal–mobile: **0 vi phạm** (bảng §3).
- Đã làm:
  - UAT: đo trước chỉ-đọc (vỏ 0 xmlid/0 cons/0 dependents) → chủ dự án duyệt → **gỡ vỏ qua RPC** `button_immediate_uninstall`
    (lời gọi ghi duy nhất, 6.4 s) → đo sau: 0 lệch với mốc F7 ngoài `state` vỏ.
  - Repo: xoá `custom/wujia_portal_order_window`; `check_layers` `DEPRECATED = set()` (34 module, 2 vi phạm R3 Thái);
    **`deploy.yml` còn `-i/-u` vỏ (F7 bỏ sót) → đổi**; bảng "tên cũ còn đâu" trong review.
  - **Dời `migrate_ownership` về L1** `wujia_core/tools/module_split.py` (chốt) + chặn module đích không tồn tại + helper
    **`imd_names`** suy xmlid theo model (model/field/selection/inherit/constraint/access/rule/view/action/srv/cron/tpl/seq).
  - Sửa test `test_split_ownership`: dòng module giả (DB trắng không có dòng vỏ → F7 chỉ Pass vì vỏ còn trên đĩa) + test
    helper phủ 36/36 xmlid F7. Comment L2 nhắc controller → bỏ.
  - `split_snapshot.py` +7 nhóm (inherit · sel · cron · tpl · srv · attach · rule theo module).
  - Thử tách MỘT PHẦN `info_request` trên `wujia_frp_trial`: helper 72/75 (3 dư = QWeb portal phải ở lại), 80 dòng đổi chủ,
    0 lệch thật, `number_next` giữ.
  - Chapter 74 §Quy trình tách 4 chỗ + số đo FR-P; build PDF.
- Commit: `9d2a606` — `review(FR-P): review pilot F7 đạt — gỡ vỏ order_window, hook đổi chủ về wujia_core` (đã push `main`; gồm cả mục F7 deploy sửa local từ phiên trước).
- Deploy: **UAT 26/09** (chủ dự án). Đo chỉ-đọc: `wujia_core 19.0.1.0.1`, 36 xmlid + 6 ràng buộc, vỏ `uninstalled`, khung giờ/tham số/Settings nguyên.
- Số đo: UAT 36 xmlid + 6 cons + 2 khung + 3 tham số + 2 menu + 2 ACL y hệt · `check_layers` 2 (Thái) · R6 0 · R7 2 (Thái) ·
  `-u` DB copy 0 ERROR · suite **834, 0 đỏ** (F7 833 + 1) · snapshot vs `f7r2/u.json` 0 lệch · DB trắng **11/11** (trước sửa
  1 error) · trial 80 đổi chủ / 0 lệch · mutation M3 trên helper đã dời **đỏ đúng**.
- Lệch plan / quyết định mới: `-u wujia_core --test-enable` kéo nạp test `wujia_franchise` (import file đã xoá) → 2 lượt
  chết 255; chỉ `-u wujia_order_window`. `ir_cron` Odoo 19 không có `name`/`model_id` (kế thừa `ir.actions.server`) — sửa cả
  helper lẫn snapshot. Hai Bash song song dùng chung cwd → đường dẫn tuyệt đối.
- Nợ để lại: (1) bàn giao Thái (chốt 26/09: phần mobile ngoài phạm vi, **không chặn F8**) — `wujia_mobile_portal_info_request`/
  `_exam` `ref()` xmlid `wujia_portal_<x>.*`, sau F8/F12 Thái đổi tiền tố; Dev báo trước khi deploy; (2) dư âm tên portal trong L2 (ICP `wujia_portal.*`, field
  `portal_order_time_*`, app/menu "Wujia Portal", xmlid view) — cần migration nếu đổi; (3) hook Khảo sát không nối + 46 cons
  `wujia_franchise` (bàn giao Thái); (4) `test_wujia_supply_demand_report` error có sẵn.
- Issue List (reconcile 7 issue STT 140–146): `grep custom/` + ledger = 0; `git log -S` chỉ bắt commit docs ⇒ **chưa có code**,
  chưa phân cụm. Toàn UI: 140 badge topbar PC · 141 store switcher mobile · 142 Home PC redesign (lớn) · 143+144 mật độ
  header/spacing `/portal/order` mobile · 145 bottom-nav 83px · 146 routing `/` → login (Suggestion).
- Phiên kế: đề xuất **Issue List cụm nhỏ trước** (143 + 144 + 145 cùng một chủ đề "mật độ mobile", 1 phiên; 140 + 141 phiên
  hai; 142 cần BA duyệt mockup; 146 hỏi BA) rồi **F8 `info_request`** — việc cần biết trước: dùng `imd_names` + liệt kê `extra` (menu), giữ 3 QWeb ở portal; báo Thái mục (1) trước deploy.

## F8 — Tách `info_request` → `wujia_info_request` + controller mỏng · 26/09/2026 · Mac
- Kết quả: ✅ xong. Nghiệm thu: `docs/f8-acceptance-matrix.md` (9/9).
- Issue List đầu phiên: 7 issue STT 140–146 `Ready for Dev`, reconcile 0 code. Chủ dự án chọn F8.
- Chủ dự án chốt: code F8, **chưa deploy** (chủ dự án tự deploy) · **sửa luôn 5 dòng tên trong `wujia_mobile_portal_info_request`**
  (UAT đang cài module này; không sửa thì `-u` gãy). Lần đầu cổng quyền Claude Code chặn; chủ dự án bảo sửa lần nữa ⇒ đã sửa.
- Đã làm:
  - Module L2 mới `wujia_info_request` (git mv model, ACL, rule, sequence, backend; `.po` tách 137 mục thành 81 + 56).
    Hook tách một phần: `imd_names(extra=[menu])` + `migrate_ownership`.
  - Controller mỏng: `_portal_can_request` · `_portal_scope_domain` · `create_from_portal` (một savepoint, upload truyền callback) ·
    `_franchise_value` (1 nguồn cho form + AJAX). 263 → 239 dòng, response giữ nguyên.
  - Test: +10 (module mới, trước đó model 0 test) + 3 HttpCase portal (luồng gửi thật). `check_layers`, `deploy.yml`, reseed.
  - Chapter 74: bước 5–6 Quy trình tách (tách một phần, chốt mobile, kết quả đo khi lỗi), số đo F8, bẫy `assertRaises`.
- Commit: `a5cb738` — `feat(F8): tách info_request → module nghiệp vụ wujia_info_request + controller mỏng` (đã push `main`).
- Deploy: **UAT 26/09** (chủ dự án). Đo chỉ-đọc + Playwright (không gửi/lưu): 3 version đúng (`19.0.1.0.0` · `19.0.2.0.0` · mobile `19.0.1.0.1`) · module mới 73 xmlid (72 + `field_…__rating_ids` có từ 17/05 vì UAT cài `rating`) · portal còn 3 QWeb · menu/action list-kanban-form/3 rule/2 ACL/seq INF- nguyên · nhãn vi_VN còn · portal PC + mobile list/form 200, ô giá trị hiện tại tự điền · backend PC list→kanban→form mới, mobile vào kanban · 0 bản ghi sinh ra. 404 `/app-assets/data/locales/en.json` có trên mọi trang portal (có từ trước, không thuộc F8). Chưa test được staff 403 trên UAT (không có mật khẩu staff; local đã phủ). Lệnh: `-i wujia_info_request -u wujia_portal_info_request,wujia_mobile_portal_info_request`.
- Số đo: hook 72 imd + 7 cons + 1 rel · snapshot 80 đổi chủ **0 lệch thật** · HTML 5 route + JSON giống từng byte (cùng lần seed)
  · 3 HttpCase mới trên code HEAD cũng xanh (đối chứng) · suite **847, 0 đỏ** (FR-P 834 + 13) · DB trắng 10/10 · mutation **3/3** · DB giống UAT (có mobile) deploy **exit 0**, test mobile 3/3, `check_layers` 2 → 1.
- Lệch plan / quyết định mới: Đã nói với chủ dự án là "lỗi thì cả lượt deploy bị huỷ", nhưng **đo ra sai**. Odoo 19 commit sau từng
  module ⇒ phần F8 vẫn vào DB, chỉ module mobile dừng, exit 255; khởi động thường vẫn chạy. Test rollback viết bằng `assertRaises`
  không bắt được lỗi quên savepoint (Odoo tự bọc savepoint) ⇒ đổi sang `try/except`.
- Bài học: log của `-u` nằm ở `logs/<năm>/<tháng>/<ngày>.log` của cây code đang chạy (worktree HEAD ghi vào scratchpad). Hai DB seed
  cách nhau vài phút làm HTML lệch giờ tạo ⇒ so HTML phải dùng hai bản copy của cùng một lần seed.
- Nợ để lại: (1) báo anh Thái đã sửa 5 dòng module mobile; (2) AJAX `values` với `other` đọc được field bất kỳ của
  cửa hàng mình (hành vi có sẵn); (3) dọn DB đo `wujia_f8*` khi xong (worktree HEAD đã gỡ).
- Phiên kế: commit F8 (khi được yêu cầu) → chủ dự án deploy → đo UAT chỉ-đọc. Sau đó **F9 `knowledge`** (có cron; grep mobile trước) hoặc cụm Issue List 143 + 144 + 145 "mật độ mobile".

## F9 — Tách `knowledge` → `wujia_knowledge` + controller mỏng · 26/09/2026 · Mac
- Kết quả: ✅ xong. Nghiệm thu: `docs/f9-acceptance-matrix.md` (9/9).
- Issue List đầu phiên: 7 issue STT 140–146 `Ready for Dev`, reconcile 0 code. Chủ dự án chọn F9.
- Chủ dự án chốt: **Home dùng chung luật hiển thị, vá luôn** (Home không lọc ngày phát hành ⇒ bài hẹn giờ đã hiện, bấm vào
  báo "đã gỡ") · **code + commit + push `main`**, deploy để chủ dự án. Mobile Thái: 0 tham chiếu knowledge.
- Đã làm:
  - Module L2 mới `wujia_knowledge` (git mv 3 model, ACL, sequence, cron, backend; `.po` 123 mục → 97 + 26 portal). Hook
    `imd_names(extra=[4 menu])` + `migrate_ownership`.
  - Controller mỏng: `_portal_visible_domain` · `_portal_search_domain` · `_portal_get_attachment` về model. 180 → 153 dòng.
    Home (`portal_base`) gọi `_portal_visible_domain` qua `env.get` + `hasattr` (không thêm depend).
  - Test: `wujia_knowledge` 10 (4 dời + slug/mã, publish, cron hết hạn, đính kèm, tìm kiếm, 2 đổi chủ); portal 13 (+ tải
    đính kèm 200/403, Home không hiện bài hẹn giờ).
  - `split_snapshot` đọc `last_value` sequence Postgres. `check_layers`, `deploy.yml`, reseed. Chapter 74 (bẫy noupdate, số đo F9, P4).
- Commit: `2ba8311` — `feat(F9): tách knowledge → module nghiệp vụ wujia_knowledge + controller mỏng` (đã push `main`).
- Deploy: **UAT 26/09** (chủ dự án). Lệnh: `-i wujia_knowledge -u wujia_portal_knowledge,wujia_portal_base`. Đo chỉ-đọc (RPC + HTTP
  `anh.owner`): 3 version đúng (`19.0.1.0.0` · `19.0.4.0.0` · `portal_base 19.0.7.25.0`) · module mới 108 xmlid (107 +
  `field_…article__rating_ids` vì UAT cài `rating`, như F8) · portal còn 5 view · 13 cons + 2 rel đổi chủ · **`KNW-` số kế 28**
  (27 bài, mã cao nhất `KNW-000027`) ⇒ bẫy noupdate đã chặn thật · cron 25 active, nextcall giữ · menu 305–308 + action 480–482
  tạo 16/05 (không bị tạo lại), action list/kanban/form · nhãn + menu vi_VN còn · portal: `/portal/knowledge` (+ `?keyword`, trang 2)
  200, category/tag/slug sai → redirect `notice=*_gone` như cũ, chi tiết 200, attachment lạ 403, JSON search 2 bài · Home 200, 2 bài
  mới nhất đúng dự kiến. UAT không có bài hẹn giờ tương lai hay đính kèm ⇒ hai nhánh đó chỉ có bằng chứng local. Mở trang chi tiết
  làm `view_count` bài QA-RETEST +1 (không tạo bản ghi).
  Browser (Playwright, chỉ xem): portal PC 1440 + mobile 390 — Home, danh sách (12/21, trang 1), lọc danh mục (2 bài), tìm
  "Checklist" (2 bài), chi tiết; 0 tràn ngang, 0 lỗi JS mới (chỉ 404 `locales/en.json` có sẵn). Home PC không có khối bài viết
  (thiết kế cũ, chỉ mobile có), Home mobile hiện đúng 2 bài. Backend admin: list bài 27 / danh mục 9 / thẻ 6, kanban, form
  `KNW-000020` mở được, chatter giữ lịch sử từ 16/05, không lưu gì. Chi tiết mở thêm 2 lần ⇒ `view_count` QA-RETEST +2.
- Số đo: hook 107 imd + 13 cons + 2 rel · snapshot 122 đổi chủ **0 lệch thật** · HTML 12/12 route + JSON 2/2 giống từng byte,
  bundle cùng md5, Home lệch đúng bài hẹn giờ · suite **856, 0 đỏ** (F8 847 + 9) · test mới trên HEAD chỉ Home đỏ · DB trắng
  10/10 · mutation M2 2 đỏ, M3 2 đỏ, M1 chỉ snapshot bắt (10 lệch) · `check_layers` 1 (exam, F12) · R7 2 (Thái).
- Lệch plan / quyết định mới: **Bẫy data `noupdate`** — lượt deploy đầu reset sequence `KNW-` 438 → 1 mà snapshot cũ báo 0 lệch
  (chỉ đọc cột `number_next`, luôn 1 với kiểu standard). `-i` chạy chế độ init ⇒ Odoo nạp lại bản ghi noupdate lên xmlid đã đổi
  chủ. Sửa: bỏ `number_next` khỏi XML + snapshot đọc `last_value`. F8 dính cùng bẫy trên UAT, vô hại (0 yêu cầu, số kế 1).
  Test đơn vị không bắt được hook quên menu (trạng thái cuối giống hệt) — việc của snapshot.
- Bài học: `createdb -T` không chép filestore ⇒ server đo trả 500 cho đính kèm/bundle (nhầm là lỗi code nếu không đọc log);
  log server nằm ở `<thư mục logfile>/<năm>/<tháng>/<ngày>.log` (wujia_core đổi chỗ).
- Nợ để lại: (1) `_sql_constraints` hết hiệu lực trên Odoo 19 — unique slug/mã bài/mã danh mục/tên tag không có trong DB (nhiều
  module cùng lỗi); (2) publish bài nháp đã có ngày hẹn thì `write` ghi đè ngày = now (hỏi BA); (3) F10–F13 có sequence thật ⇒ bỏ
  `number_next` trước khi tách (ghi ở bảng §2 + chapter 74).
- Phiên kế: **F10 `support`** (có sequence ticket,
  depends `sale`/`stock_picking_batch`/`sales_team`; C1 đã vá) hoặc cụm Issue List 143 + 144 + 145 "mật độ mobile".

## F10 — Tách `support` → `wujia_support` + controller mỏng · 26/09/2026 · Mac
- Kết quả: ✅ xong. Nghiệm thu: `docs/f10-acceptance-matrix.md` (9/9).
- Issue List đầu phiên: 8 `Ready for Dev` (STT 126, 140–146), reconcile 0 code. Chủ dự án chọn F10.
- Chủ dự án chốt: **code + commit + push `main`**, deploy để chủ dự án · **dời luôn trả lời ticket** về model.
  Mobile Thái: 0 tham chiếu support. Không có nhóm quyền riêng.
- UAT đo chỉ-đọc trước (RPC): 15 ticket, `WJ-TK` số kế 17, 7 danh mục khớp XML (vi_VN có đủ) ⇒ không dừng hỏi.
- Đã làm:
  - Module L2 mới `wujia_support` (git mv 2 model, ACL, 2 rule, sequence, 7 danh mục, backend; `.po` 204 mục → 129 + 75
    portal). Hook `imd_names(extra=[4 menu, 7 danh mục])` + `migrate_ownership`.
  - Controller mỏng: `_portal_scope_domain(user)` · `create_from_portal` (kiểm + tạo + đính kèm một savepoint, trả mã lỗi
    form) · `_portal_reply` · `_portal_get_attachment`. 200 → 166 dòng (kể cả bảng badge dời vào).
  - A2: `MOBILE_TICKET_BADGES` rời `portal_base/utils.py` về `portal_support`; test badge phần ticket dời sang `test_scan_e2b`
    để `test_scan_e2` vẫn chạy khi `portal_base` cài một mình.
  - Test: `wujia_support` 11 (model trước đó 0 test riêng) + 5 HttpCase portal. `check_layers`, `deploy.yml`, reseed.
  - Chapter 74: bẫy noupdate với dữ liệu mẫu (bước 2), số `.po`, đoạn F10, dòng P5.
- Commit: `033794c` — `feat(F10): tách support → module nghiệp vụ wujia_support + controller mỏng` (đã push `main`).
- Deploy: **UAT 26/09** (chủ dự án). Lệnh: `-i wujia_support -u wujia_portal_support,wujia_portal_base`. Đo chỉ-đọc (RPC +
  Playwright, không gửi/lưu): 3 version đúng (`wujia_support 19.0.1.0.0` · `portal_support 19.0.4.0.0` · `portal_base 19.0.7.26.0`) ·
  module mới 114 xmlid (113 + `field_…__rating_ids`, như F8/F9) · portal còn đúng 5 view · 15 ticket, số kế `WJ-TK` **17 giữ** ·
  7 danh mục + tên vi_VN nguyên · menu 309/310, action 484/485, rule 191/192 giữ id · portal admin PC + mobile 390: list 10,
  lọc `in_progress` 2, tìm mã 1, form mới hiện danh mục, chi tiết 200, ticket lạ → về list, 0 tràn ngang · `anh.owner` list 0
  (không tạo ticket nào), danh mục tiếng Việt, mở ticket người khác → về list · attachment lạ 403, ticket lạ 404 · backend kanban 4,
  list 15, form mở, 0 lỗi JS. 404 `/app-assets/data/locales/en.json` có từ trước.
  **Phát hiện có từ trước (không thuộc F10, HTML HEAD ‖ F10 giống từng byte):** trang chi tiết chỉ liệt kê `attachment_ids`
  (m2m cũ), còn file cửa hàng tải lên qua `attach_files_to_record` gắn bằng `res_model/res_id` ⇒ ticket 16 có 1 ảnh mà portal
  không hiện link tải. Chờ chủ dự án chốt sửa (phiên riêng hoặc gửi BA).
- Số đo: hook 113 imd + 16 cons + 1 rel · snapshot 130 đổi chủ, **1 lệch có giải trình** (md5 bảng danh mục: chỉ
  `write_date`) · HTML 18/18 GET giống từng byte + 9/9 POST cùng redirect + DB sau POST giống hệt, bundle cùng md5 ·
  suite **872, 0 đỏ** (F9 856 + 16) · test portal mới trên HEAD 12/12 (hành vi không đổi) · DB trắng 11/11 · mutation
  **4/4** (M2 lượt đầu chỉ test đơn vị bắt → thêm ca portal) · `check_layers` 1 (exam, F12) · R7 2 (Thái).
- Lệch plan / quyết định mới: Bẫy noupdate với **dữ liệu mẫu**: `-i` đưa field ghi trong XML về giá trị XML (đo trên DB
  giả lập: `sequence` 55 → 50) nhưng **giữ bản dịch vi_VN tuỳ biến**. UAT khớp XML nên an toàn. Test fixture bật vi_VN
  (DB copy `wujia_f8final` để admin `vi_VN` mà lang chưa bật ⇒ `message_post` lỗi "Invalid language code").
- Bài học: DB trắng phải cài trước rồi mới `-u --test-tags /<module>` — `--test-enable` lúc `-i` import cả tests
  `wujia_franchise` (file đã xoá) ⇒ registry chết. Hash URL bundle theo mtime file (worktree ≠ cây chính) ⇒ so md5 nội dung.
- Nợ để lại: (1) hỏi BA: portal support lọc theo **người tạo**, quản lý không thấy ticket nhân viên cùng cửa hàng;
  (2) `_sql_constraints` danh mục chết trên Odoo 19 (nợ chung); (3) `test_scan_e2b` import thẳng từng `portal_*`
  (không chạy khi `portal_base` một mình, có từ trước).
- Phiên kế: **F11 `announcement`** (từ `portal_notification`, giữ `_name wujia.notification`, 2 nhóm quyền — phải sửa tham chiếu
  `group_*`, sequence ANN, rule theo cửa hàng; bảng badge thông báo nếu có) hoặc cụm Issue List 143 + 144 + 145 "mật độ mobile".

## F10-fix — Portal hỗ trợ: file đính kèm + ghi chú nội bộ · 26/09/2026 · Mac

- Nguồn: đo UAT sau deploy F10 (ticket 16 có 1 ảnh, portal không hiện link). Soi thêm ra lỗi thứ hai cùng chỗ.
- Lỗi (có từ trước F10): (1) chi tiết ticket chỉ liệt kê `attachment_ids` m2m cũ, file cửa hàng tải lên gắn
  `res_model/res_id` ⇒ không hiện; (2) template lọc `message_type == 'comment'` trên ticket `sudo` ⇒ **ghi chú nội bộ HQ
  (Log note) hiện cho cửa hàng** (UAT: ticket 12 có 1 note).
- Sửa: model `_portal_messages()` (bỏ note nội bộ) + `_portal_attachments()` (m2m + res_id + file tin công khai, trừ file
  của note); `_portal_get_attachment` dùng chung tập đó ⇒ file của note tải về 403. Template PC dùng hai method, link đi
  route đã chặn quyền thay `/web/content`; **mobile thêm thẻ "File đính kèm"** (chủ dự án chốt) theo DataList compact-row
  `--inset` như Home. `wujia_support 19.0.1.0.1`, `wujia_portal_support 19.0.4.0.1`; bảng đếm CardHeader `portal_base` 5 → 6.
- Số đo: `portal_base,portal_layout,wujia_support,portal_support` **524/0** · template cũ làm test mới đỏ (mutation) ·
  Playwright local PC + mobile: note ẩn, trả lời HQ hiện, file hiện + tải 200, 0 tràn · `check_layers` 1 / R7 2 giữ.
- Deploy: `-u wujia_support,wujia_portal_support` (chủ dự án).
- Phiên kế: đo UAT (ticket 16 hiện file, ticket 12 hết note) → **F11 `announcement`** hoặc cụm Issue 143+144+145.

## F11 — Tách `notification` → `wujia_notification` + controller mỏng · 26/09/2026 · Mac
- Kết quả: ✅ xong. Nghiệm thu: `docs/f11-acceptance-matrix.md` (9/9).
- Issue List: 8 `Ready for Dev` (STT 126, 140–146), reconcile 0 code. Chủ dự án chọn F11.
- Chủ dự án chốt: tên module **`wujia_notification`**, **giữ `_name` cả 3 model** · **Home vá luôn, dùng luật chung** (KPI
  "chưa đọc" = badge chuông, list Home bỏ bài hẹn giờ/hết hạn) · **code + commit + push `main`**, deploy để chủ dự án ·
  4 màu nền loại thông báo trên UAT **để về theo code** (bẫy noupdate). Mobile Thái: 0 tham chiếu notification.
- UAT đo chỉ-đọc trước (RPC): 19 thông báo, 20 dòng đã đọc, `ANN/` số kế 20, nhóm User 0 / Administrator 1, 147 xmlid.
  5 loại: code/tên/icon khớp XML, **4/5 `bg_color` lệch** (bảng màu Sprint 4.3 còn trên UAT; XML đã đổi ở Sprint 19) ⇒ dừng hỏi.
- Đã làm:
  - Module L2 mới `wujia_notification` (git mv 3 model, 2 nhóm quyền + privilege, ACL, 2 rule, sequence `ANN/` bỏ
    `number_next`, 5 loại, backend; ACL + menu đổi ref nhóm sang cục bộ; `.po` 214 mục → 159 + 55 portal). Hook
    `imd_names(extra=[privilege, 2 nhóm, 4 menu, 5 loại])` + `migrate_ownership`.
  - Controller mỏng: domain lịch sử/còn hiệu lực, đọc/đếm chưa đọc theo cửa hàng, đính kèm thuộc thông báo về model;
    3 chỗ ghi "đã đọc" (chi tiết / mark-read / mark-all) → `wujia.notification.read._mark_read(opened, touch)`. 433 → 336 dòng.
  - Home `portal_base`: KPI + list thông báo gọi luật model qua `hasattr` (không thêm depend). A2: không có bảng badge thông báo.
  - Test: `wujia_notification` 37 (2 file test model dời + `test_portal_rules` 4 + `test_split_ownership` 2) + 5 HttpCase portal
    (Home = badge, list Home, mở lại giữ `read_date`, mark-read chỉ id truy cập được, đính kèm 200/403/404). `check_layers`,
    `deploy.yml`, reseed, `test_sprint32.py`.
  - Chapter 74: đoạn F11, dòng P6, số `.po`.
- Commit: `bfa2bae` — `feat(F11): tách notification → module nghiệp vụ wujia_notification + controller mỏng` (đã push `main`).
- Deploy: **chờ chủ dự án**. Lệnh: `-i wujia_notification -u wujia_portal_notification,wujia_portal_base`. Sau deploy đo
  chỉ-đọc: 3 version (`wujia_notification 19.0.1.0.0` · `portal_notification 19.0.3.0.0` · `portal_base 19.0.7.27.0`), module
  mới 141 xmlid (140 + `rating_ids`), portal còn 6 view, `ANN/` số kế **20**, 4 ô màu loại đổi, KPI Home = badge chuông.
- Số đo: hook 140 imd + 28 cons + 5 rel · snapshot 173 đổi chủ, **1 lệch có giải trình** (md5 bảng loại: `bg_color` về XML,
  tên vi_VN tuỳ biến giữ) · HTML 3 phiên × 40 request **117/120 giống từng byte**, 3 lệch đều Home (đúng chỗ vá) · DB đã đọc
  sau ghi giống hệt · bundle cùng md5 · suite **885, 0 đỏ** · test portal mới trên HEAD: đúng 2 đỏ (2 test Home) · DB trắng
  37/37 · mutation **5/5** · Playwright PC 1440 + mobile 390: Home 47 = popup 47 = badge 47, 0 tràn · `check_layers` 1 (exam,
  F12) · R7 2 (Thái).
- Lệch plan / quyết định mới: không dời `test_notification_timezone` (dùng tiện ích `portal_base`). `migrations/` cũ của
  portal để nguyên. Seed nháp không được có `published_date` (NOT NULL chỉ khi gửi — bỏ key).
- Bài học: HTML trang đầy đủ có `registry_hash` đổi theo registry ⇒ phải chuẩn hoá khi so hai server. `-i` module tách
  nạp lại data noupdate lên xmlid đổi chủ ⇒ **đo trước từng field XML trên UAT**, lệch thì hỏi (F11 là lần đầu lệch thật).
- Nợ để lại: (1) phụ đề danh sách "còn hiệu lực" nhưng danh sách là lịch sử (có bài hết hạn, bài hết hạn chưa mở vẫn
  "Chưa đọc") — có từ trước, hỏi BA nếu cần; (2) `is_read_by()` không còn nơi gọi — dọn ở ★FR-A; (3) `_sql_constraints`
  chết trên Odoo 19 (nợ chung).
- Phiên kế: **F12 `exam`** (mobile Thái `ref()` xmlid `wujia_portal_exam.*` — báo Thái trước deploy; hết vi phạm R3 cuối)
  hoặc cụm Issue List 143 + 144 + 145 "mật độ mobile".

## F12 — Tách `exam` → `wujia_exam` + controller mỏng (gộp F12a + F12b) · 26/09/2026 · Mac
- Kết quả: ✅ xong. Nghiệm thu: `docs/f12-acceptance-matrix.md` (9/9).
- Đầu phiên: F11 đã lên UAT (đo chỉ-đọc: `wujia_notification` installed, 141 xmlid). Issue List 8 `Ready for Dev` như F11,
  reconcile 0 code. Chủ dự án chọn F12.
- Chủ dự án chốt: tên **`wujia_exam`**, giữ `_name` cả 5 model · **sửa luôn `wujia_mobile_portal_exam` như F8** (báo Thái
  trước deploy) · gộp a+b, commit + push `main`, deploy để chủ dự án · **"tối đa người/phiếu" một nguồn cả constraint**.
- UAT đo chỉ-đọc trước (RPC): 3 ca giờ · 3 khoá · 4 kỳ thi · 12 phiếu · 12 thí sinh, 221 xmlid, nhóm Quản lý 1 / Người dùng 0;
  3 sequence noupdate khớp XML (số kế WJ-CRS 5 · WJ-EXR 17 · WJ-EXS 6), không data noupdate nào khác ⇒ không câu hỏi.
- Đã làm:
  - Module L2 mới `wujia_exam` (git mv 5 model, 2 nhóm quyền + privilege, ACL, 2 rule, 3 sequence, 4 view + menu backend,
    `test_c10_quota`; ACL + menu đổi ref nhóm sang cục bộ; `groups=` trong arch 3 form ghi đủ `wujia_exam.`; `.po` 393 →
    216 + 177 portal). Hook `imd_names(extra=[privilege, 2 nhóm, 7 menu])` + `migrate_ownership`.
  - Controller mỏng (729 → 558): trạng thái khung giờ, chọn được ca, lịch tháng, meta khoá, phạm vi cửa hàng, đếm kết quả,
    **`register_from_portal`** (kiểm + dựng dòng + SĐT/năm sinh/ảnh + membership + savepoint) về model; lớp lỗi
    `ExamPortalError(kind)` giữ nguyên mã `not_found`/`validation`/`business` và câu báo. `_effective_max_per_registration`
    (ca, trống thì khoá) dùng cho hướng dẫn, chặn portal và `_check_participant_bounds`.
  - Mobile Thái: depend + 18 dòng `wujia_portal_exam.` → `wujia_exam.` (4 view + test), `19.0.1.0.1`.
  - Test: `wujia_exam` 13 (`test_c10_quota` + `test_portal_rules` 7 + `test_split_ownership`) + portal 5 HttpCase
    (hướng dẫn tối đa, lịch/khung giờ, gửi phiếu → chi tiết + ảnh, 5 mã lỗi + rollback, cửa hàng khác 303/404).
    `check_layers`, `deploy.yml`, reseed.
  - Chapter 74: đoạn F12, dòng P7, số `.po`, bước "ref nhóm quyền đổi chủ" (bẫy groups trong arch).
- Commit: `2acbd9f` — `feat(F12): tách exam → module nghiệp vụ wujia_exam + controller mỏng` (đã push `main`).
- Đã dọn: 8 DB đo `wujia_f12*` + filestore, worktree `scratchpad/f12/head`.
- Deploy: **chờ chủ dự án — báo anh Thái trước** (đã sửa `wujia_mobile_portal_exam`). Lệnh:
  `-i wujia_exam -u wujia_portal_exam,wujia_mobile_portal_exam`. Sau deploy đo chỉ-đọc: 3 version (`wujia_exam 19.0.1.0.0` ·
  `portal_exam 19.0.6.0.0` · `mobile_portal_exam 19.0.1.0.1`), module mới ~216 xmlid (214 + `rating_ids`), portal còn 5 view,
  số kế WJ-EXR 17 · WJ-CRS 5 · WJ-EXS 6, nhóm Quản lý 1 người, 10 nút form backend hiện, `/portal/exam` 200.
- Số đo: hook 214 imd + 30 cons + 1 rel · snapshot 245 đổi chủ, 3 lệch = arch 3 form (groups, cố ý) · HTML/JSON 3 phiên
  **234/234 giống từng byte, 2 lần** (19 nhánh gửi phiếu) · DB sau ghi giống · focused 49/49 · suite **897/0/0** · test portal
  mới trên HEAD xanh · DB trắng 13/13 · deploy DB giống UAT có mobile exit 0, mobile 3/3 · mutation **6/6** · Playwright PC
  1440 + mobile 390, 12 màn, 0 tràn · `check_layers` **0 vi phạm tầng** (lần đầu) · R7 2 (Thái).
- Lệch plan / quyết định mới: gộp calendar thành `_portal_day_states` (dict ngày → trạng thái; ma trận tuần ở controller);
  `_max_hint` + nhãn khung giờ ở lại controller. `migrations/` cũ của portal để nguyên.
- Bài học: **`groups=` trong arch view phải ghi đủ `module.xmlid`** — Odoo 19 `parse(raise_if_not_found=False)` bỏ qua im
  lặng ⇒ nút ẩn cả với Administrator; snapshot bắt qua md5 arch (F8–F11 soát: chỉ có menuitem, sạch). Test phạm vi ảnh
  phải cho dòng cửa hàng khác **có ảnh**, không thì 404 vì thiếu ảnh che mất lỗi phạm vi (mutation M5 bản đầu sống).
- Nợ để lại: (1) tiêu đề PC "Khung giờ ngày —" không điền ngày sau khi chọn (có từ trước, HEAD cũng vậy); (2) 404
  `/app-assets/data/locales/en.json` (có từ trước).
- Phiên kế: đo UAT sau deploy F12 → **F13a `return`** (lớn nhất: 1108 dòng model, kế thừa SO/picking, hook picking, wizard
  SO 0đ FIFO) hoặc cụm Issue List 143 + 144 + 145 "mật độ mobile".

## F13 — Tách `return` → `wujia_return` + controller mỏng (gộp F13a + F13b) · 26/09/2026 · Mac
- Kết quả: ✅ xong. Nghiệm thu: `docs/f13-acceptance-matrix.md` (9/9). **Phân hệ cuối khối A — `PENDING_SPLIT` rỗng.**
- Đầu phiên: F12 đã lên UAT (đo chỉ-đọc: `wujia_exam 19.0.1.0.0` · `mobile_portal_exam 19.0.1.0.1` installed). Chủ dự án chọn F13.
- Chủ dự án chốt: tên **`wujia_return`**, giữ `_name` mọi model · gộp a+b, commit + push `main`, deploy để chủ dự án ·
  A2 "chuẩn nhất": luật trạng thái về model + **một bảng nhãn** (Dev tự chốt chữ theo bảng PC, màu giữ, báo BA sau).
- UAT đo chỉ-đọc trước (RPC): 14 phiếu, 5 loại lỗi, 0 allocation, 236 xmlid, nhóm Quản lý 1 / Người dùng 0; 2 sequence
  noupdate khớp XML (số kế RTN 5 · CA 1), 5 loại lỗi noupdate khớp XML ⇒ không câu hỏi. Mobile Thái 0 ref ⇒ không sửa.
- Đã làm:
  - Module L2 mới `wujia_return` (depend `mail, wujia_sale, wujia_franchise`): git mv 6 model (gồm kế thừa SO/picking/
    product), wizard bù 3 model, 2 nhóm + privilege, ACL, rule, 2 sequence, 5 loại lỗi, 4 view + menu backend,
    `test_compensation_wizard_d1`; mọi ref nhóm đổi `wujia_return.` đủ tiền tố; `.po` 333 → 239 + 94 portal. Hook
    `imd_names(extra=[privilege, 2 nhóm, 6 menu, 5 loại lỗi])` + `migrate_ownership`.
  - Controller mỏng (588 → 357): đơn hợp lệ 10 ngày, phạm vi cửa hàng, cấu hình bù, minh chứng (controller chỉ sniff MIME
    + đo dung lượng), parse payload, **`create_from_portal`** (savepoint thay `unlink` thủ công; đính kèm qua callback),
    khoá trạng thái 8 bộ lọc (`_portal_status_key`/`_portal_status_domain`), tiến độ bù (`_portal_compensation_view`) về model.
  - A2: `RETURN_STATUS_LABELS` + `return_status_label` ở `portal_base/controllers/utils.py`, thay `MOBILE_RETURN_BADGES`,
    `STATE_LABELS` portal và dict inline trong `portal_home.xml`. Home gọi `_portal_open_domain`/`_portal_recent_domain`
    qua `hasattr`. `portal_base 19.0.7.28.0`.
  - Test: `wujia_return` (`test_compensation_rules`, `test_portal_rules` 7, `test_split_ownership` 3, fixture `common.py`)
    + portal `test_return_controller` viết lại + `test_portal_return_f13` 5 HttpCase; 2 test quét badge base.
    `check_layers` (`PENDING_SPLIT = set()`), `deploy.yml`, reseed.
  - Chapter 74: đoạn F13, dòng P8, số `.po`.
- Commit: `a138d21` — `feat(F13): tách return → module nghiệp vụ wujia_return + controller mỏng` (đã push `main`).
- Đã dọn: 8 DB đo `wujia_f13*` + filestore, worktree `scratchpad/f13/head`.
- UAT sau deploy (26/09, chỉ-đọc): 3 version đúng · 14 phiếu (5 duyệt/2 hoàn tất/3 nháp/2 từ chối/2 đã gửi) · 5 loại lỗi · số kế RTN 5 · CA 1 · `wujia_return` 231 xmlid (230 + 1 field, như F8–F12) · portal còn 5 view · nhóm Quản lý 1 người, module cũ 0 nhóm · form backend đủ 6 nút cho Quản lý (`groups=wujia_return.`) · browser PC 1440 + mobile 390, 20 màn (danh sách, 4 lọc, form, 2 chi tiết, mã không tồn tại → `notice=not_found`, Home) 200, 0 tràn, 0 lỗi JS/HTTP; Home mobile hiện nhãn bảng chung. **ĐẠT.**
- Deploy: **đã deploy UAT 26/09** (không đụng module Thái). Lệnh: `-i wujia_return -u wujia_portal_return,wujia_portal_base`.
  Sau deploy đo chỉ-đọc: `wujia_return 19.0.1.0.0` · `portal_return 19.0.4.0.0` · `portal_base 19.0.7.28.0`, portal còn
  5 view, số kế RTN 5 · CA 1, nhóm Quản lý 1 người, 14 phiếu, `/portal/return` 200.
- Số đo: module mới 230 xmlid + 54 cons + 3 rel · snapshot 287 đổi chủ, 3 lệch (arch 2 view `groups` cố ý + `write_date`
  loại lỗi) · HTML 4 phiên **298/306 giống từng byte, 2 lần**, 8 khác = nhãn Home mobile cố ý (28 nhánh gửi phiếu × 2
  user) · DB sau ghi giống · focused 355/0 · suite **912/0/0** · test portal mới trên HEAD 4/5 (đỏ đúng test nhãn Home) ·
  DB trắng 0 đỏ · deploy DB giống UAT exit 0 · mutation **7/7** · Playwright 16 màn 0 tràn · `check_layers` 0 vi phạm.
- Đổi hành vi có chủ đích: Home mobile "Chờ xử lý" → "Đã gửi", "Đang xét" → "Đang xử lý", "Hoàn thành" → "Hoàn tất", phiếu
  bù một phần hiện "Đang bù một phần" (màu giữ). Lỗi bất ngờ ở bước đính kèm/gửi giờ rollback cả phiếu.
- Báo BA: đổi chữ Home mobile ở trên + câu hỏi KPI "đổi trả đang mở" có tính `reviewing` không (giữ luật cũ: không).
- Bài học: test Home phải cố định `request_date` từng cặp (Home chỉ lấy 2 phiếu mới nhất ⇒ thứ tự ngẫu nhiên nếu trùng
  giờ). Test rollback dùng `try/except`, không `assertRaises` (tự bọc savepoint — bài học F8).
- Phiên kế: đo UAT sau deploy F13 → **★FR-A** (review lại toàn khối A F7–F13, không làm tính năng).

## ★FR-A — Review toàn khối A (F1, F6, F7–F13) · 26/09/2026 · Mac
- Kết quả: ✅ **ĐẠT — khối A khép.** Doc: `docs/f-review-FR-A.md`. Không lệch tầng phía Dev; query/route giống hệt đối
  chứng; sửa nhỏ theo luật ★ + fix retest-fail `UI-DATALIST-001` (chưa deploy).
- Đầu phiên: F13 đã lên UAT (43 version khớp HEAD `164d8ec`, `wujia_support 19.0.1.0.1` = F10-fix đã lên). Chủ dự án chốt
  3 việc: review clean/perf/cấu trúc · soi Issue List còn component nào · lệch plan chỉ ghi. Chốt thêm: sửa nhỏ <30 dòng
  làm ngay; `UI-DATALIST-001` (History 26/09 BA retest fail) kiểm rồi sửa.
- Đã làm:
  - Mốc: worktree `9d2a606` (ref) ‖ HEAD; `wujia_fra` = `wujia_frp` + replay 6 đợt deploy (0 ERROR) ‖ `wujia_fra_ref`
    cùng seed; DB trắng `-i` 7 L2 EXIT 0, test 123/0/0; snapshot 1031 đổi chủ, 12 lệch giải trình + 1 bẫy mới (`INF/`
    `number_next`); HTML 63/68 giống từng byte (5 khác = nhãn Home F13 + fix debt); query 17 route × 4 user Δ0; nav 0;
    wj_measure 0 mất record; Playwright 16 màn × 2 user 200/0 tràn; mutation M0–M7 (M7 `extra` hook chỉ `pre_init` ⇒ nợ);
    `check_layers` 0 Dev (R7 Thái 2).
  - Sửa nhỏ ★ (11 file, +16 −112): 4 hàm chết `utils.py`, `is_read_by`/`get_display_summary`, `ormcache` thừa, 3 import
    thừa, `number_next` sequence INF, 14 comment mã phiên → 0 trong code khối A.
  - `UI-DATALIST-001`: `/portal/debt/payment-history` mobile dùng chung lát phân trang + `wj_pagination`; card 2 dòng chỉ
    bằng hàng chuẩn `wj_list_card_row` (CSS riêng màn bị test quét E5 chặn đúng luật — bỏ). 47 thẻ 124 → 10 thẻ 104 ở 390/360
    (kể cả memo dài 23 ký tự như UAT); PC md5 giống ở 3 biến thể trang; +2 test; `wujia_portal_debt 19.0.4.15.0`; ledger lượt 2;
    `qa_sync` dry-run 1 dòng — **chưa `--apply`** (chờ deploy).
  - Issue List: 138 issue (123 Done · 8 RfD · 4 RfR · 3 NC). 17/23 component có issue; đề xuất mở mới chỉ EmptyState;
    8 issue mở → 4 cụm 140+141 · 143+144+145 · 142 · 146. 7 issue mới 0 dòng code.
- Commit: `review(FR-A)` (sửa nhỏ + doc + test quét) và `fix(debt): pager + card payment-history mobile (UI-DATALIST-001)`.
- Đã dọn: 5 DB `wujia_fra*` + filestore, worktree `scratchpad/fra/head7`, 2 server 8097/8098.
- Deploy: **đã deploy UAT 26/09** (chủ dự án, sau push `caffb33`). Đo chỉ-đọc RPC: `wujia_portal_debt 19.0.4.15.0` installed,
  view `portal_debt_payment_history` write_date 13:31 có `t-foreach="payments"` ×2 + `dl_pager`/`wj_pagination`, 0 class cũ;
  9 số kế sequence giữ nguyên (INF 1 · RTN 5 · CA 1 · ANN 20 · KNW 28 · WJ-TK 17 · WJ-CRS 5 · WJ-EXR 17 · WJ-EXS 6);
  UAT có 12 giao dịch tháng 9 ở HCM-01 để BA retest. Ledger → ĐÃ DEPLOY, `qa_sync --apply` ghi 6 ô + 1 History
  (UI-DATALIST-001 → Ready for Retest). Chưa đo browser trên UAT bằng tài khoản portal (không đăng nhập thử mật khẩu).
- Số đo: suite **912 → 914/0/0** · DB trắng 123/0/0 · HTML 63/68 · query Δ0/17 route · mutation 7/8 (M7 giải trình) ·
  comment mã phiên còn 49 `.py` / 349 mọi file (ngoài khối A) · `_sql_constraints` 16 file (8 Dev).
- Bài học: test quét component là hàng rào thật (CSS 1 dòng cho màn bị chặn, sửa bằng bố cục hàng chuẩn); đo với dữ liệu
  dài như UAT (mồi 1 bản ghi rồi xoá); DB copy không filestore phải xoá attachment `/web/assets/%` trước khi đo browser;
  md5 khối PC lệch có thể do bản ghi mồi, không phải template.
- Phiên kế: deploy fix debt (chủ dự án) → BA retest 126 → **Issue List cụm 140+141** (shell header/store) hoặc cụm
  143+144+145 (mật độ mobile, đo trên khung E7 trước).

## END-SPRINT 63 — chốt sổ khối A kiến trúc (F6 → ★FR-A) · 26/09/2026 · Mac
- Kết quả: ✅ xong. Phiên tài liệu, **0 file dưới `custom/`**, không deploy, không đụng sheet (ledger: `UI-DATALIST-001`
  đã sync ở ★FR-A, không có issue mới).
- Chủ dự án chốt: chapter mới 77 (Sprint 63) · ADR-027 **chốt** + ghi 3 ý đã bàn · smoke `-u` (không chạy lại suite).
- Đã làm:
  - Smoke: copy `wujia_frp` → `wujia_es63`, chạy đúng lệnh `deploy.yml` (`-u/-i` 24 module + `wujia_portal_debt`)
    ⇒ **RC 0, 0 ERROR/Traceback**, 7 L2 installed, 0 module kẹt; 1 WARNING vô hại (`__pycache__` trong
    `wujia_portal_return/migrations/`). DB đã drop. Suite dẫn số ★FR-A 914/0/0.
  - Chapter `77-sprint63-cluster-f-block-a.tex`: vì sao có khối A · F6 · F7 + ★FR-P · bảng 6 module L2 (nhận gì, luật
    nào về model) · 4 bẫy · ★FR-A · nghiệp vụ · trade-off · bài học · nợ. `\include` sau chapter 76.
  - Chapter 74: trạng thái "đã chốt 26/09, đã áp khối A"; §addendum 3 ý (portal theo chức năng, mobile kế thừa view,
    `auto_install` — ghi chưa áp); `wujia_announcement` → `wujia_notification` (text + hình ERD); depends 7 L2 theo
    manifest thật; số đo F8–FR-A dời sang ch.77, giữ 2 bài học quy trình; câu BA #6 ghi "đã làm theo ADR ở F13".
    `adr-027-module-layering.tex` đổi trang bìa (đã chốt).
  - Compact summary: dòng Cập nhật · §3 ADR-027 đã chốt · §4 dòng 63 · §5 State END-SPRINT 63.
    `next-session-clusters-F.md` §2: ghi chốt sổ. `~/.claude/commands/wujia-start.md`: ADR-027 đã chốt.
- Commit: xem git log — `docs(multi): sprint 63 close-out`.
- Deploy: không.
- Số đo: `build-doc.sh` **312 → 321 trang**, 0 `! `; ADR PDF **12 → 15 trang**, 0 ref lỗi; 0 chữ Việt trong `\texttt` của
  phần mới (2 chỗ `portal\_<chức năng>` đã sửa).
- Bài học: local `wujia_tea_19` còn trước F7 ⇒ smoke khối A phải dựng từ `wujia_frp` + replay deploy; python Mac là env
  `odoo19` (env `odoo` thiếu `rjsmin`, chết 255 trước khi nạp module).
- Còn treo: `auto_install` áp đồng loạt 1 phiên · 7 câu hỏi BA ADR-027 · nợ ch.77 · BA retest 126.
- Phiên kế: **Issue List cụm 140+141** (shell header PC + store switcher mobile, cùng `wujia_portal_layout`) hoặc
  **143+144+145** (mật độ mobile, đo trên khung E7 trước).

## Phân cụm G — Issue List STT 140–146 · 26/09/2026 · Mac
- Kết quả: ✅ xong. Phiên phân cụm, **0 file dưới `custom/`**, không deploy, không ghi sheet.
- Chủ dự án chốt: quay lại Issue List; **chuẩn hoá component làm trước**; tên lứa **cụm G** (không phải F — F
  đã là cụm kiến trúc; G1/G2 ngày 18/09 là phiên lẻ khác); 144 làm cuối G1.
- Đã làm:
  - `issue_queue.py --dev`: 7 issue Ready for Dev (140–146), 0 Retest Failed. Reconcile `git log -S` + `grep`:
    chỉ commit docs nhắc mã, 0 code, 0 ledger ⇒ cả 7 chưa fix.
  - Đọc đủ cột `Đề xuất` + `Kết quả mong muốn` + `Ghi chú` (qua `sheet_io.read_values`), soi seam trong source.
  - `docs/next-session-clusters-G.md`: bảng Tiến độ + luật chung + 4 khối prompt: **G1** 143+145→144 (mật độ mobile,
    `wujia_portal_layout`+`_sale`) · **G2** 141+140 (Current Store mobile/PC + nút giỏ, `portal_base`+`portal_sale`) ·
    **G3a/G3b** 142 Home PC V4 · **G4** 146 URL gốc `/`.
  - Compact summary: dòng Cập nhật · §5 State · §13 "Bảng cụm G".
- Commit: xem git log — `docs(G): phân cụm Issue List 140–146`.
- Deploy: không.
- Số đo: 7/7 ID có mặt đúng 1 cụm; call site PageHeader 77/14 module, SectionHeader 57/8 module (grep — G1 phải đếm lại
  bằng cấu trúc).
- Lệch plan / quyết định mới: không.
- Nợ để lại: mockup V4 (142) + mockup 141 chỉ có trên Drive — cần file trước G2/G3a. BA retest 126 vẫn treo.
- Phiên kế: **G1** — hỏi đầu phiên: không có (145 ngược "BA final 83px" chỉ ghi FYI). Việc cần biết trước: dựng DB từ
  `wujia_frp` + replay `deploy.yml`; đo 360/390/430, PC Δ0.

## G1 — Mật độ mobile: PageHeader · SectionHeader · BottomNav + nhịp Đặt hàng (143 · 145 · 144) · 26/09/2026 · Mac
- Kết quả: ✅ code + đo xong, **đã deploy UAT + đo lại đạt**. 3 issue ghi ledger (`ĐÃ DEPLOY UAT`), chờ `qa_sync --apply`.
- Chủ dự án chốt: PageHeader mobile **cả 3 kiểu (title/back/create) cùng cao 44** (pad 8/1/0).
- Đã làm:
  - `wujia_portal_layout` 19.0.59.0.0: token mobile `--wujia-m-pagehead-py 8`, `--wujia-m-sechead-fs/lh 18/24`;
    PageHeader `--m` 52 → 44; SectionHeader `--m` 18/24, `--any` chỉ đổi trong `@media ≤991.98`; nav 83 → **72 + safe
    area**, mục 50, nhãn 12, badge neo góc icon; sửa công thức `--wujia-mnav-total` (sai từ trước) ⇒ sheet "Thêm" +
    backdrop bám `-total` (hết chồng nav 8px khi có safe area); pad cuối nội dung `72 + 13` thay số cứng 96.
  - `wujia_portal_exam` 19.0.6.1.0: FAB bám `-total`.
  - `wujia_portal_sale` 19.0.4.26.0 (144, làm cuối): chỉ ở wrapper `.wujia-morder` — search → chip 23 → **12**
    (nguồn 23 = `form` margin 15 toàn cục), chip → "Danh sách sản phẩm" 14 → **8**.
  - 16 test tĩnh mới (tag `wujia_mobile_density_g1`, `wujia_order_spacing_g1`) + `scripts/qa/wj_density.py` (Playwright:
    PageHeader/SectionHeader/nav/badge/cuộn cuối/nhịp Đặt hàng + vân tay bố cục PC, cờ `--safe-area`).
  - `docs/g1-acceptance-matrix.md`; ledger 3 entry.
- Commit: xem git log — `feat(G1): mật độ mobile PageHeader/SectionHeader/BottomNav + nhịp Đặt hàng`.
- Deploy: ✅ UAT 26/09 (`-u wujia_portal_layout,wujia_portal_exam,wujia_portal_sale`), chủ dự án làm tay. Đo chỉ-đọc
  `wj_density.py --readonly` (`em.hcm`): mobile 26 route × 3 khổ × có/không safe area đạt (1 lần Giỏ hàng @360 title 2 dòng
  thoáng qua, 9 lần đo lại đều 44), PC 20 route × 3 khổ không nav/không tràn; 0 request bị chặn. Ledger → `ĐÃ DEPLOY UAT`.
- Số đo: 28 route × 360/390/430 × có/không safe area 34: PageHeader 44 mọi kiểu, SH 18/24, nav 72 (106), cuộn cuối ≥13,
  0 tràn, badge không chạm icon; Đặt hàng 12/8 giữ sau lọc AJAX + tìm, smoke +/−/thêm giỏ 0 lỗi JS; PC vân tay
  **76/81** giống (5 = bộ đếm lượt xem Kiến thức, nhiễu nền); suite 21 module **930/0/0**; mutation **11/11**;
  `check_layers` 0 vi phạm Dev.
- Lệch plan / quyết định mới: sửa kèm 2 lỗi có từ trước (công thức `mnav-total`; sheet/FAB bỏ quên safe area).
- Bài học: xem "🔴 Bài học G1" trong `next-session-clusters-G.md` (form margin 15, CDP safe area, vân tay thay md5,
  `--any` ngoài media, filestore ⇒ xoá `/web/assets`).
- Nợ để lại: safe area chưa đo iPhone thật; nhánh Đặt hàng không có danh mục chưa đo trình duyệt; FYI BA 83 → 72.
- Sheet (27/09): `qa_sync --apply` 3 ID → Ready for Retest, kiểm lại bằng `export?format=csv` khớp cột ID (dòng 136/137/138).
  🔴 Phát hiện lỗi có từ trước của `qa_sync`: cột Odoo Fit ghi số cứng 17 = **R "Related Reference IDs"** (BA đã chèn cột,
  Odoo Fit dời sang S) ⇒ mỗi lần sync đè R bằng "Custom". Đã trả R gốc cho 143/144/145 (lấy từ bản dump đầu phiên) và sửa
  tool dò cột theo **tên header** (thiếu header thì dừng) + đường ledger qua symlink. **6 dòng cũ bị đè R, chưa khôi phục
  được** (không còn bản gốc): STT 126 `UI-DATALIST-001`, 129 `UI-PAGECONTAINER-001`, 131 `UI-SIDEBAR-001`, 132
  `UI-BUTTON-001`, 136 `UI-LISTCARD-001`, 139 `UI-FILTER-001` — cần lấy lại qua Version history của Google Sheet.
- Phiên kế: `qa_sync --apply --only` 3 ID (nếu chưa chạy), rồi **G2** (141 + 140) — hỏi đầu phiên câu (a)–(e) trong
  khối G2 (user 1 cửa hàng có chevron không, nhãn Manager ↔ "Quản lý", mockup 141, dải trên Home, 140 ↔ V4).

## G2 — Dải cửa hàng mobile (141) + top bar PC giỏ/chuông/khối Cửa hàng (140) · 29/09/2026 · Mac
- Kết quả: ✅ code + đo xong, **đã deploy UAT 30/09 + đo lại đạt**. 2 issue ghi ledger (`ĐÃ DEPLOY UAT`), chờ `qa_sync --apply`.
- Chủ dự án chốt: (a) user 1 cửa hàng → **ẩn chevron**, dải tĩnh · (b) nhãn vai trò **tiếng Việt một nguồn**
  (Chủ tiệm / Quản lý / Nhân viên) ở cả mobile lẫn PC · (d) **hiện dải trên Home** theo mockup · (e) chip vai trò trong
  khối theo 140, FYI BA mockup V4 vẽ tách.
- Đã làm:
  - `wujia_portal_base` 19.0.7.29.0: `ROLE_LABELS` dời vào `models/wujia_franchise_member.py` + `_portal_role_label()`
    (controller import lại, không thêm depend); dải mobile thêm chevron **chỉ trong thẻ bấm** (>1 cửa hàng); nhãn VN ở
    dải, khối PC, menu tài khoản, hero Home mobile; CSS: nền lên `.wujia-store-current-block` (hover tô cả khối, pill
    trong suốt), bỏ `capitalize`, chevron màu chính `flex: 0 0 auto`.
  - `wujia_portal_layout` 19.0.59.1.0: circle giỏ/chuông ≥1200 tự khai `inline-flex` căn giữa (gốc: `.nav-link{display:
    block}` của `web.assets_frontend` nạp sau, hồi quy từ cụm B `157814a` 04/08); icon 19/20 với selector thắng Vuexy
    `ficon` (0,4,3); badge `top:-8 right:-6`; chữ vai trò dưới avatar VN; `?v=1326`.
  - 11 test mới (tag `wujia_store_switcher_g2`, `wujia_pc_topbar_g2`); `test_e8c_account_menu` đổi 'Owner' → 'Chủ tiệm'.
  - `scripts/qa/wj_shell_g2.py` (Playwright, cờ `--readonly` cho UAT); `docs/g2-acceptance-matrix.md`; ledger 2 entry.
- Commit: xem git log — `feat(G2): dải cửa hàng mobile có chevron + top bar PC giỏ/chuông/khối Cửa hàng`.
- Deploy: ✅ UAT 30/09 (`-u wujia_portal_base,wujia_portal_layout`), chủ dự án làm tay. Đo chỉ-đọc `wj_shell_g2.py --readonly`
  (`em.hcm`, 1 cửa hàng): mobile 26 route × 3 khổ có dải, không chevron, 0 tràn; PC 3 route × 3 khổ icon giữa, badge 0 chạm,
  chip trong khối; nhãn VN 5 chỗ; 0 request bị chặn. Ledger → `ĐÃ DEPLOY UAT`. UAT chưa có user nhiều cửa hàng để thử bấm.
- Số đo (DB `wujia_g2s` = copy `wujia_g1`): mobile 27 route × 360/390/430 × 2 user — `dung.multi` chevron mép W−16, 4/4 vị
  trí bấm mở overlay, nhấn `rgb(224,247,255)`, focus viền 2px; `anh.owner` `<div>` không chevron; tên dài "…" giữ vai trò +
  chevron; 0 tràn. PC 3 route × 1440/1280/1200: lệch tâm icon (−9.4,−9.5) → (0,0), badge "12" ∩ icon 59.4 → 0 px², số 0
  ẩn, chip vai trò trong khối 430×48. Kênh bên kia: PC 78/81 lệch chỉ ở nền khối + chữ vai trò (3 = trang 403), mobile Δ0
  ngoài dải. Suite 20 module **941/0/0**; mutation **9/9**; `check_layers` 0 vi phạm Dev.
- Lệch plan / quyết định mới: plan định đưa chip vào trong `<a>` — làm bằng CSS (nền lên khối) thay vì đổi DOM, giữ
  nguyên vùng bấm; nhãn VN lan thêm 2 chỗ (chữ dưới avatar PC, hero Home mobile) cho đồng nhất theo (b).
- Bài học: xem "🔴 Bài học G2" trong `next-session-clusters-G.md` (thứ tự nạp `assets_frontend`, Vuexy `ficon`, transition
  khi đo `:active`, log chuyển của `wujia_core`, `-u` cho test post_install, `display_name` stored, hai server chung source).
- Nợ để lại: nhãn vai trò chưa dịch EN/ZH (một nguồn VN); nhấn/focus đo bằng ép pseudo-class, chưa bấm máy thật; cột R 6
  dòng cũ (mục G1) vẫn chờ khôi phục qua Version history. Server 8032 + DB `wujia_g2s` còn để đo lại (xoá được sau deploy).
- Phiên kế: deploy G2 → `wj_shell_g2.py --readonly` trên UAT → `qa_sync --apply --only` 2 ID; rồi **G3a** (142 Home PC V4 —
  khung: hàng đầu 50/50, 4 KPI, bỏ hero + Thao tác nhanh).

## G3a — Home PC khung mockup V4 (142) · 30/09/2026 · Mac
- Kết quả: ✅ code + đo xong, commit. **Chưa deploy**: chủ dự án chốt deploy gộp với G3b (một lần `-u`) để BA không thấy
  Home PC nửa mới nửa cũ. **Chưa ghi ledger 142**: issue chỉ đóng ở G3b.
- Đầu phiên: `qa_sync --apply --only` 140/141 → Ready for Retest ("ĐÃ DEPLOY UAT 30/09/2026"). Cột R, S nguyên.
- Chủ dự án chốt:
  - chỉ làm G3a;
  - bỏ KPI "Đơn chờ xử lý" + bảng "Sản phẩm mua nhiều nhất" theo đúng danh sách BA, "chỗ nào limit ráng xử". Vì vậy ô
    Công nợ PC làm số thật luôn, không để inert.
- Đã làm:
  - `wujia_portal_base` 19.0.7.30.0: khối desktop `wujia-home-pc` gồm hàng đầu 50/50 (card Cửa hàng hiện tại: tên,
    vùng/địa chỉ, pill vai trò `ROLE_LABELS` | card Khung giờ: 3 trạng thái + thanh tiến độ, dùng chung
    `_order_window_view`) và 4 KPI Đơn hàng · Thông báo · Đổi trả · Công nợ, cùng biến và link với mobile, bỏ mũi
    tên/vạch ngăn.
  - Controller xoá `waiting_orders_count` + method `_top_products` và các key top SP.
  - CSS PC trong `@media ≥992` có tiền tố `.wujia-home-pc`; xoá class chết `.wujia-kpi-arrow` / `.wujia-kpi-separator`.
  - 3 block list cũ tạm giữ tới G3b.
  - `wujia_portal_debt` 19.0.4.16.0: đặt khe `home_debt_kpi` một lần trước khối PC; ô PC và ô mobile dùng chung, gỡ
    module thì ô PC về "—".
  - Test: 17 test mới (`wujia_home_pc_g3a` 15, `wujia_home_debt_g3a` 2). `test_scan_d5_data_list` bỏ Home. F11 regex đổi
    theo nhãn "Thông báo".
  - Công cụ đo: `scripts/qa/wj_home_g3.py`. Nghiệm thu: `docs/g3-acceptance-matrix.md`.
- Commit: xem git log — `feat(G3a): Home PC khung V4 — hàng đầu cửa hàng|khung giờ + 4 KPI như mobile`.
- Deploy: ☐ gộp G3b.
- Số đo (DB `wujia_g3s`, server 8033):
  - PC 1440/1280/1024/992: 2 card hàng đầu cao bằng nhau (lệch 0, kể cả chuỗi dài); 4 KPI một hàng, đúng thứ tự và
    link; 0 tràn, 0 mũi tên; 991 ra mobile. Công nợ: `dung.multi` "17,8tr" → `/portal/debt`, `anh.owner` "—".
  - Mobile 360/390/430 vân tay **Δ0**. 26 route PC khác Δ0 (chỉ lệch do dữ liệu).
  - Query `/portal` **−7** (46→39, 43→36): 1 count + 2 `_read_group` + 4 đọc kèm.
  - Mutation **7/7** đỏ.
  - Suite 20 module 958 test: 1 error ở F11 (regex nhãn cũ). Đã sửa, chạy lại 3 module **384/0/0**.
  - `check_layers` 0 vi phạm Dev.
- Lệch plan / quyết định mới:
  - Plan định cắt tên cửa hàng bằng ellipsis. Đổi sang **xuống dòng** vì BA cấm cắt chữ.
  - Query −7 chứ không −3 như plan.
  - Plan định chèn biến Công nợ ở đầu wrapper. Làm bằng `t-set` đặt trước khối PC.
- Bài học: xem "🔴 Bài học G3a" trong `next-session-clusters-G.md`. Tóm tắt:
  - owner DB `odoo19`;
  - werkzeug INFO + log theo ngày UTC;
  - `cr.sql_log_count` để tách Δ query;
  - `t-set` dùng chung qua xpath;
  - bỏ comment trước khi test arch;
  - patch `request` bằng `new=`;
  - đổi nhãn Home thì grep test module khác.
- Nợ để lại:
  - FYI BA: thanh tiến độ màu token mobile (V4 vẽ xanh); pill vai trò soft (V4 đặc); đơn chờ xử lý xem ở
    `/portal/purchase-history`, top SP ở Báo cáo.
  - Token `--wujia-kpi-separator-*` còn trong layout.
  - 🔎 Topbar PC 992–1199 chật, logo bị khối Cửa hàng che. Có từ trước, không do G3a; báo BA thành issue riêng.
  - Server 8033 + DB `wujia_g3s` để lại cho G3b.
- Phiên kế: **G3b** (142): 7 block record thay 3 block list cũ, VNĐ, "Xem tất cả", icon theo loại, chuỗi VI/EN/ZH. Xong
  thì `-u wujia_portal_base,wujia_portal_debt` một lần + deploy + ledger 142 + `qa_sync`. Seam ở khối "G3a đã xong" trong
  `next-session-clusters-G.md`.

## G3b — Home PC 7 block record theo mockup V4, đóng 142 · 30/09/2026 · Mac
- Kết quả: ✅ code + đo xong, commit; ledger `UI-PC-HOME-REDESIGN-001` ghi ("CHƯA DEPLOY"). Nghiệm thu 12/12 = 100% "Kết
  quả mong muốn" (`docs/g3-acceptance-matrix.md` §6). **Deploy G3a + G3b gộp một lần**: chờ cổng duyệt push `main`.
- Chủ dự án chốt:
  - Giao hàng: "N đơn chưa giao" là dòng phụ, góc phải "Xem tất cả" → `/portal/delivery`;
  - lưới **2 cột 992–1399, 3 cột từ 1400** (đổi từ "3 cột từ 1200" sau khi đo ra sidebar chỉ hiện từ 1200, cột sẽ còn
    ~280px);
  - chuỗi VI/EN/ZH đo bằng dữ liệu dài; dòng Thông báo dùng ô icon chuông như mobile.
- Đã làm:
  - `wujia_portal_base` 19.0.7.31.0: xoá 3 block list cũ, thay bằng `div.wujia-home-blocks` với 7 SurfaceCard + CardHeader
    PC (icon theo loại, "Xem tất cả" 5 block, không mũi tên). Dòng chép từ block mobile: cùng biến, `portal_money`, badge,
    link. Hỗ trợ nhanh 3 lối tắt; Thông tin cửa hàng rộng cả hàng, 3 ô có vạch ngăn.
  - Map màu loại thông báo gom về **một** `noti_badge_map` (`t-set` trước khối PC) cho cả mobile và PC.
  - CSS trong `@media ≥992` + `≥1400`, tiền tố `.wujia-home-pc`: CSS grid 2→3 cột, gỡ ellipsis tiêu đề/dòng phụ, CardHeader
    `nowrap`, empty state không khung lồng.
  - Controller **không sửa**.
  - Test: `test_g3b_home_pc.py` 17 test (tag `wujia_home_pc_g3b`); sửa theo `test_scan_d3_card_header` (5 → 9),
    `test_scan_d5_data_list` (preview 5 block, COMPACT_SITES bỏ Home, mobile loại `.wujia-home-pc`, mdash 10 → 13).
  - `scripts/qa/wj_home_g3.py` thêm 1200/1199, probe 7 block (cột theo hàng, Δh, badge đè, chevron, block cũ).
- Commit: xem git log — `feat(G3b): Home PC 7 block record theo V4 …`.
- Deploy: ✅ push `d8f89bf` 16:01, UAT nhận 16:04 (G3a `160d13e` push 01:16 trước đó nhưng UAT chưa nhận; lượt này đưa cả
  hai lên). Đo chỉ-đọc `em.hcm` 6 khổ PC: 7 block đúng thứ tự, 3 cột 365 ở 1440, 2 cột 992–1399, Δh 0, 0 tràn/chevron/badge
  đè, Công nợ "4,2tr"; mobile chỉ lệch 1px ở chữ đếm lùi khung giờ. Ledger "ĐÃ DEPLOY UAT" → `qa_sync --apply --only`
  142 → **Ready for Retest** (6 ô + 1 History). `issue_queue --dev` còn 0.
- Số đo (DB `wujia_g3s`, server 8033):
  - 7 khổ × 3 user: 0 tràn, 0 chữ bị cắt, 0 badge đè, 0 chevron, 0 block cũ; 3 cột 365px ở 1440, 2 cột 992–1399, Δh 0
    trong hàng; 991 ra mobile.
  - Chuỗi dài VI/EN/ZH (đơn, đổi trả, thông báo, bài viết, cửa hàng): 0 cắt, 0 tràn; trả dữ liệu từ bản lưu SQL.
  - Mobile Δ0 (`dung.multi` md5 trùng; 2 user còn lại chỉ lệch chữ đếm lùi khung giờ).
  - Query `/portal` 39/36/36 **Δ0** so với G3a.
  - 13 selector G3b: 64 phần tử ở `/portal`, 0 ở 26 route khác.
  - Mutation **7/7** đỏ. `wujia_portal_base` 315/0/0. Suite 20 module **975/0/0**. `check_layers` 0 vi phạm Dev.
- Lệch plan / quyết định mới:
  - Plan dùng `col-xl-4 col-lg-6`; đổi sang CSS grid vì BS4/BS5 xung đột thứ tự nạp.
  - Ngưỡng 3 cột 1200 → 1400 (hỏi lại chủ dự án sau khi đo).
  - Plan nói phải thêm dáng dòng PC; thực tế `.wujia-mdash-*` đã áp toàn cục, chỉ gỡ ellipsis.
- Bài học: xem "🔴 Bài học G3b" trong `next-session-clusters-G.md`. Tóm tắt:
  - bundle cũ khi chưa `-u`;
  - mdash toàn cục;
  - BS4/BS5 → CSS grid;
  - sidebar từ 1200;
  - CardHeader wrap trong card hẹp;
  - `conda run` nuốt stdin;
  - `-u` kéo theo debt;
  - push = deploy.
- Nợ để lại:
  - FYI BA (matrix §10): Xem tất cả ở Giao hàng; lưới 2 cột 992–1399; tile chuông; tiêu đề dài 2 dòng; Tổng tiền đổi trả
    "—"; hotline = `company.phone`; Chat UI-only; Người phụ trách chỉ tên.
  - 🔎 Topbar PC 992–1199 (từ G3a) vẫn chờ BA tách issue.
  - Server 8033 + DB `wujia_g3s` xoá được sau deploy.
- Phiên kế: **G4** (146 `WJ-PORTAL-ROUTING-001`, điều hướng `/`). Xoá server 8033 + DB `wujia_g3s` khi tiện.

## H150/151 — Home: giờ + trạng thái đơn gần đây giống Lịch sử (150 `WJ-HOME-009`, 151 `WJ-HOME-010`) · 30/09/2026 · Mac
- Kết quả: ✅ code + đo + deploy UAT + đo UAT chỉ-đọc; 150 + 151 → Ready for Retest.
- Đầu phiên:
  - Định làm G4, nhưng **STT 146 không còn trên sheet** (145 → 147). Chủ dự án chuyển sang 150 + 151 (status `New`, cho
    làm trước). G4 ⏸, cách làm đã chốt, ghi ở khối G4 `next-session-clusters-G.md`.
  - BA mở 147–151 cùng lứa, đều từ đơn test S00075.
- Đã làm:
  - 150: chẩn đoán **đã hết từ G3b** — block PC cũ in `date_order` UTC, G3b thay bằng `wj_dt`. UAT chỉ-đọc `em.hcm`:
    S00075 PC = mobile = chi tiết Lịch sử = 22:57 29/09. Chỉ thêm test chặn hồi quy.
  - 151: Home có bảng nhãn riêng `MOBILE_ORDER_BADGES` (draft → "Nháp"). Dời luật trạng thái SO của Lịch sử xuống
    `wujia_portal_base/controllers/utils.py` (`portal_order_status`, `portal_order_badge`). Home PC + mobile gọi
    `wj_order_badge(o)`. Lịch sử import lại (alias `_state_meta` / `_order_status` cho `portal_sale` + test).
  - Xoá `MOBILE_ORDER_BADGES` + `wj_badge_default`. `portal_base` 19.0.7.32.0 · `purchase_history` 19.0.3.20.0.
- Commit: `0cd1f0a` — `fix(WJ-HOME-009/010): Home dùng chung luật trạng thái đơn với Lịch sử + test giờ PC`.
- Deploy: ✅ UAT `wujia_portal_base` 19.0.7.32.0 · `purchase_history` 19.0.3.20.0 (30/09 16:45). Đo chỉ-đọc `em.hcm` +
  `anh.owner`: 4 đơn trùng chữ/màu/giờ ở Home PC, Home mobile, chi tiết Lịch sử (S00075 22:57 · Chờ xác nhận); 6 khổ PC
  0 tràn/cắt/đè. `qa_sync --apply` → 150 + 151 **Ready for Retest** (6 ô mỗi dòng + 1 History mỗi issue; bridge trả
  non-JSON/404 nhưng đã ghi — đọc lại xác nhận). `dung.multi` không đăng nhập được UAT (mật khẩu khác local).
- Số đo (DB `wujia_g3s`, server 8033):
  - Nhãn Home trước/sau: "Nháp" neutral → "Chờ xác nhận" pending (3 user). Đơn 1799/12 khớp chữ + màu + giờ với chi
    tiết Lịch sử.
  - Query `/portal` 27/36/36 → 27/36/36 **Δ0**.
  - `wj_home_g3.py` 6 khổ PC: 0 tràn, 0 cắt chữ, 0 badge đè, Δh 0. Mobile đổi vân tay đúng do chữ nhãn.
  - Test mới 9 (tag `wujia_home_order_status`); mutation **6/6** đỏ. `-u` 2 module + test 3 module 393/0/0.
  - Suite 20 module (`-u` cả 20, có `wujia_sale`): 939, 0 failed, **2 error ở `wujia_sale`** (fixture tạo quant cho
    hàng consumable) — không liên quan, chưa sửa.
  - `check_layers` 0 vi phạm tầng (R7 2 dòng ở `wujia_franchise` có sẵn).
- Lệch plan / quyết định mới:
  - Test mới đặt ở `wujia_portal_purchase_history/tests/`, không ở `portal_base`, vì phải so với `_history_row_vals`.
  - Nghiệm thu ghi ở `docs/g3-acceptance-matrix.md` §12 (§11 đã có sẵn).
- Bài học:
  - 146 biến khỏi sheet mà `issue_queue --dev` không báo gì (chỉ ra 0). Đầu phiên nên liệt kê STT cuối sheet so với
    bảng cụm đang làm.
  - Bảng nhãn "mobile-riêng" trong `portal_base` là nguồn lệch. Mọi nhãn trạng thái SO phải đi qua `portal_order_status`.
  - Suite có `wujia_sale` ra 2 error fixture — biết trước để khỏi tưởng hồi quy.
- Nợ để lại:
  - FYI: Home UAT in tiền `$` (dữ liệu/đơn vị tiền của đơn), ledger G3b ghi "UAT là VND nên in ₫" — cần soi lại.
  - 2 error test `wujia_sale` (`test_06_filters_return_right_orders`, setUpClass `TestWujiaSupplyDemandReport`).
  - Hỏi BA: 146 xoá hay chuyển chỗ.
  - Server 8033 + DB `wujia_g3s` xoá được.
- Phiên kế: **148 `WJ-ORD-028`** (High — hộp xác nhận trước khi gửi đơn, chống double-submit), rồi 147 (tìm kiếm giữ
  query cũ) và 149 (ẩn "Ngày xác nhận" khi đơn còn nháp). Cả ba đang `New`, hỏi chủ dự án có làm trước không.

## Review cụm G trên UAT (G1 · G2 · G3a/b · H150/151) · 30/09/2026 · Mac
- Kết quả: ✅ review xong, chỉ đọc, 0 dòng code. Báo cáo `docs/g-review-uat.md`: 25 dòng AC → 20 ✅ · 1 ❌ · 4 LIMIT (95 % dòng
  đo được).
- Đầu phiên: chủ dự án tưởng G4 đã xong; git + UAT không có G4, session "Wujia issue G4" xác nhận chưa có dòng code (146 mất
  khỏi sheet) ⇒ review bỏ G4.
- Đã làm: version UAT = HEAD `ee22cb5` (6 module); `wj_density` mobile 26 route × 3 khổ × safe area 0/34; `wj_shell_g2`;
  `wj_home_g3` (bản chép chặn ghi) 6 khổ PC + 3 mobile; đối chiếu S00075 Home ↔ Lịch sử; soát ảnh PC + mobile. 0 request bị chặn.
- Phát hiện:
  - ❌ Top bar PC vỡ ở **đúng 992**: hamburger `li.mobile-menu.mr-auto` nhận `margin-right` 451.7px ⇒ khối Cửa hàng rớt hàng,
    bị header cắt. 993+ bình thường. Có từ trước G2 (G2 không đổi width/margin khối).
  - LIMIT: bảng giá `Default` UAT là USD (công ty VND) ⇒ đơn portal in `$`; cần chủ dự án đổi cấu hình, không phải lỗi code.
  - Nhỏ: pill ngôn ngữ 992–1199 chỉ có cờ · mã chuyến giao xuống dòng giữa chữ ở card hẹp · bảng Công nợ 992 cắt cột Thao tác.
- Bài học:
  - UAT chập chờn (`goto` quá 30 s) khi chạy 2 bộ đo song song ⇒ chạy tuần tự, đặt timeout 90 s cho script phụ.
  - `wj_density` chỉ đo sheet "Thêm" khi có `--shots`; lượt safe area phải bật `--shots` mới có số sheet.
  - Lỗi chỉ ở một khổ đúng mốc (992) ⇒ quét ±1px quanh mốc breakpoint, và so computed style 2 khổ để ra ngay thuộc tính gây lỗi.
- Nợ để lại: lượt sửa top bar 992 (`wujia_portal_layout`); quyết tiền tệ bảng giá UAT; G4 chờ BA.
- Phiên kế: sửa top bar 992 (nhỏ), rồi 148 `WJ-ORD-028` · 147 · 149 (đang `New`, hỏi chủ dự án).

## G5 (147 + 148) + G6 (149) · 30/09/2026 · Mac
- Kết quả: ✅ code + đo + push + **UAT nhận 19:46:49** (`portal_layout` 19.0.59.2.0 · `portal_base` 19.0.7.33.0 ·
  `portal_sale` 19.0.4.27.0 · `purchase_history` 19.0.3.21.0). Commit `887da0a` (G5) · `9efa67f` (G6).
  Nghiệm thu `docs/g5-acceptance-matrix.md` (148 6/6, 147 4/4) · `docs/g6-acceptance-matrix.md` (5/5).
- G5: hộp xác nhận gửi đơn PC + mobile; gửi lặp khi giỏ rỗng ⇒ về đơn vừa tạo (không đổi schema). 147 gốc = khoá
  CMP-BTN-001 (E6a) không nhả khi lọc AJAX ⇒ dính cả 11 màn danh sách; sửa bằng `wj:form:release`. Sửa kèm: nút gửi đơn
  mobile không POST (từ E6a). Test 13, mutation 12/12, suite 1006 (1 FAIL móc E6 đã sửa, 1 error fixture `wujia_sale` có
  sẵn), query Δ0 27 route, mobile Δ0.
- G6: `confirm_date` chỉ khi `state == 'sale'`; cột PC "—", chi tiết ẩn dòng, nhãn "Ngày đặt hàng". Test 7, mutation 7/7,
  393/0/0, query Δ0. **UAT đo chỉ-đọc `wj_history_g6.py` em.hcm S00075/S00043: 12/12 đạt.**
- **Tiếp phiên (sau khi user dừng), đã xong:**
  - UAT chỉ-đọc G5 (em.hcm): `wj_order_confirm_probe.py` **8/8** (chỉ mở hộp rồi Hủy, 0 request gửi đơn) ·
    `wj_resubmit.py` **21/21**.
  - Ledger 3 entry → "ĐÃ DEPLOY UAT 30/09/2026 — sẵn sàng retest"; `qa_sync --apply --only` từng ID. Verify CSV:
    027/028/029 đều **Ready for Retest**, mỗi ID đúng 1 dòng `7. ISSUE HISTORY`.
  - ⚠️ 029: bridge ghi xong 6 ô rồi trả **không phải JSON** ⇒ `qa_sync` văng trước bước History. Không chạy lại
    `--apply` (sẽ ghi History "cũ = Ready for Retest"): tự `append_row` 1 dòng "Ready for Dev → Ready for Retest",
    bridge lại trả non-JSON nhưng đọc CSV thấy đúng 1 dòng. **Luật: lỗi JSON từ bridge ⇒ đọc CSV trước, không ghi lại.**
  - Compact summary header + §5 gộp G3→G6.
- Còn lại: báo BA (147 dính cả 11 màn; nút gửi đơn mobile trước G5 không gửi được; S00074 là ví dụ rõ của 149) ·
  BA retest 027/028/029 + 142 + 150/151.
- Nợ: top bar PC vỡ ở 992; bảng giá UAT USD; G4 chờ BA; server 8055 + DB `wujia_g5s`, `wujia_g3s` + worktree
  `scratchpad/g5/base_wt` (`git worktree prune`) xoá được.

## End-sprint 64 — chốt sổ cụm G · 01/10/2026 · Mac
- Kết quả: ✅ chỉ docs, 0 dòng code. Chapter 78 `docs/chapters/78-sprint64-cluster-g-issue-list.tex` (Sprint 64: vì sao có
  cụm G · bảng 8 lượt (issue/commit/version) · G1 · G2 · G3a/b · H150/151 · review UAT · G4 ⏸ · G5 · G6 · nghiệp vụ ·
  trade-off · bài học · nợ) + `\include` vào `wujia-tea-doc.tex`; PDF build lại (lualatex, 0 lỗi, ch.78 = trang 319).
- Đầu phiên: chủ dự án nói "làm tiếp G6" — G6 đã xong trọn từ 30/09 (deploy + đo 12/12 + Ready for Retest). Chủ dự án chọn
  đóng sprint cụm G. `issue_queue --dev` = 0; STT cuối sheet 151, 146 vẫn mất; không có Retest Failed.
- Đã làm: chapter 78 · compact summary (header, §4 dòng 64, §5 State) · bảng Tiến độ `next-session-clusters-G.md` dòng chốt sổ.
  7 hash commit trong chapter kiểm bằng `git cat-file -e`.
- Lệch plan / quyết định mới: không.
- Bài học:
  - `build-doc.sh` chạy `-halt-on-error`: lỗi LaTeX ⇒ **PDF cũ bị xoá** (không giữ bản trước). Ký hiệu toán ngoài preamble
    (`\Diamond`) làm hỏng build — dùng chữ thường.
  - Máy không có `pdftoppm`/PyMuPDF: soát trang PDF bằng `gs -sDEVICE=png16m -dFirstPage=… -dLastPage=…`.
  - `git pull` qua SSH github cổng 22 có thể timeout ⇒ ghi HEAD lúc bắt đầu, kiểm lại trước khi push.
- Nợ để lại: như §Nợ chapter 78 (top bar 992 · bảng giá UAT USD · G4 chờ BA · 2 error fixture `wujia_sale` · cột R 6 dòng ·
  dọn server/DB đo · `auto_install` · 7 câu hỏi ADR-027).
- Phiên kế: `issue_queue.py --dev` (BA retest 11 ID có thể trả Retest Failed); nếu trống ⇒ sửa top bar PC 992
  (`wujia_portal_layout`, nhỏ).

## Top bar PC 992–1199 (nợ review cụm G) · 01/10/2026 · Mac
- Kết quả: ✅ code + test + đo local, commit `bea5fa8`. **Chưa push / chưa deploy UAT** — push bị chặn ở phía Claude
  (máy không ra được github cổng 22; SSH 443 chạy được nhưng lệnh push không được phép), chủ dự án push tay.
  Không có issue trên sheet (BA chưa tách) ⇒ không ledger, không `qa_sync`.
- Đầu phiên: `issue_queue --dev` = 0 (16 Ready for Retest, 3 Need Clarification, STT cuối 151).
- Chẩn đoán (đo local 8055 `wujia_g5s`, `anh.owner`): không phải lỗi "đúng 992". Hàng trái 104 + 44 + 452 = 600 + cụm
  phải 406 cần ~1034px; hẹp hơn thì `ul.nav` (Bootstrap `flex-wrap: wrap`) đẩy khối Cửa hàng xuống dòng 2 và `mr-auto`
  của hamburger nhận 423px. UAT `em.hcm` tên ngắn nên chỉ lộ ở 992.
- Đã làm (chỉ `@media (min-width: 992px) and (max-width: 1199.98px)`):
  - `wujia_portal_layout` 19.0.59.3.0 (`_pc_account.css`, `?v=1328`): pill ngôn ngữ `width: auto` (nhãn đã ẩn ở dải
    này, 118 → 55); `navbar-collapse` / `bookmark-wrapper` / `ul` `min-width: 0`, `ul` `nowrap`.
  - `wujia_portal_base` 19.0.7.34.0 (`store_picker.css`): `<li>` chứa khối + khối `min-width: 0` — giữ 430 khi đủ chỗ.
- Số đo: 992–1199 (9 khổ) khối ở hàng 1 (y=12), hamburger mr 0; 16 ca tên cửa hàng/user dài × 4 khổ: 1 hàng, chip
  trong khối, 0 đè, 0 tràn; ép cụm phải +60/+120/+200 ⇒ khối co 405/345/265, cụm phải giữ mép 992. ≥1200 không đổi;
  `wj_shell_g2` PC 27 + mobile 75 trang 0 lỗi. Test 3 (tag `wujia_pc_topbar_992` + 1 trong `wujia_store_switcher_g2`),
  mutation **5/5**, 4 module (`layout`, `base`, `debt`, `exam`) **653/0/0**.
- Lệch / quyết định: bản đầu dùng `width: auto` cho khối ⇒ khối ôm chữ, co còn 273 cả khi đủ chỗ — bỏ. Thiếu
  `min-width: 0` ở `navbar-collapse` thì khối không co mà cụm phải bị đẩy ra ngoài mép (1003 > 978) — thêm.
- Bài học:
  - Lỗi "chỉ ở một mốc" có thể là ngưỡng phụ thuộc dữ liệu (độ dài tên) — đo bằng user tên dài + ép DOM trước khi kết luận.
  - Flex co được phải có `min-width: 0` ở MỌI mắt từ container co tới phần tử co; kiểm bằng ép cụm bên cạnh rộng ra.
  - UAT + github cổng 22 cùng không vào được từ mạng này ⇒ đo trên server local có version = UAT.
- Nợ để lại: deploy UAT (`-u wujia_portal_layout,wujia_portal_base`) + đo lại chỉ-đọc 992/993/1000/1199 với `em.hcm`;
  FYI BA: pill ngôn ngữ 992–1199 chỉ còn cờ (đã vậy từ trước về chữ, nay cả bề rộng).
- Phiên kế: sau deploy đo UAT; `issue_queue.py --dev`.

## Review chuẩn component + lập cụm I/H · 02/10/2026 · Mac
- Kết quả: ✅ chỉ tài liệu, **0 dòng `custom/`**, 0 ghi sheet, chưa commit. 3 đầu ra:
  - `docs/portal-component-standard.{tex,pdf}` (20 trang): chuẩn component dùng chung + 1 trang "chưa có chuẩn" —
    gửi nhóm dev khác tự chỉnh màn của họ; không tên người, không nhắc module của nhóm đó.
  - `docs/ba-component-spec-proposal.{xlsx,tex,pdf}` (27 trang) sinh từ `scripts/qa/ba_spec_proposal.py`: 7 dòng đúng
    17 cột khối spec tab UI Component, Status `Dev Proposed` — ES · DS(+KeyValue) · IB · KPI · TAG · MD (mới) · FF (mới),
    19 câu hỏi CẦN BA CHỐT kèm phương án Dev.
  - `docs/next-session-clusters-H.md`: cụm **I** (I0–I5 + ★IR, issue 152–155 + 62) rồi cụm **H** (H0–H10 + ★HR-1/2), bảng
    trạng thái + prompt từng phiên.
- Đầu phiên: `issue_queue --dev` = 5 Ready for Dev (152, 153, 154, 155 mới; 62 BA đổi yêu cầu 01/10, Owner sheet lệch).
  Chủ dự án hỏi review chuẩn component; chốt **Issue trước, H sau** · Dev soạn spec, BA duyệt · PDF = chuẩn + 1 trang chưa chuẩn.
- Số đo (tĩnh template + Playwright local 8055 `anh.owner`, 1440 + 390, 23 route): lõi đủ (PageHeader 63 · SurfaceCard 94 ·
  CardHeader 93 · DataList 36 · Pagination 23 · FilterBar 19 · StatusBadge 76 class); hở: EmptyState 7 họ/198 · nhãn–giá trị
  8 họ/170 · Bootstrap `alert` 50 + 10 họ/53 · StatCard 7 họ · `wujia-badge` 38 · Modal 4 JS riêng + 3 `confirm()` trình duyệt ·
  FormField 6 họ, chữ trong ô mobile 12.25px.
- Lệch / quyết định: không tách thêm module (`wujia_ui_core` chưa cần theo ADR-027). Gốc 152 = `get_active_franchise_ids_filter`
  (`portal_base/controllers/portal.py:78`), 153 = `get_max_role_in_franchises` (`:89`) — module Khảo sát gọi cùng helper ⇒ fork
  phải hỏi ở I4a/I5.
- Bài học:
  - LuaTeX bỏ qua `{}` khi ghép ligature: `-{}-` vẫn ra gạch ngang; token CSS `--x` phải viết `-\kern0pt-`.
  - Đo cùng lúc thấy PC `/portal/order` báo "Chưa có cấu hình thời gian đặt hàng" còn mobile báo "Đang trong khung giờ"
    (hai phiên đăng nhập riêng) — ghi vào prompt I3 để tái hiện, chưa kết luận.
- Nợ để lại: gửi PDF chuẩn cho nhóm dev khác + gửi bản đề xuất cho BA (chủ dự án) · I0 push `bea5fa8` + deploy top bar ·
  nợ cũ giữ nguyên (bảng giá UAT USD · G4 chờ BA · `auto_install` · 7 câu hỏi ADR-027).
- Phiên kế: **I1** (#155 WJ-ORD-031) theo `docs/next-session-clusters-H.md` §3, sau I0.

## Lập cụm J + J-B1 Branding trong `wujia_core` · 04/10/2026 · Mac
- Kết quả: ✅ plan cụm J (`docs/next-session-clusters-J.md`) + J-B1 code + test, **chưa commit/push/deploy**, 0 ghi sheet.
- Đầu phiên: `git pull` (merge `b5ce925`: module dashboard AI + `wujia_fields_value` của Thái, không đụng vùng cụm J).
  `issue_queue --dev` = **15 Ready for Dev** (5 cụm I + 10 mới 156, 157, 159, 160, 162–167; reconcile 0 commit; WJ-EXAM-001 /
  WJ-NOTI-001 là ID BA dùng lại). Chủ dự án giao 3 việc mới và chốt **làm trước Issue List**: (1) branding cấu hình được trong
  Settings để dùng source cho thương hiệu khác; (2) tool dịch portal ở backend (bản đầy đủ) thay up `.po`; (3) portal Vận hành
  nhượng quyền trên backend `wujia_franchise_operations` hiện có (chấm công/nghỉ phép chờ BA).
- Đã làm (J-B1): `wujia_core` 19.0.2.0.0 — 5 field brand trên `res.company` + tab Settings "Thương hiệu" + `_wj_brand_info()`
  (ormcache) + `_wj_brand_url()` + route ảnh `/wj/brand/<cid>/<kind>` (public, width cố định, `?v=` ⇒ immutable) + bộ token màu
  `tools/brand_palette.py` (mặc định = đúng bộ BA, `css` rỗng; màu khác sinh HSL, CTA ≥4.5:1). 17 dòng VN vào glossary,
  `vi_VN.po` + `wujia_core.pot` mới.
- Số đo: DB trắng `wujia_b1t` 10 test 0 failed; mutation 5/5 đỏ đúng (1 đột biến tương đương bị loại, thay bằng đột biến thật);
  DB copy `wujia_b1` (`wujia_g5s`) `-u wujia_core` rc=0, 0 ERROR; vi_VN đọc lại nhãn Settings + lỗi Python đúng; ảnh Settings OK.
- Lệch / quyết định: logo PC dùng lại `res.company.logo` (không field trùng); không dùng `res.company.primary_color` sẵn có (là màu
  báo cáo PDF, wizard Document Layout tự đổi theo logo) ⇒ field riêng `wj_primary_color`. Công ty không có logo ⇒ route 404, B2 xử.
- Bài học:
  - `-u wujia_core --test-enable` trên DB đủ module chết vì test `wujia_franchise` của Thái import file đã xoá ⇒ test `wujia_core`
    chạy DB trắng `-i`. `wujia_core` đổi đường log sang `<dir>/<năm>/<tháng>/<ngày>.log`.
  - `sync_translations.py` ghi đè bản dịch cũ bằng glossary (vd `Active` → "Kích hoạt (Active)") ⇒ so babel trước/sau, trả lại.
  - Playwright backend Odoo 19: `wait_for_load_state('networkidle')` treo (bus longpoll) ⇒ dùng `wait_for_timeout`.
- Nợ để lại: commit J-B1 (chờ lệnh) · xoá DB `wujia_b1`, `wujia_b1t` khi xong cụm · I0 (push `bea5fa8` + deploy top bar) vẫn treo.
- Phiên kế: **J-B2** — áp brand vào portal + backend (prompt ở `docs/next-session-clusters-J.md` §4).

## J-B2 Áp brand vào portal + backend · 04/10/2026 · Mac
- Kết quả: ✅ code + test, commit (chờ deploy), 0 ghi sheet (không có ID Issue List).
- Chủ dự án chốt: thay đủ 25 câu "Ngô Gia" QWeb + 15 chuỗi Python · 2 sắc gần #1895C7/#168FBE gộp về `--wujia-primary-dark` ·
  title backend chỉ thay fallback "Odoo" (giữ tên action) · tên brand mặc định "Ngô Gia" tự điền khi cài/nâng cấp (hiện ở Settings).
- Đã làm:
  - `wujia_core` 19.0.2.1.0: `has_logo` trong `_wj_brand_info`; `_wj_fill_default_brand_name` (data `noupdate` cho `-i` +
    migration 19.0.2.1.0 cho `-u`, không ghi đè tên đã đặt); `_wj_brand_text('…{brand}…')`; `web.layout` priority 99 (sau MuK):
    favicon brand + title fallback; `session_info.wj_brand_name` + `brand_title.js` (tab backend "Odoo" → brand khi chưa có action).
  - `wujia_portal_layout` 19.0.60.0.0 (depends +`wujia_core`): biến QWeb `wj_brand` (`ir.qweb._prepare_environment`, không cần
    request); 2 head dùng `brand_head` (title `… · brand`, author, favicon/apple-touch qua URL) + `brand_style` (CSS màu sau
    `_variables.css`); logo sidebar/navbar/mobile/login/signup = URL `/wj/brand/…` thay base64; nền login theo Settings.
  - CSS: token trùng hex → `var(--wujia-primary|-soft|-dark)`, thêm `--wujia-primary-rgb`; rgba cứng → `rgb(var(--wujia-primary-rgb) / a)`
    ở theme + components + 5 CSS module màn.
  - Câu "Ngô Gia": QWeb mẫu `<t t-set="wj_txt">…{brand}…</t>` + `t-out="wj_txt.replace('{brand}', wj_brand['name'])"` (giữ 1 term dịch,
    tên được escape); Python qua `env.company._wj_brand_text()` (sale `ERROR_MESSAGES`, exam, purchase_history, `wujia_return`).
  - Bump: portal_base 7.35 · debt 4.17 · sale 4.28 · exam 6.2 · portal_return 4.1 · support 4.1 · delivery 3.22 · notification 3.1 ·
    purchase_history 3.22 · wujia_return 1.1.
- Số đo (cấu hình mặc định, HEAD vs mới, DB copy `wujia_g5s`):
  - probe 26 route × 2 khổ: chỉ đổi title (+" · Ngô Gia"), href icon, author (Cloudmedia → Ngô Gia), alt logo; logo cùng cỡ; màu 0 đổi.
  - HTML: `/portal/login` 45 953 → 13 365 byte; tổng 26 trang 4,72 → 3,03 MB (−36%, bỏ base64 logo).
  - `wj_measure` 0 cell mất record; pixel 26 route + login × 1440/992/390: 0 lệch thật (3 cell lệch 1–2 mức màu lặp lại cả khi so HEAD
    với chính nó ⇒ nhiễu caret/carousel).
  - Test DB trắng `-i wujia_core,wujia_portal_layout`: 262 test 0 failed (10 test mới `test_brand` + `test_j2_brand`); mutation 4/4 đỏ đúng.
  - Suite 11 module (layout, base, debt, sale, exam, return ×2, support, delivery, notification, purchase_history) DB trắng cài rồi `-u --test-enable`: 893 test, 1 đỏ = test `portal_base` khoá cứng `rgba(40, 169, 223, 0.04)` ⇒ sửa sang token, chạy lại 0 failed.
  - `check_layers`: 0 vi phạm depend mới, R6 0 (R7 ×2 có sẵn trong `wujia_franchise` của Thái).
- Lệch / LIMIT:
  - Không chạy lại `sync_translations`: câu "Ngô Gia" cũ trong `vi_VN.po` (debt/exam/return) đều `msgstr` rỗng, chưa có `th_TH` ⇒ 0 bản dịch
    mất; term mới (`{brand}`) gom vào J-T.
  - Test trình duyệt (sau khôi phục filestore) 26 route + login × 1440/390 + backend: mặc định 0 request ảnh/CSS lỗi, 0 ảnh vỡ;
    brand "Trà ABC"/#E4572E/logo/logo mobile/favicon/nền login ⇒ 0 chữ "Ngô Gia", title/màu/logo/nền login/favicon backend đổi theo.
    Phát hiện 12 token sắc xanh brand sót (gradient thẻ tổng quan + thanh giỏ mobile, nền ô hành động nhanh, nền ảnh SP mobile,
    sắc nhạt Thi, viền thẻ Thông báo) ⇒ `brand_palette.TINT_TOKENS` + `retint()` (xoay sắc, giữ độ sáng; mặc định trả đúng hex cũ)
    ⇒ đổi theo brand; mặc định chụp lại 0 lệch (chỉ đồng hồ đếm ngược). 404 `app-assets/data/locales/en.json` (JS Vuexy) có từ trước.
  - JS chart Khảo sát `#28A9DF` (`wujia_portal_inspection`, code Thái) chưa theo brand — defer.
- Sự cố: lệnh copy DB trong zsh (`set -- $p` không tách chuỗi ⇒ `$2` rỗng) chạy `rm -rf data/filestore/` ⇒ **mất toàn bộ filestore
  local** `WujiaTea/data/filestore` (DB vẫn còn). Script khôi phục: `scripts/dev/filestore_pack.py` (chạy máy còn filestore, ra 1 .tar
  khử trùng sha1) + `scripts/dev/filestore_restore.py` (Mac: trả file theo `ir_attachment.store_fname`, xoá dòng bundle thiếu để build lại).
- Bài học:
  - zsh KHÔNG tách biến không ngoặc (`$O`, `set -- $p`) ⇒ lệnh nhiều tham số chạy bằng file `#!/bin/bash` + `set -u`, mảng `"${O[@]}"`;
    không bao giờ `rm -rf` đường dẫn ghép biến khi chưa kiểm biến khác rỗng.
  - QWeb: node có `t-*` không dịch được và cắt câu ⇒ dùng mẫu `wj_txt` + `.replace('{brand}', …)`.
  - `<function>` trong `noupdate` chỉ chạy lúc `-i` ⇒ cần migration cho `-u`. Route portal không `website=True` ⇒ không dùng
    `_prepare_frontend_environment`, chèn biến ở `ir.qweb._prepare_environment`.
  - Odoo chỉ liệt kê DB do `db_user` sở hữu ⇒ `createdb` xong `ALTER DATABASE … OWNER TO odoo19`. `createdb -T` không copy filestore.
  - `-i` + `--test-enable` có `wujia_franchise` ⇒ ImportError test Thái ⇒ cài trước rồi `-u <module> --test-enable`.
- Lệnh deploy: `-u wujia_core,wujia_portal_layout,wujia_portal_base,wujia_portal_debt,wujia_portal_sale,wujia_portal_exam,
  wujia_portal_return,wujia_portal_support,wujia_portal_delivery,wujia_portal_notification,wujia_portal_purchase_history,wujia_return`.
- Nợ để lại: khôi phục filestore local (script trên) · xoá DB nháp `wujia_b1`, `wujia_b1t`, `wujia_b2`, `wujia_b2h`, `wujia_b2t`,
  `wujia_b2u` + worktree `scratchpad/b2/head` · server cũ giữ slot Postgres (g1, g3s, g5s:8055, e4b1…) — user tự dừng · I0 vẫn treo.
- Phiên kế: **J-T1** — `wujia_i18n` danh mục chuỗi + màn sửa + quét.

## J-T1+T2 Tool dịch `wujia_i18n` (danh mục + sửa + Áp dụng + bền qua `-u`) · 05/10/2026 · Mac
- Kết quả: ✅ code + test, **chưa commit/push/deploy**, 0 ghi sheet (không có ID Issue List).
- Đầu phiên: `git pull` (up to date). `issue_queue --dev` = 15 Ready for Dev (không đổi, chờ sau cụm J).
  Chủ dự án chốt **gộp cụm J còn 7 phiên**: T1+T2 gộp, **bỏ T3** (chuỗi code đổi ⇒ xuất `.po` + restart), O3+O4 gộp.
- Đã làm: module mới `wujia_i18n` 19.0.1.0.0 (L1) — `wujia.i18n.term` + `wujia.i18n.value` + `wujia.i18n.coverage` (SQL view)
  + wizard quét (`TranslationModuleReader`) + nút Áp dụng (`TranslationImporter` force_overwrite + xoá cache đúng loại) + override
  `ir.module.module._update_translations` áp lại bản sửa tay. App menu "Bản dịch", nhóm Người dịch (admin implied).
  67 dòng VN vào glossary; `vi_VN.po` + `wujia_i18n.pot`. `check_layers.LAYER` += `wujia_i18n: CORE`.
- Số đo:
  - DB trắng `wujia_t1t` `-i wujia_i18n --test-enable`: 12 test 0 failed; mutation 7/7 đỏ đúng (1 mutation ban đầu sống —
    bỏ xoá cache `templates` — vì test đọc `arch_db` thẳng ⇒ sửa test đọc qua `get_views`, đỏ đúng).
  - DB copy `wujia_t1` (`wujia_g5s` + `-u` 12 module J-B2 + `-i wujia_i18n`, 0 ERROR): bật vi/zh/th + nạp `.po` ⇒ quét 29 module
    × 3 ngôn ngữ: 4 839 term / 14 517 dòng, **3,1 s** (quét lại 1,8 s; 0 trùng) ⇒ chạy đồng bộ, không cần cron.
  - E2E: sửa 1 chuỗi QWeb portal (`wujia_portal_base.acct_menu_store`) + 1 nhãn field ở zh_CN ⇒ Áp dụng ⇒ process mới đọc thấy;
    chạy thật `-u wujia_portal_base --i18n-overwrite` ⇒ bản sửa vẫn còn.
  - Ảnh 1440: list Bản dịch, form Chuỗi (3 ngôn ngữ cạnh nhau), Độ phủ, wizard Quét — tiếng Việt đủ, 0 lỗi console.
- Phát hiện: **90% câu gốc portal (1 384/1 533) viết cứng tiếng Việt, module portal không có `i18n/`** ⇒ độ phủ portal ≈0% cả
  3 tiếng — đây là gốc chuyện "up .po lâu lâu không ăn" phía portal. vi_VN báo "chưa dịch" nhưng hiển thị đúng ⇒ xử ở T4.
  `wujia_franchise_inspection` (Thái) 856 term chỉ ~10% khớp DB dù `.pot` 1 156 msgid (phần lớn là chuỗi survey đọc `.po` lúc chạy).
- Lệch / LIMIT: chuỗi Python/JS sửa được trong tool nhưng **không áp** (giữ "Chờ áp dụng") tới T4 xuất `.po` + restart.
  Xoá trắng ô bản dịch ⇒ `missing`, không gỡ bản dịch đã áp trong DB (lần quét sau đồng bộ lại).
- Bài học: `res.lang._activate_lang` chỉ bật ngôn ngữ, KHÔNG nạp `.po` ⇒ phải `_update_translations([lang])`.
  Chạy test khi đang có server chụp ảnh cùng `--http-port` ⇒ test không chạy, không báo lỗi rõ ⇒ dừng server trước.
- Lệnh deploy: `-i wujia_i18n` (sau đó vào app Bản dịch → Quét chuỗi). Kèm deploy J-B2 đang treo (lệnh ở mục J-B2).
- Nợ để lại: commit J-T1+T2 (chờ lệnh) · deploy J-B2 + J-T · xoá DB nháp `wujia_t1`, `wujia_t1t` (+ b1/b2 cũ) · I0 treo.
- Bổ sung cuối phiên: quét `scripts/qa/vn_hardcode_scan.py` (mới) ⇒ **2 659 chuỗi tiếng Việt viết cứng** (team ≈ 2 375, Thái 284;
  + 945 trong test; bỏ `vendors/` lịch 1 700 chuỗi locale) ⇒ `docs/vn-hardcode-inventory.{md,csv}`. Chủ dự án: "ưu tiên xử lý
  trước" ⇒ lập **Phần V** (V0–V8 + ★VR) trong `next-session-clusters-J.md` §6, làm trước J-T4. Gom mọi tồn đọng vào
  **`docs/pending-backlog.md`** (thứ tự lô · chờ lệnh · chờ BA · nợ kỹ thuật · dọn local). UAT đọc-only: ngôn ngữ bật en/th/vi
  (chưa zh_CN); user portal 6 vi_VN + 1 en_US. `lang.js` portal là code chết template đầu tư, vẫn nạp. `bea5fa8` đã ở origin.
- Phiên kế: **J-V0** — chốt 4 câu (JS portal dịch bằng gì · user en_US · bật zh_CN · BA duyệt câu EN) + công cụ cặp EN↔VN + probe
  text vi_VN; rồi V1 `wujia_portal_layout`.

## J-V0 Chốt quy ước Việt hoá source + công cụ · 05/10/2026 · Mac
- Kết quả: ✅ code + test, **chưa commit/deploy** (theo lệnh: chỉ commit + push phần đã làm trước), 0 ghi sheet (không có ID Issue List).
- Đầu phiên: `git pull` (kéo 8 file mobile của Thái). `issue_queue --dev` = 15 Ready for Dev (không đổi). **Commit + push J-T1+T2
  `ba08698e`** (chỉ `wujia_i18n` + docs/scripts của phiên; không commit `UI/`, `figma/`, `docs/mockups/`, `wj_measure.json`, `.bak`).
- Chủ dự án chốt 4 câu V0: (a) JS portal qua `data-wj-msg-*` · (b) EN thấy EN, VN thấy VN, mặc định vi_VN · (c) bật hết vi/en/th/zh,
  thêm sau tự hiện cho mọi người chọn · (d) BA không duyệt EN; ZH/TH dịch DeepL; câu cần sửa gửi BA 1 lần ở ★VR.
- Đã làm:
  - `wujia_i18n` 19.0.1.1.0: `res.lang._wj_enable_languages()` (bật vi/en/th/zh + `_update_translations` từng ngôn ngữ), gọi từ
    data `noupdate` lúc `-i` + migration 19.0.1.1.0 cho DB đã cài; 3 test.
  - `wujia_portal_layout` 19.0.60.1.0: `ir.http._pre_dispatch` ⇒ khách chưa đăng nhập trên `/portal*` dùng vi_VN thay vì ngôn ngữ
    trình duyệt (Odoo lấy Accept-Language cho phiên mới ⇒ sau Phần V trình duyệt tiếng Anh sẽ ra login tiếng Anh); khách đã chọn ở
    bộ chọn (`PRE_LOGIN_LANG`) và user đã đăng nhập giữ lựa chọn của mình; `/web/login` backend không đụng. 3 test.
  - Quy ước JS: Odoo 19 chỉ dịch attr trong `TRANSLATED_ATTRS` (`data-*` tuỳ ý không dịch) ⇒ câu đặt trong `<t t-set>` rồi
    `t-att-data-wj-msg-*`; helper `wjMsg()` + khối `#wj-msgs` làm ở V1. Ghi `next-session-clusters-J.md` §6.
  - Công cụ: `vn_hardcode_scan.py --module/--fail-on-any` · `vn_to_en_pairs.py draft|check|apply` (mới) · `wj_text_probe.py` (mới,
    nâng từ `b2_probe.py`) · quy trình 1 phiên V trong `scripts/qa/README.md`. `sync_translations.py` đã tự tạo `i18n/` ⇒ không sửa.
  - Chuẩn bị V1: `docs/i18n-pairs/wujia_portal_layout.csv` (259 dòng, auto 205 · sửa tay 54, 4 EN lấy sẵn từ glossary).
- Số đo:
  - DB trắng `wujia_v0t` `-i wujia_i18n,wujia_portal_layout`: test `/wujia_i18n` + 3 lớp lang `portal_layout` **26/0**; mutation
    tắt luật khách ⇒ đỏ đúng `test_english_browser_gets_vietnamese_login`.
  - DB copy `wujia_t1` `-u wujia_i18n,wujia_portal_layout`: RC 0, 0 ERROR; khách `Accept-Language: en-US` ⇒ `/portal/login`
    `lang="vi-VN"`, `/web/login` không đổi; bộ chọn 4 ngôn ngữ.
  - `apply` thử trên bản copy `wujia_portal_layout` (EN giả): thay **204/205**, XML/Python hợp lệ 100%, quét lại còn đúng nhóm sửa tay
    (JS 30 · `t-*` 17 · hằng Python 4 · attr không dịch 3 · 1 `_()` nối nhiều literal). Bắt được bẫy: lxml báo dòng CUỐI của thẻ mở ⇒
    attr phải tìm ngược lên.
  - `wj_text_probe` 52 trang × 2 lần: 0/52 lệch ⇒ mốc `docs/i18n-baseline/vi_VN.json` (DB `wujia_t1`, user `anh.owner`; không có
    chi tiết giao hàng/hỗ trợ/yêu cầu thông tin trong dữ liệu).
- Lệch / LIMIT: mốc chữ gắn với dữ liệu `wujia_t1` ⇒ V1…V8 đo trên cùng DB. Trang chi tiết thiếu 3 loại (dữ liệu).
- Bài học: Odoo lấy ngôn ngữ phiên khách từ Accept-Language, không từ `base.public_user.lang`. HttpCase không pin `--db-filter`
  ⇒ request rơi vào DB mặc định (`wujia_tea_19`) ⇒ đỏ giả. Câu log cũng bị quét ⇒ log viết tiếng Anh.
- Lệnh deploy (gộp với J-B2/J-T đang chờ): `-i wujia_i18n` (tự bật zh_CN) + `-u` J-B2 (đã gồm `wujia_portal_layout`).
- Nợ để lại: commit J-V0 (chờ lệnh) · deploy J-B2 + J-T + J-V0 · xoá DB nháp `wujia_v0t` (+ `wujia_t1t`, b1/b2 cũ) · I0 treo.
- Phiên kế: **J-V1** — `wujia_portal_layout`: điền EN cho `docs/i18n-pairs/wujia_portal_layout.csv` → check → apply → sửa tay
  (helper `wjMsg` + `#wj-msgs`, xoá `lang.js`) → `.po` → probe 0 lệch.

## J-V1 Việt hoá source `wujia_portal_layout` + helper `wjMsg` · 05/10/2026 · Mac
- Kết quả: ✅ code + test, **chưa commit/push/deploy**, 0 ghi sheet (không có ID Issue List).
- Đầu phiên: `git pull` (up to date; J-V0 `d2966119` đã ở origin). `issue_queue --dev` = 15 Ready for Dev (không đổi, chờ sau cụm J).
- Đã làm (`wujia_portal_layout` 19.0.60.2.0):
  - Câu gốc → tiếng Anh: `vn_to_en_pairs.py apply` thay 204/205 dòng tự động (`docs/i18n-pairs/wujia_portal_layout.csv` điền đủ EN,
    `check` 0 lỗi — 3 EN đổi vì đụng glossary: "Hoàn tất"=Finished, "Đang xử lý"=Processing, "Đang hoạt động"=Enabled); sửa tay 54:
    `_ROLE_LABELS` → `_lt()` · `_()` nối literal gộp 1 · nhãn mặc định component (`Xem tất cả`, `Tạo mới`, filter bar `Tìm kiếm/Tất cả/
    Xóa lọc/Từ/Đến/Từ ngày/Đến ngày`) → `<t t-set>` dịch được · gallery `pc_preview` · tên kỹ thuật template sang EN.
  - Form đổi mật khẩu: viền đỏ ô lỗi theo `error_field` (`old`/`new`/`confirm`) controller trả, bỏ dò chữ trong câu lỗi (dịch xong là chết).
  - JS: helper mới `static/assets/js/wj_msg.js` (`wjMsg(el, key, fallbackEN)`) nạp ở `asset_frontend_js` + khối chung
    `wujia_portal_layout.wj_msgs` (`#wj-msgs`: unsaved-changes/show/hide) ở cả layout app và layout đăng nhập; `wj_back_guard.js`,
    `wujia_password_toggle.js` dùng helper. Xoá JS chết: `lang.js` + khối ví/đầu tư `my_js.js` (route `/bcore/*` không tồn tại),
    `overview_member.js`, `extensions/i18n.js`. `vn_hardcode_scan.py` bỏ qua `pick-a-datetime.js` (lib, chữ Pháp).
  - Tiếng Việt không dấu máy quét sót (`Trang sau`, `/ trang`, `Trang x / y`, `Xem`) → EN, bắt bằng danh sách msgid chưa dịch của `.po`.
  - Chuỗi tiếng Anh có sẵn mà user VN vẫn thấy: `Wrong login/password` (lỗi đăng nhập sai), nhãn `Login`/badge `Active` profile mobile,
    alt `avatar`, aria `Breadcrumb`/`Language` ⇒ nay ra tiếng Việt.
  - `i18n/vi_VN.po` + `.pot` mới (218 msgid, 185 dịch); glossary +171 dòng; test helper `tests/common.py::load_vi`.
- Số đo:
  - `vn_hardcode_scan --module wujia_portal_layout --fail-on-any` = **0** (trước 259).
  - DB trắng `wujia_v1t`: suite `/wujia_portal_layout` **257/0** (250 cũ — 18 đỏ do assert nhãn VN ⇒ chạy `lang=vi_VN`, không xoá assert —
    + 7 test mới `test_jv1_i18n`). Mutation: trả dò chữ cũ + gỡ `#wj-msgs` ⇒ đỏ đúng 3/3.
  - DB copy `wujia_v1b` (từ `wujia_t1`): suite `/wujia_portal_base` **316/0**.
  - `wj_text_probe` vi_VN 52 trang so mốc V0: chữ hiển thị lệch **chỉ 2 trang** (profile 1440/390: `Active`→`Đang hoạt động`,
    `Login`→`Tên đăng nhập` — chủ ý); attr: alt/aria sang tiếng Việt + 3 `data-wj-msg-*`. Đo lại 2 lần 0/52 ⇒ **mốc mới**
    `docs/i18n-baseline/vi_VN.json` cho V2.
  - Ảnh en_US/th_TH 1440 + 390 (login, home, profile, đổi mật khẩu, lịch sử, công nợ, menu avatar): 0 tràn ngang, không vỡ bố cục;
    nút Show/Hide + câu rời trang đúng ngôn ngữ (vi: Hiện/Ẩn). Console chỉ còn 404 `app-assets/data/locales/en.json` (có từ trước).
  - App "Bản dịch" độ phủ vi_VN `wujia_portal_layout` **85,5%** (213/249); 36 còn lại không tới user: gallery dev, metadata
    `ir.model`, mã đơn mẫu, 2 template cũ không route nào render.
- Lệch / LIMIT: plan đặt `wj_msg.js` trong bundle `web.assets_frontend` ⇒ đổi sang `asset_frontend_js` vì layout đăng nhập không nạp
  bundle. th_TH/zh_CN của khung chưa có bản dịch (thấy EN) — đúng plan, chờ J-T5 DeepL. Chữ VN còn trên màn (sidebar, chip vai trò
  topbar, "Hồ sơ cửa hàng") thuộc `portal_base` ⇒ V2.
- Bài học: máy quét theo dấu sót chữ không dấu ⇒ luôn xem msgid chưa dịch sau sync · Odoo gom thẻ inline thành 1 term ⇒ glossary
  đúng msgid đó · `sync --import` xong phải restart server mới thấy (cache template) · `_()` module không mượn bản dịch core.
- Lệnh deploy: không thêm — `wujia_portal_layout` đã trong lệnh `-u` J-B2; **restart sau `-u`**.
- Nợ để lại: commit J-V1 (chờ lệnh) · deploy J-B2 + J-T + J-V0 + J-V1 · xoá DB nháp `wujia_v1t`, `wujia_v1b` (giữ `wujia_t1` tới hết
  Phần V) · ★VR: xoá template `signup*`/`forgot_pass_back` chết · I0 treo.
- Phiên kế: **J-V2** — `wujia_portal_base` (382 chuỗi): `draft` → điền EN → `check` → `apply` → sửa tay (`ROLE_LABELS`, nav item, home KPI,
  chip vai trò topbar) → `.po` + liệt kê msgid chưa dịch → test `load_vi` → probe so mốc mới.

## J-V2 Việt hoá source `wujia_portal_base` · 05/10/2026 · Mac
- Kết quả: ✅ code + test, **đã push `main`** (commit `feat(i18n): J-V2 …`), deploy do chủ dự án; 0 ghi sheet (không có ID Issue List).
- Đầu phiên: `git pull` (up to date, HEAD `7b03b680` J-V1). `issue_queue --dev` = 15 Ready for Dev (không đổi, chờ sau cụm J).
- Đã làm (`wujia_portal_base` 19.0.7.36.0):
  - Câu gốc → tiếng Anh: `docs/i18n-pairs/wujia_portal_base.csv` 382 dòng (auto 253 · sửa tay 129), `check` 0 lỗi; glossary +190 dòng.
    EN đổi vì đụng câu đã chốt: "Hoàn tất"=Finished, "Đang xử lý"=Processing, "Đang hoạt động"=Enabled, "· còn"="· time left".
  - **Màu badge trạng thái** (`controllers/utils.py`): `STATUS_VARIANT_BY_LABEL` nay khoá theo câu EN, dựng từ `_lt()` nhóm theo màu.
    `status_badge_for(label)` nhận nhãn lazy (`_source`), EN, hoặc **nhãn VN cũ** (bảng ngược sinh từ `vi_VN.po`, gộp 2 cách viết
    "huỷ/hủy") ⇒ 7 module chưa qua V3–V8 gọi bằng chữ VN vẫn đúng màu. Nhánh VN cũ đánh dấu ★J-VR xoá.
  - Hằng nhãn → `_lt()`: `ROLE_LABELS`, `FRANCHISE_STATUS_LABELS`, `SALE_STATE_META`, `DEFAULT_STATE_META`, `DELIVERY_OVERRIDE_META`,
    `MOBILE_BATCH_BADGES`, `RETURN_STATUS_LABELS`, `VI_WEEKDAYS`, `DEPARTURE_LABEL_*`, `ERR_DATE_RANGE`, `build_pager(item_label)`.
    Hàm theo bản ghi (`portal_order_status/badge`, `return_status_label`, `_portal_role_label`) dịch bằng `record.env` (đúng ngôn
    ngữ user cả khi không có request: cron, test); hàm còn lại `str()` theo request.
  - `t-*`: "Không giới hạn", "Hồ sơ cửa hàng — tên", "Khu vực …", "Cửa hàng tạm khóa", "%s đơn chưa giao" → `<t t-set>` dịch được.
  - JS `franchise_realtime.js`: nhãn vai trò lấy `role_label` server trả (đã dịch), "Chủ chính" qua `data-wj-msg-main-owner` + `wjMsg`.
  - Chuỗi tiếng Anh có sẵn mà user VN vẫn thấy (`Inactive`, `User`, `Owner / Manager`) ⇒ nay ra tiếng Việt.
  - `i18n/vi_VN.po` + `.pot` mới (251 msgid, 244 dịch). `data/sample_data.xml` (17 chuỗi: tên cửa hàng/người/địa chỉ mẫu, `noupdate`)
    **giữ nguyên** — dữ liệu, không phải chữ giao diện; `vn_hardcode_scan.py` loại trừ file này (`DATA_FILES`).
  - Test: `tests/common.py::load_vi` (nạp `.po` của `portal_layout` + `portal_base`); test mới `test_jv2_i18n` (badge EN/lazy/VN cũ,
    nhãn theo ngôn ngữ, Home user vi vs en). Test module phụ thuộc chỉ sửa file test: `e4c_filter_dates` ×6 so với bản dịch
    `ERR_DATE_RANGE` theo ngôn ngữ user; `delivery_c5`, `purchase_history` (2 file), `return_controller` chạy `lang=vi_VN`.
- Số đo:
  - `vn_hardcode_scan --module wujia_portal_base --fail-on-any` = **0** (trước 382).
  - DB copy `wujia_v2b` (từ `wujia_t1`): suite `/wujia_portal_base` **324/0** (316 cũ + 8 mới). 11 module phụ thuộc (return, debt,
    info_request, exam, sale, support, purchase_history, delivery, layout, notification, report): **311 test, 3 đỏ — có sẵn**
    (`test_f5_legacy_redirect` exam/purchase_history/return 404≠301, đỏ y hệt trên worktree HEAD chưa sửa).
  - Mutation: bỏ nhánh nhãn VN cũ trong `status_badge_for` ⇒ 7 subtest đỏ đúng; đã khôi phục.
  - `wj_text_probe` vi_VN 52 trang so mốc V1: lệch **chỉ 2 trang** (`/portal/return` 1440/390: "Đã huỷ"→"Đã hủy" — chủ ý, thống
    nhất cách viết) ⇒ **mốc mới** `docs/i18n-baseline/vi_VN.json` cho V3.
  - Ảnh en_US/th_TH × 1440/390 (home, danh sách cửa hàng, thông tin nhượng quyền, chi tiết cửa hàng, hồ sơ cửa hàng) + store picker
    (user đa cửa hàng `dung.multi`, cả vi/en/th): **0 tràn ngang**, không vỡ bố cục. Chữ VN còn trên màn: dữ liệu (tên, địa chỉ,
    tiêu đề thông báo) + nav/ô của module V3–V8 (debt, return, support, knowledge, exam, report, inspection của Thái).
  - App "Bản dịch" độ phủ vi_VN `wujia_portal_base` **96,6%** (287/297); 10 còn lại không cần dịch: `ID` metadata ×3, tên khu vực
    mẫu ×5, `Email` ×2 (giống nhau 2 ngôn ngữ).
- Lệch / LIMIT:
  - EN không có số nhiều: "1 orders in 30 days", "0 undelivered orders" (câu `%s` dùng chung mọi số) — gom vào danh sách ★VR.
  - Mobile 390 EN: nhãn KPI "NOTIFICATIONS" bẻ giữa chữ (CSS `portal_layout` `overflow-wrap: anywhere`, BA cấm "…") — không tràn,
    nhưng xấu; chờ chủ dự án chọn: rút câu EN ("Alerts") hay sửa CSS.
  - EN "· time left 02:30": thứ tự chữ buộc theo cách Odoo tách đoạn quanh `t-out`.
  - Đo trên DB copy: copy DB bằng `createdb -T` dưới user Mac ⇒ DB không thuộc `odoo19` ⇒ Odoo không liệt kê (404 `/portal`), và
    filestore phải chép tay (thiếu ⇒ mất logo ⇒ lệch `alt` giả 52/52 trang). Đã sửa bằng `ALTER DATABASE … OWNER TO odoo19` + `rsync`.
- Bài học:
  - Trình trích `.pot` của Odoo lấy **phần tử đầu tuple** làm msgid với `('key', _lt('X'))` ⇒ dùng dict `{'key': _lt('X')}`.
  - `_lt(biến)` không vào `.pot` ⇒ mọi `_lt` phải là literal (bảng màu badge viết thẳng từng `_lt('…')`).
  - Hàm nhận bản ghi ⇒ dịch bằng `record.env._(lazy)`, không `str(lazy)` (không có request thì ra EN).
  - `wujia_core` chuyển log về `<thư mục logfile>/<năm>/<tháng>/<ngày>.log` (giờ UTC) ⇒ đọc kết quả test ở đó, `--logfile` trống.
- Lệnh deploy: thêm `wujia_portal_base` vào lệnh `-u` gộp (J-B2/J-T/J-V0/V1); **restart sau `-u`**.
- UAT (05/10 tối): deploy tự động (`deploy.yml`) **dừng ở `wujia_portal_base`** — core/franchise/layout lên 13:41 UTC, `portal_base` và
  module sau giữ 19.0.7.35.0 (view 12:09); không có log để biết lỗi gì (máy dev chưa đăng nhập `gh`). Nâng lại bằng nút **Upgrade**
  trên trình duyệt (admin, Apps → `wujia_portal_base`) ⇒ **thành công**, 19.0.7.36.0, view ghi 14:01 UTC (+ debt, exam). Kiểm chỉ-đọc:
  en_US 0/18 view còn chữ VN, vi_VN y cũ, th_TH ra EN; admin vi_VN 5 route × 1440/390 = 200, 0 lỗi JS, 0 tràn, badge đúng màu.
  ⚠️ Lần deploy kế mà `-u` CLI lại lỗi ⇒ cần log bước "Install / Upgrade Wujia modules".
- Nợ để lại: deploy J-B2 + J-T + J-V0 + V1 + V2 (chủ dự án deploy để test) · xoá DB nháp `wujia_v2b/d/h/p` (giữ `wujia_t1` tới hết
  Phần V) · ★VR: xoá nhánh nhãn VN cũ `_legacy_vn_status_labels` + danh sách câu EN số nhiều · 3 test `f5_legacy_redirect` đỏ sẵn · I0 treo.
- Phiên kế: **J-V3** — `wujia_portal_exam` (345) + `wujia_exam` (63): `draft` → điền EN → `check` → `apply` → sửa tay → `.po` →
  `load_vi` → probe so mốc V2. Nhãn trạng thái gọi `status_badge_for` ⇒ chuyển sang `_lt()` EN (nhánh VN cũ không cần nữa cho exam).

## J-V3 Việt hoá source `wujia_portal_exam` + `wujia_exam` · 06/10/2026 · Mac
- Kết quả: ✅ code + test, **đã push `main` `baa5b547`**, chủ dự án đã deploy UAT; 0 ghi sheet (không có ID Issue List).
- Đầu phiên: HEAD `7e1d5abf` (J-V2). Không đụng `wujia_mobile_portal_exam` (Thái) — đã soi: không xpath/assert theo chữ VN.
- Đã làm (`wujia_exam` 19.0.1.1.0 · `wujia_portal_exam` 19.0.7.0.0; `portal_base` không đổi — mọi nhãn EN đã có trong bảng màu):
  - Câu gốc → tiếng Anh: `docs/i18n-pairs/wujia_exam.csv` 63 dòng (auto 55 · tay 8), `wujia_portal_exam.csv` 345 (auto 213 · tay 132);
    glossary +290 dòng (chỉ thêm, giữ CRLF). "Họ và tên" người dự thi = "Participant's full name" (tránh đụng "Full name"="Họ tên").
  - `wujia_exam`: 49 `_()` + 3 `models.Constraint` + lỗi `register_from_portal` (`ExamPortalError` giữ `kind`) → EN; 6 `title=`/`sum=`
    view backend + manifest → EN. Backend tooltip "Đã công bố KQ" → **"Đã công bố kết quả"** (chủ ý, đủ chữ).
  - `controllers/portal.py`: `_WEEKDAYS`, `M_REG_BADGE`, `PC_REG_STATES`, `PC_PUBLISH_STATES`, `SLOT_STATUS_LABELS`, `COURSE_OPEN`,
    `RESULT_AVAILABLE` → `_lt()` (dict, `status_badge_for(lazy)`); câu theo bản ghi (`Month %(month)d %(year)d`, `%d seats left`,
    `%d participants/passed/failed`, banner `{brand}`) → `record.env._()`; `_publish_label` để không lọt msgid rác vào `.pot`.
  - QWeb: `'Đăng ký mới'`, FilterBar, `'Chưa có'`, lý do từ chối/huỷ, Đạt/Không đạt → `<t t-set>`/`t-if`; tiêu đề thứ T2…CN → Mo…Su.
  - JS `portal_exam_pc.js` + `portal_exam_wizard.js`: 45 câu → khối `_ex_msgs` (`<t t-set>` dịch được, gắn `t-att` dict lên root PC +
    wizard mobile) + helper `m(key, 'EN', arg)` qua `wjMsg`; câu ghép số → 1 câu `%s`. Biến tháng `var m` (che helper `m` trong handler
    click) đổi thành `mo`.
  - `.po` + `.pot` mới: `wujia_portal_exam` 241 msgid / 239 dịch (2 còn lại không cần: chip `i`, tên file mẫu); `wujia_exam` 215 / 176
    (trước 216 / 117; 39 còn lại = trường mixin mail + tên model, **trước J-V3 cũng chưa dịch** — không lùi). 9 msgstr cũ của
    `wujia_exam` bị glossary chung ghi đè ⇒ khôi phục bằng sửa text.
  - Test: `wujia_exam/tests/common.py::load_vi(env, modules)`; `ExamCommon` chạy vi_VN (+ user portal `lang='vi_VN'`, `_vi_modules`
    để test portal nạp `.po` khung + base + 2 module Thi); `c10_quota` vi_VN; `f5_nav_item`/`list_card_e5b2` so EN ở nguồn + tiếng
    Việt ở arch vi_VN; `f12.test_max_hint` so EN + bản dịch. Mới: `test_portal_rules.test_error_follows_user_lang` (en/vi, cả lỗi
    constraint) + `test_jv3_i18n` (badge đối chiếu nhãn VN TRƯỚC J-V3: cùng chữ + cùng màu; nhãn ca/thứ theo ngôn ngữ; mọi key
    `m("…")` của JS có `data-wj-msg-*` ở `_ex_msgs`, gắn đủ 2 root). Không xoá assert nào.
- Số đo:
  - `vn_hardcode_scan --fail-on-any`: `wujia_exam` **0** (trước 63) · `wujia_portal_exam` **0** (trước 345).
  - DB copy `wujia_v3b`: suite `/wujia_exam,/wujia_portal_exam` **53/0** (5 đỏ lần đầu đều do assert chữ VN ⇒ sửa như trên;
    3 `f5_legacy_redirect` đỏ sẵn ở V2 nay xanh trên DB này). DB trắng `wujia_v3blank` (cài rồi `-u --test-enable`): `/wujia_exam` **14/0**.
    Mobile Thái `wujia_mobile_portal_exam` cài trên bản copy `wujia_v3m`: **3/3**.
  - Mutation 3/3 đỏ đúng: đổi nhãn badge `Rejected`→`Declined` (2 subtest), bỏ 1 key `_ex_msgs`, bỏ `load_vi` ở `c10_quota`; đã khôi phục.
  - `wj_text_probe` vi_VN 52 trang so mốc V2: chữ hiển thị **0 lệch**; chỉ thêm 45 dòng `@data-wj-msg-*` (câu JS, toàn tiếng Việt) ở
    `/portal/exam/register` 1440/390 ⇒ **mốc mới** `docs/i18n-baseline/vi_VN.json` cho V4.
  - Playwright en_US/th_TH × 1440/390: danh sách, 3 chi tiết phiếu (chờ duyệt/đã đăng ký/từ chối), đăng ký (PC: kiểm tra khi chưa
    chọn ca, chọn ngày → khung giờ, modal Thêm người + lưu rỗng; mobile: chọn khoá → lịch → sheet khung giờ): **0 tràn ngang, 0 lỗi
    JS**, câu JS ra EN (th_TH chưa có `.po` ⇒ EN). Chữ VN còn: dữ liệu (tên khoá/cửa hàng/người, brand "Ngô Gia") + nav module V4–V8.
    DB đo có thêm 1 ca thi mở (id 308, "JV3 QA room") để thấy khung giờ.
- Lệch / LIMIT:
  - Nợ cũ còn nguyên: tiêu đề khung giờ PC "Time slots on —" (trước là "Khung giờ ngày —", `chosen.dateLabel` không được điền) ⇒ ★VR.
  - EN số nhiều: "1 sessions • In the next 60 days" ⇒ gom vào danh sách ★VR.
- Bài học: ghi ở `next-session-clusters-J.md` §6 "J-V3".
- Lệnh deploy: thêm `wujia_exam,wujia_portal_exam` vào lệnh `-u` gộp; **restart sau `-u`**.
- UAT (06/10): deploy tự động lại **dừng trước tầng `portal_*`** (L2 + mobile Thái lên 07:39–07:40 UTC, `wujia_portal_exam` kẹt
  19.0.6.2.0 ⇒ view cũ, thiếu khối `_ex_msgs` ⇒ câu JS sẽ ra EN cho user VN). Được chủ dự án đồng ý ⇒ Upgrade `wujia_portal_exam`
  (nút Upgrade, admin) ⇒ 19.0.7.0.0, 5 s. Kiểm chỉ-đọc `anh.owner` vi/en/th × 1440/390 (`/portal/exam`, `/portal/exam/register`, PC:
  kiểm tra khi chưa chọn ca + modal Thêm người + lưu rỗng): **0 tràn, 0 lỗi JS**, vi y cũ, en/th ra EN; chữ VN còn = dữ liệu + nav
  V4–V8. Ngôn ngữ user trả về vi_VN. LIMIT: UAT không có phiếu ở HN-01 và không có ca mở ⇒ chưa xem được chi tiết phiếu / khung
  giờ (đã xem trên DB đo local). Lần đầu đổi ngôn ngữ qua `/portal/set-lang` có lượt chưa ăn (`<html lang>` vẫn vi) ⇒ script đo phải
  xác nhận `document.documentElement.lang` trước khi chụp. ⚠️ Deploy kế cần log bước "Install / Upgrade Wujia modules" (2 lần liền dừng).
- Nợ để lại: xoá DB nháp `wujia_v3b` (giữ `wujia_t1` tới hết Phần V) · ★VR như trên + danh sách J-V2.
- Phiên kế: **J-V4** — `wujia_portal_sale` (201) + `wujia_sale` (16) + `wujia_order_window` (8), so mốc vi_VN sau V3.

## J-V4 Việt hoá source `wujia_portal_sale` + `wujia_sale` + `wujia_order_window` · 06/10/2026 · Mac
- Kết quả: ✅ code + test, **đã push `main` `359fe36c`**, chủ dự án deploy; 0 ghi sheet (không có ID Issue List).
- Đầu phiên: HEAD `baa5b547` (J-V3). Không module Thái nào phụ thuộc 3 module này (`wujia_mobile_sale` đã standalone) ⇒ không đụng code Thái.
- Đã làm (`wujia_portal_sale` 19.0.5.0.0 · `wujia_sale` 19.0.4.7.0 · `wujia_order_window` 19.0.1.1.0):
  - Câu gốc → tiếng Anh: `docs/i18n-pairs/wujia_portal_sale.csv` 201 dòng (auto 118 · tay 83), `wujia_sale.csv` 16 (12 · 4),
    `wujia_order_window.csv` 8 (4 · 4); glossary +147 dòng (chỉ thêm, giữ CRLF, 0 dòng cũ đổi).
  - `controllers/portal.py`: `ERROR_MESSAGES`, `QTY_MESSAGES`, `SUCCESS_MESSAGES`, `LINE_INVALID_MESSAGES` → dict `_lt('EN')`; tra bảng qua
    helper `_qty_message` / `_line_invalid_message` / `_success_message` (gán biến rồi mới `env._`, tránh msgid rác `QTY_ABOVE_MAX`);
    `_error_message` dịch theo request rồi mới `_wj_brand_text` (`{brand}`). Câu ghép → 1 câu `_()` có placeholder: "The quantity of %s must
    be a whole number.", khung qua đêm "%(start)s today – %(end)s tomorrow (%(tz)s)", "Today, %s" / "On %s"; `build_pager(item_label=
    _lt('products'))`; fallback ký hiệu tiền `'đ'` → `'₫'`. `wujia_portal_cart.py`: constraint + display name "Cart [%(code)s] %(name)s".
  - JS `portal_order.js` (11) + `portal_cart_sync.js` (4): template mới `wujia_portal_sale.cart_sync_root` — 13 câu `<t t-set>` + dict `t-att`
    lên `#wj-cart-sync`, gọi ở catalog + giỏ + chi tiết SP (thay div trần cũ); JS đọc qua `wjMsg` (`m(key,'EN',arg)` / `this.msg(key,'EN')`).
  - QWeb: aria-label nút mobile (`Add %s to cart`…), FilterBar (ô tìm/danh mục), trang kết quả (`Order placed`, câu `{brand}`, ngoài khung
    giờ) → `<t t-set>`; chữ không dấu máy quét sót: `SL` → `Qty`, `SP` → `SKUs`, `. Khung:` → `. Window:` (+ glossary).
  - `wujia_sale` 12 `_()` + `wujia_order_window` 2 `_()` + 2 `ValidationError` → EN; manifest, log migration, `name=` template → EN.
  - `.po` + `.pot`: `wujia_portal_sale` **mới** 163 msgid / 158 dịch (5 còn lại backend: chip `!`, Franchise, ID, 2 tên model);
    `wujia_sale` 138 / 118 (HEAD 149 / 119: 18 msgid mồ côi không còn trong source bị bỏ); `wujia_order_window` 45 / 34 (HEAD 45 / 24).
    Các msgid còn trống đều là chuỗi backend **vốn EN từ HEAD** (tên model, help field, mixin) — không lùi. msgstr `Active` bị glossary ghi đè
    và help `franchise_id` (msgid HEAD chỉ là câu đầu) ⇒ khôi phục bằng sửa text.
  - Test: `wujia_sale/tests/common.py::load_vi(env, modules)`; `test_order_window` (EN dưới en_US + VN dưới vi_VN), `f5_nav_item`,
    `f6_cart_submit` (env + user vi_VN), `portal_base/test_scan_c8_section_header` (nhãn pager "products"/"sản phẩm" theo env).
    Mới `test_jv4_i18n`: bảng câu VN TRƯỚC V4 so `env_vi._(lazy)` + placeholder, câu ghép, constraint vi/en, mọi key JS có `data-wj-msg-*`
    trong `cart_sync_root` + 3 trang gọi nó; HttpCase user `vi_VN`/`en_US` nhận lỗi giỏ đúng ngôn ngữ. Không xoá assert nào.
- Số đo:
  - `vn_hardcode_scan --fail-on-any`: 3 module **0** (trước 225).
  - DB copy `wujia_v4b`, `-u` 9 module (sale, order_window, portal_sale + account, delivery, return, portal_base, portal_report,
    purchase_history) `--test-enable`: **502 test, 0 đỏ mới**; 2 lỗi có sẵn ở HEAD (đo song song worktree HEAD + DB `wujia_v4h`: 497 / 0 / 2):
    `wujia_sale test_06_filters_return_right_orders` (phụ thuộc giờ — chạy sáng UTC ngoài khung đặt hàng) và `TestWujiaSupplyDemandReport`
    setUpClass ("Quants cannot be created for consumables"). 1 đỏ lần đầu (`portal_base` c8 assert "sản phẩm" trong arch sale) ⇒ sửa như trên.
  - Mutation: bỏ key `removed` ⇒ đỏ; đổi câu EN `PRODUCT_NOT_AVAILABLE` không thêm glossary ⇒ đỏ 3 nơi; bỏ `'lang': 'vi_VN'` của user f6 ⇒
    xanh — mutation tương đương (user tạo từ `cls.env` `lang=vi_VN` nên mặc định vẫn vi_VN); bỏ `load_vi` f6 ⇒ xanh (DB đo đã nạp `.po`;
    chốt chặn là `test_jv4_i18n`). Đã khôi phục.
  - `wj_text_probe` vi_VN 52 trang so mốc V3: chữ hiển thị **0 lệch do V4**; thêm 13 dòng `@data-wj-msg-*` (tiếng Việt) × 6 trang
    (catalog/giỏ/chi tiết × 1440/390). `/portal/exam/register` lệch "Đã đóng" ↔ "Còn lịch" do ca thi 308 ("JV3 QA room") có trên DB đo
    ⇒ **mốc mới** `docs/i18n-baseline/vi_VN.json` = probe V4, giữ 2 trang exam/register của mốc V3.
  - So giá trị vi_VN trong DB HEAD (`wujia_v4h`) ↔ mới (`wujia_v4b`) — field/help/selection/model/menu/action/arch view 3 module:
    **0 chỗ VN → EN**; 36 chỗ EN → VN (field backend nay có bản dịch: Ngày tạo, Người cập nhật, Đủ hàng/Thiếu hàng…).
  - Playwright en_US/th_TH × 1440/390 (`<html lang>` xác nhận): catalog, giỏ, chi tiết SP, ngoài khung giờ, đã gửi đơn (S00012), modal
    xác nhận: **0 tràn ngang, 0 lỗi JS mới**; câu JS ra EN ("Please enter a valid quantity.", "The minimum/maximum quantity is %s.",
    "Quantity in cart: %s. View cart →", "Added to cart (1)", confirm "Remove this product from the cart?"); vi_VN cùng luồng ra y chữ cũ.
    Chữ VN còn: dữ liệu (tên SP/danh mục/quy cách/cửa hàng/người, brand "Ngô Gia") + nav module V5–V8.
- Fix nốt (cùng phiên, chủ dự án "cái nào fix được fix nốt"):
  - **404 locale Vuexy** `/<lang>/app-assets/data/locales/en.json` trên mọi trang portal (có từ trước): `core/app.js` gọi `i18next.init` ngay
    lúc nạp nên stub trong `my_js.js` (nạp sau) không chặn được ⇒ bỏ `i18next.init` + `changeLanguage` trong `core/app.js`, xoá stub chết;
    `?v=` cho 2 file; `wujia_portal_layout` 19.0.60.3.0. Đo th_TH × 1440/390: **0 request ≥400, 0 lỗi JS**, bấm dropdown ngôn ngữ ⇒ vi-VN.
  - **Nợ dịch backend**: 35 msgid vốn EN chưa có bản vi (`wujia_sale` 20, `wujia_order_window` 11, `wujia_portal_sale` 4) ⇒ dịch, thuật ngữ
    theo Odoo core (`Đơn bán hàng`, `Biến thể sản phẩm`, `Lệnh chuyển hàng`…); help `franchise_id` dịch đủ 2 câu. Độ phủ vi_VN:
    `wujia_sale` **138/138**, `wujia_order_window` **45/45**, `wujia_portal_sale` **162/163** (còn chip `!`). Glossary +32 (chỉ thêm).
  - Help khung giờ có chữ không dấu "Vd" ⇒ source "E.g."; lỗi tạo đơn portal ngoài khung giờ in giờ `10.00 – 4.00` ⇒ `10:00 – 04:00`
    (`_hhmm`, msgid `%(f)s – %(t)s`, test thêm `assertRegex` giờ:phút).
  - **2 lỗi test có sẵn của `wujia_sale`**: `test_06_filters_return_right_orders` tắt giới hạn khung giờ trong `setUpClass` (test lọc, không
    phụ thuộc giờ chạy); `TestWujiaSupplyDemandReport` (code anh Thái `c64de509`, chưa từng chạy qua setUpClass): sản phẩm test thêm
    `is_storable` (Odoo 19), `flush_all()` trước khi đọc SQL view, sửa xmlid menu `menu_wujia_sale_supply_demand_report`.
  - Suite 10 module (thêm `wujia_portal_layout`) `-u --test-enable`: 761 test ⇒ chỉ còn 2 đỏ ở test cung–cầu (lộ ra khi setUpClass hết gãy)
    ⇒ sửa ⇒ `/wujia_sale` **16/0**. Quét 4 module = 0.
- Lệch / LIMIT:
  - ★VR: "SP" → EN "SKUs"; glossary "Qty" = "SL" cũng áp nhãn field backend `qty` của dòng giỏ; "Có lỗi xảy ra, vui lòng thử lại" dùng
    chung câu EN ⇒ bản vi giờ là "Có lỗi xảy ra. Vui lòng thử lại." (dấu `,` → `.`); 35 câu backend mới dịch (danh sách ở `.po`) cho BA rà.
- Bài học: ghi ở `next-session-clusters-J.md` §6 "J-V4".
- Lệnh deploy: thêm `wujia_portal_layout,wujia_sale,wujia_order_window,wujia_portal_sale` vào lệnh `-u` gộp; **restart sau `-u`**. Kiểm deploy kế có thật sự
  chạy tới tầng `portal_*` (V3 dừng trước tầng này 2 lần).
- UAT (06/10, chủ dự án deploy `359fe36c`): 4 module đúng bản (`portal_layout` 19.0.60.3.0 · `sale` 19.0.4.7.0 · `order_window` 19.0.1.1.0 ·
  `portal_sale` 19.0.5.0.0, upgrade 09:06 UTC — lần này deploy chạy tới tầng `portal_*`). Kiểm chỉ-đọc `anh.owner` (Playwright chặn mọi
  POST trừ đăng nhập ⇒ 0 ghi): vi/en/th × 1440/390 × catalog, giỏ, chi tiết SP, ngoài khung giờ — **0 tràn, 0 lỗi JS, 0 request lỗi
  (hết 404 locale)**, `<html lang>` đúng, 13 key `data-wj-msg-*`; câu client chi tiết SP + confirm xoá + modal xác nhận (`{brand}`) +
  khung qua đêm "10:00 today – 04:00 tomorrow (UTC+7)" ra EN ở en/th, y chữ cũ ở vi. Ngôn ngữ user trả về vi_VN.
  Phát hiện (có sẵn, không do V4): (1) trang chi tiết SP khổ 390 hàng nút không `flex-wrap` ⇒ nút "Xem giỏ"/"View cart" bị cắt ở mép thẻ
  (vi cũng vậy); (2) mọi trang portal nạp `pdfmake` + `vfs_fonts` (~1,8 MB) của datatable ⇒ `load` ~2 s; bấm nút trước `load` thì
  lazyloader Odoo giữ cú bấm (spinner) rồi phát lại — đúng thiết kế, không kẹt.
- Sửa sau UAT (06/10, **đã push `6129ca59`**): `portal_layout` 19.0.60.4.0 · `portal_sale` 19.0.5.1.0 · `portal_exam` 19.0.7.1.0 ·
  `portal_base` 19.0.7.37.0.
  - Chi tiết SP: hàng "Số lượng · Thêm vào giỏ · Xem giỏ" thêm `flex-wrap` + nhãn `text-nowrap` ⇒ 390 nút "Xem giỏ" xuống dòng, hết cắt.
  - `assets.xml`: bỏ `tables_js` (DataTables + `pdfmake`/`vfs_fonts`, ~2 MB/trang, không trang nào dùng — `$.fn.DataTable` vốn không gắn
    được dưới AMD Odoo) + CSS datatables + bản nạp trùng `jquery.orgchart.js` + `<script src="https://cdnjs.com/libraries/orgchart">`
    (URL là trang HTML ⇒ mỗi trang 1 request ra ngoài vô ích).
  - Thi PC "Đăng ký mới": tiêu đề khung giờ kẹt "Khung giờ ngày —" kể cả sau khi chọn ngày — D3d chuyển sang `wj_card_header` nhưng
    `portal_exam_pc.js` vẫn tìm `.wj-exam-pc-slots__title` (null, im lặng). Sửa selector `.wj-exam-pc-slots__head .wj-card-header__title`;
    chưa chọn ngày hiện "Khung giờ" (giống JS khi đổi khoá). Guard mới `TestCardHeaderExamPcJsContract`.
  - Số ít EN: "1 order in 30 days", "1 undelivered order" (home PC + mobile), "1 session • In the next 60 days" (khoá thi) — msgid số ít
    riêng, vi_VN trỏ cùng câu cũ (glossary +4 dòng). Test `test_home_counts_singular_plural`, `test_course_meta_singular_plural`.
  - Nghiệm thu: `-u` 4 module, suite `/wujia_portal_layout,/wujia_portal_base,/wujia_portal_exam,/wujia_portal_sale,/wujia_exam` **686/0**;
    scan 6 module = 0; Playwright local vi/en × 1440/390: 0 tràn, 0 lỗi JS, 0 HTTP lỗi, **0 request pdfmake/datatable/cdnjs**, nút "Xem giỏ"
    trọn trong thẻ, tiêu đề thi "Khung giờ" → "Khung giờ ngày 11/10/2026"; probe vi_VN 52 trang: lệch chữ duy nhất có chủ đích là
    "Khung giờ ngày —" → "Khung giờ" (còn lại do dữ liệu DB đo: giỏ có hàng, khoá thi có lịch mở).
  - Lệnh deploy: `-u wujia_portal_layout,wujia_portal_base,wujia_portal_exam,wujia_portal_sale` + restart.
- Nợ để lại: xoá DB nháp `wujia_v3b`, `wujia_v4b`, `wujia_v4h` + worktree nháp trong scratchpad (giữ `wujia_t1` tới hết Phần V); ★VR như trên.
- Phiên kế: **J-V5** — `wujia_portal_debt` (196) + `wujia_account` (4), so mốc vi_VN sau V4.

## J-V5 Việt hoá source `wujia_portal_debt` + `wujia_account` · 06/10/2026 · Mac
- Kết quả: ✅ code + test, **đã push `main` `2f9f5695`**, chủ dự án deploy; 0 ghi sheet (không có ID Issue List).
- Đầu phiên: HEAD `a6f97309` (J-V4, khớp `origin/main`). Không module Thái nào phụ thuộc 2 module này; phụ thuộc ngược chỉ
  `wujia_portal_base` (Home KPI qua `hasattr`) + test `wujia_portal_layout` ⇒ không đụng code Thái.
- Đã làm (`wujia_portal_debt` 19.0.5.0.0 · `wujia_account` 19.0.1.2.0):
  - Câu gốc → tiếng Anh: `docs/i18n-pairs/wujia_portal_debt.csv` 196 dòng (auto 161 · tay 35), `wujia_account.csv` 4 (tay);
    glossary +122 dòng (chỉ thêm, CRLF, 0 dòng cũ đổi).
  - `models/wujia_portal_debt.py`: `STATE_BADGE` / `INVOICE_BADGE` → `_lt` đúng câu EN đã có trong `_STATUS_TERMS_BY_VARIANT`
    (Has overdue · Partially paid · Unpaid · Credit balance · Paid · Overdue · Partial · Credit note) ⇒ màu badge giữ nguyên, 0 term mới;
    helper `translated_badges(env, badges)` cho controller. Số rút gọn `_short_amount(amount, symbol, env)`: đơn vị `_lt('%sB'|'%sM'|'%sK')`
    (vi = `%stỷ`/`%str`/`%sk`) + dấu thập phân theo `res.lang` người xem (en `12.7M`, vi `12,7tr`). Fallback `self.env._('Bank')` /
    `_('Bank transfer')`.
  - `controllers/portal.py`: `build_pager(item_label=_lt('invoices'|'transactions'))`; badge dịch theo `request.env`.
  - QWeb: 6 biểu thức `t-*` → `<t t-set>` (nhãn filter "Invoice week"/"Payment period", tiêu đề thẻ, "Amount paid/Deducted/Remaining",
    badge PC "No activity"/"No debt", trạng thái rỗng lịch sử); số ít/số nhiều EN qua `t-if n == 1` ("1 invoice", "1 transaction"…),
    vi_VN cả 2 nhánh trỏ cùng câu cũ; `name=` 7 template + nav/Home KPI → EN ("Debts & payments").
  - JS `portal_debt.js` 3 câu nút sao chép → `data-wj-msg-copy-empty|copied|copy-failed` (`<t t-set>` + dict `t-att` trên khối ngân hàng PC
    + mobile) + `copyMsg(el, key, 'EN')` qua `wjMsg`.
  - `wujia_account`: manifest + 3 log migration → EN.
  - `.po` + `.pot`: `wujia_portal_debt` 149 msgid / 145 dịch (HEAD 52; còn `PDF`, 2 chip `i`, `ID` — giống source);
    `wujia_account` **mới** 18 / 17 (13 nhãn field/help backend vốn EN nay có bản vi, thuật ngữ Odoo core).
  - Test: `tests/common.py::load_vi`; `test_portal_debt` (HttpCase user vi_VN, badge so `._source`, `TestShortAmountSigned` chạy env vi +
    case en mới), `test_list_card_e5b2`, `test_f5_nav_item`, `test_card_header_d3f` (thẻ bank có thêm `t-att`). Mới `test_jv5_i18n`: bảng
    nhãn VN TRƯỚC V5 (badge + màu, fallback bank, pager, arch vi/en 4 template), mọi key JS có attr trên 2 root, HttpCase vi/en
    (tổng quan + "1 invoice", trang pay `data-wj-msg-*` ×2, lịch sử rỗng + "0 transactions"). Không xoá assert nào.
- Số đo:
  - `vn_hardcode_scan --fail-on-any`: 2 module **0** (trước 200).
  - `-u wujia_account,wujia_portal_debt,wujia_portal_base,wujia_portal_layout --test-enable` (DB copy `wujia_v5b`): **666 test, 0 đỏ**;
    HEAD (worktree + `wujia_v5h`) 656 / 0 / 0. Lần đầu 2 đỏ do test (d3f tìm `<section class="wj-debt-bank">` nguyên thẻ; arch en còn
    comment XML tiếng Việt) ⇒ sửa test.
  - Mutation (đã khôi phục): bỏ key `copied` 1 root ⇒ đỏ 2 test; đổi câu EN badge `Unpaid` không thêm glossary ⇒ đỏ (nhãn + màu); bỏ dịch
    đơn vị ở `_unit` ⇒ đỏ 9 test số rút gọn.
  - So giá trị vi_VN DB HEAD ↔ mới (field/help/selection/model/menu/action/arch): **0 chỗ VN → EN**; 17 chỗ EN → VN (backend `wujia_account`).
  - `wj_text_probe` vi_VN 52 trang HEAD ↔ mới: **0/52 lệch** ⇒ mốc `docs/i18n-baseline/vi_VN.json` giữ nguyên.
  - Playwright `anh.owner` en_US/th_TH × 1440/390 (`/portal/debt`, `?all=1`, `/pay`, `/payment-history`, Home): **20/20 OK** — 0 tràn,
    0 lỗi JS, 0 HTTP ≥400, `<html lang>` đúng; chữ VN còn là dữ liệu (cửa hàng, địa chỉ, "Ngô Gia") + nội dung module V6–V8 trên Home.
- Lệch / LIMIT:
  - `anh.owner` (DB đo) không có công nợ ⇒ probe/Playwright chỉ thấy trạng thái rỗng; trạng thái có hoá đơn (badge, số rút gọn, khối ngân
    hàng + câu JS, modal QR PC) chỉ đo bằng HttpCase `TestJv5PortalByLang` (1 hoá đơn, tài khoản JV5-ACC) — chưa đo tràn chữ EN bằng mắt.
  - ★VR: tiêu đề trang EN "Debts"; nhãn "Debts & payments"; "No activity"/"No debt"; 13 nhãn backend `wujia_account` mới dịch cho BA rà.
- Bài học: ghi ở `next-session-clusters-J.md` §6 "J-V5".
- Lệnh deploy (sau khi được lệnh push): `-u wujia_account,wujia_portal_debt` + **restart sau `-u`**.
- Nợ để lại: xoá DB nháp `wujia_v5b`, `wujia_v5h` + worktree `wt_head` (scratchpad) — giữ `wujia_t1` tới hết Phần V.
- UAT (06/10, deploy `0d6464be`): deploy lại **dừng trước tầng `portal_*`** (lần 3) — chỉ `portal_layout` lên bản; code đã pull
  (`installed_version` đĩa mới). Upgrade tay qua admin (`button_immediate_upgrade`) 5 module: `wujia_account` 19.0.1.2.0 ·
  `portal_debt` 19.0.5.0.0 · `portal_base` 19.0.7.37.0 · `portal_exam` 19.0.7.1.0 · `portal_sale` 19.0.5.1.0 (2 module cuối là sửa sau UAT
  V4 `6129ca59` chưa từng lên). Arch vi/en 3 view debt đúng (RPC chỉ-đọc). Playwright `anh.owner` chỉ-đọc (chặn POST trừ đăng nhập)
  vi/en/th × 1440/390 × 5 trang: **30/30 0 tràn, 0 lỗi JS, 0 HTTP ≥400**, `<html lang>` đúng; 3 "BAD" chỉ là kiểm chữ tiêu đề của
  script (trang lịch sử khổ 390 không có chữ "Công nợ"/"Debts") — không lỗi. Chữ VN còn ở en/th = dữ liệu + brand + nội dung V6–V8.
  Mạng tới UAT nghẽn ngắt quãng (bundle `web.assets_frontend` lúc treo) ⇒ script cần retry + 1 lần đăng nhập. Ngôn ngữ user trả vi_VN.
  Đã xoá DB nháp `wujia_v5b`/`wujia_v5h` + worktree; local chỉ còn `wujia_t1`.
- Phiên kế: **J-V6** — `wujia_portal_return` (168) + `wujia_return` (69).

## J-V6 Việt hoá source `wujia_portal_return` + `wujia_return` · 06/10/2026 · Mac
- Kết quả: ✅ code + test, **đã push `main` `b78c4568`**, chờ deploy; 0 ghi sheet (không có ID Issue List).
- Đầu phiên: HEAD `0d6464be` = `origin/main`. Không module Thái nào phụ thuộc; phụ thuộc ngược `wujia_portal_base` (Home KPI +
  `RETURN_STATUS_LABELS` đã `_lt` từ V2) + `wujia_portal_layout` ⇒ `-u` cả 4. Issue List 10 Ready for Dev (157–168) để sau ★JR.
- Đã làm (`wujia_portal_return` 19.0.5.0.0 · `wujia_return` 19.0.2.0.0):
  - Câu gốc → tiếng Anh: `docs/i18n-pairs/wujia_portal_return.csv` 168 dòng (auto 141 · tay 27), `wujia_return.csv` 69 (auto 63 · tay 6);
    glossary +170 dòng (chỉ thêm, CRLF, byte cũ giữ nguyên).
  - `controllers/portal.py`: `RESOLUTION_LABELS`, `COMPENSATION_STATUS_LABELS`, `FILTER_ALL_LABEL` → `_lt`, dịch lúc render bằng
    `request.env._` (helper `_translated`); badge bù hàng dùng đúng câu EN đã có trong `_STATUS_TERMS_BY_VARIANT` (Not processed ·
    Replacement ordered · Partially compensated · Fully compensated) ⇒ màu giữ nguyên, 0 term mới. `item_label=_lt('requests')`, lỗi chung
    + 5 nhãn tiến độ giao (`Delivered %d/%d slips`) qua `request.env._`. Bỏ `resolution_labels` thừa trong ctx chi tiết.
  - QWeb: biểu thức `t-*` → `<t t-set>` (dict notice 3 câu, placeholder/nhãn filter, "No notes."); số ít/số nhiều EN qua biến đếm
    (`_ret_n`) — "1 result"/"1 request"/"1 attached photo"; `name=` nav/sheet → EN ("Returns / Compensation").
  - JS `portal_return.js` 2 placeholder select sản phẩm → `data-wj-msg-select-product|no-products` (`<t t-set>` + dict `t-att` trên
    `#wj-ret-pc-order` + `#wj-ret-m-order`) + `msg(key, 'EN')` qua `wjMsg`.
  - `wujia_return`: 50 `_()` model/wizard + 4 `models.Constraint` + 3 attr view backend + manifest → EN. `_('SO bù hàng')` đổi thành
    "Compensation sales order" (không trùng nhãn field "Compensation SO" = "SO bù").
  - **Seed loại lỗi** (`noupdate`): XML → EN; `legacy_seed.py` (bảng VN cũ ↔ EN, miễn quét) + `migrations/19.0.2.0.0/post-migrate.py`
    chỉ đổi bản ghi mà `en_US` còn ĐÚNG câu VN seed (đặt `en_US`=EN, thêm `vi_VN`=VN nếu chưa có) — HQ sửa tay giữ nguyên. DB copy:
    "10 issue-type field(s) moved to EN source". DB cài mới lấy vi_VN từ `.po` (`model:wujia.return.issue.type`).
  - `.po` + `.pot` (mới cả 2): `wujia_portal_return` 127 msgid (HEAD 94), còn `MB.` (giống source); `wujia_return` 255 (HEAD 239),
    42 chưa dịch đều là field mail/activity của mixin core (có từ trước). Khôi phục 6 msgstr cũ bị glossary chung ghi đè (Active, Compensation
    SO, Complete, In progress, Original order, Partially compensated) bằng sửa text `.po` + `i18n import -w`.
  - Test: `load_vi` cho 2 module (`wujia_portal_return/tests/common.py` mới); `test_portal_rules` + `TestCompensationConfig` chạy env vi;
    `test_f5_nav_item` + `test_return_card_d6` (assert EN + vi). Mới `wujia_portal_return/tests/test_jv6_i18n.py` (bảng VN TRƯỚC V6:
    phương án, tình trạng bù + màu, filter-all, nhãn giao, lỗi chung, arch vi/en 3 màn; key JS có attr trên 2 select; HttpCase vi/en list
    "1 result/1 request", form `data-wj-msg-*` ×2, chi tiết bù hàng + "1 attached photo") + `wujia_return/tests/test_jv6_i18n.py`
    (12 thông báo + 3 constraint vi; bảng seed khớp XML; migration: bản cũ đổi, bản HQ sửa giữ, vi_VN có sẵn giữ, chạy lại = 0).
    Không xoá assert nào.
- Số đo:
  - `vn_hardcode_scan --fail-on-any`: 2 module **0** (trước 237).
  - `-u wujia_return,wujia_portal_return,wujia_portal_base,wujia_portal_layout --test-enable` (DB copy `wujia_v6b`): **679 test, 0 đỏ**;
    HEAD (worktree + `wujia_v6h`) 663 / 0 / 0. Lần đầu 8 đỏ + 1 lỗi đều do test (assert VN ở env en; test d3 cấm `returns` trong `t-if`;
    nav/d6 đọc arch gốc) ⇒ sửa test/biến đếm.
  - Mutation (đã khôi phục): bỏ key `no-products` ⇒ đỏ 2 test; đổi câu EN badge `Not processed` không thêm glossary ⇒ đỏ 2 test (nhãn +
    màu, chi tiết HttpCase); bỏ `_lt` ở `Exchange` ⇒ đỏ.
  - So giá trị vi_VN DB HEAD ↔ mới (field/help/selection/menu/action/arch/constraint/issue type, 254 bản ghi): **0 chỗ VN → EN**; chữ hiển
    thị 3 màn portal chỉ THÊM (t-set notice/JS, nhánh số nhiều).
  - `wj_text_probe` vi_VN 52 trang HEAD ↔ mới: **2/52 lệch, đều có chủ đích** — `/portal/return/new` @1440/@390 thêm 4 attr
    `data-wj-msg-*` (chữ VN cũ của JS); chữ hiển thị 0 lệch.
  - Playwright `anh.owner` en_US/th_TH × 1440/390 (`/portal/return`, `/new`, chi tiết `/464`): **12/12 OK** — 0 tràn, 0 lỗi JS, 0 HTTP ≥400.
    Placeholder JS (kích bằng option giả): vi "— Đơn không có sản phẩm —", en/th "— Order has no products —".
- Lệch / LIMIT:
  - DB đo không có đơn trong 10 ngày ⇒ nhánh "— Select a product —" chỉ kiểm bằng test arch/HttpCase, chưa nhìn bằng trình duyệt.
  - th_TH chưa có bản dịch module ⇒ thấy EN (đúng thiết kế, chờ J-T5).
  - ★VR: "Replacement ordered" (badge EN cũ từ V2), "Still short", "Compensation sales order", "Canceled" (ribbon backend) cho BA rà.
- Bài học: ghi ở `next-session-clusters-J.md` §6 "J-V6".
- Lệnh deploy: `-u wujia_return,wujia_portal_return` + **restart sau `-u`** (migration seed chạy trong `-u`).
- Nợ để lại: xoá DB nháp `wujia_v6b`, `wujia_v6h` + worktree `v6/head` (scratchpad) — giữ `wujia_t1` tới hết Phần V.
- UAT (06/10, deploy `8a0d5df6`): code đã pull + restart nhưng **2 module return chưa upgrade** (DB `wujia_return` 19.0.1.1.0,
  `portal_return` 19.0.4.1.0) ⇒ trạng thái lệch: Python/JS mới + view cũ ⇒ en/th vẫn chữ Việt, form không có `data-wj-msg-*` nên user
  vi_VN thấy placeholder EN. Chủ dự án duyệt ⇒ upgrade tay qua admin (`button_immediate_upgrade`, 6 s): 2 module lên 19.0.2.0.0 /
  19.0.5.0.0; migration seed chạy — loại lỗi en_US = EN, vi_VN giữ nguyên (cả bản HQ đã sửa "Hết hạn / cận ngày"); constraint en/vi đúng.
  Playwright `anh.owner` chỉ-đọc (chặn POST trừ đăng nhập) vi/en/th × 1440/390 × 3 trang (danh sách, tạo mới, chi tiết `/14`):
  **18/18 0 tràn, 0 HTTP ≥400**; vi thấy y chữ cũ, en/th thấy EN (tiêu đề, "Resolution", "Compensation status", "No notes.",
  "— All statuses —"); placeholder JS vi "— Đơn không có sản phẩm —", en/th "— Order has no products —". 1 lỗi JS lẻ
  `$(...).pickadate is not a function` (th @1440, lượt đầu) — chạy lại 3 lượt × th/vi × 3 trang = 18/18 sạch ⇒ race nạp vendor khi mạng
  UAT chập chờn, không liên quan V6. Ngôn ngữ `anh.owner` trả vi_VN.
- Phiên kế: **J-V7** — support (112+2) + knowledge (46+2) + notification (86+27).

## J-V7 Việt hoá source support + knowledge + notification (+ WJ-SUPPORT-003) · 07/10/2026 · Mac
- Phạm vi: `wujia_portal_support` (112) + `wujia_support` (2) · `wujia_portal_knowledge` (46) + `wujia_knowledge` (2) ·
  `wujia_portal_notification` (86) + `wujia_notification` (27). Gộp **WJ-SUPPORT-003** (chủ dự án chốt 06/10): PC "Normal" ≠ mobile
  "Bình thường". KHÔNG làm WJ-SUPPORT-002. Không đụng module Thái. Commit `351932a8` (đã push, chờ deploy).
- Đã làm:
  - `vn_to_en_pairs` draft → check → apply cho 6 module (`docs/i18n-pairs/*.csv` CRLF); glossary +48 dòng (chỉ nối thêm; dòng
    "General" của phiên này đổi thành "General notice" — key chung chung dễ đụng).
  - support: `STATE_LABELS` / `MOBILE_TICKET_BADGES` / `PRIORITY_LABELS` → `_lt`, dịch lúc render qua `_translated()` + `_label_ctx()`
    (màu badge giữ: `status_badge_for(lazy)`, Canceled ghim danger); t-set filter/placeholder; số ít/nhiều ticket/tickets, reply/replies.
    **WJ-SUPPORT-003**: dd Mức độ PC đọc `priority_labels` (cùng nguồn mobile) thay `dict(_fields['priority'].selection)`.
  - knowledge: `_lt('articles')`, t-set placeholder/tiêu đề "Recently updated documents", badge Mandatory/Important/New (PC + 2 dict
    mobile), article/articles, view/views.
  - notification portal: `ERROR_MESSAGES` + `PORTAL_PRIORITY_LABELS` → `_lt` + helper `_error_message` / `_priority_labels` /
    `_pc_priority_tags` (JSON `/recent` cũng dịch); dict `WJ_PTAG` / `WJ_TDESC` ra t-set; JS `header_bell_badge.js` +
    `portal_notification_pc.js` đọc `data-wj-msg-*` (popup chuông `#wj-noti-popup`, nút đánh dấu đã đọc ở template `results_part`)
    với `%s` + số ít/nhiều.
  - `wujia_notification`: MSG_* `_lt`, 6 constraint EN, `_compute_priority_label` thêm `@api.depends_context('lang')`; seed 5 loại thông
    báo (noupdate) → EN + `legacy_seed.py` + `migrations/19.0.2.0.0/post-migrate.py` (mẫu V6). Máy quét khai `legacy_seed.py`.
  - Tên template nav (attr `name`) → EN. Bump version 6 module. `.po` vi_VN tái sinh + `.pot` mới cho 4 module; khôi phục 14 msgstr
    bị glossary chung ghi đè (Active, Archive, Attachments, In progress, Priority, Support → "Hỗ Trợ", Knowledge → "Kiến Thức",
    Published, Submission date) bằng sửa text + `i18n import -w`; `msgfmt -c` sạch.
  - Test: `tests/common.py` `load_vi` cho 3 module L2; `test_f5_nav_item` support/knowledge kiểm arch vi + en. Mới `test_jv7_i18n.py`
    ×4 (bảng VN TRƯỚC phiên: trạng thái/badge + màu, ưu tiên, pager, lỗi, arch không còn `_fields['priority'].selection`, key JS ↔ attr,
    JS không còn chữ Việt; HttpCase vi/en số ít "1 ticket/1 reply/1 article/1 view/1 notification"; **PC = mobile vi/en + đổi
    ngôn ngữ**; MSG_*/constraint/priority_label theo ngôn ngữ; seed khớp XML + migration giữ bản HQ sửa, chạy lại = 0). Không xoá assert.
- Số đo:
  - `vn_hardcode_scan --fail-on-any`: 6 module **0** (trước 275).
  - `-u` 6 module + `portal_base` + `portal_layout` `--test-enable` (DB copy `wujia_v7b`): **1032 test, 0 đỏ**; HEAD 999 / 0.
  - Mutation (đã khôi phục): bỏ attr JS, đổi câu EN badge, bỏ `_lt`, trả PC ưu tiên về selection ⇒ 5 đỏ + 1 lỗi.
  - So vi_VN DB HEAD ↔ mới: 52 chỗ khác, đều EN → VN (backend dịch thêm), **0 VN → EN**. Migration log "5 notification type(s) moved".
  - `wj_text_probe` vi_VN 54 trang (thêm trang chi tiết kiến thức vào probe): mới 2 lần 0/54 lệch; HEAD ↔ mới chỉ (a) attr
    `data-wj-msg-*` của popup chuông (mọi trang) — có chủ đích; (b) `/portal/support/new` danh mục seed "Order"/"Delivery" nay "Đặt
    hàng"/"Giao hàng" (trước user vi thấy EN). Chữ VN → EN: 0.
  - Playwright `anh.owner` en_US/th_TH × 1440/390 (support danh sách/tạo/chi tiết, knowledge danh sách/chi tiết, notification danh
    sách/chi tiết + chuông, home): **0 tràn, 0 lỗi JS, 0 HTTP ≥400**. Chữ VN còn lại = dữ liệu người dùng + menu module khác (V8).
    Ticket đo `WJ-TK/26/00328` (DB nháp): vi PC "Mức độ: Khẩn" = mobile "Ưu tiên: Khẩn"; en/th cả hai "Urgent".
- WJ-SUPPORT-003: ledger + `qa_sync.py --only WJ-SUPPORT-003 --apply` ⇒ **Ready for Retest** (6 ô + 1 dòng History), build ghi
  "CHƯA lên UAT | commit 351932a8".
- Lệch / LIMIT: zh/th chưa có bản dịch câu mới ⇒ thấy EN (chờ J-T5). `wujia.notification.priority_label` nay dịch theo ngôn ngữ (HEAD
  trả EN thô; không view nào dùng). msgid chưa dịch còn lại là field mixin mail/activity + vài câu EN có sẵn từ trước (không phải lùi).
- Sự cố trong phiên: backup mutation chép 2 file cùng tên `portal.py` vào một thư mục ⇒ lúc khôi phục controller support bị đè bằng
  controller notification; đã viết lại đúng nội dung, đối chiếu diff với HEAD + diffstat các file khác khớp trước mutation, test 0 đỏ.
- Bài học: ghi ở `next-session-clusters-J.md` §6 "J-V7".
- Lệnh deploy: `-u wujia_support,wujia_portal_support,wujia_knowledge,wujia_portal_knowledge,wujia_notification,wujia_portal_notification`
  + **restart sau `-u`** (migration seed loại thông báo). Kiểm tra version DB sau upgrade (bài học UAT V6).
- UAT (07/10, `fa6a6835`): đã deploy + **đã upgrade** sẵn (6 module DB = code: support 19.0.1.1.0 / portal 19.0.5.0.0, knowledge
  19.0.1.1.0 / 19.0.5.0.0, notification 19.0.2.0.0 / 19.0.4.0.0) ⇒ không cần upgrade tay. Migration seed chạy: loại thông báo en
  "Emergency, General notice, Promotion, System, Other", vi giữ "Khẩn cấp, Thông báo chung, Khuyến mãi, Hệ thống, Khác"; constraint
  en/vi đúng; template chi tiết hỗ trợ không còn `_fields['priority'].selection` (dùng `priority_labels` ×3).
  Playwright `anh.owner` chỉ-đọc (chặn POST trừ đăng nhập + `/portal/notification/recent`) vi/en/th × 1440/390 × 7 trang (hỗ trợ
  danh sách/tạo, kiến thức danh sách/chi tiết, thông báo danh sách/chi tiết, home): **42/42 0 tràn, 0 lỗi JS, 0 HTTP ≥400**; popup
  chuông vi "2 thông báo • 1 chưa đọc", en "2 notifications • 1 unread", th tên loại tiếng Thái có sẵn. Ngôn ngữ `anh.owner` trả vi_VN.
  LIMIT: `anh.owner` (HN-01) 0 phiếu hỗ trợ, `dung.multi` (HN-02) không đăng nhập được bằng mật khẩu test ⇒ phiếu WJ-TK/26/00006 chưa
  nhìn bằng trình duyệt trên UAT (đã đo trên DB copy + HttpCase). Ghi nhận: form tạo mobile có 2 chip "Gấp"/"Khẩn cấp" cùng map
  `urgent` (BA, có từ trước) ⇒ chi tiết hiện "Khẩn" — ngoài phạm vi.
- Phiên kế: **J-V8** — purchase_history (99) + delivery (93+15) + info_request (85+7) + report (69) + fleet/core/metabase (21).

## J-V8a Việt hoá source lịch sử đặt hàng + giao hàng + đội xe · 07/10/2026 · Mac
- Phạm vi (chủ dự án chốt 07/10 tách J-V8 làm đôi): `wujia_portal_purchase_history` (99) · `wujia_portal_delivery` (93) ·
  `wujia_delivery` (15) · `wujia_fleet` (11) = 218 chuỗi. Gom vì cùng nhãn trạng thái chuyến giao. Không đụng module Thái.
  Commit `dbd4335b` (push cùng J-V8b), nền HEAD `5dc1c1a0`.
- Đã làm:
  - `vn_to_en_pairs` draft → check → apply cho 4 module (`docs/i18n-pairs/*.csv` CRLF, 4 file mới); glossary +101 dòng (chỉ nối thêm).
    4 key EN của phiên đổi cho cụ thể vì đụng msgid field backend module khác: "Shipping status" (không "Delivery status"),
    "Vehicle trip", "Departs at", "Total drop".
  - purchase_history: `BATCH_STATUS_LABELS` (6 nhãn) / `ERR_NO_STORE` / `ERR_NOT_FOUND` → `_lt`, dịch lúc render (`_batch_status_labels()`,
    `_error_message()`); `BACKEND_REQUESTER_LABEL = _lt('Created by {brand}')` dịch TRƯỚC rồi `_wj_brand_text`; pager dùng nhãn chung
    `records`. QWeb: 7 t-set `_ph_t_*` (câu dự phòng "Not delivered yet", "No delivery information yet", "No notes(.)", placeholder,
    "All statuses", "Order details"); số ít/nhiều order(s), latest order(s), product(s).
  - portal_delivery: `MOBILE_BATCH_BADGE` → nhãn `_lt` + helper `_batch_badge()` (màu ghim cứng theo trạng thái, không đổi); pager
    `_lt('trips')`; file ICS `env._('Delivery %s')` / `env._('Batch: %s')`; t-set `_dlv_t_*` cho filter/placeholder; trip(s).
    Module chưa có `i18n/` ⇒ sinh mới `vi_VN.po` + `.pot`.
  - delivery: 10 `sum=` + `title="Overloaded"` ở report/view; manifest + log migration → EN. fleet: 4 constraint + 4 câu `_()` + log +
    manifest → EN.
  - Tên template nav (attr `name`) → EN. Chữ không dấu máy quét bỏ sót: "Xem" → View, "STT" → No., "· SL: x" → "· Qty: x".
  - Bump: purchase_history / portal_delivery 19.0.3.22.0 → **19.0.4.0.0**, delivery 19.0.1.1.0 → **19.0.1.2.0**, fleet 19.0.1.0.1 →
    **19.0.1.1.0**. Không có seed `noupdate` tiếng Việt ⇒ không migration.
  - `.po` vi_VN tái sinh + `.pot` cho 4 module; khôi phục 6 msgstr fleet bị glossary chung ghi đè (Active, Archive, Coverage,
    Identification, Priority, Reset to draft) bằng sửa text + `i18n import -w`; `msgfmt -c` sạch.
  - Test: `test_f5_nav_item` delivery/purchase_history kiểm nhãn EN ở arch en + VN ở arch vi (không xoá assert). Mới `test_jv8_i18n.py`
    ×3 (purchase_history, portal_delivery, fleet): bảng VN TRƯỚC phiên (6 nhãn chuyến, 6 badge + màu, lỗi, "{brand} tạo đơn", pager
    "chuyến"), arch en không còn chữ Việt / câu dự phòng không nằm trong biểu thức; HttpCase vi/en số ít "1 order/1 trip/1 product",
    câu dự phòng, placeholder, badge chi tiết, "Loading goods"/"Đang chất hàng", lỗi không tìm thấy, ICS "Delivery/Batch:" ↔
    "Giao hàng/Mã lô:"; constraint + `_()` fleet theo ngôn ngữ.
- Số đo:
  - `vn_hardcode_scan --fail-on-any`: 4 module **0** (trước 218).
  - `-u fleet,delivery,portal_delivery,portal_purchase_history,portal_sale,portal_base,portal_layout --test-enable` (DB copy
    `wujia_v8r` từ mốc HEAD): **985 test**; HEAD 966 / 0. Lần chạy đủ còn 2 đỏ do chính regex test mới bắt nhầm `or '—'` ⇒ siết regex
    chỉ bắt chữ có dấu, chạy lại `wujia_jv8,wujia_f5,wujia_delivery_c5`: **37/37 xanh**.
  - Mutation trên bản snapshot (code thật không đụng): đổi câu EN badge, bỏ t-set, ICS không qua `_()`, bỏ `_lt`, đổi câu constraint
    ⇒ **6 đỏ + 1 lỗi**, đủ 5/5 đột biến bị bắt.
  - So vi_VN DB HEAD ↔ mới: 32 chỗ khác, đều EN → VN, **0 VN → EN**. Arch vi các view backend không đổi.
  - `wj_text_probe` vi_VN 54 trang: mới 2 lần, mỗi lần so mốc HEAD **0/54 lệch**.
  - Playwright `anh.owner` chỉ-đọc (chặn POST trừ đăng nhập) en_US/th_TH × 1440/390 × 4 trang (home, lịch sử danh sách/chi tiết
    `/1799`, giao hàng danh sách): **16/16 0 tràn, 0 lỗi JS, 0 HTTP ≥400** (2 lỗi console mỗi trang chỉ do script chặn 2 POST đếm
    badge chuông/giỏ). Chữ VN còn lại trên trang en = dữ liệu (cửa hàng, người dùng, thương hiệu "Ngô Gia"), tên ngôn ngữ "Tiếng Việt",
    menu "Báo cáo"/"Khảo sát" (thuộc V8b).
- Lệch / LIMIT: `anh.owner` không có chuyến giao nào ⇒ chi tiết chuyến chưa nhìn bằng trình duyệt (đã phủ HttpCase badge + ICS).
  zh/th chưa có bản dịch câu mới ⇒ thấy EN (chờ J-T5). Câu EN chi tiết đơn tạo từ backend từng đọc "Ordered by Created by Ngô Gia"
  ⇒ chủ dự án chốt 07/10 `BACKEND_REQUESTER_LABEL = _lt('{brand} (backend)')` ("Ordered by Ngô Gia (backend)"), vi y cũ; `wujia_jv8` 10/10.
- Bài học: ghi ở `next-session-clusters-J.md` §6 "J-V8a".
- Lệnh deploy: `-u wujia_fleet,wujia_delivery,wujia_portal_delivery,wujia_portal_purchase_history` + **restart sau `-u`**; kiểm version
  DB = 19.0.1.1.0 / 19.0.1.2.0 / 19.0.4.0.0 / 19.0.4.0.0.
- Dọn sau: DB `wujia_v8h`/`wujia_v8t`/`wujia_v8b`/`wujia_v8r` + filestore, worktree `scratchpad/v8/head` (`git worktree remove`).
  Giữ `wujia_t1` tới hết Phần V.
- Phiên kế: **J-V8b** — `wujia_portal_info_request` (85) + `wujia_info_request` (7) + `wujia_portal_report` (69) + `wujia_core` (9,
  sửa câu **không bump version**; `DEFAULT_BRAND_NAME = 'Ngô Gia'` giữ + khai miễn quét) + `wujia_metabase_connector` (1).

## J-V8b Việt hoá source yêu cầu cập nhật thông tin + báo cáo + core + metabase · 07/10/2026 · Mac
- Phạm vi: `wujia_portal_info_request` (85) · `wujia_info_request` (7) · `wujia_portal_report` (69) · `wujia_core` (9) ·
  `wujia_metabase_connector` (1) = 171 chuỗi. Không đụng module Thái. Nền HEAD `dbd4335b` (= commit J-V8a, push cùng phiên này).
- Đã làm:
  - `vn_to_en_pairs` draft → check → apply 5 module (`docs/i18n-pairs/*.csv` CRLF, 5 file mới); glossary +74 dòng (chỉ nối thêm).
    Key EN đổi cho cụ thể vì trùng msgid module khác: "Withdraw request" / "Withdraw this request?" (trùng `wujia_return`),
    "Orders cancelled" (trùng `wujia_sale`); "The request has been cancelled." (glossary đã có "Request cancelled." nghĩa khác).
  - portal_info_request: `REQUEST_TYPE_LABELS` (7) + `STATE_LABELS` (5, màu badge giữ nhờ `status_badge_for(lazy)`) → `_lt`, dịch lúc
    render (`_type_labels()`, `_type_options()`, `_state_labels()`); 6 câu lỗi `_()` → EN; pager `_lt('requests')`; QWeb t-set
    `_inf_t_*` cho filter; confirm huỷ qua `data-wj-msg-confirm` (không còn câu trong `onclick`); result(s) số ít/nhiều.
  - info_request: 3 câu `_()` + `_sql_constraints` + manifest → EN; refuse_reason "Cancelled by user" (vi "User huỷ").
  - portal_report: `STATE_LABELS` (5 nhãn, màu giữ) → `_lt` + `_state_label(env, state)`; tiêu đề `_('Order report')`; 7 cột XLSX
    `EXPORT_HEADERS` → `_lt`, dịch theo ngôn ngữ người xuất; câu JS ApexCharts (Revenue, Total, %s order(s), %sM/%sK, câu rỗng) →
    khối `_rep_msgs` `data-wj-msg-*` ở cả gốc mobile + PC; số rút gọn theo `decimal_point` ngôn ngữ (payload); "Không xác định" → t-set;
    order(s) in total, product(s); tên template nav → EN.
  - core: 2 constraint (`res.area`, `res.ward`), `_('Wards of %s')`, log `__init__`/`module_split`, manifest → EN; **không bump version**;
    `DEFAULT_BRAND_NAME = 'Ngô Gia'` khai miễn quét (`LITERAL_EXEMPT` trong `vn_hardcode_scan.py`).
  - metabase: placeholder `e.g. Company Metabase BI` (chủ dự án chốt 07/10), vi_VN.po trả "e.g. Ngô Gia Metabase BI".
  - Bump: portal_info_request 19.0.2.0.0 → **19.0.3.0.0**, info_request 19.0.1.0.0 → **19.0.1.1.0**, portal_report 19.0.2.7.0 →
    **19.0.3.0.0**, metabase 19.0.1.0.0 → **19.0.1.0.1**; core giữ 19.0.2.1.1. Không seed `noupdate` tiếng Việt ⇒ không migration.
  - `.po` vi_VN + `.pot` tái sinh 5 module (portal_report có `i18n/` mới); khôi phục 6 msgstr bị glossary chung ghi đè (Representative,
    Submission date, Active ×2, Manager, help người phụ trách khu vực) + thêm "Revenue (" → "Doanh thu ("; `msgfmt -c` sạch.
  - Test: `test_f5_nav_item` report đọc arch vi qua `load_vi` + thêm assert "Reports" ở en; `test_info_request_errors_f1` user vi_VN +
    `load_vi` (không xoá assert). Mới `test_jv8b_i18n.py` ×3: report (bảng VN TRƯỚC phiên 5 nhãn + màu, 7 cột XLSX, tiêu đề,
    `decimal_point`; arch en không chữ Việt; HttpCase vi/en "1 order in total"/"1 đơn hàng", "1 product", 7 `data-wj-msg-*` ×2 gốc,
    file XLSX header + cột trạng thái theo ngôn ngữ), info_request (7 loại, 5 trạng thái + badge = badge tính từ nhãn VN cũ, 7 câu lỗi;
    HttpCase "1 result", nhãn loại/trạng thái, confirm attr, lỗi "Invalid information type." ↔ "Loại thông tin không hợp lệ."), core
    (2 constraint vi qua `_sql_error_to_message`, tiêu đề action phường) — test core chỉ chạy DB trắng.
- Số đo:
  - `vn_hardcode_scan --fail-on-any` 9 module V8a+V8b: **0** (trước 171 cho V8b).
  - `-u info_request,portal_info_request,portal_report,metabase,portal_base,portal_layout --test-enable` trên DB đo `wujia_v8bn`:
    **1014 test, 0 đỏ** (HEAD `wujia_v8bh` 992 / 0; +17 test mới, +5 test metabase vì metabase chỉ cài trên DB đo).
  - Core trên DB trắng `-i wujia_core --test-tags wujia_jv8b,wujia_brand`: **19/19**.
  - Mutation trên snapshot (8 đột biến: đổi câu EN trạng thái/loại, header XLSX không dịch, "Không xác định" về biểu thức, bỏ số ít,
    đổi tên `data-wj-msg-*`, confirm viết cứng, đổi nhãn đổi màu badge) ⇒ **8/8 bị bắt**; bản gốc 22/22 xanh.
  - So vi_VN DB HEAD ↔ mới: 18 chỗ khác = 12 field chung EN → VN + 6 arch view, **0 VN → EN**.
  - `wj_text_probe` vi_VN (thêm 1 yêu cầu nháp cho `anh.owner` ở cả 2 DB đo để có trang chi tiết) 56 trang × 2 lần: chỉ lệch các
    `data-wj-msg-*` mới (báo cáo 7 khoá × 2 gốc; chi tiết yêu cầu "Huỷ yêu cầu này?" = đúng câu `confirm` cũ); chữ hiện ra 0 lệch.
  - Playwright `anh.owner` chỉ-đọc en_US/th_TH × 1440/390 × 4 trang (báo cáo, yêu cầu danh sách/tạo/chi tiết): **16/16 0 tràn,
    0 lỗi JS, 0 HTTP ≥400**. Chữ VN còn lại = dữ liệu + "Khảo sát"/"Xem kết quả đánh giá & khảo sát cửa hàng" (module Thái).
- Lệch / LIMIT: `-u wujia_core` kéo `wujia_franchise_inspection` (Thái) ⇒ 120 dòng ERROR "malformed po … unknown occurrence:
  web_survey_ui" từ `.po` zh/th của module Thái (không do phiên này; báo Thái ở ★VR). Câu core: `_()` có hiệu lực sau restart,
  constraint vi cần lần `-u wujia_core` tự nhiên sau này. zh/th chưa có bản dịch câu mới ⇒ thấy EN (chờ J-T5).
- Bài học: ghi ở `next-session-clusters-J.md` §6 "J-V8b".
- Commit: J-V8a `dbd4335b` + J-V8b `02e363fc`, push cùng phiên.
- Lệnh deploy (J-V8a + J-V8b): `-u wujia_fleet,wujia_delivery,wujia_portal_delivery,wujia_portal_purchase_history,wujia_info_request,`
  `wujia_portal_info_request,wujia_portal_report` (+ `wujia_metabase_connector` nếu UAT có cài) + **restart sau `-u`**; kiểm version
  DB 19.0.1.1.0 / 19.0.1.2.0 / 19.0.4.0.0 / 19.0.4.0.0 / 19.0.1.1.0 / 19.0.3.0.0 / 19.0.3.0.0 (/ 19.0.1.0.1).
- UAT (07/10, `6ef4db78`): 7/8 module DB = code (fleet 19.0.1.1.0, delivery 19.0.1.2.0, portal_delivery / purchase_history
  19.0.4.0.0, info_request 19.0.1.1.0, portal_info_request / portal_report 19.0.3.0.0); `wujia_metabase_connector` lúc đầu chưa
  upgrade (DB 19.0.1.0.0, đĩa 19.0.1.0.1, không module nào phụ thuộc) ⇒ chủ dự án duyệt, upgrade tay qua Apps (`button_immediate_upgrade`)
  ⇒ DB 19.0.1.0.1, 0 module treo, placeholder en "e.g. Company Metabase BI" / vi "e.g. Ngô Gia Metabase BI". Core đã restart ăn
  `.po` mới (tiêu đề phường vi "Phường/Xã thuộc …", en "Wards of …"). XML-RPC `authenticate` trả Access Denied ⇒ đọc qua JSON-RPC
  phiên web (`/web/session/authenticate` + `/web/dataset/call_kw`).
  Playwright `anh.owner` chỉ-đọc (chặn mọi request không phải GET trừ đăng nhập) vi/en/th × 1440/390 × 7 trang (home, lịch sử
  danh sách/chi tiết `/45`, giao hàng, yêu cầu cập nhật danh sách/tạo, báo cáo): **42/42 0 tràn, 0 lỗi JS, 0 HTTP ≥400**, chữ mẫu
  đúng ngôn ngữ ("All statuses"/"Tất cả trạng thái", "— Select type —"/"— Chọn loại —", "Total orders"/"Tổng đơn hàng",
  `data-wj-msg-order` "%s order"/"%s đơn"); chi tiết đơn tạo từ backend en "Ngô Gia (backend)". Chữ VN còn trên trang en = dữ liệu +
  "Tiếng Việt" + 2 mục menu Khảo sát (Thái). XLSX báo cáo: en "Order code … Total amount" + "Draft", vi "Mã đơn … Tổng tiền" + "Nháp".
  Backend: selection info_request vi giữ "Người đại diện"/"Đang xem", en "Representative"/"Being reviewed"; constraint fleet vi
  "Mã đội xe phải duy nhất." ↔ en "Fleet code must be unique.". Ngôn ngữ `anh.owner` trả vi_VN.
  LIMIT: UAT 0 yêu cầu cập nhật thông tin và 3 chuyến giao không thuộc HN-01 ⇒ chi tiết yêu cầu + chi tiết chuyến chưa nhìn bằng trình
  duyệt trên UAT (không tạo dữ liệu thật; đã phủ ở DB đo + HttpCase).
- Dọn: DB `wujia_v8h`/`v8t`/`v8b`/`v8r`/`v8bh`/`v8bn`/`v8bm`/`v8bc` + filestore, worktree scratchpad. Giữ `wujia_t1` tới hết Phần V.
- Phiên kế: **★J-VR** — review Phần V (quét lại = 0 code team, vi_VN 0 lệch chữ/ảnh, ảnh en/th, gửi Thái danh sách chuỗi module Thái
  + lỗi `.po` zh/th `web_survey_ui`).

## ★J-VR Review Phần V (Việt hoá source) · 07/10/2026 · Mac
- Kết quả: ✅ xong — Phần V khép (V0 → ★VR), chapter 79 `chapters/79-sprint65-cluster-j-part-v.tex`, PDF build lại.
- Đã làm:
  - Quét lại: `vn_hardcode_scan` code team **0** / 24 module; Thái 284. msgid vi_VN chưa dịch MỚI so với trước Phần V (`d2966119`):
    83, không chỗ nào người dùng thấy (gallery dev, template chết `signup_form`/`forgot_pass_back`, field backend, metabase).
    Grep viết tắt không dấu bắt 1 chỗ: cột "SL" chi tiết chuyến giao mobile ⇒ "Qty" (vi giữ "SL"), `.po` sinh lại.
  - Bỏ nhánh tra ngược nhãn VN `_legacy_vn_status_labels` trong `status_badge_for`. Rà 8 module gọi: Lịch sử đặt hàng (list +
    chi tiết) và màn "Đặt hàng thành công" mobile còn tô màu từ nhãn ĐÃ DỊCH (vi đúng nhờ nhánh tạm, th/zh sau J-T5 sẽ ra xám) ⇒
    PH dùng `portal_order_badge(order)`, sale dùng helper mới `portal_order_state_badge(state)`. Đáp án màu cũ cho test chuyển vào
    `wujia_portal_base/tests/common.py::legacy_vn_badge` (7 file test đổi đáp án, không xoá assert). Test mới `test_jvr_badge` (sale,
    vi/en cùng màu) + assert "Qty"/"SL" trong `test_jv8_i18n` delivery.
  - Bump: portal_base 19.0.7.37.0 → **19.0.7.37.1**, portal_sale 19.0.5.1.0 → **19.0.5.1.1**, purchase_history 19.0.4.0.0 →
    **19.0.4.0.1**, portal_delivery 19.0.4.0.0 → **19.0.4.0.1**.
  - Danh sách gửi đi `docs/i18n-review/`: `ba-en-terms.csv` (1 361 cặp VN → EN, 10 dòng cần chốt 1 VN ↔ 2 EN), `thai-vn-hardcode.csv`
    (284, 18 có gợi ý EN), `README.md` (+ lỗi `.po` `#: web_survey_ui` + WJ-INSPECT-001). Chưa gửi.
  - Mốc `docs/i18n-baseline/vi_VN.json` cập nhật (54 trang, DB `wujia_vr`).
- Commit: `457ff953` — feat(i18n): ★J-VR review Phần V (đã push, chờ deploy)
- Deploy: ✅ UAT 07/10 (chủ dự án deploy) — lệnh: `-u wujia_portal_base,wujia_portal_sale,wujia_portal_purchase_history,wujia_portal_delivery` + **restart**;
  kiểm version DB 19.0.7.37.1 / 19.0.5.1.1 / 19.0.4.0.1 / 19.0.4.0.1.
- UAT (07/10, `c72ae576`): 4 module DB = code (portal_base 19.0.7.37.1, portal_sale 19.0.5.1.1, purchase_history / portal_delivery
  19.0.4.0.1), 0 module treo ⇒ không cần upgrade tay. JSON-RPC phiên web cần `db: wujia_tea_19` trong `/web/session/authenticate`.
  Playwright `anh.owner` chỉ-đọc vi/en/th × 1440/390 × 24 route = **144 trang: 0 tràn, 0 lỗi JS, 0 HTTP ≥400**. Badge Home + Lịch sử
  (list + chi tiết S00011/S00013) cùng màu ở 3 ngôn ngữ (Đã xác nhận/Confirmed = info, Chờ xác nhận/Awaiting confirmation = pending).
  "Đặt hàng thành công" mobile S00045 (nháp) = pending, S00002 (đã xác nhận) = info ở vi/en/th. Arch chi tiết chuyến giao: vi "SL",
  en/th "Qty". LIMIT: HN-01 không có chuyến giao ⇒ chi tiết chuyến chưa xem bằng trình duyệt (đã kiểm arch + test). Ngôn ngữ
  `anh.owner` trả lại vi_VN.
- Số đo (DB `wujia_vr` = copy `wujia_t1` + `-u` 26 module team):
  - `wj_text_probe` vi_VN 54 trang: 2 lần 0/54 lệch; so mốc trước Phần V chỉ thêm `data-wj-msg-*` + 2 sửa có chủ đích (khung giờ thi V4,
    danh mục hỗ trợ V7).
  - So vi_VN DB `wujia_t1` ↔ `wujia_vr` (field/help/selection/model/menu/action/arch): **0 VN → EN**, arch 0 term VN mất.
  - Playwright chỉ-đọc vi/en/th × 1440/390 × 26 route = **156 trang: 0 tràn, 0 lỗi JS, 0 HTTP ≥400**. Chữ Việt trên en/th = dữ liệu +
    "Tiếng Việt" + 2 menu Khảo sát (Thái).
  - Độ phủ vi_VN (`wujia_i18n`): portal 96,6–100 % (thiếu = PDF/ID/Email/chip "i"); backend L2 41–95 % (field backend tiếng Anh có từ
    trước); th 1,4 %, zh 1,0 % (chờ J-T5).
  - Suite 25 module (trừ core) `--test-enable`: 1 185 test, 2 đỏ ⇒ `e2b` bảng nhãn BA đổi đáp án sang `legacy_vn_badge`; `wujia_i18n`
    `test_scan_reads_db_and_code_terms` đỏ do DB đo có sẵn kết quả quét cũ (120 × 3 ngôn ngữ) — không do code. Chạy lại nhóm liên quan
    (portal_base/exam/debt/return/support/info_request + `wujia_jvr` + `wujia_home_order_status`): **544/0**; delivery 22/0.
  - Mutation trên snapshot: PH về nhãn đã dịch · sale về nhãn đã dịch · khôi phục tra ngược · trả "SL" ⇒ **4/4 bị bắt**.
- Lệch plan / quyết định mới: không so ảnh pixel vi (không có ảnh mốc) — thay bằng probe chữ + Playwright layout; ghi LIMIT.
- Nợ để lại: deploy ★VR; gửi 2 danh sách (BA, Thái) khi chủ dự án duyệt; backend L2 thiếu bản vi (có từ trước); xoá template chết
  layout; DB `wujia_t1` + `wujia_vr` còn giữ (chờ chủ dự án cho xoá).
- Bài học: `next-session-clusters-J.md` §6 "★J-VR".
- Phiên kế: **J-T4** — nhập/xuất CSV kiểu Thái + zip `.po`/`.pot` (`wujia_i18n`, scripts).

## J-T4 Nhập/xuất bản dịch (CSV kiểu Thái + zip `.po`/`.pot`) · 07/10/2026 · Mac
- Kết quả: ✅ xong — `wujia_i18n` 19.0.1.1.0 → **19.0.1.2.0**. Chưa commit/push/deploy.
- Chủ dự án chốt trong phiên: (1) nhập CSV **giữ bản sửa tay** (ô tick riêng để đè); (2) thêm CLI `scripts/i18n_tool.py`;
  (3) dòng chỉ khớp theo câu nguồn (không ref / ref cũ) **chỉ điền chỗ chưa dịch** — đo thử chế độ "đè hết" làm đổi 90 (glossary)
  + 162 (file Thái) bản vi_VN đã chốt ở Phần V.
- Đã làm:
  - `wujia_i18n/tools/po_writer.py` (babel + csv, không import odoo): chuyển nguyên `load_glossary`/`existing_msgstr`/`build_po`/
    `translate_markup`/`msgfmt_ok` từ `scripts/sync_translations.py` + thêm `fill_po`, `read_glossary_rows` (nhận `key,option,VN,CN,TH`
    lẫn `key,VN,CN,TH`, ô = key bỏ qua), `write_glossary_csv`, `parse_option`/`format_option`. `sync_translations.py` nạp lại file này
    theo đường dẫn — dry-run 3 module trước/sau **15/15 file giống hệt** (trừ dòng ngày giờ).
  - AbstractModel `wujia.i18n.transfer`: `_wj_import_csv` (khớp ref → câu nguồn; giống ⇒ bỏ qua; khác ⇒ override + áp ngay nhãn/menu/
    view; chuỗi code chờ xuất), `_wj_export_csv` (định dạng Thái), `_wj_export_po_zip` (`.pot` từ `trans_export(None)` + `.po` babel;
    msgstr = sửa tay > bản đang chạy > `.po` source; xung đột cùng msgid ghi README trong zip; xuất xong hết "chờ").
  - Wizard `wujia.i18n.transfer.wizard` + menu Import / Export + nút "Export .po for code strings" trên list Translations; help
    `pending` sửa theo đường mới. ACL nhóm translator.
  - `scripts/i18n_tool.py` `import-csv | export-csv | export-po [--write-source]` qua `odoo-bin shell`; `--write-source` từ chối module Thái.
    Hướng dẫn: `scripts/qa/README.md` §Bản dịch — nhập/xuất.
  - Glossary +34 dòng (chỉ nối thêm); `vi_VN.po` + `.pot` `wujia_i18n` sinh lại: 0 bản cũ đổi, 34 câu mới có bản vi, `msgfmt -c` sạch.
  - Test cũ `test_scan_reads_db_and_code_terms` đếm theo đúng ngôn ngữ vừa quét (hết đỏ giả trên DB đã từng quét; giữ assert).
- Số đo (DB `wujia_t4` = copy `wujia_vr`):
  - Suite `/wujia_i18n` **28/0** (trước 15 test, 1 đỏ giả); DB trắng `-i wujia_i18n` **28/0**. Mutation trên snapshot 6/6 bị bắt đúng test
    (bỏ ưu tiên sửa tay · ô = key thành bản dịch · đè sửa tay khi không tick · `.pot` có msgstr · không bỏ "chờ" sau xuất · khớp câu
    nguồn đè bản đã dịch). `vn_hardcode_scan --module wujia_i18n --fail-on-any` = 0.
  - Nhập thật (mặc định): `docs/i18n-glossary.csv` 2 195 dòng → 1 469 khớp câu nguồn, 726 không thấy, 675 bản đổi (633 áp ngay, 42 code
    chờ), giữ 103 bản đã dịch, **0,2 s**; file Thái 1 280 dòng → 225 khớp ref, 894 khớp câu nguồn, 161 không thấy, 1 939 bản đổi, giữ 164,
    **0,3 s** (đo rồi rollback, DB đo không giữ).
  - Xuất `.po` module chưa sửa trùng repo: exam `.pot`/`vi_VN.po` 0 dòng khác; core `vi_VN.po` thêm 3 bản dịch DB đang có.
  - Nghiệm thu §5 T4 (zh_CN): sửa QWeb `wujia_portal_exam.layout_sidenav_exam` "Exam registration" + nhãn `wujia.exam.course.active` +
    `_()` "Monday" (portal_exam) + JS "Unsaved changes" (web — team không còn chuỗi `_t`) ⇒ Áp dụng: QWeb + nhãn đổi ngay; xuất zip qua
    CLI 9,5 s → giải vào bản copy module ở scratchpad → `-u` + restart ⇒ `_()` "ZH-T4 PY", JS "ZH-T4 JS" (`/web/webclient/translations`),
    QWeb + nhãn vẫn còn sau `-u`; vi "Thứ 2" không đổi; JSON-RPC chỉ-đọc `fields_get` lang zh_CN = "ZH-T4 LABEL".
- Lệch / LIMIT: chưa nhìn wizard bằng trình duyệt (view nạp sạch khi `-i`/`-u`, wizard chạy qua test). File glossary Thái cũ: 773/1 004 ref
  trỏ `wujia_franchise.*` đã sang `wujia_franchise_inspection` ⇒ rơi xuống khớp câu nguồn. Xuất `.po` module lõi (`web`) lệch nhẹ
  (3 bản theo DB) ⇒ chỉ commit zip module team.
- Bài học: `next-session-clusters-J.md` §6 "J-T4".
- Commit: `ca198ace` — feat(i18n): J-T4 nhập/xuất bản dịch CSV + zip .po/.pot (đã lên UAT 07/10 cùng J-T5)
- Lệnh deploy đề xuất: `-u wujia_i18n` + restart; kiểm version DB 19.0.1.2.0; menu Translation Tool có Import / Export.
- Dọn: đã xoá DB `wujia_t4`, `wujia_t4b` + filestore; giữ `wujia_t1`/`wujia_vr` chờ chủ dự án.
- Phiên kế: **J-T5** — dịch tự động (DeepL), xem §6b; dịch máy chỉ điền chỗ trống, không đè bản sửa tay.

## J-T5 Dịch tự động (DeepL) trong tool Bản dịch · 07/10/2026 · Mac
- Kết quả: ✅ xong — `wujia_i18n` 19.0.1.2.0 → **19.0.1.3.0**. Chưa commit/push/deploy.
- Chủ dự án chốt đầu phiên: (1) **chưa có key DeepL** ⇒ code đủ + test giả lập HTTP, tạo key sau; (2) **áp ngay, rà sau**;
  (3) **bảng thuật ngữ trong tool**; (4) mặc định module team, wizard cho tick thêm module Thái (chỉ ghi DB tool).
- Đã làm:
  - `tools/mt_deepl.py` (không import odoo): `DeepLClient` (key `:fx` ⇒ api-free; ngôn ngữ đích + cặp glossary hỏi động từ
    `/v2/languages`, `/v2/glossary-language-pairs`; lỗi ⇒ `MTError` auth/quota/rate/other) + `PROVIDERS` chừa provider khác;
    `protect`/`restore`/`check`: placeholder `%s %(x)s {x} {{x}} ${x}`, entity, thuật ngữ giữ nguyên ⇒ thẻ `<x i="n"/>`
    (`tag_handling=xml`), chuỗi không phải HTML escape XML, khoảng trắng đầu/cuối tách riêng; mất placeholder/thẻ ⇒ loại.
  - State mới **`machine`** (Dịch máy): quét lại không đè, áp lại sau `-u`, nhập CSV của người được đè, xuất `.po` lấy
    sửa tay > máy > bản đang chạy; nút **Mark reviewed** (⇒ `override`); sửa tay ⇒ `override` như cũ. Field `mt_queued`, `mt_error`.
  - `models/i18n_mt.py`: `_wj_mt_enqueue` + cron `_wj_mt_run_queue` (lô 50 câu / 30k ký tự, `_commit_progress` trong cron, đọc lại
    state trước khi ghi ⇒ người sửa giữa chừng thắng, nhãn/menu/view `_wj_apply` ngay, chuỗi code ⇒ "chờ xuất .po");
    hết hạn mức / key sai ⇒ dừng giữ hàng đợi + lưu lỗi; DeepL bận ⇒ hẹn lại 1 phút. Câu nguồn còn chữ Việt (module Thái) ⇒ không
    gửi `source_lang`/glossary, DeepL tự nhận.
  - `wujia.i18n.glossary` (EN → bản dịch theo ngôn ngữ / "Giữ nguyên"; seed "Ngô Gia", "Wujia") ⇒ DeepL glossary tạo lại khi nội
    dung đổi (id lưu `ir.config_parameter`), cặp không hỗ trợ ⇒ thay thẳng bản đã chốt.
  - Wizard **Machine translate** (ước số chuỗi/ký tự, cảnh báo thiếu key / ngôn ngữ DeepL không hỗ trợ / ngôn ngữ chưa bật ⇒
    tự bật + quét; nút kiểm hạn mức) · menu Glossary + Settings · Settings app "Translation Tool" (provider + khoá, chỉ admin) ·
    độ phủ thêm cột "Dịch máy" + "% đã duyệt" · filter Machine translated / In queue / Error.
  - Quyền chỉ-đọc `ir.module.module` cho nhóm Translator (người dịch không phải admin trước đây lỗi quyền ở ô Module của mọi wizard).
  - Glossary +56 dòng VN (chỉ nối thêm); `vi_VN.po` + `.pot` sinh lại: **0 bản cũ đổi**, 58 câu mới (2 câu = chính nó: "DeepL",
    "DeepL: %s"), `msgfmt -c` sạch. `vn_hardcode_scan` miễn 2 chỗ (thuật ngữ "Ngô Gia", bảng chữ nhận diện tiếng Việt) ⇒ 0.
- Số đo:
  - Suite `/wujia_i18n` **55/0** trên DB trắng `-i` và DB copy `wujia_vr` `-u` (28 cũ + 27 mới). Mutation trên snapshot **8/8** bị bắt
    (bỏ kiểm placeholder · không đọc lại override · quét đè machine · không áp DB kind · reapply bỏ machine · bỏ glossary_id ·
    refresh lấy cả override · nhập CSV không đè machine) — 3 đột biến sống ở lượt đầu do test lỏng, đã siết.
  - Smoke DeepL giả lập (trễ 0,3 s/request) trên DB copy: th_TH × 26 module team (0 module Thái) = **4 174 chuỗi / ~105 000 ký tự**
    (≈ 21 % hạn mức Free/tháng), 85 request, 30,3 s (25,5 s là trễ giả lập), 0 lỗi, 452 chuỗi code chờ xuất `.po`.
  - Trình duyệt (DB nháp): portal `/portal/set-lang/th_TH` ⇒ Home 45 + Order 32 chỗ chữ dịch máy hiện **ngay không restart**;
    backend th wizard dịch máy hiện chữ máy; màn wizard / Settings / Bản dịch / Độ phủ (vi) đúng, 0 lỗi JS.
- Lệch / LIMIT: chưa gọi DeepL thật (chưa có key) — chất lượng dịch, thẻ QWeb phức tạp, cặp glossary EN→th thật cần smoke khi có
  key. Fallback thuật ngữ cho cặp không có glossary là thay chữ thô (ngữ pháp có thể gượng). "Khảo sát" (module Thái) vẫn tiếng Việt
  trên portal th — đúng phạm vi mặc định. Chuỗi code dịch máy chỉ có hiệu lực sau xuất `.po` + commit + restart (đường J-T4).
- Bài học: `next-session-clusters-J.md` §6 "J-T5".
- Commit: `78a68ea5` — feat(i18n): J-T5 dịch tự động DeepL (đã lên UAT 07/10: wujia_i18n 19.0.1.3.0, kiểm chỉ-đọc qua JSON-RPC — menu, cron, glossary seed, field, view, ACL đủ)
- Lệnh deploy đề xuất: `-u wujia_i18n` + restart; kiểm version 19.0.1.3.0, menu Translation Tool có Machine translate / Glossary /
  Settings, cron "Translation Tool: machine translation queue" active. Có key ⇒ Settings → wizard th_TH 1 module nhỏ → rà.
- Dọn: đã xoá DB `wujia_t5`, `wujia_t5t` + filestore; giữ `wujia_t1`/`wujia_vr`.
- Phiên kế: **J-O0** nếu BA đã trả lời câu hỏi Vận hành; chưa thì Issue List cụm I (I1 #155). Khi có key DeepL: 1 phiên ngắn smoke thật.

## J-T5b Smoke DeepL thật trên UAT (trình duyệt) · 07/10/2026 · Mac
- Kết quả: ✅ dịch máy chạy thật — key DeepL (gói Free) chủ dự án đã nhập ở UAT; không sửa code, không commit.
- Đã làm (Playwright Chromium có giao diện, chỉ đọc + 1 lần bấm "Kiểm tra hạn mức"):
  - Wizard Dịch máy: Thai + `wujia_portal_exam` ⇒ 0 chuỗi còn thiếu; hạn mức 67 293 / 1 000 000 ký tự (chủ dự án đã chạy dịch
    trước đó, cron OdooBot 16:52). Không bấm Dịch lại.
  - JSON-RPC chỉ-đọc: th_TH machine 1 774 (13 module portal) · zh_CN machine 1 850 · hàng đợi 0 · lỗi 2 (zh exam QWeb "HTML tags
    changed", th sale `On %s` "empty translation" — bộ kiểm chặn đúng). Placeholder `{name}` `{limit}` `{brand}` giữ nguyên.
    th machine: model_terms 1 496 + model 2 đã áp; code_python **276 chờ xuất `.po`**.
  - Portal `anh.owner` th_TH × 1440/390 × 6 route (Home, Exam, Đăng ký thi, Đặt hàng, Hỗ trợ, Thông báo): HTTP 200, 0 tràn, 0 lỗi
    JS, chữ Thái hiện ngay không restart. Còn tiếng Anh = chuỗi `_()` (nhãn trạng thái, "Store owner", "Month 10 2026", "Mo") chờ
    `.po`; chữ Việt = dữ liệu + "Ngô Gia" (giữ nguyên theo glossary) + menu Khảo sát (Thái). User trả về vi_VN.
  - Cùng 6 route × 1440/390 ở en_US và vi_VN: 0 tràn, 0 lỗi JS. en: chữ Việt chỉ còn dữ liệu (tên cửa hàng/SP/thông báo) +
    "Khảo sát" (Thái); vi: tiếng Anh chỉ còn tên SP "Matcha Latte size M", "Topping". Ghi chú ngoài i18n: giá portal hiện "$"
    ở CẢ vi lẫn en (tiền tệ bảng giá dữ liệu UAT, không phải dịch); cột "Thành tiền" giỏ PC bị cắt mép ở cả 2 ngôn ngữ.
- Phiên kế: xuất `.po` th/zh (nút "Export .po for code strings") → commit → `-u` + restart nếu chủ dự án muốn chuỗi `_()` ra Thái/Trung;
  sửa tay 2 câu lỗi. Sau đó Issue List cụm I (I1 #155).

## END-SPRINT 66 — chốt sổ cụm J (B + T + V) + plan Issue List cụm I mở rộng · 07/10/2026 · Mac
- Kết quả: ✅ chapter 80 + PDF + docs; **0 dòng code**, 0 ghi sheet, không deploy.
- Đầu phiên: `git pull` (up to date). `issue_queue --dev` = 15 Ready for Dev; reconcile `git log -S` + `custom/` + ledger: 0 issue đã fix.
  Kiểm chỉ-đọc UAT (XML-RPC): `wujia_core` 19.0.2.1.1 · `portal_layout` 19.0.60.4.0 · `portal_base` 19.0.7.37.1 · `portal_sale` 19.0.5.1.1 ·
  `wujia_i18n` 19.0.1.3.0 — khớp repo ⇒ J-B, J-T, J-V và top bar 992 (I0) đều đã lên UAT.
- Chủ dự án chốt: **Phần O pend theo ý BA**; sang Issue List cụm I + cụm H + 10 issue mới; chapter 80 riêng cho B + T; **#62 Dev nhận**.
- Đã làm:
  - `chapters/80-sprint66-cluster-j-branding-i18n-tool.tex` + `\include` master; `build-doc.sh` rc=0 (PDF chương 79, tr. 328–330).
  - Phân cụm 10 issue mới, gộp vào cụm I: I1 #155 → I2 #156 → I3 #154 → I4a #152 → I4b #152+#157 → I5 #153 → I6 #159 →
    I7 #62+#163 → I8 #160+#162+#166 → I9 #167+#164 → I10 #168+H2 → ★IR. Prompt từng phiên + bảng §1.D: `next-session-clusters-H.md`.
  - Compact summary (tiêu đề, §4 dòng 66, §5 State, §13 bảng cụm I mở rộng) · `pending-backlog.md` §1/§2/§3 · `next-session-clusters-J.md` (O ⏸).
- Lệch / LIMIT: BA dùng lại ID `WJ-EXAM-001` (#157) và `WJ-NOTI-001` (#159) — ledger có entry 08/2026 cùng key ⇒ phiên I4b/I6 thay entry
  và kiểm `qa_sync --dry-run`. #164 WJ-INSPECT-001 có thể nằm trong module anh Thái ⇒ I9 chỉ bàn giao nếu gốc ở đó.
- Nợ để lại: xuất `.po` th/zh chuỗi code (276 th) + sửa 2 câu máy lỗi · gửi `docs/i18n-review/` cho BA/Thái · câu hỏi Vận hành chờ BA.
- Phiên kế: **I1 #155 WJ-ORD-031** — danh mục Portal bắt buộc khi công khai SP (`next-session-clusters-H.md` §3 Prompt I1).

## I1 #155 WJ-ORD-031 — danh mục Portal bắt buộc khi công khai SP · 08/10/2026 · Mac
- Kết quả: ✅ code + test + đo; commit `0b5834d2` **đã push**, chưa deploy; sheet chưa ghi (dry-run đúng 1 dòng) — chủ dự án deploy + test browser rồi mới ghi.
- Đầu phiên: `git pull` up to date. `issue_queue --dev` = 17 (15 cụm I + **2 mới chưa phân cụm: #169 WJ-PORTAL-UI-005, #170 WJ-PORTAL-UI-006**).
  Reconcile WJ-ORD-031: chỉ commit docs, `custom/` 0, ledger 0.
- Chủ dự án chốt: SP thiếu danh mục **đang trong giỏ** ⇒ như SP bị tắt (`PRODUCT_NOT_AVAILABLE` trên dòng, chặn gửi, không xoá giỏ);
  danh mục **lưu trữ** ⇒ không hợp lệ, chỉ ẩn, không chặn lưu trữ.
- Đã làm:
  - `wujia_sale` 19.0.4.8.0: `_portal_orderable_domain()` + `_portal_is_orderable()` (một nguồn) · constraint riêng `_check_portal_category`
    (tách khỏi `_check_portal_qty_rules` để sửa min_qty SP cũ vẫn lưu được) · form `required="is_public_portal"` · vi_VN.po/.pot.
  - `wujia_portal_sale` 19.0.5.2.0: catalog, `_read_group` chip, chi tiết, related, `cart/add`, `_portal_invalid_reason` gọi helper.
  - Test: `wujia_sale/tests/test_portal_category.py` (4) + 2 ca trong `test_f6_cart_submit.py`; fixture SP công khai thêm danh mục.
- Kiểm: DB copy `wujia_i1` (từ `wujia_vr`, phải `-u wujia_i18n` trước — copy còn trước J-T4/T5) · `-u wujia_sale,wujia_portal_sale --test-tags`
  **85/85**, RC=0 · mutation bỏ điều kiện danh mục ⇒ 5 FAIL + 1 ERROR · Playwright 1920/391: Tất cả 55 = Σ chip 51+2+2 (trước sửa 61),
  6 SP thiếu danh mục không ở list/tìm, chi tiết redirect `PRODUCT_NOT_AVAILABLE`, `cart/add` trả `PRODUCT_NOT_AVAILABLE`;
  regression `/portal`, giỏ, chi tiết, lịch sử × 2 viewport: 200, tràn 0, 0 JS. Harness: scratchpad `i1_measure.py`.
- UAT chỉ-đọc: 2/5 SP công khai thiếu danh mục — **TS-HONG, TS-MAT**, nằm trong giỏ **HN-01** + **HCM-01** ⇒ ghi LIMIT, BA gắn danh mục khi deploy.
- Bài học: `qa_sync.py` mặc định là dry-run (không có cờ `--dry-run`), chạy bằng env `odoo19` (env `odoo` thiếu yaml).
- Nợ: chủ dự án deploy `-u wujia_sale,wujia_portal_sale` + test browser ⇒ sửa `build_override` ledger (ĐÃ DEPLOY) → `qa_sync --only WJ-ORD-031 --apply` → verify `export?format=csv`.
  Xoá DB nháp `wujia_i1` + `data/filestore/wujia_i1` khi xong.
- Phiên kế: **I2 #156 WJ-RETURN-001** (`next-session-clusters-H.md` §3 Prompt I2); phân cụm #169/#170.


## I2 #156 WJ-RETURN-001 — hạn đổi trả từ giao hoàn tất + bỏ Lưu nháp · 08/10/2026 · Mac
- Kết quả: ✅ code + test + đo; commit `8da0a983` **đã push**, chưa deploy; sheet chưa ghi (dry-run đúng 1 dòng). Chủ dự án: review test dồn một lần sau khi xong hết cụm I.
- Đầu phiên: `git pull` (về `muk_mcp` của anh Thái, không đụng return). `issue_queue --dev` = 22: cụm I + **chưa phân cụm #142
  UI-PC-HOME-REDESIGN-001, #169, #170, #171 WJ-HOME-001**. Reconcile WJ-RETURN-001: chỉ commit docs, `custom/` 0, ledger 0.
- Dữ liệu thật (chỉ-đọc): UAT 15 đơn `sale`, **0 đơn validate phiếu xuất**; S00035 (HCM-01) chuyến `done` nhưng phiếu chưa validate.
  `wujia_vr`: 1 đơn 2 phiếu xuất, 1 phiếu huỷ, 0 backorder ⇒ luật dựng theo Odoo + test tự tạo ca.
- Chủ dự án chốt: mốc = **phiếu xuất validate** (không dùng trạng thái chuyến giao).
- Đã làm:
  - `wujia_return` 19.0.2.1.0: `sale.order.wj_delivery_done_date` (store, index) = max `date_done` outgoing khi mọi outgoing done/cancel, ≥1 done.
    `_portal_scope_order_domain` + `_portal_eligible_order_domain` (theo mốc) + `_portal_check_order_window` (2 câu lý do);
    `_portal_prepare_vals` trả `vals`; `create_from_portal` luôn `action_submit`; `_portal_check_evidence` bỏ `require_min`.
  - `wujia_portal_return` 19.0.5.1.0: bỏ nút Lưu nháp PC; option đơn "— giao xong dd/mm/yyyy" PC + mobile; sắp theo mốc.
  - vi_VN.po + `.pot` 2 module (`.pot` sinh bằng `odoo-bin i18n export -o`).
  - Test: fixture `_deliver()`; ca 3 GIVEN + backorder chờ/xong, backorder huỷ, huỷ toàn bộ, phiếu trả incoming; POST thẳng `action=draft`,
    đơn chưa giao / quá hạn; form không còn `value="draft"`; snapshot `test_jv6_i18n` thay câu cũ.
- Kiểm: DB `wujia_i2` (copy `wujia_i1`) `-u wujia_return,wujia_portal_return --test-tags` **106/106**, RC=0 · mutation **5/5** đỏ (max→min ·
  bỏ điều kiện mọi phiếu · quay lại `date_order` · để lọt draft · bỏ chặn quá hạn) · Playwright 1920/391 `/portal/return/new`: chỉ "Gửi yêu cầu",
  option = S00012 (đặt 05/09, giao 06/10), không có đơn chưa giao / giao 26/09; gửi thật ⇒ Đã gửi; POST thẳng bị chặn đúng câu, `action=draft` ⇒
  `submitted`; 2 phiếu Nháp cũ còn. Regression `/portal`, `/portal/return`, `/portal/purchase-history` × 2: 200, tràn 0, 0 JS. `check_layers` 0 mới.
  Đối chiếu "Kết quả mong muốn" 7/7 Pass. Harness: scratchpad `i2_measure.py`, `i2_regr.py`, `i2_mutate.py`.
- Bài học: Odoo đọc `.po` code **merge với `.pot`** ⇒ câu chưa có trong `.pot` bị bỏ (test ra tiếng Anh). DB copy chạy HttpCase cần
  `--db-filter='^<db>$'` (config dbfilter chặn ⇒ 404 hàng loạt). Log thật ở `<logfile dir>/<năm>/<tháng>/<ngày>.log` (wujia_core dời log).
- Nợ: chủ dự án deploy `-u wujia_return,wujia_portal_return` + test browser ⇒ sửa `build_override`
  → `qa_sync --only WJ-RETURN-001 --apply` → verify CSV. Báo BA: kho phải validate phiếu xuất thì form đổi trả mới có đơn. Xoá DB `wujia_i1`, `wujia_i2`
  + filestore khi xong.
- Phiên kế: **I3 #154 WJ-ORD-030** (schema M2M); phân cụm #142/#169/#170/#171.

## I3 #154 WJ-ORD-030 — khung giờ nhiều khu vực + múi giờ cửa hàng · 08/10/2026 · Mac
- Kết quả: ✅ code + test + đo; commit `2984550a` **đã push**, chưa deploy; sheet chưa ghi (dry-run đúng 1 dòng).
- Đầu phiên: `git pull` up to date. `issue_queue --dev` = 22 (cụm I + chưa phân cụm #142, #169, #170, #171). Reconcile WJ-ORD-030:
  chỉ commit docs, `custom/` 0, ledger 0. Issue BA (01–02/10) rộng hơn prompt I3: thêm **múi giờ IANA theo cửa hàng**, chặn khu vực rỗng,
  chặn cấu hình trùng, banner hiện tên múi giờ thay `UTC+7`.
- Dữ liệu UAT (chỉ-đọc): 1 window active (HCM) + 1 lưu trữ "TEST DUPLICATE OP-05"; cấu hình chung đã lưu 10:00→04:00; partner tz trống 3/4 cửa hàng.
- Chủ dự án chốt: tz = `partner_id.tz` · migration điền Asia/Ho_Chi_Minh cho cửa hàng trống · trùng = cùng giờ + chung ≥1 khu vực ⇒ chặn.
- Đã làm:
  - `wujia_order_window` 19.0.2.0.0: `area_ids` M2M + constraint rỗng/trùng; `tz` related trên `wujia.franchise.management` + xpath form cửa hàng;
    `_is_within_order_window(franchise)` / `_next_order_window(franchise)` theo `_utc_now()` → tz cửa hàng; `sale.order.create` chặn thiếu tz;
    `migrations/19.0.2.0.0/post-migrate.py` chép `area_id` (assert đếm) + điền tz; views, `.pot`/vi_VN.po.
  - `wujia_portal_sale` 19.0.5.3.0: giỏ `STORE_TZ_NOT_CONFIGURED`; context/nhãn theo `tz_label`; warnbar PC/mobile cùng đọc `order_window_open` +
    `order_window_tz_missing`; bỏ alert PC theo cờ `configured` (gốc lệch PC↔mobile đo 02/10).
  - `wujia_portal_base` 19.0.7.38.0: Home state `tz_missing`, nhãn múi giờ, "mở lại" = window kế; guard `hasattr` cả `_next_order_window`.
  - Test: viết lại `test_order_window.py` (HCM/Tokyo, tz user, DST New York, thiếu tz, A+B, OR, trùng, migration); 2 HttpCase trong
    `test_f6_cart_submit.py` (banner = submit theo giờ Tokyo; thiếu tz); sửa `test_g3a_home_pc`, `test_fra3_layer_guard`, `test_jv4_i18n`,
    `test_split_ownership`; `test_scan_e6_button` 5→4 nút form đổi trả (sót từ I2).
- Kiểm: DB `wujia_i3` (copy `wujia_i2`, dựng 3 window kiểu UAT) `-u` RC=0, migration 3/3 + 4 partner tz, cột `area_id` đã drop ·
  `--test-tags` 4 module **429/429** · lân cận purchase_history/return/delivery/report 51/51 · mutation **5/5** đỏ (bỏ OR · tz user · bỏ chặn thiếu tz ·
  bỏ copy migration · bỏ chặn trùng) · Playwright 4 kịch bản × 1920/391 (`i3_measure.py`): Home = Đặt hàng = Giỏ = submit, 0 tràn, 0 JS ·
  XML-RPC: view list/form/search có `area_ids`, form cửa hàng có `tz`, tạo trùng bị chặn · `check_layers` 0 mới. "Kết quả mong muốn" 9/9 Pass.
- Bài học: M2M `required=True` ORM không kiểm, `@api.constrains` chỉ chạy với field có trong vals ⇒ gắn kiểm rỗng vào constraint của trường giờ
  (luôn có default). Chạy test không `-u` vẫn vấp import `wujia_franchise` tests. `qa_sync` phải gọi bằng python env `odoo19` (python3 hệ thiếu yaml).
- Bàn giao Thái: `wujia_mobile_sale/tests` tạo đơn portal cho cửa hàng không tz ⇒ sẽ đỏ (đề xuất thêm `'tz'` cho partner trong fixture).
- Nợ: chủ dự án deploy `-u wujia_order_window,wujia_portal_sale,wujia_portal_base` + test browser ⇒ sửa `build_override` →
  `qa_sync --only WJ-ORD-030 --apply` → verify CSV. BA rà múi giờ từng cửa hàng. Xoá DB `wujia_i1`, `wujia_i2`, `wujia_i3` + filestore khi xong.
- Phiên kế: **I4a #152 WJ-PORTAL-SCOPE-001** (fork helper dùng chung với Khảo sát); phân cụm #142/#169/#170/#171.

## I4a #152 WJ-PORTAL-SCOPE-001 — helper scope một nguồn + Home · Giao hàng · Báo cáo · 08/10/2026 · Mac
- Kết quả: ✅ code + test + đo; commit `58fcc113` (đã push, đầu phiên I4b); sheet/ledger ghi chung với I4b.
- Đầu phiên: `git pull` up to date. `issue_queue --dev` = 22 (cụm I + chưa phân cụm #142, #169, #170, #171). Reconcile WJ-PORTAL-SCOPE-001:
  chỉ commit docs, `custom/` 0, ledger 0.
- Chủ dự án chốt: (a) **helper mới**, helper cũ giữ nguyên cho nhóm Khảo sát + bàn giao; chưa chọn ⇒ **khối nhắc chọn** (không hiện số 0).
- Đã làm:
  - `wujia_portal_base` 19.0.7.39.0: `get_current_store_ids()` · `get_store_scope_state()` · `get_active_franchise_id()` xoá cookie cửa hàng không còn
    quyền · `get_active_franchise_ids_filter()` DEPRECATED · Home dùng helper mới, `must_pick` theo lựa chọn đã validate (cookie chết từng che modal) ·
    template một nguồn `wj_store_scope_prompt` (`views/store_scope_prompt.xml`) thay 2 alert Home PC/mobile.
  - `wujia_portal_delivery` 19.0.4.1.0: list/results/detail/ics dùng helper mới; 2 khối "chưa có cửa hàng" PC/mobile → prompt chung.
  - `wujia_portal_report` 19.0.3.1.0: orders/export dùng helper mới; chưa chọn ⇒ trang + prompt (không lọc/KPI/biểu đồ), export ⇒ về trang báo cáo;
    không cửa hàng nào ⇒ về Home như cũ; role check giữ nguyên (I5).
  - i18n: `.pot` base + delivery sinh lại; vi_VN 4 câu prompt; xoá 2 câu chết ở delivery.
  - Test: `test_i4a_store_scope.py` (base, 7) · `test_i4a_delivery_scope.py` (5) · `test_i4a_report_scope.py` (6) — tag `wujia_scope_i4a`.
  - Docs: `docs/i4-scope-callers.md` (bảng route → helper → hành vi, dùng cho I4b) · `docs/handover-inspection-scope.md`.
- Kiểm: DB `wujia_i4` (copy `wujia_i3`) `-u` 3 module `--test-tags` **379/379** · hồi quy purchase_history/debt/exam/return/sale/notification **332/332** ·
  mutation **5/5** đỏ (helper trả mọi cửa hàng · bỏ xoá cookie · scope luôn ok · export không chặn · chi tiết chuyến không lọc) ·
  Playwright admin 3 cửa hàng × 6 route × 1920/391 (`i4a_measure.py`, `i4a_prompt_shot.py`): chưa chọn ⇒ prompt + modal ở Home/Giao hàng/Báo cáo,
  nút mở lại modal; HN-01 vs HN-02 mã đơn không giao nhau, KPI Đơn hàng 4/0 khớp SQL; 0 tràn, 0 JS · `check_layers` 0 mới (2 R7 cũ của `wujia_franchise`).
- Đối chiếu "Kết quả mong muốn" phần I4a: Home/Giao hàng/Báo cáo chưa chọn · chọn A · đổi B · sửa ID · export · tự chọn 1 cửa hàng · xoá lựa chọn cũ ·
  regression — Pass. Còn: Đổi trả · YC cập nhật (I4b) · Khảo sát (bàn giao) · ID tệp đính kèm (`utils.py:399`, I4b).
- Ghi nhận ngoài phạm vi: chuông top bar vẫn đếm 42 khi chưa chọn cửa hàng (I4b Thông báo / I6).
- Nợ: commit (chờ chủ dự án) · deploy `-u wujia_portal_base,wujia_portal_delivery,wujia_portal_report` · xoá DB `wujia_i1`…`wujia_i4` + filestore khi xong.
- Phiên kế: **I4b #152 + #157 WJ-EXAM-001** (`next-session-clusters-H.md` §3 Prompt I4b) — dùng `get_current_store_ids()` + `wj_store_scope_prompt`.

## I4b #152 WJ-PORTAL-SCOPE-001 (màn còn lại) + #157 WJ-EXAM-001 · 08/10/2026 · Mac
- Kết quả: ✅ code + test + đo + ledger; commit `907035bf` (đã push); sheet chưa ghi (`--apply` sau deploy).
- Chủ dự án chốt: Hỗ trợ = **người tạo + cửa hàng đang chọn** · Thông báo chưa chọn = **chỉ toàn hệ + khối nhắc chọn** · commit I4a riêng trước (`58fcc113`).
- Đã làm:
  - `wujia_portal_return` 19.0.5.2.0: 5 chỗ → `get_current_store_ids()`; list chưa chọn ⇒ prompt chung (PC + mobile), bỏ notice `no_store`.
  - `wujia_portal_info_request` 19.0.3.1.0: list/new/detail/cancel/AJAX values theo cửa hàng đang chọn; **route tệp mới**
    `/portal/info-request/<id>/attachment/<att>` thay `/web/content` (ir.rule cho mọi cửa hàng của user).
  - `wujia_support` 19.0.1.2.0 `_portal_scope_domain(user, franchise_ids)` + `wujia_portal_support` 19.0.5.1.0 (list/new/detail/reply/tệp).
  - `wujia_portal_notification` 19.0.4.1.0: 8 chỗ → helper mới; `_portal_history_domain(())` sẵn chỉ toàn hệ ⇒ không đổi L2; prompt trên list.
  - `wujia_portal_base` 19.0.7.40.0: `utils.check_attachment_access` (0 lời gọi) theo cửa hàng đang chọn; test badge 11→13 call site exam.
  - #157: `wujia_exam` 19.0.1.2.0 `PORTAL_STATE_LABELS` + `_portal_has_result()`; `wujia_portal_exam` 19.0.7.2.0 một map `REG_STATES`
    (bỏ `M_REG_BADGE`/`PC_REG_STATES`), chip "Có kết quả" riêng (list + detail mobile), chưa chọn ⇒ prompt.
  - i18n: `.pot` exam/portal_exam/info_request/return sinh lại; vi "Chờ xác nhận"/"Đã đăng ký"; xoá 8 câu chết.
  - Test tag `wujia_scope_i4b`: return 6 · info_request 6 · support · notification · exam 4; sửa `test_support`, `test_jv3_i18n`, `test_scan_e2b_status_badge`.
  - Docs: `i4-scope-callers.md` (I4b ✅, sau I4b chỉ Khảo sát còn helper cũ) · `handover-inspection-scope.md`.
  - Dev tool: `qa_sync.py` nhận `stt:` trong entry ledger (BA dùng lại ID — `WJ-EXAM-001` #157, sắp tới `WJ-NOTI-001` #159).
- Kiểm: DB `wujia_i4b` `-u` 8 module `--test-tags` 563 (4 đỏ do test, đã sửa) → lượt 2 exam/info_request/base + hồi quy purchase_history ·
  debt · delivery · report · sale · knowledge **652/652**, RC=0 · mutation **6/6** đỏ (return gộp · support bỏ lọc store · notification gộp ·
  exam đè trạng thái · AJAX values theo accessible · tệp YC theo accessible) · Playwright admin 3 cửa hàng × 9 route × 1920/391
  (`i4b_measure.py`): chưa chọn ⇒ prompt 7 màn + nút mở modal, chuông 13 (toàn hệ) vs 42; HN-01/HCM-01 mã không giao nhau, khớp SQL;
  0 tràn, 0 JS · `check_layers` 0 mới (2 R7 cũ `wujia_franchise`) · `vn_hardcode_scan` 0.
- Đối chiếu "Kết quả mong muốn": #152 7 gạch — 6 Pass + gạch 1 Pass 5/6 màn (Khảo sát = LIMIT bàn giao) ⇒ ≥90%. #157 5/5 Pass.
- Bài học: BA dùng lại ID ⇒ `qa_sync` khớp dòng đầu (Done) — dùng `stt:`. Form có modal chọn cửa hàng liệt kê mọi cửa hàng ⇒ test phạm vi
  phải soi đúng khối `<select>`, không cả trang. `ExamCommon` dựng sẵn 1 phiếu chờ ở kỳ `full`.
- Nợ: deploy `-u wujia_portal_base,wujia_portal_delivery,wujia_portal_report,
  wujia_support,wujia_exam,wujia_portal_return,wujia_portal_info_request,wujia_portal_support,wujia_portal_notification,wujia_portal_exam` →
  `qa_sync --only WJ-PORTAL-SCOPE-001 --apply` + `--only WJ-EXAM-001 --apply` · báo BA: Hỗ trợ/Thông báo nay theo cửa hàng · Khảo sát bàn giao ·
  issue chưa phân cụm #142, #169–#174 · xoá DB `wujia_i1`…`wujia_i4b` + filestore khi xong.
- Phiên kế: **I5 #153 WJ-PORTAL-ROLE-001** (role theo cửa hàng đang chọn; có Báo cáo + menu YC cập nhật).

## I5 #153 WJ-PORTAL-ROLE-001 · 09/10/2026 · Mac
- Kết quả: ✅ code + test + đo + ledger; commit `b9e7c3c7` (đã push); sheet chưa ghi (`--apply` sau deploy).
- Chủ dự án chốt: Home **ẩn hẳn ô Công nợ** với Nhân viên · YC cập nhật **chỉ chặn backend** (không thêm lối vào) ·
  `/portal/franchises/<id>`, `/my/franchises/<id>`, JSON members **theo role tại đúng cửa hàng đó** · **một trang "Không có quyền" chung** (403).
- Đã làm:
  - `wujia_portal_base` 19.0.7.41.0: `STORE_ADMIN_ROLES`, `get_current_store_role()` (cache theo request), `is_current_store_admin()`,
    `render_no_permission()` + `views/portal_no_permission.xml`; xoá `get_max_role_in_franchises` + `ROLE_RANK`; Home `show_debt_kpi`;
    Hồ sơ cửa hàng chỉ query thành viên khi Chủ/QL (mobile thêm thẻ "Thông tin thành viên" cho Nhân viên); `_members_if_admin` cho 2 route cũ;
    shell `_nav_store_admin` thay vòng lặp `_nav_mgr_fids`.
  - `wujia_portal_layout` 19.0.60.5.0: `.wujia-mhome-hero-kpis` lưới tự co 4 ⇄ 3 ô.
  - `wujia_portal_report` 19.0.3.2.0 (trang 403, export ⇒ về trang báo cáo, bỏ `max_role`) · `wujia_portal_debt` 19.0.5.1.0 (`_debt_access`,
    bỏ `portal_debt_no_permission`, KPI Home không query với Nhân viên) · `wujia_portal_info_request` 19.0.3.2.0 (guard list/new/detail/cancel/tệp/AJAX
    gọi lại L2 `_portal_can_request`, bỏ `Forbidden` thô). Nav sidebar + sheet report/debt theo luật chung.
  - i18n: `.pot` 4 module sinh lại; vi_VN thêm câu mới, xoá câu chết (sửa tay theo msgid, không qua polib để giữ diff nhỏ).
  - Test tag `wujia_role_i5` (base 4 · report · debt · info_request); sửa `test_f5_nav_item` ×2, `test_scan_e7_page_container`, `test_e8c_account_menu`,
    `test_f5_menu_ownership`, `test_scan_d3_card_header` (6→7), `test_portal_debt` (200→403), `test_jv8b_i18n`.
- Kiểm: DB `wujia_i5` (copy `wujia_i4b`) `-u` 5 module + hồi quy sale/return/exam/notification/delivery/purchase_history/support/knowledge:
  1060 test, 1 đỏ (snapshot i18n câu cũ) ⇒ sửa, rerun info_request + I5 22/22 RC=0 · mutation **5/5** đỏ (report guard · YC list guard ·
  KPI nợ luôn gửi · thành viên luôn query · nav luôn admin) · Playwright Chủ@HN-01+NV@HCM-01 và QL@HN-01 × 17 route × 1920/391 (`i5_measure.py`):
  NV ⇒ 403 đủ màn, export 303, AJAX forbidden, menu/sheet không Báo cáo/Công nợ, Home 3 ô đều; Chủ/QL ⇒ 200, xlsx thật, 4 ô; 0 JS ·
  `check_layers` 0 mới · `vn_hardcode_scan` 0.
- Đối chiếu "Kết quả mong muốn": 6/6 gạch Pass. LIMIT: YC chưa có lối vào menu · route cũ theo cửa hàng mang mã · Hỗ trợ/Khảo sát/Metabase ngoài phạm vi ·
  `/my/franchises` (danh sách website gốc) tràn ngang mobile 81px — có sẵn.
- Bài học: CSRF token trong HttpCase phải lấy SAU `authenticate` (đổi session). Test cũ mã hoá luật "QL nơi khác thấy Báo cáo" ⇒ đổi theo luật mới.
- Nợ: deploy `-u wujia_portal_base,wujia_portal_layout,wujia_portal_report,wujia_portal_debt,wujia_portal_info_request` →
  `qa_sync --only WJ-PORTAL-ROLE-001 --apply` (cùng nợ I1–I4b) · xoá DB `wujia_i1`…`wujia_i5` + filestore khi xong.
- Phiên kế: **I6 #159 WJ-NOTI-001** (`next-session-clusters-H.md` Prompt I6 — ledger đã có entry 08/2026 cùng ID ⇒ thay entry, dùng `stt: 159`).

## I6 #159 WJ-NOTI-001 — phạm vi dấu đã đọc + một luật số chưa đọc · 09/10/2026 · Mac
- Kết quả: ✅ code + test + đo + ledger; commit `76f5671d` (đã push); sheet chưa ghi (dry-run đúng 1 dòng, `--apply` sau deploy).
- Đầu phiên: repo up to date với upstream. `issue_queue --dev` = 22 (cụm I + chưa phân cụm #142, #169–#174). Reconcile WJ-NOTI-001:
  `custom/` chỉ còn comment timezone 08/2026 (`cc7570f`) ⇒ chưa fix; ledger có key cùng ID ⇒ thay entry, `stt: 159`.
- UAT chỉ-đọc: 19 thông báo (10 toàn hệ), 22 dấu: toàn hệ+cửa hàng 10 · toàn hệ+NULL 2 · chỉ định đúng cửa hàng 6 · **chỉ định+NULL 4**
  (admin, ANN/2026/0012–0015 gửi cửa hàng 1/2/3).
- Chủ dự án chốt: 4 dấu chỉ định thiếu cửa hàng ⇒ **xoá** (không tự gán) · thống kê backend thông báo toàn hệ **đếm theo user**.
- Đã làm:
  - `wujia_notification` 19.0.3.0.0: `_portal_read_scope` (toàn hệ = dòng franchise NULL theo user; chỉ định = dòng cửa hàng đang chọn) ·
    `_portal_read_domain` (domain trên thông báo, bền với dòng lệch) · **`_portal_unread_domain` = một luật** (hiệu lực + `read_ids not any`) ·
    `_portal_unread_count` = 1 `search_count` (bỏ phép trừ đếm) · `_mark_read` tách toàn hệ/chỉ định, ghi cả khi chưa chọn, bỏ qua cửa hàng
    không nhận · `_compute_read_stats` toàn hệ đếm user · migration `19.0.3.0.0/post-migrate.py` (gộp dấu toàn hệ min read/max open, xoá dấu
    chỉ định NULL/sai cửa hàng, log từng id, assert đếm) · help field + `.pot`/vi_VN.
  - `wujia_portal_notification` 19.0.5.0.0: lọc Chưa đọc/Đã đọc gọi L2 (bỏ query `read_noti_ids` tự dựng) · chi tiết/mark-read/mark-all bỏ chặn
    `STORE_NOT_SELECTED`, mark-all = `_portal_unread_domain` + trả số thật · nút "Đánh dấu tất cả là đã đọc" + tooltip phạm vi theo `store_scope`.
  - Home (`portal_base`) không sửa — đã gọi `_portal_unread_count`.
  - Test tag `wujia_noti_i6`: `wujia_notification/tests/test_i6_read_scope.py` (5 GIVEN + dòng lệch + read stats + migration chạy lại idempotent) ·
    `wujia_portal_notification/tests/test_i6_unread_one_rule.py` (Home = badge = popup = lọc; mark-all có/không cửa hàng; tooltip). Sửa
    `test_portal_rules`, `test_portal_notification_read` (chưa chọn ⇒ ghi dòng NULL), `test_portal_notification_f11`, `test_jv7_i18n`.
- Kiểm: DB `wujia_i6` (copy `wujia_i5`, dựng thêm dấu kiểu UAT): migration 18 → 11 dòng, 6 cặp toàn hệ, xoá 5 sai phạm vi · `-u` 3 module
  `--test-tags` **435/435** · hồi quy 12 module portal (layout/sale/return/exam/support/info_request/delivery/report/debt/purchase_history/
  knowledge/i18n) **737/737** · mutation **6/6** đỏ (`i6_mutate.py`) · EXPLAIN: 1 câu, subquery dấu đọc hashed 1 lần/requests, dùng
  `uniq_noti_user_no_store` / `user_id` index ⇒ không thêm index · Playwright admin 3 cửa hàng × 1920/391 (`i6_measure.py`): Home = chuông =
  hộp chuông = meta = số dòng lọc Chưa đọc ở mọi bước — 12/41/41 → mở 1 toàn hệ khi chưa chọn 11/40/40 → mark-all chưa chọn (11) 0/29/29 →
  mark-all HN-01 0 / HCM-01 29; 0 tràn, 0 JS · `check_layers` 0 mới · `vn_hardcode_scan` notification 0.
- Đối chiếu "Kết quả mong muốn": 6/6 gạch Pass. LIMIT: UAT xoá 4 dấu admin (thấy lại 4 bài chưa đọc) · mobile không có nút Đánh dấu tất cả (có
  sẵn) · Home chưa chọn vẫn khối nhắc chọn (I4a) · thống kê backend toàn hệ đổi cách đếm.
- Bài học: DB copy từ phiên trước mang user đo (`i5.mix`, `i5.mgr`) ⇒ test tạo cùng login vỡ setUpClass — đổi login trong DB nháp. BSD `sed`
  không hiểu `\|` (tag test ghép sai). Gọi `count` giữa `cr.execute(EXPLAIN)` và `fetchall` làm mất kết quả.
- Nợ: deploy `-u wujia_notification,wujia_portal_notification` (CÓ cập nhật dữ liệu — xem log `read scope`) →
  `qa_sync --only WJ-NOTI-001 --apply` (cùng nợ I1–I5) · xoá DB `wujia_i1`…`wujia_i6` + filestore khi xong.
- Phiên kế: **I7 #62 WJ-PH-003 + #163 WJ-PH-009** (`next-session-clusters-H.md` Prompt I7).

## I7 #62 WJ-PH-003 + #163 WJ-PH-009 — Lịch sử gồm đơn Đã hủy + ghi chú đặt hàng PC · 09/10/2026 · Mac
- Kết quả: ✅ code + test + đo + ledger; commit `34880bf0` (đã push); sheet chưa ghi (dry-run đúng 1 dòng/issue, `--apply` sau deploy).
- Đầu phiên: chủ dự án chốt commit I6 riêng ⇒ `76f5671d` + docs `9acbf6b4` (đã push). `issue_queue --dev` = 22 (cụm I + #142, #169–#174).
  Reconcile: WJ-PH-003 chỉ có commit theo yêu cầu cũ (`2f0e466b`, `0cd1f0a4`) ⇒ thay entry ledger + `stt: 62`; WJ-PH-009 0 dấu vết.
- Đã làm:
  - `wujia_portal_base` 19.0.7.42.0: `SALE_STATE_META` thêm `cancel` → `_lt('Cancelled')` (badge danger có sẵn). Home vẫn lọc `state != cancel`.
  - `wujia_portal_purchase_history` 19.0.4.1.0: list/lọc/phân trang/chi tiết bỏ `state != cancel` (giữ `franchise_id = fid`); option "Đã hủy"
    cuối ô lọc PC + **chip "Đã hủy" mobile** (mobile không có ô chọn trạng thái — phát hiện khi đo); thẻ PC "Ghi chú khi đặt hàng"
    (`portal_note`) dưới 2 panel; một chuỗi rỗng "Không có ghi chú" cho mọi ghi chú cả 2 kênh; `.wj-ph-note` pre-line + anywhere.
  - `wujia_portal_sale`: chỉ sửa comment guard huỷ ở màn kết quả gửi đơn.
  - i18n purchase_history: bỏ "No notes.", thêm "Cancelled" (sửa tay `.pot`/vi_VN — `--i18n-export` CLI Odoo 19 trả RC 2).
  - Test tag `wujia_ph_i7` (`test_i7_cancel_note.py`, 11 test); sửa `test_jv8_i18n` (bỏ "No notes."), `test_scan_d3_card_header` (8→9).
- Kiểm: DB `wujia_i7` (copy `wujia_i6`) `-u base,purchase_history` + base/sale/layout/return/delivery/report/i18n **585/585**, sau chip 465/465 ·
  mutation **4/4** đỏ (`i7_mutate.py`: list loại huỷ · detail bỏ scope · bỏ thẻ ghi chú PC · PC đọc delivery_note) · Playwright admin
  HCM-01 × 5 khổ (`i7_measure.py`): Tất cả 56 · Đã hủy 50 · trang 3 đủ 10 · nháp 1 · chi tiết huỷ badge danger · ghi chú 2 dòng + chuỗi 200
  ký tự PC = mobile, gọn thẻ · đổi HN-01 ⇒ không tìm thấy · 0 tràn, 0 JS · `check_layers` 0 mới · `vn_hardcode_scan` 0.
  UAT chỉ-đọc trước deploy: S00077 @HCM-01 PC không có ghi chú, không có option lọc huỷ (ảnh `i7_shots/uat_before_1440_77.png`).
- Đối chiếu "Kết quả mong muốn": #62 4/4 gạch Pass (list · lọc · phân trang · chi tiết + IDOR; 5 trạng thái cũ giữ). #163 2/2 GIVEN Pass.
- LIMIT: không tách đơn thay thế (BA chốt) · Home không hiện đơn huỷ · dòng "Trạng thái" trong khung Thông tin đơn PC vẫn chữ xanh (có sẵn).
- Bài học: mobile Lịch sử lọc bằng chip, không có select ⇒ thêm trạng thái lọc phải soi cả chip, đo `option[value]` trên mobile ra số của khối PC ẩn.
- Nợ: deploy `-u wujia_portal_base,wujia_portal_purchase_history` → `qa_sync --only WJ-PH-003 --apply` + `--only WJ-PH-009 --apply`
  (cùng nợ I1–I6) · xoá DB `wujia_i1`…`wujia_i7` + filestore khi xong.
- Phiên kế: **I8 #160 WJ-ORD-032 + #162 WJ-SUPPORT-002 + #166 WJ-EXAM-008** (`next-session-clusters-H.md` Prompt I8).

## I8 #160 WJ-ORD-032 + #162 WJ-SUPPORT-002 + #166 WJ-EXAM-008 — lệch PC↔mobile nhỏ · 09/10/2026 · Mac
- Kết quả: ✅ code + test + đo + ledger; commit `f8744424` (đầu phiên I9, chưa push); sheet chưa ghi (dry-run đúng 1 dòng/issue).
- Đầu phiên: repo up to date. `issue_queue --dev` = 22 (cụm I + #142, #169–#174). Reconcile: 0 commit/0 dòng `custom/` mang 3 ID, nhưng
  #160 thực tế đã sửa ở `6129ca59` (06/10, "nút Xem giỏ 390" — thêm `flex-wrap`), đo UAT chỉ-đọc 360/390/430 không tràn.
- Chủ dự án chốt: #160 chỉ ledger + đo lại (không chia cột đều) · #162 hiện đầy đủ nội dung (không thu gọn).
- Đã làm:
  - #160: không code. Đo DB copy + UAT: 5 khổ, tên SP ~110 ký tự, số lượng 99999 ⇒ 3 thành phần trong viewport, nút 44 (mobile)/40 (PC), 0 tràn.
  - #162 `wujia_portal_support` 19.0.5.2.0: khối mobile thêm thẻ "Request content" (msgid PC sẵn có ⇒ "Nội dung yêu cầu") sau Meta grid,
    trước File đính kèm; `.wujia-mticket-content` (14/21, đệm 6/14/14) + `.wj-sup-content` overflow-wrap anywhere, ảnh/bảng max-width, dùng
    cả ở PC (PC 1440 trước đó tràn chuỗi liền dài khỏi thẻ — phát hiện khi đo).
  - #166 `wujia_portal_exam` 19.0.7.3.0: XML khung ảnh mặc định `is-empty` + "No photo selected", bỏ tên tệp mẫu viết cứng, nút "Choose photo",
    Xoá ảnh `hidden`; JS `resetPhotoPreview(fileLabel, error)` = nơi duy nhất vẽ trạng thái (tiêu đề, nút Chọn↔Thay, Xoá, dòng tệp, class);
    `onPhotoPick` lỗi/thành công đi qua hàm này. 3 key `data-wj-msg-photo-{selected,choose,change}`; msgid mới "Choose photo" → "Chọn ảnh" (sửa tay `.pot`/vi_VN).
  - Test: `wujia_portal_support/tests/test_i8_mobile_content.py` (4, tag `wujia_support_i8`) · `wujia_portal_exam/tests/test_i8_photo_state.py`
    (3, tag `wujia_exam_i8`) · guard `test_scan_d3_card_header` support_detail 6→7 (CALL_SITES + FLUSH_VIEWS).
- Kiểm: DB `wujia_i8` (copy `wujia_i7`, ticket 5 dựng nội dung nhiều đoạn + URL dài + chuỗi liền + tệp tên dài) · test mới 7/7 · `-u` 8 module
  (support, exam, portal_layout, portal_base, portal_sale, portal_support, portal_exam, i18n) **821/821** sau khi sửa guard · mutation **4/4** đỏ
  (`i8_mutate.py`) · Playwright (`i8_measure.py`) 5 khổ trước/sau: #162 mobile có thẻ, chữ gọn, Gửi cách bottom nav 41px, PC hết tràn;
  #166 mở/validate/chọn/validate/xoá/tệp lỗi/sửa dòng có ảnh/mở lại ⇒ luôn đúng 1 trạng thái; 0 tràn, 0 JS · `check_layers` 0 mới (R7 = 2 có sẵn,
  module Thái) · `vn_hardcode_scan` support/exam 0.
- Đối chiếu "Kết quả mong muốn": #160 Pass (đã có trên UAT) · #162 3/3 ý Pass · #166 4/4 GIVEN/WHEN Pass.
- LIMIT: #160 bố cục lệch theo khổ (chốt giữ), SP 5 của issue không còn bán, chỉ đo tiếng Việt (đổi lang admin trên DB nháp không áp vào phiên đo) ·
  #162 không thu gọn nội dung dài · #166 kéo thả ảnh vẫn chỉ là chữ hướng dẫn (có sẵn), modal chỉ có ở PC.
- Bài học: Odoo 19 `-u A --test-tags /B` chỉ chạy test của module đang nạp ⇒ hồi quy phải `-u` cả nhóm module muốn test. Sửa CSS khi server
  đo đang chạy không đổi bundle — `-u` module rồi khởi động lại. `qa_sync.py` không có `--dry-run`: chạy không `--apply` là chạy thử.
- Nợ: deploy `-u wujia_portal_support,wujia_portal_exam` → `qa_sync --only WJ-SUPPORT-002 --apply` + `--only WJ-EXAM-008 --apply`
  · `qa_sync --only WJ-ORD-032 --apply` làm được ngay (đã trên UAT) · cùng nợ I1–I7 · xoá DB `wujia_i1`…`wujia_i8` + filestore khi xong.
- Phiên kế: **I9 #167 WJ-LANG-002 + #164 WJ-INSPECT-001** (`next-session-clusters-H.md` Prompt I9).

## I9 #167 WJ-LANG-002 + #164 WJ-INSPECT-001 — ngôn ngữ trên header · 09/10/2026 · Mac
- Kết quả: ✅ code + test + đo + ledger; commit `0e53d12b` (đã push cùng I8); sheet chưa ghi (chạy thử đúng 1 dòng/issue).
- Đầu phiên: chủ dự án chốt commit I8 riêng ⇒ `f8744424` + docs `c3f6aeda` (chưa push). `issue_queue --dev` = 22. Reconcile #167/#164:
  0 commit / 0 dòng `custom/` / 0 ledger.
- Gốc (tái hiện đúng số BA trên DB nháp + UAT chỉ-đọc):
  - #167: pill PC `width: 118px !important` còn 90px cho cờ + nhãn; nhãn không co ⇒ cờ bị bóp (en 4.36×15, vi 11.38×15).
  - #164: 4 route Khảo sát (code anh Thái) khai `website=True` ⇒ `http_routing._match` chọn lang theo URL › cookie `frontend_lang` › context,
    lệch mặc định `en_US` thì redirect `/vi/...`. UAT: vừa đăng nhập đã có cookie `en_US` ⇒ Home Việt, Khảo sát English (cờ US).
- Chủ dự án chốt: pill nới theo nhãn, tối thiểu 118 · #164 vá ở khung + bàn giao (không sửa `wujia_portal_inspection`).
- Đã làm (`wujia_portal_layout` 19.0.60.6.0):
  - `_pc_account.css` (`?v=1329`): pill `width:auto !important; min-width:118px`, nhãn nowrap; cờ `flex:0 0 20px; 20×15` (độ đặc hiệu ≥ Vuexy
    `bootstrap-extended.css:1804`, giữ margin cũ); dải 992–1199 trả `min-width:0` (không thì pill chỉ có cờ phình 118).
  - `models/ir_http.py` `_match`: user đã đăng nhập + path `/portal*` ⇒ gán sẵn `request.is_frontend(_multilang) = False` ⇒ http_routing bỏ
    khâu chọn lang/redirect ⇒ mọi route portal lang = `res.users.lang`. Khách giữ nhánh cũ (J-V0).
  - Bàn giao: mục mới trong `docs/handover-inspection-scope.md` (gốc, chỗ đã vá, khuyến nghị bỏ `website=True` + đưa chữ cứng qua `_()`).
  - Test tag `wujia_lang_i9` (`test_i9_lang.py`, 8): cookie en cũ, không cookie (không redirect `/vi/`), header Khảo sát = Home, đổi th theo,
    ID lạ redirect không tiền tố, khách về login, CSS cờ/pill. Sửa guard `test_g2_pc_topbar.test_pill_ngon_ngu_bo_be_rong_118` theo luật mới.
- Kiểm: DB `wujia_i9` (copy `wujia_i8`; ⚠ `createdb -T` ra owner sai ⇒ `ALTER DATABASE … OWNER TO odoo19`, không thì Odoo về db selector) ·
  `wujia_lang_i9` 8/8 · hồi quy `-u` 11 module (layout/base/sale/notification/support/exam/purchase_history/report/delivery/return/i18n)
  1031/1032 → đỏ duy nhất là guard 118 cũ ⇒ sửa ⇒ layout 265/265 · mutation **4/4** đỏ (`i9_mutate.py`) · Playwright (`i9_measure.py`)
  4 locale × 7 khổ: cờ 20×15 ở 1440/1920 mọi locale, pill en 139.6 / vi 126.6 / th, zh 118, cách giỏ 22; 992–1199 pill 55 và mobile 22×16
  không đổi; vi + cookie en: Home → Đặt hàng → Khảo sát → chi tiết → khắc phục đều `vi-VN` + cờ VN, mobile aria "Ngôn ngữ" (trước "Language"),
  không `/vi/`; set-lang en ⇒ Khảo sát English · `check_layers` 0 mới · `vn_hardcode_scan` layout 0.
- Đối chiếu "Kết quả mong muốn": #167 3/3 ý Pass (3 locale × 2 khổ 20×15 căn giữa · dropdown + mobile không đổi · tên dài không chồng lấn).
  #164 Pass (vi nhất quán qua Portal ↔ Khảo sát, không tự đổi locale, locale khác phản ánh đúng).
- LIMIT: DB nháp 0 phiếu Khảo sát ⇒ chi tiết/khắc phục chỉ đo tới redirect về list · chữ nội dung Khảo sát vẫn viết cứng tiếng Việt (nhóm Khảo sát)
  · pill en/vi rộng hơn 118 (chốt) · lỗi JS có sẵn `Cannot read properties of null (reading 'stop')` ở `/portal/order` 360 (trước = sau, ngoài phạm vi).
- Bài học: route `website=True` dưới `/portal` đi nhánh lang khác hẳn route thường — đo ngôn ngữ phải thử cả có/không cookie `frontend_lang`.
  `--test-tags` Odoo 19 là `tag/module`, không phải `/module:tag` (ra 0 test). Guard CSS cũ ghim số Figma ⇒ đổi luật thì sửa guard cùng phiên.
- Nợ: deploy `-u wujia_portal_layout` → `qa_sync --only WJ-LANG-002 --apply` + `--only WJ-INSPECT-001 --apply`
  · cùng nợ I1–I8 · xoá DB `wujia_i1`…`wujia_i9` + filestore khi xong.
- Phiên kế: **I10 #168 UI-LISTCARD-002 + H2** (`next-session-clusters-H.md` Prompt I10).

## I10 #168 UI-LISTCARD-002 + H2 StatusBadge sót — chữ ListCard + căn badge · 09/10/2026 · Mac
- Kết quả: ✅ code + test + đo + ledger; commit `5b0d057c` (push đầu phiên I11); sheet chưa ghi (`qa_sync` bị chặn quyền ghi — chủ dự án chạy tay).
- Đầu phiên: `git pull` (đã mới nhất, `f5b58f5c`). `issue_queue --dev` thêm **6 issue mới #169–#174** (0 code, chỉ docs nhắc ID; #171 dùng lại
  `WJ-HOME-001`). Reconcile #168: 0 commit / 0 dòng `custom/` / 0 ledger.
- Chủ dự án chốt: CategoryBadge trong card **cùng line-height, giữ cao riêng** (không kéo lên 28) · #174 để phiên sau.
- Gốc (đo trước trên DB `wujia_i10`, khớp số BA): label 13/400, value 13/400; `.wj-status-badge` line-height 1 (12) vs `.wujia-badge` 1.4 (16.8).
- Đã làm:
  - `wujia_portal_layout` 19.0.60.7.0: token `--wj-lc-title/label/value/strong-*`, `--wj-lc-lh` 18, `--wj-badge-lh` 16 (`_variables.css?v=1330`);
    `_components.css?v=1332`: rule ListCard đọc token; `--compact` thêm line-height; `.wj-lc .wujia-badge` inline-flex căn giữa, `--sm` đệm dọc 2
    (cao 26 / 22, trước 26.8 / 23.4). Đo lần 1 lộ card +1–2px ⇒ `.wj-lc__row` căn **đỉnh** (baseline label 12 vs value 13 đẩy hàng lên 19) +
    `.wj-lc__label` inline-flex căn giữa (icon 16 `.wj-lc__icon` đội hộp chữ 12 lên 19).
  - H2: fallback map trạng thái `'wujia-badge-muted'` → `'wj-status-badge--neutral'` (return list ×2, support ×2, info_request list); ưu tiên detail
    Yêu cầu cập nhật Bootstrap → `wujia-badge` như list (giữ họ tag chờ Q-TAG-1); Hồ sơ cửa hàng `/portal/franchises/<id>/profile` khoá Portal /
    Hết hạn / Sắp hết hạn → StatusBadge danger/pending. Bump base 19.0.7.43.0 · return, support 19.0.5.3.0 · info_request 19.0.3.3.0.
  - Guard: `test_scan_e2_status_badge` + 2 test quét mọi view `wujia_portal_*` (Bootstrap badge chỉ còn loại trừ BA, đếm đúng số; fallback map
    không họ cũ) + miễn trừ `--compact` thành {font-size, line-height}; e2b sửa assert chip "phương án xử lý" về đúng trang chi tiết (cũ bám nhầm
    chuỗi fallback ở list); E5 đọc số qua token. Test mới `wujia_listcard_i10` (`test_i10_listcard_tokens.py`, 7).
- Kiểm: `wujia_listcard_i10` + e5 + e2 + e2b 58/58 · hồi quy `-u` 11 module (layout/base/return/info_request/support/notification/knowledge/exam/
  debt/delivery/purchase_history) **1010/1010** · mutation **10/10** đỏ (`i10_mutate.py`) · Playwright `i10_measure.py` 10 route × 360/390/430/1440:
  label 12/500/18, value 13/500/18, strong 13/600/18, name 15/600/20, Inter; 0 card cao lên (Công nợ 360: 2 card −18 vì hàng nhãn–giá trị nay vừa
  1 dòng; Hỗ trợ −0.8/card), số card thấy không giảm, 0 cắt mới, 0 tràn, badge bảng desktop y nguyên · `wj_measure --diff` (em.hcm, 5 khổ):
  1440/1024/992 0 lệch, chỉ Hỗ trợ mobile −16px, 0 record mất · `check_layers` 0 mới (R7 2 cũ ở `wujia_franchise`) · `vn_hardcode_scan` 0.
- Đối chiếu "Kết quả mong muốn" #168: 7/7 ý Pass (ý 3: hai họ cùng line-height 16 + căn giữa; cao khác 2px theo chốt).
- LIMIT: card thành viên Hồ sơ cửa hàng (role + status cùng hàng, ngoài 8 màn BA) tâm lệch 1px — làm lại ở #174 · tên Thông báo vẫn kẹp 2 dòng (luật LC
  cũ, trước = sau) · màu label (contrast) là #170 · "Khẩn" giữ họ tag chờ Q-TAG-1.
- Bài học: đổi cỡ chữ một phía trong hàng flex căn baseline là đổi chiều cao hàng — đo chiều cao card trước/sau, đừng chỉ đo font.
- Nợ: deploy `-u wujia_portal_layout,wujia_portal_base,wujia_portal_return,wujia_portal_info_request,wujia_portal_support` →
  `qa_sync --only UI-LISTCARD-002` (xem) → `--apply` · cùng nợ I1–I9 · xoá DB `wujia_i1`…`wujia_i10` + filestore khi xong.
- Phiên kế: **I11 #174 + #172 + #173 Hồ sơ cửa hàng** (`next-session-clusters-H.md` Prompt I11).

## I11 #174 WJ-PROFILE-003 + #172 WJ-PROFILE-001 + #173 WJ-PROFILE-002 — Hồ sơ cửa hàng · 09/10/2026 · Mac
- Kết quả: ✅ code + test + đo + ledger; commit `cbaceca8` (push đầu phiên I12); sheet chưa ghi (`qa_sync` dry-run 1 dòng/issue, `--apply` sau deploy).
- Đầu phiên: chủ dự án chốt commit + push I10 ⇒ `5b0d057c` + docs `7e072dd5` (đã push). `issue_queue --dev` = 22. Reconcile #172–174:
  0 commit / 0 dòng `custom/` / 0 ledger.
- Gốc (tái hiện trên DB `wujia_i11` trước khi sửa):
  - #173: `wujia_franchise.remaining_days` + `is_expired` **stored**, chỉ depend `franchise_end_date` ⇒ không tự giảm theo ngày, không cron nào tính
    lại (UAT lệch 28 ngày; local HCM-01 lưu 730, đúng 696). `context_today` theo user, không theo cửa hàng.
  - #172: PC thiếu Ngày khai trương / SĐT / Email / Bắt đầu / Kết thúc / Còn lại; mobile thiếu Người phụ trách.
  - #174: card thành viên `lc_prefix` (role) + `lc_state` (status) ép tên còn 26–32px ở 320, 96–102 ở 390; tên clamp 2 dòng + overflow hidden.
- Chủ dự án chốt: #173 **Portal tính sống + bàn giao** (không đụng `wujia_franchise*`) · đếm **không gồm hôm nay** (585) · #174 **role xuống hàng meta**,
  status giữ góc phải.
- Đã làm:
  - `wujia_portal_base` 19.0.7.44.0: model `_inherit wujia.franchise.management` `_portal_today()` (tz `partner_id.tz`, sai/rỗng ⇒ VN) +
    `_portal_contract_days()` → `(days, expired)`; 3 chỗ hiển thị (Hồ sơ PC + mobile, `/portal/franchises/<id>/profile`) gọi helper; end rỗng ⇒ "—".
    PC thêm 3 ô vào Thông tin nhượng quyền + panel Hợp đồng nhượng quyền; mobile thêm Người phụ trách. vi_VN.po +8 msgid, `.pot` sinh lại.
  - `wujia_portal_layout` 19.0.60.8.0: `wj_list_card` param `lc_name_wrap` ⇒ `.wj-lc__name--wrap` (block, bỏ clamp, `overflow-wrap: break-word`),
    `_components.css?v=1333`. Card thành viên: bỏ `lc_prefix`, hàng "Vai trò" trong `lc_rows`.
  - Bàn giao `docs/handover-franchise-remaining-days.md` (gốc + đề xuất cron daily theo tz cửa hàng cho backend/bộ lọc ≤30 ngày).
  - Guard `test_scan_d3_card_header` 7 → 8 call site (panel Hợp đồng mới).
- Kiểm: `-u layout,base` RC=0 · `wujia_profile_i11` (`test_i11_profile.py`) **11/11** (585 đúng ví dụ BA, biên 0/−1/30/31, end rỗng, giảm theo ngày,
  tz Pago Pago 586 / VN sau 17h UTC 584, tz rác fallback; render PC = mobile 7 trường; hết hạn bỏ qua cờ stored; trang profile cũ cùng số; card không role ở
  hàng tên; CSS wrap) · hồi quy `-u` 11 module **1021/1021** (sau sửa guard D3) · mutation **9/9** đỏ (`i11_mutate.py`) · Playwright `i11_measure.py` 320/360/390/430/1440:
  vùng tên 116/156/186/217 (trước 26–32/66–72/96–102/136–142), 0 tên cắt (tên thử 45 ký tự 4 dòng ở 320), 0 tràn, 0 JS; "Còn lại" 696 ở 3 chỗ
  (trước 730); PC 12 trường, mobile cùng giá trị · `check_layers` 0 mới · `vn_hardcode_scan` base/layout 0.
- Đối chiếu "Kết quả mong muốn": #172 Pass (9 nhóm thông tin cùng giá trị 2 kênh, khác bố cục) · #173 Pass (585 với ví dụ BA, tự giảm, theo hợp đồng
  hiện hành) · #174 Pass (320–430 đọc đủ tên, không vỡ ký tự, không cắt 2 dòng, không tràn).
- LIMIT: backend vẫn đọc `remaining_days` cũ (bàn giao) · card thành viên cao +18–32px (thêm hàng Vai trò) · nhãn SĐT PC "Số điện thoại" vs mobile "SĐT"
  · chữ trạng thái "Kích hoạt (Active)" là bản dịch sẵn có.
- Bài học: field compute `store=True` phụ thuộc "hôm nay" là số chết — ORM chỉ tính lại khi field depend đổi; con số theo lịch phải tính lúc đọc hoặc có cron.
- Nợ: deploy `-u wujia_portal_layout,wujia_portal_base` → `qa_sync --only WJ-PROFILE-001/002/003 --apply` · cùng nợ I1–I10 · xoá DB
  `wujia_i1`…`wujia_i11` + filestore khi xong.
- Phiên kế: **I12 #169 WJ-PORTAL-UI-005 + #171 WJ-HOME-001** (`next-session-clusters-H.md` Prompt I12).

## I12 #169 WJ-PORTAL-UI-005 + #171 WJ-HOME-001 — hộp chọn cửa hàng là dialog + khối đầu Home PC · 09/10/2026 · Mac
- Kết quả: ✅ code + test + đo + ledger; commit `a64ce589` (đã push); sheet chưa ghi (`qa_sync` dry-run, `--apply` sau deploy).
- Đầu phiên: chủ dự án chốt commit + push I11 ⇒ `cbaceca8` + docs `429e0894` (đã push). Reconcile: #169 0 commit / 0 dòng `custom/`;
  #171 là **ID dùng lại** (entry ledger 08/2026 C7 nhãn KPI mobile) ⇒ thay entry.
- Gốc (đo trước trên DB `wujia_i12`, admin 3 cửa hàng, khớp mô tả BA): hộp không role/aria-modal/tên · mở bằng Enter focus vẫn ở trigger ·
  Tab 10/10 + Shift+Tab 10/10 ra ngoài · Esc không đóng · ×/Hủy/nền ⇒ focus rơi BODY · must-pick focus BODY. Home PC: PageHeader 64px +
  câu chào ⇒ toprow y=209; mobile "Khung giờ đặt hàng" là h3 đứng trước mọi h2 (nhảy cấp).
- Chủ dự án chốt: mở hộp ⇒ focus nút Đóng × (như sheet Thêm WJ-PORTAL-UI-004); must-pick (không ×) ⇒ radio đang chọn/đầu.
- Đã làm:
  - `wujia_portal_base` 19.0.7.45.0: `store_picker_modal.xml` card `role=dialog aria-modal aria-labelledby/-describedby` (tiêu đề + câu dẫn có sẵn,
    0 msgid mới), icon `aria-hidden`; trigger (badge PC, strip mobile, mục menu tài khoản, nút scope prompt) `aria-haspopup=dialog aria-controls`.
    `store_picker.js`: `show(trigger)` nhớ trigger + `inert` mọi con của `body` trừ overlay + `aria-expanded` + focus ×; `hide()` gỡ đúng phần
    inert đã đặt, trả focus về trigger nếu còn thấy, không thì Current Store đang hiện (mục menu tài khoản đã đóng); keydown Esc (chỉ khi có
    nút đóng) + bẫy Tab (radio group = 1 điểm dừng); must-pick khởi tạo inert + focus; đồng bộ `--active` khi đổi radio bằng mũi tên.
  - Home: bỏ `.content-header` PC (PageHeader + câu chào); 1 `<h1 class="visually-hidden">Store overview</h1>` ngay trong `.wujia-home-wrapper`
    (ngoài khối `d-none`/`d-lg-none` ⇒ chung PC + mobile); mobile "Ordering window" `ch_level=2`.
  - `wujia_portal_layout` 19.0.60.9.0: utility `.visually-hidden` kiểu BS5 (bundle portal là BS4 chỉ có `.sr-only`), `_components.css?v=1334`.
- Kiểm: `-u layout,base` RC=0 · `wujia_i12` (`test_i12_dialog_home.py`) **8/8** · hồi quy `-u` 11 module **1069/1069** · mutation **8/8** đỏ
  (`i12_mutate.py`: role, aria-haspopup, inert, Esc, trả focus, H1 vào khối PC, mobile h3, visibility:hidden) · Playwright `i12_measure.py`
  1440 + 390: dialog tên "Đổi cửa hàng đang thao tác", focus ×, Tab/Shift+Tab 0/10 thoát, nền inert 12/12, Esc/×/Hủy/nền ⇒ focus Current Store,
  menu tài khoản ⇒ Current Store, cookie cửa hàng không đổi, must-pick focus radio + 0 thoát + Esc không đóng, 0 lỗi JS · Home PC toprow
  209 → 96, KPI 358 → 245, trang −113px; mobile 390/320 ảnh trước = sau (chỉ đồng hồ khung giờ), heading H1(ẩn) → h2… cả 2 kênh ·
  `check_layers` 0 mới (R7 2 cũ ở `wujia_franchise`) · `vn_hardcode_scan` base/layout 0.
- Đối chiếu "Kết quả mong muốn": #169 Pass (tên/vai trò, focus trong hộp, nền không tương tác, Esc/Đóng/Hủy về trigger, Tab không thoát,
  không đổi store) · #171 Pass (PC không còn tiêu đề + câu chào, KPI lên cao 0 khoảng trắng, mobile y nguyên, H1 visually-hidden, section h2).
- LIMIT: chưa đo trên VoiceOver/TalkBack thật (chỉ cây truy cập Chromium) · chưa chạy Đổi cửa hàng thật (đúng phạm vi issue) · tab trình duyệt
  vẫn "Trang chủ" khác H1 "Tổng quan cửa hàng".
- Bài học: user admin đăng nhập vào `/odoo` có long-poll ⇒ Playwright `networkidle` treo, chờ `load`. Log test Odoo ở
  `logs/<năm>/<tháng>/<ngày>.log` (wujia_core chuyển log), không phải `logs/odoo.log`.
- Nợ: deploy `-u wujia_portal_layout,wujia_portal_base` → `qa_sync --only WJ-PORTAL-UI-005` + `--only WJ-HOME-001 --apply`
  · cùng nợ I1–I11 · xoá DB `wujia_i1`…`wujia_i12` + filestore khi xong.
- Phiên kế: **I13 #170 WJ-PORTAL-UI-006 contrast token chung** (`next-session-clusters-H.md` Prompt I13).

## I13 #170 WJ-PORTAL-UI-006 — tương phản chữ dùng chung ≥ 4.5:1 · 09/10/2026 · Mac
- Kết quả: ✅ code + test + đo + ledger; commit `69670757` + docs `6cee7dc2` (đã push); sheet chưa ghi (`qa_sync` dry-run, `--apply` sau deploy).
- Đầu phiên: I12 đã push. Reconcile #170: 0 commit / 0 dòng `custom/` / 0 ledger.
- Gốc: #28A9DF (2.68 trên trắng) và xám #8A939E/#8A9099/#9CA3AF (2.5–3.2) dùng làm MÀU CHỮ ở ~190 khai báo, 16 file CSS; cả `--wujia-cta`
  #0F7CA8 (4.33 trên #F3F6F8) và subtitle #6B7280 (4.45) cũng trượt. Chữ trắng trên #28A9DF / #16A34A / #EF4444. Topbar chữ trắng trên cyan.
- Chủ dự án chốt: token + quét hết module mình (không `wujia_franchise*` / `portal_inspection` / `mobile_*`) · chữ vô hiệu cũng ≥4.5 ·
  chữ trắng ⇒ làm đậm nền · topbar giữ nền #28A9DF, chữ + icon navy.
- Đã làm:
  - `wujia_portal_layout` 19.0.60.10.0 `_variables.css`: token mới `--wujia-brand-text` #166F94 / `-hover` #125C7B, `--wujia-brand-fill`
    (= cta) / `-hover`, `--wujia-{danger,success,warning}-{text,fill}`, `--wujia-topbar-fg` #0B2430, `--wj-disabled-{fg,bg,border}`;
    muted + subtitle → #616774, info-text #13773B; token mobile (nav, strip, morder, mres, msheet) trỏ về token mới. `--wujia-primary` giữ.
  - Quét bằng script: 189 `color:` brand/xám cũ → token chữ; 39 khối chữ trắng + nền sáng → token `-fill`. Topbar PC + header mobile
    đổi `--wujia-focus-ring` cục bộ sang navy. Placeholder chung `::placeholder` = muted, opacity 1. Sửa 4 hover làm mất chữ (KPI Home,
    chip checked, FAB Đăng ký thi, nút Tạo). DataList thêm `.wj-data-item.is-disabled` (nền/viền xám) thay `opacity .55` của khoá thi đã đóng.
  - Module màn bump: base 7.46 · debt 5.2 · delivery 4.2 · exam 7.4 · knowledge 5.1 · notification 5.1 · report 3.3 · return 5.4 · sale 5.4;
    `assets.xml` `?v=1335` (9 file layout).
  - Công cụ mới `scripts/qa/wj_contrast.py` (Playwright): mọi text node + placeholder + chữ SVG (`fill`), nền đặc gộp alpha + opacity,
    hover/focus từng dạng phần tử tương tác, vòng focus so nền cha, `--diff`.
- Kiểm: DB `wujia_i13` (copy `wujia_frp`) · `wj_contrast` 56 trang (28 route + chi tiết × 1440/390) × owner + manager, 3.702 mẫu/tài khoản
  (default/hover/focus): **1.635 → 0** cặp <4.5, focus ring **140 → 0** <3, 0 HTTP lỗi · `wj_measure --diff` HEAD ↔ mới 5 khổ: 0 đổi chiều cao,
  0 mất record, 0 lỗi JS · `-u` 13 module portal `--test-tags` **1127/1127** · test mới `wujia_i13` (layout token 5 + base quét CSS 3) ·
  mutation **13/13** (`i13_mutate.py`) · sửa 4 guard cũ ghim màu cũ (E3 pager #9CA3AF, E8 sidebar primary-dark, G2 chevron, D5h tự kiểm
  rỗng ⇒ tự kiểm bằng mẫu) · `check_layers` 0 mới (R7 2 cũ ở `wujia_franchise`) · `vn_hardcode_scan` 10 module 0.
- Đối chiếu "Kết quả mong muốn" #170: Pass — Sidebar, bảng/list, StoreContextBar, BottomNavigation, FilterChip, StatusBadge, link ≥4.5 ở
  mọi trạng thái PC + mobile; đang chọn/chưa chọn phân biệt bằng nền + đậm; #28A9DF giữ cho nền/viền/icon/topbar; focus ≥3.
- LIMIT: 12 dòng chữ sáng trên gradient tối Home mobile máy không đo (tính tay ≥5.6) · icon trắng header mobile giữ · dialog chọn cửa hàng /
  dropdown mở chưa đo bằng máy · muted = subtitle cùng xám · nền `alert-info` Vuexy giữ · nhóm Thái chưa sửa.
- Bài học: đo chữ SVG phải đọc `fill`, không `color` (báo động giả biểu đồ) · guard "phải quét trúng ≥1 rule" vỡ khi rule cuối bị bỏ đúng ⇒
  tự kiểm guard bằng mẫu · `--logfile=/dev/null` làm hỏng chuyển log của wujia_core (RC 255).
- Nợ: deploy `-u wujia_portal_layout,wujia_portal_base,wujia_portal_debt,wujia_portal_delivery,wujia_portal_exam,wujia_portal_knowledge,
  wujia_portal_notification,wujia_portal_report,wujia_portal_return,wujia_portal_sale` → `qa_sync --only WJ-PORTAL-UI-006 --apply` · cùng nợ
  I1–I12 · xoá DB `wujia_i1`…`wujia_i13` + filestore khi xong.
- Phiên kế: **★IR Review cụm I** (`next-session-clusters-H.md` Prompt ★IR).

## ★IR — Review cụm I trên UAT (09–10/10/2026)
- Phạm vi: đo chỉ đọc trên UAT sau khi chủ dự án deploy cụm I. Báo cáo đầy đủ ở `docs/i-review.md` (ma trận, từng issue, sửa, nợ).
- Deploy UAT: lần đầu chạy 2 tiến trình `-u` cùng lúc (PID 2992, 14244) nên khoá DB, nâng cấp dừng giữa chừng. Chạy lại với danh sách
  module ⇒ 0 module lệch. Ghi luật **lệnh deploy sau mỗi issue/phiên** vào compact §6 (đúng dạng chủ dự án chạy, không cờ lạ).
- Đo: `scripts/qa/wj_ir_matrix.py` 274 ô (5 ngữ cảnh × 2 khổ × 28 route + chi tiết), 252 đạt. 22 ô lệch là kỳ vọng script quá chặt;
  admin chưa chọn cửa hàng: quét 0 lộ chứng từ. `wj_ir_checks.py` 44 kiểm: 42 đạt + #159 đo tay đạt + #172 nhãn "SĐT" đạt.
  #166 modal ảnh đạt @1440/1920.
- Sửa `afc42869`: #170 trên UAT còn 32 cặp <4.5. Nguyên nhân: chip Giao hàng chỉ hiện khi có dữ liệu; số Đã thanh toán Công nợ;
  placeholder bị `.form-control::placeholder` của bundle website đè. Bump layout 19.0.60.10.1 · delivery 19.0.4.2.1 · debt 19.0.5.2.1 ·
  `?v=1336`. Test DB `wujia_i13` 736/736 (nhớ `--db-filter='^<db>$'`, thiếu thì 118 test HTTP 404).
- Sheet (CSV kiểm 10/10): 20 dòng Ready for Retest + #156 `Done` (BA đóng) · `issue_queue --dev` chỉ còn #142. `qa_sync --only` từng ID,
  chừa #142; #154 lỗi bridge ở bước History (ô đã ghi) ⇒ có thể thiếu 1 dòng History. Ledger: 19 issue "ĐÃ DEPLOY UAT 09/10/2026",
  #160 đã ghi từ trước, #170 "CHƯA lên UAT (phần bổ sung)".
- #142 UI-PC-HOME-REDESIGN-001: Home hiện `$` do dữ liệu (partner HCM-01 gắn pricelist "Default (USD)"), không phải code ⇒ chờ chủ dự án.
- Deploy: `nssm stop Odoo; python D:\wujia-tea\odoo19\odoo-bin -c D:\wujia-tea\config\odoo-server.conf -d wujia_tea_19 --addons-path "D:\wujia-tea\custom,D:\wujia-tea\odoo19\addons" -u wujia_portal_layout,wujia_portal_delivery,wujia_portal_debt --stop-after-init; nssm start Odoo`
- 10/10 sau deploy `afc42869`: version 3 module khớp · `wj_contrast` UAT **32 → 0** cặp <4.5 (56 trang, 4.001 mẫu) · ledger + sheet dòng 170
  "ĐÃ DEPLOY UAT 10/10/2026" (+1 History; ghi trực tiếp vì `qa_deploy_mark` chỉ thay tiền tố "Chờ deploy UAT") · xoá 14 DB `wujia_i1…i13`, `i4b` + filestore.
- 10/10 #142 UI-PC-HOME-REDESIGN-001 → Ready for Retest (chủ dự án chọn): không đổi code, LIMIT ghi phản hồi BA RETEST FAIL 08/10 — `$` do
  bảng giá duy nhất "Default" USD trên UAT (76/77 đơn USD), PC = mobile; retest cần đổi bảng giá sang VND + đơn mới. `issue_queue --dev` = 0.
- Phiên kế: cụm H (H-A không cần BA) / Phần O cụm J (chờ BA).

## Chỉnh UI header — badge đỏ nhạt + topbar PC thẻ trắng · 10/10/2026 · Mac
- Kết quả: ✅ **ĐÃ DEPLOY UAT 10/10/2026** (commit `c592558c`), đo lại trên UAT đạt. Không có Issue ID ⇒ không ledger/`qa_sync`.
- Yêu cầu chủ dự án: (1) badge số giỏ hàng đỏ quá đậm; (2) thanh header PC xấu. Chốt qua ảnh dựng thử: thẻ trắng · đỏ `#DC2626` ·
  **cho lệch số đo Figma UI-01 (khối cửa hàng 430 cố định) và UI-03 (tài khoản 204×52)**.
- Đã làm:
  - `wujia_portal_layout` 19.0.60.11.0 `_variables.css`: `--wujia-danger-fill` #C92020 → #DC2626 (chữ trắng 4.83); nhóm
    `--wujia-navbar-pill-*` thành thẻ trắng (nền `bg-card`, hover `primary-soft`, chữ `text-primary`, icon `brand-text`, nhãn
    `text-subtitle`, bo 14, thêm `-shadow`). `_pc_account.css`: tài khoản 52 → 48 bo theo token; cụm phải (giỏ/chuông tròn 40,
    khoảng cách, padding phải 20) áp từ **992** thay vì 1200 — trước đây 992–1199 giỏ/chuông trần trên nền xanh, pill tài khoản dính mép.
  - `wujia_portal_base` 19.0.7.47.0 `store_picker.css`: khối cửa hàng `width: auto; max-width: 430px` (ôm nội dung, tên dài ellipsis);
    chip vai trò trong khối bo tròn, nền nhạt + chữ đậm theo vai trò (neutral / success / warning). Chip ở menu tài khoản không đổi.
  - Guard sửa cùng phiên: `test_g2_store_switcher` (430 cố định → trần 430), `test_g2_pc_topbar` (`PC_MQ` 1200 → 992),
    `test_i13_contrast` (thêm chữ/icon/nhãn pill trên nền pill + hover ≥4.5). `assets.xml` `?v=1337`.
- Kiểm: DB `wujia_hdr` (copy `wujia_vr`; phải `-u wujia_i18n` trước rồi mới `-u` toàn bộ module, không thì `mt_queued` thiếu cột) ·
  `-u wujia_portal_layout,wujia_portal_base --test-tags` **637/637** · đo cascade thật owner/manager/staff × 1920/1440/1200/1100/992:
  cao 48/40/40/40/48, bo 14/20, nền trắng, khối 252–267 (tên dài 426–430 + ellipsis), 0 tràn, 0 lỗi JS · badge `rgb(220,38,38)` PC + mobile ·
  `wj_contrast` 33 trang (6 route × 1440/1100/390, default/hover/focus) 2.662 mẫu: **0** cặp <4.5, 0 focus ring <3 ·
  hồi quy 6 trang × 2 khổ: 200, 0 tràn, 0 lỗi JS.
- LIMIT: dựng thử ban đầu bằng nhúng CSS trên UAT (thứ tự cascade khác thật) — số chốt lấy từ DB copy · hamburger 992–1199 giữ màu cũ.
- Deploy: `nssm stop Odoo; python D:\wujia-tea\odoo19\odoo-bin -c D:\wujia-tea\config\odoo-server.conf -d wujia_tea_19 --addons-path "D:\wujia-tea\custom,D:\wujia-tea\odoo19\addons" -u wujia_portal_layout,wujia_portal_base --stop-after-init; nssm start Odoo`
- Sau deploy (UAT, chỉ đọc): XML-RPC layout 19.0.60.11.0 · base 19.0.7.47.0; 3 file CSS phục vụ khớp repo từng byte; `?v=1337`.
  `/portal` HN-01 (Nhân viên) + HCM-01 (Quản lý) × 1920/1440/1200/1100/992: khối cửa hàng 267 / 313 × 48 bo 14, ngôn ngữ 127×40
  (55×40 dưới 1200), giỏ/chuông 40×40 bo 20, tài khoản 204×48 bo 14, nền trắng + bóng, mép phải 20, hover `rgb(234,247,253)`,
  0 tràn, 0 lỗi JS · `--wujia-danger-fill` = #DC2626, badge giỏ/chuông `rgb(220,38,38)` chữ trắng ở 1440 + 390.
  LIMIT: admin không có số nào đang hiện (giỏ trống, 0 thông báo chưa đọc) ⇒ màu badge đọc từ phần tử ẩn, chưa nhìn badge thật trên UAT.
- **Đổi lần 2 cùng ngày — kính mờ + chữ trắng đúng Figma** (chủ dự án xem thẻ trắng trên UAT thấy xấu, so 4 kiểu rồi chốt B). ✅ **ĐÃ DEPLOY UAT
  10/10/2026** (commit `8f72a740`), đo lại trên UAT đạt. layout 19.0.60.12.0 · base 19.0.7.48.0 · `?v=1338`.
  - `_variables.css`: `--wujia-navbar-pill-bg` rgb(255 255 255 / .18), hover .30, chữ + icon #FFFFFF, nhãn trắng .82, bỏ bóng, thêm
    `--wujia-navbar-chip-bg` .26. `store_picker.css`: chip vai trò trong khối một kiểu kính + chữ trắng (bỏ 3 màu theo vai trò).
    `_pc_account.css` + `_sidebar.css`: nút ba gạch 992–1199 ra trắng (trước giờ thua `.navbar-light .navbar-nav .nav-link`, xám 50%).
    Hình học giữ như lần 1 (khối ôm nội dung ≤430, tài khoản 204×48, bo 14).
  - ⚠️ **Ngoại lệ WJ-PORTAL-UI-006 (#170) do chủ dự án chốt**: chữ trắng trên kính 1.77–2.24:1. `wj_contrast` 33 trang 2.662 mẫu:
    319 mẫu <4.5, **toàn bộ trong topbar PC** (nhãn/tên cửa hàng, chip vai trò, tên/vai trò tài khoản, nhãn ngôn ngữ); ngoài topbar 0;
    focus ring <3: 0. Guard `test_i13_contrast::test_topbar_keeps_cyan_with_glass_pills` đổi sang khoá đúng giá trị Figma.
  - Kiểm DB `wujia_glass` (copy `wujia_vr`): test 2 module **637/637** · owner/manager/staff × 1920/1440/1200/1100/992: 48/40/40/40/48,
    nền rgba .18, chip .26, chữ trắng, hover .30, mép phải 20, 0 tràn, 0 lỗi JS · badge `rgb(220,38,38)` · 5 trang × 1440/390: 200, 0 tràn, 0 lỗi JS.
  - Deploy: lệnh như trên (`-u wujia_portal_layout,wujia_portal_base`).
  - Sau deploy lần 2 (UAT, chỉ đọc): XML-RPC đúng 2 version; 4 file CSS phục vụ khớp repo từng byte; `?v=1338`. `/portal` HN-01 + HCM-01 ×
    1920/1440/1200/1100/992: khối 267 / 313 × 48 bo 14 nền rgba .18, chip .26, ngôn ngữ 127×40 (55×40 dưới 1200), giỏ/chuông 40×40, tài khoản
    204×48, chữ + icon trắng, nhãn trắng .82, nút ba gạch trắng, hover .30, mép phải 20, 0 tràn, 0 lỗi JS · badge `rgb(220,38,38)` ·
    5 trang × 1440/390: 200, 0 tràn, 0 lỗi JS (`/portal/debt` 403 với admin vai Nhân viên HN-01 — quyền, không liên quan CSS).
- Nợ: báo BA: số đo UI-01/UI-03 đã đổi **và topbar PC là ngoại lệ tương phản #170** (retest WJ-PORTAL-UI-006 sẽ thấy cặp <4.5 ở topbar).
  DB `wujia_hdr`, `wujia_glass` + filestore đã xoá.
- Phiên kế: cụm H (H-A không cần BA) / Phần O cụm J (chờ BA).

## Thông báo giỏ hàng — thẻ `wjToast` dùng chung + hộp hỏi xoá của portal · 10/10/2026 · Mac

- Nguồn: BA gửi ảnh màn Giỏ hàng mobile (UAT, HCM-01) — thông báo "Đã bỏ khỏi giỏ" đè lên cờ/giỏ/tài khoản và không đọc được. Không có
  Issue ID (hàng đợi Dev = 0) ⇒ làm theo yêu cầu chủ dự án, không ledger/`qa_sync`. ✅ **ĐÃ DEPLOY UAT 10/10/2026** (commit `841f329e`), đo lại trên UAT đạt.
- Gốc: toast viết tay `div.alert.alert-success` ghim `top:20px; right:20px` (ô 240×52 tại y 20–72 = đúng header mobile 72), màu theme
  nền xanh lá 20% + chữ xanh lá trên nền `#28A9DF`. Chỉ hiện khi `/cart/step` trả `removed` ("−" ở số tối thiểu); thùng rác đi `/cart/remove`:
  hỏi bằng `window.confirm`, xoá xong im lặng. Portal có 3 toast viết tay khác nhau (giỏ, đặt hàng, thông báo PC).
- Chủ dự án chốt (ảnh so: https://claude.ai/artifact/KKmNYo4WnGdbB4GFKhfZSb): thẻ nền trắng + dấu tích xanh, tự tắt 3 giây; mobile ngay dưới
  header, PC góc phải dưới thanh trên; thùng rác hỏi bằng hộp của portal rồi mới báo; một thành phần chung; "−" ở số tối thiểu giữ như WJ-ORD-021.
- Sửa:
  - `wujia_portal_layout` 19.0.60.13.0, `?v=1339`: **mới** `static/assets/js/wj_toast.js` — `window.wjToast(text, {type: 'success'|'error'})`,
    `top` = đáy `.wujia-mheader`/`.wujia-navbar` đang hiện + 12 (đã cuộn qua thì 12), tối đa 3 thẻ, `role=status|alert`, chữ đặt bằng
    `textContent`. `_variables.css` thêm `--wujia-toast-*`; `_components.css` thêm `.wj-toast-host`/`.wj-toast*` (chỉ token).
  - `wujia_portal_sale` 19.0.5.5.0: `portal_cart_sync.js` + `portal_order.js` gọi `wjToast`; `handleRemove` mở hộp `#wjCartRemove`
    (template mới `cart_remove_modal` trong `order_confirm_modal.xml`, dùng lại khuôn `wj-pc-modal__*` + `wj-order-confirm*` ⇒ không thêm CSS;
    Hủy/Esc/bấm nền = không xoá; thiếu hộp thì rơi về `window.confirm`). `portal_cart_remove` trả thêm `removed: True`. Xoá `.wj-pc-toast--error`
    (chưa từng dùng). `.po` thêm `Remove` → "Xoá".
  - `wujia_portal_notification` 19.0.5.2.0: `portal_notification_pc.js` bỏ thanh đen giữa đáy, gọi `wjToast`.
  - Test mới: `wujia_portal_sale/tests/test_cart_feedback.py` (4) · `wujia_portal_layout/tests/test_toast.py` (4) ·
    `wujia_portal_base/tests/test_scan_toast.py` (2, không JS portal nào tự dựng ô `position:fixed`); sửa `test_remove_idempotent` + `test_jv4_i18n`.
- Kiểm: DB `wujia_toast` (copy `wujia_vr`) · test 4 module **761/761** · Playwright bấm thật 390 / 1440 / 1100:
  thùng rác → hộp mở (tên sản phẩm, focus nút Hủy, Tab xoay 2 nút), Hủy/Esc/nền giữ nguyên số dòng, "Xoá" bớt 1 dòng + thẻ; "−" ở số tối
  thiểu xoá ngay + thẻ, không mở hộp; thẻ mobile 366×48 tại x 12, `top` 84 (header 72), cuộn 487px thì `top` 12; PC 360×48 cách phải 24, `top` 84;
  nền `rgb(255,255,255)` chữ `rgb(17,24,39)`, dấu `rgb(21,128,61)`; chạm số tối đa → thẻ lỗi dấu `rgb(220,38,38)` `role=alert`; thêm vào giỏ +
  đánh dấu đã đọc (Thông báo PC) ra cùng thẻ; thẻ mất sau 3 giây; không giao nút nào của header; hộp "Xác nhận đơn hàng" vẫn mở/đóng;
  0 hộp thoại trình duyệt, 0 lỗi JS, 0 tràn ngang.
- Bài học: `.po` không có dòng `#:` — Odoo ghép tham chiếu từ `.pot`; thêm view mới dùng lại msgid cũ ("Cancel") mà quên thêm `#:` của view
  đó vào `.pot` thì chữ không được dịch ở view mới.
- LIMIT: tiêu đề hộp dài ("Xoá sản phẩm này khỏi giỏ?") xuống 2 dòng ở 390 · trang Thông báo PC tải lại sau 0,6 giây nên thẻ chỉ kịp thoáng hiện
  (hành vi cũ) · `wj_back_guard.js` vẫn dùng `window.confirm` (ngoài phạm vi).
- Deploy: `nssm stop Odoo; python D:\wujia-tea\odoo19\odoo-bin -c D:\wujia-tea\config\odoo-server.conf -d wujia_tea_19 --addons-path "D:\wujia-tea\custom,D:\wujia-tea\odoo19\addons" -u wujia_portal_layout,wujia_portal_sale,wujia_portal_notification --stop-after-init; nssm start Odoo`
- Sau deploy (UAT, chỉ xem — mở hộp hỏi rồi Hủy/Esc, gọi `wjToast` trong trình duyệt đo, 0 request đổi giỏ): XML-RPC đúng 3 version; 6 file
  JS/CSS phục vụ khớp repo (chỉ khác CRLF). HCM-01 × 390 / 1440 / 1100, trang giỏ + trang đặt hàng + thông báo: hộp `#wjCartRemove` mở với tên
  "Pudding Trứng", nút Hủy/Xoá, focus Hủy, Esc + Hủy đóng và giữ 2 dòng; thẻ mobile 366×48 tại x 12, `top` 84 (header 72); PC 360×48 cách phải
  24, `top` 84; nền trắng, chữ `rgb(17,24,39)`, dấu `rgb(21,128,61)` / lỗi `rgb(220,38,38)` `role=alert`; mất sau 3 giây; không đè nút header;
  0 hộp thoại trình duyệt, 0 lỗi JS, 0 tràn ngang. LIMIT: không bấm "Xoá"/"−" thật trên UAT (luồng xoá thật đo ở local); ca đã cuộn chỉ đo ở local.
- Nợ: báo BA đã đổi thông báo giỏ + cách tái hiện (bấm "−" ở số tối thiểu) để BA retest xoá thật. DB `wujia_toast` + filestore đã xoá.
- Phiên kế: cụm H (H-A không cần BA) / Phần O cụm J (chờ BA).

## Ghi chú đổi hạ tầng — UAT mới, repo mới, aaPanel, Metabase, mô hình nhánh · 12/10/2026 · Mac

- Kết quả: ✅ xong ghi chú + thay tham chiếu + dọn repo (xoá 330 file cũ trong `docs/` và `scripts/`, ~24 MB), push lên repo mới.
  Nhánh/CI chưa đổi (phiên repo riêng).
- Nguồn: chủ dự án báo đổi repo sang `huynhngoanhthai/WujiaTea-ERP-internal`, UAT sang `https://dev.wujiatea.com.vn`
  (thay hẳn `113.161.187.126:8019`), thêm aaPanel + Metabase, kèm sơ đồ nhánh `deploy/production` · `deploy/staging` ·
  `feature/*` · `staff/<name>/<task>` · `hotfix/*`.
- Đã làm:
  - `docs/CREDENTIALS.md` viết lại: repo mới, UAT mới, aaPanel, Metabase; máy Windows cũ gom vào mục "ngừng dùng".
  - Thay địa chỉ UAT/link repo ở tài liệu sống (compact summary §1/§5/§6/§12, `UAT_ACCESS_AND_DEBUG.md`, chuẩn QA 01/02,
    `CHECKLIST.tex`, `setup-server.ps1`), mặc định của 6 script `scripts/qa/` + 6 file `~/wujia-devkit/ba_spec/`
    (kể cả nightly), và lệnh `/wujia-start`.
  - **Mới** `docs/next-session-repo-migration.md`: hiện trạng đo được, sơ đồ nhánh, 6 nhận xét, danh sách việc đổi repo,
    mục bảo mật, mục chưa biết.
  - Bỏ lệnh deploy máy Windows (`nssm`) khỏi compact summary §6 và hai lệnh `/wujia-*`; §6 giờ ghi quy trình máy mới chưa chốt.
  - Dọn repo theo yêu cầu chủ dự án: danh sách xoá/giữ ở `docs/next-session-repo-migration.md` §7. Ledger + chapter `.tex` giữ nguyên.
- Đo (chỉ đọc): repo mới chỉ có `main` @ `edef2fed`; máy mới 115.74.247.189, Odoo 19, DB `wujia_tea_19` + `wujia_mn` +
  `huipeng_db`; Metabase 200; link aaPanel 404 với request thường; cả hai repo GitHub đọc được không cần đăng nhập.
- Kiểm: `py_compile` 10 script + `bash -n` 2 file nightly đạt; địa chỉ cũ chỉ còn ở mục "máy cũ" và file lịch sử.
- LIMIT: chưa đăng nhập UAT mới / aaPanel / Metabase; chưa biết version module trên UAT mới ⇒ số đo UAT trước 12/10
  là của máy cũ.
- Nợ: chủ dự án báo tài khoản UAT mới + cách deploy máy mới · repo đang công khai mà `CREDENTIALS.md` có mật khẩu
  (chủ dự án quyết ghi thẳng) · `wujia-end-sprint.md` còn `push origin master` · thay đổi ở `~/wujia-devkit` chưa commit.
- Issue List 12/10: 9 `Ready for Dev` — #182 UI-FORM-VALIDATION-001 (High) · #175 #176 #177 #178 #180 (Home) · #179 ·
  #181 WJ-OPS-001 · #139 UI-FILTER-001 (đã có code + ledger, cần reconcile).
- Phiên kế: Issue List — #182 trước, rồi cụm Home 175–180, #181 phiên thiết kế riêng, reconcile #139. Phiên repo chạy riêng.

## ADR-028 — dời source theo miền (kiểu Beesuite) · 12/10/2026 · Mac

- Kết quả: ✅ **đã lên UAT**. PR #7 (`feature/source-restructure`, 4 commit code + 2 commit tài liệu) merge vào `deploy/staging` = `f3107562`;
  deploy 22:23 12/10 bằng *Deploy latest* trong aaPanel; UAT chạy trên bố cục mới.
- Nguồn: chủ dự án chốt chia folder theo miền, Wujia là core, mỗi nước/bên nhượng quyền clone cả core + module riêng trong `addons/`.
- Đã làm:
  - `8fbd0c68` dời 59 module khỏi `custom/` + `themes/oca_queue` vào `base/ franchise/ sales/ logistics/ account/ academy/ service/ portal/
    mobile/ bi/ tools/ third_party/{oca,oca_queue,om,misc}/`; `addons/` rỗng; `UI/` → `docs/design/`. Thuần `git mv`.
  - `a2c1d1ac` `scripts/wj_paths.py` = nguồn duy nhất của bố cục (`--addons-path`, `--where`, `--list`, `--changed-modules`); 10 script QA,
    2 script i18n, 4 script shell chuyển sang dùng nó; `check_layers.py` thêm luật R8; `config/odoo.conf.example`; `README.md` gốc.
  - `3a241ca0` 30 file test quét source thôi ghép đường dẫn từ thư mục cha, dùng `wujia_portal_layout/tests/src_paths.py`.
  - `ae72cd63` dời `build_pager` / `rate_limit` từ `portal_base` xuống khung `portal_layout` (khung hết import ngược); `portal_base` import
    lại tên cũ. layout 19.0.60.13.1 · base 19.0.7.48.1.
  - Tài liệu: chapter 82 (ADR-028), compact summary §1/§2/§3/§5/§6/§11, `next-session-repo-migration.md` §4 + §8, `CREDENTIALS.md`.
- Kiểm: tree SHA 81 module trước = sau · cùng lệnh test trên 2 bản sao `wujia_vr` (bố cục cũ qua worktree, bố cục mới): **1359/1359, 0 đỏ** ở
  cả hai, số test 21 module khớp từng module; chạy lại sau `ae72cd63` vẫn 1359/0 · file source test quét thấy: 2092 = 2092 · `check_layers`
  0 vi phạm tầng, 0 vi phạm R8 · khởi động server bố cục mới: `/web/login` + `/portal/login` 200, file tĩnh từ 4 folder khác nhau 200,
  92 module `installed` ở cả hai bản · 2 câu chữ dời sang layout vẫn ra tiếng Việt.
- Bài học: (1) test quét source dựng đường dẫn bằng `dirname(__file__)/../..` ⇒ dời folder thì 72 test đỏ, và vài test **xanh giả** vì vòng
  quét không còn thấy module nào — phải so tập file quét được, không chỉ đếm test. (2) Tạo DB copy bằng `createdb -T` phải kèm `-O odoo19`:
  DB thuộc user khác thì Odoo không tự chọn DB cho khách ⇒ test HTTP chưa đăng nhập trả 404.
- Khảo sát máy chủ (chỉ đọc qua aaPanel): `odoo-dev` systemd, source `/www/wwwroot/dev.wujiatea.com.vn` @ `ded91f1b`, config
  `config/odoo.conf`; deploy = bấm *Deploy latest* trong aaPanel → hook → `deploy.sh --no-pull`; **merge không tự deploy** (Automatic deployment Off). Ba instance Odoo là ba tiến trình riêng.
- LIMIT: chưa đăng nhập đo trong UAT (chưa có tài khoản UAT mới), mới kiểm từ ngoài · `scripts/qa/css_move/` (script một lần) còn đường dẫn cũ.
- Deploy (đã làm, qua aaPanel): (1) sao lưu rồi sửa `addons_path` trong `config/odoo.conf` (17 folder của bố cục mới + 3 mục cũ ở cuối) và `deploy.sh`
  dòng 222 → `CHANGED_MODULES=$("$PYTHON_BIN" scripts/wj_paths.py --changed-modules "$OLD_HEAD" "$NEW_HEAD")`; (2) merge PR #7; (3) *Deploy latest*: máy chủ `ded91f1b` → `f3107562`,
  `odoo-dev` restart. Kiểm từ ngoài: `/web/login` + `/portal/login` 200, file tĩnh của 13 folder 200, log sau restart 0 ERROR, module nạp từ
  `franchise/…` `portal/…`. `deploy.sh` **không chạy `-u`** (đường *Deploy latest* cho `OLD_HEAD = NEW_HEAD` + merge commit ⇒ dò ra rỗng);
  PR này chỉ đổi Python + `.po` + 2 số version nên không cần, nhưng `latest_version` DB của layout/base còn `.0`.
- Bài học deploy: (3) đừng suy ra "merge là deploy" từ việc có git hook — phải xem Git Manager của site (Automatic deployment Off). (4) Số dòng
  đọc qua script tự viết bị lệch 1 vì script in thêm dòng tiêu đề: dòng cần sửa là 222, không phải 223.
- Nợ: báo anh Thái (đường dẫn module của anh ấy đổi, nội dung không đổi; nhánh đang mở + 3 PR `jules` #4–#6 phải merge `deploy/staging` về) ·
  sửa lỗ hổng `OLD_HEAD = NEW_HEAD` trong `deploy.sh` (lấy `ORIG_HEAD`) · xoá vỏ `custom/` + `themes/oca_queue` trên máy chủ rồi bỏ khỏi `addons_path` ·
  `~/wujia-devkit` đã sửa 4 file theo bố cục mới, chưa commit, vẫn trỏ repo cũ · `server_wide_modules` máy chủ thiếu `queue_job` so với local ·
  webhook Discord viết thẳng trong `deploy.sh` · Huipeng còn bố cục cũ.
- Issue List 12/10: 10 `Ready for Dev` — #182 UI-FORM-VALIDATION-001 (High) · #175–#180 (Home) · #181 WJ-OPS-001 · #183 UI-LISTCARD-003 ·
  #139 UI-FILTER-001 (reconcile).
- Sau deploy: `admin` / `Wujia@2026` đăng nhập được UAT mới (161 module `installed`); bảng "Sửa ở đâu" ghi ở §6 compact summary + `CREDENTIALS.md`.
- Phiên kế: Issue List (#182 trước). Việc máy chủ còn lại: xem Nợ.

## Lập plan cụm K — chia 17 issue + ghi chú máy chủ · 14/10/2026 · Mac

- Kết quả: ✅ xong, chỉ tài liệu, 0 code. Nhánh `feature/cluster-k-plan` (từ `deploy/staging` @ `f878ed65`), chưa commit.
- Nguồn: chủ dự án muốn chia cụm trước khi code vì 17 dòng `Ready for Dev` có cả tính năng mới; anh Thái nêu `wwwroot`
  chỉ nên chứa folder domain.
- Đã làm:
  - **Mới** `docs/next-session-clusters-K.md`: K0 → K7 + ★KR (15 issue lỗi/UI), S0 → ★SR (#185 bán theo tồn),
    trỏ Phần O cụm J cho #181; bảng fork phải hỏi.
  - `next-session-clusters-J.md`: Phần O mở lại theo #181 (BA xác nhận 11/10, 14 màn, có tạo/sửa, không Nháp); tách J-O3 / J-O4.
  - `pending-backlog.md` §1 + §3, compact summary §5 + §6, `next-session-repo-migration.md` §8.
- Phát hiện:
  - #139, #73, #37 **không phải đã fix chỉ cần sync**: tab `7. ISSUE HISTORY` ghi BA mở lại sau retest fail 11–12/10
    (Enter không gửi tìm kiếm ở Giao hàng và Lịch sử thanh toán; ngày ngược vẫn ra 0 dòng; H1 `payment-history` PC ≠ mobile;
    Top sản phẩm Báo cáo lộ mã nội bộ). Reconcile bằng `git log -S` + ledger là chưa đủ, phải đọc cả History.
  - `deploy/staging` có `f878ed65` (13/10): job CI gọi webhook aaPanel khi push. Câu "merge không tự deploy" có thể đã cũ.
  - Tab Tasks: STT 5 (controller Notification) và STT 7 (controller Ticket) trống cột trạng thái AI — chưa đối chiếu.
- Quyết định: bố cục `odoo19` trên máy UAT để anh Thái lo, chỉ ghi chú (compact summary §6, repo-migration §8) ·
  portal Vận hành mình làm.
- LIMIT: không đăng nhập được aaPanel trong phiên (bị chặn) ⇒ bố cục máy chủ ghi theo khảo sát 12/10, chưa đo lại ·
  chưa xem được kết quả chạy của job CI ⇒ chưa biết webhook có `-u` không.
- Nợ: báo anh Thái khoá webhook nằm thẳng trong file workflow · `/wujia-start` còn câu "merge không tự deploy" (sửa khi
  đã xác nhận job CI) · các nợ máy chủ của mục ADR-028 giữ nguyên.
- Phiên kế: **K0** — #139 + #73 + #37. Sửa Enter ở khuôn FilterBar dùng chung, hỏi BA cách hiển thị khi ngày ngược.

## K0 — #139 Enter + ngày ngược · #73 H1 Lịch sử thanh toán · #37 bỏ mã nội bộ · 14/10/2026 · Mac

- Kết quả: ✅ xong. PR #10 merge vào `deploy/staging` @ `319a16fb` (code `8c01ba9f`) · **đã lên UAT 14/10**, 9/9 module đúng
  version · đo lại trên UAT đạt · sheet: #139, #73, #37 → `Ready for Retest` (18 ô + 3 dòng History, kiểm `export?format=csv` theo ID).
  Bảng đo: `docs/k0-uat-measure.md`. Ledger + bảng đo ở nhánh `feature/k0-ledger`.
- Nguồn: ba dòng BA mở lại 11–12/10 (tab `7. ISSUE HISTORY`). Chủ dự án chốt: Enter = thử kỹ + thêm phòng thủ ·
  ngày ngược = một khối nhắc trung tính, Dev tự dịch · H1 = "Lịch sử thanh toán" ở cả hai khổ.
- Đã làm:
  - **#139 Enter** (2 seam chung, không vá từng màn): `wj_ajax_list.js` thêm `onKeydown` — Enter trong ô của form lọc ⇒
    `requestSubmit()`, bỏ qua khi đang gõ IME; `wujia_button_loading.js` khoá chống gửi lặp chỉ còn áp cho form không phải GET.
  - **#139 ngày ngược**: partial mới `wujia_portal_layout.wj_filter_invalid` + CSS `.wj-filter-invalid`; sáu màn có ô ngày
    (Giao hàng, Lịch sử đặt hàng, Thông báo, Thi, Bù hàng, Báo cáo) khi `filter_error` chỉ còn khối này ở thân — không số đếm,
    không EmptyState, không phân trang. Giao hàng có `view_state='invalid'` riêng.
  - **#73**: `ph_title` bản PC của `portal_debt_payment_history` "Debts" → "Payment history".
  - **#37**: `portal_product_name()` ở `portal_base/controllers/utils.py` (công tắc core `display_default_code=False`), thay 8 chỗ
    `display_name` ở Báo cáo, chi tiết đơn, chi tiết giao hàng, Bù hàng (template nhận qua `wj_pname`).
  - Bump patch 9 module · `?v=1339` → `1340` · 2 câu mới vào `.po` + `.pot` của layout.
- Số đo (script `k0_measure.py`, chromium, khổ 1440 + 390; "trước" = UAT bản `f878ed65`, "sau" = UAT bản `319a16fb`,
  DB copy `wujia_k0` cho cùng kết quả):

  | Hạng mục | Trước | Sau |
  |---|---|---|
  | Enter phím thật, 15 ô / 11 màn | 15/15 | 15/15 |
  | Enter ca đặc biệt (phím không kèm ký tự ×4, hai Enter liền, Enter khi lượt trước còn treo, ô ngày, NumpadEnter, IME) | 3/9 | 9/9 |
  | Ngày ngược 6 màn × 2 khổ × (URL, AJAX, sửa lại) | 11/34 | 34/34 (Thông báo mobile không có ô ngày ⇒ chỉ đo bước URL) |
  | Bấm nút Tìm kiếm ra cùng đường dẫn với Enter | chưa đo | 15/15 |
  | H1 `payment-history` PC / mobile | "Công nợ" / "Lịch sử thanh toán" | "Lịch sử thanh toán" cả hai · quét 23 route: 22 giống nhau |
  | Lượt xem còn mã sản phẩm `[TS-…]` | 8/32 | 0/32 |
  | Hồi quy 13 màn × 2 khổ (200, 0 lỗi JS, 0 tràn) | 26/26 | 26/26, cao thanh lọc 26/26 không đổi |

- Test: `-u` 20 module lệch version trên `wujia_k0` RC=0, 0 ERROR · 9 module đụng tới **1017 test 0 fail** (24 test mới) ·
  4 module portal còn lại 144 test 0 fail · `check_layers` 0 vi phạm · `msgfmt -c` sạch.
- Phát hiện:
  - Enter bằng phím thật **không tái hiện được lỗi** trên UAT mới; hỏng thật ở 2 đường: phím không kèm ký tự (công cụ test,
    CDP) và Enter lần hai khi lượt một chưa về (bị khoá nuốt, ô tìm bị ghi đè về từ khoá cũ).
  - Thông báo mobile không có ô ngày ⇒ ngày ngược qua URL hiện khối nhắc "Sửa Từ ngày…" mà không có ô để sửa (thoát bằng chip).
    Lệch PC/mobile này có từ trước, chạm FB-10.
  - UAT: URL lạ dưới `/portal/…` trả **500** (local trả 404); `/khong-co-…` ngoài `/portal` vẫn 404. Chưa rõ nguyên nhân.
  - `wujia_vr` (DB mẫu duy nhất trên Mac) đứng ở layout `60.4.0` ⇒ DB copy phải `-u` 20 module trước khi đo.
  - **Merge vào `deploy/staging` CÓ tự deploy và CÓ `-u`**: job "Triển khai Staging" của run `38509363758` chạy đạt ngay sau
    merge, ~1 phút sau XML-RPC đọc 9/9 module đã ở version mới mà không ai bấm *Deploy latest*. Câu "merge không tự deploy" đã cũ.
  - `/portal/info-request`: H1 PC "Yêu cầu cập nhật thông tin" ≠ mobile "Cập nhật thông tin" — cùng họ lỗi #73, route ngoài
    bảng đặt tên, đã ghi vào LIMIT của #73 chờ BA cho tên.
  - BA thêm **#189 `UI-FILTERCHIP-001`** (Low, `Ready for Dev`) trong lúc phiên chạy: dải chip lọc mobile cuộn ngang không có
    dấu hiệu. Chưa xếp vào phiên nào của cụm K.
- LIMIT: webkit/firefox chưa đo (máy chỉ có chromium) · câu chữ khối nhắc do Dev đặt, chờ BA duyệt · H1 PC lệch Figma v1.1
  ở dòng tiêu đề theo chốt chủ dự án · chip / select / phân trang không đo lại riêng (không sửa, dựa vào test tự động).
- Việc dở: merge nhánh `feature/k0-ledger` (chỉ tài liệu: ledger, bảng đo, nhật ký).
- Nợ: báo anh Thái khoá webhook nằm trong file workflow · sửa câu "merge không tự deploy" trong `/wujia-start` ·
  lỗi 500 của URL lạ dưới `/portal` trên UAT · ô ngày cho Thông báo mobile + tên trang `/portal/info-request` (chờ BA) ·
  xếp #189 vào cụm K.
- Phiên kế: **K1** — #187 · #188 · #186 form Hỗ trợ.

## K1 — #187 form Hỗ trợ một cấu hình · #188 nhãn + lỗi có aria · #186 thẻ thông tin ticket · 14/10/2026 · Mac

- Kết quả: ✅ xong. PR #12 merge vào `deploy/staging` @ `00e9443f` (code `842b4ffc`) · **đã lên UAT 14/10** (CI tự `-u`),
  `wujia_portal_layout` 19.0.60.14.0 · `wujia_portal_support` 19.0.5.4.0 · đo lại trên UAT đạt. Bảng đo: `docs/k1-uat-measure.md`.
  Ledger + bảng đo ở nhánh `feature/k1-ledger`.
- Chủ dự án chốt 14/10: bỏ dòng Cửa hàng ở chi tiết cả hai khổ · một bộ nhãn theo PC cho form + chi tiết · ý "lỗi đọc được
  bằng trình đọc màn hình" của #188 làm luôn, không ghi LIMIT.
- Đã làm:
  - **Khung** (`wujia_portal_layout`): `static/assets/js/wj_form_validate.js` — form có `data-wj-validate` ⇒ `noValidate`,
    submit (capture) control sai ⇒ `aria-invalid` + hiện `#<id>-err` + nối `aria-describedby`, focus ô đầu, chặn submit +
    `wj:form:release`; `input`/`change` tự gỡ. Partial `wj_field_error` (`fe_for`, `fe_msg`, `fe_show`). CSS `.wj-field-error`
    màu `--wujia-danger-text` + viền `[aria-invalid]`. `?v=1341`.
  - **Form** (`portal_support`): nhãn + câu lỗi `t-set` một lần, hai khổ cùng đọc; Phân loại option rỗng đầu + `required`;
    Mức độ lặp `priority_options` (từ `PRIORITY_LABELS`) ⇒ `normal`/`urgent`; PC id `wj-sup-pc-*` + `label for`; template con
    `portal_support_form_alert` (`role=alert`) gọi ở hai khổ; controller `ERROR_FIELDS` đánh dấu sẵn ô theo mã lỗi.
  - **Chi tiết**: `_ticket_meta()` + `META_LABELS`/`META_EMPTY` (`_lt`), PC `<dl>` và mobile cùng lặp `meta`; bỏ Cửa hàng;
    mọi `.strftime` trong file → `wj_dt` (`fmt_local_dt`) — trước lệch −7 giờ.
  - `.po` + `.pot` dựng lại theo export Odoo (7 câu mới), `msgfmt -c` sạch.
- Số đo (UAT sau deploy, chỉ đọc; tạo ticket chỉ trên DB copy):

  | Hạng mục | Trước | Sau |
  |---|---|---|
  | Phân loại mở ra trống + bắt buộc (PC / mobile) | chọn sẵn / trống | trống + `required` cả hai |
  | Mức độ (PC / mobile) | 2 / 3 (2 cái cùng `urgent`) | 2 / 2, `normal` mặc định |
  | Control PC có `id` + `label[for]`, bấm nhãn → focus | 0/6 | 6/6 |
  | Gửi trống: `aria-invalid` + câu lỗi + focus, nút không kẹt | bong bóng trình duyệt | đạt hai khổ |
  | Lỗi máy chủ `role=alert` | chỉ mobile, không aria | hai khổ, ô liên quan đánh dấu |
  | Thẻ thông tin PC = mobile (đã giải quyết + mới) | lệch 4 dòng | trùng 6/6 dòng |
  | Tràn ngang 3 URL × 10 khổ · lỗi JS | 0 · 0 | 0 · 0 |
  | Hồi quy 4 màn form × 2 khổ | — | 8/8 |

- Test: `-u` layout + support + portal_base, 4 tag ⇒ **698 test 0 fail** (14 mới `test_k1_form_detail.py`, tag
  `wujia_support_k1`); sửa `test_jv7_i18n.py` theo nguồn nhãn mới; `test_scan_d5_data_list` 13 → 10 hàng mdash tĩnh.
  `check_layers` 0 vi phạm tầng.
- Bẫy gặp: test sửa `resolved_date` bằng SQL phải `env.flush_all()` trước — `invalidate_recordset()` flush `write()` đang chờ
  *sau* câu SQL và ghi đè. Babel bắt nhầm msgid khi `_lt` lồng trong alias `_` cục bộ ⇒ đặt tên alias `tr`.
- LIMIT / ngoài phạm vi: gợi ý file mobile "tối đa 5 tệp" ≠ máy chủ 6 (chờ BA) · chip Mức độ mobile `d-none` ⇒ không đi được
  bằng Tab · nhánh `t-elif="franchises"` của form mobile đã chết · ticket mẫu 00013 trên UAT có `resolved_date` sớm hơn
  `create_date` 12 giờ (dữ liệu seed) · #189 chưa xếp phiên.
- Việc dở: merge nhánh `feature/k1-ledger` (chỉ tài liệu). DB `wujia_k1` + filestore đã xoá.
- Phiên kế: **K2** — #182 Shared Form Validation (mở rộng `wj_form_validate.js`: Error Summary, giữ dữ liệu, `return/new`).

## K2a — #182 Shared Form Validation: khung + Hỗ trợ + Đổi trả + Khắc phục · 14/10/2026 · Mac

- Kết quả: ✅ code + test + đo trên DB copy. PR #14 (`feature/k2-form-validation` @ `4ac86ac3`) **chưa merge — chủ dự án
  chốt để K2b**: K2b làm xong thì merge một lượt, đo UAT một lần, rồi mới ghi ledger. #182 trên sheet giữ `Ready for Dev`
  / `Dev In Progress`, chưa `qa_sync`.
- Chủ dự án chốt 14/10: phạm vi K2a = khung + `support/new` + `return/new` + Khắc phục; K2b = `info-request`,
  `change-password`, `exam/register` · Error Summary = hộp đỏ nhạt + danh sách link · Khắc phục (module anh Thái, được
  phép sửa) **luôn bắt buộc ảnh**, bỏ qua cờ `require_evidence_if_fail`.
- Đã làm:
  - **Khung** (`wujia_portal_layout` 19.0.60.15.0, `?v=1342`): partial `wj_error_summary` (`role=alert`, tiêu đề dịch có
    `{n}` qua `data-wj-msg-title`). `wj_form_validate.js` dựng danh sách "Nhãn: câu lỗi" + link focus ô; luật tệp
    `data-wj-min-files` / `-max-files` / `-max-mb` / `-total-mb` + `data-wj-total-group` + `accept` qua `setCustomValidity`;
    `data-wj-focus` cho input file ẩn sau vùng kéo thả; lỗi server render sẵn ⇒ tự nối aria + dựng hộp + focus.
    CSS `.wj-error-summary` dùng token `--wujia-danger-*`.
  - **Hỗ trợ** (19.0.5.5.0): POST lỗi ⇒ `_render_form(error, post)` tại chỗ (bỏ redirect `?error=`; GET `?error=` giữ cho
    link cũ). Bind lại mọi ô; `missing_fields` chỉ đánh dấu ô thật sự trống. Ô tệp mang `MAX_FILES=6`, `MAX_FILE_MB=5`.
  - **Đổi trả**: `wujia_return` (19.0.2.1.1) thêm `ReturnPortalError(ValidationError)` có `field`; mọi luật portal ném kèm
    tên ô. `portal_return` (19.0.5.5.0) bắt lỗi ⇒ đánh dấu đúng ô (cửa hàng ⇒ banner vì mobile 1 cửa hàng là input ẩn), bind
    lại mọi giá trị, select dòng sản phẩm chọn lại qua `data-selected`; ô ảnh/video mang hằng của model.
  - **Khắc phục** (`portal_inspection` 19.0.1.8.1): server trả JSON lỗi khi không có ảnh mới lẫn ảnh cũ; form có `*`,
    `required`, lỗi inline dưới vùng tải ảnh (Enter/Space mở được); bỏ popup "ghi chú hoặc ảnh".
  - i18n `vi_VN.po` + `.pot` (layout, portal_return) merge theo khối, `msgfmt -c` sạch.
- Số đo (DB copy `wujia_k2`, Chromium, 992/1024/1440/360/390/430, vi_VN + en_US):

  | Hạng mục | Kết quả |
  |---|---|
  | Gửi trống: hộp tổng hiện + link nhảy đúng ô + focus ô đầu + aria (Hỗ trợ 2 ô, Đổi trả 5 ô) | 12/12 lượt |
  | Sửa một ô ⇒ hộp tự đếm lại | đạt |
  | Lẫn ngôn ngữ en/vi | 0 |
  | Đổi trả chọn 2 ảnh ⇒ chặn trước POST, giữ SL + ghi chú; đủ 3 ảnh ⇒ ô ảnh hết lỗi | 6/6 khổ |
  | POST bỏ qua client (Hỗ trợ thiếu tiêu đề, Đổi trả thiếu đơn) ⇒ 200, giữ giá trị, đánh dấu ô | đạt |
  | Khắc phục không ảnh: chặn client (1440/390) + server JSON lỗi; có ảnh ⇒ `remediated` | đạt |
  | Hồi quy 6 màn × 2 khổ: 200 · tràn ngang · lỗi JS | 12/12 · 0 · 0 |

- Test: `-u` 6 module + full test ⇒ 832 test, 1 fail có sẵn từ K1 (`test_split_ownership` thiếu view
  `portal_support_form_alert`) — sửa, chạy lại 0 fail. Mới: `test_k2_form_validation.py` (support 3, return 4, tag
  `wujia_support_k2` / `wujia_return_k2`) + `test_portal_error_names_the_field`. Test K1 sửa theo render tại chỗ.
  `check_layers` không thêm vi phạm (R7 2 dòng có sẵn ở `wujia_franchise`).
- Bẫy gặp: `<textarea t-out="x"/>` với `x` None ⇒ QWeb **bỏ hẳn thẻ** (ô Mô tả/Ghi chú biến mất) — dùng `x or ''`.
  `values.setdefault(...)` làm dict luôn truthy ⇒ phải lấy cờ `posted` trước. Câu có `t-out` lồng trong `t-set` bị export
  thành mảnh ⇒ dựng câu có tham số ở controller (`request.env._`).
- LIMIT (K2b xử lý cái nào cần): không điền lại được `input[type=file]` sau lỗi server · câu tiếng Việt cứng sẵn có trong
  module Khắc phục · th/zh chưa dịch · webkit/firefox chưa đo · nhãn mobile Đổi trả cho ô ảnh/video vẫn là `aria-label`.
- DB `wujia_k2` (đã `-u` K2a, có 1 phiếu kiểm tra mẫu HCM-01) **giữ lại cho K2b**; xoá khi K2b xong.
- Phiên kế: **K2b** — `info-request`, `change-password`, `exam/register` trên cùng nhánh/PR #14 → merge → đo UAT → ledger.

## K2b — #182 Shared Form Validation: Cập nhật thông tin + Đổi mật khẩu + Đăng ký thi · merge + UAT · 14/10/2026 · Mac

- Chủ dự án chốt 14/10: **không điền lại ô mật khẩu** sau lỗi máy chủ (ghi LIMIT cho BA).
- Đã làm (commit `054abfea`, merge PR #14 `e61baf83` cùng K2a):
  - **Khung** (`wujia_portal_layout` 19.0.60.16.0, `?v=1343`): luật `data-wj-match="<id>"`; phạm vi kiểm là form
    `data-wj-validate` hoặc khối `data-wj-validate-scope`; API `window.wjFormValidate.check(root)` (đánh dấu + hộp tổng +
    focus, trả số ô sai) / `reset(root)` cho wizard gửi JSON không có `<form>`.
  - **Cập nhật thông tin** (19.0.3.4.0): `InfoRequestFormError(ValidationError)` mang `errors` {ô: câu}, `_parse_payload` gom
    mọi lỗi một lượt; `field_target` chỉ `required` khi chọn Khác; ô tệp `accept` + 6 tệp × 5 MB.
  - **Đổi mật khẩu** (layout): controller trả `field_errors` {old, new, confirm} (trống / < 8 / trùng cũ / lệch / sai cũ);
    PC + mobile `data-wj-validate`, ô nhập lại `data-wj-match`; không render lại mật khẩu.
  - **Đăng ký thi** (19.0.7.5.0): modal PC + bước 3 mobile gọi `wjFormValidate.check`; phone `pattern`
    `(0|\+84)[0-9]{8,10}`; mobile gán id/nhãn theo người ("Nhân sự n — …"). Nhãn "Họ và tên" thống nhất PC/mobile.
- Test: 534 test (7 module) + 508 test (portal phụ thuộc) 0 fail; mới `test_k2_*` (info_request 4, layout 3, exam 2).
- UAT (sau deploy, 7/7 version khớp; chỉ gửi form thiếu, không tạo bản ghi, không đổi mật khẩu, thi không bấm gửi):
  5 form × 6 khổ × vi_VN/en_US đạt hộp tổng + link + focus + aria; bypass máy chủ 4/4 giữ giá trị; hồi quy 16/16 · 0 tràn ·
  0 lỗi JS. Đối chiếu *Kết quả mong muốn* ≈ 94 % (loading khi gửi hợp lệ chưa đo trên UAT). Bảng: `docs/k2-uat-measure.md`.
- Bẫy gặp: `-u` không ghi đè bản dịch đã nạp ⇒ sửa `.po` của msgid đã có trên DB copy phải `--i18n-overwrite` (UAT nạp mới
  nên không cần). Harness đổi ngôn ngữ ngay sau login (webclient `/odoo` còn bắn RPC nền) có lúc mất — rời `/odoo`
  (`about:blank`) rồi mới gọi `/portal/set-lang`, kiểm `<html lang>`.
- LIMIT: ô tệp không điền lại · mật khẩu không điền lại (chốt) · th/zh chưa dịch · câu Việt cứng ở Khắc phục · Khắc phục chưa
  đo trên UAT · chỉ Chromium · ảnh/video Bù hàng mobile dùng `aria-label`.
- Phiên kế: **S0** — #185 WJ-ORD-033 thiết kế bán theo tồn (theo thứ tự `next-session-clusters-K.md`).

## K3 — #175 WJ-RETURN-002 Đổi trả: Home + danh sách + chi tiết · merge + UAT · 14/10/2026 · Mac

- Chủ dự án chốt 14/10: chi tiết PC một cột · số lượng bỏ số 0 thừa · bộ câu thiếu dữ liệu đề xuất.
- Đã làm (commit `61c2971d`, merge PR #15 `a8347586`): `wujia_return` 19.0.2.2.0 (`_portal_recent_domain` loại Nháp,
  `_portal_qty_label()`), `wujia_portal_base` 19.0.7.49.0 (Home bỏ "Total: —", thêm Sản phẩm · SL, sắp ngày + id),
  `wujia_portal_return` 19.0.5.6.0 (danh sách bỏ cột Cửa hàng; chi tiết PC/mobile chung nhóm `wj-ret-g--*`, bỏ Cửa hàng,
  tách ghi chú và phản hồi; template `portal_return_feedback_body`, `portal_return_photo_count`).
- Test: 611/611 (7 module) trên DB copy `wujia_k3`; mới `test_k3_return_content.py` (4 test, user khoá `en_US`).
- UAT (3/3 version khớp, chỉ đọc): Home + danh sách HCM-01/HN-01 × 390/1440, chi tiết 6 phiếu × 6 khổ: đúng nhóm, không
  cửa hàng, 0 tràn, 0 lỗi JS. Ledger #175 ghi kết quả đo (không tách file đo riêng).
- Nhánh: đã xoá các `feature/*` đã merge (máy + GitHub); `main` = `deploy/staging`. Từ K3 làm thẳng trên `main`.
- LIMIT: câu thiếu dữ liệu chờ BA sửa chữ · th/zh chưa dịch · UAT chưa có phiếu có ảnh/video của HCM-01.
- Phiên kế: **S0** — #185 WJ-ORD-033 hoặc **K4** theo `next-session-clusters-K.md`.

## KT — #191 · #193 · #73 · #83 Cụm chữ + header màn chi tiết · merge + UAT · 16/10/2026 · Mac

- Chủ dự án chốt 16/10: phạm vi toàn cụm chữ + header; thang chữ thân lấy số #183 (ghi LIMIT xin BA); header mobile giữ 44/8 +
  18/24 theo #143, hỏi BA (không sửa code).
- Đã làm (commit `306ccfac`, merge PR #17 `72c47095`):
  - **Token vai trò** `--wj-t-*` ở `_variables.css` (name 15/600 · label 12/500 · value 14 PC / 13 mobile · body 15/14 · caption 12 ·
    code 20/18) + class `.wj-t-*`; `--wj-lc-*` (ListCard #183) trỏ sang ⇒ một nguồn số.
  - **#191**: Giao hàng/Đổi trả/Hỗ trợ/Thông báo/Kiến thức/Thi/Sản phẩm/Lịch sử chuyển sang token, 0 chữ thông tin < 12px;
    Giao hàng mobile `sectiontop` → `wj_card_header`; Sản phẩm bỏ `<h3>` tên lặp; Kiến thức `ph_title` = tên bài, bỏ
    `h1.article-title`, heading trong nội dung hạ về 15.
  - **#193**: chi tiết Thi PC dùng `wj_page_header` back, badge trạng thái vào kv grid; Kiến thức bỏ nút "Back to library".
  - **#73/#83**: Lịch sử PC bỏ số ở PageHeader; đếm "đơn hàng"/"yêu cầu" theo `total_items` sau lọc (Hỗ trợ, Đổi trả, Lịch sử).
  - `wujia_portal_purchase_history` 19.0.4.3.0 **post-migrate** chỉ đổi term vi `order/orders` → "đơn hàng" (`update_field_translations`).
- Test: DB copy `wujia_kt` (từ `wujia_k3`, phải `-u wujia_core,wujia_delivery` trước vì Thái thêm cột) — 1203 test, sửa 2 bảng
  đếm call site rồi chạy lại xanh; layout 296, exam 53, purchase_history 64. Guard mới `test_kt_typography`.
- UAT (10/10 version, `?v=1344`, chỉ đọc): 8 màn × 8 khổ vi = 64/64 một H1 · 0 < 12px · 0 tràn · 0 lỗi JS; en 390/1440 đạt
  (1 ô lỗi harness). Sheet 4 issue `Ready for Retest` (đã verify CSV). Bảng: `docs/kt-uat-measure.md`.
- Bẫy gặp:
  - **Term QWeb là cả thẻ inline**: `<span class="x">Status</span>` cạnh span `t-out` ⇒ msgid phải là nguyên chuỗi span, msgid
    "Status" trần không ăn (im lặng). Kiểm bằng `field.get_trans_terms(arch)` trong `odoo shell`.
  - **Đổi msgstr của term đã nạp trên UAT**: `-u` giữ bản cũ ⇒ cần post-migrate nhắm đúng term, không `--i18n-overwrite` cả module.
  - `/xmlrpc/` UAT trả 403 từ 15/10 ⇒ kiểm version bằng JSON-RPC `/web/dataset/call_kw` sau login Playwright.
  - Log Odoo local nay ở `logs/<năm>/<tháng>/<ngày>.log` (không còn `logs/odoo.log`).
  - Thái thêm commit lên `deploy/staging` 15–16/10 (`base_user_role`, Fleet/Delivery BE-002/003, BE003-PERF).
- LIMIT: thang chữ theo #183 chờ BA xác nhận · header mobile 44/8 vs 52/12 · mobile giữ số đếm Lịch sử · tên `/portal/info-request`
  · `<h3>` trùng tên trong nội dung bài ui12-01 (chờ BA sửa bài / cho tự ẩn) · câu Anh sẵn có ở chi tiết Thi · zh/th chưa đo.
- Phiên kế: **K4** — #178 Giao hàng (hoặc **S0** #185) theo `next-session-clusters-K.md`.

## KT2 — nội dung Home/danh sách/form theo thang chữ + lập cụm TS · 16/10/2026 · Mac

- Chủ dự án (ảnh Home mobile): mã SO to hơn dòng khác, hai dòng Kiến thức như khác cỡ ⇒ làm lại hết nội dung, **đo từng màn**.
- Đo UAT (chỉ đọc) 31 màn × 390/1440: 17 màn có chữ < 12px (KPI Home 9, chip lọc mobile 11.3, cả cụm Công nợ 11–11.5,
  gợi ý form 11, nhãn form 11.9, badge 11, lịch Thi 11, trục biểu đồ 9/11); cùng vai trò khác cỡ (dòng Home 13/15/16, tên
  sản phẩm 14, nhãn form 11.9/13/14, Tài khoản 13/14 và 12/16). Hai dòng Kiến thức thật ra cùng 13 (một dòng viết hoa).
- Đã làm (commit `4915777e`, merge PR #20 `7636d929`, CI deploy xanh): dòng Home một cỡ tên 15/600, dòng phụ caption 12, nhãn KPI 12
  (320 xuống 2 dòng, số vẫn thẳng); sàn 12px toàn CSS portal (miễn chấm đếm, icon, chrome header); nhãn/giá trị Tài khoản,
  Công nợ, Báo cáo, Thi, thẻ KPI về label/value; nhãn ô nhập mọi form = cỡ value + 600; Công nợ thẻ tổng/ngân hàng `height` →
  `min-height` (chữ 12 làm tràn 5px). `?v=1345`, 10 module bump.
- Test DB copy `wujia_kt`: 1205 test, 3 test cũ ghim 11/11.5px → sửa, chạy lại 740/740. Guard mới: sàn 12px toàn portal,
  dòng Home cùng cỡ tên. Playwright 30 màn × 8 khổ = 240/240: 0 < 12px, 0 tràn, 0 lỗi JS, 0 khung cắt chữ.
- Chủ dự án chốt: làm **thang chữ một nguồn ở base**, chia nhiều phiên. Trang xem thử cho BA chốt số:
  <https://claude.ai/artifact/B3TgSv8yDKawdBxYxcPpp4>. Plan: `docs/next-session-typescale.md`; bộ đo `scripts/qa/wj_type_audit.py`.
- UAT (chỉ đọc): 10/10 version, `wj_type_audit.py screens` 30 màn × 360/390/1440 = 90/90 sạch; dòng Home 15/600, nhãn KPI 12.
- LIMIT: số KPI còn khác nhau (mobile 22/25/20, PC 28/26/24) — TS áp một cỡ · ledger/sheet chưa ghi, gộp vào TS7.
- BA gửi thang 16/10: bản 1 giữ nguyên đề xuất, rồi **bản 2 đổi 9/12 vai trò** (thay bản 1; nguyên văn §7 `next-session-typescale.md`).
  Chủ dự án chốt áp nguyên bản 2. Ghi chú ledger ở TS7: bản 2 khác số của #143 (tiêu đề nhóm mobile 18) và #183/KT (tên dòng 15).
- Phiên kế: **TS0** theo `next-session-typescale.md` (PR #20, #21 đã merge).

## TS0 — thang chữ bản 2 một nguồn ở base · 16/10/2026 · Mac

- Kết quả: ✅ code + test + đo DB copy; PR chờ chủ dự án duyệt merge (chưa lên UAT).
- Chủ dự án chốt 16/10: CardHeader hai bậc cùng vai trò `card`; **Q1 giữ `html` 14px mọi khổ** — đo thực tế Vuexy
  `components.css` (nạp sau) đã ép 14 ở 390/800/1440, rule 14/15/16 của `_variables.css` chưa từng ăn.
- Đã làm (`wujia_portal_layout` 19.0.60.19.0, `?v=1346` cho 3 file CSS):
  - `_variables.css`: đủ 12 vai trò `--wj-t-*` theo bản 2 BA (PC ở `:root`, mobile ở khối <992); thêm `page/section/card/
    kpi/button/chip` + `--wj-t-heading-fw`, `--wj-t-code-fw`; `--wujia-m-sechead-*` thành alias của `section`.
  - PageHeader / SectionHeader / CardHeader (PC + mobile) đọc token, giữ selector + `!important`; thêm class `.wj-t-page/
    -section/-card/-kpi/-button/-chip`; chip lọc mobile `label` → `chip`.
  - `scripts/qa/wj_type_audit.py` tách `count_css()`; baseline `docs/typescale/css-baseline.json`; test
    `test_ts0_type_scale` (số bản 2, header đọc vai trò, `html` 14, **chặn tăng** chữ/icon/chấm đếm gõ cứng theo file).
  - Test cũ theo số mới: `test_g1_mobile_density` (sechead alias, `--any` đọc section), `test_i10`/`test_e5` (ListCard
    mobile tên 13/18, nhãn 13).
- Đổi nhìn thấy được (đo `wj_type_audit screens`, 30 màn × 8 khổ, `wujia_kt` trước ↔ `wujia_ts0` sau):
  tiêu đề trang 26/22 → 24/20 · nhóm 22 PC/18 mobile → 18/16 · thẻ 18 PC/16 mobile → 17/15 · mã chứng từ 20/18 → 16/14 ·
  đoạn văn 15/14 → 14/13 · tên dòng mobile 15 → 13 (ListCard, dòng Home, sản phẩm, Báo cáo) · nhãn mobile 12 → 13 (ListCard,
  KPI, Tài khoản, Công nợ, chi tiết). Chip lọc mobile giữ 12.
- Số đo: `wujia_portal_layout` 303/0/0 · cả portal 1210/0/0 (DB copy `wujia_ts0`) · mutation thêm 1 `font-size: 13px` ⇒ đỏ
  đúng 1 subtest · gõ cứng chữ 426 → 418, token 126 → 137 · 240/240 ô: 0 chữ < 12px, tràn 0 → 0, lỗi JS 0 → 0, khung cắt
  chữ 141 → 132 (giỏ mobile giảm, không ô nào tăng) · Khảo sát 390/768 chỉ đổi tiêu đề trang 22 → 20, không tràn, 0 lỗi JS.
- Còn lệch, để phiên sau: CardHeader PC giữ số riêng ở màn (Thi 16 · Cập nhật thông tin/Kiến thức/Sản phẩm liên quan 18) →
  TS3–TS5; chip PC 13 (base) → TS1; tiêu đề chi tiết Thông báo PC đọc `code` (20 → 16) — xem lại vai trò ở TS5.
- Nợ: ledger/sheet gộp TS7 (Q7: #143 nhóm mobile 18, #183/#191 tên dòng 15 khác bản 2).
- Chủ dự án chốt cuối phiên: **chỉ push, không merge** — PR #22 mở suốt cụm, deploy một lần ở TS7.
- Phiên kế: **TS1** (`_components.css` + `_pc_components.css`) làm tiếp trên `feature/ts0-type-tokens` (merge
  `origin/deploy/staging` trước), DB copy `wujia_ts0`.
