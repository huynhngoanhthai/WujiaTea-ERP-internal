"""E2 / UI-STATUSBADGE-001 — phần StatusBadge chạm nhiều module.

F5b dời khỏi `wujia_portal_layout`: bảng trạng thái → badge nằm ở `portal_base`, và
việc quét call site là việc của tầng ghép. Hợp đồng dáng của component vẫn ở layout.
"""
import os
import re

from lxml import html

from odoo.addons.wujia_portal_base.controllers.utils import (
    MOBILE_BATCH_BADGES,
    SALE_STATE_META,
    RETURN_STATUS_LABELS,
    STATUS_BADGE_VARIANTS,
    status_badge,
    status_badge_for,
)
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .common import legacy_vn_badge, load_vi

CUSTOM = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
THAI_MODULES = ('wujia_portal_inspection',)

# H2 (I10) — Bootstrap `badge` BA loại khỏi CMP-SB-001 (chờ CMP-TAG-001 / H4b), đếm đúng số dòng.
# Khoá = (file, mẫu nhận dạng dòng) → số dòng.
BOOTSTRAP_BADGE_EXCLUDED = {
    # RoleBadge + "Main owner" + cờ "Updated" (ẩn, JS bật) — màn chọn cửa hàng
    ('wujia_portal_base/views/portal_templates.xml', r'text-bg-#\{role_color\}'): 2,
    ('wujia_portal_base/views/portal_templates.xml', r'text-bg-warning ms-1">Main owner'): 2,
    ('wujia_portal_base/views/portal_templates.xml', r'text-bg-success d-none">Updated'): 1,
    ('wujia_portal_base/views/portal_franchises_in_layout.xml', r'badge-#\{role_color\}'): 2,
    ('wujia_portal_base/views/portal_franchises_in_layout.xml', r'badge-warning ml-1">Main owner'): 2,
    ('wujia_portal_base/views/portal_franchises_in_layout.xml', r'badge-success d-none">Updated'): 1,
    ('wujia_portal_base/views/portal_franchise_profile.xml', r'is_primary_owner.*Main owner'): 1,
    # CountBadge: số bài theo danh mục Kiến thức + số trên chuông/giỏ header
    ('wujia_portal_knowledge/views/portal_knowledge.xml', r'article_count'): 1,
    ('wujia_portal_notification/views/header_bell_inherit.xml', r'wujia-header-noti-count'): 1,
    ('wujia_portal_sale/views/header_cart_inherit.xml', r'wujia-header-cart-count'): 1,
}


