# Ngô Gia ERP — Chuẩn lên danh sách Task cho AI Dev Agent (tab `Tasks`)

**Phiên bản:** 1.0 · **Ngày:** 21/07/2026
**Gửi cho:** BA + trợ lý GPT của BA.
**Đi kèm:** `01_NGO_GIA_QA_OPERATING_STANDARD.md` (luồng Issue List / retest).

---

## 0. Bối cảnh — vì sao cần chuẩn này

Mỗi tối **22:00** có một **AI Dev Agent** tự chạy. Nó **đọc tab `Tasks`**, chọn các task BA đánh dấu **"Sẵn sàng cho AI = Yes"**, rồi **tự đọc code + spec → tự code → tự test → commit/push** (người deploy tay), và **ghi kết quả ngược lại vào tab `Tasks`**.

Vì chạy ban đêm không ai trực, agent hoạt động theo 2 nguyên tắc cứng:

1. **Đủ thông tin thì làm, thiếu/mập mờ thì KHÔNG đoán** — agent chuyển task sang `Need Clarification` và ghi câu hỏi vào sheet để sáng hôm sau BA trả lời.
2. **Không tự đóng `Done`** — agent tối đa chỉ đưa được tới trạng thái đã-code-đã-test; BA/Tester mới xác nhận Pass.

➡️ **Task viết càng đầy đủ & rõ ràng, agent làm được càng nhiều trong đêm.** Task viết mơ hồ = sáng ra chỉ nhận được câu hỏi, không có code.

---

## 1. Cấu trúc tab `Tasks`

Giữ nguyên 7 cột gốc (A–G), **bổ sung H–R**. Cột do **BA** điền và cột do **AI** điền tách bạch — **BA không đụng cột O–R** (của AI).

| Cột | Tên | Ai điền | Nội dung / giá trị hợp lệ |
|---|---|---|---|
| A | STT | BA | Số thứ tự |
| B | Nhóm chức năng | BA | Phân hệ (Portal, Sale, Delivery, Franchise…) |
| C | Task việc | BA | Tiêu đề ngắn (1 dòng) |
| D | Mô tả | BA | Mô tả chi tiết cần làm gì |
| E | **Link/Hình ảnh** | BA | **Nguồn spec** — theo Loại task, xem §3. Bắt buộc truy cập được |
| F | Ưu tiên | BA | `Cao` / `Trung bình` / `Thấp` |
| G | Ghi chú | BA | Ghi chú thêm |
| H | **Loại task** | BA | `Controller` · `UI-Issue` · `Model-Field` · `Bugfix` · `Refactor` · `Doc` |
| I | **Module/Phạm vi** | BA | Tên module custom liên quan (vd `wujia_portal_sale`). Không chắc → để trống, agent tự tìm |
| J | **Kết quả mong muốn (Acceptance)** | BA | Tiêu chí Pass/Fail cụ thể để agent **tự kiểm** (xem §4) |
| K | **Ràng buộc / Out-of-scope** | BA | Cấm đụng gì, giữ nguyên gì |
| L | **Ngày giao** | BA | `YYYY-MM-DD` |
| M | **Sẵn sàng cho AI?** | BA | `Yes` / `No` — **cổng chính**. Chỉ `Yes` khi đủ Definition of Ready (§2) |
| N | **Cho phép tự deploy?** | BA | `No` (mặc định) — hiện agent luôn push code, người deploy tay; cột này để dành khi có CI/CD |
| O | Trạng thái (AI) | **AI** | `Queued` · `In Progress` · `Done-pushed` · `Need Clarification` · `Blocked` |
| P | Câu hỏi của Dev (AI) | **AI** | Câu hỏi khi thiếu spec / có fork |
| Q | Kết quả Dev (AI) | **AI** | Branch/commit + kết quả test + evidence |
| R | Ngày AI xử lý | **AI** | `YYYY-MM-DD` |

---

## 2. Definition of Ready for AI (điều kiện để đặt cột M = `Yes`)

BA chỉ đặt **M = Yes** khi task có đủ:

