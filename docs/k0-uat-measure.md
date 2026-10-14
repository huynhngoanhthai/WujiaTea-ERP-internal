# K0 — bảng đo trên UAT (14/10/2026)

> Issue: #139 `UI-FILTER-001` · #73 `UI-PAGEHEADER-001` · #37 `WJ-ORD-008`.
> Máy: `https://dev.wujiatea.com.vn`, tài khoản `admin`, cửa hàng HCM-01. Chromium, khổ 1440×900 và 390×844.
> Chỉ gửi GET (tìm, lọc, mở trang) — không tạo, sửa hay xoá bản ghi nào.
> **Trước** = bản `f878ed65` (đo 14/10 trước khi merge). **Sau** = bản `319a16fb` (code `8c01ba9f`), CI tự deploy kèm nâng cấp module.
> Script đo: `k0_measure.py` + `k0_extra.py` (ngoài repo, chạy bằng Playwright).

## 1. Bản đang chạy

9/9 module đúng version sau deploy (đọc `ir.module.module` qua XML-RPC): `wujia_portal_layout` 19.0.60.13.2 ·
`_base` 19.0.7.48.2 · `_delivery` 19.0.4.2.2 · `_debt` 19.0.5.2.2 · `_report` 19.0.3.3.1 · `_purchase_history` 19.0.4.1.1 ·
`_return` 19.0.5.4.1 · `_notification` 19.0.5.2.1 · `_exam` 19.0.7.4.1. Tệp giao diện: `?v=1340`.

## 2. #139 — Enter ở ô tìm kiếm

Gõ `zq9` rồi nhấn Enter bằng phím thật; đạt khi đường dẫn nhận đúng từ khoá. Cột cuối: bấm nút Tìm kiếm có ra cùng đường dẫn không.

| Khổ | Màn | Ô | Trước | Sau | Bấm nút ≡ Enter |
|---|---|---|---|---|---|
| PC | `/portal/delivery` | `q` | Đạt | Đạt | Có |
| PC | `/portal/debt/payment-history` | `q` | Đạt | Đạt | Có |
| PC | `/portal/purchase-history` | `q` | Đạt | Đạt | Có |
| PC | `/portal/notification` | `keyword` | Đạt | Đạt | Có |
| PC | `/portal/return` | `q` | Đạt | Đạt | Có |
| PC | `/portal/exam` | `q` | Đạt | Đạt | Có |
| PC | `/portal/order` | `keyword` | Đạt | Đạt | Có |
| PC | `/portal/knowledge` | `keyword` | Đạt | Đạt | Có |
| Mobile | `/portal/delivery` | `q` | Đạt | Đạt | Có |
| Mobile | `/portal/purchase-history` | `q` | Đạt | Đạt | Có |
| Mobile | `/portal/notification` | `keyword` | Đạt | Đạt | Có |
| Mobile | `/portal/return` | `q` | Đạt | Đạt | Có |
| Mobile | `/portal/order` | `keyword` | Đạt | Đạt | Có |
| Mobile | `/portal/knowledge` | `keyword` | Đạt | Đạt | Có |
| Mobile | `/portal/support` | `q` | Đạt | Đạt | Có |

Tổng: trước 15/15 · sau 15/15 · bấm nút ≡ Enter 15/15.

Ca đặc biệt (PC 1440):

| Ca | Trước | Sau |
|---|---|---|
| Sự kiện phím do script phát (Giao hàng) | Hỏng | Đạt |
| Phím qua CDP `rawKeyDown` | Hỏng | Đạt |
| Phím qua CDP `keyDown` không kèm ký tự | Hỏng | Đạt |
| Hai lần Enter liền nhau, đổi từ khoá ở giữa | Hỏng | Đạt |
| Enter lần hai khi lượt một còn đang tải (làm chậm 1,5 giây) | Hỏng | Đạt |
| Enter khi đang đứng ở ô ngày | Đạt | Đạt |
| Enter của bàn phím số | Đạt | Đạt |
| Sự kiện phím do script phát (Lịch sử thanh toán) | Hỏng | Đạt |
| Enter lúc đang gõ dấu (IME) — phải KHÔNG gửi | Đạt | Đạt |

Tổng: trước 3/9 · sau 9/9. Lỗi JS trong lúc đo: 0.

## 3. #139 — khoảng ngày ngược

Mở `?date_from=2026-10-10&date_to=2026-10-01`. Yêu cầu: đúng một dòng đỏ ở thanh lọc, đúng một khối nhắc, không EmptyState,
không số đếm 0, hai ô ngày giữ nguyên giá trị.

