"""Đề xuất spec component (Dev Proposed) theo khuôn 17 cột tab "UI Component" của BA.

Một nguồn dữ liệu → hai đầu ra (không gõ hai lần):
  docs/ba-component-spec-proposal.xlsx   BA dán thẳng vào khối spec (dòng 30 trở đi)
  docs/ba-component-spec-proposal.tex    bản đọc; build: lualatex ×2

Chạy (cần openpyxl — env odoo19 trên Mac):
  python scripts/qa/ba_spec_proposal.py
Số liệu "Hiện trạng": đo Playwright computed-style 02/10/2026 (1440×900, 390×844,
user chủ cửa hàng, build cùng version UAT) + đếm class trong template portal.
Không ghi gì lên Google Sheet.
"""
import os
import re
import textwrap

DOCS = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'docs'))
UAT = 'https://dev.wujiatea.com.vn'
DATE = '02/10/2026'

COLUMNS = ['STT', 'Component ID', 'Nhóm', 'Component', 'Mục tiêu', 'Hiện trạng / Vấn đề',
           'Spec chuẩn hóa', 'Variants', 'Màn hình áp dụng', 'Acceptance Criteria',
           'Out of scope / Rủi ro', 'Priority', 'Status', 'Related Task / Issue',
           'Link tham chiếu', 'Odoo Fit', 'Ngày cập nhật']


def T(s):
    return textwrap.dedent(s).strip('\n')


VIEWPORTS = ('PC 1440×900, 1024×768, breakpoint 992/991; mobile 390×844, 360×800')

COMMON_ACCEPT = T(f"""
    [ ] Kiểm {VIEWPORTS}; chữ dài, focus/keyboard, vùng chạm mobile ≥44.
    [ ] Không đổi dữ liệu, điều kiện truy vấn, quyền, store context hoặc workflow.
    [ ] Dev bàn giao ảnh trước/sau cùng viewport/role/URL + số đo máy; FIX/IMPACT/RETEST/LIMIT + Build/Deploy hợp lệ. BA retest sau deploy.
""")

COMMON_FIT = T("""
    ODOO / RỦI RO
    - Custom: một template QWeb + CSS dùng chung ở tầng khung portal; không thêm model/field.
    - Trang chỉ truyền nội dung; không override dáng component trong CSS trang (cùng luật StatusBadge/ListCard).
""")

