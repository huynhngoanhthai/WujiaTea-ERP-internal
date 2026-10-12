"""D3d — `portal_exam_wizard.js` đọc tiêu đề khoá thi để chép sang thẻ "đã chọn".

F5b dời khỏi `wujia_portal_layout`: guard này kiểm chính màn Đăng ký thi.
"""
import os

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'wujia_card_header_d3')
class TestCardHeaderExamJsContract(TransactionCase):
    """D3d — `portal_exam_wizard.js` đọc tiêu đề khoá thi để chép sang thẻ "đã chọn".

    Migrate đổi tên class tiêu đề mà quên sửa JS thì KHÔNG có lỗi, không đỏ build:
    tên khoá thi chỉ âm thầm biến mất khỏi bước 2 và 3 (đã chứng minh bằng mutation).
    """

    def _js(self):
        path = os.path.join(os.path.dirname(__file__), '..',
                            'static', 'src', 'js', 'portal_exam_wizard.js')
        with open(path, encoding='utf-8') as fh:
            return fh.read()

    def test_wizard_reads_component_title_not_retired_class(self):
        """E5b2 đổi NGUỒN chứ không đổi ĐÍCH: card khoá thi ở bước 1 nay là
        ListCard (tên ở `.wj-lc__name`), thẻ "đã chọn" vẫn là `wj_card_header`.
        Đọc nhầm nguồn thì bước 2 hiện tiêu đề RỖNG — chính guard này bắt được."""
        js = self._js()
        self.assertIn("card.querySelector('.wj-lc__name')", js)
        for retired in ("'.wujia-mexam-course-title'", "'.wujia-mexam-selcard-title'"):
            self.assertNotIn(retired, js)

    def test_wizard_still_scopes_selected_card_title_to_that_card(self):
        # Bám `.wj-card-header__title` trần là quét TRÚNG mọi header khác của wizard
        # (bước 1 + bước 4) rồi ghi đè tên chúng.
        self.assertIn(".wujia-mexam-selcard .wj-card-header__title", self._js())

    def test_person_head_left_untouched_pending_ba(self):
        # 2 vùng trailing (badge "Bắt buộc" + nút xoá) > tối đa MỘT của spec ⇒ defer;
        # và JS clone chính khối này làm template, đọc `.wujia-mexam-person-name`.
        arch = self.env.ref('wujia_portal_exam.portal_exam_register').arch_db
        self.assertIn('wujia-mexam-person-name', arch)
        self.assertIn("querySelector('.wujia-mexam-person-name')", self._js())


@tagged('post_install', '-at_install', 'wujia_card_header_d3')
class TestCardHeaderExamPcJsContract(TransactionCase):
    """PC "Đăng ký mới": D3d chuyển khung giờ sang `wj_card_header` nhưng `portal_exam_pc.js` vẫn tìm
    `.wj-exam-pc-slots__title` ⇒ selector ra null, tiêu đề kẹt "Khung giờ ngày —" dù đã chọn ngày (UAT 06/10)."""

    def test_pc_slot_title_selector_matches_card_header(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'static', 'src', 'js', 'portal_exam_pc.js')
        with open(path, encoding='utf-8') as fh:
            js = fh.read()
        self.assertIn('qs(root, ".wj-exam-pc-slots__head .wj-card-header__title")', js)
        self.assertNotIn('".wj-exam-pc-slots__title"', js)
        arch = self.env.ref('wujia_portal_exam.portal_exam_register').arch_db
        self.assertIn("'wj-exam-pc-slots__head'", arch, 'ch_class của header khung giờ đổi ⇒ sửa selector JS')

    def test_pc_slot_title_without_day_has_no_dash(self):
        # Chưa chọn ngày: "Time slot" (giống JS khi đổi khoá), không phải "Time slots on —".
        arch = self.env.ref('wujia_portal_exam.portal_exam_register').arch_db
        self.assertIn("""<t t-if="pc_summary['exam_date'] != '—'">Time slots on""", arch)
        self.assertIn('<t t-else="">Time slot</t>', arch)
