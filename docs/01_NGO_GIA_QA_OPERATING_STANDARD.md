# Ngô Gia ERP — QA Operating Standard

**Phiên bản:** 1.0  
**Ngày hiệu lực:** 21/07/2026  
**Áp dụng cho:** BA, Tester, Dev và trợ lý AI làm việc trên milestone Portal.

## 1. Mục tiêu

- Một Issue ID chỉ có một dòng trạng thái hiện hành trong `5. Issue List`.
- Mọi người nhìn vào issue đều biết ai đang giữ việc và hành động tiếp theo.
- Chỉ retest bản đã deploy rõ ràng lên UAT.
- Dev không tự đóng `Done`; BA/Tester xác nhận kết quả bằng black-box testing.
- Mọi lần đổi trạng thái đều có dấu vết trong `7. ISSUE HISTORY`.

## 2. Vai trò

| Vai trò | Trách nhiệm chính |
|---|---|
| BA | Chốt phạm vi, expected, mức ưu tiên, quyết định nghiệp vụ/UI và issue đủ điều kiện giao Dev |
| Dev | Phân tích kỹ thuật, phân loại Odoo Fit, sửa lỗi, deploy UAT và bàn giao build rõ ràng |
| Tester/BA | Chuẩn bị test, test/retest black-box, ghi evidence và kết luận Pass/Fail |
| Trợ lý AI | Đọc Sources + Sheet, lập queue, thực hiện kiểm thử được cho phép và cập nhật đúng rule |

## 3. Cấu trúc `5. Issue List`

| Cột | Nội dung | Người chịu trách nhiệm |
|---|---|---|
| A–H | STT, Phân hệ, ID, Khu vực, Vấn đề, Evidence ban đầu, Đề xuất, Kết quả mong muốn | BA/Tester |
| I | Trạng thái | BA/Tester và Dev theo luồng cho phép |
| J | Ngày cập nhật | Người vừa đổi trạng thái |
| K | Ghi chú mới nhất | BA/Tester hoặc Dev |
| L | Loại issue | BA/Tester |
| M | Severity | BA/Tester |
| N | Need BA Confirm | BA/Tester |
| O | Current Owner | Theo người đang giữ hành động tiếp theo |
| P | Build / Deploy | Dev |
| Q | Related Feature ID | BA/Tester |
| R | Odoo Fit | Dev xác nhận |

Dev không sửa nội dung gốc ở A–H. Nếu Dev không đồng ý với actual/expected, ghi câu hỏi tại K, thêm History và chuyển `Need Clarification` thay vì sửa nội dung của BA.

## 4. Luồng trạng thái duy nhất

```text
New
  → Need Clarification → Ready for Dev
  → Ready for Dev
Ready for Dev → Dev In Progress
Dev In Progress → Ready for Retest
Ready for Retest → BA Retesting
BA Retesting → Done
BA Retesting → Retest Failed → Dev In Progress → Ready for Retest
```

| Trạng thái | Ai đang giữ việc | Điều kiện/hành động tiếp theo |
|---|---|---|
| `New` | BA | Bổ sung mô tả, expected và evidence ban đầu |
| `Need Clarification` | Người phải trả lời | Chốt câu hỏi còn thiếu; không tính là Dev đang sửa |
| `Ready for Dev` | Dev | Issue đã đủ thông tin để Dev nhận |
| `Dev In Progress` | Dev | Dev đang phân tích/sửa; chưa được hiểu là đã deploy |
| `Ready for Retest` | BA/Tester | Dev đã deploy và điền đủ thông tin bàn giao |
| `BA Retesting` | BA/Tester | Đang test trên một build đã khóa |
| `Retest Failed` | Dev | Bản sửa chưa đạt; dùng lại cùng Issue ID |
| `Done` | Closed | BA/Tester đã xác nhận Pass hoặc BA đã chốt quyết định kết thúc |

### Chuyển trạng thái Dev được phép thực hiện

- `Ready for Dev` → `Dev In Progress`.
- `Retest Failed` → `Dev In Progress`.
- `Dev In Progress` → `Ready for Retest` khi đã deploy đủ điều kiện.
- Bất kỳ trạng thái Dev đang giữ → `Need Clarification` khi thật sự thiếu expected/source/quyết định; phải ghi câu hỏi cụ thể.

Dev không được chuyển `Done` và không được bỏ qua `Ready for Retest`.

