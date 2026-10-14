# K1 — bảng đo trên UAT (14/10/2026)

> Issue: #187 `WJ-SUPPORT-005` · #188 `WJ-SUPPORT-006` · #186 `WJ-SUPPORT-004`.
> Máy: `https://dev.wujiatea.com.vn`, tài khoản `admin` (vi_VN), cửa hàng HCM-01. Chromium, khổ 1440×900 và 390×844.
> Trên UAT chỉ mở trang + gửi form trống (bị chặn trên trình duyệt) — không tạo ticket nào. Tạo ticket thật chỉ làm trên
> DB copy `wujia_k1` (đã xoá).
> **Trước** = bản `dba19d43` (đo 14/10 trước khi code). **Sau** = bản `00e9443f` (code `842b4ffc`), CI tự deploy kèm `-u`.
> Script đo: `k1_measure.py` + `k1_regress.py` (ngoài repo, Playwright).

## 1. Bản đang chạy

2/2 module đúng version (XML-RPC `ir.module.module`): `wujia_portal_layout` 19.0.60.14.0 · `wujia_portal_support`
19.0.5.4.0. Tệp giao diện `_components.css` + `wj_form_validate.js`: `?v=1341`.

## 2. #187 — form `/portal/support/new`

| Yêu cầu | Trước | Sau (PC · mobile) | Đạt |
|---|---|---|---|
| Phân loại mở ra trống "Chọn loại yêu cầu" | PC chọn sẵn "Đặt hàng" · mobile trống | trống · trống | ✅ |
| Phân loại bắt buộc | PC không có ô trống để bắt | `required` · `required` | ✅ |
| Mức độ đúng 2 lựa chọn, mỗi cái 1 giá trị | PC 2 · mobile 3 (Gấp + Khẩn cấp cùng `urgent`) | `normal`/`urgent` · `normal`/`urgent` | ✅ |
| Nhãn hai khổ giống nhau | mobile "Nhóm", "Ưu tiên"… | cùng bộ nhãn PC | ✅ |
| Tạo ticket PC và mobile cùng lựa chọn ra cùng dữ liệu (DB copy) | — | cùng `category_id` + `urgent` | ✅ |

## 3. #188 — nhãn + trạng thái lỗi

| Yêu cầu | Trước | Sau PC | Sau mobile | Đạt |
|---|---|---|---|---|
| Mỗi control có `id` + đúng 1 `label[for]` | 0/6 | 6/6 | 6/6 (chip Mức độ: `role=radiogroup` + `aria-labelledby`) | ✅ |
| Bấm nhãn → focus đúng control | 0/6 | 6/6 | 4/4 | ✅ |
| Tên đọc được duy nhất | rỗng | 6 tên khác nhau | 6 | ✅ |
| Gửi trống: không bong bóng native, `aria-invalid`, câu lỗi gắn `aria-describedby`, focus ô đầu | bong bóng trình duyệt | Phân loại + Tiêu đề, focus Phân loại | như PC | ✅ |
| Nút Gửi không kẹt loading sau khi bị chặn | — | không kẹt | không kẹt | ✅ |
| Sửa ô → lỗi tắt | — | Tiêu đề tắt, Phân loại còn | như PC | ✅ |
| Lỗi máy chủ (`?error=`) có `role=alert` + ô liên quan được đánh dấu | chỉ mobile, không aria | 4/4 mã | 3/4 (cửa hàng ẩn trên mobile) | ✅ |

## 4. #186 — thẻ thông tin chi tiết

Ticket đã giải quyết `WJ-TK/26/00013`:

| Trước PC | Trước mobile | Sau (PC = mobile) |
|---|---|---|
| Cửa hàng · Phân loại · Mức độ · Ngày gửi 27/05/2026 17:36 · Người xử lý · Ngày giải quyết | Nhóm · Ưu tiên · Người gửi · Ngày tạo | Phân loại Sản phẩm · Mức độ Bình thường · Người gửi Administrator · Ngày gửi **28/05/2026 00:36** · Người xử lý Administrator · Ngày giải quyết 27/05/2026 |

Ticket chưa phân công `WJ-TK/26/00004`: PC = mobile, Người xử lý "Chưa phân công", Ngày giải quyết "Chưa giải quyết".
Giờ gửi trước lệch −7 tiếng (in giờ UTC), nay giờ VN. Ngày giải quyết của 00013 sớm hơn ngày gửi là do dữ liệu mẫu
(`resolved_date` 05:36 UTC < `create_date` 17:36 UTC), không phải lỗi hiển thị.

## 5. Tràn ngang + lỗi JS

`/portal/support/new`, `/portal/support/new?error=missing_fields`, `/portal/support/13` × 320/360/390/430/768/991/992/
1024/1440/1920: tràn ngang 0 ở cả 30 lượt (trước cũng 0). Lỗi JS: 0.

Hồi quy (khung dùng chung đổi): `/portal/return/new`, `/portal/info-request`, `/portal/exam`, `/portal/support` × 390/1440
— 8/8 lượt HTTP 200, tràn 0, lỗi JS 0; form không bật `data-wj-validate` giữ kiểm lỗi gốc của trình duyệt.

## 6. Test tự động

`-u wujia_portal_layout,wujia_portal_support,wujia_portal_base --test-enable` trên DB copy: 0 failed / 698 (14 test mới
`test_k1_form_detail.py`, tag `wujia_support_k1`). `check_layers.py`: 0 vi phạm tầng.

**Kết luận:** 3/3 issue đạt toàn bộ mục `Kết quả mong muốn` đo được (≥ 90 %).
