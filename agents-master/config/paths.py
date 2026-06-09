"""项目路径常量。"""

import os

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT_OUTPUT_DIR = os.path.join(APP_DIR, "data", "outputs")
DEFAULT_RAG_SERVER_DIR = os.path.normpath(os.path.join(APP_DIR, "..", "rag-server"))
