---
id: integration/troubleshooting
title: 常见故障排查
tags: [integration, troubleshooting, ops]
sources:
  - agents-master/README.md
  - wiki/10-host/mcp-client.md
  - QA/integration-qa.md
related: [integration/config-and-keys, integration/mcp-lifecycle, analysis/tool-failures]
updated: 2026-09-10
---

# 常见故障排查

> **TL;DR**：联调故障优先按「Key → 双 venv → 是否入库 → collection 名称 → embedding 一致 → MCP 子进程」的顺序排查；多数问题落在配置与依赖，而非代码逻辑。

## 是什么

高频现象与处理：

| 现象 | 优先检查 |
| --- | --- |
| 初始化失败 / 无法连接 MCP | `config.json` JSON 是否合法；`cwd` 是否指向 rag-server 工程根目录 |
| `No module named chromadb` | rag-server 是否已 `pip install -e ".[dev]"`；`resolve_mcp_config()` 是否用上其 `.venv` |
| 检索无结果 | 是否做过 ingest；collection 名称是否与入库一致（先调 `list_collections`） |
| Embedding 报错 | `settings.yaml` 的 `embedding.model` 是否与百炼控制台已开通模型一致 |
| 高德工具不可用 | 是否在 `agents-master/` 执行 `npm install`；`.env` 是否配 `AMAP_MAPS_API_KEY` |
| rag-server 路径不对 | 修改 `config.json` 中 `cwd` 为 rag-server 的绝对路径 |

## 为什么这样设计

- **先排环境后排代码**：绝大多数问题源自 Key 缺失、依赖未装、未入库、名称不一致，而非逻辑缺陷。
- **可二分定位**：不启 Host 时，用 `rag-server/scripts/query.py` 单独跑检索，可把问题二分为「Host/MCP 编排问题」还是「RAG 内部问题」。

## 怎么实现

**知识库问答排障顺序**：

1. **Key**：`agents-master/.env` 与 `rag-server/config/settings.yaml` 是否有效。
2. **双 venv**：rag-server 是否独立安装；`resolve_mcp_config()` 是否用到正确 Python。
3. **是否已入库**：目标 collection 是否存在、是否有文档。
4. **collection 名称**是否选对。
5. **embedding 一致**：入库与检索是否同一 embedding 模型。
6. **（扩展）** MCP 子进程 spawn、`cwd` 路径、工具/LLM 报错信息。

**启动前的健康检查**：侧边栏应显示 **4 个** MCP（时间、文档导出、rag-server、高德）；缺项说明对应服务未连上。

## 关键代码锚点

| 位置 | 作用 |
| --- | --- |
| `rag-server/scripts/query.py` | 脱离 Host 单独验证检索链路 |
| `agents-master/config/mcp_config.py` | 定位配置解析问题 |
| `rag-server/scripts/ingest.py` | 确认入库是否执行 |

## 关联

- 配置与密钥：[[integration/config-and-keys]]
- MCP 生命周期：[[integration/mcp-lifecycle]]
- 工具失败分型：[[analysis/tool-failures]]
