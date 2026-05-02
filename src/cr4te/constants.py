from pathlib import Path

# === General project structure ===
CR4TE_PACKAGE_DIR = Path(__file__).resolve().parent

CR4TE_ASSETS_DIR = CR4TE_PACKAGE_DIR / "assets"
CR4TE_DEFAULTS_DIR = CR4TE_ASSETS_DIR / "defaults"
CR4TE_CSS_DIR = CR4TE_ASSETS_DIR / "css"
CR4TE_FAVICON_PATH = CR4TE_ASSETS_DIR / "favicon.svg"
CR4TE_JS_DIR = CR4TE_ASSETS_DIR / "js"
CR4TE_TEMPLATES_DIR = CR4TE_PACKAGE_DIR / "templates"

# === Shared filenames ===
CR4TE_JSON_FILE_NAME = "cr4te.json"
