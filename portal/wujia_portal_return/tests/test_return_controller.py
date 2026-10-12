"""Task STT3 — controller Portal ↔ bù hàng: đọc MIME thật, nhãn trạng thái, route (guard cửa hàng, notice, redirect).

Chạy: `--test-tags wujia_return_ct`. Luật (10 ngày, cấu hình bù, SO bù) test ở `wujia_return`.
"""
from odoo import http
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase

from odoo.addons.wujia_return.models.wujia_return_request import MAX_IMAGES, MAX_TOTAL_MB
from odoo.addons.wujia_return.tests.common import (
    JPEG, MOV, MP4, PNG, TEXT, ReturnFixture, _file,
)
from odoo.addons.wujia_portal_return.controllers.portal import (
    MIN_IMAGES, WujiaPortalReturn, state_label,
)


@tagged('post_install', '-at_install', 'wujia_return_ct')
class TestEvidenceValidation(TransactionCase):
    """Acceptance #7 — 3–5 ảnh, ≤1 video, MIME thật, dung lượng từng tệp + tổng."""

    def setUp(self):
        super().setUp()
        self.ctrl = WujiaPortalReturn()
        self.Req = self.env['wujia.return.request']

    def _validate(self, images, video):
        """Đường portal thật: controller đọc MIME từ nội dung, model áp luật."""
        self.Req._portal_check_evidence([self.ctrl._sniff(f) for f in images],
                                        [self.ctrl._sniff(f) for f in video])

    def _images(self, n, data=JPEG, **kw):
        return [_file(data, filename=f'p{i}.jpg', **kw) for i in range(n)]

    def test_three_to_five_images_accepted(self):
        for n in (MIN_IMAGES, 4, MAX_IMAGES):
            self._validate(self._images(n), [])

    def test_two_images_rejected(self):
        with self.assertRaises(ValidationError):
            self._validate(self._images(2), [])

    def test_six_images_rejected(self):
        with self.assertRaises(ValidationError):
            self._validate(self._images(6), [])

    def test_png_accepted(self):
        self._validate(
            [_file(PNG, filename=f'p{i}.png', content_type='image/png')
             for i in range(3)], [])

    def test_fake_extension_rejected_by_real_mime(self):
        """Đổi đuôi + đổi header vẫn không qua được: MIME đọc từ nội dung."""
        files = self._images(2) + [_file(TEXT, filename='evil.jpg')]
        with self.assertRaises(ValidationError):
            self._validate(files, [])

    def test_image_over_size_limit_rejected(self):
        big = self._images(2) + [_file(JPEG, filename='big.jpg', pad=6 * 1024 * 1024)]
        with self.assertRaises(ValidationError):
            self._validate(big, [])

    def test_video_mp4_and_mov_accepted(self):
        self._validate(
            self._images(3), [_file(MP4, 'v.mp4', 'video/mp4')])
        self._validate(
            self._images(3),
            [_file(MOV, 'v.mov', 'application/octet-stream')])

    def test_video_mime_is_sniffed_not_trusted(self):
        real = self.ctrl._real_mime(_file(MOV, 'v.mov', 'application/octet-stream'))
        self.assertEqual(real, 'video/quicktime')
        self.assertEqual(self.ctrl._real_mime(_file(MP4, 'v.mp4')), 'video/mp4')

    def test_second_video_rejected(self):
        with self.assertRaises(ValidationError):
            self._validate(
                self._images(3),
                [_file(MP4, 'v1.mp4', 'video/mp4'), _file(MP4, 'v2.mp4', 'video/mp4')])

    def test_video_over_size_limit_rejected(self):
        with self.assertRaises(ValidationError):
            self._validate(
                self._images(3),
                [_file(MP4, 'v.mp4', 'video/mp4', pad=11 * 1024 * 1024)])

    def test_total_over_30mb_rejected(self):
        # Từng tệp vẫn dưới trần riêng (ảnh <5MB, video <10MB) nhưng tổng ~34MB.
        images = [_file(JPEG, filename=f'p{i}.jpg', pad=int(4.9 * 1024 * 1024))
                  for i in range(5)]
        video = [_file(MP4, 'v.mp4', 'video/mp4', pad=int(9.9 * 1024 * 1024))]
        with self.assertRaises(ValidationError) as err:
            self._validate(images, video)
        self.assertIn(str(MAX_TOTAL_MB), str(err.exception))