- [ ] **H Loại task** đã chọn.
- [ ] **D Mô tả** nêu rõ cần làm gì (không chỉ "sửa cho đẹp").
- [ ] **E Link** trỏ tới nguồn spec **truy cập được** đúng theo Loại task (§3).
- [ ] **J Acceptance** đủ rõ để phân biệt Pass/Fail.
- [ ] Không còn quyết định nghiệp vụ/UI nào đang chờ BA chốt.
- [ ] Nếu có đổi schema (thêm/xoá/sửa field, đổi tên model) → nói rõ trong D/K (nếu không chắc, để agent hỏi thì cứ ghi mô tả, agent sẽ defer).

Thiếu bất kỳ mục quan trọng nào → để **M = No**. Agent chỉ đụng task M = Yes.

---

## 3. Cột E (Link) phải chứa gì — theo từng Loại task (H)

| Loại task (H) | Cột E bắt buộc có |
|---|---|
| **Controller** | **URL chat ChatGPT share** của BA mô tả mapping controller (Màn hình/Action/Model/Input/Rule/Field trả về). Nếu có, trỏ thêm tab `1. Model Field` / `3. Controller` + từ khoá model |
| **UI-Issue** | **Figma node** (vd `4600:66`) **hoặc** `Issue-ID` trong tab `5. Issue List` (vd `UI-03`). Kèm viewport (PC 1920 / mobile 391) |
| **Model-Field** | Trỏ tab `1. Model Field` + tên model + danh sách field (tên, kiểu, bắt buộc/không, mặc định) |
| **Bugfix** | URL trang bị lỗi + bước tái hiện + evidence (ảnh/log). Nếu là lỗi đã có trong Issue List → ghi `Issue-ID` |
| **Refactor** | Mô tả phạm vi + file/model liên quan; nêu rõ "không đổi hành vi" |
| **Doc** | Nội dung cần viết + nơi lưu |

> Agent **verify tên model/field thật trong source** trước khi code (BA hay đặt tên lý tưởng hoá khác thật, vd `wujia.announcement` ↔ `wujia.notification`). Nếu spec BA lệch source → agent defer hỏi, **không tự đổi tên**.

---

## 4. Cột J (Acceptance) viết sao để agent tự test được

Agent test bằng: nâng cấp module (`-u` RC=0), test ORM/HTTP, và với UI thì chụp màn hình đối chiếu. Nên Acceptance nên **đo được**:

- ✅ Tốt: *"Ở /portal/order PC 1920: Account pill rộng 202px, cao 52px, hiện tên user + role dưới tên; upgrade RC=0."*
- ✅ Tốt: *"Controller trả JSON gồm field `id, name, qty, price_taxed`; đơn cancel không xuất hiện; user store khác không xem được đơn (403)."*
- ❌ Tệ: *"Làm cho đẹp hơn"* / *"Sửa lại giao diện"* (không có mốc Pass/Fail → agent defer).

---

## 5. Agent sẽ / sẽ không làm gì (để BA đúng kỳ vọng)

**Sẽ:** đọc code + spec, code trên branch riêng, test local, commit + push `main` khi test xanh, ghi kết quả vào O/Q/R, và với task đụng Issue List thì set issue tương ứng sang `Ready for Retest` (đúng QA Standard).

**Sẽ KHÔNG:** tự đóng `Done`; tự quyết khi mập mờ (sẽ defer + hỏi ở P); đổi tên model/field theo spec nếu lệch source; drop/reseed database; tạo đơn/hoá đơn/email thật; auto-deploy prod (người deploy tay).

**Ngày nào tab `Tasks` không có task M = Yes** → agent không làm gì (chỉ đồng bộ Issue List nếu có).

---

## 6. Ví dụ điền (2 dòng mẫu)

**Ví dụ A — Controller**
- C: `Controller danh sách sản phẩm portal`
- D: `Viết controller trả danh sách sản phẩm cho trang đặt hàng theo mapping BA.`
- E: `https://chatgpt.com/share/xxxxxxxx` (+ tab `3. Controller`, keyword `product`)
- H: `Controller` · I: `wujia_portal_sale` · F: `Cao`
- J: `Endpoint trả JSON [{id,name,uom,price_taxed,min_qty}]; ẩn sản phẩm is_public_portal=False; user store A không thấy sản phẩm riêng store B; upgrade RC=0; test HTTP pass.`
- K: `Không đổi model sale.order; không đụng giỏ hàng.`
- L: `2026-07-22` · M: `Yes` · N: `No`

