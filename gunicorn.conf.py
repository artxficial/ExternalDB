import os
import sys

# Ensure Gunicorn can find your custom Filter class in the current directory
sys.path.append(os.getcwd())
# NOTE: Replace 'config_logging' with the actual name of your Python logging file
from core.logsplitter import NoiseFilter 

# Automatically ensure the logs directory exists at the server level
os.makedirs("logs", exist_ok=True)

# Tell Gunicorn to spin up its standard stream tracking
accesslog = "-"
errorlog = "-"
capture_output = True

# Pass your custom layout as Gunicorn's official logging configuration dictionary
logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "noise_filter": {
            "()": NoiseFilter
        }
    },
    "formatters": {
        "generic": {
            "format": "[%(asctime)s] %(message)s",
            "datefmt": "%m-%d %H:%M:%S"
        },
        "error": {
            "format": "[%(asctime)s] [ERROR] %(message)s",
            "datefmt": "%m-%d %H:%M:%S"
        }
    },
    "handlers": {
        "app_file": {
            "class": "logging.FileHandler",
            "filename": "logs/app.log",
            "formatter": "generic",
            "encoding": "utf-8",
            "filters": ["noise_filter"]
        },
        "access_file": {
            "class": "logging.FileHandler",
            "filename": "logs/access.log",
            "formatter": "generic",
            "encoding": "utf-8",
            "filters": ["noise_filter"]
        },
        "error_file": {
            "class": "logging.FileHandler",
            "filename": "logs/error.log",
            "formatter": "error",
            "encoding": "utf-8",
            "level": "ERROR",
            "filters": ["noise_filter"]
        }
    },
    "loggers": {
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["access_file"],
            "propagate": False
        },
        "gunicorn.error": {
            "level": "INFO",
            "handlers": ["error_file"],
            "propagate": False
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["app_file", "error_file"]
    }
}