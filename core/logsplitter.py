import sys
import os
import logging
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

        spam_keywords = [
            "GET /static/",
            "GET /livereload",
            "GET /favicon.ico",
            "POST /externaldb/api/logs/stream",
        ]

        return not any(k in msg for k in spam_keywords)


# =========================
# MAIN INIT FUNCTION
# =========================
def init_logging():
    os.makedirs("logs", exist_ok=True)

    # -------------------------
    # 1. RESET ROOT LOGGING
    # -------------------------
    logging.getLogger().handlers.clear()

    # -------------------------
    # 2. ACCESS LOGGERS (HTTP)
    # -------------------------
    access_loggers = [
        logging.getLogger("werkzeug"),
        logging.getLogger("tornado.access"),
        logging.getLogger("tornado.application"),
    ]

    spam_filter = AssetLogFilter()

    # ---- ACCESS FILE LOG ----
    access_file_handler = logging.FileHandler(
        ACCESS_LOG_PATH,
        encoding="utf-8"
    )
    access_file_handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(message)s", datefmt="%m-%d %H:%M:%S")
    )
    access_file_handler.addFilter(spam_filter)

    # ---- ACCESS CONSOLE LOG ----
    access_console_handler = logging.StreamHandler(sys.__stderr__)
    access_console_handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(message)s", datefmt="%m-%d %H:%M:%S")
    )
    access_console_handler.addFilter(spam_filter)

    # ---- APPLY TO ALL ACCESS LOGGERS ----
    for logger in access_loggers:
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        logger.propagate = False

        logger.addHandler(access_file_handler)
        logger.addHandler(access_console_handler)

    # -------------------------
    # 3. APP LOGS (print + errors)
    # -------------------------
    app_log_file = open(APP_LOG_PATH, "a", encoding="utf-8")

    sys.stdout = LogStreamSplitter(sys.stdout, app_log_file)
    sys.stderr = LogStreamSplitter(sys.stderr, app_log_file)