@tagged('post_install', '-at_install', 'wujia_status_badge_e2')
class TestStatusBadgeMapsAndCallSites(TransactionCase):

    def _read(self, rel):
        with open(os.path.join(CUSTOM, rel), encoding='utf-8') as fh:
            return fh.read()

    # --- 2. một chủ sở hữu dáng -------------------------------------------
    def test_no_route_or_breakpoint_variant_owns_the_shape(self):
        """Mọi rule chạm .wj-status-badge chỉ được sửa MÀU hoặc VỊ TRÍ, không sửa dáng."""
        shape = re.compile(r'\b(height|min-width|padding|border-radius|font-size|'
                           r'font-weight|line-height)\s*:')
        offenders = []
        for root, _dirs, files in os.walk(CUSTOM):
            if '/static/' not in root or not root.endswith('css'):
                continue
            for fn in files:
                if not fn.endswith('.css'):
                    continue
                path = os.path.join(root, fn)
                # bỏ comment trước khi tách rule: /* … */ dính vào selector làm
                # test đọc nhầm rule gốc thành rule có tổ tiên.
                text = re.sub(r'/\*.*?\*/', '', open(path, encoding='utf-8').read(), flags=re.S)
                for selector, body in re.findall(r'([^{}]+)\{([^}]*)\}', text):
                    if 'wj-status-badge' not in selector:
                        continue
                    # chỉ rule GỐC (tên lớp đứng một mình) được khai dáng
                    bare = selector.strip().startswith('.wj-status-badge')
                    if bare and '--' not in selector and ' ' not in selector.strip():
                        continue
                    # LC-25 (BA 06/09): ListCard được dùng badge chữ 12 qua MỘT
                    # modifier chung. Miễn trừ hẹp: chỉ `--compact`, chỉ font-size
                    # + line-height (UI-LISTCARD-002: cùng dòng chữ với CategoryBadge).
                    if selector.strip() == '.wj-status-badge--compact':
                        khai = {d.split(':')[0].strip()
                                for d in body.split(';') if ':' in d}
                        if khai == {'font-size', 'line-height'}:
                            continue
                    if shape.search(body):
                        offenders.append('%s → %s' % (os.path.basename(path), selector.strip()))
        self.assertEqual(offenders, [], 'dáng badge bị ghi đè theo route/breakpoint')

    # --- 3. lỗi gốc BA nêu -------------------------------------------------
    def test_confirmed_label_is_info_not_success(self):
        # WJ-HOME-010: Home dùng chung SALE_STATE_META với Lịch sử, màu theo nhãn.
        # J-V2: nhãn là `_lt` ⇒ so bản dịch vi_VN; màu theo câu gốc nên đúng ở mọi ngôn ngữ.
        label = SALE_STATE_META['sale'][0]
        self.assertEqual(load_vi(self.env)._(label), 'Đã xác nhận')
        self.assertEqual(status_badge_for(label), 'wj-status-badge--info')
        # ★J-VR: nhãn đã dịch không quyết màu nữa; màu cũ của chữ VN giữ qua đáp án test.
        self.assertEqual(legacy_vn_badge('Đã xác nhận'), 'wj-status-badge--info')

    def test_every_shared_map_emits_a_component_class(self):
        order = {k: (lbl, status_badge_for(lbl)) for k, (lbl, _t) in SALE_STATE_META.items()}
        for name, mapping in (('order', order), ('batch', MOBILE_BATCH_BADGES),
                              ('return', RETURN_STATUS_LABELS)):
            for state, (label, cls) in mapping.items():
                self.assertTrue(label, '%s/%s thiếu nhãn' % (name, state))
                self.assertRegex(cls, r'^wj-status-badge--(%s)$' % '|'.join(STATUS_BADGE_VARIANTS),
                                 '%s/%s còn class cũ: %s' % (name, state, cls))

    def test_unknown_variant_falls_back_to_neutral(self):
        self.assertEqual(status_badge('khong-co-that'), 'wj-status-badge--neutral')
        self.assertEqual(status_badge_for('Nhãn lạ chưa map'), 'wj-status-badge--neutral')

    # --- 4. họ ngoài phạm vi ----------------------------------------------
    def test_excluded_families_keep_their_own_class(self):
        """RoleBadge/AreaBadge/CodeBadge/loại thông báo KHÔNG được migrate (BA loại)."""
        arch = self.env.ref('wujia_portal_base.portal_franchise_information').arch_db
        root = html.fromstring('<div>%s</div>' % arch)
        role = root.xpath('.//span[contains(@t-attf-class,"wj-pc-badge--staff")]')
        area = root.xpath('.//span[contains(@class,"wj-pc-badge--area")]')
        self.assertEqual(len(role), 1, 'RoleBadge phải giữ nguyên hệ cũ')
        self.assertEqual(len(area), 1, 'AreaBadge phải giữ nguyên hệ cũ')

    # --- 5. call site đã về component --------------------------------------
    def test_audited_screens_have_no_legacy_status_badge_left(self):
        """Màn BA chụp ảnh (Lịch sử đặt hàng) + Giao hàng + Kết quả gửi đơn: 0 họ cũ."""
        legacy = re.compile(r'(?<![\w-])(wujia-badge|wj-pc-badge|wujia-mdelivery-badge|'
                            r'wujia-mres-badge)(?![\w-])')
        for rel in ('wujia_portal_purchase_history/views/portal_history.xml',
                    'wujia_portal_delivery/views/portal_delivery.xml',
                    'wujia_portal_sale/views/portal_order_result.xml'):
            self.assertEqual(legacy.findall(self._read(rel)), [],
                             '%s còn badge họ cũ' % rel)

    def _portal_views(self):
        """Mọi view của module portal của mình (bỏ Khảo sát — code anh Thái)."""
        for mod in sorted(os.listdir(CUSTOM)):
            if not mod.startswith('wujia_portal_') or mod in THAI_MODULES:
                continue
            views = os.path.join(CUSTOM, mod, 'views')
            if not os.path.isdir(views):
                continue
            for fn in sorted(os.listdir(views)):
                if fn.endswith('.xml'):
                    rel = '%s/views/%s' % (mod, fn)
                    yield rel, self._read(rel)

    def test_every_portal_screen_has_no_bootstrap_badge_outside_ba_exclusions(self):
        """H2 (I10): Bootstrap `badge` thô chỉ còn ở họ BA loại (Role · Main owner · đếm · cờ
        'Updated' ẩn). Danh sách loại trừ đếm ĐÚNG số chỗ ⇒ thêm một chỗ mới cũng đỏ, H4b hạ dần."""
        bootstrap = re.compile(r'(?<![\w-])badge\s+(?:bg|text-bg|badge)-')
        found = {}
        for rel, text in self._portal_views():
            for line in text.splitlines():
                if bootstrap.search(line):
                    key = next((k for k in BOOTSTRAP_BADGE_EXCLUDED
                                if k[0] == rel and re.search(k[1], line)), (rel, line.strip()[:90]))
                    found[key] = found.get(key, 0) + 1
        self.assertEqual(found, BOOTSTRAP_BADGE_EXCLUDED,
                         'Bootstrap badge ngoài danh sách loại trừ BA (hoặc loại trừ đã cũ)')

    def test_status_maps_never_fall_back_to_a_legacy_family(self):
        """H2 (I10): fallback của map trạng thái trong template cũng phải là component —
        state lạ (dữ liệu cũ) thì vẫn ra `.wj-status-badge--neutral`, không ra chip họ cũ."""
        fallback = re.compile(r'(?:state_labels|comp_status_labels|status_labels)\.get\([^)]*?'
                              r"'(?!wj-status-badge--)[\w-]*badge[\w-]*'")
        offenders = ['%s → %s' % (rel, m.group(0)[:80])
                     for rel, text in self._portal_views() for m in fallback.finditer(text)]
        self.assertEqual(offenders, [], 'fallback map trạng thái còn họ badge cũ')
