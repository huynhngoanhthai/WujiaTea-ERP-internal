"""F13 — luật portal trên model: trạng thái hiển thị, phạm vi, minh chứng, tạo phiếu một khối."""
import base64

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .common import ReturnFixture, load_vi

MB = 1024 * 1024


@tagged('post_install', '-at_install', 'wujia_return')
class TestPortalRules(TransactionCase, ReturnFixture):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # J-V6: câu gốc là tiếng Anh ⇒ assert câu tiếng Việt chạy ở vi_VN.
        cls.env = load_vi(cls.env)
        cls._setup_return_data()
        cls.Req = cls.env['wujia.return.request']

    def _post(self, **kw):
        line = self.order_ok.order_line[0]
        post = {'franchise_id': str(self.franchise.id), 'sale_order_id': str(self.order_ok.id),
                'sale_order_line_id': str(line.id), 'issue_type_id': str(self.issue_type.id),
                'request_qty': '3', 'opening_datetime': '2026-09-01T08:00', 'note': 'F13 rule'}
        post.update(kw)
        return post

    def _attach(self, n):
        def attach(rr):
            atts = self.env['ir.attachment'].create([{
                'name': f'p{i}.jpg', 'res_model': rr._name, 'res_id': rr.id,
                'datas': base64.b64encode(b'x'), 'mimetype': 'image/jpeg'} for i in range(n)])
            rr.image_attachment_ids = [(4, a.id) for a in atts]
        return attach

    def test_status_key_merges_review_and_derives_partial(self):
        rr = self._request()
        expected = {'draft': 'draft', 'submitted': 'submitted', 'reviewing': 'processing',
                    'processing': 'processing', 'approved': 'approved', 'done': 'done',
                    'rejected': 'rejected', 'cancelled': 'cancelled'}
        for state, key in expected.items():
            rr.state = state
            self.assertEqual(rr._portal_status_key(), key, state)
        rr.write({'state': 'approved', 'resolution_type': 'compensation', 'approved_qty': 20.0,
                  'approved_uom_id': self.uom_kg.id})
        self.env['wujia.compensation.allocation'].create({
            'request_id': rr.id, 'allocated_qty': 20.0, 'allocation_uom_id': self.uom_kg.id,
            'delivered_qty': 5.0, 'state': 'partial'})
        rr.state = 'processing'
        self.assertEqual(rr._portal_status_key(), 'partial')

    def test_status_domain_matches_status_key(self):
        states = ('draft', 'submitted', 'reviewing', 'processing', 'approved', 'done', 'rejected', 'cancelled')
        reqs = self.Req.browse()
        for state in states:
            reqs |= self._request(state=state)
        for key in ('draft', 'submitted', 'processing', 'approved', 'partial', 'done', 'rejected', 'cancelled'):
            found = self.Req.search(self.Req._portal_scope_domain(self.franchise.ids)
                                    + self.Req._portal_status_domain(key))
            self.assertEqual(found, reqs.filtered(lambda r: r._portal_status_key() == key), key)
        self.assertEqual(self.Req._portal_status_domain('reviewing'), [])
        self.assertEqual(self.Req._portal_status_domain('rác'), [])

    def test_home_open_and_recent_domains(self):
        reqs = {s: self._request(state=s) for s in ('draft', 'submitted', 'reviewing', 'approved',
                                                    'rejected', 'cancelled')}
        other = self._request(franchise=self.other, order=self.order_other)
        open_ = self.Req.search(self.Req._portal_open_domain(self.franchise.ids))
        self.assertEqual(open_, reqs['submitted'] | reqs['approved'])
        recent = self.Req.search(self.Req._portal_recent_domain(self.franchise.ids))
        self.assertEqual(recent, reqs['draft'] | reqs['submitted'] | reqs['reviewing'] | reqs['approved'])
        self.assertNotIn(other, recent)

    def test_evidence_rules(self):
        check = self.Req._portal_check_evidence
        img = (MB, 'image/jpeg')
        check([img] * 3, [])
        for images, videos in (([img] * 2, []), ([img] * 6, []), ([img] * 3, [(MB, 'video/mp4')] * 2),
                               ([img] * 2 + [(MB, 'text/plain')], []), ([img] * 2 + [(6 * MB, 'image/png')], []),
                               ([img] * 3, [(11 * MB, 'video/mp4')]),
                               ([(int(4.9 * MB), 'image/png')] * 5, [(int(9.9 * MB), 'video/quicktime')])):
            with self.assertRaises(ValidationError):
                check(images, videos)

    def test_portal_never_creates_draft(self):
        before = self.Req.search_count([])
        for action in ('draft', 'send', None):
            post = self._post() if action is None else self._post(action=action)
            sent = self.Req.create_from_portal(post, self.franchise.ids,
                                               images=[(10, 'image/jpeg')] * 3, attach=self._attach(3))
            self.assertEqual(sent.state, 'submitted')
            self.assertEqual(sent.request_uom_id, self.uom_kg)
            self.assertIn('Yêu cầu đã được gửi', ' '.join(sent.message_ids.mapped('body')))
        self.assertEqual(self.Req.search_count([]), before + 3)
        with self.assertRaises(ValidationError):
            self.Req.create_from_portal(self._post(action='draft'), self.franchise.ids,
                                        images=[(10, 'image/jpeg')], attach=self._attach(1))
        self.assertEqual(self.Req.search_count([]), before + 3)

    def _post_order(self, order):
        return self._post(sale_order_id=str(order.id), sale_order_line_id=str(order.order_line[0].id))

    def test_window_counts_from_full_delivery(self):
        sent = self.Req.create_from_portal(self._post_order(self.order_old), self.franchise.ids,
                                           images=[(10, 'image/jpeg')] * 3, attach=self._attach(3))
        self.assertEqual(sent.sale_order_id, self.order_old)
        with self.assertRaises(ValidationError) as err:
            self.Req.create_from_portal(self._post_order(self.order_undelivered), self.franchise.ids,
                                        images=[(10, 'image/jpeg')] * 3)
        self.assertEqual(str(err.exception), 'Đơn hàng chưa giao hoàn tất, chưa thể tạo yêu cầu.')
        done = fields.Datetime.context_timestamp(self.Req, self.order_expired.wj_delivery_done_date)
        with self.assertRaises(ValidationError) as err:
            self.Req.create_from_portal(self._post_order(self.order_expired), self.franchise.ids,
                                        images=[(10, 'image/jpeg')] * 3)
        self.assertEqual(str(err.exception),
                         f"Đã quá 10 ngày kể từ khi đơn hàng giao hoàn tất ({done.strftime('%d/%m/%Y')}).")

    def test_rejects_input_the_client_can_tamper(self):
        cases = {
            'Cửa hàng không truy cập được.': self._post(franchise_id=str(self.other.id)),
            'Đơn hàng gốc không hợp lệ.': self._post(sale_order_id=str(self.order_other.id)),
            'Sản phẩm phải thuộc đơn hàng gốc của cửa hàng.': self._post(
                sale_order_line_id=str(self.order_other.order_line[0].id)),
            'Vui lòng chọn loại lỗi.': self._post(issue_type_id='abc'),
            'Số lượng yêu cầu phải lớn hơn 0.': self._post(request_qty='-1'),
            'Vui lòng nhập thời gian mở hàng hợp lệ.': self._post(opening_datetime='01/09/2026'),
        }
        for msg, post in cases.items():
            with self.assertRaises(ValidationError) as err:
                self.Req.create_from_portal(post, self.franchise.ids)
            self.assertEqual(str(err.exception), msg)

    def test_failed_submit_rolls_back_whole_request(self):
        # try/except thường: assertRaises tự bọc savepoint, sẽ che mất lỗi quên savepoint (bài học F8)
        before = self.Req.search_count([])
        try:
            self.Req.create_from_portal(self._post(action='send'), self.franchise.ids,
                                        images=[(10, 'image/jpeg')] * 3, attach=self._attach(2))
        except ValidationError as e:
            self.assertIn('ít nhất 3 ảnh', str(e))
        else:
            self.fail('thiếu ảnh mà vẫn gửi được')
        self.assertEqual(self.Req.search_count([]), before)
        self.assertFalse(self.env['ir.attachment'].search([('res_model', '=', self.Req._name),
                                                           ('name', '=like', 'p_.jpg')]))
