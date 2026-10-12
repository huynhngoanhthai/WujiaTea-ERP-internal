"""E5 (quét nhiều module) — call site ListCard CMP-LC-001 (`UI-LISTCARD-001`).

Khung `wujia_portal_layout` giữ hợp đồng template (luật F5b); ở đây là bảng
"màn nào đã về component" cộng ba luật không màn nào được phá:

  · một implementation — call site nào cũng gọi `wj_list_card`, không tự dựng ruột;
  · không CSS anatomy theo route — `.wj-lc*` chỉ được khai ở khung;
  · họ class cũ của màn đã migrate phải BIẾN MẤT khỏi cả view lẫn CSS (nếu không,
    hai bộ dáng cùng sống và cái sau đè cái trước tuỳ độ đặc hiệu).

E5b thêm route mới chỉ bằng cách thêm một dòng vào MIGRATED.
"""
import os
import re

from odoo.tests import TransactionCase, tagged

from odoo.addons.wujia_portal_base.tests.css_probe import (
    CUSTOM, _mod_css, _strip_comments, _view,
)

TMPL = 'wujia_portal_layout.wj_list_card'
ROW = 'wujia_portal_layout.wj_list_card_row'

# (module, file view, số call site record, họ RIÊNG phải biến mất, file CSS module,
#  họ DÙNG CHUNG chỉ phải rời khỏi item đã migrate)
# Vì sao hai loại họ: `wujia-mdash-row` (Home 50 chỗ) và `wujia-content-card-row`
# (Home) còn sống ở màn khác ⇒ xoá rule của chúng là vỡ Home. Với họ dùng chung,
# luật thu hẹp lại: KHÔNG còn nằm trong cây con của item đã migrate.
MIGRATED = [
    ('wujia_portal_purchase_history', 'portal_history.xml', 1,
     ('wujia-mhist-row',), 'portal_history.css', ()),
    ('wujia_portal_delivery', 'portal_delivery.xml', 1,
     ('wujia-mdelivery-row-top', 'wujia-mdelivery-row-headmain', 'wujia-mdelivery-row-id',
      'wujia-mdelivery-row-cols', 'wujia-mdelivery-row-colval'), 'portal_delivery.css', ()),
    ('wujia_portal_notification', 'portal_notification.xml', 1,
     ('wujia-mnoti-list', 'wujia-mnoti-row', 'wujia-mnoti-row-icon', 'wujia-mnoti-row-main',
      'wujia-mnoti-row-title', 'wujia-mnoti-row-source', 'wujia-mnoti-row-tags',
      'wujia-mnoti-row-side', 'wujia-mnoti-row-dot', 'wujia-mnoti-row-date'),
     'portal_notification.css', ()),
    ('wujia_portal_support', 'portal_support.xml', 1,
     ('wujia-mticket-rowside', 'wujia-mticket-tag'), 'portal_support.css',
     ('wujia-mdash-row',)),
    ('wujia_portal_return', 'portal_return_list.xml', 1,
     ('wujia-mreturn-row-body', 'wujia-mreturn-row-product', 'wujia-mreturn-row-divider',
      'wujia-mreturn-row-meta', 'wujia-mreturn-row-metacell', 'wujia-mreturn-row-chevron',
      'wujia-mreturn-row-progress', 'wujia-mreturn-row-badges'), 'portal_return.css', ()),
    ('wujia_portal_knowledge', 'portal_knowledge.xml', 2,
     ('wujia-mknow-list', 'wujia-mknow-row-main', 'wujia-mknow-row-title',
      'wujia-mknow-row-foot', 'wujia-mknow-date'), 'portal_knowledge.css',
     ('wujia-content-card-row',)),
    ('wujia_portal_base', 'portal_franchise_information.xml', 1,
     (), 'portal_dashboard.css', ('wujia-mdash-row',)),
    # E5b2 — Thi ×3. `wujia-mexam-card-top`/`-card-line` KHÔNG nằm trong danh sách
    # phải biến mất: khối tóm tắt phiếu (không phải danh sách) vẫn dùng chúng.
    ('wujia_portal_exam', 'portal_exam.xml', 3,
     ('wujia-mexam-list', 'wujia-mexam-card', 'wujia-mexam-card-title',
      'wujia-mexam-courselist', 'wujia-mexam-course-main', 'wujia-mexam-course-title',
      'wujia-mexam-course-meta', 'wujia-mexam-course-choose', 'wujia-mexam-rlist',
      'wujia-mexam-rrow-main', 'wujia-mexam-rrow-name', 'wujia-mexam-rrow-meta',
      'wujia-mexam-rrow-note'), 'portal_exam.css', ()),
    ('wujia_portal_debt', 'portal_debt.xml', 2,
     ('wj-debt-invoices', 'wj-debt-payments', 'wj-debt-inv__name', 'wj-debt-inv__badge',
      'wj-debt-inv__meta', 'wj-debt-inv__amount', 'wj-debt-pay__ref', 'wj-debt-pay__badge',
      'wj-debt-pay__meta', 'wj-debt-pay__trace', 'wj-debt-pay__amount'),
     'portal_debt.css', ()),
]

