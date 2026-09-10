---
id: decisions/0003-mcp-stdio
title: ADR-0003 MCP 选 stdio 而非 HTTP
tags: [adr, mcp, stdio, transport]
sources:
  - wiki/10-host/mcp-client.md
  - agents-master/config.json
  - agents-master/config/mcp_config.py
related: [host/mcp-client, integration/mcp-lifecycle, analysis/mcp-init-performance]
updated: 2026-09-10
---

# ADR-0003 · 为什么用 MCP stdio 而非 HTTP

> **TL;DR**：本项目是单机 monorepo 联调场景，`streamlit run app.py` 时由 Host 直接拉起 4 个 MCP 子进程（stdio 管道），省掉端口、服务发现与鉴权；代价是初始化有 spawn 开销、生命周期要自行管理。

## 背景

Host 与 RAG（以及高德地图、时间、导出等能力）跨进程通信，MCP 支持多种传输方式。需要选择一种作为生产路径。

## 选项

| 维度 | stdio（**采用**） | HTTP / SSE |
| --- | --- | --- |
| 连接方式 | 客户端拉起子进程，走标准输入输出管道 | 独立服务监听端口，客户端按 URL 连接 |
| 端口 / 鉴权 | 不占端口、无需鉴权 | 需要端口分配、服务发现与鉴权 |
| 部署 | monorepo 本地一键联调简单 | 适合多客户端共享、Docker / K8s 拆服务 |
| 日志 | 子进程 **stdout 只能走协议**，日志必须打 stderr | 日志约束相对宽松 |
| 多客户端复用 | 每个 Host 进程各自 spawn | 天然支持多客户端共享 |

## 决策

生产路径**全部使用 stdio**，且无改为 HTTP 的改造计划（该对比仅用于技术讲解）。

理由：monorepo 里执行 `streamlit run app.py` 即可自动拉起 4 个 MCP（`get_current_time`、`document-export`、`rag-server`、`amap-maps`）；`cwd` 指向同级 `rag-server`，由 `resolve_mcp_config()` 自动选对虚拟环境，本地联调成本最低。

## 后果

**收益**

- 零网络配置：不需要端口、服务发现、鉴权与证书。
- 进程随 Host 启停，天然对齐「单机开发工具」的使用方式。
- 配置声明式：`config.json` 每个条目只需 `command` / `args` / `cwd` / `transport` / `env`。

**代价**

- **初始化有成本**：每次启动都要 spawn 子进程并握手 `get_tools()`，`npx` 冷启动尤其慢（见 [[analysis/mcp-init-performance]]）。缓解手段：解析本地 `mcp-amap` 二进制、切模式只 `rebuild_agent_only()` 不重连 MCP。
- **生命周期需自行管理**：子进程重连、僵尸进程、异常退出都要处理（见 [[integration/mcp-lifecycle]]）。
- **stdout 是协议通道**：rag-server 侧任何 `print` 都会污染协议，日志必须走 stderr。

## 关联

- 相关：[[host/mcp-client]]
- 相关：[[integration/mcp-lifecycle]]
- 相关：[[analysis/mcp-init-performance]]
