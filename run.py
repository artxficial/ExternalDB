import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import core.logsplitter

# Determine if we are in production or local development
ENV = os.environ.get("FLASK_ENV") or ("development" if os.path.exists(".env") else "production")

core.logsplitter.init_logging()

from web_app import create_app

app = create_app()

if ENV == "development":
    app.config['TEMPLATES_AUTO_RELOAD'] = True
else:
    app.config['TEMPLATES_AUTO_RELOAD'] = False


if __name__ == "__main__":
    # This block ONLY runs locally when you type `python run.py`
    if ENV == "development":
        from livereload import Server
        server = Server(app.wsgi_app)
        server.watch("web_app/templates/")
        server.watch("web_app/static/")
        print("Starting LiveReload development server on port 5000...")
        server.serve(port=5000)
    else:
        # Fallback local production testing (not used by actual production servers)
        print("Starting production fallback server on port 5000...")
        app.run(host="0.0.0.0", port=5000)