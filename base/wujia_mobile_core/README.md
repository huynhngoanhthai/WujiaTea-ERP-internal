# Tài Liệu Hướng Dẫn Sử Dụng & Quy Chuẩn Phát Triển — Module `wujia_mobile_core`

Tài liệu này cung cấp hướng dẫn chi tiết cho các Lập trình viên Odoo (Dev) và Chuyên viên Vận hành về cách sử dụng, kế thừa và triển khai quy chuẩn giao diện di động dựa trên module nền tảng **`wujia_mobile_core`**.

---

## 1. Tổng Quan Module

* **Tên Module:** `wujia_mobile_core`
* **Vị trí mã nguồn:** `custom/wujia_mobile_core/`
* **Mục đích:** Cung cấp bộ quy chuẩn giao diện di động tập trung cho Odoo Backend Web Client (`web.assets_backend`), bao gồm SCSS Breakpoints, Responsive Classes, Thẻ Kanban Card (`.wj_mobile_kanban`), Header/Action Bar/Badges, QWeb Templates & OWL Components dùng chung, Python Model Mixin và Phân nhóm quyền Odoo 19.
* **Phụ thuộc:** `base`, `web`.

---

## 2. Hướng Dẫn Khai Báo Phụ Thuộc (Dependencies)

Khi phát triển bất kỳ module di động con nào (ví dụ: `wujia_mobile_sale`, `wujia_mobile_inventory`...), bắt buộc khai báo `wujia_mobile_core` trong tệp `__manifest__.py`:

```python
{
    'name': 'Wujia Mobile Sale',
    'version': '19.0.1.0.0',
    'category': 'Wujia/Mobile',
    'depends': [
        'wujia_mobile_core',  # <-- Bắt buộc phụ thuộc module core
        'sale',
    ],
    # ...
}
```

---

## 3. Quy Chuẩn Giao Diện Mobile Kanban (`.wj_mobile_kanban`)

### 3.1. Cách Sử Dụng Trong Views XML

Bất kỳ view Kanban nào hiển thị trên di động chỉ cần thêm `class="wj_mobile_kanban"` vào thẻ gốc `<kanban>`:

```xml
<record id="view_wujia_sale_order_kanban_mobile" model="ir.ui.view">
    <field name="name">wujia.sale.order.kanban.mobile</field>
    <field name="model">sale.order</field>
    <field name="arch" type="xml">
        <!-- Áp dụng class wj_mobile_kanban vào view gốc -->
        <kanban class="wj_mobile_kanban">
            <field name="name"/>
            <field name="partner_id"/>
            <field name="amount_total"/>
            <field name="state"/>
            <field name="date_order"/>
            <templates>
                <t t-name="card">
                    <div class="wj_mobile_card">
                        <!-- Header / Mã đơn & Badge -->
                        <div class="d-flex align-items-center justify-content-between mb-1">
                            <span class="wj_mobile_card__code"><field name="name"/></span>
                            <span t-attf-class="wj_mobile_badge #{record.state.raw_value == 'sale' and 'wj_mobile_badge--success' or 'wj_mobile_badge--warning'}">
                                <field name="state"/>
                            </span>
                        </div>

                        <!-- Nội dung chính / Khách hàng -->
                        <div class="wj_mobile_card__title mb-1">
                            <field name="partner_id"/>
                        </div>

                        <!-- Footer / Thông tin phụ & Giá trị nổi bật -->
                        <div class="d-flex align-items-center justify-content-between mt-2 pt-1 border-top">
                            <span class="wj_mobile_card__meta"><field name="date_order"/></span>
                            <span class="wj_mobile_card__value text-primary"><field name="amount_total"/></span>
                        </div>
                    </div>
                </t>
            </templates>
        </kanban>
    </field>
</record>
```

### 3.2. Bộ Class Thẻ Card & Text Standards (`.wj_mobile_card`)

- **`.wj_mobile_card`**: Khung padding thẻ card di động
- **`.wj_mobile_card__code`**: Mã chứng từ (SO, PO, WH/OUT...) — chữ đậm, màu thương hiệu
- **`.wj_mobile_card__title`**: Nội dung chính (Tên khách hàng, nhà cung cấp) — chữ vừa, đậm vừa
- **`.wj_mobile_card__meta`**: Thông tin phụ (Ngày tạo, kho, người phụ trách) — chữ mờ, nhỏ
- **`.wj_mobile_card__value`**: Giá trị nổi bật (Tổng tiền, tổng khối lượng kg) — chữ đậm, nổi bật

### 3.3. Bộ Class Badge Trạng Thái Chuẩn (`.wj_mobile_badge`)

* `.wj_mobile_badge--neutral`: Badge màu trung tính (Xám)
* `.wj_mobile_badge--info`: Badge màu thông tin (Xanh dương)
* `.wj_mobile_badge--warning`: Badge màu cảnh báo (Vàng)
* `.wj_mobile_badge--success`: Badge màu thành công (Xanh lá)
* `.wj_mobile_badge--danger`: Badge màu lỗi / hủy (Đỏ)

---

## 4. Hướng Dẫn Kế Thừa Python Model Mixin (`wujia.mobile.mixin`)

Khi cần lấy class CSS badge tự động từ Python backend:

```python
# -*- coding: utf-8 -*-
from odoo import models, fields

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'wujia.mobile.mixin']

    mobile_badge_class = fields.Char(
        string='Mobile Badge Class',
        compute='_compute_mobile_badge_class',
    )

    def _compute_mobile_badge_class(self):
        for rec in self:
            # Tự động trả về class wj_mobile_badge--*
            rec.mobile_badge_class = rec.get_mobile_badge_class(rec.state)
```

---

## 5. Hướng Dẫn Nhúng QWeb Templates Dùng Chung

Module core cung cấp các mẫu QWeb dùng chung:

```xml
<!-- Empty State -->
<t t-call="wujia_mobile_core.empty_state">
    <t t-set="icon">fa-shopping-cart</t>
    <t t-set="title">Chưa có đơn hàng</t>
    <t t-set="text">Không có đơn hàng nào cần xử lý.</t>
</t>

<!-- Card Section -->
<t t-call="wujia_mobile_core.card_section">
    <t t-set="section_title">Thông tin giao hàng</t>
    <group>
        <field name="partner_id"/>
    </group>
</t>
```

---

## 6. Quy Chuẩn Form View Di Động (`.o_wujia_mobile_form`)

Module `wujia_mobile_core` cung cấp bộ khung CSS tiêu chuẩn cho Form View trên màn hình điện thoại (breakpoint max-width 767px):

- Container chính: `.o_wujia_mobile_form` (kèm class responsive `.d-none .d-mb-block .w-100`).
- Tiêu đề khối: `.wujia-mobile-title`
- Danh sách các trường: `.wujia-mobile-list`
- Mỗi dòng trường: `.wujia-mobile-row` (thêm `.has-icon` nếu có icon).
- Nhãn trường: `.wujia-mobile-label`
- Vùng nội dung nhập liệu: `.wujia-mobile-content`
- Icon định danh: `.wujia-mobile-icon`
- Trường nhập liệu: `.wujia-mobile-field` (tự động xử lý underline, focus, readonly, dropdown và trạng thái invalid).

Mọi module con chỉ cần định nghĩa cấu trúc XML và không cần viết thêm bất kỳ CSS nào.

