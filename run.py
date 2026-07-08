# run.py
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
# OPTIONAL but recommended: make ROOT import-safe everywhere
sys.path.insert(0, ROOT)

import core.logsplitter
core.logsplitter.init_logging()

from web_app import create_app

app = create_app()

app.config['TEMPLATES_AUTO_RELOAD'] = True


if __name__ == "__main__":
    from livereload import Server

    server = Server(app.wsgi_app)

    server.watch("web_app/templates/")
    server.watch("web_app/static/")

    print("Starting LiveReload development server on port 5000...")

    server.serve(port=5000)