@tagged('post_install', '-at_install', 'wujia_return_ct')
class TestStateLabels(TransactionCase, ReturnFixture):
    """Acceptance #8 — 6 nhãn BA, 'Đang bù một phần' suy từ tiến độ, không đổi schema."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # J-V2: nhãn trạng thái của portal_base là `_lt` (câu gốc EN) ⇒ chạy ở vi_VN để giữ assert tiếng Việt.
        cls.env['res.lang']._activate_lang('vi_VN')
        cls.env = cls.env(context=dict(cls.env.context, lang='vi_VN'))
        cls._setup_return_data()

    def test_basic_labels(self):
        expected = {'submitted': 'Đã gửi', 'reviewing': 'Đang xử lý',
                    'approved': 'Đã duyệt', 'rejected': 'Từ chối',
                    'done': 'Hoàn tất'}
        rr = self._request()
        for state, label in expected.items():
            rr.state = state
            self.assertEqual(state_label(rr)[0], label)

    def test_partial_compensation_label(self):
        rr = self._request(state='approved', resolution_type='compensation',
                           approved_qty=20.0, approved_uom_id=self.uom_kg.id)
        self.env['wujia.compensation.allocation'].create({
            'request_id': rr.id, 'allocated_qty': 20.0,
            'allocation_uom_id': self.uom_kg.id, 'delivered_qty': 5.0,
            'state': 'partial'})
        rr.state = 'processing'
        self.assertEqual(rr.compensation_status, 'partial')
        self.assertEqual(state_label(rr)[0], 'Đang bù một phần')


@tagged('post_install', '-at_install', 'wujia_return_ct')
class TestPortalRoutes(HttpCase, ReturnFixture):
    """Acceptance #2/#3/#9 — phạm vi cửa hàng, bộ lọc, phản hồi cuối cùng."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_return_data()
        cls.member_user = cls.env['res.users'].create({
            'name': 'CT3 owner', 'login': 'ct3.owner', 'password': 'ct3.owner',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.env['wujia.franchise.member'].create({
            'franchise_id': cls.franchise.id,
            'user_id': cls.member_user.id,
            'role': 'owner',
        })
        cls.mine = cls._request(backend_note='SECRET internal note',
                                approval_note='HQ duyệt 20kg',
                                resolution_type='compensation',
                                approved_qty=20.0,
                                approved_uom_id=cls.uom_kg.id,
                                compensation_product_id=cls.product.id)
        cls.theirs = cls._request(franchise=cls.other, order=cls.order_other)

    def _login_portal(self):
        self.authenticate('ct3.owner', 'ct3.owner')

    def test_list_shows_only_my_store(self):
        self._login_portal()
        body = self.url_open('/portal/return').text
        self.assertIn(self.mine.name, body)
        self.assertNotIn(self.theirs.name, body)

    def test_cross_store_detail_redirects_with_notice(self):
        self._login_portal()
        res = self.url_open(f'/portal/return/{self.theirs.id}')
        self.assertNotIn(self.theirs.name, res.text)
        self.assertIn('Không tìm thấy yêu cầu hoặc bạn không có quyền truy cập',
                      res.text)

    def test_detail_hides_internal_note_and_shows_final_reply(self):
        self._login_portal()
        body = self.url_open(f'/portal/return/{self.mine.id}').text
        self.assertNotIn('SECRET internal note', body)
        self.assertIn('HQ duyệt 20kg', body)

    def test_bad_date_range_returns_friendly_message(self):
        """E4c tách hai loại lỗi: ngày NGƯỢC báo tại thanh lọc (cùng câu chữ với
        5 màn kia), ngày SAI ĐỊNH DẠNG vẫn là lỗi cấp trang ở banner."""
        self._login_portal()
        nguoc = self.url_open(
            '/portal/return?date_from=2026-12-31&date_to=2026-01-01').text
        self.assertIn('Từ ngày không được lớn hơn Đến ngày', nguoc)
        self.assertNotIn('Bộ lọc không hợp lệ', nguoc)
        hong = self.url_open('/portal/return?date_from=31/12/2026').text
        self.assertIn('Bộ lọc không hợp lệ', hong)

    def test_keyword_and_pagination(self):
        self._login_portal()
        hit = self.url_open(f'/portal/return?q={self.mine.name}').text
        self.assertIn(self.mine.name, hit)
        miss = self.url_open('/portal/return?q=KHONGTONTAI999').text
        self.assertNotIn(self.mine.name, miss)
        # page_size là số hợp lệ và có trần — giá trị rác không được làm nổ trang.
        self.assertEqual(self.url_open('/portal/return?page_size=abc').status_code, 200)
        self.assertEqual(self.url_open('/portal/return?page=99999').status_code, 200)

    def test_send_from_portal_goes_through_action_submit(self):
        self._login_portal()
        line = self.order_ok.order_line[0]
        res = self.url_open('/portal/return/new', data={
            'franchise_id': self.franchise.id, 'sale_order_id': self.order_ok.id,
            'sale_order_line_id': line.id, 'issue_type_id': self.issue_type.id,
            'request_qty': '3', 'opening_datetime': '2026-09-01T08:00',
            'action': 'send', 'note': 'F1 send',
            'csrf_token': http.Request.csrf_token(self),
        }, files=[('images', (f'p{i}.jpg', JPEG, 'image/jpeg')) for i in range(MIN_IMAGES)],
            allow_redirects=False)
        rr = self.env['wujia.return.request'].search(
            [('note', '=', 'F1 send')], limit=1)
        self.assertTrue(rr, res.text[:500])
        self.assertEqual(rr.state, 'submitted')
        self.assertIn('Yêu cầu đã được gửi', ' '.join(rr.message_ids.mapped('body')))

    def test_endpoint_cannot_create_draft(self):
        self._login_portal()
        line = self.order_ok.order_line[0]
        Req = self.env['wujia.return.request']
        drafts = Req.search_count([('state', '=', 'draft')])
        base = {
            'franchise_id': self.franchise.id, 'sale_order_id': self.order_ok.id,
            'sale_order_line_id': line.id, 'issue_type_id': self.issue_type.id,
            'request_qty': '3', 'opening_datetime': '2026-09-01T08:00',
            'action': 'draft', 'csrf_token': http.Request.csrf_token(self),
        }
        self.url_open('/portal/return/new', data=dict(base, note='I2 one photo'),
                      files=[('images', ('p.jpg', JPEG, 'image/jpeg'))], allow_redirects=False)
        self.assertFalse(Req.search([('note', '=', 'I2 one photo')]))
        self.url_open('/portal/return/new', data=dict(base, note='I2 draft action'),
                      files=[('images', (f'p{i}.jpg', JPEG, 'image/jpeg')) for i in range(MIN_IMAGES)],
                      allow_redirects=False)
        self.assertEqual(Req.search([('note', '=', 'I2 draft action')]).mapped('state'), ['submitted'])
        self.assertEqual(Req.search_count([('state', '=', 'draft')]), drafts)

    def test_endpoint_rejects_undelivered_and_expired_orders(self):
        self._login_portal()
        Req = self.env['wujia.return.request']
        for order, msg in ((self.order_undelivered, 'chưa giao hoàn tất'), (self.order_expired, 'Đã quá 10 ngày')):
            res = self.url_open('/portal/return/new', data={
                'franchise_id': self.franchise.id, 'sale_order_id': order.id,
                'sale_order_line_id': order.order_line[0].id, 'issue_type_id': self.issue_type.id,
                'request_qty': '3', 'opening_datetime': '2026-09-01T08:00', 'note': f'I2 {order.id}',
                'csrf_token': http.Request.csrf_token(self),
            }, files=[('images', (f'p{i}.jpg', JPEG, 'image/jpeg')) for i in range(MIN_IMAGES)],
                allow_redirects=False)
            self.assertIn(msg, res.text)
            self.assertFalse(Req.search([('note', '=', f'I2 {order.id}')]))

    def test_form_has_only_submit_and_lists_delivered_orders(self):
        self._login_portal()
        body = self.url_open('/portal/return/new').text
        self.assertNotIn('value="draft"', body)
        self.assertNotIn('Lưu nháp', body)
        self.assertEqual(body.count('name="action" value="send"'), 2)
        for order in (self.order_ok, self.order_old):
            self.assertIn(order.name, body)
        for order in (self.order_undelivered, self.order_expired, self.order_draft):
            self.assertNotIn(order.name, body)