## 5. Definition of Ready for Dev

BA chỉ chuyển `Ready for Dev` khi có đủ:

- Issue ID duy nhất.
- Khu vực/URL hoặc luồng bị ảnh hưởng.
- Actual mô tả được vấn đề hiện tại.
- Evidence ban đầu có thể truy cập.
- Expected đủ rõ để xác định Pass/Fail.
- Severity đã chọn.
- `Need BA Confirm = No`.
- `Current Owner = Dev`.

Thiếu bất kỳ mục nào quan trọng thì dùng `Need Clarification`, không dùng `Ready for Dev`.

## 6. Definition of Ready for Retest — Dev bắt buộc tuân thủ

Dev chỉ chuyển `Ready for Retest` sau khi:

1. Code đã được deploy lên `https://dev.wujiatea.com.vn/`.
2. Hệ thống đã deploy xong và ổn định, không còn đang restart/update.
3. Cột P `Build / Deploy` đúng mẫu:

```text
UAT | YYYY-MM-DD HH:mm | build/commit/release: <mã> | URL: <đường dẫn>
```

Ví dụ:

```text
UAT | 2026-07-22 16:30 | build: wj-portal-20260722.2 | URL: /portal/order
```

4. Cột K ghi ngắn gọn theo mẫu:

```text
FIX: <đã thay đổi gì> | IMPACT: <màn hình/luồng liên quan> | RETEST: <điểm cần kiểm tra> | LIMIT: <giới hạn còn lại hoặc Không có>
```

5. Cột R `Odoo Fit` chọn đúng một giá trị:
   - `Odoo Standard`: đáp ứng bằng chức năng chuẩn, không cần code riêng.
   - `Configuration`: đáp ứng bằng cấu hình/quyền/dữ liệu thiết lập, không viết chức năng riêng.
   - `Custom`: có thay đổi module, template, controller, JS/CSS hoặc logic riêng.
   - `Need Dev Confirm`: chưa đủ cơ sở kỹ thuật để kết luận.
   - `N/A`: không áp dụng phân loại Odoo.
6. Cột J cập nhật ngày bàn giao.
7. Cột O chuyển `BA/Tester` khi bàn giao retest.
8. Thêm một dòng vào `7. ISSUE HISTORY`.

Nếu không có mã build/commit, Dev vẫn phải cung cấp một release marker duy nhất và thời gian deploy chính xác. Không được chỉ ghi `đã sửa`, `done` hoặc `check lại giúp`.

## 7. Cách cập nhật `7. ISSUE HISTORY`

Mỗi lần đổi trạng thái, thêm một dòng, không sửa/xóa lịch sử cũ:

| Cột | Nội dung bắt buộc |
|---|---|
| Ngày | Ngày/giờ cập nhật |
| Issue ID | Đúng ID trong Issue List |
| Trạng thái cũ | Trạng thái trước khi đổi |
| Trạng thái mới | Trạng thái sau khi đổi |
| Owner sau cập nhật | Người giữ hành động tiếp theo |
| Người cập nhật | BA/Tester/Dev hoặc tên người |
| Lý do cập nhật | Nội dung thay đổi hoặc kết quả test |
| Build / Deploy | Mã build/mốc deploy đang áp dụng |
| Evidence | Link evidence có quyền truy cập |

## 8. Severity

| Severity | Cách hiểu thực tế |
|---|---|
| `Critical` | Không vào được hệ thống, rủi ro bảo mật/mất dữ liệu/kế toán nghiêm trọng, hoặc luồng cốt lõi dừng hoàn toàn và không có workaround |
| `High` | Chức năng/role quan trọng không dùng được, sai kết quả nghiệp vụ lớn, ảnh hưởng nhiều người dùng hoặc không có workaround đơn giản |
| `Medium` | Chức năng sai một phần, trường hợp phụ hoặc có workaround chấp nhận tạm thời |
| `Low` | Sai UI/text/căn chỉnh nhỏ, không làm sai nghiệp vụ |
| `Suggestion` | Đề xuất cải tiến, không phải lỗi so với expected đã duyệt |
| `TBD` | Chưa đủ thông tin để phân loại; phải đi cùng `Need BA Confirm = Yes` |

Severity do BA/Tester chốt. Dev có thể đề nghị thay đổi trong Ghi chú/History nhưng không tự sửa.

