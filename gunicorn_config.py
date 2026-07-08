import os
import sys
import logging

from core.logsplitter import init_logging, AssetLogFilter

# Server Architecture
workers = 5
bind = "127.0.0.1:8000"

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")

accesslog = os.path.join(LOG_DIR, "access.log")
errorlog = os.path.join(LOG_DIR, "gunicorn_error.log")

# Logging destinations
accesslog = "logs/access.log"
errorlog = "logs/gunicorn_error.log"
access_log_format = '[%{X-Forwarded-For}i] %(t)s "%(r)s" %(s)s'

# Native worker hook for your spam filter
def post_fork(server, worker):
    init_logging()
    
    gunicorn_access_logger = logging.getLogger("gunicorn.access")
    spam_filter = AssetLogFilter()
    
    for handler in gunicorn_access_logger.handlers:
        handler.addFilter(spam_filter)