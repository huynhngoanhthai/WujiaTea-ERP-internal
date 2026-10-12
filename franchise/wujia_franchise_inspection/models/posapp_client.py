from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import logging
import threading
import requests

_logger = logging.getLogger(__name__)

class PosAppClient:
    """
    Client for interacting with the PosApp Admin and Manage APIs.
    This class is a utility class and does not link to the database.
    """

    def __init__(self, token=None, session_cookie=None, base_url="https://admin-api.posapp.vn"):
        """
        Initialize the PosApp Client.
        :param token: The API token for authentication.
        :param session_cookie: The value of the posapp_session cookie.
        :param base_url: The base URL of the PosApp API.
        """
        self.base_url = base_url.rstrip('/')
        self.token = token or 'f48e656477b064b12575'
        self.session_cookie = session_cookie or 'eF2We3YQdG6SQRHCmf51zsUBG8mB8UCOSBQT1XVn'
        
        self._account_id = None
        self._shops = []
        self.data_groups = []  # Dữ liệu được nhóm lại: [{"date": "YYYY-MM", "count_receipt": int, "count_amount": float, "count_amount_app": float}]
        self._lock = threading.Lock()  # Khóa bảo vệ ghi dữ liệu đồng thời từ nhiều luồng

        self.session = requests.Session()
        if self.session_cookie:
            self.session.headers.update({
                'Cookie': f'posapp_session={self.session_cookie}'
            })

    def set_data_group_by_date(self):
        with self._lock:
            self.data_groups = []

    def get_orders_by_payment_status(self, date_start, date_end, shop_code, page=1, limit=2000, payment_status=3):
        """
        Retrieve orders from PosApp by payment status and group statistics by month.
        
        :param date_start: Start date in YYYY-MM-DD format.
        :param date_end: End date in YYYY-MM-DD format.
        :param shop_code: Shop code/name prefix (e.g. 'H004').
        :param page: Page number (default: 1).
        :param limit: Number of records per page (default: 2000).
        :param payment_status: Payment status filter (default: -1).
        :return: Dict containing orders and data_groups.
        """
        if not self._shops or not self._account_id:
            with self._lock:
                if not self._shops or not self._account_id:
                    self.system_login()

        url = f"{self.base_url}/api/getOrdersByPaymentStatus"
        shop_id = ""
        token = ""
        
        for shop in self._shops:
            if shop.get('shop_name') == shop_code:
                shop_id = shop.get('shop_id')
                token = shop.get('token')
                break
        
        if not shop_id:
            _logger.warning("Shop code '%s' not found in account shops: %s", shop_code, self._shops)
        
        payload = {
            'date_start': str(date_start),
            'date_end': str(date_end),
            'account_id': str(self._account_id or ''),
            'shop_id': str(shop_id),
            'page': str(page),
            'limit': str(limit),
            'token': token or self.token,
            'payment_status': str(payment_status),
            'filter_manage': '{"filter_type":11,"data":[{"key":"status","key_text":"Trạng thái","operator":{"key":"is","value":"Là"},"value":[15431],"dynamic_date_type":null,"value_as_text":"Hoàn thành","to_string":"Trạng thái là Hoàn thành"}],"keyword":"","sort_by":1}'
        }
        
        try:
            _logger.info("Sending POST request to PosApp API: %s with payload: %s", url, payload)
            response = self.session.post(url, data=payload, timeout=30)
            response.raise_for_status()
            
            try:
                json_data = response.json()
                data = json_data.get('data') or {}
                orders = data.get('orders') or {}
                orders_data = orders.get('data') if isinstance(orders, dict) else []
                if not isinstance(orders_data, list):
                    orders_data = []

                date_obj = datetime.strptime(date_end, "%Y-%m-%d")
                date_key = date_obj.strftime("%Y-%m")
                count_receipt = 0
                total_amount = 0
                total_amount_app = 0
                count_amount_mini_app = 0

                list_channel_ids = [3,54,2,15] #  app-grad (3,54) mini app (2) Shopee Food (15)
                channel_id_mini_app = 2

                for order in orders_data:
                    count_receipt += 1
                    total_val = float(order.get('total', 0) or 0)
                    total_amount += total_val
                    code = str(order.get('code', ''))
                    channel_id = order.get('channel_id', '')
                    if channel_id in list_channel_ids:
                        total_amount_app += total_val
                    if channel_id == channel_id_mini_app:
                        count_amount_mini_app += 1
                # Ghi vào data_groups với Lock để đảm bảo thread-safe
                with self._lock:
                    found_date = False
                    for item in self.data_groups:
                        if item.get('date') == date_key:
                            item['count_receipt'] += count_receipt
                            item['total_amount'] += total_amount
                            item['total_amount_app'] += total_amount_app
                            item['count_amount_mini_app'] += count_amount_mini_app
                            found_date = True
                            break
                    
                    if not found_date:
                        self.data_groups.append({
                            'date': date_key,
                            'count_receipt': count_receipt,
                            'total_amount': total_amount,
                            'total_amount_app': total_amount_app,
                            'count_amount_mini_app': count_amount_mini_app
                        })

                # Đệ quy lấy các trang tiếp theo nếu có
                if isinstance(orders, dict):
                    current_page = int(orders.get('current_page', 1) or 1)
                    last_page = int(orders.get('last_page', 1) or 1)
                    if current_page < last_page:
                        self.get_orders_by_payment_status(date_start, date_end, shop_code, current_page + 1, limit, payment_status)
                
                return {
                    "success": True,
                    "orders": orders_data,
                    "data_groups": self.data_groups
                }
            except ValueError:
                _logger.warning("PosApp API response is not a valid JSON: %s", response.text)
                return {
                    'success': False,
                    'error': 'Invalid JSON response',
                    'raw_response': response.text
                }
                
        except requests.exceptions.RequestException as e:
            _logger.error("Failed to connect to PosApp API: %s", e)
            return {
                'success': False,
                'error': str(e)
            }

    def get_orders_by_date_ranges(self, date_ranges, shop_code, max_workers=5, limit=2000):
        """
        Lấy dữ liệu đơn hàng cho nhiều khoảng thời gian (chạy song song đa luồng).
        
        :param date_ranges: Danh sách các tuple khoảng ngày [('YYYY-MM-01', 'YYYY-MM-31'), ...]
        :param shop_code: Mã cửa hàng (vd: 'H004')
        :param max_workers: Số luồng chạy song song tối đa (mặc định: 5)
        :param limit: Giới hạn số đơn / trang (mặc định: 2000)
        :param payment_status: Trạng thái thanh toán (mặc định: -1)
        :return: Danh sách data_groups đã gom nhóm và sắp xếp theo ngày
        """
        if not self._shops or not self._account_id:
            self.system_login()

        with ThreadPoolExecutor(max_workers=min(max_workers, len(date_ranges) or 1)) as executor:
            futures = [
                executor.submit(
                    self.get_orders_by_payment_status,
                    date_start=d_start,
                    date_end=d_end,
                    shop_code=shop_code,
                    page=1,
                    limit=limit,
                )
                for d_start, d_end in date_ranges
            ]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    _logger.error("Lỗi trong luồng tải đơn hàng: %s", e)

        with self._lock:
            self.data_groups.sort(key=lambda x: x.get('date', ''))

        return self.data_groups

    def system_login(self, user="vanhanhhtng", password="HtNg@2026", jwt_token=None):
        """
        Authenticate with the PosApp Manage system login API.
        
        :param user: Username (default: "vanhanhhtng").
        :param password: Password (default: "HtNg@2026").
        :param jwt_token: Optional jwt_token cookie value.
        :return: JSON response or dict containing the response details.
        """
        url = "https://manage-api.posapp.vn/api/system/login"
        
        headers = {
            'Content-Type': 'application/json',
        }
        
        token = jwt_token or '597052%7CaJV9tnAlCqPcrftGUwvyYRhPBsIPRS5V92lvrwMK6989d442'
        if token:
            headers['Cookie'] = f'jwt_token={token}'
            
        payload = {
            'user': user,
            'pass': password
        }
        
        try:
            _logger.info("Sending POST request to PosApp Login API: %s", url)
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            try:
                json_data = response.json()
                data = json_data.get('data') or {}
                self._account_id = data.get('id')
                
                self._shops = [
                    {
                        "shop_id": shop.get('shop_id'),
                        "shop_name": (shop.get('shop_name') or '')[0:4],
                        "token": shop.get('token')
                    }
                    for shop in data.get('account_shops', [])
                ]
                return {
                    "account_id": self._account_id,
                }

            except ValueError:
                _logger.warning("PosApp Login API response is not a valid JSON: %s", response.text)
                return {
                    'success': False,
                    'error': 'Invalid JSON response',
                    'raw_response': response.text
                }
                
        except requests.exceptions.RequestException as e:
            _logger.error("Failed to connect to PosApp Login API: %s", e)
            return {
                'success': False,
                'error': str(e)
            }
