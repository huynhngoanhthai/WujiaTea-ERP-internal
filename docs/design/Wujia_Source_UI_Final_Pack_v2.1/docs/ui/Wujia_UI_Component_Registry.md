# Wujia UI Component Registry

**Dự án:** Ngô Gia / Wujia Internal ERP — Franchise Portal  
**Mục đích:** Làm “source of truth” cho các component UI mobile đã chốt, để khi làm màn hình mới không bị mỗi trang một kiểu header, filter, warning bar, bottom nav, card/list.

**Document version:** v3  
**Cập nhật chính:** thêm `WJ_Mobile_CurrentStoreStrip_v1` — dải thông tin cửa hàng compact dưới header cho các trang ngoài Home.  


> Cách dùng nhanh trong chat mới: upload file này và ghi:  
> “Dùng đúng Wujia UI Component Registry này. Không tự thiết kế lại header/filter/current store strip/bottom nav. Màn mới chỉ thiết kế phần nội dung riêng.”

---

## 1. Nguyên tắc chung

| Nhóm | Quy định |
|---|---|
| Mobile base frame | `391px` width. Có thể responsive cho `375px – 414px`. |
| Layout mobile | 1 cột, scroll dọc, không dùng table nhiều cột. |
| Nền trang | `#F3F6F8` cho mockup mobile mới. Nếu bám code production desktop thì kiểm tra lại `#E8ECEF`. |
| Màu brand mobile đang chốt | `#28A9DF`. |
| Màu hover / strip đậm | `#1895C7`. |
| Card background | `#FFFFFF`. |
| Border/divider | `#E5E7EB`. |
| Text chính | `#111827`. |
| Text phụ | `#6B7280`. |
| Text muted | `#8A9099`. |
| Badge đỏ | `#EF4444` hoặc `#EC3845`; ưu tiên `#EF4444` theo SVG header mobile đã gửi. |
| Font | Inter / Arial / system sans-serif. Nếu có tiếng Hoa/CJK, dùng thêm Noto Sans CJK fallback. |
| Icon | Ưu tiên Font Awesome style / `react-icons/fa6`, không pha nhiều bộ icon khác nhau. |
| Radius card | `14px – 16px`, riêng hero/dashboard có thể `20px – 24px`. |
| Page padding mobile | `16px`. |
| Section gap | `16px – 20px`. |
| Bottom padding | Chừa `88px – 96px` để nội dung không bị bottom nav/CTA che. |

---

## 2. Component đã chốt

### 2.1 `WJ_Mobile_Header_Primary`

**Mục đích:** Header xanh dùng chung cho toàn bộ mobile portal.

| Thuộc tính | Giá trị chuẩn |
|---|---|
| Base width | `391px` |
| Header height | `112px` |
| Background | `#28A9DF` |
| Bottom strip | `#1895C7`, opacity thấp, cao khoảng `8px` |
| Logo | Logo Ngô Gia trong pill trắng bên trái |
| Logo pill | khoảng `x=16`, `y=42`, `w=118`, `h=46`, radius `14px` |
| Icon phải | Cart, notification bell, avatar |
| Icon style | Font Awesome / solid, màu trắng |
| Badge | Red circle `#EF4444`, text trắng, chỉ hiện khi count > 0 |
| Avatar | Icon user trắng trên vòng tròn trắng mờ |
| Không được | Không tự đổi height, màu nền, vị trí icon giữa các màn. |

**Source tham chiếu:** SVG header do BA gửi trong chat, bắt đầu bằng `width="391" height="1200"` và header background `#28A9DF`.

**Rule khi làm màn mới:**

```text
Reuse WJ_Mobile_Header_Primary.
Không tự dựng header khác.
Chỉ thay đổi badge count, logo file nếu cần.
```

---

### 2.2 `WJ_Mobile_BottomNav`

**Mục đích:** Thanh điều hướng dưới mobile.

| Thuộc tính | Giá trị chuẩn |
|---|---|
| Position | Fixed bottom |
| Height | `72px – 80px` |
| Background | `#FFFFFF` |
| Shadow | Nhẹ phía trên |
| Border top | `1px #E5E7EB` |
| Số tab | 5 |
| Icon size | `22px – 24px` |
| Label size | `11px – 12px` |
| Active color | Đang dùng đỏ nhấn ở mockup; có thể chốt lại xanh nếu BA muốn đồng bộ hoàn toàn |
| Inactive color | `#8A9099` |

**Tab chuẩn:** Trang chủ, Đặt hàng, Giao hàng, Thông báo, Thêm.

