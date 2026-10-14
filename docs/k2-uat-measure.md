# K2 — bảng đo trên UAT (14/10/2026)

> Issue: #182 `UI-FORM-VALIDATION-001` (K2a + K2b, PR #14).
> Máy: `https://dev.wujiatea.com.vn`, tài khoản `admin`, cửa hàng HCM-01. Chromium, khổ PC 992/1024/1440 × 900 và mobile 360/390/430.
> Trên UAT chỉ mở trang + gửi form thiếu (bị chặn trên trình duyệt, hoặc POST thiếu trường bị máy chủ từ chối). Không tạo bản ghi,
> không đổi mật khẩu (POST với mật khẩu cũ sai), Đăng ký thi chỉ đo phía trình duyệt (không bấm gửi). Ngôn ngữ đổi bằng
> `/portal/set-lang/<lang>`, đo xong trả về `vi_VN` như trước.
> Bản đo: `e61baf83` (merge PR #14: K2a `4ac86ac3` + K2b `054abfea`), CI tự deploy kèm `-u`.
> Script đo: `k2_measure.py` (Hỗ trợ, Bù hàng) + `k2b_measure.py` (Cập nhật thông tin, Đổi mật khẩu, Đăng ký thi), ngoài repo, Playwright.

## 1. Bản đang chạy

7/7 module đúng version (XML-RPC `ir.module.module`): `wujia_portal_layout` 19.0.60.16.0 · `wujia_portal_support` 19.0.5.5.0 ·
`wujia_return` 19.0.2.1.1 · `wujia_portal_return` 19.0.5.5.0 · `wujia_portal_inspection` 19.0.1.8.1 ·
`wujia_portal_info_request` 19.0.3.4.0 · `wujia_portal_exam` 19.0.7.5.0. Tệp giao diện: `?v=1343`.

## 2. Gửi trống — hộp tóm tắt (giống nhau ở cả 6 khổ, vi_VN · en_US)

| Form | Số lỗi | Dòng trong hộp (vi_VN) | Focus đầu |
|---|---|---|---|
| `/portal/support/new` | 2 | Phân loại · Tiêu đề | ô Phân loại |
| `/portal/return/new` | 5 | Loại lỗi · Đơn hàng gốc · Sản phẩm · Thời gian mở hàng · Ảnh minh chứng (mobile xếp theo thứ tự ô trên mobile) | ô đầu tiên của khổ |
| `/portal/info-request/new` | 3 | Cửa hàng · Loại thông tin · Giá trị mới | ô Cửa hàng |
| `/portal/change-password` | 3 | Mật khẩu hiện tại · Mật khẩu mới · Xác nhận / Nhập lại mật khẩu mới | ô Mật khẩu hiện tại |
| `/portal/exam/register` PC (modal) | 2 | Họ và tên · Số điện thoại | ô Họ và tên |
| `/portal/exam/register` mobile (bước 3) | 2/người | Nhân sự n — Họ và tên · Nhân sự n — Số điện thoại | ô sai đầu tiên |

en_US: cùng số lỗi và cùng thứ tự, chữ tiếng Anh ("Please fix 3 field(s) below.", "Store: Please select a store."…), không lẫn tiếng Việt.

## 3. Tình huống con (6/6 khổ)

| Tình huống | Kết quả |
|---|---|
| Bấm một dòng trong hộp | con trỏ vào đúng ô (đo `info-new-value`, `pc/m-con-password`, `wj_exam_p_phone`, `wj-exam-m-p1-name`) |
| Cập nhật thông tin chọn "Khác" | thêm lỗi Tên trường; điền xong thì chỉ còn Cửa hàng + Giá trị mới |
| Mật khẩu nhập lại lệch | chỉ ô nhập lại báo "Nhập lại đúng mật khẩu mới ở trên."; sửa cho khớp → 0 lỗi |
| Mật khẩu mới < 8 ký tự | chỉ ô Mật khẩu mới báo lỗi |
| Đăng ký thi PC số điện thoại sai | 1 lỗi Số điện thoại; sửa đúng → hộp ẩn; Lưu → thêm 1 dòng người thi (chỉ trên trang) |
| Đăng ký thi mobile 2 người, người 2 trống | lỗi "Nhân sự 2 — …", dữ liệu người 1 còn nguyên |

## 4. Bỏ qua trình duyệt (POST thẳng thiếu dữ liệu)

| Form | Kết quả |
|---|---|
| Hỗ trợ (thiếu Tiêu đề) | 200, giữ Mô tả, lỗi dưới ô Tiêu đề |
| Bù hàng (thiếu đơn gốc…) | 200, giữ ghi chú + số lượng, lỗi dưới ô Đơn hàng gốc (PC + mobile) |
| Cập nhật thông tin (thiếu Giá trị mới) | 200, giữ ghi chú, chỉ ô Giá trị mới báo lỗi |
| Đổi mật khẩu (mật khẩu hiện tại sai) | 200, lỗi dưới ô Mật khẩu hiện tại (PC + mobile), HTML không chứa mật khẩu đã gửi |

## 5. Hồi quy

8 màn (`/portal`, danh sách + form Cập nhật thông tin, Đổi mật khẩu, danh sách + đăng ký Thi, Hỗ trợ, Bù hàng) × 1440 + 390:
16/16 trả 200, 0 tràn ngang, 0 lỗi trình duyệt. Mọi lượt đo form: 0 tràn ngang, 0 lỗi trình duyệt.

## 6. Đối chiếu *Kết quả mong muốn* #182

| Yêu cầu | Đo được | Đạt |
|---|---|---|
| Có Error Summary đầu form | 5/5 form trên UAT, 6/6 khổ (Khắc phục: DB copy) | ✅ |
| Lỗi inline đúng ngôn ngữ user | vi_VN + en_US, không lẫn | ✅ |
| `aria-invalid` + `aria-describedby` | đúng các ô sai, câu lỗi gắn vào ô | ✅ |
| Focus ô lỗi đầu tiên | 6/6 khổ mọi form | ✅ |
| Không chỉ báo bằng màu | icon + chữ dưới ô + hộp tóm tắt | ✅ |
| Lỗi máy chủ trả form tại chỗ, giữ giá trị | 4/4 form có tải lại trang; Đăng ký thi không tải lại | ✅ |
| PC và mobile cùng danh sách lỗi | cùng tập lỗi ở 6 khổ (Bù hàng xếp theo thứ tự ô của từng khổ) | ✅ |
| Máy chủ vẫn chặn khi bỏ qua trình duyệt | 4/4 | ✅ |
| Nút gửi loading + chống gửi lặp | bị chặn → nút nhả ra; gửi hợp lệ dùng khoá chung sẵn có, không đo trên UAT vì sẽ tạo dữ liệu thật | ⚠️ |
| Ô mật khẩu giữ giá trị | không điền lại — chủ dự án chốt 14/10 (LIMIT) | — |

8/9 yêu cầu đạt trọn, 1 đạt một phần (loading khi gửi hợp lệ chưa đo trên UAT) ⇒ ≈ 94 % (≥ 90 %).

## 7. Giới hạn

Không điền lại được ô tệp/ảnh sau lỗi máy chủ (giới hạn trình duyệt) · ô mật khẩu không điền lại (chốt) · th/zh chưa dịch ·
câu Việt cứng sẵn có ở Khắc phục · Khắc phục chưa đo trên UAT · chỉ đo Chromium · ảnh/video Bù hàng mobile dùng `aria-label`.
