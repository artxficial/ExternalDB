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

    # =========================
    # ACCESS LOG FILE
    # =========================
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

    access_file_handler.addFilter(AssetLogFilter())


    # =========================
    # GUNICORN ACCESS LOGGER
    # =========================
    access_logger = logging.getLogger("gunicorn.access")

    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False

    # remove only existing access handlers
    for handler in access_logger.handlers[:]:
        access_logger.removeHandler(handler)

    access_logger.addHandler(access_file_handler)


    # =========================
    # APP STDOUT/STDERR LOGGING
    # =========================
    app_log_file = open(
        APP_LOG_PATH,
        "a",
        encoding="utf-8"
    )

    sys.stdout = LogStreamSplitter(
        sys.__stdout__,
        app_log_file
    )

    sys.stderr = LogStreamSplitter(
        sys.__stderr__,
        app_log_file
    )