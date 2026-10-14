# Tồn đọng toàn dự án WujiaTea — gom 05/10/2026

Một chỗ duy nhất liệt kê mọi việc còn treo, chia lô làm dần. Mỗi phiên: làm lô đầu bảng "Thứ tự làm", xong thì gạch ở đây +
ghi `f-progress.md`. Nguồn gom: compact summary §5, `f-progress.md` (mục Nợ), chapter 74/77/78, `next-session-clusters-{H,J}.md`.

## 1. Thứ tự làm (chủ dự án chốt 04–05/10, sắp lại 07/10)

> 07/10: cụm J Phần B + T + V **xong, đã lên UAT** (END-SPRINT 66, chapter 79 + 80). Phần O **pend theo ý BA**.
> Issue List: 15 Ready for Dev gom thành **cụm I mở rộng** (11 phiên + ★IR), rồi cụm H.
> 14/10: cụm I xong (END-SPRINT 67). Issue List có 17 Ready for Dev ⇒ **cụm K** + 2 tính năng (#185, #181 — Phần O mở lại).

| # | Lô | Nội dung | Số phiên | Plan |
|---|---|---|---|---|
| ~~1~~ | ~~Phần V~~ ✅ 07/10 | Việt hoá source V0…V8b + ★VR — ch.79 | — | `next-session-clusters-J.md` §6 |
| ~~2~~ | ~~J-T4 · J-T5 · J-T5b~~ ✅ 07/10 | Nhập/xuất `.po` + dịch máy DeepL (key thật đã chạy trên UAT) — ch.80 | — | `next-session-clusters-J.md` §6b |
| ~~3~~ | ~~Issue List — cụm I mở rộng~~ ✅ 10/10 | I1 → I13 + ★IR, 21 issue — ch.81 | — | `next-session-clusters-H.md` §2–3 |
| **1** | **Issue List — cụm K** (lập 14/10) | 17 `Ready for Dev`: K0 #139+#73+#37 (BA mở lại) → K1 #187+#188+#186 → K2 #182 → K3 #175 → K4 #178 → K5 #177+#176 → K6 #179+#180 → K7a/b #183+#184 → ★KR | 10 | `next-session-clusters-K.md` |
| 1b | Tính năng #185 bán theo tồn | S0 thiết kế → S1 → S2 → ★SR, xen kẽ cụm K | 4 | `next-session-clusters-K.md` §2 |
| 1c | J-O0…O4 + ★JR | Portal Vận hành — **mở lại 14/10** theo #181 WJ-OPS-001 (14 màn), xen kẽ cụm K | 6 | `next-session-clusters-J.md` §5 |
| 2 | Cụm H | Chuẩn hoá component lượt 2 (H0, H1, H3 → ★HR-1 chờ BA 19 câu → H4–H10 → ★HR-2; H2 đã gộp vào I10; H9 FormField gộp vào K2) | 10 | `next-session-clusters-H.md` |

Issue List vẫn là task thường trực: đầu mỗi phiên chạy `issue_queue.py --dev`; issue **Retest Failed** / Severity High mới thì báo
chủ dự án trước khi làm lô kế.

## 2. Chờ lệnh chủ dự án (làm được ngay khi có lệnh)

- [x] ~~Commit + deploy J-B1/B2, J-T1…T5, J-V0…★VR, top bar 992 (`bea5fa8`)~~ — kiểm chỉ-đọc UAT 07/10: `wujia_core` 19.0.2.1.1 ·
      `wujia_portal_layout` 19.0.60.4.0 · `wujia_portal_base` 19.0.7.37.1 · `wujia_portal_sale` 19.0.5.1.1 · `wujia_i18n` 19.0.1.3.0 — khớp repo.
- [ ] **Tool dịch — chuỗi code th/zh**: nút "Export .po for code strings" (th còn 276 chuỗi `_()` chờ) → commit → `-u wujia_i18n` + restart;
      sửa tay 2 câu dịch máy bị chặn (zh exam QWeb "HTML tags changed", th sale `On %s`).
- [ ] Gửi BA 1 361 cặp câu + gửi anh Thái 284 chuỗi + lỗi `.po` `web_survey_ui` (`docs/i18n-review/`).

## 3. Chờ BA / chủ dự án trả lời

| Chủ đề | Câu hỏi | Chặn lô |
|---|---|---|
| ~~Phần V~~ | ✅ chốt 05/10 (§6 plan J): JS qua `data-wj-msg-*` · mặc định vi_VN · bật hết vi/en/th/zh · EN không cần BA duyệt, ZH/TH DeepL — **gửi BA 1 danh sách câu cần sửa ở ★VR** | — |
| Vận hành (**BA trả lời 11/10 bằng #181**) | Phạm vi MVP + 2 gói mockup FINAL đã có. Còn phải soi ở J-O0: Staff xem gì · gắn nhân viên ↔ tài khoản portal · lệch spec mục G ↔ backend · luật portal đặt ở module anh Thái | J-O1 |
| Dịch tự động | ~~key DeepL~~ ✅ đã nhập UAT, smoke thật 07/10 đạt · **ai rà bản th/zh** | rà bản dịch máy |
| ADR-027 | 7 câu hỏi BA (chapter 74 §Câu hỏi) | áp `auto_install` |
| Chuẩn component | 19 câu "CẦN BA CHỐT" (`ba-component-spec-proposal.xlsx`) + gửi 2 PDF chuẩn component | cụm H |
| Issue #146 (G4) | Routing `/` — BA đã xoá dòng khỏi sheet, chờ BA mở lại | — |
| UAT dữ liệu | Bảng giá UAT đang USD — đổi VNĐ? · cột R sheet 6 dòng | — |
| BA retest | 11 ID Ready for Retest từ cụm G (theo dõi qua `issue_queue`) | — |

## 4. Nợ kỹ thuật (xếp vào phiên gần nhất cùng module)

- [ ] Áp `auto_install: True` cho module ghép thuần (`portal_report`, `portal_purchase_history`, `portal_delivery`, 3 mobile Thái) — 1 phiên, sau 7 câu ADR-027.
- [ ] Nợ chapter 77: ghi trực tiếp ở `portal_sale` (chuyển về L2) · `_sql_constraints` cũ → `models.Constraint` · tài liệu bàn giao Thái.
- [ ] 2 error fixture có sẵn trong suite `wujia_sale`.
- [x] ~~`lang.js` code chết~~ — xoá ở J-V1 (+ khối ví/đầu tư trong `my_js.js`, `overview_member.js`, `extensions/i18n.js`).
- [ ] ★VR gom: template `signup_form`/`signup` + `forgot_pass_back` (`wujia_portal_layout`, tiếng Anh, không route nào render) ⇒ xoá ·
      gallery dev `/portal/_pc-preview` còn ~19 nhãn kỹ thuật tiếng Anh (chỉ nhân viên nội bộ) ⇒ để nguyên ·
      404 `/vi/app-assets/data/locales/en.json` (i18next của Vuexy `app.js`, có từ trước) ⇒ no-op sớm hơn.
- [ ] `@route(type='json')` deprecated (Odoo 19 ⇒ `jsonrpc`) ở 5 controller portal (exam, info_request, knowledge, notification, sale) + `wj_ks_dashboard_ninja` — gộp vào phiên V cùng module (`wujia_franchise_inspection` là của Thái).
- [ ] `check_layers.py`: 3 module chưa phân tầng (`wujia_audit`, `wujia_fields_value`, `wujia_metabase_connector`) · R7 ×2 trong `wujia_franchise` (Thái).
- [ ] Tool dịch: vi_VN báo "chưa dịch" với câu gốc đã là tiếng Việt (tự hết sau Phần V) · chuỗi code chỉ áp sau xuất `.po` + restart (J-T4).
- [ ] Token `--wujia-kpi-separator-*` còn trong layout · FYI BA về màu thanh tiến độ/pill vai trò (từ G3a).
- [ ] Safe area chưa đo iPhone thật · nhánh Đặt hàng không có danh mục chưa đo trình duyệt.

**Code của Thái — chỉ báo, không sửa:** 284 chuỗi VN viết cứng (lọc `owner=Thái` trong `vn-hardcode-inventory.csv`) · chart Khảo sát
`#28A9DF` chưa theo màu brand (`wujia_portal_inspection`) · `.po` của `wujia_franchise_inspection` lỗi "unknown occurrence:
web_survey_ui" · `msgid ""` rỗng ở `wujia_franchise_inspection.py:1725` · test `wujia_franchise` import file đã xoá (vì vậy không
`-u wujia_core --test-enable` trên DB đủ module).

## 5. Dọn máy local (không ảnh hưởng UAT)

- [ ] Khôi phục filestore local (`scripts/dev/filestore_pack.py` máy còn filestore → `filestore_restore.py` trên Mac).
- [ ] Xoá DB nháp: `wujia_b1`, `wujia_b1t`, `wujia_b2`, `wujia_b2h`, `wujia_b2t`, `wujia_b2u`, `wujia_t1t`, `wujia_v0t`, `wujia_v1t`, `wujia_v1b`
      (**giữ `wujia_t1`** tới hết Phần V — mốc `docs/i18n-baseline/vi_VN.json` đo trên nó) + các DB đo cũ
      (`wujia_e4*`, `wujia_f*`, `wujia_fra3_*`, `wujia_g*`, `wujia_rhythm_*`) + filestore tương ứng + worktree `scratchpad/b2/head`.
- [ ] Dừng các server Odoo cũ còn giữ slot Postgres (g1, g3s, g5s:8055, e4b1, b2…).
