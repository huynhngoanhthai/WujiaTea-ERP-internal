"""D5 — DataList trên màn Đăng ký thi.

F5b dời khỏi `wujia_portal_layout`: guard này kiểm chính màn của module này.
"""
import os
import re

from lxml import html

from odoo.tests import TransactionCase, tagged

from odoo.addons.wujia_portal_base.tests.css_probe import (
    CSS_DIR, CUSTOM, _chu_the, _css, _mod_css, _rule, _rule_in_media, _strip_comments,
    _view,
)

TMPL = 'wujia_portal_layout.wj_data_list'


@tagged('post_install', '-at_install', 'wujia_data_list_d5')
class TestDataListExam(TransactionCase):
    """D5h — Thi: 1 bảng PC + 3 danh sách mobile, cả ba nay dùng ruột ListCard
    (E5b2) nên item mang `wj-lc`; dáng NGOÀI vẫn là việc của D5.
    Variant chọn theo SỐ ĐO: lịch thi 104 và khoá thi 96–109 → dải 96–120;
    danh sách nhân sự đo LẠI sau E5b2 là 92–146, ra khỏi dải compact-row 64–76
    ⇒ khai `detail-card`.
    Hai call site nằm ở MÀN CON (/portal/exam/register, /portal/exam/registration/N)
    nên bộ đo 10 route BA không nhìn thấy — guard là chỗ duy nhất ghim chúng."""

    VIEW = ('wujia_portal_exam', 'portal_exam.xml')

    def _root(self):
        return _view(*self.VIEW)

    def _css(self):
        with open(os.path.join(CUSTOM, 'wujia_portal_exam', 'static', 'src', 'css',
                               'portal_exam.css'), encoding='utf-8') as fh:
            return fh.read()

    def _calls(self, variant=None):
        out = []
        for call in self._root().xpath('//t[@t-call="wujia_portal_layout.wj_data_list"]'):
            got = call.xpath('./t[@t-set="dl_variant"]/@t-value')
            got = got[0].strip("'") if got else None
            if got == variant:
                out.append(call)
        return out

    def _bang(self):
        """Chọn theo CẤU TRÚC (có thead) — bất biến trước mọi phép thay dl_variant
        (bài học D5g #3)."""
        return [c for c in self._root().xpath(
            '//t[@t-call="wujia_portal_layout.wj_data_list"]') if c.xpath('.//thead')]

    def _mobile(self, ho):
        """Quét TOKEN ở bất kỳ vị trí nào: item thi mở đầu bằng lớp wj-surface-card
        của D4 nên `re.match` từ đầu chuỗi (cách D5g) bỏ sót đúng call site này."""
        out = []
        for call in self._root().xpath('//t[@t-call="wujia_portal_layout.wj_data_list"]'):
            for el in call.iter():
                cls = el.get('class') or el.get('t-attf-class') or ''
                if re.search(r'(^|\s)%s(?![-\w])' % re.escape(ho), cls):
                    out.append((call, cls))
                    break
        return out

    def _bang_theo_lop(self, lop):
        """Chọn bảng theo LỚP CŨ ở dl_table_class — hai bảng PC của màn Thi khác
        nhau ở chỗ đó, còn cấu trúc (có thead) thì giống hệt."""
        out = []
        for call in self._bang():
            got = call.xpath('./t[@t-set="dl_table_class"]/@t-value')
            if got and re.search(r'(^|\s)%s(?![-\w])' % re.escape(lop), got[0]):
                out.append(call)
        return out

    def test_bon_call_site(self):
        self.assertEqual(len(self._bang()), 2, 'bảng PC lịch sử đăng ký + bảng kết quả')
        self.assertEqual(len(self._bang_theo_lop('wj-exam-pc-list-table')), 1)
        self.assertEqual(len(self._bang_theo_lop('wj-exam-pc-res-table')), 1,
                         'bảng kết quả thi (D5h.1) phải nằm trong wj_data_list')
        self.assertEqual(len(self._calls('detail-card')), 3,
                         'lịch thi + khoá thi + danh sách nhân sự')
        self.assertEqual(len(self._calls('compact-row')), 0,
                         'E5b2: không còn danh sách nào của màn Thi ở dải 64–76')

    def test_moi_th_deu_co_scope(self):
        """0/8 trước lượt này. Bảng `wj-exam-pc-part-table` của form nhập KHÔNG
        nằm trong DataList nên cố ý ngoài phạm vi — ghi ở LIMIT."""
        tong = 0
        for call in self._bang():
            ths = call.xpath('.//thead//th')
            self.assertTrue(ths, 'bảng PC mất thead')
            for th in ths:
                self.assertEqual(th.get('scope'), 'col',
                                 'th thiếu scope="col": %s' % (th.text or '').strip())
            tong += len(ths)
        self.assertEqual(tong, 15, 'số cột hai bảng PC màn Thi đổi (8 + 7)')

    def test_item_mobile_mang_ca_hai_lop(self):
        """E5b2: neo theo `wj-lc` — hai trong ba họ cũ đã retire, chỉ còn
        `wujia-mexam-course`/`-rrow` sống như lớp TRẠNG THÁI (is-closed, màu ô icon)."""
        found = self._mobile('wj-lc')
        self.assertEqual(len(found), 3, 'phải đúng 3 danh sách mobile dùng ListCard')
        for _call, cls in found:
            self.assertIn('wj-data-item', cls.split(), 'item thiếu wj-data-item')

    def test_pager_di_qua_component(self):
        """Trước D5 pager màn Thi hiện dù chỉ 1 trang; E3c đưa cả guard đó vào
        component nên ở đây chỉ ghim: bảng PC thi phân trang bằng `wj_pagination`."""
        thay = 0
        for call in self._bang_theo_lop('wj-exam-pc-list-table'):
            pagers = call.xpath('./t[@t-set="dl_pager"]')
            self.assertEqual(len(pagers), 1, 'bảng PC thi phải truyền dl_pager')
            self.assertEqual(
                len(pagers[0].xpath('.//t[@t-call="wujia_portal_layout.wj_pagination"]')), 1,
                'bảng PC thi không gọi component pager')
            self.assertFalse(pagers[0].xpath('.//*[contains(@t-attf-class, "wj-pc-page-btn")]'),
                             'nút trang cũ quay lại màn thi')
            thay += 1
        self.assertGreaterEqual(thay, 1, 'không quét trúng bảng nào — guard rỗng')

    def test_bang_ket_qua_khong_de_pager_va_co_empty_state(self):
        """D5h.1 — bảng kết quả thi render trọn theo `pc_detail['lines']`, KHÔNG
        phân trang ⇒ không được đẻ pager giả (bài học pager giả ở D5h)."""
        # Chọn theo CẤU TRÚC (thead 7 cột) — đổi tên lớp là phép của
        # test_bon_call_site, không được kéo test này đỏ theo (bài học D5g #3).
        bang = [c for c in self._bang() if len(c.xpath('.//thead//th')) == 7]
        self.assertEqual(len(bang), 1)
        call = bang[0]
        self.assertFalse(call.xpath('./t[@t-set="dl_pager"]'),
                         'bảng kết quả không phân trang mà vẫn truyền dl_pager')
        self.assertFalse(call.xpath('.//t[@t-call="wujia_portal_layout.wj_pagination"]'
                                    ' | .//*[contains(@class, "wj-pagination")]'))
        empty = call.xpath('./t[@t-set="dl_empty"]/@t-value')
        self.assertEqual(len(empty), 1, 'thiếu dl_empty ⇒ 0 dòng vẫn vẽ khung bảng rỗng')
        self.assertIn("pc_detail['lines']", empty[0])
        self.assertTrue(call.xpath('./t[@t-set="dl_state"]//*[contains(@class, "wj-pc-empty")]'),
                        'thiếu DataState cho bảng kết quả')

    def test_bang_ket_qua_khoa_dang_cu(self):
        """Hai tầng: `.wj-exam-pc-res-table` cũ ép cứng header 46 / row 62 / đệm 20;
        phải khoá bằng :not(.wj-data-table) mới nhường số BA cho component."""
        css = _strip_comments(self._css())
        kiem = 0
        for khoi in re.finditer(r'([^{}]+)\{([^{}]*)\}', css):
            sel, than = khoi.group(1).strip(), khoi.group(2)
            for phan in sel.split(','):
                if not re.search(r'\.wj-exam-pc-res-table(?![-\w])', phan):
                    continue
                kiem += 1
                if ':not(.wj-data-table)' in phan:
                    continue
                for prop in ('height', 'padding'):
                    self.assertNotRegex(
                        than, r'(^|;)\s*%s\s*:' % prop,
                        'rule cũ "%s" còn ép %s mà chưa khoá :not(.wj-data-table)'
                        % (phan.strip(), prop))
        self.assertGreaterEqual(kiem, 3, 'không quét trúng rule nào — guard rỗng')

    def test_mot_chu_so_huu_dang_item(self):
        """E5b2: ba họ ruột đã retire (sổ đăng ký E5 canh), chỉ còn
        `wujia-mexam-course`/`-rrow` sống như lớp TRẠNG THÁI ⇒ cấm khai lại dáng."""
        DANG = ('padding', 'background', 'border-radius', 'height', 'display')

        def quet(css):
            loi = []
            for khoi in re.finditer(r'([^{}]+)\{([^{}]*)\}', _strip_comments(css)):
                sel, than = khoi.group(1).strip(), khoi.group(2)
                for phan in sel.split(','):
                    chu = _chu_the(re.sub(r':not\([^)]*\)', '', phan))
                    if not re.match(r'\.(wujia-mexam-course|wujia-mexam-rrow)(?![-\w])', chu):
                        continue
                    loi += ['rule "%s" giành lại dáng item bằng %s' % (phan.strip(), prop)
                            for prop in DANG if re.search(r'(^|;)\s*%s\s*:' % prop, than)]
            return loi
        # I13 bỏ rule cuối (`.is-closed { opacity }`) — khoá đã đóng dùng `.wj-data-item.is-disabled` của
        # DataList ⇒ CSS màn có thể không còn rule nào; tự kiểm guard bằng mẫu thay cho đếm ≥1.
        self.assertTrue(quet('.wujia-mexam-course.is-closed { background: #eee; }'), 'guard rỗng')
        self.assertFalse(quet(self._css()))

    def test_khong_con_rule_layout_rieng_cho_item(self):
        """E5b2 đảo chiều test cũ: layout bên trong item nay là của ListCard ⇒ màn
        KHÔNG được khai lại rule layout cho item, nếu không hai bộ dáng lại đè nhau."""
        css = _strip_comments(self._css())
        for ho in ('wujia-mexam-course', 'wujia-mexam-rrow'):
            for variant in ('detail-card', 'compact-row'):
                sel = '.wj-data-list--%s .%s.wj-data-item' % (variant, ho)
                self.assertIsNone(_rule_in_media(css, sel),
                                  '%s: rule layout riêng quay lại' % sel)

    def test_surface_card_khong_bi_sua(self):
        """E5b2: item màn Thi rời `wj-surface-card` — dáng ngoài nay do D5
        detail-card lo một mình. Component D4 vẫn phải bất biến."""
        css = _css('_components.css')
        than = _rule(css, '.wj-surface-card')
        self.assertIsNotNone(than, 'mất rule .wj-surface-card')
        self.assertRegex(than, r'border-radius:\s*var\(--wujia-surface-radius\)',
                         'CSS của SurfaceCard đã bị sửa ở lượt D5h')
        self.assertEqual(self._mobile('wj-surface-card'), [],
                         'item màn Thi lại mang hai chủ dáng (D4 + D5)')
