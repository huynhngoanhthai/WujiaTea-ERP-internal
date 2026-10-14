# Cụm K — Issue List lứa 175–188 + 3 dòng BA mở lại + 2 tính năng (lập 14/10/2026)

> Chủ dự án chốt 14/10: **chia cụm trước, chưa code** — 17 dòng `Ready for Dev` có cả lỗi lẫn tính năng mới.
> Portal Vận hành (#181) **mình làm**, kế hoạch nằm ở `next-session-clusters-J.md` Phần O (mở lại 14/10).
> "Cụm K" là tên cụm Issue List, **không phải** Sprint K (bù hàng).
> HEAD lúc lập: `f878ed65` (`deploy/staging`).

## 0. Luật áp suốt cụm

- **Không sửa code anh Thái**: `wujia_franchise*` (gồm `wujia_franchise_operations`), `wujia_portal_inspection`,
  `wujia_mobile_core`, `wujia_mobile_*`. Đụng tới ⇒ dừng hỏi chủ dự án, ghi bàn giao.
- Phạm vi dữ liệu = **một cửa hàng đang chọn** + role tại cửa hàng đó (helper cụm I ở `portal_base`), không viết lại.
- Luật portal sửa ở module L2 (`_portal_*`, `create_from_portal`), controller giữ mỏng (ADR-027).
- Field mới phải có tiền tố `wujia_`. CSS dùng `var(--wujia-*)`, đổi CSS thì bump `?v=`.
- Mỗi phiên: `git pull` · tách `feature/*` từ `origin/deploy/staging` · test kèm `-u` trên DB copy · đo ≥90 % cột
  `Kết quả mong muốn` · ledger → `qa_sync.py --dry-run` → `--apply` · ghi `f-progress.md` + ✅ bảng §2.
- Sau merge: kiểm version module trên UAT qua XML-RPC trước khi đo và ghi sheet (job CI 13/10 chưa rõ có `-u`).
- Dev tối đa `Ready for Retest`. Gặp fork ở §4 ⇒ hỏi, không tự quyết.

## 1. Hiện trạng (đọc sheet 14/10)

Issue List 179 dòng: 152 Done · 6 Ready for Retest · 4 Need Clarification · **17 Ready for Dev**.

| STT | ID | Sev | Loại | Dấu vết git |
|---|---|---|---|---|
| 37 | WJ-ORD-008 | Med | **Mở lại 12/10** (Done → Ready for Dev) | chưa có code |
| 73 | UI-PAGEHEADER-001 | Med | **Mở lại 12/10** | fix cũ `4da3a57` + `30bed39` (11/08), ledger có |
| 139 | UI-FILTER-001 | Med | **Mở lại 11/10**, thêm ca 12/10 | fix cũ `faa76f5` (19/09), ledger có |
| 175 | WJ-RETURN-002 | Med | Lỗi nội dung + phạm vi | chưa |
| 176 | WJ-HOME-011 | Med | Lỗi nội dung + cấu hình | chưa |
| 177 | WJ-NOTI-002 | Med | Lỗi lọc + thứ tự | chưa |
| 178 | WJ-DELIVERY-008 | Med | Lỗi nhãn + thứ tự | chưa |
| 179 | WJ-KNOW-002 | Low | Lỗi nội dung + số đếm | chưa |
| 180 | WJ-KNOW-003 | Med | **Tính năng nhỏ** (field mới) | chưa |
| 181 | WJ-OPS-001 | Med | **Tính năng lớn** (14 màn) | chưa — Phần O cụm J |
| 182 | UI-FORM-VALIDATION-001 | High | Component dùng chung | chưa |
| 183 | UI-LISTCARD-003 | Med | Component + nội dung ~9 màn | chưa |
| 184 | UI-REPORT-DATE-001 | Med | Lỗi responsive | chưa |
| 185 | WJ-ORD-033 | High | **Tính năng lớn** (tồn + đồng thời) | chưa |
| 186 | WJ-SUPPORT-004 | Med | Lỗi lệch PC/mobile | chưa |
| 187 | WJ-SUPPORT-005 | High | Lỗi lệch PC/mobile | chưa |
| 188 | WJ-SUPPORT-006 | Med | Accessibility | chưa |
| 189 | UI-FILTERCHIP-001 | Low | Lỗi UI mobile (BA thêm 14/10): dải chip lọc cuộn ngang không có dấu hiệu | chưa — **chưa xếp phiên** |

**Ba dòng mở lại — lý do BA ghi ở tab `7. ISSUE HISTORY`** (không phải "đã fix, chỉ cần sync"):

- **#139** (11/10): `/portal/delivery` nhấn Enter không gửi tìm kiếm ở PC 1440 và mobile 390; ngày bắt đầu lớn hơn ngày
  kết thúc vẫn ra 0 chuyến + EmptyState dù đã hiện cảnh báo. (12/10): `/portal/debt/payment-history` PC nhấn Enter không
  tìm, gõ thẳng query thì chạy.
- **#73** (12/10): `/portal/debt/payment-history` H1 là "Công nợ" trên desktop nhưng "Lịch sử thanh toán" trên mobile.
- **#37** (12/10): Top sản phẩm ở `/portal/reports/orders` hiện mã nội bộ trước tên (`[TS-MAT]`, `[TP-PUDD]`…), kèm một
  ca ở chi tiết đơn — đọc nguyên văn dòng History trước khi sửa.

## 2. Bảng trạng thái

**Nhóm sửa lỗi / UI** — mỗi phiên một deploy UAT.

| Phiên | Issue | Nội dung | Module chính | Trạng thái |
|---|---|---|---|---|
| K0 | #139 · #73 · #37 | Enter gửi tìm kiếm + ngày ngược · H1 `payment-history` một tên · bỏ mã nội bộ khỏi tên sản phẩm | portal_layout (FilterBar), portal_debt, portal_report |✅ 14/10 · `319a16fb` · sheet `Ready for Retest` |
| K1 | #187 · #188 · #186 | Form Hỗ trợ một cấu hình PC/mobile (phân loại rỗng bắt buộc, 2 mức ưu tiên) · nhãn gắn control · metadata chi tiết ticket | wujia_support, portal_support | ☐ |
| K2 | #182 | Shared Form Validation: Error Summary + lỗi tại field + `aria-*` + giữ dữ liệu khi server trả lỗi; áp `support/new`, `return/new`. Gộp H9 FormField của cụm H | portal_layout, portal_support, portal_return | ☐ |
| K3 | #175 | Đổi trả: Home + danh sách + chi tiết theo cửa hàng đang chọn, bỏ Tổng tiền, thêm Sản phẩm · SL ĐVT | wujia_return, portal_return, portal_base | ☐ |
| K4 | #178 | Giao hàng: một bộ nhãn trạng thái Home/danh sách/chi tiết, "Chưa có lịch", thứ tự, bỏ Tổng tiền | portal_delivery, portal_base | ☐ |
| K5 | #177 · #176 | Thông báo nổi bật (ghim → mức độ → ngày, badge Mức độ) · khối Hỗ trợ nhanh (thêm Theo dõi yêu cầu, ẩn hotline/chat chưa cấu hình) | wujia_notification, portal_base | ☐ |
| K6 | #179 · #180 | Kiến thức: tên khối "Danh sách bài viết" + số tổng sau lọc · field `wujia_show_on_home` + lọc backend + nguồn Home | wujia_knowledge, portal_knowledge, portal_base | ☐ |
| K7a | #183 (phần 1) · #184 | ListCard mobile: khung chung + nửa số màn · ô Từ/Đến ngày Báo cáo mobile | portal_layout + module màn, portal_report | ☐ |
| K7b | #183 (phần 2) | ListCard mobile: các màn còn lại, đóng issue | module màn | ☐ |
| ★KR | — | Review cả cụm trên UAT: ma trận route × khổ, đối chiếu từng issue, 0 lỗi JS, 0 tràn | — | ☐ |

**Nhóm tính năng** — phiên đầu là thiết kế, 0 code, ra danh sách fork gửi BA.

| Phiên | Issue | Nội dung | Module | Trạng thái |
|---|---|---|---|---|
| S0 | #185 | Thiết kế bán theo tồn còn lại: đọc mục U + Q tab `1. Model/ Field`, soi luồng giỏ/submit hiện có, chọn cách khoá khi ~1.000 cửa hàng gửi cùng lúc | docs | ☐ |
| S1 | #185 | Field chính sách trên sản phẩm + sổ cam kết + luật L2 + test gửi đồng thời | wujia_sale | ☐ |
| S2 | #185 | Portal: danh sách, chi tiết, giỏ, submit dùng một công thức; thông báo nêu SKU + số còn đặt được; giỏ giữ nguyên khi lỗi | portal_sale | ☐ |
| ★SR | #185 | Đo tải trên DB copy: không bán vượt, không cam kết âm, không deadlock | — | ☐ |
| J-O0…★JR | #181 | Portal Vận hành 14 màn — bảng trạng thái ở `next-session-clusters-J.md` §2 | wujia_portal_operations (mới) | ☐ |

**Thứ tự đề xuất:** K0 → K1 → K2 → S0 → K3 → K4 → K5 → K6 → J-O0 → K7a → K7b → (S1… và J-O1… xen kẽ) → ★KR.
S0 và J-O0 đặt sớm để BA có thời gian trả lời trong lúc làm các phiên Home. K7 đứng sau K3–K5 vì #183 dùng lại nội
dung card của #175, #177, #178.

## 3. Prompt từng phiên

Dán **sau `/wujia-start`**. Nội dung từng phiên = dòng tương ứng ở §2 + cột `Đề xuất điều chỉnh` và `Kết quả mong muốn`
của chính issue trên sheet (đọc bằng `export?format=csv&gid=335593633`, không dùng gviz).

```text
Làm phiên <Kx> cụm K (docs/next-session-clusters-K.md). Đọc §0, §2, §4 trước.
1. Đọc nguyên văn issue <ID> trên sheet + dòng History gần nhất của nó.
2. Soi source hiện có, liệt kê fork ở §4 còn mở rồi hỏi trước khi code.
3. Sửa ở chỗ gốc, đo trước/sau, bảng đối chiếu Yêu cầu | Đo được | Pass/Fail ≥ 90 %.
4. Ledger → qa_sync --dry-run → chờ duyệt → --apply. Ghi f-progress + ✅ §2.
```

Riêng K0: sửa Enter ở **khuôn FilterBar dùng chung**, không vá từng màn; rồi đo lại mọi màn có ô tìm kiếm.
Riêng S0 và J-O0: không code, sản phẩm là một file thiết kế trong `docs/` + câu hỏi BA.

## 4. Fork đã thấy — hỏi khi tới phiên

| Phiên | Câu hỏi | Hỏi ai |
|---|---|---|
| K0 | Ngày ngược: danh sách hiển thị gì (BA chỉ nói không được ra 0 dòng kèm EmptyState) | BA |
| K2 | `/portal/inspection/remediation` gửi được khi thiếu ảnh — module anh Thái: bàn giao hay được phép sửa | Chủ dự án |
| K2 | Danh sách form trong phạm vi ngoài `support/new` và `return/new` | BA |
| K5 | Số hotline và kênh chat cấu hình ở đâu (công ty, Settings, hay theo khu vực) | BA |
| S0 | Trạng thái đơn nào tính cam kết · khi nào nhả cam kết · cấu hình location mục Q đã có trong source chưa | BA + chủ dự án |
| J-O1 | Luật portal: thêm file mới vào `wujia_franchise_operations` hay anh Thái viết | Chủ dự án + anh Thái |
