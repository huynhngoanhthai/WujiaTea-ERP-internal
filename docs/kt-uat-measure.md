# KT — bảng đo trên UAT (16/10/2026)

> Issue: #191 `UI-DETAILTYPO-001` · #193 `UI-DETAIL-NAV-PC-001` · phần còn lại #73 `UI-PAGEHEADER-001` · #83 `UI-SECTIONHEADER-001` (PR #17).
> Máy: `https://dev.wujiatea.com.vn`, tài khoản `admin`, cửa hàng HCM-01, Chromium. Chỉ mở trang, không tạo/sửa/xoá bản ghi.
> Tiếng Anh đo bằng `/portal/set-lang/en_US`, đo xong trả về `vi_VN`.
> Bản đo: `306ccfac` (merge PR #17 `72c47095`), CI tự deploy kèm `-u`.
> Script đo: `kt_type_audit.py` (ngoài repo, Playwright): đếm H1 nhìn thấy, tập cỡ chữ, số phần tử chữ < 12px, tràn ngang, lỗi JS.

## 1. Bản đang chạy

10/10 module đúng version (JSON-RPC `ir.module.module`; `/xmlrpc/` bị chặn từ 15/10): `wujia_portal_layout` 19.0.60.17.0 ·
`wujia_portal_base` 19.0.7.50.0 · `wujia_portal_delivery` 19.0.4.3.0 · `wujia_portal_return` 19.0.5.7.0 · `wujia_portal_support` 19.0.5.6.0 ·
`wujia_portal_notification` 19.0.5.3.0 · `wujia_portal_knowledge` 19.0.5.2.0 · `wujia_portal_sale` 19.0.5.6.0 · `wujia_portal_exam` 19.0.7.6.0 ·
`wujia_portal_purchase_history` 19.0.4.3.0. Tệp giao diện: `?v=1344`.

## 2. Thang chữ (token `--wj-t-*`, số theo #183)

| Vai trò | PC | Mobile |
|---|---|---|
| Tên / tiêu đề dòng | 15 / 20 / 600 | 15 / 20 / 600 |
| Nhãn | 12 / 18 / 500 | 12 / 18 / 500 |
| Giá trị (quan trọng 600) | 14 / 20 / 500 | 13 / 18 / 500 |
| Nội dung bài | 15 / 22 | 14 / 21 |
| Chú thích | 12 / 18 | 12 / 18 |
| Mã chứng từ | 20 / 28 / 700 | 18 / 24 / 700 |

## 3. Trước / sau — 8 màn chi tiết

Trước = UAT 16/10 sáng (trước PR #17). Ô = số H1 · số cỡ chữ khác nhau · số phần tử chữ < 12px.

| Màn | URL | 390 trước | 390 sau | 1440 trước | 1440 sau |
|---|---|---|---|---|---|
| Giao hàng | `/portal/delivery/1` | 1 · 10 · 7 | 1 · 6 · 0 | 1 · 5 · 0 | 1 · 5 · 0 |
| Lịch sử đặt hàng | `/portal/purchase-history/81` | 1 · 9 · 1 | 1 · 7 · 0 | 1 · 7 · 0 | 1 · 8 · 0 |
| Đổi trả | `/portal/return/16` | 1 · 8 · 1 | 1 · 6 · 0 | 1 · 5 · 0 | 1 · 6 · 0 |
| Hỗ trợ | `/portal/support/17` | 1 · 7 · 1 | 1 · 7 · 0 | 1 · 5 · 0 | 1 · 6 · 0 |
| Thông báo | `/portal/notification/26` | 1 · 8 · 2 | 1 · 5 · 0 | 1 · 6 · 0 | 1 · 7 · 0 |
| Kiến thức | `/portal/knowledge/ui12-01` | **2** · 8 · 1 | 1 · 5 · 0 | **2** · 6 · 0 | 1 · 5 · 0 |
| Đăng ký thi | `/portal/exam/registration/16` | 1 · 8 · 1 | 1 · 7 · 0 | 1 · 5 · 0 | 1 · 5 · 0 |
| Sản phẩm | `/portal/order/product/6` | 1 · 10 · 2 | 1 · 6 · 0 | 1 · 8 · 1 | 1 · 5 · 0 |

PC có màn tăng 1 cỡ vì nhãn/giá trị cũ cùng cỡ 13/15 đậm 700 nay tách đúng vai trò 12 và 14.

## 4. Ma trận khổ (sau deploy)

- vi_VN, 8 màn × 320/360/390/430/992/1024/1440/1920 = **64/64**: 1 H1, 0 chữ < 12px, 0 tràn ngang, 0 lỗi JS.
- en_US, 8 màn × 390/1440: 15/16 đạt như trên; ô Đổi trả 390 script không bắt được link chi tiết từ danh sách (lỗi harness, khổ 1440 cùng màn đạt).

## 5. Chữ đếm và điều hướng (vi_VN, PC 1440)

| Kiểm | Kết quả |
|---|---|
| `/portal/purchase-history` PageHeader | chỉ "Lịch sử đặt hàng", không số |
| `/portal/purchase-history` đầu thẻ danh sách | "66 đơn hàng" |
| `/portal/support` | "7 yêu cầu" |
| `/portal/return` | "9 yêu cầu" |
| `/portal/exam/registration/16` | Quay lại + tiêu đề cùng hàng, ô "Trạng thái" trong khung, không hàng Back riêng |
| `/portal/knowledge/ui12-01` | H1 = tên bài; còn một H3 trùng tên nằm trong nội dung bài (dữ liệu người soạn, xem LIMIT) |

## 6. Còn lại

- Bài `ui12-01` có `<h3>` trùng tên ngay đầu nội dung — chờ BA sửa bài hoặc cho tự ẩn.
- Chi tiết Thi còn vài câu tiếng Anh sẵn có trong code ("01 people", "The request has been sent to Ngô Gia.") — ngoài phạm vi.
- zh/th chưa đo; chỉ Chromium.
