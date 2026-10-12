# -*- coding: utf-8 -*-
import logging
import os
from datetime import datetime
# pyrefly: ignore [missing-import]
from odoo.tools import config

class DailyFolderRotatingFileHandler(logging.Handler):
    def __init__(self, base_dir, filename_format='%Y-%m-%d.log'):
        super().__init__()
        self.base_dir = base_dir
        self.filename_format = filename_format
        self.current_date = None
        self.file_handler = None
        self._check_and_create_handler()

    def _check_and_create_handler(self):
        now = datetime.now()
        date_str = now.strftime('%Y-%m-%d')
        if self.current_date != date_str:
            self.current_date = date_str
            year = now.strftime('%Y')
            month = now.strftime('%m')
            log_dir = os.path.join(self.base_dir, year, month)
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f"{date_str}.log")
            
            if self.file_handler:
                self.file_handler.close()
                
            self.file_handler = logging.FileHandler(log_file, encoding='utf-8')
            if self.formatter:
                self.file_handler.setFormatter(self.formatter)

    def emit(self, record):
        try:
            self._check_and_create_handler()
            if self.file_handler:
                self.file_handler.formatter = self.formatter
                self.file_handler.emit(record)
        except Exception:
            self.handleError(record)

# Reconfigure logging to split logs by year/month/y-m-d.log
root_logger = logging.getLogger()
logfile = config.get('logfile')
if logfile:
    base_log_dir = os.path.dirname(logfile)
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.FileHandler) and handler.baseFilename == os.path.abspath(logfile):
            custom_handler = DailyFolderRotatingFileHandler(base_log_dir)
            custom_handler.setLevel(handler.level)
            if handler.formatter:
                custom_handler.setFormatter(handler.formatter)
            root_logger.removeHandler(handler)
            root_logger.addHandler(custom_handler)
            # logfile trong odoo.conf từ giờ trống — để lại đường dẫn thật, không thì
            # người debug mở đúng file cấu hình mà chẳng thấy log nào.
            with open(logfile, 'a', encoding='utf-8') as f:
                f.write(f"[wujia_core] logs moved to {base_log_dir}/<year>/<month>/"
                        f"<year-month-day>.log\n")
            break

from . import controllers
from . import models
