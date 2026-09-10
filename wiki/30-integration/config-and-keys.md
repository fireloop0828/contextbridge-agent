---
id: integration/config-and-keys
title: 配置与密钥分工
tags: [integration, config, security]
sources:
  - README.md
  - agents-master/README.md
  - agents-master/config/mcp_config.py
related: [integration/end-to-end, host/mcp-client, rag/architecture]
updated: 2026-09-10
---

# 配置与密钥分工

> **TL;DR**：项目有**两套配置**——`agents-master/.env`（LLM Key、高德 Key、记忆 Embedding）与 `rag-server/config/settings.yaml`（RAG 的 LLM 与 Embedding 模型）；密钥一律不入 Git，由启动时解析注入子进程。

## 是什么

| 配置位置 | 管什么 |
| --- | --- |
| `agents-master/.env` | 聊天模型 Key、高德地图 `AMAP_MAPS_API_KEY`、长期记忆 Embedding 的 `DASHSCOPE_*` |
| `agents-master/config.json` | MCP 服务注册表（连哪些服务、怎么连） |
| `rag-server/config/settings.yaml` | RAG 的 `llm` / `embedding` 的 Key、模型名与检索参数 |
| `rag-server/config/collections.yaml` | 知识库 collection 定义 |

密钥与用途的对应关系：

| 目的 | 配置位置 |
| --- | --- |
| 聊天模型 | `agents-master/.env`（+ `agents-master/config/models.py`） |
| 长期记忆 Embedding | `agents-master/.env`（`DASHSCOPE_*`） |
| 知识库检索 | `rag-server/config/settings.yaml` |
| 旅行 POI / 地图 | `agents-master/.env`（`AMAP_MAPS_API_KEY`） |

## 为什么这样设计

- **按进程分权**：Host 与 RAG 是独立进程，各自读自己的配置，互不依赖对方的密钥文件。
- **密钥不进配置**：`config.json` 里写 `${VAR}` 占位符，而非明文 Key，避免密钥进 Git。
- **同一 Key 可复用**：两处 LLM 若都用百炼，填同一个 Key 即可，但**模型名**可能不同（RAG 的 embedding 模型需与入库时一致）。

## 怎么实现

1. 应用启动时 `load_dotenv(override=True)` 载入 `agents-master/.env`。
2. `resolve_mcp_config()` 把 `config.json` 里的 `${VAR}` 占位符替换为环境变量值，并注入对应 MCP 子进程的 `env`（如把 `AMAP_MAPS_API_KEY` 注入高德子进程）。
3. rag-server 子进程启动后自行读取 `config/settings.yaml`。

**禁止事项**：

- 禁止在 `config.json` 明文长期存放生产 API Key。
- 禁止提交含真实 Key 的 `rag-server/config/settings.yaml`（从 example 模板复制后本地填写）。
- 提交前检查 `config.json` 里 MCP 的 `env` 段，不得含明文 Key。

## 关键代码锚点

| 位置 | 作用 |
| --- | --- |
| `agents-master/config/mcp_config.py` | `_interpolate_env_vars()` 做 `${VAR}` 替换与注入 |
| `agents-master/.env.example` | 环境变量模板 |
| `rag-server/config/settings.dashscope.example.yaml` | RAG 配置模板 |

## 关联

- 端到端链路：[[integration/end-to-end]]
- MCP 配置解析：[[host/mcp-client]]
- RAG 架构与配置：[[rag/architecture]]
- 排障清单：[[integration/troubleshooting]]
