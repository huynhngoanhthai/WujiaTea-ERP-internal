"""K1 — form tạo + chi tiết Hỗ trợ: một cấu hình PC/mobile, nhãn gắn control, lỗi có aria.

WJ-SUPPORT-005 (#187) · WJ-SUPPORT-006 (#188) · WJ-SUPPORT-004 (#186). Chạy: `--test-tags wujia_support_k1`.
"""
from datetime import datetime

from lxml import html as lhtml

from odoo import http
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_base.controllers.portal import ACTIVE_FRANCHISE_COOKIE
from odoo.addons.wujia_support.tests.common import load_vi
from odoo.addons.wujia_support.tests.test_support import SupportCommon

SUPPORT_MODULES = ('wujia_portal_layout', 'wujia_portal_base', 'wujia_support', 'wujia_portal_support')
PC_FORM = '//div[contains(@class, "d-lg-block")]//form[@action="/portal/support/new"]'
M_FORM = '//div[contains(@class, "d-lg-none")]//form[@action="/portal/support/new"]'


def _clean(el):
    return ' '.join(el.text_content().split())


@tagged('post_install', '-at_install', 'wujia_support', 'wujia_support_k1')
class TestK1SupportForm(SupportCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_support()
        load_vi(cls.env, SUPPORT_MODULES)
        cls.owner.lang = 'vi_VN'

    def _doc(self, url):
        self.authenticate('f10.owner', 'f10.owner')
        self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(self.franchise.id))
        res = self.url_open(url, timeout=30, allow_redirects=False)
        self.assertEqual(res.status_code, 200)
        return lhtml.fromstring(res.text)

    def _forms(self, url='/portal/support/new'):
        doc = self._doc(url)
        pc, m = doc.xpath(PC_FORM), doc.xpath(M_FORM)
        self.assertEqual((len(pc), len(m)), (1, 1))
        return doc, pc[0], m[0]

    @staticmethod
    def _labels(form):
        return [_clean(el) for el in form.xpath('.//label[@for] | .//*[@id="wj-sup-m-priority-label"]')]

    @staticmethod
    def _priority(form):
        sel = form.xpath('.//select[@name="priority"]')
        if sel:
            opts = sel[0].xpath('./option')
            return [(o.get('value'), _clean(o), o.get('selected') is not None) for o in opts]
        return [(r.get('value'), _clean(r.getparent()), r.get('checked') is not None)
                for r in form.xpath('.//input[@name="priority"]')]

    def test_category_empty_required_on_both(self):
        _doc, pc, m = self._forms()
        for form in (pc, m):
            sel = form.xpath('.//select[@name="category_id"]')[0]
            first = sel.xpath('./option')[0]
            self.assertEqual(first.get('value'), '')
            self.assertEqual(_clean(first), 'Chọn loại yêu cầu')
            self.assertIsNotNone(first.get('selected'))
            self.assertIsNotNone(sel.get('required'))
            self.assertIsNotNone(form.get('data-wj-validate'))

    def test_priority_two_levels_same_on_both(self):
        _doc, pc, m = self._forms()
        expected = [('normal', 'Bình thường', True), ('urgent', 'Khẩn', False)]
        self.assertEqual(self._priority(pc), expected)
        self.assertEqual(self._priority(m), expected)
        group = m.xpath('.//*[@role="radiogroup"]')[0]
        self.assertEqual(group.get('aria-labelledby'), 'wj-sup-m-priority-label')

    def test_same_field_labels_on_both(self):
        _doc, pc, m = self._forms()
        common = ['Phân loại', 'Mức độ', 'Tiêu đề', 'Mô tả chi tiết', 'File đính kèm (tùy chọn)']
        self.assertEqual([x for x in self._labels(pc) if x != 'Cửa hàng'], common)
        self.assertEqual(sorted(self._labels(m)), sorted(common))

    def test_pc_controls_have_one_label_each(self):
        doc, pc, _m = self._forms()
        controls = pc.xpath('.//select | .//textarea | .//input[not(@type="hidden")]')
        self.assertEqual(len(controls), 6)
        ids = [c.get('id') for c in controls]
        self.assertTrue(all(ids))
        self.assertEqual(len(set(ids)), 6)
        for cid in ids:
            with self.subTest(control=cid):
                self.assertEqual(len(doc.xpath('//*[@id=$i]', i=cid)), 1)
                labels = doc.xpath('//label[@for=$i]', i=cid)
                self.assertEqual(len(labels), 1)
                self.assertTrue(_clean(labels[0]))
        names = [_clean(doc.xpath('//label[@for=$i]', i=cid)[0]) for cid in ids]
        self.assertEqual(len(set(names)), 6)

    def test_mobile_controls_labelled(self):
        doc, _pc, m = self._forms()
        for el in m.xpath('.//select | .//textarea | .//input[@type="text" or @type="file"]'):
            with self.subTest(control=el.get('name')):
                self.assertTrue(doc.xpath('//label[@for=$i]', i=el.get('id')))

    def test_error_slots_hidden_by_default(self):
        doc, pc, m = self._forms()
        for form in (pc, m):
            for el in form.xpath('.//*[@required]'):
                if el.get('type') == 'hidden':
                    continue
                with self.subTest(control=el.get('id')):
                    err = doc.xpath('//*[@id=$i]', i=el.get('id') + '-err')
                    self.assertEqual(len(err), 1)
                    self.assertIsNotNone(err[0].get('hidden'))
                    self.assertTrue(_clean(err[0]))
                    self.assertIsNone(el.get('aria-invalid'))
            self.assertFalse(form.xpath('.//*[@role="alert"][not(@data-wj-error-summary)]'))

    def test_server_error_marks_fields_on_both(self):
        cases = {
            'missing_fields': (['title', 'category_id'], 'Vui lòng điền đầy đủ thông tin bắt buộc.'),
            'invalid_input': (['category_id'], 'Dữ liệu gửi lên không hợp lệ.'),
            'invalid_attachment': (['attachments'], None),
        }
        for code, (fields, alert) in cases.items():
            doc, pc, m = self._forms('/portal/support/new?error=%s' % code)
            for form in (pc, m):
                with self.subTest(code=code, form=form.get('class')):
                    box = form.xpath('.//*[@role="alert"][not(@data-wj-error-summary)]')
                    self.assertEqual(len(box), 1)
                    if alert:
                        self.assertEqual(_clean(box[0]), alert)
                    bad = form.xpath('.//*[@aria-invalid="true"]')
                    self.assertEqual(sorted(b.get('name') for b in bad), sorted(fields))
                    for el in bad:
                        err = doc.xpath('//*[@id=$i]', i=el.get('aria-describedby'))
                        self.assertEqual(len(err), 1)
                        self.assertIsNone(err[0].get('hidden'))
                        self.assertTrue(_clean(err[0]))

    def test_unknown_error_code_ignored(self):
        _doc, pc, m = self._forms('/portal/support/new?error=<b>x</b>')
        for form in (pc, m):
            self.assertFalse(form.xpath('.//*[@role="alert"][not(@data-wj-error-summary)] | .//*[@aria-invalid]'))

    def _post(self, **data):
        self.authenticate('f10.owner', 'f10.owner')
        self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(self.franchise.id))
        payload = {'franchise_id': self.franchise.id, 'title': 'K1 post',
                   'csrf_token': http.Request.csrf_token(self)}
        payload.update(data)
        return self.url_open('/portal/support/new', data=payload, allow_redirects=False)

    def test_post_without_category_rejected(self):
        before = self.Ticket.search_count([('created_by_id', '=', self.owner.id)])
        res = self._post(category_id='')
        self.assertIn('data-wj-error="missing_fields"', res.text)
        self.assertEqual(self.Ticket.search_count([('created_by_id', '=', self.owner.id)]), before)

    def test_post_priority_values_kept(self):
        for value in ('normal', 'urgent'):
            with self.subTest(priority=value):
                self._post(category_id=self.cat.id, priority=value, title='K1 %s' % value)
                ticket = self.Ticket.search([('title', '=', 'K1 %s' % value)])
                self.assertEqual(ticket.priority, value)
                self.assertEqual(ticket.category_id, self.cat)