| Khổ | Màn | Trước | Sau |
|---|---|---|---|
| PC | Giao hàng | 1 dòng đỏ · 0 khối nhắc · 1 EmptyState · số đếm: 0 chuyến | 1 dòng đỏ · 1 khối nhắc |
| PC | Lịch sử đặt hàng | 1 dòng đỏ · 0 khối nhắc · số đếm: 0 bản ghi, 0 đơn | 1 dòng đỏ · 1 khối nhắc |
| PC | Thông báo | 1 dòng đỏ · 0 khối nhắc · 1 EmptyState | 1 dòng đỏ · 1 khối nhắc |
| PC | Bù hàng | 1 dòng đỏ · 0 khối nhắc · 1 EmptyState · số đếm: 0 kết quả | 1 dòng đỏ · 1 khối nhắc |
| PC | Đăng ký thi | 1 dòng đỏ · 0 khối nhắc · 1 EmptyState | 1 dòng đỏ · 1 khối nhắc |
| PC | Báo cáo đặt hàng | 1 dòng đỏ · 0 khối nhắc · 1 EmptyState · số đếm: 0 sản phẩm, 0 đơn | 1 dòng đỏ · 1 khối nhắc |
| Mobile | Giao hàng | 1 dòng đỏ · 0 khối nhắc · 1 EmptyState | 1 dòng đỏ · 1 khối nhắc |
| Mobile | Lịch sử đặt hàng | 1 dòng đỏ · 0 khối nhắc · số đếm: 0 đơn | 1 dòng đỏ · 1 khối nhắc |
| Mobile | Thông báo | 1 dòng đỏ · 0 khối nhắc · 1 EmptyState | 1 dòng đỏ · 1 khối nhắc |
| Mobile | Bù hàng | 1 dòng đỏ · 0 khối nhắc · 1 EmptyState · số đếm: 0 yêu cầu | 1 dòng đỏ · 1 khối nhắc |
| Mobile | Đăng ký thi | 1 dòng đỏ · 0 khối nhắc · 1 EmptyState · số đếm: 0 đăng ký | 1 dòng đỏ · 1 khối nhắc |
| Mobile | Báo cáo đặt hàng | 1 dòng đỏ · 0 khối nhắc · 2 EmptyState · số đếm: 0 đơn | 1 dòng đỏ · 1 khối nhắc |

Mỗi màn còn đo thêm hai bước không tải lại trang: gõ ngày ngược rồi Enter (kết quả như bảng trên), rồi sửa Đến ngày thành
31/10 và Enter — dòng đỏ và khối nhắc biến mất, danh sách trở lại, 0 lỗi JS. Tổng ba bước: trước 11/34 · sau 34/34.
Hai ô ngày giữ nguyên `10/10/2026` và `01/10/2026` ở mọi màn có ô ngày. Thông báo trên mobile không có ô ngày (có từ trước)
nên chỉ đo được bước mở bằng đường dẫn.

Câu chữ: dòng đỏ "Từ ngày không được lớn hơn Đến ngày" · khối nhắc "Khoảng ngày chưa hợp lệ — Sửa Từ ngày hoặc Đến ngày để xem danh sách."

## 4. #73 — tiêu đề trang (H1) máy tính so với điện thoại

| Route | Trước PC | Trước mobile | Sau PC | Sau mobile |
|---|---|---|---|---|
| `/portal/debt` | Công nợ | Công nợ | Công nợ | Công nợ |
| `/portal/debt/payment-history` | Công nợ | Lịch sử thanh toán | Lịch sử thanh toán | Lịch sử thanh toán |
| `/portal/debt/pay` | Thanh toán công nợ | Thanh toán công nợ | Thanh toán công nợ | Thanh toán công nợ |

Quét rộng sau deploy, 23 route (danh sách + tạo mới + chi tiết): 22/23 có H1 giống nhau ở hai khổ, 0 tràn ngang.

Còn lệch: `/portal/info-request` — PC "Yêu cầu cập nhật thông tin", mobile "Cập nhật thông tin". Route này không có trong Page Naming Matrix của CMP-PG-001 ⇒ chờ BA cho tên.

## 5. #37 — mã nội bộ trước tên sản phẩm

Quét chuỗi dạng `[MÃ]` trong phần thân trang. `[HCM-01]` là mã cửa hàng, không tính.

