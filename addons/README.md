# addons/ — module riêng của bản triển khai

Thư mục này **rỗng ở core**. Mỗi quốc gia / bên nhượng quyền là một bản clone của repo core; module chỉ dùng cho
bản đó đặt ở đây, mỗi module một thư mục con (`addons/<ten_module>/`).

- Không sửa các thư mục core (`base/`, `franchise/`, `sales/`, `portal/`…) trong bản clone. Thiếu điểm mở thì sửa ở
  core rồi kéo về.
- Module ở đây kế thừa module core bằng `_inherit` / xpath và khai `depends` tới module core nó mở rộng.
- `addons/` đã nằm sẵn trong `addons_path` (xem `scripts/wj_paths.py`).
