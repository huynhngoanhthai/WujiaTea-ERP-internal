# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class WujiaFranchiseInspectionQuestion(models.Model):
    _name = 'wujia.franchise.inspection.question'
    _description = 'Inspection Question Library'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _rec_name = 'question_text'

    code = fields.Char(string='Question Code', tracking=True)
    question_text = fields.Text(
        string='Question Text',
        required=True,
        tracking=True,
        help='Question content. Use ____ to represent blanks to fill.'
    )
    score = fields.Float(string='Score', default=1.0, tracking=True, help='Score obtained when answering this question correctly.')
    
    # Mảng JSON lưu trữ mảng đáp án đúng tương ứng với các ô trống (Dùng default=False để tránh Odoo gọi list(self))
    correct_answers = fields.Json(
        string='Correct Answers (JSON)',
        default=False,
        help='JSON array containing answers for each blank ____. Example: [["500", "500ml"], ["10", "10 min"]]'
    )
    
    # Giao diện nhập liệu thân thiện cho người dùng
    correct_answers_text = fields.Text(
        string='Correct Answers (1 Line per Blank)',
        compute='_compute_correct_answers_text',
        inverse='_inverse_correct_answers_text',
        store=False,
        help='Nhập đáp án đúng cho từng chỗ trống ____.\n'
             '- Chỗ trống 1: Nhập ở Dòng 1.\n'
             '- Chỗ trống 2: Nhập ở Dòng 2.\n'
             '- Nếu 1 chỗ trống có nhiều đáp án chấp nhận được, phân cách nhau bằng dấu chấm phẩy (;).'
    )
    
    active = fields.Boolean(string='Active', default=True, tracking=True)

    @api.depends('code', 'question_text')
    def _compute_display_name(self):
        """Hàm tính toán tên hiển thị ngắn gọn cho bản ghi"""
        for rec in self:
            if rec.code and rec.question_text:
                short_text = rec.question_text[:40] + ('...' if len(rec.question_text) > 40 else '')
                rec.display_name = f"[{rec.code}] {short_text}"
            elif rec.question_text:
                rec.display_name = rec.question_text[:50]
            elif rec.code:
                rec.display_name = rec.code
            else:
                rec.display_name = _("New Question")

    @api.depends('correct_answers')
    def _compute_correct_answers_text(self):
        """
        Hàm tự động chuyển dữ liệu JSON từ correct_answers
        thành chuỗi văn bản nhiều dòng để hiển thị ra giao diện.
        """
        for rec in self:
            val = rec.correct_answers
            if isinstance(val, list):
                formatted_lines = []
                for item in val:
                    if isinstance(item, models.BaseModel):
                        continue
                    if isinstance(item, list):
                        clean_items = [
                            str(x) for x in item
                            if x is not None and not isinstance(x, models.BaseModel) and isinstance(x, (str, int, float))
                        ]
                        if clean_items:
                            formatted_lines.append('; '.join(clean_items))
                    elif isinstance(item, (str, int, float)) and item:
                        formatted_lines.append(str(item))
                rec.correct_answers_text = '\n'.join(formatted_lines)
            else:
                rec.correct_answers_text = False

    def _inverse_correct_answers_text(self):
        """
        Hàm xử lý khi người dùng nhập văn bản vào correct_answers_text trên giao diện:
        Phân tách từng dòng văn bản và lưu ngược lại vào trường correct_answers (JSON) trong CSDL.
        """
        for rec in self:
            if rec.correct_answers_text:
                result_list = []
                for line in rec.correct_answers_text.splitlines():
                    line_clean = line.strip()
                    if not line_clean:
                        continue
                    if ';' in line_clean:
                        parts = [p.strip() for p in line_clean.split(';') if p.strip()]
                        result_list.append(parts)
                    else:
                        result_list.append(line_clean)
                rec.correct_answers = result_list
            else:
                rec.correct_answers = False

    def action_save(self):
        """Lưu bản ghi câu hỏi"""
        self.ensure_one()
        return True


    @api.model
    def _init_default_questions(self):
        """Khởi tạo danh sách 15 câu hỏi kiểm tra mặc định từ DB nếu chưa tồn tại trong database."""
        default_questions = [
            {
                'code': '01',
                'question_text': 'Công thức pha chế món "Sữa Tươi Khoai Môn Nghiền" 50% đường, đá bình thường: Khoai môn nghiền _____ viên (_____gr), Khoai Môn Nghiền vá ( gr), sữa tươi 150ml, nước đường ____cc, đong trà Olong có đường ml trên ca định lượng.',
                'score': 1.0,
                'correct_answers': [['1.5', '1,5'], '120', '10'],
                'active': True,
            },
            {
                'code': '02',
                'question_text': 'Công thức pha chế món "Hồng Trà Kem Cheese" 50% đường, ít đá: Đong Hồng Trà có đường ____ml trên ca định lượng, đong Hồng trà không đường ____ml trên ca định lượng, cho đá đến vạch 450ml trên ly PP, kem chesse cho đến vạch ____ml trên lý PP',
                'score': 1.0,
                'correct_answers': ['250', '100', '600'],
                'active': True,
            },
            {
                'code': '03',
                'question_text': 'Công thức pha chế món "Olong Nho" 70% đường, ít đá: _____gr mứt nho, _____cc nước cốt nho, cho đá đến vạch 300, đong ____ml Olong có đường trên ca định lượng, đong _____ml Olong không đường.',
                'score': 1.0,
                'correct_answers': ['50', '30', '200', '100'],
                'active': True,
            },
            {
                'code': '04',
                'question_text': 'Công thức pha chế món "Olong Latte" + 1 phần Pudding Trứng Muối, size L, 50% đường, ít đá: Pudding Trứng Muối____ vá ( ____gr), sữa tươi 150ml, nước đường _____cc, đong trà Olong có đường ____ml trên ca định lượng, đong trà Olong không đường ____ml trên ca định lượng, đá đến vạch _______',
                'score': 1.0,
                'correct_answers': ['2', '120', '0', '250', '100', '800'],
                'active': True,
            },
            {
                'code': '05',
                'question_text': 'Công thức pha chế món "Trà Xí Muội Ngô Gia" size M, ít đá: Hạt é _____ vá (_____gr), Thạch Aiyu_____ vá (____gr), đá đến vạch 300, đong trà Xí Muội ____ml trên ca định lượng',
                'score': 1.0,
                'correct_answers': ['2', '60', '1', '40', '300'],
                'active': True,
            },
            {
                'code': '06',
                'question_text': 'Lượng sữa tươi trong thức uống "Sữa Tươi Trân Châu Đường Đen" nhiều đá size M là _____ml; size L là ______ml.',
                'score': 1.0,
                'correct_answers': ['200', '300'],
                'active': True,
            },
            {
                'code': '07',
                'question_text': 'Điền chính xác định lượng các loại topping sau: Trân Châu Vị Dâu ___vá (____gr),Khoai môn Nghiền ____viên (____gr), Trân Châu 3Q Trắng _____vá (____gr).',
                'score': 1.0,
                'correct_answers': ['2', '100', '1', '80', '1', '45'],
                'active': True,
            },
            {
                'code': '08',
                'question_text': 'Công thức pha chế món "Hồng Trà Bí Đao" size M, 70% đường, ít đá: Đong ____ml Trà Bí Đao trên ca định lượng, đong _____ml Hồng Trà có đường trên ca định lượng, đong ____ml Hồng Trà không đường trên ca định lượng, cho đá đến vạch ___trên ly PP.',
                'score': 1.0,
                'correct_answers': ['210', '70', '70', '600'],
                'active': True,
            },
            {
                'code': '09',
                'question_text': 'Sau khi cho Hạt é, nước lọc và nước đường vào khuấy đều, để yên ___ phút mới có thể sử dụng.',
                'score': 1.0,
                'correct_answers': ['2'],
                'active': True,
            },
            {
                'code': '10',
                'question_text': 'Hạn sử dụng của topping "Pudding Sương Sáo" đã khui là: ________',
                'score': 1.0,
                'correct_answers': [['Sử dụng ngay', 'dùng liền', 'dùng ngay']],
                'active': True,
            },
            {
                'code': '11',
                'question_text': 'Hạn sử dụng của "Kem chesse" thành phân là: _____ngày (tốt nhất ___tiếng)',
                'score': 1.0,
                'correct_answers': ['1', ['24', '24h', '24H']],
                'active': True,
            },
            {
                'code': '12',
                'question_text': 'Công thức nấu 150gr "Trân Châu Vị Dâu": Nước lọc_____ml, nước đường _____cc.',
                'score': 1.0,
                'correct_answers': ['2000', '25'],
                'active': True,
            },
            {
                'code': '13',
                'question_text': 'Công thức nâu 300gr "Khoai Dẻo Tam Sắc": Nước lọc _____ml, nước đường _______cc.',
                'score': 1.0,
                'correct_answers': ['2000', '30'],
                'active': True,
            },
            {
                'code': '14',
                'question_text': 'Công thức nâu 2000gr "Trân Châu Đường Đen": Nước lọc ____ml, nước đường ______cc, siro đường đen _____cc.',
                'score': 1.0,
                'correct_answers': ['5000', '220', '300'],
                'active': True,
            },
            {
                'code': '15',
                'question_text': 'Công thức nâu 500gr "Trân Châu Khoai Môn": Nước lọc _____ml, nước đường _____cc.',
                'score': 1.0,
                'correct_answers': ['2500', '75'],
                'active': True,
            },
        ]
        for q_data in default_questions:
            existing = self.with_context(active_test=False).search([('code', '=', q_data['code'])], limit=1)
            if not existing:
                self.create(q_data)
