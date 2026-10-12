"""E2b / UI-STATUSBADGE-001 — phần còn lại của CMP-SB-001.

E2a khoá component + nhóm màn BA chụp ảnh. E2b khoá nốt thông báo · thi ·
trả hàng · công nợ · yêu cầu thông tin · hỗ trợ, và khoá hai chiều:
badge trạng thái phải về component, chip BA loại (ưu tiên · loại · đếm ·
tệp đính kèm · phương án xử lý) phải Ở NGUYÊN họ cũ.

F5b dời khỏi `wujia_portal_layout`: cả bộ này đọc map + view của 6 module nghiệp vụ.
"""

import os
import re

from lxml import etree

from odoo.addons.wujia_portal_base.controllers.utils import STATUS_BADGE_VARIANTS
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .common import legacy_vn_badge

# Bậc BA chốt cho nhãn mới của E2b (tab UI Component + spec CMP-SB-001). Nhãn theo chữ vi_VN của spec ⇒
# ★J-VR: so qua `legacy_vn_badge` (câu EN có bản dịch vi = nhãn này ⇒ màu đó).
BA_LABEL_VARIANT = {
    'Chưa đọc': 'info', 'Đã đọc': 'neutral', 'Đã hết hiệu lực': 'neutral',
    'Chờ duyệt': 'pending', 'Đã đăng ký': 'info', 'Đã công bố': 'success',
    'Chưa công bố': 'neutral', 'Chưa có': 'neutral', 'Không áp dụng': 'neutral',
    'Có kết quả': 'success', 'Chưa có kết quả': 'pending', 'Hết chỗ': 'pending',
    'Còn lịch': 'info', 'Đã lên đơn bù': 'processing', 'Đang bù một phần': 'processing',
    'Chưa xử lý': 'pending', 'Đã bù đủ': 'success',
    'Có quá hạn': 'danger', 'Quá hạn': 'danger', 'Chưa thanh toán': 'pending',
    'Thanh toán một phần': 'processing', 'Một phần': 'processing',
    'Đã thanh toán': 'success', 'Dư có': 'info', 'Giấy báo có': 'info',
    'Cần bổ sung': 'feedback', 'Chờ phản hồi': 'feedback', 'Có phản hồi': 'feedback',
}

# Họ trợ giúp bị xoá hẳn ở E2b — còn sót một cái là còn một nguồn dáng thứ hai.
DEAD_FAMILIES = (
    'wj-debt-badge', 'wj-debt-pc-badge',
    'wujia-mexam-card-badge', 'wujia-mexam-course-badge', 'wujia-mexam-rrow-badge',
    'wj-exam-pc-hbadge', 'wj-exam-pc-pbadge', 'wj-exam-pc-rbadge',
)

# Call site component sau migrate — đếm theo CẤU TRÚC (phần tử mang class),
# không đếm chuỗi: một phần tử fallback chứa tên lớp hai lần.
MIGRATED = {
    'wujia_portal_notification/views/portal_notification.xml': 6,
    'wujia_portal_exam/views/portal_exam.xml': 13,
    'wujia_portal_debt/views/portal_debt.xml': 8,
    'wujia_portal_return/views/portal_return_list.xml': 4,
    'wujia_portal_return/views/portal_return_detail.xml': 4,
    'wujia_portal_info_request/views/portal_info_request_list.xml': 1,
    'wujia_portal_info_request/views/portal_info_request_detail.xml': 1,
    'wujia_portal_support/views/portal_support.xml': 4,
}


