# UAT — cách truy cập và cách chẩn đoán lỗi 500

Ghi lại sau sự cố 05/08/2026 (toàn bộ `/portal/*` trả lỗi 500). Dùng cho các phiên sau.

## 1. Máy chủ UAT

| | |
|---|---|
| Odoo | https://dev.wujiatea.com.vn — DB `wujia_tea_19`, tài khoản chờ chủ dự án báo (từ 12/10/2026) |
| Quản lý máy chủ | aaPanel https://aapanel.hongtrangogia.com/4b9b3f91 — tài khoản ở `docs/CREDENTIALS.md` |
| Máy cũ (ngừng dùng 12/10/2026) | http://113.161.187.126:8019 — `admin` / `Wujia@2026`; các dòng Windows/RDP dưới đây là của máy này |
| Hệ điều hành | Windows, mã nguồn nằm ở `D:\wujia-tea` |
| RDP | `113.161.187.126:5761`, tài khoản `dev` / `Dev@2026` |
| SSH | **không có** |

### Vào RDP
Máy dev cài sẵn Remmina (`/usr/bin/remmina`) — mở giao diện, tạo kết nối RDP tới
`113.161.187.126:5761`. Bằng dòng lệnh:

```bash
remmina -c rdp://dev@113.161.187.126:5761        # hoặc
xfreerdp3 /v:113.161.187.126:5761 /u:dev /p:'Dev@2026' /dynamic-resolution
```

Vào rồi thì log Odoo nằm cạnh mã nguồn trong `D:\wujia-tea` (thư mục `logs`), đọc phần cuối file
để lấy traceback.

> **Giới hạn của agent:** phiên Claude chạy headless, không mở được cửa sổ RDP. Muốn agent đọc log
> UAT trực tiếp thì phải có người mở RDP rồi dán log vào, **hoặc** dùng cách ở mục 2 — cách này
> không cần RDP và đã cho ra nguyên nhân trong sự cố 05/08.

## 2. Chẩn đoán lỗi 500 mà không cần RDP

Trang lỗi 500 của UAT chỉ trả về 290 byte werkzeug trần, không kèm traceback, kể cả khi thêm
`?debug=1` và đăng nhập admin. Cách moi thông tin theo thứ tự:

1. **JSON-RPC vẫn trả traceback đầy đủ.** Đăng nhập `/web/session/authenticate` rồi gọi
   `/web/dataset/call_kw`; lỗi trả về có trường `error.data.debug`. Dùng để đọc trạng thái module,
   `ir.ui.view`, `ir.logging`… (`ir.ui.view.render_public_asset` **không** dùng được: template
   portal là qweb primary nên bị chặn "riêng tư".)
2. **Đối chiếu môi trường.** So danh sách module `installed` giữa UAT và bản local — chính bước này
   lộ ra UAT có `website`, `website_sale` và ~20 module eCommerce mà bản local không có.
3. **Tái hiện trên bản sao cô lập** (công thức ở `docs/issue-clusters/prompts.md`): dựng DB copy,
   cài đúng những module UAT có mà local không có, chạy lại route → lỗi hiện ra y hệt và
   traceback đầy đủ nằm trong `logs/odoo.log` của máy dev.

Bước 2 + 3 là bước quyết định: đừng đoán từ mã nguồn, hãy làm cho môi trường local giống UAT rồi
đọc log của chính mình.

## 3. Sự cố 05/08/2026 — nguyên nhân và cách xử lý

**Hiện tượng:** mọi đường dẫn `/portal/*` trả 500, giao diện quản trị `/odoo` vẫn bình thường.

**Nguyên nhân:** app **Website / eCommerce** được cài thêm vào UAT. Shell portal tự dựng phần
`<head>` nên phải tự gọi khối session info (`wujia_portal_layout/views/layouts.xml`, thêm từ
WJ-ORD-002). Các route portal là route http thường, không khai báo `website=True`, nên Odoo không
gán `request.website` / `request.lang`; bản mở rộng của app Website lại đọc thẳng hai thuộc tính đó
⇒ `AttributeError` giữa lúc dựng trang ⇒ 500 trên **mọi** trang portal.

Đây là xung khắc có sẵn từ trước, **không phải do đợt phát hành cụm H2** — bản sao local ở đúng
commit H2 mà không có app Website thì 9/9 đường dẫn chạy bình thường.

**Đã sửa:** `wujia_portal_layout/models/ir_http.py` gán sẵn website hiện hành và ngôn ngữ trước khi
lấy session info, nên portal chạy được dù có hay không có app Website.

**Cần quyết định:** UAT có thật sự cần app Website / eCommerce không. Nếu không, nên gỡ để hệ thống
gọn lại; bản vá trên vẫn giữ để phòng lần sau.
