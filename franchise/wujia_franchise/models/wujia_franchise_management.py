import re

from odoo import _, api, fields, models
# pyrefly: ignore [missing-import]
from odoo.exceptions import ValidationError


EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')


class WujiaFranchiseManagement(models.Model):
    _name = 'wujia.franchise.management'
    _description = 'Wujia Franchise Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'
    _order = 'code, name'

    code = fields.Char(
        string='Store code',
        required=True,
        index=True,
        tracking=True,
        help='Franchise store code, e.g. H010 or HN-01.',
    )
    name = fields.Char(
        string='Store name',
        required=True,
        tracking=True,
        help='Display name, e.g. "[H010] 219 Vinh Vien store".',
    )
    display_name = fields.Char(compute='_compute_display_name', store=True)

    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        ondelete='restrict',
        index=True,
        tracking=True,
        help='Link to the res.partner representing the store — the transactional entity for '
             'sale.order, account.move, membership.',
    )

    opening_date = fields.Date(string='Opening date', tracking=True)
    address = fields.Text(string='Address', tracking=True)
    state_id = fields.Many2one(
        'res.country.state',
        string='Province',
        tracking=True,
    )
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')

    franchise_start_date = fields.Date(
        string='Franchise start date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    franchise_end_date = fields.Date(
        string='Franchise end date',
        tracking=True,
    )
    remaining_days = fields.Integer(
        string='Days remaining',
        compute='_compute_remaining_days',
        store=True,
    )
    is_expired = fields.Boolean(
        string='Contract expired',
        compute='_compute_remaining_days',
        store=True,
    )

    area_id = fields.Many2one(
        'res.area',
        string='Area',
        tracking=True,
        ondelete='restrict',
    )
    area_name = fields.Char(related='area_id.name', store=True, readonly=True)

    description = fields.Text(
        string='Operating description',
        help='Operating notes: delivery, loading bans, parking bans...',
    )
    note = fields.Text(string='Internal note')

    portal_locked = fields.Boolean(
        string='Portal locked',
        default=False,
        tracking=True,
        help='Block every portal access of this store (e.g. contract breach).',
    )
    invoiced = fields.Boolean(
        string='Invoiced',
        default=False,
        help='Flag tracking whether the related invoices have been issued.',
    )

    status = fields.Selection(
        [
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('locked', 'Locked'),
            ('closed', 'Closed'),
            ('expired', 'Expired'),
        ],
        string='Status',
        required=True,
        default='active',
        tracking=True,
    )

    member_ids = fields.One2many(
        'wujia.franchise.member',
        'franchise_id',
        string='Members',
    )
    member_count = fields.Integer(
        string='Member count',
        compute='_compute_member_count',
    )
    main_owner_member_id = fields.Many2one(
        'wujia.franchise.member',
        string='Primary owner',
        compute='_compute_main_owner_member',
        help='The active member with role=owner for this store (BA spec).',
    )

    supervision_user_id = fields.Many2one(
        'res.users',
        string='Supervisor',
        tracking=True,
    )

    document_ids = fields.One2many(
        'wujia.franchise.document',
        'franchise_id',
        string='Documents',
        copy=False,
    )
    google_map_url = fields.Char(string='Google Map URL')

    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        'UNIQUE (code)',
        'Store code must be unique.',
    )

    # ===========================================================
    # Compute / depends
    # ===========================================================
    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            if rec.code and rec.name:
                rec.display_name = f'[{rec.code}] {rec.name}'
            else:
                rec.display_name = rec.name or rec.code or _('New Franchise')

    @api.depends('franchise_end_date')
    def _compute_remaining_days(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.franchise_end_date:
                delta = (rec.franchise_end_date - today).days
                rec.remaining_days = delta
                rec.is_expired = delta < 0
            else:
                rec.remaining_days = 0
                rec.is_expired = False

    @api.depends('member_ids.is_currently_valid', 'member_ids.active', 'member_ids.is_working')
    def _compute_member_count(self):
        for rec in self:
            rec.member_count = len(
                rec.member_ids.filtered(lambda m: m.active and m.is_working)
            )

    @api.depends('member_ids.role', 'member_ids.is_currently_valid')
    def _compute_main_owner_member(self):
        for rec in self:
            owner = rec.member_ids.filtered(
                lambda m: m.role == 'owner' and m.is_currently_valid
            )[:1]
            rec.main_owner_member_id = owner

    # ===========================================================
    # Constraints
    # ===========================================================
    @api.constrains('franchise_start_date', 'franchise_end_date')
    def _check_franchise_dates(self):
        for rec in self:
            if (rec.franchise_end_date and rec.franchise_start_date
                    and rec.franchise_end_date < rec.franchise_start_date):
                raise ValidationError(_(
                    "Franchise end date must be >= start date."
                ))

    @api.constrains('email')
    def _check_email_format(self):
        for rec in self:
            if rec.email and not EMAIL_RE.match(rec.email):
                raise ValidationError(_("Email '%s' is invalid.", rec.email))

    @api.constrains('status', 'partner_id')
    def _check_partner_required_when_active(self):
        for rec in self:
            if rec.status == 'active' and not rec.partner_id:
                raise ValidationError(_(
                    "Active store '%s' must have an associated Partner for sales orders/invoicing.", rec.display_name,
                ))

    # ===========================================================
    # Onchange / Actions
    # ===========================================================
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.name = self.name or self.partner_id.name
            self.phone = self.phone or self.partner_id.phone
            self.email = self.email or self.partner_id.email
            self.state_id = self.state_id or self.partner_id.state_id

    def action_view_members(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Members of %s', self.display_name),
            'res_model': 'wujia.franchise.member',
            'view_mode': 'list,form',
            'domain': [('franchise_id', '=', self.id)],
            'context': {'default_franchise_id': self.id},
        }

    def action_set_active(self):
        for rec in self:
            rec.status = 'active'
            rec.portal_locked = False

    def action_lock_portal(self):
        for rec in self:
            rec.status = 'locked'
            rec.portal_locked = True

    def action_close(self):
        for rec in self:
            rec.status = 'closed'
            rec.portal_locked = True

    @api.model
    def _cron_check_expired(self):
        """Cảnh báo HQ ngày hợp đồng vừa hết hạn — KHÔNG đụng status/portal_locked (WJ-FRANCHISE-004)."""
        just_expired = self.search([
            ('franchise_end_date', '=', fields.Date.subtract(fields.Date.context_today(self), days=1)),
            ('status', 'not in', ['expired', 'closed']),
            ('active', '=', True),
        ])
        for rec in just_expired:
            rec.message_post(body=_(
                "Franchise contract of store %(store)s expired on %(date)s. "
                "The store is NOT locked — renew the contract to keep the records tidy.",
                store=rec.display_name, date=rec.franchise_end_date,
            ))
        return len(just_expired)



    @api.model
    def _bootstrap_franchise_data(self):
        """Tự động nạp dữ liệu từ các file CSV chuẩn trong data/ khi cài đặt hoặc upgrade module."""
        import os
        import csv
        import datetime
        from odoo import fields

        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')

        # 1. Nạp Khu vực (res.area.csv)
        area_csv = os.path.join(data_dir, 'res.area.csv')
        if os.path.exists(area_csv) and self.env['res.area'].search_count([]) < 100:
            try:
                Area = self.env['res.area']
                with open(area_csv, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        code = row.get('code', '').strip()
                        name = row.get('name', '').strip()
                        seq = int(row['sequence']) if row.get('sequence') and row['sequence'].isdigit() else 10
                        desc = row.get('description', '')
                        if not Area.search(['|', ('code', '=', code), ('name', '=', name)], limit=1):
                            Area.create({
                                'code': code,
                                'name': name,
                                'sequence': seq,
                                'description': desc,
                                'active': True,
                            })
            except Exception as e:
                print(f"[BOOTSTRAP CSV] Lỗi nạp res.area.csv: {e}")

        # 2. Nạp Cửa hàng nhượng quyền & Partner (wujia.franchise.management.csv)
        franchise_csv = os.path.join(data_dir, 'wujia.franchise.management.csv')
        partner_csv = os.path.join(data_dir, 'res.partner.franchise.csv')
        if os.path.exists(franchise_csv) and self.search_count([]) < 100:
            try:
                Partner = self.env['res.partner']
                Area = self.env['res.area']
                
                # Nạp partner trước
                partner_map = {}
                if os.path.exists(partner_csv):
                    with open(partner_csv, mode='r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            name = row.get('name', '').strip()
                            phone = row.get('phone', '').strip()
                            street = row.get('street', '').strip()
                            p = Partner.search([('name', '=', name)], limit=1)
                            if not p:
                                p = Partner.create({
                                    'name': name,
                                    'is_franchise': True,
                                    'phone': phone,
                                    'street': street,
                                })
                            partner_map[row.get('id', '').strip()] = p.id

                # Nạp franchise
                with open(franchise_csv, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        code = row.get('code', '').strip()
                        name = row.get('name', '').strip()
                        p_ext_id = row.get('partner_id/id', '').replace('wujia_franchise.', '').strip()
                        partner_id = partner_map.get(p_ext_id, False)
                        if not partner_id:
                            p = Partner.search([('name', '=', name)], limit=1)
                            partner_id = p.id if p else False

                        start_str = row.get('franchise_start_date', '').strip() or None
                        end_str = row.get('franchise_end_date', '').strip() or None

                        f_rec = self.with_context(active_test=False).search([('code', '=', code)], limit=1)
                        vals = {
                            'code': code,
                            'name': name,
                            'partner_id': partner_id,
                            'phone': row.get('phone', '').strip(),
                            'address': row.get('address', '').strip(),
                            'status': row.get('status', 'active').strip() or 'active',
                            'portal_locked': bool(int(row.get('portal_locked', '0'))),
                            'invoiced': bool(int(row.get('invoiced', '0'))),
                            'description': row.get('description', ''),
                        }
                        contracts_on = 'wujia.franchise.contract' in self.env
                        if not contracts_on:
                            vals['franchise_start_date'] = start_str or fields.Date.today()
                            vals['franchise_end_date'] = end_str or None
                        if not f_rec:
                            f_rec = self.create(vals)
                        else:
                            f_rec.write(vals)
                        if contracts_on:
                            f_rec._wj_ensure_contract(start_str or fields.Date.today(), end_str or None)
            except Exception as e:
                print(f"[BOOTSTRAP CSV] Lỗi nạp wujia.franchise.management.csv: {e}")

        # 3. Nạp Nhân viên cửa hàng từ employee.csv và liên kết vào wujia.franchise.member theo franchise_code
        emp_csv = os.path.join(data_dir, 'employee.csv')
        if os.path.exists(emp_csv):
            try:
                portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)
                Member = self.env['wujia.franchise.member']
                Franchise = self.env['wujia.franchise.management']

                # Lấy bản đồ franchise_code -> franchise_id
                all_franchises = Franchise.with_context(active_test=False).search([])
                f_map = {f.code.strip(): f.id for f in all_franchises if f.code}

                # Đọc danh sách nhân viên từ employee.csv
                rows = []
                unique_users = {}
                with open(emp_csv, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        phone = r.get('phone', '').strip()
                        name = r.get('employee_name', '').strip()
                        if phone:
                            if phone not in unique_users:
                                unique_users[phone] = name or phone
                            rows.append(r)

                # Tạo partner & user nếu chưa có
                existing_users = {}
                if unique_users:
                    self.env.cr.execute("SELECT login, id FROM res_users WHERE login IN %s", (tuple(unique_users.keys()),))
                    for login, uid in self.env.cr.fetchall():
                        existing_users[login] = uid

                    to_create = [(phone, name) for phone, name in unique_users.items() if phone not in existing_users]
                    for phone, name in to_create:
                        self.env.cr.execute("""
                            INSERT INTO res_partner (name, phone, active, is_company, partner_share, lang, create_date, write_date)
                            VALUES (%s, %s, TRUE, FALSE, TRUE, 'vi_VN', NOW(), NOW())
                            RETURNING id
                        """, (name, phone))
                        partner_id = self.env.cr.fetchone()[0]

                        self.env.cr.execute("""
                            INSERT INTO res_users (login, partner_id, active, share, notification_type, company_id, create_date, write_date)
                            VALUES (%s, %s, TRUE, TRUE, 'email', 1, NOW(), NOW())
                            RETURNING id
                        """, (phone, partner_id))
                        user_id = self.env.cr.fetchone()[0]

                        if portal_group:
                            self.env.cr.execute("""
                                INSERT INTO res_groups_users_rel (gid, uid) VALUES (%s, %s) ON CONFLICT DO NOTHING
                            """, (portal_group.id, user_id))

                        self.env.cr.execute("""
                            INSERT INTO res_company_users_rel (cid, user_id) VALUES (1, %s) ON CONFLICT DO NOTHING
                        """, (user_id,))
                        existing_users[phone] = user_id

                # Tạo thành viên cửa hàng (wujia.franchise.member)
                if Member.search_count([]) < 100:
                    created_pairs = set()
                    self.env.cr.execute("SELECT user_id, franchise_id FROM wujia_franchise_member")
                    for uid, fid in self.env.cr.fetchall():
                        created_pairs.add((uid, fid))

                    for r in rows:
                        phone = r.get('phone', '').strip()
                        f_code = r.get('franchise_code', '').strip()
                        user_id = existing_users.get(phone)
                        franchise_id = f_map.get(f_code)

                        if user_id and franchise_id and (user_id, franchise_id) not in created_pairs:
                            job = r.get('job_position', '').strip().lower()
                            if 'chủ' in job or 'owner' in job:
                                role = 'owner'
                            elif 'quản' in job or 'manager' in job:
                                role = 'manager'
                            else:
                                role = 'staff'

                            is_pass = (r.get('result', '').strip().lower() == 'passed')
                            exam_date_str = r.get('exam_date', '').strip()
                            try:
                                date_from = datetime.datetime.strptime(exam_date_str, '%Y-%m-%d').date()
                            except Exception:
                                date_from = fields.Date.today()

                            self.env.cr.execute("""
                                INSERT INTO wujia_franchise_member (
                                    user_id, franchise_id, role, is_pass, is_working, active, date_from, create_date, write_date
                                ) VALUES (
                                    %s, %s, %s, %s, TRUE, TRUE, %s, NOW(), NOW()
                                )
                            """, (user_id, franchise_id, role, is_pass, date_from))
                            created_pairs.add((user_id, franchise_id))

            except Exception as e:
                print(f"[BOOTSTRAP] Lỗi nạp employee.csv: {e}")


class WujiaFranchiseDocument(models.Model):
    _name = 'wujia.franchise.document'
    _description = 'Franchise Store Document'
    _order = 'create_date desc, id desc'

    franchise_id = fields.Many2one(
        'wujia.franchise.management',
        string='Franchise Store',
        required=True,
        ondelete='cascade',
    )
    name = fields.Char(
        string='Document Name',
    )
    file = fields.Binary(
        string='Download',
        required=True,
        attachment=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') and vals.get('file'):
                vals['name'] = _('Document')
        return super().create(vals_list)