**Ví dụ B — UI-Issue**
- C: `Chuẩn hoá Account pill header PC`
- D: `Account control PC hiện thiếu role; chuẩn theo Figma.`
- E: `Figma 4600:89–96` (hoặc Issue-ID `UI-03`)
- H: `UI-Issue` · I: `wujia_portal_layout` · F: `Trung bình`
- J: `PC 1920: pill 202×52, hiện tên + role dưới tên + chevron; desktop khác không vỡ; upgrade RC=0.`
- K: `Chỉ sửa header PC; không đụng mobile.`
- L: `2026-07-22` · M: `Yes` · N: `No`

---

## 7. PROMPT DÁN VÀO CHATGPT (để GPT lên danh sách task đúng chuẩn)

> BA copy nguyên khối dưới đây dán vào ChatGPT, rồi mô tả công việc bằng lời. GPT sẽ trả ra các dòng task đúng cấu trúc + tự chỉ ra chỗ còn thiếu.

```
Bạn là trợ lý BA của dự án Ngô Gia ERP (Odoo 19 + portal). Nhiệm vụ: chuyển mô tả
công việc của tôi thành các DÒNG TASK để một AI Dev Agent tự động thực thi ban đêm.

Xuất ra dạng BẢNG với đúng các cột sau (mỗi task 1 dòng):
STT | Nhóm chức năng | Task việc | Mô tả | Link/Hình ảnh | Ưu tiên | Ghi chú |
Loại task | Module/Phạm vi | Acceptance | Ràng buộc | Ngày giao | Sẵn sàng cho AI | Cho phép tự deploy

Quy tắc bắt buộc:
1. "Loại task" chỉ được là một trong: Controller, UI-Issue, Model-Field, Bugfix, Refactor, Doc.
2. Cột "Link/Hình ảnh" phải có nguồn spec truy cập được theo loại:
   - Controller → URL chat ChatGPT share mô tả mapping (Màn hình/Action/Model/Input/Rule/Field trả về).
   - UI-Issue → Figma node (vd 4600:66) hoặc Issue-ID (vd UI-03) + viewport.
   - Model-Field → tên model + danh sách field (tên, kiểu, bắt buộc, mặc định).
   - Bugfix → URL trang lỗi + bước tái hiện + ảnh/log.
3. "Acceptance" phải ĐO ĐƯỢC (tiêu chí Pass/Fail cụ thể: kích thước px, field JSON trả về,
   quyền truy cập, "upgrade RC=0"...). KHÔNG viết chung chung như "làm cho đẹp".
4. "Ngày giao" theo định dạng YYYY-MM-DD (hỏi tôi nếu chưa biết).
5. "Sẵn sàng cho AI" = Yes CHỈ KHI đủ: Loại task + Mô tả rõ + Link truy cập được + Acceptance +
   (nếu có) Module. Thiếu bất kỳ mục nào → đặt No và LIỆT KÊ rõ còn thiếu gì để tôi bổ sung.
6. "Cho phép tự deploy" mặc định No.
7. Nếu công việc có đổi schema (thêm/xoá/sửa field, đổi tên model) → ghi rõ trong Mô tả và Ràng buộc.
8. Nếu mô tả của tôi mơ hồ, HỎI LẠI tôi trước khi điền Yes — đừng tự bịa spec.

Bắt đầu bằng cách hỏi tôi công việc hôm nay là gì.
```

---

## 8. Liên hệ với Issue List

- **Task** = việc cần làm (intake). **Issue** = lỗi QA cần retest (tab `5. Issue List`).
- Một Task loại `UI-Issue`/`Bugfix` thường trỏ tới 1+ `Issue-ID`. Khi agent làm xong task đó, nó tự cập nhật Issue tương ứng sang `Ready for Retest` theo QA Operating Standard (điền Build/Deploy, Ghi chú FIX/IMPACT/RETEST/LIMIT, Odoo Fit, + dòng `7. ISSUE HISTORY`).
- BA/Tester retest trên UAT `https://dev.wujiatea.com.vn/` rồi mới chuyển `Done`.