**Menu trong “Thêm”:** Đổi trả, Đào tạo/Thi, Kiến thức, Hỗ trợ, Hồ sơ cửa hàng, Cài đặt.

---


### 2.10 `WJ_Mobile_FooterActionBar`

**Mục đích:** Thanh footer action / bottom navigation chuẩn cho mobile portal, dùng cố định ở đáy màn hình. Đây là component mới BA vừa gửi bằng SVG và cần ưu tiên dùng cho các mockup mobile sau này.

| Thuộc tính | Giá trị chuẩn |
|---|---|
| Base width | `391px` |
| Height | `83px` |
| Position | Fixed bottom |
| Background | `#FFFFFF` |
| Border / top line | `#EEF2F5` |
| Số action | 5 |
| Actions | `Trang chủ`, `Đặt hàng`, `Giao hàng`, `Thông báo`, `Thêm` |
| Active item | `Trang chủ` |
| Active color | `#EF4444` |
| Inactive color | `#8A939E` |
| Badge | Circle đỏ `#EF4444`, text trắng; dùng cho `Thông báo` khi có unread count |
| Icon style | Solid icon, đồng bộ với Font Awesome style |
| Text label | Font sans-serif, nhỏ, canh giữa dưới icon |

**Source tham chiếu:** `WJ_Mobile_FooterActionBar.svg`, SVG BA gửi có `width="391"`, `height="83"`, nền trắng và viền `#EEF2F5`.

**Rule khi làm màn mới:**

```text
Reuse WJ_Mobile_FooterActionBar.
Không tự dựng lại bottom nav/footer action khác.
Chỉ thay đổi active item theo màn hiện tại và badge count nếu cần.
Giữ height 83px, nền trắng, border #EEF2F5, inactive #8A939E.
```

**Mapping active item đề xuất:**

| Màn hình | Active footer action |
|---|---|
| Dashboard / Home | Trang chủ |
| Product List / Cart / Order | Đặt hàng |
| Delivery | Giao hàng |
| Notification | Thông báo |
| Knowledge / Ticket / Return / Exam / Profile | Thêm |

### 2.3 `WJ_Mobile_SearchFilter_Order`

**Mục đích:** Filter/search chuẩn cho trang Đặt hàng, dùng làm mẫu cho các màn listing khác.

| Thuộc tính | Giá trị chuẩn |
|---|---|
| Container | Card trắng hoặc block trắng đơn giản |
| Padding | `12px – 16px` |
| Gap | `8px – 10px` |
| Input height | `42px – 44px` |
| Input radius | `10px – 12px` |
| Border | `1px #E5E7EB` |
| Placeholder | “Tìm sản phẩm” |
| Category/filter | Có filter “Tất cả” / category; không cần link “Xem tất cả” ở title nếu đã có filter Tất cả |
| Button search | Primary `#28A9DF`, height `42px – 44px`, radius `10px – 12px` |

**Rule tái sử dụng cho màn khác:**

| Màn hình | Placeholder | Field/filter có thể đổi |
|---|---|---|
| Đặt hàng | Tìm sản phẩm | Danh mục |
| Lịch sử đặt hàng | Tìm mã đơn | Trạng thái, ngày |
| Giao hàng | Tìm mã giao hàng/chuyến | Trạng thái, ngày giao |
| Đổi trả | Tìm mã yêu cầu | Trạng thái |
| Kiến thức | Tìm bài viết | Danh mục |

**Không được:** Mỗi màn tự tạo filter mới khác height, radius, màu, padding.

---

### 2.4 `WJ_Mobile_OrderWarningBar`

**Mục đích:** Hiển thị cảnh báo khung giờ đặt hàng.

| Thuộc tính | Giá trị chuẩn |
|---|---|
| Background | Đỏ nhạt / hồng nhạt |
| Text color | Đỏ `#EF4444` hoặc `#EC3845` |
| Height | `36px – 44px` |
| Radius | `10px – 12px` |
| Padding | `10px – 12px` |
| Text đề xuất | `Khung giờ đặt hàng: 10:00 - 04:00` |
| Dùng ở | Product List và Cart |

**Rule:** Cart cũng dùng warning bar giống Product List, không dùng card riêng cho khung giờ.

---

### 2.5 `WJ_Mobile_ProductRow_Compact`

**Mục đích:** Dòng sản phẩm compact cho danh sách sản phẩm, tránh card quá lớn vì có nhiều sản phẩm.

