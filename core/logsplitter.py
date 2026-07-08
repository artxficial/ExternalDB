import sys
import os
import logging
import re
from datetime import datetime

# =========================
# FILE PATHS
# =========================
APP_LOG_PATH = "logs/app.log"
ACCESS_LOG_PATH = "logs/access.log"
ERROR_LOG_PATH = "logs/error.log"


# =========================
# ENVIRONMENT DETECTION
# =========================
def get_environment():
    """Detect if running in development or production."""
    env = os.environ.get("FLASK_ENV")
    if env:
        return env
    return "development" if os.path.exists(".env") else "production"


# =========================
# UNIVERSAL SPAM FILTER
# =========================
class NoiseFilter(logging.Filter):
    """
    Universal filter that removes noisy log entries.
    Works on the message content directly, not logger names.
    """
    
    SPAM_PATTERNS = [
        r"GET /static/",                       # Static files (CSS, JS, images)
        r"GET /livereload",                    # LiveReload dev server
        r"GET /favicon\.ico",                  # Browser favicon requests
        r"POST /externaldb/api/logs/stream",   # Log polling from dashboard
        r"GET /\?_=",                          # Bot referrer query spam
        r"HEAD /",                             # HEAD requests (health checks)
        r"304 GET /static/",                   # 304 cache responses for static
        r"206 GET /static/",                   # 206 partial content for videos
        r"101 GET /livereload",                # WebSocket upgrade for livereload
        r"Start watching changes",             # LiveReload startup
        r"Start detecting changes",            # LiveReload startup
        r"Browser Connected",                  # LiveReload browser connection
        r"Reload.*waiters",                    # LiveReload reload
        r"Ignore:",                            # LiveReload ignore patterns
        r"Using selector:",                    # Selector debug
        r"Serving on http://",                 # Server startup message
    ]

    def filter(self, record):
        """Returns True to keep, False to discard."""
        msg = record.getMessage()
        
        # Check if this matches any spam pattern
        for pattern in self.SPAM_PATTERNS:
            if re.search(pattern, msg):
                return False  # Block this log
        
        return True  # Allow this log


# =========================
# SMART STDOUT / STDERR LOGGER (Development Only)
# =========================
class SmartDevLogStreamSplitter:
    """
    Smart log splitter that:
    1. Doesn't capture logging framework output (avoid duplicates)
    2. Only captures genuine print() statements and warnings
    3. Applies filtering to what it captures
    """
    def __init__(self, terminal, log_file):
        self.terminal = terminal
        self.log_file = log_file
        self.noise_filter = NoiseFilter()
        # Track if we're inside a logging call to avoid duplication
        self._in_logging_call = False

    def write(self, message):
        if not message or not message.strip():
            self.terminal.write(message)
            return
        
        # Check if this is logging framework output (starts with standard log prefixes)
        # These should only go to terminal, not file (to avoid duplication)
        logging_prefixes = (
            "[I ",      # logging.INFO from livereload/werkzeug
            "[W ",      # logging.WARNING
            "[E ",      # logging.ERROR
            "[D ",      # logging.DEBUG
        )
        
        is_logging_output = message.lstrip().startswith(logging_prefixes)
        
        if is_logging_output:
            # This is from the logging framework - only write to terminal
            # The logging handlers will write to file
            self.terminal.write(message)
            return
        
        # This is genuine print() output or non-logging stderr
        # Check if it should be filtered
        should_filter = not self.noise_filter.filter(logging.LogRecord(
            name="stdout",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None
        ))
        
        if not should_filter:
            timestamp = datetime.now().strftime('%m-%d %H:%M:%S')
            formatted = f"[{timestamp}] {message.rstrip()}\n"
            self.log_file.write(formatted)
            self.log_file.flush()

        # Always write to terminal
        self.terminal.write(message)

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()


# =========================
# DEVELOPMENT LOGGING SETUP
# =========================
def init_logging_development():
    """
    Development mode: Captures all output, shows in console + files.
    Filters spam at multiple levels and prevents duplication.
    """
    os.makedirs("logs", exist_ok=True)

    # ===== APP LOG FILE (WITH FILTER) =====
    app_file_handler = logging.FileHandler(APP_LOG_PATH, encoding="utf-8")
    app_file_handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(message)s",
            datefmt="%m-%d %H:%M:%S"
        )
    )
    # Apply filter to handler
    app_file_handler.addFilter(NoiseFilter())

    # ===== ERROR LOG FILE (WITH FILTER) =====
    error_file_handler = logging.FileHandler(ERROR_LOG_PATH, encoding="utf-8")
    error_file_handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] [ERROR] %(message)s",
            datefmt="%m-%d %H:%M:%S"
        )
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.addFilter(NoiseFilter())

    # ===== ROOT LOGGER =====
    # This catches EVERYTHING from all libraries (Flask, Werkzeug, LiveReload, etc.)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove any existing handlers to start fresh
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    root_logger.addHandler(app_file_handler)
    root_logger.addHandler(error_file_handler)

    # ===== STDOUT/STDERR CAPTURE =====
    # Smart capture that avoids duplicating logging output
    app_log_file = open(APP_LOG_PATH, "a", encoding="utf-8")
    sys.stdout = SmartDevLogStreamSplitter(sys.__stdout__, app_log_file)
    sys.stderr = SmartDevLogStreamSplitter(sys.__stderr__, app_log_file)

    print("[LOGGING] Development mode initialized - filtering noise...")


# =========================
# PRODUCTION LOGGING SETUP
# =========================
def init_logging_production():
    """
    Production mode: Uses Gunicorn's logging infrastructure.
    Separates access logs, app logs, and error logs.
    """
    os.makedirs("logs", exist_ok=True)

    # ===== ACCESS LOG HANDLER =====
    access_file_handler = logging.FileHandler(ACCESS_LOG_PATH, encoding="utf-8")
    access_file_handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(message)s",
            datefmt="%m-%d %H:%M:%S"
        )
    )
    access_file_handler.addFilter(NoiseFilter())

    # ===== GUNICORN ACCESS LOGGER =====
    access_logger = logging.getLogger("gunicorn.access")
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False
    
    for handler in access_logger.handlers[:]:
        access_logger.removeHandler(handler)
    
    access_logger.addHandler(access_file_handler)

    # ===== APP LOG HANDLER =====
    app_file_handler = logging.FileHandler(APP_LOG_PATH, encoding="utf-8")
    app_file_handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(message)s",
            datefmt="%m-%d %H:%M:%S"
        )
    )
    app_file_handler.addFilter(NoiseFilter())

    # ===== ERROR LOG HANDLER =====
    error_file_handler = logging.FileHandler(ERROR_LOG_PATH, encoding="utf-8")
    error_file_handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] [ERROR] %(message)s",
            datefmt="%m-%d %H:%M:%S"
        )
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.addFilter(NoiseFilter())

    # ===== ROOT LOGGER =====
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    root_logger.addHandler(app_file_handler)
    root_logger.addHandler(error_file_handler)

    # ===== GUNICORN ERROR LOGGER =====
    error_logger = logging.getLogger("gunicorn.error")
    error_logger.setLevel(logging.ERROR)
    error_logger.addHandler(error_file_handler)


# =========================
# MAIN INIT FUNCTION
# =========================
def init_logging():
    """Universal logging initializer."""
    env = get_environment()

    if env == "development":
        init_logging_development()
    else:
        logging.getLogger("gunicorn.error").info("[LOGGING] Production configuration active via Gunicorn engine.")