ROWS = [
    # ------------------------------------------------------------------ 1
    {
        'STT': 13, 'Component ID': 'CMP-ES-001', 'Nhóm': 'Feedback', 'Component': 'EmptyState',
        'Mục tiêu': 'Một EmptyState dùng chung cho danh sách/khối không có dữ liệu; phân biệt '
                    '"chưa có dữ liệu" với "lọc ra 0 kết quả" và là nơi đặt nút "Xóa lọc" '
                    'theo FB-03/FB-07 đã chốt.',
        'Hiện trạng / Vấn đề': T("""
            Đo build hiện hành 02/10/2026 (1440×900, 390×844, user chủ cửa hàng):
            - 7 họ class, 198 lần dùng trong template: `.wj-empty-state` 165 · `.wj-pc-empty` 14 · `.wujia-empty-state` 7 · `.wj-debt-pc-emptybox` 4 · `.wj-debt-empty` 4 · `.wj-exam-pc-panel-empty` 2 · `.wj-rep-mempty` 2.
            - PC có 4 dáng: Hỗ trợ/Yêu cầu cập nhật padding 48/24, icon 36 xám, không tiêu đề, cao 165; Đăng ký thi card riêng padding 40/24, icon 28, tiêu đề 20/700, cao 232; Công nợ padding 40/24, icon 30, tiêu đề 18/700, cao 216–237; Home (khối chuyến giao sắp tới) padding 12/0, icon 20, tiêu đề 16/700, cao 83.
            - Mobile có 4 dáng: mẫu "rich" (Giỏ hàng, Giao hàng, Hỗ trợ, Đăng ký thi) card radius 14, padding 24/18, icon 76, tiêu đề 18/700, mô tả 14/400, cao 261–280; Công nợ radius 14, padding 22/18, icon 28; Home radius 16, padding 22/15, cao 108; Yêu cầu cập nhật mobile vẫn dùng dáng PC (padding 48/24, không card, cao 186).
            - Chưa có luật chung phân biệt "chưa có dữ liệu" / "không khớp bộ lọc"; FB-07 đã chuyển nút "Xóa lọc" về EmptyState nhưng EmptyState chưa có chuẩn để nhận.
        """),
        'Spec chuẩn hóa': T("""
            ES-01 — Cơ sở / boundary
            Mobile lấy mẫu "rich" của Giao hàng làm chuẩn (đang chiếm đa số, chỉnh ít). PC dùng cùng cấu trúc và cùng chữ, chỉ khác padding/icon. Một template dùng chung ở tầng khung; trang chỉ truyền nội dung. EmptyState thay nội dung DataList (đúng CMP-DL-001): không render header bảng rỗng.

            ES-02 — Cấu trúc
            Thứ tự: icon (tùy chọn) → tiêu đề (bắt buộc) → mô tả (tùy chọn, tối đa 2 dòng) → hành động (tùy chọn: tối đa 1 primary + 1 secondary). Căn giữa. Tiêu đề là đoạn văn đậm, không phải heading (không làm lệch cấp heading của trang).

            ES-03 — Geometry
            list (trong card DataList): không nền/viền riêng, dùng card cha — không lồng card trong card. PC padding 40/24, min-height 200; mobile padding 24/18.
            Mobile khi đứng riêng (không có card cha): card trắng radius 14, viền 1px --wujia-border-soft (giữ mẫu rich).
            Icon: mobile 76 (giữ), PC 64; màu --wujia-primary trên nền --wujia-primary-soft.
            Chữ: tiêu đề 18/700 --wujia-text-primary; mô tả 14/400 --wujia-text-muted. Khoảng cách icon→tiêu đề 12, tiêu đề→mô tả 4, mô tả→hành động 16.
            row (khối nhỏ trong Home/card phụ): icon 20 bên trái, tiêu đề 15/700, mô tả 13/400, padding 12/0, căn trái.

            ES-04 — Trạng thái
            empty (chưa có dữ liệu): tiêu đề "Chưa có <đối tượng>"; hành động tạo mới chỉ khi màn đang có nút tạo và user có quyền.
            filtered (lọc ra 0): tiêu đề "Không tìm thấy <đối tượng> phù hợp"; mô tả nhắc đổi điều kiện; hành động secondary "Xóa lọc" → URL mặc định của màn, giữ store/role context (đúng FB-07). Không hiện "Xóa lọc" ở trạng thái empty.
            error (tải lỗi / không có quyền xem): icon tone danger, không hành động tạo mới.
            Controller truyền trạng thái (DataList đã có tham số state); không suy trạng thái ở CSS/JS.

            ES-05 — Integration
            DataList rỗng gọi EmptyState qua slot rỗng hiện có. Danh sách lọc không reload (AJAX) trả đúng cùng markup với lần render đầu.

            ES-06 — Token
            Chỉ dùng token sẵn có (--wujia-primary, --wujia-primary-soft, --wujia-text-primary, --wujia-text-muted, --wujia-danger-bg); không hex/px riêng trong CSS trang.
        """),
        'Variants': T("""
            Bố cục: list (mặc định, trong DataList) · row (khối nhỏ Home) · page (trang không có danh sách, vd Giỏ trống — bắt buộc hành động primary).
            Trạng thái: empty · filtered · error.
            Props đề xuất: es_variant, es_state, es_icon, es_title, es_sub, es_action_url/_label, es_reset_url.
        """),
        'Màn hình áp dụng': T("""
            ES-07 — Mapping
            1. Danh sách: /portal/purchase-history, /portal/delivery, /portal/return, /portal/notification, /portal/knowledge, /portal/support, /portal/info-request, /portal/exam, /portal/debt, /portal/debt/payment-history, /portal/reports/orders — list + empty/filtered.
            2. /portal (Home): các khối rỗng — row.
            3. /portal/order/cart: Giỏ trống — page, hành động "Đặt hàng".
            Khảo sát thuộc hạng mục khác, ngoài phạm vi.
        """),
        'Acceptance Criteria': T("""
            ES-08 — Acceptance / checklist
            [ ] 7 họ class rỗng → 1; script kiểm kê trong repo báo 0 họ cũ ở các màn mapping.
            [ ] Danh sách rỗng PC không còn header bảng rỗng; mobile không còn card lồng card.
            [ ] Lọc ra 0 → filtered + "Xóa lọc" về mặc định, giữ store; chưa có dữ liệu → empty, không có "Xóa lọc".
            [ ] Hình học đúng ES-03 trên mọi khổ; tiêu đề không cắt, mô tả tối đa 2 dòng ở 360.
            [ ] Icon trang trí aria-hidden; hành động có nhãn chữ.
            [ ] AJAX và render đầu cho cùng markup.
        """) + '\n' + COMMON_ACCEPT,
        'Out of scope / Rủi ro': T("""
            OUT OF SCOPE
            - Không thêm skeleton/loading, toast; không đổi nội dung nghiệp vụ hay điều kiện truy vấn.
            - Không sửa FilterBar (CMP-FB-001); chỉ nhận trạng thái lọc từ đó.

            RỦI RO
            - Chiều cao trang rỗng đổi ở PC (165–237 → ~200): ảnh BA cũ sẽ lệch.

            CẦN BA CHỐT
            - Q-ES-1: Icon PC 64 (đề xuất) hay giữ 76 như mobile?
            - Q-ES-2: Bộ nhãn tiêu đề/mô tả theo từng màn — Dev lập bảng nhãn hiện hành, BA duyệt; nếu BA không đổi, giữ nhãn hiện hành.
            - Q-ES-3: Khối rỗng ở Home dùng variant row chung, hay giữ dáng riêng của Home?
        """) + '\n\n' + COMMON_FIT,
        'Priority': 'High', 'Related Task / Issue': 'UI-EMPTY-001',
        'Link tham chiếu': f'{UAT}/portal/delivery ; {UAT}/portal/support ; {UAT}/portal/debt\n'
                           'Liên quan: CMP-DL-001 (EmptyState thay DataList), CMP-FB-001 FB-03/FB-07 ("Xóa lọc" nằm tại EmptyState).',
    },
    # ------------------------------------------------------------------ 2
    {
        'STT': 14, 'Component ID': 'CMP-DS-001', 'Nhóm': 'Detail',
        'Component': 'DetailSummary + KeyValue',
        'Mục tiêu': 'Chuẩn khối đầu màn chi tiết (mã chứng từ + StatusBadge + thông tin chính) '
                    'và một atom nhãn–giá trị (KeyValue) dùng lại ở mọi khối thông tin record.',
        'Hiện trạng / Vấn đề': T("""
            Đo build hiện hành 02/10/2026:
            - 8 họ nhãn–giá trị, 170 lần dùng: `wujia-mhist-kv` 57 (Lịch sử, Đổi trả mobile) · `wujia-maccount-kv` 39 (Tài khoản mobile) · `wj-pc-kv` 24 (Lịch sử, Giao hàng, Thông báo PC) · `wj-pc-acct-field` 15 (Tài khoản PC) · `wj-exam-pc-kv` 12 · `wujia-mexam-kv` 12 · `wujia-mres-info-row` 6 (Kết quả gửi đơn) · `wj-exam-pc-sumkv` 5.
            - PC `wj-pc-kv`: nhãn 13/700 muted, giá trị 15/700, xếp chồng, cao 46, lưới 2 cột. Tài khoản PC: ô nền tonal radius 12, padding 14/16, nhãn 12/700, giá trị 16/700, cao 80–104. Đăng ký thi: nhãn 12/700, giá trị 14–15/700.
            - Mobile `wujia-mhist-kv`: một hàng nhãn trái 12.5/400 – giá trị phải 12.5/700, cao 31. `wujia-maccount-kv`: nhãn 13/400 – giá trị 14/600, cao 44, có kẻ dưới.
            - Cùng loại thông tin có 4 cỡ nhãn (12/12.5/13) và 4 cỡ giá trị (12.5/14/15/16); vị trí mã chứng từ + trạng thái khác nhau giữa các màn chi tiết; chưa có luật chung cho giá trị trống.
        """),
        'Spec chuẩn hóa': T("""
            DS-01 — Cơ sở / boundary
            DetailSummary = SurfaceCard variant summary (CMP-SC-001), đặt ngay dưới PageHeader. Mã chứng từ ở đây, không lên PageHeader (đúng CMP-PG-001). KeyValue là atom dùng chung: trong DetailSummary và các khối thông tin record khác (Tài khoản, Thông tin cửa hàng, Kết quả gửi đơn).

            DS-02 — Hàng đầu
            Mã chứng từ 18/700 (PC) · 16/700 (mobile), --wujia-text-primary, chọn/copy được. StatusBadge (CMP-SB-001) bên phải mã; mobile cùng hàng nếu đủ chỗ, thiếu chỗ xuống dòng dưới mã. Meta phụ (ngày tạo, cửa hàng) 13/400 muted dưới mã.

            DS-03 — KeyValue PC (stacked)
            Giữ dáng `wj-pc-kv` đang dùng (chỉnh ít): nhãn 13/700 --wj-pc-muted, giá trị 15/700 --wujia-text-primary, gap 4. Lưới: 4 cột ≥1200, 2 cột 992–1199; gap hàng 16, cột 24. Giá trị dài (địa chỉ, ghi chú) chiếm cả hàng (full); không cắt ellipsis mã/địa chỉ.

            DS-04 — KeyValue mobile (inline)
            Lấy dáng `wujia-maccount-kv`: nhãn trái 13/400 muted (cột 40%, tối thiểu 96px), giá trị phải 14/600 text-primary căn phải; min-height 40, padding 8/0, kẻ dưới 1px --wujia-border-soft trừ hàng cuối. Bỏ cỡ 12/12.5. Giá trị nhiều dòng tự chuyển stacked (nhãn trên, giá trị dưới, căn trái).

            DS-05 — Giá trị trống / số
            Trống hiển thị "—" màu muted; không để ô rỗng, không in giá trị kỹ thuật. Tiền theo định dạng portal hiện hành; "0 đ" chỉ khi giá trị thực bằng 0.

            DS-06 — Tonal field
            Màn hồ sơ/tài khoản cần chia ô: ô nền --wujia-surface-tonal, radius 12, padding 14/16; chữ theo DS-03 (bỏ nhãn 12).
        """),
        'Variants': T("""
            DetailSummary: record (mã + StatusBadge + meta) · info (không mã, vd Tài khoản/Thông tin cửa hàng).
            KeyValue: stacked (PC) · inline (mobile) · tonal-field · modifier full (chiếm cả hàng), strong (nhấn giá trị tổng).
            Props đề xuất: ds_code, ds_state_label, ds_state_variant, ds_meta; kv_label, kv_value, kv_full, kv_strong.
        """),
        'Màn hình áp dụng': T("""
            DS-07 — Mapping
            1. Chi tiết: /portal/purchase-history/<id>, /portal/delivery/<id>, /portal/return/<id>, /portal/info-request/<id>, /portal/support/<id>, /portal/notification/<id>, /portal/exam/<id> — record.
            2. /portal/profile, /portal/franchise-information — info + tonal-field (PC).
            3. Kết quả gửi đơn (sau Đặt hàng) — info.
            Khảo sát thuộc hạng mục khác, ngoài phạm vi.
        """),
        'Acceptance Criteria': T("""
            DS-08 — Acceptance / checklist
            [ ] 8 họ nhãn–giá trị → 1 atom KeyValue; script kiểm kê báo 0 họ cũ ở màn mapping.
            [ ] Mọi màn chi tiết mapping có mã chứng từ + StatusBadge tại DetailSummary; không còn mã ở PageHeader.
            [ ] Không còn nhãn <13px ở mọi khổ.
            [ ] 1440: 4 cột; 1024 và 992: 2 cột; ≤991 bố cục mobile; 390/360 nhãn–giá trị một hàng, giá trị dài tự stacked, không tràn ngang.
            [ ] Giá trị trống hiển thị "—".
        """) + '\n' + COMMON_ACCEPT,
        'Out of scope / Rủi ro': T("""
            OUT OF SCOPE
            - Hàng thông tin trong ListCard (CMP-LC-001), bảng dòng sản phẩm, timeline, tệp đính kèm, form.
            - Không đổi nhãn trường hoặc thứ tự trường đã BA duyệt ở từng màn.

            RỦI RO
            - Lịch sử/Đổi trả mobile tăng cỡ chữ 12.5 → 13/14: trang chi tiết dài thêm khoảng 10–15%.

            CẦN BA CHỐT
            - Q-DS-1: Nhãn PC giữ 700 (hiện hành) hay giảm 600 để tách rõ với giá trị?
            - Q-DS-2: StatusBadge mobile cùng hàng mã (đề xuất) hay luôn dưới mã?
            - Q-DS-3: Tài khoản PC giữ ô tonal hay về lưới KeyValue thường như các màn chi tiết?
        """) + '\n\n' + COMMON_FIT,
        'Priority': 'Medium', 'Related Task / Issue': 'UI-DETAIL-001',
        'Link tham chiếu': f'{UAT}/portal/purchase-history (mở một đơn) ; {UAT}/portal/return (mở một yêu cầu) ; {UAT}/portal/profile\n'
                           'Liên quan: CMP-PG-001 (mã chứng từ không nằm ở PageHeader), CMP-SB-001.',
    },
    # ------------------------------------------------------------------ 3
    {
        'STT': 15, 'Component ID': 'CMP-IB-001', 'Nhóm': 'Feedback', 'Component': 'InfoBanner',
        'Mục tiêu': 'Một khối thông báo ngữ cảnh trong trang (khung giờ đặt hàng, quy định, '
                    'hướng dẫn quy trình), cùng dáng PC/mobile, màu theo token StatusBadge thay vì Bootstrap.',
        'Hiện trạng / Vấn đề': T("""
            Đo build hiện hành 02/10/2026:
            - Bootstrap `alert` 50 lần trong template portal (Đặt hàng 22, Đổi trả 10, Home 8, Yêu cầu cập nhật 6, khung 4) + 10 họ riêng 53 lần: `wujia-mhome-window` 17 · `wj-exam-pc-banner` 8 · `wujia-morder-warnbar` 6 · `wujia-mticket-hint` 5 · `wj-pc-acct-banner` 4 · `wujia-maccount-alert` 4 · `wj-exam-pc-alert` 4 · `wj-debt-banner` 2 · `wj-debt-pc-banner` 2 · `wujia-mreturn-banner` 1.
            - Cùng một thông điệp "Mỗi yêu cầu chỉ áp dụng cho 1 sản phẩm…" (Tạo đổi trả): PC là `alert-info` Bootstrap (radius 5.25, padding 14, nền cyan, cao 53); mobile là banner riêng (radius 10, padding 10/12, nền #DDF6FF, chữ 13).
            - Đặt hàng: PC `alert-warning` Bootstrap (nền cam 20%, radius 5.25, cao 53); mobile thanh khung giờ radius 12, padding 11/12, nền xanh lá, chữ 13/700, cao 61.
            - Công nợ: PC radius 12, padding 14/20, tiêu đề 14/700; mobile radius 16, padding 8/14, tiêu đề 15/700, mô tả 11.5.
            - Đăng ký thi PC: radius 10, padding 12, có viền, nhãn 12/700. Gợi ý form mobile 11px không nền.
            - 3 nguồn màu (Bootstrap, token Wujia, hex riêng), radius 5–16, chữ 11–15.
        """),
        'Spec chuẩn hóa': T("""
            IB-01 — Cơ sở / boundary
            Thông tin ngữ cảnh gắn với trang hoặc khối: khung giờ, hạn chót, quy định, hướng dẫn quy trình, cảnh báo trạng thái chứng từ. Không dùng cho: toast sau thao tác, lỗi validation từng trường (thuộc FormField), lỗi khoảng ngày của bộ lọc (FB-05), EmptyState.

            IB-02 — Tone / màu
            Dùng chung bộ token StatusBadge, bỏ màu Bootstrap: info (nền #EAF7FD / chữ #1378A3) · success (#EAF8EF / #11813B) · warning (#FFF7E6 / #AC5E05) · danger (#FEECEC / #D52222).

            IB-03 — Cấu trúc
            Icon theo tone (bắt buộc, 18) → tiêu đề (tùy chọn, 14/700) + nội dung 14/400 (mobile 13/400) → hành động (tùy chọn: link hoặc Button secondary nhỏ; PC bên phải, mobile xuống dòng).

            IB-04 — Geometry
            Radius 12 (--wj-pc-component-radius); padding PC 12/16, mobile 10/12; không viền; mobile min-height 44. Rộng hết cột nội dung (PageContainer/card), không tự cộng gutter. Cách khối kế tiếp 16 (PC), 12 (mobile). Chữ không nhỏ hơn 13.

            IB-05 — Hành vi
            Mặc định không đóng được. Nội dung do server render; đổi trạng thái thì đổi tone (vd khung giờ mở = success, đã đóng/chưa cấu hình = warning). Mỗi vùng tối đa 1 banner cùng tone; nhiều thông điệp gộp thành danh sách trong một banner.

            IB-06 — Accessibility
            info/success: role="status"; danger cần chú ý ngay: role="alert". Icon aria-hidden. Không truyền nghĩa chỉ bằng màu (luôn có icon + chữ).

            IB-07 — Khung giờ đặt hàng
            PC và mobile cùng component, cùng tone, cùng nội dung lấy từ một nguồn hiện có (Home, Đặt hàng, Giỏ). Không đổi điều kiện/luật khung giờ (issue khung giờ xử lý riêng).
        """),
        'Variants': T("""
            Tone: info · success · warning · danger.
            Mật độ: regular (có tiêu đề) · compact (một dòng, không tiêu đề).
            Modifier: action (có link/nút).
            Props đề xuất: ib_tone, ib_title, ib_text, ib_icon, ib_action_url/_label, ib_compact.
        """),
        'Màn hình áp dụng': T("""
            IB-08 — Mapping
            1. /portal (Home), /portal/order, /portal/order/cart: banner khung giờ đặt hàng.
            2. /portal/return/new, /portal/info-request/new, /portal/support/new: quy định/hướng dẫn đầu form.
            3. /portal/debt, /portal/debt/payment-history: banner thông tin công nợ.
            4. /portal/exam/register: banner thông tin kỳ thi.
            5. /portal/profile, /portal/franchise-information: banner tài khoản.
            Gợi ý dưới trường form (hint 11px) chuyển sang help của FormField (CMP-FF-001), không thuộc InfoBanner. Khảo sát ngoài phạm vi.
        """),
        'Acceptance Criteria': T("""
            IB-09 — Acceptance / checklist
            [ ] 0 Bootstrap `alert` trong template portal ở màn mapping; 10 họ riêng → 1.
            [ ] Cùng thông điệp ở PC và mobile dùng cùng tone/component.
            [ ] Radius 12, padding đúng IB-04, chữ ≥13 trên mọi khổ.
            [ ] Màu chỉ từ token IB-02; đạt tương phản ≥4.5:1.
            [ ] Banner khung giờ đổi tone đúng trạng thái mở/đóng; nội dung không đổi so với hiện hành.
        """) + '\n' + COMMON_ACCEPT,
        'Out of scope / Rủi ro': T("""
            OUT OF SCOPE
            - Toast/notification popup, lỗi validation từng trường, lỗi bộ lọc ngày, banner trang đăng nhập.
            - Không đổi luật khung giờ, nội dung câu chữ do BA đã duyệt.

            RỦI RO
            - Đặt hàng có 22 chỗ `alert`: cần đối chiếu từng chỗ là banner ngữ cảnh hay thông báo lỗi sau thao tác, để không gộp nhầm.

            CẦN BA CHỐT
            - Q-IB-1: Khung giờ "chưa cấu hình" và "đã đóng" cùng tone warning (đề xuất) hay tách danger?
            - Q-IB-2: Có cần variant đóng được (dismissible) cho banner hướng dẫn không? Đề xuất: không.
        """) + '\n\n' + COMMON_FIT,
        'Priority': 'Medium', 'Related Task / Issue': 'UI-BANNER-001',
        'Link tham chiếu': f'{UAT}/portal/order ; {UAT}/portal/return/new ; {UAT}/portal/debt/payment-history\n'
                           'Liên quan: CMP-SB-001 (bộ màu tone), CMP-FB-001 FB-05 (lỗi ngày không thuộc InfoBanner).',
    },
    # ------------------------------------------------------------------ 4
    {
        'STT': 16, 'Component ID': 'CMP-KPI-001', 'Nhóm': 'Data Display', 'Component': 'StatCard',
        'Mục tiêu': 'Một StatCard cho chỉ số tổng quan (Home, Báo cáo, Công nợ): cùng thang chữ, '
                    'cùng luật "—" ≠ "0 đ", cả card bấm được khi có đích.',
        'Hiện trạng / Vấn đề': T("""
            Đo build hiện hành 02/10/2026:
            - 7 họ: `wj-pc-metric-card` (68 class kể cả phần tử con; Báo cáo PC) · `wujia-mhome-kpi` 15 (Home mobile + Công nợ mobile) · `wj-rep-mkpi` 9 + `wj-rep-mcard` 4 (Báo cáo mobile) · `wujia-kpi-card` 8 (Home PC) · `wj-rep-pccard` 6 · `wj-debt-pc-summary` 1 / `wj-debt-summary` 2 (Công nợ).
            - Home PC: card cao 108, padding 16, radius 16, viền, icon 56. Báo cáo PC: cao 96, radius 16, viền, giá trị 24/700 (CSS gốc của họ là 30/700). Công nợ PC: khối tổng hợp cao 138, padding 24/28, radius 18.
            - Home mobile: dải nền màu, nhãn 9/700, giá trị 22/700 chữ trắng, cao 52. Báo cáo mobile: card trắng radius 16, không viền, nhãn 13/600, giá trị 20/700, cao 101–110.
            - Giá trị có 4 cỡ (20/22/24/30), nhãn 9–15 (9px dưới ngưỡng đọc), radius 16/18, viền có/không.
        """),
        'Spec chuẩn hóa': T("""
            KPI-01 — Cơ sở / boundary
            StatCard = SurfaceCard variant summary (CMP-SC-001) + icon (tùy chọn) + nhãn + giá trị + mô tả/xu hướng (tùy chọn). Header theo CMP-CH-001 compact khi có. Không phải ListCard/ProductCard.

            KPI-02 — PC metric
            min-height 96 (--wj-pc-metric-h), padding 16/20, radius 16, viền 1px --wujia-border-soft. Icon 52 (--wj-pc-metric-icon), radius 12, nền tone nhạt. Nhãn 13/600 muted; giá trị 24/700 --wujia-text-primary, số tabular; mô tả 13/400 muted. Lưới 4 card/hàng ≥1200, 2/hàng 992–1199, gap 16.

            KPI-03 — Mobile compact
            Card trắng radius 14, padding 12; nhãn 12/600 muted; giá trị 20/700. Lưới 2 cột, gap 8; số card lẻ thì card cuối chiếm cả hàng.

            KPI-04 — Inverse (Home mobile)
            Giữ dải nền màu của Home (chỉnh ít): nhãn nâng 9 → 12/700 trắng 85%, giá trị 22/700 trắng; ngăn cách bằng --wujia-kpi-separator.

            KPI-05 — Giá trị
            Tiền theo định dạng portal hiện hành. "—" khi chưa có chứng từ/không đủ dữ liệu; "0 đ" chỉ khi tổng thực bằng 0 (giữ luật đang áp ở Công nợ/Báo cáo). Giá trị không xuống dòng; quá dài thì giảm một bậc cỡ chữ (24 → 20), không ellipsis.

            KPI-06 — Link
            Khi có đích, cả card là link: hover --wujia-hover-shadow, focus ring token, aria-label "<nhãn>: <giá trị>"; mobile vùng chạm ≥44.
        """),
        'Variants': T("""
            metric (PC) · compact (mobile) · inverse (dải Home mobile) · plain (không viền, nằm trong khối tổng hợp như Công nợ) · modifier link.
            Props đề xuất: kpi_variant, kpi_label, kpi_value, kpi_sub, kpi_icon, kpi_tone, kpi_href.
        """),
        'Màn hình áp dụng': T("""
            KPI-07 — Mapping
            1. /portal (Home): PC metric + link; mobile inverse.
            2. /portal/reports/orders: PC metric; mobile compact.
            3. /portal/debt, /portal/debt/payment-history: khối tổng hợp = SurfaceCard summary chứa StatCard plain; mobile compact.
            Không đổi công thức/khoảng thời gian của chỉ số.
        """),
        'Acceptance Criteria': T("""
            KPI-08 — Acceptance / checklist
            [ ] 7 họ → 1 component; script kiểm kê báo 0 họ cũ ở màn mapping.
            [ ] Giá trị 24 (PC) / 20 (mobile) / 22 (inverse); không còn nhãn <12.
            [ ] "—" và "0 đ" đúng KPI-05 trên dữ liệu có/không chứng từ.
            [ ] 1440: 4 card/hàng; 1024/992: 2/hàng; 390/360: 2 cột, giá trị không xuống dòng hay tràn.
            [ ] Card link bấm được toàn vùng, có focus ring.
        """) + '\n' + COMMON_ACCEPT,
        'Out of scope / Rủi ro': T("""
            OUT OF SCOPE
            - Biểu đồ, bảng báo cáo, export; công thức và nguồn số liệu.

            RỦI RO
            - Home PC cao 108 → 96: khối dưới dịch lên; Báo cáo PC giữ nguyên.

            CẦN BA CHỐT
            - Q-KPI-1: Giá trị PC 24 (đang hiển thị ở Báo cáo, đề xuất) hay 30 (CSS gốc)?
            - Q-KPI-2: Home mobile giữ dải nền màu (inverse, đề xuất) hay chuyển card trắng như Báo cáo?
            - Q-KPI-3: Số tiền lớn có rút gọn đơn vị (tr, tỷ) không? Đề xuất: không, giữ số đầy đủ.
        """) + '\n\n' + COMMON_FIT,
        'Priority': 'Medium', 'Related Task / Issue': 'UI-KPI-001',
        'Link tham chiếu': f'{UAT}/portal ; {UAT}/portal/reports/orders ; {UAT}/portal/debt\n'
                           'Liên quan: CMP-SC-001 (variant summary), CMP-CH-001 (Summary/StatCard compact).',
    },
    # ------------------------------------------------------------------ 5
    {
        'STT': 17, 'Component ID': 'CMP-TAG-001', 'Nhóm': 'Status',
        'Component': 'RoleBadge · CategoryBadge · AlertBadge · CountBadge',
        'Mục tiêu': 'Đặc tả 4 badge mà CMP-SB-001 đã yêu cầu tách khỏi StatusBadge, để dọn họ '
                    '`wujia-badge` cũ và Bootstrap `badge` mà không lẫn với màu/dáng trạng thái.',
        'Hiện trạng / Vấn đề': T("""
            Đo build hiện hành 02/10/2026:
            - `wujia-badge` 38 lần (Kiến thức 12, Thông báo 8, Home 7, Đổi trả 4, Yêu cầu cập nhật 4, Hỗ trợ 3): pill cao 27, padding 4/10, viền 1px, chữ 12/600 (mobile cao 23, chữ 11/600). Một phần là trạng thái nghiệp vụ (bù hàng Đổi trả, trạng thái Yêu cầu cập nhật) — phần này thuộc StatusBadge, sẽ dọn theo CMP-SB-001.
            - `wj-pc-badge` 16 lần (vai trò/khu vực, loại thông báo): pill cao 28, padding 0/14, radius 14, không viền, chữ 13/600 — trùng dáng StatusBadge (28/14).
            - Bootstrap `badge` 35 lần trong template portal: số đếm (chuông, menu) cao 18, padding 0/5, nền #EF4444, chữ 11.25/700; Kiến thức dùng badge xám radius 5.25.
            - Cùng chức năng "phân loại" có 3 dáng; số đếm chưa có luật >99/0.
        """),
        'Spec chuẩn hóa': T("""
            TAG-01 — Phân loại (theo CMP-SB-001)
            RoleBadge: vai trò/khu vực của user tại cửa hàng. CategoryBadge: phân loại nội dung (danh mục Kiến thức, loại thông báo, danh mục hỗ trợ). AlertBadge: mức ưu tiên/cảnh báo gắn record (vd "Khẩn"). CountBadge: số đếm trên icon/menu (chưa đọc, giỏ). Trạng thái nghiệp vụ không thuộc mục này → StatusBadge.

            TAG-02 — RoleBadge
            Giữ dáng `wj-pc-badge` hiện hành (BA đã khóa trong SB): cao 28, padding 0/14, radius 14, chữ 13/600, nền --wujia-primary-soft, chữ --wujia-primary-dark; mobile cao 24, chữ 12/600.

            TAG-03 — CategoryBadge
            Viền, nền trắng: cao 24, padding 0/10, radius 999, viền 1px --wujia-border, chữ 12/600 --wujia-text-secondary. Không dùng màu trạng thái.

            TAG-04 — AlertBadge
            Cao 22, padding 0/8, radius 6 (vuông bo — khác pill trạng thái), chữ 12/700; chỉ 2 tone: danger (#FEECEC/#D52222), warning (#FFF7E6/#AC5E05); icon 12 tùy chọn.

            TAG-05 — CountBadge
            min-width 18, cao 18, padding 0/5, radius 999, nền --wujia-danger, chữ 11/700 trắng, số tabular. 0 → ẩn; >99 → "99+". Đặt góc phải trên icon (lệch −4/−6). Số đếm nằm trong aria-label của nút cha (vd "Thông báo, 44 chưa đọc"); badge aria-hidden.
        """),
        'Variants': T("""
            RoleBadge: role · area. CategoryBadge: một dáng. AlertBadge: danger · warning. CountBadge: một dáng (trên icon / trong menu).
            Props đề xuất: tag_kind (role/area/category/alert/count), tag_label, tag_tone (alert), tag_count.
        """),
        'Màn hình áp dụng': T("""
            TAG-06 — Mapping
            1. Header (chuông, giỏ), sidebar, bottom nav: CountBadge.
            2. /portal/franchise-information, /portal/profile: RoleBadge role/area.
            3. /portal/notification (+ chi tiết): CategoryBadge loại thông báo.
            4. /portal/knowledge: CategoryBadge danh mục/thẻ bài.
            5. /portal/support (+ chi tiết): AlertBadge ưu tiên, CategoryBadge danh mục.
            6. /portal (Home): badge thông báo/ưu tiên theo loại tương ứng.
        """),
        'Acceptance Criteria': T("""
            TAG-07 — Acceptance / checklist
            [ ] 0 `wujia-badge` và Bootstrap `badge` trong template portal ở màn mapping; test guard StatusBadge mở ra toàn bộ module portal với danh sách loại trừ là 4 badge này.
            [ ] Không badge nào ngoài StatusBadge dùng bộ màu trạng thái (trừ AlertBadge 2 tone).
            [ ] CountBadge: 0 ẩn, 100 hiển thị "99+", không che icon ở 360.
            [ ] Tương phản chữ/nền ≥4.5:1.
        """) + '\n' + COMMON_ACCEPT,
        'Out of scope / Rủi ro': T("""
            OUT OF SCOPE
            - StatusBadge (CMP-SB-001), FilterChip (CMP-FC-001), CodeBadge.

            CẦN BA CHỐT
            - Q-TAG-1: Ưu tiên "Khẩn" là AlertBadge (đề xuất) hay StatusBadge danger?
            - Q-TAG-2: CountBadge hiện "99+" (đề xuất) hay số thật?
            - Q-TAG-3: RoleBadge giữ pill hiện hành (trùng dáng StatusBadge info) hay đổi sang viền để tách rõ?
        """) + '\n\n' + COMMON_FIT,
        'Priority': 'Medium', 'Related Task / Issue': 'UI-TAG-001',
        'Link tham chiếu': f'{UAT}/portal/knowledge ; {UAT}/portal/notification ; {UAT}/portal/franchise-information\n'
                           'Liên quan: CMP-SB-001 (Components tách riêng: RoleBadge, CountBadge, FilterChip, CategoryBadge, AlertBadge).',
    },
    # ------------------------------------------------------------------ 6
    {
        'STT': 18, 'Component ID': 'CMP-MD-001', 'Nhóm': 'Feedback', 'Component': 'Modal / Dialog',
        'Mục tiêu': '(Đề xuất thêm vào danh sách component.) Một Modal dùng chung cho xác nhận, '
                    'thông tin, form ngắn, QR — cùng kích thước và cùng hành vi bàn phím/đóng.',
        'Hiện trạng / Vấn đề': T("""
            Đo build hiện hành 02/10/2026 + đọc source:
            - 4 nơi dùng hộp thoại, mỗi nơi tự viết JS đóng/mở riêng (Đặt hàng, Công nợ, 2 file Đăng ký thi); họ `wj-pc-modal` 26 class.
            - Khung gốc: rộng 420, radius 20, padding 26/32 (mobile radius 16, padding 20); Công nợ QR 560, padding 28/32; Đăng ký thi 820 và 880, padding 22/36.
            - Còn 3 hộp xác nhận mặc định của trình duyệt: hủy yêu cầu cập nhật, xóa sản phẩm khỏi giỏ, rời trang khi có thay đổi chưa lưu — không theo giao diện portal.
            - Lớp chọn cửa hàng là màn phủ riêng; popup chuông là dropdown; sheet "Thêm" mobile thuộc bottom nav.
            - Chưa có hợp đồng chung cho Esc, bấm nền, focus, khóa cuộn trang.
        """),
        'Spec chuẩn hóa': T("""
            MD-01 — Cơ sở / boundary
            Hộp thoại chặn cho: xác nhận, thông tin, form ngắn, xem QR/ảnh. Không gồm: popup chuông (dropdown), sheet "Thêm" (CMP-BN-001), toast.

            MD-02 — Kích thước
            sm 420 (xác nhận/thông tin) · md 560 (form ngắn, QR) · lg 880 (nội dung dài). max-width calc(100vw − 32px); max-height 100vh − 64; thân cuộn bên trong, tiêu đề/hành động cố định.

            MD-03 — Geometry
            Radius 20 (PC) / 16 (mobile); padding 24/32 (PC), 20 (mobile). Header: tiêu đề 18/700 + IconButton đóng 36 (aria-label "Đóng"). Footer: hành động căn phải, primary cuối, gap 12; mobile nút chiếm đều chiều ngang. Nền phủ rgba(17,24,39,.18) (giữ hiện hành).

            MD-04 — Mobile ≤991
            Mặc định giữ hộp giữa màn như hiện hành (chỉnh ít) — xem câu hỏi Q-MD-1.

            MD-05 — Hành vi
            Mở: focus phần tử đầu (confirm danger: focus nút "Hủy"). Tab vòng trong modal. Esc và bấm nền = Hủy, trừ khi đang gửi dữ liệu (khóa đóng tới khi xong). Đóng: trả focus về nút đã mở. Khóa cuộn trang khi mở. role="dialog", aria-modal="true", aria-labelledby = tiêu đề.

            MD-06 — Confirm
            Tiêu đề là câu hỏi; nội dung nêu hậu quả; 2 nút: secondary "Hủy" + primary/danger với động từ cụ thể ("Gửi đơn", "Xóa", "Hủy yêu cầu"), không dùng "OK". Nút chính khóa + hiện đang xử lý khi gửi, chống bấm 2 lần. Thay 3 hộp xác nhận trình duyệt bằng confirm của portal.
        """),
        'Variants': T("""
            confirm · confirm-danger · info · form · media (QR/ảnh) × size sm/md/lg.
            Props đề xuất: md_id, md_size, md_variant, md_title, md_body, md_confirm_label, md_cancel_label.
        """),
        'Màn hình áp dụng': T("""
            MD-07 — Mapping
            1. /portal/order, /portal/order/cart: xác nhận gửi đơn (sm), xóa sản phẩm khỏi giỏ (confirm-danger).
            2. /portal/debt: QR thanh toán (media md).
            3. /portal/exam/register: các hộp thoại của luồng đăng ký (lg).
            4. /portal/info-request/<id>: hủy yêu cầu (confirm-danger).
            5. Rời trang khi form có thay đổi chưa lưu (confirm).
            Lớp chọn cửa hàng: xem Q-MD-3.
        """),
        'Acceptance Criteria': T("""
            MD-08 — Acceptance / checklist
            [ ] 0 hộp xác nhận mặc định của trình duyệt ở màn mapping.
            [ ] Mọi modal mapping dùng một khung; đúng 3 size; tiêu đề 18/700, có nút đóng.
            [ ] Bàn phím: Tab không thoát khỏi modal; Esc đóng; focus trả về nút mở; đang gửi thì không đóng được.
            [ ] Trang nền không cuộn khi modal mở; nội dung dài cuộn trong thân modal ở 360×800.
            [ ] Gửi đơn bấm 2 lần nhanh chỉ tạo 1 yêu cầu.
        """) + '\n' + COMMON_ACCEPT,
        'Out of scope / Rủi ro': T("""
            OUT OF SCOPE
            - Popup chuông, sheet "Thêm" mobile, toast; nội dung/luồng nghiệp vụ trong từng modal.

            RỦI RO
            - Hộp "rời trang khi chưa lưu" của trình duyệt (beforeunload) không thay được bằng modal khi đóng tab — chỉ thay được khi bấm link/nút trong portal.

            CẦN BA CHỐT
            - Q-MD-1: Mobile dùng hộp giữa màn (hiện hành, đề xuất) hay bottom sheet full chiều ngang?
            - Q-MD-2: Bấm nền có đóng modal form không (rủi ro mất dữ liệu đang nhập)? Đề xuất: confirm/info đóng, form không.
            - Q-MD-3: Lớp chọn cửa hàng có đưa về Modal (form, md) hay giữ màn phủ riêng?
        """) + '\n\n' + COMMON_FIT,
        'Priority': 'Medium', 'Related Task / Issue': 'UI-MODAL-001',
        'Link tham chiếu': f'{UAT}/portal/order/cart (bấm Gửi đơn — chỉ mở hộp, không xác nhận) ; {UAT}/portal/debt\n'
                           'Liên quan: CMP-BTN-001 (nút trong footer), CMP-BN-001 (sheet "Thêm" ngoài phạm vi).',
    },
    # ------------------------------------------------------------------ 7
    {
        'STT': 19, 'Component ID': 'CMP-FF-001', 'Nhóm': 'Form / Filter', 'Component': 'FormField',
        'Mục tiêu': '(Đề xuất thêm vào danh sách component.) Một FormField cho form tạo/sửa: '
                    'nhãn, control, gợi ý, lỗi, bắt buộc — cùng kích thước theo nền tảng.',
        'Hiện trạng / Vấn đề': T("""
            Đo build hiện hành 02/10/2026:
            - Họ riêng: `wj-pc-control` 18 · `wj-pc-field` 14 · `wj-exam-pc-control` 8 · `wj-exam-pc-field` 5 · `wj-auth-control` 6 (đăng nhập); Bootstrap `form-control` 31 + `form-select` 13 (Đổi trả, Yêu cầu cập nhật, Hỗ trợ).
            - PC Tạo hỗ trợ: control cao 42, padding 0/16, radius 10, chữ 14; nhãn 14/600. PC Đăng ký thi: control cao 38, chữ 13; nhãn 13/700.
            - Mobile Tạo đổi trả/Tạo hỗ trợ: control cao 48, radius 12 (đúng chuẩn mobile đã chốt) nhưng chữ trong ô 12.25px; textarea 96–102, chữ 14; gợi ý dưới trường 11px.
            - Chữ trong ô <16px trên mobile làm iPhone tự phóng to trang khi chạm vào ô.
            - Trạng thái lỗi, dấu bắt buộc và vị trí gợi ý chưa thống nhất giữa các form.
        """),
        'Spec chuẩn hóa': T("""
            FF-01 — Cơ sở / boundary
            Nhãn (trên control) → control → gợi ý (tùy chọn) → lỗi (thay gợi ý khi lỗi). Mỗi control có id + nhãn gắn với control (đã chốt ở chuẩn form mobile). Bắt buộc: dấu * màu --wujia-danger sau nhãn + aria-required. Không gồm control của bộ lọc (CMP-FB-001).

            FF-02 — PC
            Control cao 42 (--wj-pc-input-h), radius 10 (--wj-pc-input-radius), padding 0/14, chữ 14/400, viền 1px --wujia-border, nền trắng. Nhãn 14/600 --wujia-text-secondary, cách control 6. Gợi ý 13/400 muted; lỗi 13/500 --wujia-danger. Textarea min-height 96, chỉ kéo dọc. Khoảng cách giữa trường 16. Form ≥1200 được 2 cột cho trường ngắn; textarea/upload luôn cả hàng.

            FF-03 — Mobile ≤991
            Control cao 48, radius 12 (giữ chuẩn đã chốt), padding 0/14, chữ 16/400 (tránh tự phóng to trên iPhone). Nhãn 14/600; gợi ý/lỗi 13 (bỏ 11/11.5). Khoảng cách giữa trường 14. Checkbox/radio: nhãn bên phải, vùng chạm ≥44.

            FF-04 — Trạng thái
            default · focus (viền --wujia-primary + focus ring token) · error (viền danger, chữ lỗi, aria-invalid + aria-describedby) · disabled (nền --wujia-muted-bg, chữ muted) · readonly (giá trị dạng chữ, không viền).

            FF-05 — Lỗi khi gửi
            Gửi lỗi: giữ giá trị đã nhập; lỗi từng trường hiển thị tại trường và cuộn tới trường lỗi đầu; lỗi chung của form dùng InfoBanner danger đầu form (CMP-IB-001).
        """),
        'Variants': T("""
            text · number · date · select · textarea · choice (checkbox/radio) · upload (xem Q-FF-1).
            Props đề xuất: ff_id, ff_label, ff_required, ff_help, ff_error, ff_type; control truyền qua slot.
        """),
        'Màn hình áp dụng': T("""
            FF-06 — Mapping
            1. /portal/support/new, /portal/return/new, /portal/info-request/new: form tạo.
            2. /portal/exam/register: form đăng ký (PC 38 → 42).
            3. /portal/profile: các trường sửa được (nếu có).
            Trang đăng nhập và control bộ lọc ngoài phạm vi.
        """),
        'Acceptance Criteria': T("""
            FF-07 — Acceptance / checklist
            [ ] 0 Bootstrap `form-control`/`form-select` và họ control riêng ở màn mapping.
            [ ] PC control 42, mobile 48; chữ trong ô mobile 16 — chạm vào ô trên iPhone không phóng to trang.
            [ ] Mọi control có nhãn gắn id; trường bắt buộc có * và aria-required.
            [ ] Gửi thiếu trường bắt buộc: lỗi tại trường, focus trường lỗi đầu, giữ giá trị đã nhập.
            [ ] Không còn gợi ý/lỗi <13px.
        """) + '\n' + COMMON_ACCEPT,
        'Out of scope / Rủi ro': T("""
            OUT OF SCOPE
            - Control bộ lọc (CMP-FB-001 giữ 42/38/32), trang đăng nhập (cao 50), trình soạn thảo rich text.
            - Không đổi trường, thứ tự trường, điều kiện kiểm tra dữ liệu.

            RỦI RO
            - Đăng ký thi PC tăng control 38 → 42: form dài thêm, cần kiểm khổ 1024×768.

            CẦN BA CHỐT
            - Q-FF-1: Upload ảnh/video (Đổi trả 3–5 ảnh + video) là variant của FormField hay component riêng?
            - Q-FF-2: Chữ trong ô mobile 16 (đề xuất, vì iPhone) hay giữ cỡ hiện hành và chấp nhận phóng to?
        """) + '\n\n' + COMMON_FIT,
        'Priority': 'Medium', 'Related Task / Issue': 'UI-FORM-001',
        'Link tham chiếu': f'{UAT}/portal/support/new ; {UAT}/portal/return/new ; {UAT}/portal/exam/register (chỉ xem, không gửi)\n'
                           'Liên quan: chuẩn form mobile đã chốt (control ≥48, radius 12), CMP-FB-001, CMP-IB-001.',
    },
]