@tagged('post_install', '-at_install', 'wujia_status_badge_e2b')
class TestStatusBadgeRemainder(TransactionCase):

    def _read(self, rel):
        with open(os.path.join(os.path.dirname(__file__), '..', '..', rel),
                  encoding='utf-8') as fh:
            return fh.read()

    # --- 1. nhãn mới đúng bậc BA ------------------------------------------
    def test_new_labels_carry_the_ba_variant(self):
        for label, variant in BA_LABEL_VARIANT.items():
            self.assertEqual(legacy_vn_badge(label), 'wj-status-badge--%s' % variant,
                             '%s phải là %s theo bậc BA' % (label, variant))

    # --- 2. map của từng module lấy class từ nguồn chung --------------------
    def test_module_maps_emit_a_component_class(self):
        from odoo.addons.wujia_portal_debt.models.wujia_portal_debt import (
            INVOICE_BADGE, STATE_BADGE,
        )
        from odoo.addons.wujia_portal_exam.controllers.portal import (
            PC_PUBLISH_STATES, REG_STATES,
        )
        from odoo.addons.wujia_portal_info_request.controllers.portal import (
            STATE_LABELS as INFO_STATES,
        )
        from odoo.addons.wujia_portal_base.controllers.utils import (
            RETURN_STATUS_LABELS as RETURN_STATES,
        )
        from odoo.addons.wujia_portal_return.controllers.portal import (
            COMPENSATION_STATUS_LABELS,
        )
        from odoo.addons.wujia_portal_support.controllers.portal import (
            MOBILE_TICKET_BADGES, STATE_LABELS as SUPPORT_STATES,
        )
        maps = {
            'debt.state': STATE_BADGE, 'debt.invoice': INVOICE_BADGE,
            'exam.state': REG_STATES,
            'exam.publish': PC_PUBLISH_STATES, 'return.state': RETURN_STATES,
            'return.compensation': COMPENSATION_STATUS_LABELS,
            'info_request.state': INFO_STATES, 'support.state': SUPPORT_STATES,
            'support.mobile': MOBILE_TICKET_BADGES,
        }
        allowed = re.compile(r'^wj-status-badge--(%s)$' % '|'.join(STATUS_BADGE_VARIANTS))
        for name, mapping in maps.items():
            for state, (label, cls) in mapping.items():
                self.assertTrue(label, '%s/%s thiếu nhãn' % (name, state))
                self.assertRegex(cls, allowed, '%s/%s còn class cũ: %s' % (name, state, cls))

    # --- 3. họ trợ giúp bị xoá hẳn ------------------------------------------
    def test_dead_helper_families_have_no_call_site_and_no_rule(self):
        root = os.path.join(os.path.dirname(__file__), '..', '..')
        offenders = []
        for mod_dir, _dirs, files in os.walk(root):
            if '/wujia_portal_inspection' in mod_dir or '/wujia_franchise_inspection' in mod_dir:
                continue  # module Khảo sát — phạm vi cấm đụng
            for fn in files:
                if not fn.endswith(('.xml', '.css')):
                    continue
                text = self._read(os.path.relpath(os.path.join(mod_dir, fn), root))
                for family in DEAD_FAMILIES:
                    if re.search(r'(?<![\w-])%s(?![\w-])' % re.escape(family), text):
                        offenders.append('%s → %s' % (fn, family))
        self.assertEqual(offenders, [], 'họ badge trợ giúp lẽ ra đã bị xoá')

    # --- 4. đã migrate đủ call site -----------------------------------------
    def test_migrated_templates_keep_their_component_call_sites(self):
        attrs = ('class', 't-att-class', 't-attf-class')
        for rel, count in MIGRATED.items():
            tree = etree.fromstring(self._read(rel).encode('utf-8'))
            found = sum(1 for el in tree.iter()
                        if any('wj-status-badge' in (el.get(a) or '') for a in attrs))
            self.assertEqual(found, count, '%s lệch số call site component' % rel)

    # --- 5. chiều ngược: chip BA loại KHÔNG được migrate ---------------------
    def test_excluded_chips_stay_on_the_legacy_family(self):
        noti = self._read('wujia_portal_notification/views/portal_notification.xml')
        self.assertEqual(noti.count('WJ_PTAG'), 4, 'chip ưu tiên phải giữ nguyên hệ cũ')
        self.assertIn('wj-pc-badge wj-pc-badge--confirmed', noti, 'loại thông báo là CategoryBadge')
        self.assertIn('wj-pc-badge wj-pc-badge--cancel', noti, 'badge đếm chưa đọc là CountBadge')
        # I10: chip phương án xử lý nằm ở trang chi tiết; list chỉ còn fallback của map trạng thái
        # (nay là `wj-status-badge--neutral`, khoá ở test_scan_e2).
        ret = self._read('wujia_portal_return/views/portal_return_detail.xml')
        self.assertEqual(ret.count('class="wujia-badge wujia-badge-info" t-out="comp[\'resolution_label\']"'), 2,
                         'phương án xử lý là CategoryBadge')

    # --- 6. badge 28px không được kéo chip bên cạnh -------------------------
    def test_notification_rows_do_not_stretch_the_excluded_chips(self):
        # E5b1: hàng chip của danh sách mobile đã về ruột ListCard ⇒ luật "không
        # stretch" của hàng đó nay do component giữ (kiểm ngay dưới), ở đây còn
        # hai khối chip của trang chi tiết.
        lc = self._read('wujia_portal_layout/static/assets/css/_components.css')
        for selector in ('.wj-lc__head', '.wj-lc__row'):
            m = re.search(r'(?<![\w.-])' + re.escape(selector) + r'\s*\{([^}]*)\}', lc)
            self.assertTrue(m, 'không tìm thấy rule %s' % selector)
            self.assertNotRegex(m.group(1), r'align-items:\s*stretch',
                                '%s để stretch ⇒ chip bị kéo cao theo badge' % selector)
        css = self._read('wujia_portal_notification/static/src/css/portal_notification.css')
        for selector in ('.wujia-mnoti-detail-badges',
                         '.wj-pc-noti-detail-badgerow'):
            m = re.search(r'(?<![\w.-])' + re.escape(selector) + r'\s*\{([^}]*)\}', css)
            self.assertTrue(m, 'không tìm thấy rule %s' % selector)
            self.assertRegex(m.group(1), r'align-items:\s*center',
                             '%s để stretch ⇒ chip ngoài phạm vi bị kéo cao theo badge' % selector)

    # --- 7. ô bảng chứa badge không được vẽ dấu "…" -------------------------
    def test_exam_status_cell_does_not_ellipsize_the_badge(self):
        css = self._read('wujia_portal_exam/static/src/css/portal_exam.css')
        m = re.search(r'\.wj-exam-pc-list-table td\.wj-exam-pc-td--badge\s*\{([^}]*)\}', css)
        self.assertTrue(m, 'thiếu rule tắt ellipsis cho ô trạng thái')
        self.assertRegex(m.group(1), r'text-overflow:\s*clip')
        self.assertIn('wj-exam-pc-td--badge',
                      self._read('wujia_portal_exam/views/portal_exam.xml'))
