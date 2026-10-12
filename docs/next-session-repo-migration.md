# Phiên repo — đổi repo, mô hình nhánh, deploy máy mới

Ghi 12/10/2026. Phiên đó **chỉ ghi chú**; chưa đổi remote, chưa tạo nhánh, chưa sửa CI. Thông tin kết nối:
`docs/CREDENTIALS.md`.

## 1. Hiện trạng (đo chỉ đọc 12/10/2026)

| | Cũ | Mới |
|---|---|---|
| Repo | `github.com/huyban2003/WujiaTea-ERP-internal` | `github.com/huynhngoanhthai/WujiaTea-ERP-internal` |
| UAT | `http://113.161.187.126:8019` (máy Windows) — vẫn đang chạy | `https://dev.wujiatea.com.vn` (115.74.247.189, nginx, quản lý bằng aaPanel) |
| DB | `wujia_tea_19` | `wujia_tea_19` + `wujia_mn` + `huipeng_db` cùng máy |
| Production | chưa có | chưa có |

- Repo mới chỉ có `main` @ `edef2fed` (bằng HEAD local ngày 12/10). Repo cũ còn: `main`, `thai`, `feature/khang`,
  `devkit`, 10 nhánh `dev/2026-*`.
- Local `origin` vẫn trỏ repo cũ (SSH). `~/wujia-devkit` (lệnh `/wujia-*` + `ba_spec`) cùng origin cũ, nhánh `devkit`.
- Metabase `https://metabase.hongtrangogia.com` trả 200. Link aaPanel trả 404 với request thường (chưa đăng nhập thử).

## 2. Mô hình nhánh chủ dự án đưa

```
deploy/production  ──●────────●──────────────────────●──   (PR Release từ staging)
                      \(PR)  / \                    /
hotfix/<title>         ●────●   \ (merge thẳng)    /
                                 \                /
deploy/staging     ───────────────●──────────────●─────
                                 /              / (PR hoàn tất)
feature/<title>    ─────────────●──────────────●           [đường ray]
                               / \            /
staff/<name>/<task> ──────────●───●──────────●             [dev cá nhân]
```

- `staff/<name>/<task>` ⇄ `feature/<title>`: dev làm ở nhánh cá nhân, đẩy lên ray, kéo ray về.
- `feature/<title>` → `deploy/staging`: vào giữa chừng và lần cuối bằng "PR hoàn tất".
- `deploy/staging` → `deploy/production`: "PR Release".
- `hotfix/<title>`: tách từ production, PR về production, rồi production merge thẳng xuống staging.

## 3. Nhận xét

Khung hợp lý: hai nhánh triển khai dài hạn, hotfix chảy ngược xuống, dev cá nhân không đụng nhánh chung. Sáu chỗ nên
chốt thêm trước khi áp:

1. **Staging là điểm nghẽn "tất cả hoặc không".** PR Release lấy nguyên staging, mà ray vào staging từ giữa chừng ⇒
   một ray trượt retest BA chặn mọi ray khác. Luật đề xuất: ray chỉ vào staging khi dev đã tự nghiệm thu; release chỉ
   mở khi mọi issue trên staging đã `Done`; cái trượt thì revert khỏi staging.
2. **Ray tách từ `deploy/production`, không từ staging** (sơ đồ chưa vẽ điểm tách). Tách từ staging là kéo theo code
   chưa release của ray khác. Khi chưa có production: tách từ điểm release gần nhất của staging (có tag).
3. **Hotfix phải chảy tới cả ray đang mở.** Sau mỗi hotfix/release, mọi `feature/*` merge production vào. Dự án này
   hay đụng nhau ở ba chỗ: version trong `__manifest__.py`, thư mục `migrations/<version>/`, số `?v=NNNN` trong
   `assets.xml`. Luật sẵn có (L17 compact summary): lấy số lớn hơn rồi +1 cho mọi module đụng.
4. **Cấm squash giữa các nhánh dài hạn** (feature→staging, staging→production, production→staging). Ray vào staging
   hai lần; squash thì lần sau xung đột lại toàn bộ. Squash chỉ cho `staff/*` → `feature/*`.
5. **Đường tắt cho việc nhỏ.** Phần lớn việc hiện tại là issue 1–3 file; đi `staff → feature → staging` là hai PR cho
   một dòng CSS. Đề xuất: một ray theo cụm Issue List (`feature/issue-list-<cụm>`), hoặc cho `staff/*` PR thẳng staging
   với việc Issue List. Ray riêng dành cho việc nhiều người/nhiều tuần (WJ-OPS-001, mobile anh Thái).
6. **Ba thứ vận hành còn thiếu.**
   - Hotfix không có môi trường thử trước production ⇒ bắt buộc chạy test trên DB copy trước khi merge.
   - Gắn tag mỗi lần release để lùi được.
   - "Merge thẳng" production→staging mâu thuẫn với branch protection bắt PR ⇒ hoặc cũng làm PR, hoặc chỉ định người
     được bypass.
   - Khi có production: làm mới DB staging từ production định kỳ, vì migration Odoo không chạy ngược.