# Màn giữ nguyên grouped rows theo LC-23 — E5 KHÔNG được đụng.
GIU_NGUYEN = [('wujia_portal_base', 'portal_home.xml')]


@tagged('post_install', '-at_install', 'wujia_list_card_e5')
class TestListCardCallSites(TransactionCase):

    def _calls(self, module, filename):
        root = _view(module, filename)
        return root.xpath('//t[@t-call="%s"]' % TMPL)

    def _items(self, module, filename):
        root = _view(module, filename)
        out = []
        for el in root.iter():
            cls = el.get('class') or el.get('t-attf-class') or ''
            if 'wj-lc' in cls.split():
                out.append((el, cls))
        return out

    def test_moi_man_da_migrate_deu_goi_component(self):
        for module, filename, n, _cu, _css, _chung in MIGRATED:
            calls = self._calls(module, filename)
            self.assertEqual(len(calls), n,
                             '%s: số call site ListCard đổi' % module)

    def test_item_mang_ca_hai_lop(self):
        """Neo TOKEN ĐỨNG ĐẦU: `contains()` khớp cả `wj-lc__name` (bẫy D5c #3).

        Đếm >= SỐ CALL SITE, không phải "có ít nhất một": màn nhiều danh sách
        (Thi 3, Công nợ 2, Kiến thức 2) mà rơi mất lớp ở một chỗ thì phép đếm
        "có item nào không" vẫn xanh — mũi mutation M1 của E5b2 lọt đúng kiểu đó.
        Dấu >= là vì Giao hàng có thêm item skeleton lúc tải."""
        for module, filename, n, _cu, _css, _chung in MIGRATED:
            items = self._items(module, filename)
            self.assertGreaterEqual(
                len(items), n,
                '%s: %d call site nhưng chỉ %d item mang wj-lc' % (module, n, len(items)))
            for _el, cls in items:
                self.assertIn('wj-data-item', cls.split(),
                              '%s: item thiếu wj-data-item (dáng ngoài của D5)' % module)

    def test_khong_con_ho_class_cu(self):
        """Hai bộ dáng cùng sống là nguồn của mọi hồi quy specificity đã trả giá
        ở D3/D4 — nên họ cũ phải mất ở CẢ view lẫn CSS."""
        for module, filename, _n, cu, css_file, _chung in MIGRATED:
            with open(os.path.join(CUSTOM, module, 'views', filename), encoding='utf-8') as fh:
                view = fh.read()
            css = _strip_comments(_mod_css(module, css_file))
            for ho in cu:
                # So theo TOKEN class, không phải chuỗi con: `wujia-mexam-card` là
                # tiền tố của `wujia-mexam-card-top` (bẫy tên con BEM, bài học D4e).
                self.assertNotRegex(view, r'%s(?![-\w])' % re.escape(ho),
                                    '%s: họ cũ %s còn trong view' % (module, ho))
                self.assertNotRegex(css, r'\.%s(?![-\w])' % re.escape(ho),
                                    '%s: họ cũ %s còn rule CSS' % (module, ho))

    def test_ho_dung_chung_roi_khoi_item_da_migrate(self):
        """Họ dùng chung vẫn sống ở màn khác, nhưng item đã migrate không được
        còn dính — nếu dính thì hai bộ dáng lại đè nhau đúng chỗ vừa dọn."""
        for module, filename, _n, _cu, _css, chung in MIGRATED:
            if not chung:
                continue
            for el, _cls in self._items(module, filename):
                for node in el.iter():
                    cls = (node.get('class') or '') + ' ' + (node.get('t-attf-class') or '')
                    for ho in chung:
                        self.assertNotIn(ho, cls,
                                         '%s: item đã migrate còn mang họ chung %s'
                                         % (module, ho))

    def test_khong_css_anatomy_theo_route(self):
        """LC-24: một implementation — module không được tự khai lại `.wj-lc*`.

        Miễn trừ theo TÍNH CHẤT (tiền lệ D5f): rule chỉ đổi MÀU cho một trạng thái
        riêng của màn (Thông báo tô đậm tên khi chưa đọc) không phải rule dáng —
        cấm nó là mất dấu chưa đọc, mà dáng thì vẫn nguyên ở khung."""
        thay = []
        for root, _dirs, files in os.walk(CUSTOM):
            if '/static/' not in root or not root.endswith('css'):
                continue
            if os.sep + 'wujia_portal_layout' + os.sep in root:
                continue
            for fn in files:
                if not fn.endswith('.css'):
                    continue
                css = _strip_comments(open(os.path.join(root, fn), encoding='utf-8').read())
                for sel, body in re.findall(r'([^{}]+)\{([^}]*)\}', css):
                    if not re.search(r'\.wj-lc(?![-\w])|\.wj-lc__', sel):
                        continue
                    khai = {d.split(':')[0].strip() for d in body.split(';') if ':' in d}
                    # Điều kiện thật là "được BỌC bởi một lớp trạng thái của màn",
                    # không phải "tên lớp bắt đầu bằng .wujia-" (Công nợ dùng
                    # .wj-debt-inv--overdue, vẫn đúng tính chất được miễn trừ).
                    ngoai_khung = re.sub(r'\.wj-lc(__[\w-]+)?(--[\w-]+)?', '', sel)
                    if khai and khai <= {'color'} and '.' in ngoai_khung:
                        continue
                    thay.append('%s → %s' % (fn, sel.strip()[:60]))
        self.assertEqual(thay, [], 'anatomy ListCard bị khai lại ngoài khung')

    def test_hang_phu_dung_khuon_chung(self):
        """LC-05: hàng phụ phải đi qua `wj_list_card_row`, không viết span tay —
        viết tay là cách nhãn/giá trị lệch cỡ chữ giữa các màn."""
        for module, filename, _n, _cu, _css, _chung in MIGRATED:
            root = _view(module, filename)
            rows = root.xpath('//t[@t-call="%s"]' % ROW)
            self.assertTrue(rows, '%s: không hàng phụ nào dùng khuôn chung' % module)
            # `wj-lc__row` trần được phép: khối skeleton là thanh xám, không có
            # nhãn/giá trị. Cấm là nhãn/giá trị viết tay — đó mới là chỗ lệch cỡ chữ.
            tay = [el.get('class') for el in root.iter()
                   if (el.get('class') or '') in ('wj-lc__label', 'wj-lc__value')]
            self.assertEqual(tay, [], '%s: còn nhãn/giá trị viết tay' % module)

    def test_home_giu_grouped_rows(self):
        """LC-23: Home preview KHÔNG tách 1 record 1 card — cấm migrate nhầm."""
        for module, filename in GIU_NGUYEN:
            self.assertFalse(self._calls(module, filename),
                             '%s: Home bị migrate, trái LC-23' % module)
            self.assertFalse(self._items(module, filename),
                             '%s: Home đã mang lớp wj-lc' % module)
