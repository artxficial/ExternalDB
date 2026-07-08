import sys
import os
import logging
import re
from datetime import datetime


# =========================
# FILE PATHS
# =========================
APP_LOG_PATH = "logs/database_activity.log"
ACCESS_LOG_PATH = "logs/access.log"


# =========================
# STDOUT / STDERR LOGGER
# =========================
class LogStreamSplitter:
    def __init__(self, terminal, log_file):
        self.terminal = terminal
        self.log_file = log_file

    def write(self, message):
        if message and message.strip():
            timestamp = datetime.now().strftime('%m-%d %H:%M:%S')
            self.log_file.write(f"[{timestamp}] {message.rstrip()}\n")
            self.log_file.flush()

        self.terminal.write(message)

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()


# =========================
# ACCESS LOG FILTER (spam remover)
# =========================
class AssetLogFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()

        # Regular expressions to catch static files, health streams, and bot parameters
        spam_patterns = [
            r"GET /static/",
            r"GET /livereload",
            r"GET /favicon.ico",
            r"POST /externaldb/api/logs/stream",
            r"GET /\?_=",  # Sweeps out the bot referrer query spam (?_=swftkpp7)
        ]

        return not any(re.search(p, msg) for p in spam_patterns)


# =========================
# MAIN INIT FUNCTION
# =========================
def init_logging():
    os.makedirs("logs", exist_ok=True)

    # -------------------------
    # ACCESS LOGGERS
    # -------------------------
    access_loggers = [
        logging.getLogger("werkzeug"),
        logging.getLogger("gunicorn.access"),
        logging.getLogger("gunicorn.error"),
        logging.getLogger("uvicorn.access"),
        logging.getLogger("tornado.access"),
        logging.getLogger("tornado.application"),
    ]

    spam_filter = AssetLogFilter()

    # -------------------------
    # ACCESS FILE HANDLER
    # -------------------------
    access_file_handler = logging.FileHandler(
        ACCESS_LOG_PATH,
        encoding="utf-8"
    )

    access_file_handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(message)s",
            datefmt="%m-%d %H:%M:%S"
        )
    )

    access_file_handler.addFilter(spam_filter)


    # -------------------------
    # ACCESS CONSOLE HANDLER
    # -------------------------
    access_console_handler = logging.StreamHandler(sys.__stderr__)

    access_console_handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(message)s",
            datefmt="%m-%d %H:%M:%S"
        )
    )

    access_console_handler.addFilter(spam_filter)


    # -------------------------
    # APPLY ACCESS HANDLERS
    # -------------------------
    for logger in access_loggers:
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Allows logs to pass cleanly up to Gunicorn's parent listeners
        logger.propagate = True

        logger.addHandler(access_file_handler)
        logger.addHandler(access_console_handler)


    # -------------------------
    # APP LOGS
    # -------------------------
    app_log_file = open(
        APP_LOG_PATH,
        "a",
        encoding="utf-8"
    )

    # Fixed: Uses system base streams to prevent recursive lockups
    sys.stdout = LogStreamSplitter(
        sys.__stdout__,
        app_log_file
    )

    sys.stderr = LogStreamSplitter(
        sys.__stderr__,
        app_log_file
    )


# ==================================================
# GUNICORN HOOK (Injects filter into active workers)
# ==================================================
def gunicorn_post_fork(server, worker):
    """
    Gunicorn auto-discovers this function signature via the command line.
    It forces newly spawned workers to run init_logging and apply the spam filter.
    """
    init_logging()
    
    gunicorn_access_logger = logging.getLogger("gunicorn.access")
    spam_filter = AssetLogFilter()
    
    for handler in gunicorn_access_logger.handlers:
        handler.addFilter(spam_filter)