for _r in ROWS:
    _r.setdefault('Status', 'Dev Proposed')
    _r.setdefault('Odoo Fit', 'Custom')
    _r.setdefault('Ngày cập nhật', DATE)
    assert set(_r) == set(COLUMNS), (_r['Component ID'], set(COLUMNS) ^ set(_r))


def plain(s):
    """Bản cho Sheet: bỏ dấu ` đánh dấu mã."""
    return s.replace('`', '') if isinstance(s, str) else s


# ---------------------------------------------------------------- xlsx
def write_xlsx(path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill, Border, Side

    wb = Workbook()
    ws = wb.active
    ws.title = 'UI Component (đề xuất)'
    ws.append(COLUMNS)
    for r in ROWS:
        ws.append([plain(r[c]) for c in COLUMNS])
    thin = Side(style='thin', color='D0D5DD')
    widths = [6, 14, 13, 22, 34, 60, 90, 40, 50, 60, 55, 10, 14, 16, 45, 12, 13]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = w
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical='top')
            c.border = Border(top=thin, bottom=thin, left=thin, right=thin)
    for c in ws[1]:
        c.font = Font(bold=True, color='FFFFFF')
        c.fill = PatternFill('solid', fgColor='28A9DF')
    ws.freeze_panes = 'C2'
    wb.save(path)


