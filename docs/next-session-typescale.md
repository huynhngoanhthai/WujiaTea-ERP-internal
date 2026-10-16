# Cụm TS — Thang chữ một nguồn ở base (lập 16/10/2026)

> Chủ dự án chốt 16/10: cỡ chữ portal phải **gắn ở base**: sửa một dòng là mọi màn đổi theo. Làm dần qua nhiều phiên.
> **BA gửi bản 2 ngày 16/10** (đổi 9/12 vai trò so với đề xuất; thay bản 1 "giữ nguyên") — số ở §2, nguyên văn §7. Chủ dự án chốt: **áp nguyên bản 2**, không chờ hỏi lại.
> Trang xem thử: <https://claude.ai/artifact/B3TgSv8yDKawdBxYxcPpp4>.
> Màn chỉ gọi vai trò, số nằm ở `_variables.css`; sau này BA đổi số thì chỉ sửa file đó.
> Nối tiếp KT (PR #17) và KT2 (PR #20, merge `7636d929`, đã lên UAT). TS0 tách nhánh từ `origin/deploy/staging` ≥ `7636d929`.

## 0. Luật áp suốt cụm

- Tách `feature/ts<N>-…` từ `origin/deploy/staging` (PR #20 đã merge 16/10); PR về `deploy/staging`.
- Không sửa code anh Thái: `wujia_franchise*`, `wujia_portal_inspection`, `wujia_mobile_*`. Khảo sát ngoài phạm vi.
- Không `-u wujia_core --test-enable`; không chạy hai `-u` cùng lúc. Test trên DB copy (`wujia_kt` còn dùng được).
- Đổi CSS thì bump `?v=` ở `wujia_portal_layout/views/assets.xml` + version mọi module có file đổi.
- Mỗi phiên chuyển **theo vai trò của phần tử, không theo con số đang có** (bảng §3). Giá trị lẻ (12.5, 13.5, 17, 19…) về vai trò gần nhất.
- Đo trước/sau bằng `scripts/qa/wj_type_audit.py` (§5). Đổi nhìn thấy được phải ghi vào mục phiên ở `f-progress.md`.
- UAT chỉ đọc. Merge và deploy chỉ khi chủ dự án duyệt từng PR.

## 1. Hiện trạng (đo 16/10 trên nhánh PR #20)

`font-size` gõ cứng trong CSS portal của team (bỏ `_variables.css`, thư viện ngoài, Khảo sát):

| | Số chỗ |
|---|---|
| Chữ (phải về vai trò) | **426** |
| Icon | 88 |
| Chấm đếm số / ô ảnh thay thế | 38 |
| Đã qua token | 126 |

Theo file (chữ · icon · chấm đếm):

| File | Chữ | Icon | Đếm | Phiên |
|---|---|---|---|---|
| `wujia_portal_layout/_components.css` | 72 | 28 | 16 | TS1 |
| `wujia_portal_layout/_pc_components.css` | 36 | 5 | 3 | TS1 |
| `wujia_portal_layout/_auth.css` | 31 | 6 | 0 | TS2 |
| `wujia_portal_layout/_pc_account.css` | 31 | 6 | 1 | TS2 |
| `wujia_portal_layout/_sidebar.css` | 2 | 0 | 0 | TS2 |
| `wujia_portal_base/portal_dashboard.css` | 17 | 3 | 2 | TS2 |
| `wujia_portal_base/store_picker.css` | 8 | 1 | 2 | TS2 |
| `wujia_portal_exam/portal_exam.css` | 87 | 11 | 3 | TS3 |
| `wujia_portal_sale/portal_order.css` | 53 | 9 | 9 | TS4 |
| `wujia_portal_report/portal_report.css` | 18 | 1 | 0 | TS4 |
| `wujia_portal_debt/portal_debt.css` | 24 | 8 | 0 | TS5 |
| `wujia_portal_notification/portal_notification.css` | 21 | 7 | 1 | TS5 |
| `wujia_portal_delivery/portal_delivery.css` | 10 | 3 | 1 | TS5 |
| `wujia_portal_return/portal_return.css` | 6 | 0 | 0 | TS5 |
| `wujia_portal_purchase_history/portal_history.css` | 5 | 0 | 0 | TS5 |
| `wujia_portal_knowledge/portal_knowledge.css` | 4 | 0 | 0 | TS5 |
| `wujia_portal_support/portal_support.css` | 1 | 0 | 0 | TS5 |

Ngoài CSS:
- 4 `style="font-size:…"` trong `wujia_portal_base/views/store_picker_modal.xml` (TS2).
- 36 chỗ class Bootstrap `small` / `fs-*` / `h1`–`h6` / `<small>` trong QWeb portal (TS5).
- 6 `fontSize` trong `wujia_portal_report/static/src/js/portal_report_charts.js` (TS4).
- ~~`html { font-size }` đổi 14 → 15 → 16px theo khổ~~ — TS0 đo: rule đó chưa từng ăn, Vuexy `components.css` (nạp sau) ép 14px mọi khổ; TS0 ghi một dòng 14px (Q1).

## 2. Thang BA gửi (bản 2, 16/10) — chiều cao dòng và độ đậm do dev đặt

| Vai trò | Token | PC | Mobile | Đậm | Ghi chú |
|---|---|---|---|---|---|
| Tiêu đề trang | `--wj-t-page` | 24/32 | 20/28 | 700 | đang là số cứng ở `.wj-page-header--pc/--m` (26/22) |
| Tiêu đề nhóm | `--wj-t-section` | 18/24 | 16/22 | 700 | alias `--wujia-m-sechead-*`; mobile 18 → 16 khác #143 (Q7) |
| Tiêu đề thẻ | `--wj-t-card` | 17/24 | 15/20 | 700 | CardHeader compact (đang 18/16) |
| Số KPI | `--wj-t-kpi` | 22/28 | 18/24 | 700 | **mới**; hiện 20–28 tuỳ màn |
| Mã chứng từ | `--wj-t-code` | 16/22 | 14/20 | 700 | đang 20/18 |
| Tên / mã dòng | `--wj-t-name` | 15/20 | **13/18** | 600 | mobile 15 → 13 khác #183 (Q7) |
| Đoạn văn | `--wj-t-body` | 14/21 | 13/20 | 400 | đang 15/14 |
| Nút | `--wj-t-button` | 14/20 | 13/18 | 600 | **mới** |
| Giá trị | `--wj-t-value` | 14/20 | 13/18 | 500 (đậm 600) | giữ |
| Nhãn | `--wj-t-label` | 12/18 | **13/18** | 500 | mobile lớn hơn PC — theo BA (Q6) |
| Dòng phụ | `--wj-t-caption` | 12/18 | 12/18 | 400 | giữ |
| Chip / badge | `--wj-t-chip` | 12/16 | 12/16 | 600 | **mới**; badge trạng thái hiện 13 |
| Icon | `--wj-icon-sm/md/lg` | 14 / 16 / 20 | 14 / 16 / 20 | — | TS6, không thuộc thang chữ |
| Chấm đếm số | `--wj-t-count` | 11 | 11 | 700 | TS6, ngoại lệ sàn 12 có tên |

Icon và chấm đếm không nằm trong trang BA chốt: số ở bảng là đề xuất dev, chốt ở TS6 bằng cách đo cỡ đang dùng nhiều nhất.

## 3. Luật chọn vai trò (dùng khi chuyển từng rule)

| Phần tử là… | Vai trò |
|---|---|
| H1 PageHeader / tiêu đề nhóm / tiêu đề thẻ | page / section / card |
| Số lớn trên thẻ KPI, tổng tiền nổi bật | kpi |
| Mã chứng từ ở đầu màn chi tiết | code |
| Tên/mã ở dòng danh sách, thẻ, dòng Home, tên sản phẩm | name |
| Đoạn văn, ghi chú, nội dung bài | body |
| Chữ trong nút | button |
| Ô bảng PC, giá trị dưới nhãn, nhãn ô nhập (đậm 600), giá tiền | value (+ strong) |
| Nhãn trên giá trị, tiêu đề cột bảng, nhãn KPI | label |
| Ngày, meta, số đếm cạnh tiêu đề, gợi ý dưới ô nhập | caption |
| Badge trạng thái, chip lọc, pill | chip |
| Icon font (`i`, `.fa`, `::before`) | icon (TS6) |
| Chấm số trên icon (giỏ, chuông, nav) | count (TS6) |

- Cỡ **và** đậm đi theo vai trò (đậm 700 lẻ ở dòng tên → 600). Muốn giữ khác phải có lý do ghi ở comment một dòng.
- Thẻ cao cố định (Figma) mà chữ mới không vừa ⇒ đổi `height` → `min-height` như KT2 làm ở Công nợ, không giữ số lẻ.
- Rule `!important` của component header: giữ đặc hiệu, chỉ đổi giá trị sang token.

## 4. Bảng phiên

| Phiên | Việc | Phạm vi | Trạng thái |
|---|---|---|---|
| TS0 | (PR #20 đã merge) · thêm token mới (`page`, `section`, `card`, `kpi`, `button`, `chip`) **theo §2 (bản 2 BA)**, header cũ thành alias · class `.wj-t-*` cho vai trò mới · `wj_type_audit.py css --save docs/typescale/css-baseline.json` · test **chặn tăng**: mỗi file không được nhiều chỗ gõ cứng hơn baseline | `_variables.css`, `_components.css`, test layout | ✅ 16/10 nhánh `feature/ts0-type-tokens` (chữ gõ cứng 426 → 418) |
| TS1 | Component dùng chung: `_components.css` + `_pc_components.css` (108 chữ) — ăn nhiều màn nhất | layout | ☐ |
| TS2 | Khung + tài khoản + Home: `_auth`, `_pc_account`, `_sidebar`, `portal_dashboard`, `store_picker` + 4 `style=` inline (89 chữ) | layout, portal_base | ☐ |
| TS3 | Thi: `portal_exam.css` (87 chữ) — màn PC đăng ký có lịch, chú ý ô lịch | portal_exam | ☐ |
| TS4 | Đặt hàng + Báo cáo: `portal_order.css`, `portal_report.css` + 6 `fontSize` chart JS (71 chữ) | portal_sale, portal_report | ☐ |
| TS5 | Các module còn lại (71 chữ) + 36 class Bootstrap cỡ chữ trong QWeb | debt, notification, delivery, return, history, knowledge, support | ☐ |
| TS6 | Thêm `--wj-icon-*`, `--wj-t-count` · icon (88) và chấm đếm (38) chuyển sang · test chặn tăng → **cấm hẳn**: 0 `font-size` số cứng ngoài `_variables.css` | layout + mọi module | ☐ |
| TS7 | Đo UAT đủ 31 màn × 8 khổ đối chiếu §2 · ledger + sheet · bàn giao (số đã áp từ TS0) | — | ☐ |

Mỗi phiên TS1–TS6: chạy `css --baseline` cho thấy số giảm, `screens` trước/sau trên DB copy, 0 chữ < 12px (ngoài chấm đếm), 0 tràn, 0 lỗi JS, 0 khung cắt chữ.
Một phiên một PR, một lần deploy.

## 5. Bộ đo

```
# đếm số gõ cứng; --baseline báo file nào tăng (exit 1)
python3 scripts/qa/wj_type_audit.py css --baseline docs/typescale/css-baseline.json
# đo mọi màn (Python env có Playwright); UAT thì mật khẩu admin theo docs/CREDENTIALS.md
python -I scripts/qa/wj_type_audit.py screens http://localhost:8071 admin /tmp/after.json --widths 320,360,390,430,992,1024,1440,1920
python3 scripts/qa/wj_type_audit.py diff /tmp/before.json /tmp/after.json
```

Mốc 16/10 sau KT2:
- DB copy `wujia_kt`: 30 màn × 8 khổ = 240/240 sạch (chi tiết Kiến thức không đo được trên local).
- UAT (`7636d929`, 10/10 version): 30 màn × 360/390/1440 = 90/90 sạch (chi tiết info-request: HCM-01 chưa có phiếu).
- `clip` ở `/portal/order`, `/portal/purchase-history` mobile là vùng chạm 44px của nút phân trang, có từ trước, không phải chữ bị cắt.

## 6. Câu hỏi treo (hỏi trước khi đụng)

| # | Câu hỏi | Ảnh hưởng |
|---|---|---|
| ~~Q1~~ | ✅ Chủ dự án 16/10: giữ **14px mọi khổ** — đo thực tế Vuexy `components.css` đã ép 14 ở mọi khổ, rule 14/15/16 của mình chết từ trước; TS0 ghi một dòng 14px + test ghim | TS0 |
| Q2 | Đậm theo vai trò (tên dòng 600 thay 700 ở nhiều màn) có cần BA duyệt riêng? | TS1–TS5 |
| Q3 | Trang đăng nhập / quên mật khẩu (`_auth.css`) có theo thang portal không? | TS2 |
| Q4 | BA mở một dòng Issue List (vd `UI-TYPESCALE-001`) để `qa_sync` ghi được không? Nếu không, chỉ ghi `f-progress.md` | TS7 |
| ~~Q5~~ | ✅ BA 16/10: số KPI một cỡ cho mọi màn — 22 PC / 18 mobile (Home 22→18, Công nợ mobile 25→18, PC 28/26/24→22) | TS2/TS4/TS5 |
| ~~Q6~~ | ✅ Chủ dự án 16/10: theo BA — nhãn mobile 13 (lớn hơn PC 12, bằng giá trị) giữ nguyên | TS0 |
| Q7 | Không chặn code. Bản 2 khác số đã ghi ở #143 (tiêu đề nhóm mobile 18) và #183/#191 (tên dòng 15): ghi chú vào ledger ở TS7 để QA retest theo số mới, nhờ BA sửa `Kết quả mong muốn` hai dòng đó | TS7, ledger |

## 7. Kết quả BA (nguyên văn, 16/10/2026)

**Bản 2 (đang dùng):**

```
Thang chữ Wujia Portal — BA chốt 16/10/2026
Đã chỉnh 9 vai trò so với đề xuất.
Vai trò | token | PC | Mobile
Tiêu đề trang | --wj-t-page | 24 (đề xuất 26) | 20 (đề xuất 22)
Tiêu đề nhóm | --wj-t-section | 18 (đề xuất 20) | 16 (đề xuất 18)
Tiêu đề thẻ | --wj-t-card | 17 (đề xuất 18) | 15 (đề xuất 16)
Số KPI | --wj-t-kpi | 22 (đề xuất 24) | 18 (đề xuất 20)
Mã chứng từ | --wj-t-code | 16 (đề xuất 20) | 14 (đề xuất 18)
Tên / mã dòng | --wj-t-name | 15 | 13 (đề xuất 15)
Đoạn văn | --wj-t-body | 14 (đề xuất 15) | 13 (đề xuất 14)
Nút | --wj-t-button | 14 | 13 (đề xuất 14)
Giá trị | --wj-t-value | 14 | 13
Nhãn | --wj-t-label | 12 | 13 (đề xuất 12)
Dòng phụ | --wj-t-caption | 12 | 12
Chip / badge | --wj-t-chip | 12 | 12
```

**Bản 1 (bị bản 2 thay, giữ để đối chiếu):**

```
Thang chữ Wujia Portal — BA chốt 16/10/2026
Giữ nguyên đề xuất.
Vai trò | token | PC | Mobile
Tiêu đề trang | --wj-t-page | 26 | 22
Tiêu đề nhóm | --wj-t-section | 20 | 18
Tiêu đề thẻ | --wj-t-card | 18 | 16
Số KPI | --wj-t-kpi | 24 | 20
Mã chứng từ | --wj-t-code | 20 | 18
Tên / mã dòng | --wj-t-name | 15 | 15
Đoạn văn | --wj-t-body | 15 | 14
Nút | --wj-t-button | 14 | 14
Giá trị | --wj-t-value | 14 | 13
Nhãn | --wj-t-label | 12 | 12
Dòng phụ | --wj-t-caption | 12 | 12
Chip / badge | --wj-t-chip | 12 | 12
```

BA chỉ chốt cỡ chữ. Chiều cao dòng và độ đậm theo bảng §2. Badge trạng thái 13 → 12 có trong cả hai bản.
