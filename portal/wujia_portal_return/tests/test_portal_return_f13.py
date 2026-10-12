"""F13 — portal đổi trả qua luật model: lọc 8 trạng thái, gửi phiếu một khối, phạm vi, nhãn Home một nguồn."""
from datetime import timedelta

from lxml import html

from odoo import fields, http
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_return.tests.common import JPEG, TEXT, ReturnFixture


@tagged('post_install', '-at_install', 'wujia_return_ct')
class TestPortalReturnF13(HttpCase, ReturnFixture):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_return_data()
        cls.user = cls.env['res.users'].create({
            'name': 'F13 owner', 'login': 'f13.owner', 'password': 'f13.owner',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.env['wujia.franchise.member'].create({
            'franchise_id': cls.franchise.id, 'user_id': cls.user.id, 'role': 'owner'})
        cls.reqs = {s: cls._request(state=s) for s in (
            'draft', 'submitted', 'reviewing', 'approved', 'done', 'rejected', 'cancelled')}
        partial = cls._request(state='approved', resolution_type='compensation', approved_qty=20.0,
                               approved_uom_id=cls.uom_kg.id)
        cls.env['wujia.compensation.allocation'].create({
            'request_id': partial.id, 'allocated_qty': 20.0, 'allocation_uom_id': cls.uom_kg.id,
            'delivered_qty': 5.0, 'state': 'partial'})
        partial.state = 'processing'
        cls.reqs['partial'] = partial
        cls.theirs = cls._request(franchise=cls.other, order=cls.order_other)

    def setUp(self):
        super().setUp()
        self.authenticate('f13.owner', 'f13.owner')

    def _post(self, n_images=3, image=JPEG, **kw):
        line = self.order_ok.order_line[0]
        data = {'franchise_id': self.franchise.id, 'sale_order_id': self.order_ok.id,
                'sale_order_line_id': line.id, 'issue_type_id': self.issue_type.id,
                'request_qty': '3', 'opening_datetime': '2026-09-01T08:00', 'action': 'send',
                'note': 'F13 portal', 'csrf_token': http.Request.csrf_token(self)}
        data.update(kw)
        return self.url_open('/portal/return/new', data=data, allow_redirects=False,
                             files=[('images', (f'p{i}.jpg', image, 'image/jpeg')) for i in range(n_images)])

    def test_filter_keys_follow_status_key(self):
        expect = {'draft': 'draft', 'submitted': 'submitted', 'processing': 'reviewing',
                  'approved': 'approved', 'partial': 'partial', 'done': 'done',
                  'rejected': 'rejected', 'cancelled': 'cancelled'}
        for key, owner in expect.items():
            body = self.url_open(f'/portal/return?state={key}&page_size=50').text
            for state, rr in self.reqs.items():
                (self.assertIn if state == owner else self.assertNotIn)(rr.name, body, f'{key}/{state}')

    def test_send_creates_submitted_request(self):
        res = self._post()
        rr = self.env['wujia.return.request'].search([('note', '=', 'F13 portal')])
        self.assertEqual(res.status_code, 303)
        self.assertTrue(res.headers['Location'].endswith(f'/portal/return/{rr.id}?message=created'))
        self.assertEqual((rr.state, len(rr.image_attachment_ids)), ('submitted', 3))

    def test_errors_render_form_and_create_nothing(self):
        cases = {
            'Cần tải từ 3 đến 5 ảnh minh chứng.': self._post(n_images=2),
            'Tệp không đúng định dạng hoặc vượt quá dung lượng cho phép.': self._post(image=TEXT),
            'Cửa hàng không truy cập được.': self._post(franchise_id=self.other.id),
            'Vui lòng chọn loại lỗi.': self._post(issue_type_id=''),
        }
        for msg, res in cases.items():
            self.assertEqual(res.status_code, 200, msg)
            self.assertIn(msg, res.text)
        self.assertFalse(self.env['wujia.return.request'].search([('note', '=', 'F13 portal')]))

    def test_other_store_is_out_of_scope(self):
        res = self.url_open(f'/portal/return/{self.theirs.id}')
        self.assertIn('Không tìm thấy yêu cầu hoặc bạn không có quyền truy cập', res.text)
        att = self.env['ir.attachment'].create({'name': 'x.jpg', 'res_model': self.theirs._name,
                                                'res_id': self.theirs.id, 'raw': JPEG})
        self.theirs.image_attachment_ids = [(4, att.id)]
        self.assertEqual(self.url_open(f'/portal/return/{self.theirs.id}/attachment/{att.id}').status_code, 404)
        self.assertNotIn(self.theirs.name, self.url_open('/portal/return').text)

    def test_home_uses_the_same_labels_as_the_list(self):
        """PC + mobile Home cùng bảng nhãn với /portal/return (trước F13 lệch 3 chữ)."""
        want = {'submitted': 'Đã gửi', 'reviewing': 'Đang xử lý', 'approved': 'Đã duyệt',
                'partial': 'Đang bù một phần'}
        for step, pair in enumerate((('reviewing', 'partial'), ('submitted', 'approved')), start=1):
            for state in pair:  # Home chỉ hiện HOME_PREVIEW_LIMIT phiếu mới nhất
                self.reqs[state].request_date = fields.Datetime.now() + timedelta(days=step)
            root = html.fromstring(self.url_open('/portal').text)
            for state in pair:
                rid = self.reqs[state].id
                badges = root.xpath(
                    f'//li[.//a[@href="/portal/return/{rid}"]]//span[contains(@class,"wj-status-badge")]'
                    f' | //a[@href="/portal/return/{rid}"]//span[contains(@class,"wj-status-badge")]')
                self.assertEqual(len(badges), 2, state)
                self.assertEqual({b.text_content().strip() for b in badges}, {want[state]}, state)