# ---------------------------------------------------------------- tex
UNI = {'→': r'\(\to\)', '≥': r'\(\geq\)', '≤': r'\(\leq\)', '×': r'\(\times\)',
       '−': r'\(-\)', '≠': r'\(\neq\)', '⇒': r'\(\Rightarrow\)'}


def esc(s):
    s = s.replace('\\', r'\textbackslash{}')
    for a, b in (('&', r'\&'), ('%', r'\%'), ('$', r'\$'), ('#', r'\#'), ('_', r'\_'),
                 ('{', r'\{'), ('}', r'\}'), ('~', r'\textasciitilde{}'), ('^', r'\^{}')):
        s = s.replace(a, b)
    s = s.replace(r'\textbackslash\{\}', r'\textbackslash{}')
    s = re.sub(r'"([^"]*)"', '“\\1”', s).replace('"', '”')
    s = s.replace('<', r'\textless{}').replace('>', r'\textgreater{}')
    for a, b in UNI.items():
        s = s.replace(a, b)
    s = s.replace('--', r'-\kern0pt-')  # token CSS; LuaTeX bỏ qua {} khi ghép ligature
    # đường dẫn, token, tên CSS dài: cho phép ngắt sau / và -
    s = re.sub(r'(?<=[\w)])/(?=[\w<(\\])', r'/\\allowbreak{}', s)
    s = re.sub(r'(?<=\w)-(?=-?[a-z])', r'-\\allowbreak{}', s)
    return s


