"""D6b — phân cấp card Bù hàng: UAT-BH-008 (tách badge) + UAT-BH-007 (tên 2 dòng).

Bám cột `Kết quả mong muốn` của hai issue:

  BH-008  "Người dùng phân biệt ngay trạng thái phê duyệt và tiến độ bù; card có
          thứ bậc thông tin rõ, cân đối và nhất quán với hệ thống Portal."
  BH-007  "…tên song ngữ dễ đọc, không bị cắt giữa nội dung và không tạo cảm giác
          dùng font rời rạc."

Đo *dáng* là việc của `scripts/qa/wj_returncard.py` (trình duyệt thật). Ở đây khoá
**hợp đồng cấu trúc + CSS nguồn**, thứ mà bảng đo không giữ được qua các sprint sau.
"""
import os
import re

from lxml import etree

from odoo.tests import TransactionCase, tagged

from .common import load_vi

HERE = os.path.dirname(__file__)
MOD = os.path.abspath(os.path.join(HERE, '..'))
VIEW = os.path.join(MOD, 'views', 'portal_return_list.xml')
CSS = os.path.join(MOD, 'static', 'src', 'css', 'portal_return.css')
# E5b1: ruột card về CMP-LC-001 ⇒ clamp 2 dòng và lưới metadata nay khai ở khung.
LC_CSS = os.path.join(os.path.dirname(MOD), 'wujia_portal_layout', 'static', 'assets',
                      'css', '_components.css')


# J-V6: câu gốc nhãn là tiếng Anh (file nguồn); vi_VN dịch về đúng chữ BA ("Tiến độ bù", "Ngày yêu cầu")
# — kiểm ở `test_nhan_vi_giu_nguyen`.
LBL_PROGRESS = 'Compensation progress'
LBL_REQUEST_DATE = 'Request date'


def _view():
    return etree.parse(VIEW)


def _css():
    with open(CSS, encoding='utf-8') as fh:
        return fh.read()


def _lc_css():
    with open(LC_CSS, encoding='utf-8') as fh:
        return fh.read()


def _strip_comments(css):
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


def _rule(css, selector):
    """Thân rule của `selector`, tìm ở MỌI tầng (file này bọc trong @media)."""
    css = _strip_comments(css)
    for m in re.finditer(re.escape(selector) + r'\s*\{([^}]*)\}', css):
        return m.group(1)
    return None


def _has_class(el, name):
    return name in (el.get('class') or '').split()