## 9. Nguyên tắc testing

### 9.1 Phạm vi

- Chỉ black-box test trên UAT, không tự đọc source để kết luận nguyên nhân kỹ thuật.
- Test theo hành vi người dùng, role, dữ liệu, URL, device/viewport và expected đã chốt.
- Với Odoo, luôn tách rõ:
  - Có sẵn theo Odoo Standard.
  - Cần Configuration.
  - Cần Custom.
  - Rủi ro dữ liệu, phân quyền, kế toán và vận hành.
- Tester không tự điền `Odoo Fit`; Dev chịu trách nhiệm kết luận kỹ thuật.

### 9.2 Điều kiện trước khi retest

- Status là `Ready for Retest`.
- Có Build / Deploy hợp lệ.
- `Need BA Confirm = No`.
- UAT không đang deploy.
- Có đúng role/tài khoản test và dữ liệu test.
- Có expected rõ và source version áp dụng.

Nếu thiếu, chưa test. Chuyển `Need Clarification` với Owner đúng người cần xử lý, ghi rõ thiếu gì.

### 9.3 Bằng chứng tối thiểu

Mỗi kết quả test phải ghi được:

- Issue ID và build.
- Ngày/giờ.
- URL hoặc luồng.
- Role/tài khoản dạng mô tả, không ghi mật khẩu.
- Device, trình duyệt, viewport/zoom nếu liên quan UI.
- Steps đã thực hiện.
- Actual quan sát được.
- Expected dùng để so sánh.
- Ảnh/video/log giao diện có link chia sẻ phù hợp.

Tên evidence đề xuất:

```text
<IssueID>_<YYYYMMDD>_<Build>_<PASS-FAIL>_<Device>
```

### 9.4 Kết luận retest

| Kết quả | Cách cập nhật |
|---|---|
| Pass | `BA Retesting` → `Done`; Owner `Closed`; ghi ngày, build và evidence |
| Fail cùng vấn đề | `BA Retesting` → `Retest Failed`; Owner `Dev`; ghi steps, actual mới và evidence; không tạo issue trùng |
| Không test được do môi trường/dữ liệu/thiếu expected | `Need Clarification`; Owner là người cần xử lý; không kết luận Fail |
| Phát hiện lỗi khác độc lập | Tạo Issue ID mới sau khi đủ actual, expected, severity và evidence |

Một issue chỉ Pass khi đạt toàn bộ expected của issue. Không dùng `Done` cho trường hợp “đỡ hơn”, “gần đúng” hoặc “đã sửa một phần”.

### 9.5 Regression sau khi sửa

- `Critical/High`: test lại issue, luồng chính liên quan, role liên quan và PC/mobile nếu cùng component dùng chung.
- `Medium`: test issue và ít nhất một luồng liền trước/liền sau có khả năng bị ảnh hưởng.
- `Low`: test đúng viewport/component và một màn hình khác đang tái sử dụng component nếu có.
- Nếu Dev khai báo `IMPACT` rộng, phạm vi regression lấy theo phạm vi rộng hơn.

## 10. Giới hạn an toàn

Không tự thực hiện các hành động sau nếu chưa được BA cho phép rõ cho đúng phiên test:

- Tạo/xác nhận đơn thật.
- Tạo/post/cancel hóa đơn hoặc bút toán.
- Thanh toán, hoàn tiền hoặc đối soát.
- Xóa dữ liệu.
- Đổi quyền/role/công ty/cửa hàng của người dùng.
- Gửi email/SMS/thông báo thật cho khách hàng.
- Test tải lớn hoặc thao tác có thể ảnh hưởng người khác.

Chỉ sử dụng dữ liệu test có thể nhận diện. Không đưa mật khẩu, token hoặc dữ liệu nhạy cảm vào Sheet, Project Sources hay evidence.

## 11. Checklist audit bàn giao của Dev

- [ ] Đúng Issue ID.
- [ ] Status `Ready for Retest`.
- [ ] UAT đã deploy xong.
- [ ] Build / Deploy đúng mẫu và có URL.
- [ ] Ghi chú có FIX, IMPACT, RETEST và LIMIT.
- [ ] Odoo Fit đã chọn.
- [ ] Ngày cập nhật mới.
- [ ] Owner là `BA/Tester`.
- [ ] Có dòng Issue History.
- [ ] Dev không tự đóng `Done`.