def inline(s):
    out = []
    for i, part in enumerate(s.split('`')):
        if i % 2:
            out.append(r'\codesp{%s}' % part if ' ' in part else r'\code{%s}' % part)
        else:
            out.append(esc(part))
    return ''.join(out)


HEAD = re.compile(r'^([A-Z]{2,4}-\d{2} — .+|OUT OF SCOPE|RỦI RO|ODOO / RỦI RO|CẦN BA CHỐT)$')


def block(text):
    """Dòng '- ' → itemize; '[ ] ' → checklist; tiêu đề mục con → đậm."""
    lines, out, mode = str(text).split('\n'), [], None

    def close():
        nonlocal mode
        if mode:
            out.append(r'\end{itemize}')
        mode = None

    for ln in lines:
        s = ln.strip()
        if not s:
            close(); out.append(''); continue
        m = re.match(r'^(-|\[ \]|\d+\.)\s+(.*)$', s)
        if m:
            kind = {'-': 'bul', '[ ]': 'chk'}.get(m.group(1), 'num')
            if mode != kind:
                close()
                opt = {'bul': '', 'chk': r'[label=$\square$]', 'num': r'[label={}]'}[kind]
                lbl = m.group(1) + ' ' if kind == 'num' else ''
                out.append(r'\begin{itemize}' + opt)
                mode = kind
            else:
                lbl = m.group(1) + ' ' if kind == 'num' else ''
            out.append(r'\item ' + esc(lbl) + inline(m.group(2)))
            continue
        close()
        if HEAD.match(s):
            out.append(r'\par\smallskip\textbf{%s}\par' % inline(s))
        else:
            out.append(inline(s) + r'\par')
    close()
    return '\n'.join(out)


