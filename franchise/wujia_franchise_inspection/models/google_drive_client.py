# -*- coding: utf-8 -*-
import base64
import io
import json
import logging
import os
import tempfile
import threading

_logger = logging.getLogger(__name__)

# Scopes for Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive.file']


class GoogleDriveClient:
    """
    Utility client for Google Drive API operations:
    - OAuth2 credentials loading and automatic token refresh
    - Managing folders (wujia media / <store_code>)
    - Uploading inspection media streams / files directly to Google Drive
    """

    _instance = None
    _lock = threading.Lock()

    def __init__(self, token_path=None, credentials_path=None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(base_dir, '..', 'data')
        self.token_path = token_path or os.path.join(data_dir, 'token.json')
        self.credentials_path = credentials_path or os.path.join(data_dir, 'credentials.json')
        self._service = None

    def _get_credentials(self):
        """Loads and refreshes OAuth2 credentials from token.json / credentials.json."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            _logger.error(
                "Google Drive API libraries are not installed. "
                "Please run: pip install google-api-python-client google-auth google-auth-oauthlib"
            )
            raise RuntimeError(
                "Thư viện Google Drive API chưa được cài đặt trên hệ thống (cần google-api-python-client, google-auth)."
            )

        creds = None
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except Exception as e:
                _logger.warning("Error reading token.json: %s", str(e))
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    with open(self.token_path, 'w', encoding='utf-8') as token_file:
                        token_file.write(creds.to_json())
                    _logger.info("Google Drive OAuth token refreshed successfully.")
                except Exception as e:
                    _logger.error("Failed to refresh Google Drive token: %s", str(e))
                    raise RuntimeError(f"Lỗi làm mới token Google Drive: {e}")
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Không tìm thấy file credentials.json tại: {self.credentials_path}"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
                with open(self.token_path, 'w', encoding='utf-8') as token_file:
                    token_file.write(creds.to_json())

        return creds

    def get_service(self):
        """Returns the Google Drive service instance (thread-safe build)."""
        from googleapiclient.discovery import build

        creds = self._get_credentials()
        return build('drive', 'v3', credentials=creds, cache_discovery=False)

    def get_or_create_folder(self, folder_name, parent_id=None):
        """Finds or creates a folder on Google Drive."""
        service = self.get_service()
        
        query_parts = [
            "mimeType = 'application/vnd.google-apps.folder'",
            f"name = '{folder_name}'",
            "trashed = false"
        ]
        if parent_id:
            query_parts.append(f"'{parent_id}' in parents")
        
        query = " and ".join(query_parts)
        results = service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()
        items = results.get('files', [])

        if items:
            folder_id = items[0]['id']
            _logger.info("Found existing Google Drive folder '%s' (ID: %s)", folder_name, folder_id)
            return folder_id

        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            folder_metadata['parents'] = [parent_id]

        folder = service.files().create(
            body=folder_metadata,
            fields='id'
        ).execute()
        folder_id = folder.get('id')
        _logger.info("Created new Google Drive folder '%s' (ID: %s)", folder_name, folder_id)
        return folder_id

    def upload_inspection_video(self, video_data, store_code, date_str, original_filename=None):
        """
        Uploads inspection video directly to Google Drive under: 'wujia media/<store_code>/ks<date_str>.mp4'
        Uses 20MB chunking without heavy video transcoding.
        """
        from googleapiclient.http import MediaFileUpload

        temp_files_to_clean = []

        try:
            # 1. Ghi file nguồn ra đĩa tạm (tránh ngậm 1GB trong RAM)
            if isinstance(video_data, str) and os.path.exists(video_data):
                source_path = video_data
            else:
                if isinstance(video_data, str):
                    raw_bytes = base64.b64decode(video_data)
                elif isinstance(video_data, bytes):
                    raw_bytes = video_data
                else:
                    raise ValueError("Invalid video data format.")

                tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                tmp_in.write(raw_bytes)
                tmp_in.flush()
                tmp_in.close()
                source_path = tmp_in.name
                temp_files_to_clean.append(source_path)

            service = self.get_service()

            # 2. Tìm hoặc tạo thư mục 'wujia media' và '<store_code>'
            root_folder_id = self.get_or_create_folder('wujia media')
            sanitized_store_code = (store_code or 'UNKNOWN').strip()
            store_folder_id = self.get_or_create_folder(sanitized_store_code, parent_id=root_folder_id)

            # 3. Xác định tên file đích trên Drive: ksYYYYMMDD.mp4
            file_ext = '.mp4'
            if original_filename and '.' in original_filename:
                ext = os.path.splitext(original_filename)[1].lower()
                if ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.3gp']:
                    file_ext = ext

            target_file_name = f"ks{date_str}{file_ext}"

            mime_type = 'video/mp4'
            if file_ext == '.mov':
                mime_type = 'video/quicktime'
            elif file_ext == '.webm':
                mime_type = 'video/webm'
            elif file_ext == '.avi':
                mime_type = 'video/x-msvideo'

            file_metadata = {
                'name': target_file_name,
                'parents': [store_folder_id]
            }

            # 4. Upload trực tiếp theo từng Chunk 20MB (nhanh, nhẹ, không tốn CPU)
            chunk_size = 20 * 1024 * 1024  # 20MB
            media = MediaFileUpload(
                source_path,
                mimetype=mime_type,
                chunksize=chunk_size,
                resumable=True
            )

            _logger.info("Đang upload trực tiếp '%s' lên Drive...", target_file_name)

            request = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink, webContentLink'
            )

            uploaded_file = None
            while uploaded_file is None:
                status, uploaded_file = request.next_chunk()
                if status:
                    _logger.info("Tiến độ upload '%s': %d%%", target_file_name, int(status.progress() * 100))

            file_id = uploaded_file.get('id')
            web_view_link = uploaded_file.get('webViewLink') or f"https://drive.google.com/file/d/{file_id}/view"
            web_content_link = uploaded_file.get('webContentLink')

            try:
                service.permissions().create(
                    fileId=file_id,
                    body={'type': 'anyone', 'role': 'reader'}
                ).execute()
            except Exception as perm_err:
                _logger.warning("Không thể cấp quyền public: %s", str(perm_err))

            _logger.info("Upload hoàn tất! ID: %s, Link: %s", file_id, web_view_link)

            return {
                'id': file_id,
                'name': target_file_name,
                'webViewLink': web_view_link,
                'webContentLink': web_content_link
            }

        finally:
            for temp_f in temp_files_to_clean:
                if os.path.exists(temp_f):
                    try:
                        os.remove(temp_f)
                    except Exception:
                        pass
