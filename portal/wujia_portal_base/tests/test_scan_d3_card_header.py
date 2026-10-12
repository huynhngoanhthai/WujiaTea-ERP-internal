"""D3 (quét nhiều module) — call site CardHeader CMP-CH-001.

F5b dời khỏi `wujia_portal_layout`: khung không được biết màn nào. Hợp đồng render
của component + rule dáng của chính khung vẫn ở layout.
"""
import os
import re

from lxml import html

from odoo.tests import TransactionCase, tagged

from .common import need


@tagged('post_install', '-at_install', 'wujia_card_header_d3')
class TestCardHeaderCallSites(TransactionCase):
    """Route đã migrate (D3a + D3b) phải dùng component và bỏ được các bệnh BA nêu."""

    CALL_SITES = {
        # D3a — 4 họ markup mẫu
        'wujia_portal_support.portal_support_list': 1,
        'wujia_portal_return.portal_return_form': 4,
        # D3c — nốt phần còn lại của chính 4 file D3a
        'wujia_portal_delivery.portal_delivery_detail': 4,
        'wujia_portal_base.portal_franchise_information': 8,
        'wujia_portal_support.portal_support_form': 1,
        'wujia_portal_support.portal_support_detail': 7,  # +1 thẻ "File đính kèm" mobile (26/09) · +1 "Nội dung yêu cầu" mobile (I8)
        # D3b — nhóm màn kế tiếp
        # G3b/142: Khung giờ (PC + mobile) + 7 block Home PC V4 (3 block list cũ đã bỏ)
        'wujia_portal_base.portal_home_page': 9,
        'wujia_portal_base.portal_franchise_profile_full': 4,
        'wujia_portal_knowledge.portal_knowledge_list': 2,
        'wujia_portal_knowledge.portal_knowledge_detail': 3,
        'wujia_portal_notification.portal_notification_results_part': 1,
        'wujia_portal_notification.portal_notification_detail': 4,
        'wujia_portal_report.portal_report_orders': 3,
        'wujia_portal_sale.pc_cart_panel': 1,
        'wujia_portal_sale.portal_order_product_detail': 1,
        'wujia_portal_info_request.portal_info_request_list': 1,
        'wujia_portal_return.portal_return_list': 1,
        # D3d — màn Đăng ký thi (PC + wizard mobile)
        # E5b2: đầu card danh sách nay là .wj-lc__head của ListCard, không CardHeader.
        'wujia_portal_exam.portal_exam_schedule': 1,
        'wujia_portal_exam.portal_exam_register': 8,
        'wujia_portal_exam.portal_exam_registration_detail': 3,
        # D3e — chi tiết bù hàng + lịch sử đặt hàng
        'wujia_portal_return.portal_return_detail': 15,
        'wujia_portal_purchase_history.portal_history_results_part': 1,
        # I7 WJ-PH-009: +1 card "Ghi chú khi đặt hàng" bản PC.
        'wujia_portal_purchase_history.portal_history_detail': 9,
    }

    ZERO_COUNT_VIEWS = {
        'wujia_portal_support.portal_support_list': 'tickets',
        'wujia_portal_knowledge.portal_knowledge_list': 'articles',
        'wujia_portal_report.portal_report_orders': 'top_products',
        'wujia_portal_info_request.portal_info_request_list': 'requests',
        'wujia_portal_return.portal_return_list': 'returns',
        'wujia_portal_support.portal_support_detail': 'comments',
        'wujia_portal_purchase_history.portal_history_results_part': 'rows',
    }

    FLUSH_VIEWS = {
        'wujia_portal_base.portal_franchise_profile_full': 4,
        'wujia_portal_knowledge.portal_knowledge_list': 1,
        'wujia_portal_knowledge.portal_knowledge_detail': 1,
        # D3c: 4 card Bootstrap + card "Lịch sử trao đổi" (card khai padding:0) + thẻ "File đính kèm" mobile
        # + thẻ "Nội dung yêu cầu" mobile (I8, WJ-SUPPORT-002)
        'wujia_portal_support.portal_support_detail': 7,
        # khối `wj-pc-acct-staff` — dòng `__line` dưới đã tự khai margin-top 8px
        'wujia_portal_base.portal_franchise_information': 1,
        # summary head chuyến giao — `.wj-pc-order-head` đã có padding riêng
        'wujia_portal_delivery.portal_delivery_detail': 1,
        # D3e: 5 card Bootstrap của chi tiết bù hàng + summary head lịch sử đặt hàng
        'wujia_portal_return.portal_return_detail': 5,
        'wujia_portal_purchase_history.portal_history_detail': 1,
    }

    RETIRED_IN_VIEW = {
        'wujia_portal_base.portal_home_page': ('wujia-content-card-header-title',
                                               'wujia-mhome-window-title'),
        'wujia_portal_base.portal_franchise_profile_full': ('card-title',),
        'wujia_portal_knowledge.portal_knowledge_detail': ('wujia-mknow-h',),
        'wujia_portal_notification.portal_notification_detail': ('wujia-mnoti-detail-sectitle',),
        'wujia_portal_report.portal_report_orders': ('wj-pc-card__title',),
        'wujia_portal_sale.pc_cart_panel': ('wj-pc-cart-title',),
        'wujia_portal_info_request.portal_info_request_list': ('wujia-content-card-header-title',),
        'wujia_portal_return.portal_return_list': ('wujia-content-card-header-title',),
        # D3c
        'wujia_portal_support.portal_support_form': ('wujia-mdash-title',),
        'wujia_portal_support.portal_support_detail': ('wujia-mdash-title',),
        'wujia_portal_base.portal_franchise_information': ('wujia-maccount-cardtitle',
                                                           'wujia-maccount-store-name'),
        'wujia_portal_delivery.portal_delivery_detail': ('wj-pc-order-head__code',
                                                         'wj-pc-dlv-head-meta'),
        # D3d
        'wujia_portal_exam.portal_exam_schedule': ('wujia-mexam-card-title',),
        'wujia_portal_exam.portal_exam_register': ('wujia-mexam-course-title',
                                                   'wujia-mexam-selcard-title',
                                                   'wujia-mexam-cftitle',
                                                   'wj-exam-pc-slots__title'),
        'wujia_portal_exam.portal_exam_registration_detail': ('wujia-mexam-rsum-title',),
        # D3e
        'wujia_portal_return.portal_return_detail': ('wujia-mhist-card-head',),
        'wujia_portal_purchase_history.portal_history_results_part': ('wj-pc-card__title',),
        'wujia_portal_purchase_history.portal_history_detail': ('wujia-mhist-card-head',
                                                                'wj-pc-order-head__code',
                                                                'wj-pc-card__title'),
    }

    SHARED_MARKUP_VIEWS = ('wujia_portal_info_request.portal_info_request_list',)

    def _arch(self, xmlid):
        need(self, xmlid)
        return self.env.ref(xmlid).arch_db

    def test_shared_markup_views_do_not_bake_platform(self):
        for xmlid in self.SHARED_MARKUP_VIEWS:
            with self.subTest(view=xmlid):
                arch = self._arch(xmlid)
                self.assertNotIn('d-lg-none', arch, 'view này phải là markup dùng chung')
                # bám directive, KHÔNG bám chữ: comment giải thích cũng chứa "ch_platform"
                self.assertNotIn('t-set="ch_platform"', arch)

    def test_call_sites_use_component(self):
        for xmlid, count in self.CALL_SITES.items():
            with self.subTest(view=xmlid):
                self.assertEqual(
                    self._arch(xmlid).count('wujia_portal_layout.wj_card_header'),
                    count)

    def test_count_not_hidden_when_zero(self):
        # Spec: "Count 0 vẫn hiển thị" ⇒ khối count không được bọc `t-if` theo recordset.
        for xmlid, recordset in self.ZERO_COUNT_VIEWS.items():
            with self.subTest(view=xmlid):
                root = html.fromstring('<div>%s</div>' % self._arch(xmlid))
                counts = root.xpath('.//t[@t-set="ch_meta"]')
                self.assertTrue(counts, 'view phải có slot count')
                for node in counts:
                    for el in [node] + node.xpath('.//*'):
                        self.assertNotIn(recordset, el.get('t-if') or '')

    def test_flush_on_legacy_card_header_wrapper(self):
        for xmlid, count in self.FLUSH_VIEWS.items():
            with self.subTest(view=xmlid):
                self.assertEqual(
                    self._arch(xmlid).count('wj-card-header--flush'), count)

    def test_retired_heading_classes_gone_from_migrated_views(self):
        for xmlid, classes in self.RETIRED_IN_VIEW.items():
            arch = self._arch(xmlid)
            for cls in classes:
                with self.subTest(view=xmlid, cls=cls):
                    self.assertNotIn('class="%s' % cls, arch)

    def test_migrated_headers_drop_stacking_margin(self):
        # Spec cấm cộng chồng margin header với body ⇒ `mb-3`/`mb-1` phải biến mất
        # khỏi CHÍNH dòng tiêu đề (component tự quyết nhịp 8/12).
        root = html.fromstring(
            '<div>%s</div>' % self._arch('wujia_portal_return.portal_return_form'))
        self.assertEqual(root.xpath('.//p[contains(@class,"wujia-mdash-title")]'), [])

    def test_header_keeps_the_class_that_pays_its_padding(self):
        # Component KHÔNG tự khai padding ⇒ 4 header của /portal/support/<id> phải giữ lớp
        # vỏ cấp padding, nếu không header dính sát mép card. D4e2 (3d83af2) đổi nguồn đó
        # từ `card-header` của Bootstrap sang `wj-surface-card__head`; quan hệ không đổi.
        arch = self._arch('wujia_portal_support.portal_support_detail')
        self.assertEqual(arch.count("'wj-surface-card__head wj-card-header--flush'"), 4)
        self.assertNotIn("'card-header wj-card-header--flush'", arch)

    def test_store_name_became_subtitle_not_a_second_heading(self):
        # Chủ dự án chốt 02/09: mobile xếp giống bản PC cùng card (tiêu đề → dòng phụ →
        # badge). Tên cửa hàng phải đi vào slot subtitle, KHÔNG còn là heading rời, và
        # hàng badge phải nằm SAU header.
        root = html.fromstring(
            '<div>%s</div>' % self._arch('wujia_portal_base.portal_franchise_information'))
        subs = root.xpath('.//t[@t-set="ch_subtitle"][@t-value="franchise.name or \'—\'"]')
        self.assertEqual(len(subs), 1)
        # D4e2 thay `div.wujia-mdash-card` bằng `t-call wj_surface_card` + slot `sc_class`.
        # FR-B(b): thẻ này là <div> thuần (không sc_href) nên đã gỡ marker `wj-state-surface`;
        # guard kiểm THỨ TỰ tiêu đề → badge, chuỗi class chỉ là chi tiết nhận dạng thẻ.
        card = root.xpath('.//t[@t-call="wujia_portal_layout.wj_surface_card"]'
                          '[t[@t-set="sc_class"][@t-value="\'wujia-mdash-card\'"]]'
                          '[t[@t-call="wujia_portal_layout.wj_card_header"]]'
                          '[div[@class="wujia-maccount-badgerow"]]')
        self.assertEqual(len(card), 1, 'card "Cửa hàng nhượng quyền" phải còn nguyên')
        kids = [c.get('t-call') or c.get('class') for c in card[0]]
        self.assertLess(kids.index('wujia_portal_layout.wj_card_header'),
                        kids.index('wujia-maccount-badgerow'))

    def test_no_pseudo_heading_left_in_migrated_views(self):
        for xmlid in self.CALL_SITES:
            with self.subTest(view=xmlid):
                root = html.fromstring('<div>%s</div>' % self._arch(xmlid))
                self.assertEqual(
                    root.xpath('.//p[contains(@class,"wujia-mdash-title")]'
                               '|.//p[contains(@class,"card-title")]'), [])