@tagged('post_install', '-at_install', 'wujia_return_d6')
class TestReturnCardD6(TransactionCase):

    def setUp(self):
        super().setUp()
        self.root = _view()
        rows = self.root.xpath('//a[@t-foreach="returns"]')
        self.assertEqual(len(rows), 1, 'card mobile phải là DUY NHẤT 1 mẫu record')
        self.row = rows[0]

    # ------------------------------------------------------------ BH-008
    def test_dong_dau_khong_con_badge_tien_do_bu(self):
        """Gốc rễ BH-008: trước D6b cả hai badge nằm chung dòng đầu. Sau E5b1 dòng
        đầu là slot `lc_state` của ListCard — vẫn chỉ được có trạng thái phê duyệt."""
        heads = self.row.xpath('.//t[@t-set="lc_state"]')
        self.assertEqual(len(heads), 1, 'card phải có đúng 1 slot trạng thái')
        head = heads[0]
        # `comp_status_labels` là nguồn DUY NHẤT của nhãn tiến độ bù ⇒ dấu vết
        # của nó bên trong dòng đầu nghĩa là badge vẫn còn ở đó.
        dau_vet = [el for el in head.iter()
                   if 'comp_status_labels' in (el.get('t-value') or '')
                   or 'clbl' in (el.get('t-attf-class') or '')
                   or 'clbl' in (el.get('t-out') or '')]
        self.assertFalse(
            dau_vet, 'badge tiến độ bù vẫn nằm trong dòng đầu — BH-008 chưa đạt')

    def test_co_dong_tien_do_bu_rieng_co_nhan(self):
        """BA đòi rõ: dòng riêng, **nhãn "Tiến độ bù"**. Sau E5b1 dòng phụ đi qua
        khuôn `wj_list_card_row`, nhãn nằm ở `lcr_label`."""
        prog = self._hang_co_nhan(LBL_PROGRESS)
        self.assertIsNotNone(prog, 'thiếu dòng riêng có nhãn cho tiến độ bù')
        # dòng này nằm trong thân card (`lc_rows`), không lồng vào slot trạng thái
        to = [a.get('t-set') for a in prog.iterancestors()]
        self.assertIn('lc_rows', to, 'dòng tiến độ bù không nằm trong thân card')
        self.assertNotIn('lc_state', to, 'dòng tiến độ bù chui lại vào dòng đầu')

    def _hang_co_nhan(self, nhan):
        """Hàng phụ (`wj_list_card_row`) có `lcr_label` đúng bằng `nhan`."""
        for row in self.row.xpath('.//t[@t-call="wujia_portal_layout.wj_list_card_row"]'):
            for lbl in row.xpath('./t[@t-set="lcr_label"]'):
                if (lbl.text or '').strip() == nhan:
                    return row
        return None

    def test_nhan_tien_do_bu_lay_tu_hang_controller(self):
        """Không hardcode 4 nhãn: nguồn phải là `comp_status_labels`, vốn chính là
        `COMPENSATION_STATUS_LABELS` truyền qua qcontext. Hardcode thì đổi nhãn ở
        controller mà card vẫn in nhãn cũ."""
        prog = self._hang_co_nhan(LBL_PROGRESS)
        badge = prog.xpath('.//span[contains(@t-attf-class, "wj-status-badge")]')
        self.assertEqual(len(badge), 1)
        self.assertIn('clbl', badge[0].get('t-out') or '',
                      'badge tiến độ bù phải in từ biến clbl')
        nguon = self.row.xpath('.//t[contains(@t-value, "comp_status_labels")]')
        self.assertTrue(nguon, 'mất tham chiếu tới comp_status_labels')

        from ..controllers.portal import COMPENSATION_STATUS_LABELS
        for nhan, _lop in COMPENSATION_STATUS_LABELS.values():
            self.assertNotIn(
                nhan._source, etree.tostring(self.row, encoding='unicode'),
                'nhãn %r bị chép cứng vào template' % nhan)

    def test_nhan_vi_giu_nguyen(self):
        """J-V6: user vi_VN vẫn thấy đúng hai nhãn BA trên card mobile."""
        arch = self.env.ref('wujia_portal_return.portal_return_list').with_env(load_vi(self.env)).arch
        for vi in ('Tiến độ bù', 'Ngày yêu cầu'):
            self.assertIn('<t t-set="lcr_label">%s</t>' % vi, arch)

    def test_nhan_ngay_yeu_cau_du_nam(self):
        """LC-15: nhãn đầy đủ "Ngày yêu cầu" (không viết tắt) và ngày ĐỦ NĂM —
        `%d/%m` khiến phiếu cuối năm và đầu năm sau trông như cùng một kỳ."""
        row = self._hang_co_nhan(LBL_REQUEST_DATE)
        self.assertIsNotNone(row, 'mất nhãn "Ngày yêu cầu" (LC-15)')
        gia_tri = row.xpath('./t[@t-set="lcr_value"]/@t-value')
        self.assertTrue(gia_tri, 'hàng ngày yêu cầu không còn giá trị')
        self.assertIn("'%d/%m/%Y'", gia_tri[0], 'ngày yêu cầu mất phần năm')

    def test_metadata_hai_cot_on_dinh(self):
        """`flex` cho ô thứ hai trôi theo độ dài ô thứ nhất (đo trước D6b: 2 bố
        cục left khác nhau). BA đòi "bố cục hai cột ổn định" ⇒ sau E5b1 hai ô là
        hai cột của lưới `wj-lc__body`, KHÔNG phải hai item flex co giãn."""
        than = _rule(_lc_css(), '.wj-lc__body')
        self.assertIsNotNone(than, 'mất rule thân ListCard')
        self.assertRegex(than, r'display:\s*grid')
        self.assertRegex(than, r'grid-template-columns:\s*minmax\(0, 1fr\) auto')
        hang = [r for r in self.row.xpath(
            './/t[@t-call="wujia_portal_layout.wj_list_card_row"]')
            if r.xpath('./t[@t-set="lcr_class"][contains(@t-value, "wj-lc__row--inline")]')]
        self.assertEqual(len(hang), 2, 'hai ô metadata phải nằm chung một hàng lưới')

    # ------------------------------------------------------------ BH-007
    def test_ten_san_pham_toi_da_hai_dong(self):
        """E5b1: clamp 2 dòng về khung (`wj-lc__row--clamp2`), call site chỉ khai
        dùng nó — cả hai vế đều phải còn, mất vế nào cũng là BH-007 tái phát."""
        than = _rule(_lc_css(), '.wj-lc__row--clamp2 .wj-lc__value')
        self.assertIsNotNone(than, 'mất rule clamp 2 dòng ở khung')
        self.assertRegex(than, r'-webkit-line-clamp:\s*2\b')
        self.assertNotIn('nowrap', than,
                         'còn `nowrap` ⇒ vẫn cắt ngay dòng 1, BH-007 chưa đạt')
        self.assertTrue(
            self.row.xpath('.//t[@t-set="lcr_class"][contains(@t-value, "wj-lc__row--clamp2")]'),
            'hàng tên sản phẩm không còn khai clamp 2 dòng')

    def test_khong_khai_lai_stack_font(self):
        """Fallback CJK đã nằm trên `--wujia-font-family` từ D2. Khai stack thứ hai
        ở module là nguồn của chính lỗi "font rời rạc" mà BH-007 phàn nàn."""
        self.assertNotIn('font-family', _strip_comments(_css()))

    # --------------------------------------------------- giao cắt D5f
    def test_giu_nguyen_hop_dong_datalist_d5f(self):
        """D6b sửa phân cấp BÊN TRONG card, KHÔNG đụng khung — nếu không sẽ tái
        tạo hồi quy "thẻ trắng lồng thẻ trắng" mà D5h.2 vừa vá."""
        self.assertTrue(_has_class(self.row, 'wj-data-item'))
        self.assertTrue(_has_class(self.row, 'wj-lc'), 'item mất ruột ListCard')
        calls = self.root.xpath(
            '//t[@t-call="wujia_portal_layout.wj_data_list"]'
            '[t[@t-set="dl_variant"][@t-value="\'detail-card\'"]]')
        self.assertEqual(len(calls), 1, 'call site DataList detail-card bị đổi')
        # E5b1: họ `wujia-mreturn-row*` của danh sách đã đi hẳn ⇒ module không còn
        # rule dáng nào cho hàng; giữ luật "không khai lại dáng" bằng cách quét CSS.
        css = _strip_comments(_css())
        for dang in ('border-radius', 'min-height'):
            self.assertNotRegex(
                css, r'\.wj-lc[^{}]*\{[^}]*%s' % dang,
                'module khai lại dáng %r của ListCard — phải để component giữ' % dang)