def questions(r):
    txt = r['Out of scope / Rủi ro']
    if 'CẦN BA CHỐT' not in txt:
        return []
    tail = txt.split('CẦN BA CHỐT', 1)[1].split('ODOO / RỦI RO')[0]
    return [ln.strip()[2:] for ln in tail.split('\n') if ln.strip().startswith('- ')]


PREAMBLE = r"""% SINH TỰ ĐỘNG bởi scripts/qa/ba_spec_proposal.py — sửa dữ liệu ở đó rồi chạy lại.
% Build: lualatex ba-component-spec-proposal.tex (2 lần)
\documentclass[11pt,a4paper]{report}
\usepackage{fontspec}
\setmainfont{Lato}
\setsansfont{Lato}
\setmonofont{Noto Sans Mono}[Scale=0.82]
\usepackage[margin=2cm]{geometry}
\usepackage{parskip}
\setlength{\parindent}{0pt}
\usepackage{booktabs,longtable,array,tabularx,enumitem,amssymb}
\setlist{itemsep=1pt,topsep=3pt}
\usepackage{xcolor}
\definecolor{wjblue}{RGB}{40,169,223}
\renewcommand{\chaptername}{Chương}
\renewcommand{\contentsname}{Mục lục}
\usepackage{hyperref}
\hypersetup{colorlinks=true,linkcolor=blue!50!black,urlcolor=blue!60!black,
  pdftitle={WujiaTea Portal — Đề xuất spec component (Dev Proposed)},pdfauthor={WujiaTea Dev Team}}
\PassOptionsToPackage{obeyspaces,spaces}{url}
\usepackage{xurl}
\DeclareUrlCommand\code{\urlstyle{tt}}
\newcommand{\codesp}[1]{\texttt{\detokenize{#1}}}
\renewcommand{\arraystretch}{1.25}
\emergencystretch=3em
\title{\vspace{1cm}\textbf{WujiaTea Odoo 19 --- Portal cửa hàng}\\[0.3cm]\Large Đề xuất spec component chưa có chuẩn\\[0.2cm]\large 7 dòng theo khuôn tab \textit{UI Component} --- trạng thái \textit{Dev Proposed}, chờ BA duyệt}
\author{Dev Team}
\date{Phiên bản 1.0 · %(date)s}
\begin{document}
\maketitle
\tableofcontents
"""


