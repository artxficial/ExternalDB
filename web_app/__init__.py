import os
import sys
import pkgutil
import importlib
from flask import Flask

def create_app() -> Flask:
    from config import ROOT
    
    # ========================================
    # CRITICAL: Initialize logging FIRST
    # This must run before anything else logs
    # ========================================
    import core.logsplitter
    core.logsplitter.init_logging()
    
    root_dir = ROOT

    app = Flask(
        __name__,
        template_folder=os.path.join(root_dir, "web_app", "templates"),
        static_folder=os.path.join(root_dir, "web_app", "static")
    )

    app.config.from_object('config')
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    modules_path = os.path.join(root_dir, "web_app", "modules")

    print("\n--- Auto-Deploying Flask Modules ---")

    if not os.path.exists(modules_path):
        print(f"[CRITICAL ERROR] Modules path does not exist: {modules_path}")
        print("------------------------------------\n")
        return app

    for _, module_name, is_pkg in pkgutil.iter_modules([modules_path]):
        if is_pkg:
            continue

        try:
            mod = importlib.import_module(f".modules.{module_name}", package=__name__)

            bp_attr_name = f"{module_name}_bp"

            if hasattr(mod, bp_attr_name):
                blueprint = getattr(mod, bp_attr_name)

                url_prefix = None if module_name == "frontend" else f"/{module_name}"

                app.register_blueprint(blueprint, url_prefix=url_prefix)
                print(f"[SUCCESS] Auto-deployed module: '{module_name}' via prefix '{url_prefix or '/'}'")
            else:
                print(f"[WARNING] Module '{module_name}' found, but missing blueprint variable '{bp_attr_name}'")

        except Exception as e:
            print(f"[ERROR] Failed to auto-deploy module '{module_name}': {e}")

    print("------------------------------------\n")
    return app