## 4. Việc phải làm khi đổi repo

- [ ] `git remote set-url origin` cho repo chính và cho `~/wujia-devkit`; quyết nhánh `devkit` ở repo mới hay tách repo.
- [ ] Số phận nhánh cũ: `thai`, `feature/khang`, `devkit`, 10 nhánh `dev/2026-*` (kiểm đã merge hết chưa rồi mới bỏ).
- [ ] `main` → `deploy/staging`; tạo `deploy/production`; đặt default branch + branch protection.
- [ ] `.github/workflows/deploy.yml`: đang `on: push main`, runner self-hosted trên máy Windows cũ, danh sách
      module cứng ⇒ viết lại cho máy aaPanel, mỗi nhánh deploy một job.
- [ ] Chốt lệnh deploy máy mới rồi ghi vào §6 compact summary (lệnh máy Windows cũ đã bỏ 12/10).
- [ ] `~/wujia-devkit/commands/wujia-end-sprint.md`: đang ghi `git push origin master`.
- [ ] Nightly agent `ba_spec/qa_nightly/agent_prompt_interactive.md`: "branch riêng từ main", "push main".
- [ ] `.env.local` biến `GITHUB_REMOTE`.
- [ ] Viết checklist dựng máy mới (checklist + script dựng máy Windows cũ đã xoá 12/10).
- [ ] Thiết kế lại cấu trúc source theo cách Besco tổ chức các dự án trong repo (chủ dự án có kế hoạch riêng).

## 5. Bảo mật

- Gọi GitHub không đăng nhập, cả repo cũ lẫn repo mới đều trả 200 và clone ẩn danh được ⇒ đang **công khai**.
- `docs/CREDENTIALS.md` được git theo dõi, chứa mật khẩu RDP máy cũ, admin Odoo, và từ 12/10 cả aaPanel + Metabase
  (chủ dự án quyết ghi thẳng). `admin/Wujia@2026` nằm trong nhiều file docs và script.
- Phiên repo cần quyết: chuyển repo sang private; đổi mật khẩu aaPanel (`wujia`/`admin`) và Metabase (`Admin@123`) —
  cả hai mở ra internet; đổi mật khẩu đã nằm trong lịch sử git.

## 6. Chưa biết

- Tài khoản đăng nhập UAT mới (chủ dự án báo sau). Các script đo còn mặc định `admin` / `Wujia@2026`.
- Cách deploy trên máy mới (đường dẫn source, service, ai chạy).
- `wujia_mn` và `huipeng_db` trên máy mới là gì.
- UAT mới đang ở commit / version module nào — đo XML-RPC `ir.module.module` khi có tài khoản, trước khi tin số đo cũ.
- Máy cũ tắt khi nào; BA đã chuyển sang retest trên domain mới chưa.

## 7. Đã làm 12/10

- Thay địa chỉ UAT và link repo trong: `docs/CREDENTIALS.md`, `docs/wujia-compact-summary.md` (§1, §5, §6, §12),
  `docs/UAT_ACCESS_AND_DEBUG.md`, hai chuẩn QA 01/02, 6 script `scripts/qa/`, 6 file `~/wujia-devkit/ba_spec/`,
  `~/wujia-devkit/commands/wujia-start.md` + `wujia-end-sprint.md` (bỏ lệnh deploy máy Windows).
- Dọn repo: xoá 330 file (~24 MB) — biên bản nghiệm thu / số đo / inventory các cụm C–G, `prompt-*`, `prompts/`,
  `issue-clusters/` (trừ `prompts.md`), `next-session-clusters-C/D/E/G`, ghi chú merge Thái, `deploy-d4*`,
  `DEPLOY_SPRINT5.md`, `CHECKLIST`, `ba-notice-*`, `ba-question*`, `f-review-*`, ảnh baseline, `figma_ref/`,
  `WJ_PageHeader/`, bộ icon module; trong `scripts/`: 2 script Windows, `test_sprint30/31/32*`, 6 seed demo cụm D/E.
  Cần lại thì lấy từ lịch sử git trước commit dọn.
- Giữ: `chapters/` + `wujia-tea-doc` + ADR-027; file quy trình (compact summary, `f-progress.md`, ledger, chuẩn QA,
  `next-session-clusters-F/H/J`, backlog); file code đọc (`i18n-*`, `handover-*`); tài liệu gửi BA (controller-spec,
  controller-inventory, ba-component-spec-proposal, portal-component-standard, figma-brief); toàn bộ `scripts/qa/`.
- Số đo UAT trong chapter và ledger trước 12/10 là đo trên máy cũ `113.161.187.126:8019`.