def write_tex(path):
    o = [PREAMBLE.replace('%(date)s', DATE)]
    o.append(r'\chapter{Mục đích và cách dùng}')
    o.append(block(T("""
        Tab UI Component đã có spec BA cho 12 component. Rà toàn bộ source portal ngày 02/10/2026 còn 4 component đã có tên trong danh mục nhưng chưa có spec (EmptyState, DetailSummary, InfoBanner, StatCard), nhóm badge mà CMP-SB-001 yêu cầu tách riêng, và 2 nhóm chưa có trong danh mục (Modal, FormField). Mỗi nhóm đang có từ 4 đến 11 họ class khác nhau.
        Tài liệu này là bản Dev đề xuất, viết đúng 17 cột của khối spec (từ dòng 30) để BA đọc, sửa và duyệt. Dev không ghi lên Sheet; file `ba-component-spec-proposal.xlsx` đi kèm có sẵn 7 dòng cùng thứ tự cột để BA dán khi đã duyệt. Status đang là `Dev Proposed`, BA đổi sang `BA Confirmed` khi chốt.
    """)))
    o.append(r'\section*{Cách lấy số liệu ``Hiện trạng''}')
    o.append(block(T("""
        - Đo computed-style và kích thước bằng trình duyệt tự động trên build hiện hành (cùng version UAT), user chủ cửa hàng, khổ 1440×900 và 390×844, ngày 02/10/2026.
        - Số lần dùng = số lần class xuất hiện trong template portal.
        - Khảo sát thuộc hạng mục khác, không đo và không đề xuất ở đây.
    """)))
    o.append(r'\section*{Nguyên tắc chọn giá trị đề xuất}')
    o.append(block(T("""
        - Chỉnh ít: lấy dáng đang chiếm đa số trên UAT làm chuẩn, như cách BA đã làm ở CMP-FB-001.
        - Chỉ dùng token đã có; màu theo bộ StatusBadge; cỡ chữ tối thiểu 13 (12 cho badge/nhãn KPI).
        - Nhất quán với spec đã chốt: PageContainer, SurfaceCard, CardHeader, StatusBadge, FilterBar, ListCard.
        - Chỗ có hai lựa chọn ngang nhau: Dev không tự quyết, ghi thành câu hỏi ở mục CẦN BA CHỐT (cột Out of scope / Rủi ro) và nêu phương án Dev đề xuất.
    """)))
    o.append(r'\section*{Tổng hợp 7 dòng}')
    o.append(r'\begin{tabularx}{\textwidth}{@{}l l X l l@{}}\toprule')
    o.append(r'\textbf{STT} & \textbf{ID} & \textbf{Component} & \textbf{Priority} & \textbf{Task}\\\midrule')
    for r in ROWS:
        o.append('%s & %s & %s & %s & %s\\\\' % (r['STT'], esc(r['Component ID']), inline(r['Component']),
                                                 r['Priority'], esc(r['Related Task / Issue'])))
    o.append(r'\bottomrule\end{tabularx}')
    o.append(r'\section*{Câu hỏi cần BA chốt}')
    o.append(r'\begin{longtable}{@{}p{0.17\textwidth}p{0.79\textwidth}@{}}\toprule')
    o.append(r'\textbf{Dòng} & \textbf{Câu hỏi (kèm phương án Dev đề xuất)}\\\midrule\endhead')
    for r in ROWS:
        for q in questions(r):
            o.append('%s & %s\\\\' % (esc(r['Component ID']), inline(q)))
    o.append(r'\bottomrule\end{longtable}')
    o.append(r'\section*{Thứ tự triển khai sau khi BA duyệt}')
    o.append(block(T("""
        1. EmptyState (High — FilterBar đã chuyển nút "Xóa lọc" sang đây).
        2. Badge tách khỏi StatusBadge.
        3. DetailSummary + KeyValue.
        4. InfoBanner.
        5. StatCard.
        6. Modal, FormField (nếu BA đưa vào danh mục).
        Mỗi dòng một đợt riêng, có ảnh trước/sau và số đo máy theo Acceptance của dòng đó.
    """)))

    o.append(r'\chapter{Đề xuất chi tiết}')
    sections = ['Mục tiêu', 'Hiện trạng / Vấn đề', 'Spec chuẩn hóa', 'Variants', 'Màn hình áp dụng',
                'Acceptance Criteria', 'Out of scope / Rủi ro', 'Link tham chiếu']
    for i, r in enumerate(ROWS):
        if i:
            o.append(r'\clearpage')
        o.append(r'\section{%s --- %s}' % (esc(r['Component ID']), inline(r['Component'])))
        o.append(r'\begin{tabularx}{\textwidth}{@{}l X l X@{}}\toprule')
        o.append(r'STT & %s & Nhóm & %s\\' % (r['STT'], esc(r['Nhóm'])))
        o.append(r'Priority & %s & Status & %s\\' % (r['Priority'], esc(r['Status'])))
        o.append(r'Task & %s & Odoo Fit & %s\\' % (esc(r['Related Task / Issue']), esc(r['Odoo Fit'])))
        o.append(r'Ngày cập nhật & %s & & \\\bottomrule\end{tabularx}' % r['Ngày cập nhật'])
        for col in sections:
            o.append(r'\subsection*{%s}' % esc(col))
            o.append(block(r[col]))
    o.append(r'\end{document}')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(o) + '\n')


if __name__ == '__main__':
    write_xlsx(os.path.join(DOCS, 'ba-component-spec-proposal.xlsx'))
    write_tex(os.path.join(DOCS, 'ba-component-spec-proposal.tex'))
    print('ok: %d dòng × %d cột' % (len(ROWS), len(COLUMNS)))