| Màn | Trước (PC / mobile) | Sau (PC / mobile) |
|---|---|---|
| `/portal` | 0 / 0 | 0 / 0 |
| `/portal/reports/orders` | [TP-CHEE], [TP-PUDD], [TS-DAO], [TS-HONG], [TS-MAT] / [TP-CHEE], [TP-PUDD], [TS-DAO], [TS-HONG], [TS-MAT] | 0 / 0 |
| `/portal/order` | 0 / 0 | 0 / 0 |
| `/portal/order/cart` | — / — | 0 / 0 |
| `/portal/purchase-history` | 0 / 0 | 0 / 0 |
| `/portal/delivery` | 0 / 0 | 0 / 0 |
| `/portal/return` | 0 / 0 | 0 / 0 |
| `/portal/return/new` | 0 / 0 | 0 / 0 |
| `/portal/purchase-history/80` | [TP-CHEE], [TP-PUDD], [TS-DAO] / [TP-CHEE], [TP-PUDD], [TS-DAO] | 0 / 0 |
| `/portal/purchase-history/79` | [TP-CHEE], [TS-DAO] / [TP-CHEE], [TS-DAO] | 0 / 0 |
| `/portal/purchase-history/78` | 0 / 0 | 0 / 0 |
| `/portal/delivery/1` | [TP-CHEE], [TS-HONG] / [TP-CHEE], [TS-HONG] | 0 / 0 |
| `/portal/delivery/2` | 0 / 0 | 0 / 0 |
| `/portal/return/15` | 0 / 0 | 0 / 0 |
| `/portal/return/13` | 0 / 0 | 0 / 0 |
| `/portal/return/12` | 0 / 0 | 0 / 0 |

Lượt xem còn mã sản phẩm: trước 8/32 · sau 0/32. (Giỏ hàng lượt "trước" chưa đo do sai đường dẫn.)

## 6. Hồi quy

13 màn × 2 khổ = 26 ô: 26/26 trả 200, 0 lỗi JS, 0 tràn ngang. Chiều cao thanh lọc trước/sau giống nhau 26/26 ô.

## 7. Đối chiếu `Kết quả mong muốn`

**#139 UI-FILTER-001**

| Yêu cầu | Đo được | Kết luận |
|---|---|---|
| UI giữ mẫu UAT, control / căn lề đồng nhất | Chiều cao thanh lọc 26/26 ô không đổi | Đạt |
| Ngày ngược có validation | 6 màn × 2 khổ: một dòng đỏ + một khối nhắc, 0 EmptyState, 0 số đếm 0 | Đạt |
| Ngày hợp lệ lọc đúng | Sửa lại ngày thì danh sách trở lại ở 11/11 ô có ô ngày | Đạt |
| Search Enter / click tương đương | Enter 15/15 · bấm nút ra cùng đường dẫn 15/15 · ca đặc biệt 9/9 | Đạt |
| Chip / select / query nhất quán | Không sửa phần này; test tự động của 9 module 1017/1017 | Đạt (không đo lại riêng) |
| Phân trang giữ điều kiện | Không sửa phần này; test tự động xanh | Đạt (không đo lại riêng) |
| Không tràn ngang, không mất nhãn | 0 tràn ở 26 ô | Đạt |
| Mobile không thêm Xóa lọc | Khối nhắc không có nút | Đạt |
| Không thêm/bớt điều kiện, không đổi ListCard / field / workflow / quyền / store | Chỉ đổi trạng thái hiển thị khi ngày ngược | Đạt |
| Evidence trước/sau PC + mobile, build hợp lệ | File này + 9/9 module đúng version | Đạt |

**#73 UI-PAGEHEADER-001** (phần BA mở lại: tên trang PC ≠ mobile)

| Yêu cầu | Đo được | Kết luận |
|---|---|---|
| Tên PageHeader giống nhau giữa desktop / mobile | `payment-history`: "Lịch sử thanh toán" cả hai · 22/23 route quét rộng giống nhau | Đạt trong 17 màn của bảng đặt tên; 1 route ngoài bảng còn lệch |
| Không chồng lấn, không scroll ngang | 0 tràn ở 23 route × 2 khổ | Đạt |
| Không ảnh hưởng TopHeader, Sidebar, Bottom Navigation, nghiệp vụ | Chỉ đổi một chuỗi tiêu đề | Đạt |

**#37 WJ-ORD-008**

| Yêu cầu | Đo được | Kết luận |
|---|---|---|
| Nhận diện bằng tên sản phẩm; không hiển thị mã nội bộ / SKU | 8 lượt xem còn mã → 0 | Đạt |

## 8. Giới hạn

- Enter bằng phím thật: không tái hiện được lỗi BA báo trên UAT mới, cả trước lẫn sau khi sửa (15/15). Hai đường hỏng tìm thấy
  và đã sửa là phím không kèm ký tự và Enter lần hai khi lượt một chưa về.
- Chỉ đo trên Chromium; Safari và Firefox chưa đo.
- Câu chữ khối nhắc do Dev đặt, chờ BA duyệt.
- Thông báo trên mobile không có ô ngày: mở đường dẫn ngày ngược thì thấy khối nhắc nhưng không có ô để sửa, thoát bằng chip.
- H1 PC của `payment-history` là "Lịch sử thanh toán" theo chốt của chủ dự án; Figma v1.1 ghi "Công nợ" ở dòng tiêu đề.