| Thuộc tính | Giá trị chuẩn |
|---|---|
| Row height | khoảng `68px – 76px` |
| Layout | Row ngang trong list/card |
| Padding | `10px – 12px` |
| Divider | `1px #E5E7EB` |
| Product name | Max 1–2 dòng, dài thì ellipsis |
| Quy cách/UoM | Font `12px – 13px`, text phụ |
| Price | Canh phải, bold |
| Add button | Icon cart/plus màu primary, touch area tối thiểu `40px` |
| Quantity badge | Chỉ hiện nếu đã thêm vào giỏ |

**Không được:** Dùng card lớn khiến một màn chỉ hiển thị được 2–3 sản phẩm.

---

### 2.6 `WJ_Mobile_CartRow_Fixed`

**Mục đích:** Dòng sản phẩm trong giỏ hàng, đã sửa ở v8/v9 để không bể layout.

| Thuộc tính | Giá trị chuẩn |
|---|---|
| Row height | khoảng `90px – 96px` |
| Padding | `14px 16px` |
| Product name | Max 1 dòng, ellipsis |
| UoM + đơn giá | 1 dòng, font `13px`, màu `#6B7280` |
| Quantity stepper | Fixed width khoảng `112px – 120px` |
| Stepper button | Touch area tối thiểu `32px` |
| Total amount | Fixed width khoảng `100px – 110px`, `text-align: right` |
| Delete button | `40x40px`, icon thùng rác căn giữa tuyệt đối |
| Divider | `1px #E5E7EB` |
| Không dùng badge | Không cần badge “Đang bán” vì sản phẩm hiện portal mặc định là đang bán |

**Layout rule quan trọng:**

```text
Không để thành tiền nằm cùng vùng với quantity stepper.
Không để icon thùng rác tự trôi theo text.
Tên sản phẩm dài phải ellipsis, không đẩy vỡ dòng quantity/amount.
```

---

### 2.7 `WJ_Mobile_CartScrollContainer`

**Mục đích:** Danh sách sản phẩm trong cart.

| Thuộc tính | Giá trị chuẩn |
|---|---|
| Hiển thị | Render toàn bộ sản phẩm trong khung |
| Scroll | `overflow-y: auto` nếu danh sách dài |
| Không dùng | Không dùng “Xem thêm”, không collapse, không phân trang |
| Container | Có max-height tùy viewport |
| Padding bottom | Chừa chỗ cho sticky summary/CTA |

**Rule dev:**

```text
Cart không dùng “Xem thêm”.
Render toàn bộ sản phẩm trong .cart-items-scroll-container.
Nếu danh sách dài, container tự scroll dọc.
```

---

### 2.8 `WJ_Mobile_CartSummaryCTA`

**Mục đích:** Tổng tiền và nút gửi đơn cuối trang cart.

| Thuộc tính | Giá trị chuẩn |
|---|---|
| Position | Sticky bottom trong content hoặc đặt ngay trên bottom nav |
| Background | `#FFFFFF` |
| Border/shadow | Nhẹ |
| Total label | Text phụ |
| Total value | Bold, `#111827` |
| Submit button | Primary `#28A9DF`, height `48px – 52px`, radius `12px` |
| Warning | Nếu ngoài khung giờ thì disable submit và hiện message rõ |

---

### 2.9 `WJ_Mobile_BackSecondaryButton`

**Mục đích:** Nút quay lại/chọn tiếp sản phẩm trong Cart mà không làm thay đổi header xanh.

| Thuộc tính | Giá trị chuẩn |
|---|---|
| Text | “Tiếp tục chọn sản phẩm” |
| Vị trí | Dưới title trang Cart |
| Style | Secondary button |
| Height | `44px` |
| Radius | `10px – 12px` |
| Icon | Arrow-left nhỏ nếu cần |
| Không được | Không đưa nút back vào header xanh để tránh phải sửa header dùng chung |

---

## 3. Màn hình / version đã chốt

### 3.1 Dashboard Mobile

| Hạng mục | Bản chốt / ghi chú |
|---|---|
| Dashboard direction | App-like mobile dashboard theo tham khảo Mitsubishi nhưng giữ Ngô Gia brand |
| Header | Dùng `WJ_Mobile_Header_Primary` |
| Hero card | Giữ card tổng quan cửa hàng xanh đậm, bỏ hình ly trà |
| Hero card height | Compact, khoảng `180px – 210px` |
| Quick actions | 2 cột, button xanh Ngô Gia |
| Content | Card/list, không table |
| Version tham chiếu | `ngo_gia_mobile_dashboard_header_blue_refined_detailed_v5` |

### 3.2 Order Mobile

