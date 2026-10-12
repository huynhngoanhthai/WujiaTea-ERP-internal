# Wujia UI Component Registry — FINAL v1

## Trạng thái
Bản này là **mobile shell final** đã chốt cho Wujia / Ngô Gia Franchise Portal.

## Frame chuẩn
- Mobile frame: `391 × 844px`
- Export mockup: `@3x`
- Background app: `#F3F6F8`
- Font: `Inter / Arial / Helvetica`

## Cấu trúc layout cố định

| Block | Component | Vị trí | Kích thước | Ghi chú |
|---|---|---:|---:|---|
| Header | `WJ_Mobile_Header_Primary_FINAL_v1` | `x=0, y=0` | `391 × 104` | Header xanh liền khối, không có dải xanh đậm |
| Current Store | `WJ_Mobile_CurrentStoreStrip_FINAL_v1` | `x=0, y=104` | `391 × 48` | Hiển thị store context ngắn gọn |
| Content | Page content area | `x=0, y=152` | `391 × 609` | Padding ngang 16px, padding bottom tối thiểu 96px |
| Footer | `WJ_Mobile_FooterActionBar_FINAL_v1` | `x=0, y=761` | `391 × 83` | Fixed bottom navigation |

## Header mobile final

**Component:** `WJ_Mobile_Header_Primary_FINAL_v1`

Thông số:
- Height: `104px`
- Background: `#28A9DF`
- Không dùng dải xanh đậm ở đáy header.
- Logo slot bên trái: `x=16, y=32, w=116, h=44, radius=14`.
- Logo asset hiện tại chỉ là placeholder. Khách hàng/designer cần cung cấp logo tối ưu cho mobile header.
- Right actions: `Language flag / Cart shortcut / Avatar`.
- Bỏ notification bell khỏi header mobile.
- Cart trên header là shortcut vào giỏ hàng hiện tại, không phải tab `Đặt hàng`.

## Current Store Strip final

**Component:** `WJ_Mobile_CurrentStoreStrip_FINAL_v1`

Thông số:
- Height: `48px`
- Background: `#FFFFFF`
- Bottom border: `#EEF2F5`
- Nội dung: `[H000] Cửa hàng Nguyễn Trãi    Owner`
- Không thêm dòng phụ như “Đang thao tác cho cửa hàng này”.
- Không thêm địa chỉ, hotline, mô tả dài trong strip.

## Footer final

**Component:** `WJ_Mobile_FooterActionBar_FINAL_v1`

Thông số:
- Height: `83px`
- Background: `#FFFFFF`
- Top border: `#EEF2F5`
- Tabs: `Trang chủ / Đặt hàng / Giao hàng / Thông báo / Thêm`
- Active tab: brand cyan `#28A9DF`
- Inactive tab: `#8A939E`
- Badge thông báo: `#EF4444`
- Quy tắc màu: xanh = brand/active/navigation, đỏ = badge/cảnh báo/thông báo.

## Spacing rules cho trang con

| Rule | Giá trị chốt |
|---|---:|
| Content padding trái/phải | `16px` |
| Store strip → page title | `16px` |
| Page title → filter/search | `12px` |
| Filter/search → list/card | `12–16px` |
| Khoảng cách giữa card/list item | `10–12px` |
| Padding bottom của content khi có fixed footer | `≥96px` |
| Card radius đề xuất | `14px` |
| Main card background | `#FFFFFF` |
| Main border | `#E5E7EB` hoặc `#EEF2F5` |

## Developer implementation note

```css
:root {
  --wj-primary: #28A9DF;
  --wj-bg: #F3F6F8;
  --wj-surface: #FFFFFF;
  --wj-border: #EEF2F5;
  --wj-text: #111827;
  --wj-muted: #6B7280;
  --wj-inactive: #8A939E;
  --wj-danger: #EF4444;
}

.wj-mobile-header {
  height: 104px;
  background: var(--wj-primary);
}

.wj-current-store-strip {
  height: 48px;
  background: var(--wj-surface);
  border-bottom: 1px solid var(--wj-border);
}

.wj-mobile-content {
  padding: 16px 16px 104px;
  background: var(--wj-bg);
}

.wj-mobile-footer {
  height: 83px;
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--wj-surface);
  border-top: 1px solid var(--wj-border);
}
```

## File trong pack

- `WJ_Mobile_BlankShell_FINAL_v1.svg`
- `WJ_Mobile_BlankShell_FINAL_v1@3x.png`
- `WJ_Mobile_BlankShell_FINAL_v1_annotated.svg`
- `WJ_Mobile_BlankShell_FINAL_v1_annotated@3x.png`
- `WJ_Mobile_Header_Primary_FINAL_v1.svg`
- `WJ_Mobile_Header_Primary_FINAL_v1@3x.png`
- `WJ_Mobile_CurrentStoreStrip_FINAL_v1.svg`
- `WJ_Mobile_CurrentStoreStrip_FINAL_v1@3x.png`
- `WJ_Mobile_FooterActionBar_FINAL_v1.svg`
- `WJ_Mobile_FooterActionBar_FINAL_v1@3x.png`
- `Wujia_UI_Component_Registry_FINAL_v1.json`
- `Wujia_UI_Design_Tokens_FINAL_v1.css`
- `Wujia_UI_Component_Registry_FINAL_v1.md`
- `Wujia_UI_CHANGELOG_FINAL_v1.md`
