---
id: decisions/0002-dual-venv
title: ADR-0002 双 venv 隔离依赖
tags: [adr, venv, dependencies, monorepo]
sources:
  - README.md
  - agents-master/config/mcp_config.py
  - QA/fast-qa.md
related: [decisions/0001-monorepo-split, host/mcp-client, integration/config-and-keys]
updated: 2026-09-10
---

# ADR-0002 · 为什么双 venv 隔离依赖

> **TL;DR**：两个子项目各自持有 `.venv`（Host 与 RAG 互不共用），代价是启动 rag-server MCP 时必须由 `resolve_mcp_config()` 显式选中 `rag-server/.venv/bin/python`。

## 背景

monorepo 里两个子项目的依赖画像完全不同：

- **Host**：Streamlit、LangGraph、LangChain、MCP 适配器等，偏 UI 与编排。
- **RAG**：chromadb、embedding 模型、cross-encoder 精排、PyMuPDF 解析等，偏数据处理，包重且对版本敏感（例如 PyMuPDF 未安装会导致 PDF 图片数为 0，见 [[analysis/rag-issues]]）。

如果共用一个虚拟环境，任一侧升级依赖都可能把另一侧弄坏；而 RAG 侧的模型类依赖体积大，也不适合让 Host 承担。

## 选项

| 选项 | 说明 |
| --- | --- |
| A. 单 venv 共用 | 安装一次，`import` 直接可用，但版本冲突面大 |
| B. 双 venv（**采用**） | 每个子项目独立 `.venv`，跨进程用 MCP 连接 |

## 决策

采用 **B**：`agents-master/.venv` 与 `rag-server/.venv` 各自独立，按根 `README.md`「快速开始」分两段安装：

```bash
cd agents-master && python3.12 -m venv .venv && pip install -r requirements.txt
cd ../rag-server && python3.12 -m venv .venv && pip install -e ".[dev]"
```

## 后果

**收益**

- 依赖完全隔离，两侧可独立升级、独立锁版本。
- RAG 可脱离 Host 单独运行与测试（`scripts/query.py`、`streamlit run dashboard.py`）。

**代价**

- **Host 无法用自身解释器拉起 rag-server**：`config.json` 里 `command: "python"` 必须被解析成 RAG 侧的解释器。这正是 `resolve_mcp_config()` 的一条核心规则——识别到 rag-server（按 name / cwd 目录名 / `args == ["-m", "src.mcp_server.server"]`）时，优先使用 `rag-server/.venv/bin/python`。
- **环境准备成本翻倍**：新机器需装两次，且需注意两侧 Python 版本一致（均 3.12）。
- **排障多一层**：检索无结果时，需先确认「双 venv 是否各自装好、`resolve_mcp_config` 是否选对了 Python」，再怀疑业务逻辑（见 [[integration/troubleshooting]]）。

## 关联

- 相关：[[decisions/0001-monorepo-split]]
- 相关：[[host/mcp-client]]
- 相关：[[integration/config-and-keys]]