| Hạng mục | Bản chốt / ghi chú |
|---|---|
| Product List | Compact row, không dùng card lớn |
| Search/filter | Dùng `WJ_Mobile_SearchFilter_Order` |
| Warning bar | Dùng `WJ_Mobile_OrderWarningBar` |
| Cart | Dùng cart layout v9 |
| Cart list | Render toàn bộ sản phẩm trong scroll container |
| Không dùng | Không dùng “Xem thêm” trong cart, không dùng badge “Đang bán” |
| Version tham chiếu | `ngo_gia_mobile_order_page_v11_registry_header_fixed` |

### 3.3 Current Store Strip Mobile

| Hạng mục | Bản chốt / ghi chú |
|---|---|
| Component | `WJ_Mobile_CurrentStoreStrip_v1` |
| Layout | `[H000] Cửa hàng Nguyễn Trãi                  Owner` |
| Vị trí | Ngay dưới header xanh ở các trang ngoài Home |
| Không dùng | Không hiển thị câu “Đang thao tác cho cửa hàng này.” |
| Version tham chiếu | `WJ_Mobile_CurrentStoreStrip_v1.svg` |

---

## 4. Quy tắc khi làm màn hình mới

### 4.1 Component phải reuse

Khi làm bất kỳ màn mobile mới nào, bắt buộc dùng lại:

```text
WJ_Mobile_Header_Primary
WJ_Mobile_BottomNav
WJ_Mobile_FooterActionBar
WJ_Mobile_CurrentStoreStrip
WJ_Mobile_SearchFilter hoặc variant của nó
WJ_Mobile_OrderWarningBar nếu có cảnh báo/thời gian
WJ_Badge_Status
WJ_Button_Primary
WJ_Button_Secondary
```

### 4.2 Không tự thiết kế lại các block dùng chung

| Block | Quy định |
|---|---|
| Header xanh | Không tự dựng lại |
| Bottom nav | Không tự dựng lại |
| Search/filter | Dùng variant, không đổi style gốc |
| Warning bar | Dùng đúng style gốc |
| Badge trạng thái | Dùng màu state chuẩn |
| Button | Dùng primary/secondary chuẩn |

### 4.3 Khi cần đổi component

Không sửa riêng từng màn. Phải sửa component gốc và ghi version mới:

```text
WJ_Mobile_Header_Primary_v2
WJ_Mobile_SearchFilter_v2
```

---

## 5. Prompt mẫu dùng cho chat mới

```text
Context:
Dự án Wujia / Ngô Gia Franchise Portal.
Dùng đúng file Wujia UI Component Registry này làm source of truth.
Mobile base frame 391px.
Primary color #28A9DF.
Header mobile dùng WJ_Mobile_Header_Primary.
Bottom nav/footer action dùng WJ_Mobile_FooterActionBar.
Search/filter dùng component chuẩn, không tự thiết kế lại.
Màn đang cần làm: [tên màn].
Yêu cầu: thiết kế phần nội dung riêng, giữ nguyên header/filter/bottom nav chuẩn.
```

---

## 6. Checklist nghiệm thu UI mobile

| Tiêu chí | Đạt/Không |
|---|---|
| Header đúng `WJ_Mobile_Header_Primary` |
| Footer action đúng `WJ_Mobile_FooterActionBar` |
| Màu header đúng `#28A9DF` |
| Logo đúng trong pill trắng |
| Cart/bell/avatar đúng vị trí và màu trắng |
| Badge đỏ đúng kích thước, không lệch |
| Filter/search giống component chuẩn |
| Warning bar giống Product List/Cart |
| Không có link “Xem tất cả” thừa khi đã có filter Tất cả |
| Product row compact, không quá cao |
| Cart row không bể layout |
| Thành tiền không đè số lượng |
| Icon thùng rác thẳng hàng |
| Nội dung không bị bottom nav/CTA che |
| Mobile 375px, 391px, 414px không vỡ layout |
| Empty/loading/error state có thiết kế hoặc ghi chú rõ |

---

## 7. Open decisions cần BA chốt thêm

| Vấn đề | Hiện trạng | Đề xuất |
|---|---|---|
| Primary color code thật vs mockup | Code production từng ghi `#22A9DE`, mockup/header đang dùng `#28A9DF` | BA chốt 1 màu cuối cùng. Với mockup mobile hiện tại: dùng `#28A9DF`. |
| Active bottom nav | Có lúc dùng đỏ, có lúc nên dùng xanh brand | Chốt sau khi xem tổng thể. Nếu ưu tiên đồng bộ brand, dùng xanh; nếu muốn nổi tab active, dùng đỏ. |
| Header height | SVG chuẩn đang khoảng `112px` | Giữ `112px` cho mobile header nếu không có lý do đổi. |
| Logo source | Có nhiều file logo/favicon | Nên chốt 1 PNG/SVG logo chính thức cho mobile header. |