@tagged('post_install', '-at_install', 'wujia_card_header_d3')
class TestCardHeaderD3eLayout(TransactionCase):
    """D3e — hai bẫy đã trả giá khi migrate 2 file này, khoá lại bằng test."""

    def _arch(self, xmlid):
        need(self, xmlid)
        return self.env.ref(xmlid).arch_db

    def test_order_head_meta_stays_card_content(self):
        # Dòng meta dài hơn mã đơn; đưa nó vào `ch_subtitle` thì lead nở theo nó và
        # badge (trailing) trôi khỏi mã đơn — chỉ ẢNH CHỤP bắt được, số đo vẫn Pass.
        root = html.fromstring(
            '<div>%s</div>'
            % self._arch('wujia_portal_purchase_history.portal_history_detail'))
        head = root.xpath('.//div[@class="wj-pc-order-head"]')
        self.assertEqual(len(head), 1)
        self.assertTrue(head[0].xpath('.//p[@class="wj-pc-order-head__meta"]'))
        self.assertEqual(head[0].xpath('.//t[@t-set="ch_subtitle"]'), [])

    def test_order_head_lead_shrinks_in_shared_css(self):
        # Rule gom về gốc `.wj-pc-order-head` (2 consumer: delivery D3c + history D3e).
        path = os.path.join(os.path.dirname(__file__), '..', '..',
                            'wujia_portal_layout', 'static', 'assets', 'css',
                            '_pc_components.css')
        with open(path, encoding='utf-8') as fh:
            css = fh.read()
        self.assertRegex(
            css,
            r'\.wj-pc-order-head \.wj-card-header__lead\s*\{[^}]*flex:\s*0 1 auto')

    def test_return_sublabels_keep_their_own_shape(self):
        # 4 nhãn phụ trong thân card: chuẩn hoá cấu trúc nhưng KHÔNG được to bằng
        # tiêu đề card cha, nếu không một card có ba dòng chữ cùng cỡ.
        arch = self._arch('wujia_portal_return.portal_return_detail')
        # Từ D3 REVIEW, ch_class mở đầu bằng modifier chung rồi mới tới lớp module.
        self.assertEqual(arch.count("wj-card-header--sublabel wj-return-sublabel"), 4)
        path = os.path.join(os.path.dirname(__file__), '..', '..', 'wujia_portal_return',
                            'static', 'src', 'css', 'portal_return.css')
        with open(path, encoding='utf-8') as fh:
            css = fh.read()
        # Cỡ chữ đã về modifier dùng chung `wj-card-header--sublabel` (D3 REVIEW
        # 2026-09-04) — ở lại file module đúng phần MÀU riêng. Quan hệ được giữ
        # vẫn y nguyên: nhãn phụ .875rem < tiêu đề card 18px.
        # F4: màu thường cũng về modifier chung; module chỉ còn màu danger (ngữ nghĩa).
        self.assertNotRegex(
            css,
            r'\.wj-surface-card__body > \.wj-card-header\.wj-return-sublabel'
            r'\s+\.wj-card-header__title\s*\{')
        self.assertRegex(
            css,
            r'\.wj-card-header\.wj-return-sublabel--danger'
            r'\s+\.wj-card-header__title\s*\{[^}]*color:')
        self.assertEqual(arch.count('wj-card-header--sublabel'), 4)


