"""
Modular RAG MCP Server - Main Entry Point

Validates configuration, then starts the MCP Server (stdio transport).
Implementation lives in ``src.mcp_server.server``.
"""

import sys
from pathlib import Path

from src.core.settings import SettingsError, load_settings
from src.mcp_server.server import run_stdio_server


def main() -> int:
    """Load settings and run the stdio MCP server."""
    settings_path = Path("config/settings.yaml")
    try:
        load_settings(settings_path)
    except SettingsError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    return run_stdio_server()


if __name__ == "__main__":
    sys.exit(main())
