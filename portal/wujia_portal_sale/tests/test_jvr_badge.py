"""★J-VR — màu badge màn "Đặt hàng thành công" (mobile) tính từ `_lt`, không từ nhãn đã dịch.

Trước ★J-VR controller truyền nhãn ĐÃ DỊCH vào `status_badge_for`; user vi_VN vẫn đúng màu nhờ nhánh tra ngược
vi_VN.po (đã bỏ), còn ngôn ngữ khác (th/zh sau J-T5) rơi về neutral. Chạy: `--test-tags wujia_jvr`.
"""
from odoo.tests import tagged

from . import test_g5_submit_confirm as g5  # module, không import class: loader sẽ chạy lại cả G5


@tagged('post_install', '-at_install', 'wujia_jvr')
class TestJVRSubmittedBadge(g5.TestG5SubmitConfirm):
    """Kế thừa fixture F6/G5 (user f6_owner vi_VN, `make_order`, `page`) — chỉ chạy test bên dưới."""

    for _name in [n for n in dir(g5.TestG5SubmitConfirm)
                  if n.startswith('test_') and callable(getattr(g5.TestG5SubmitConfirm, n))]:
        locals()[_name] = None
    del _name

    def _badge(self, so, lang):
        self.user.lang = lang
        self.authenticate('f6_owner', 'f6_owner')  # ngôn ngữ phiên cố định lúc đăng nhập
        badge = self.page('/portal/order/submitted/%s' % so.id).xpath(
            "//span[contains(concat(' ', @class, ' '), ' wj-status-badge ')]")
        self.assertEqual(len(badge), 1)
        return badge[0].text_content().strip(), badge[0].get('class').split()

    def test_same_colour_in_every_language(self):
        cases = (
            ('draft', 'Chờ xác nhận', 'Awaiting confirmation', 'wj-status-badge--pending'),
            ('sale', 'Đã xác nhận', 'Confirmed', 'wj-status-badge--info'),
        )
        for state, vi, en, css in cases:
            so = self.make_order(state=state)
            for lang, text in (('vi_VN', vi), ('en_US', en)):
                with self.subTest(state=state, lang=lang):
                    label, classes = self._badge(so, lang)
                    self.assertEqual(label, text)
                    self.assertIn(css, classes)