@tagged('post_install', '-at_install', 'wujia_support', 'wujia_support_k1')
class TestK1SupportDetail(SupportCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_support()
        load_vi(cls.env, SUPPORT_MODULES)
        cls.owner.lang = 'vi_VN'
        cls.owner.tz = 'Asia/Ho_Chi_Minh'
        cls.t_new = cls._ticket(title='K1 new')
        cls.t_done = cls._ticket(title='K1 done', priority='urgent', assigned_user_id=cls.hq.id)
        cls.t_done.write({'state': 'resolved'})
        cls.env.flush_all()
        cls.env.cr.execute(
            "UPDATE wujia_support_ticket SET create_date=%s, resolved_date=%s WHERE id=%s",
            (datetime(2026, 5, 27, 18, 30), datetime(2026, 5, 27, 18, 45), cls.t_done.id))
        cls.t_done.invalidate_recordset()

    def _meta(self, ticket, login='f10.owner'):
        self.authenticate(login, login)
        self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(self.franchise.id))
        res = self.url_open('/portal/support/%d' % ticket.id, timeout=30)
        self.assertEqual(res.status_code, 200)
        doc = lhtml.fromstring(res.text)
        pc = doc.xpath('//div[contains(@class, "d-lg-block")]//dl[contains(@class, "profile-dl")]')[0]
        pc_rows = [(_clean(dt), _clean(dt.getnext())) for dt in pc.xpath('./dt')]
        m = doc.xpath('//div[contains(@class, "wujia-mticket") and contains(@class, "d-lg-none")]')[0]
        m_rows = []
        for row in m.xpath('.//div[contains(@class, "wujia-mdash-row")]'):
            subs = row.xpath('.//span[contains(@class, "wujia-mdash-row-sub")]')
            m_rows.append((_clean(subs[0]), _clean(subs[1])))
        return pc_rows, m_rows

    def test_resolved_ticket_same_meta_on_both(self):
        pc, m = self._meta(self.t_done)
        self.assertEqual(pc[:2], [('Mã yêu cầu', self.t_done.name), ('Tiêu đề', 'K1 done')])
        self.assertEqual(pc[2:], m)
        self.assertEqual(m, [
            ('Phân loại', 'F10 cat active'),
            ('Mức độ', 'Khẩn'),
            ('Người gửi', 'f10 owner'),
            ('Ngày gửi', '28/05/2026 01:30'),
            ('Người xử lý', 'f10 hq'),
            ('Ngày giải quyết', '28/05/2026'),
        ])

    def test_store_row_removed(self):
        pc, m = self._meta(self.t_done)
        labels = [label for label, _v in pc + m]
        self.assertNotIn('Cửa hàng', labels)

    def test_empty_fields_use_clear_placeholders(self):
        pc, m = self._meta(self.t_new)
        self.assertEqual(pc[2:], m)
        values = dict(m)
        self.assertEqual(values['Người xử lý'], 'Chưa phân công')
        self.assertEqual(values['Ngày giải quyết'], 'Chưa giải quyết')

    def test_english_labels(self):
        self.owner.lang = 'en_US'
        pc, m = self._meta(self.t_new)
        self.assertEqual(pc[2:], m)
        self.assertEqual([label for label, _v in m],
                         ['Classification', 'Severity', 'Sender', 'Sent on', 'Assignee', 'Resolved on'])
        self.assertEqual(dict(m)['Assignee'], 'Not assigned yet')
