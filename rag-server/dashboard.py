"""RAG 控制台 — 根目录浅入口（实现位于 src/observability/dashboard/）。

推荐::

    streamlit run dashboard.py

与主应用同机运行时换端口::

    python scripts/start_dashboard.py --port 8502
"""

from src.observability.dashboard.app import main

if __name__ == "__main__":
    main()