@tagged('post_install', '-at_install', 'wujia_card_header_d3')
class TestCardHeaderD3Review(TransactionCase):
    """D3 REVIEW (2026-09-04) — mỗi guard giữ một QUAN HỆ: nhãn phụ nhỏ hơn tiêu đề
    card cùng card, hai module cùng vai trò dùng CHUNG một khai báo, chữ đủ tương
    phản với nền của chính nó.
    """

    def _read(self, rel):
        path = os.path.join(os.path.dirname(__file__), '..', '..', rel)
        with open(path, encoding='utf-8') as fh:
            return fh.read()

    def _arch(self, xmlid):
        need(self, xmlid)
        return self.env.ref(xmlid).arch_db

    COMPONENTS = 'wujia_portal_layout/static/assets/css/_components.css'

    EXAM = 'wujia_portal_exam/static/src/css/portal_exam.css'

    INSP = 'wujia_portal_inspection/static/src/css/portal_inspection.css'

    RETURN = 'wujia_portal_return/static/src/css/portal_return.css'

    def test_module_css_no_longer_redeclares_sublabel_size(self):
        # Còn bản chép tay nào là "đồng bộ" lại vỡ ngay lần sửa sau.
        for rel in (self.RETURN, self.INSP):
            with self.subTest(css=rel):
                self.assertNotRegex(
                    self._read(rel),
                    r'\.wj-(return|insp)-sublabel[^{}]*\.wj-card-header__title\s*\{'
                    r'[^}]*font-size')

    def test_sublabel_call_sites_carry_the_shared_modifier(self):
        # 5 chỗ: 4 ở phiếu trả hàng (D3e) + 1 ở khảo sát (D3f).
        self.assertEqual(
            self._arch('wujia_portal_return.portal_return_detail')
            .count('wj-card-header--sublabel'), 4)
        self.assertEqual(
            self._arch('wujia_portal_inspection.portal_inspection_detail')
            .count('wj-card-header--sublabel'), 1)

    def test_exam_nested_labels_step_down_from_the_card_title(self):
        # D3d hội tụ tiêu đề card 22->18 nhưng không hạ khối con theo, nên cả hai
        # cùng 18px và mất phân cấp — bảng đo D3d vẫn Pass vì so từng số với chuẩn
        # chứ không so hai số VỚI NHAU. Chủ dự án chốt khối con = 16px.
        css = self._read(self.EXAM)
        self.assertRegex(
            css,
            r'\.wj-exam-pc \.wj-card-header\.wj-exam-pc-sechead--sm'
            r'\s+\.wj-card-header__title,\s*'
            r'\.wj-exam-pc \.wj-card-header\.wj-exam-pc-sechead--2'
            r'\s+\.wj-card-header__title,\s*'
            r'\.wj-exam-pc \.wj-card-header\.wj-exam-pc-slots__head'
            r'\s+\.wj-card-header__title\s*\{[^}]*font-size:\s*16px\s*!important')
        # F4: rule `.wj-exam-pc .wj-pc-card__title{22px}` đã xoá — 0 phần tử khớp (exam
        # không còn `wj-pc-card__title`); tiêu đề card là CardHeader 18px > 16px ở trên.
        self.assertNotIn('.wj-exam-pc .wj-pc-card__title', css)

    def test_exam_sectitle_rules_survive_because_a_call_site_is_still_live(self):
        # `wj-exam-pc-sectitle` CHƯA chết: còn 1 call site ở portal_exam.xml
        # ("Người tham gia" — chỗ defer chờ BA). Xoá rule là vỡ im lặng.
        css = self._read(self.EXAM)
        self.assertRegex(css, r'\.wj-exam-pc \.wj-exam-pc-sectitle\s*\{'
                              r'[^}]*font-size:\s*20px\s*!important')

    DEAD = (
        'wujia-content-card-header', 'wujia-mdash-title', 'wujia-mhist-card-head',
        'wujia-mknow-h', 'wujia-maccount-store-name', 'wj-pc-acct-staff__title',
        'wj-pc-order-head__code', 'wj-pc-cart-title', 'wj-pc-dlv-head-meta',
        'wujia-mexam-rsum-title', 'wujia-mnoti-detail-sectitle',
        'wj-exam-pc-sectitle--2',
    )

    DEAD_CSS = (COMPONENTS, EXAM,
                'wujia_portal_layout/static/assets/css/_pc_account.css',
                'wujia_portal_layout/static/assets/css/_pc_components.css',
                'wujia_portal_sale/static/src/css/portal_order.css',
                'wujia_portal_delivery/static/src/css/portal_delivery.css',
                'wujia_portal_notification/static/src/css/portal_notification.css',
                # F2: CSS mhist/mknow/mticket dời khỏi _components.css
                'wujia_portal_purchase_history/static/src/css/portal_history.css',
                'wujia_portal_knowledge/static/src/css/portal_knowledge.css',
                'wujia_portal_support/static/src/css/portal_support.css')

    def test_dead_card_header_classes_stay_deleted(self):
        # Chúng đã hết call site sau khi D3 migrate 95 chỗ; để lại là mỗi phiên sau
        # lại phải đọc và đoán xem còn sống không.
        for rel in self.DEAD_CSS:
            css = self._read(rel)
            for cls in self.DEAD:
                with self.subTest(css=rel, cls=cls):
                    self.assertNotRegex(css, r'\.%s([^-_a-zA-Z0-9]|$)' % re.escape(cls))

    def test_exam_summary_card_keeps_the_rhythm_of_its_neighbour(self):
        # Bốn card một trang phải cùng nhịp header→body. D3 chốt con số ở chính file exam
        # (36 → 18px); D4e2 (3d83af2) chuyển quyền giữ nhịp sang `.wj-surface-card__body`
        # nên exam phải KHÔNG còn khai margin — khai lại là đúng loại drift cũ.
        block = re.search(r'\.wj-exam-pc-sumlist\s*\{([^}]*)\}', self._read(self.EXAM))
        self.assertTrue(block, 'không tìm thấy rule .wj-exam-pc-sumlist')
        self.assertNotRegex(block.group(1), r'margin(-top)?\s*:')
        self.assertRegex(self._read(self.COMPONENTS),
                         r'\.wj-surface-card__body\s*\{[^}]*padding:')
