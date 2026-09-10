---
id: rag/requirements
title: RAG 需求目标与模块设计
tags: [rag, requirements]
sources:
  - rag-server/src/
  - rag-server/DEV_SPEC.md
related: [rag/architecture, rag/flow, overview/project]
updated: 2026-09-10
---

# rag-server 需求目标与模块设计

> **TL;DR**：rag-server 定位为可独立运行的 RAG 项目，同时作为 ContextBridge 的知识检索子系统；围绕入库、检索、评估、MCP 对外四类模块定义目标与可观测性要求。

> 内部设计笔记 · 定义项目要做什么、解决什么问题，以及各模块与界面应达成什么目标。

## 目录

- [TL;DR](#tldr)
- [1. 项目定位与目标](#1-项目定位与目标)
  - [1.1 独立 RAG 项目](#11-独立-rag-项目)
  - [1.2 ContextBridge 知识检索子系统](#12-contextbridge-知识检索子系统)
  - [1.3 要达成的目标](#13-要达成的目标)
- [2. 解决什么问题](#2-解决什么问题)
- [3. 使用方](#3-使用方)
- [4. 模块与可观测性目标](#4-模块与可观测性目标)
  - [4.1 入库](#41-入库)
  - [4.2 检索](#42-检索)
  - [4.3 评估](#43-评估)
  - [4.4 MCP 对外服务](#44-mcp-对外服务)

---

## TL;DR

rag-server 是一个**可插拔、可观测的模块化 RAG 服务**：负责把文档建成可检索的知识库（Dense 向量 + 本项目自研 BM25 文件索引），并通过 **MCP 协议**把**检索**能力交给上层 Agent；**自然语言回答由上层 Agent 生成**。在 **ContextBridge** 中，它为 agents-master 提供旅行攻略、知识库问答等场景下的私有知识检索。

---

## 1. 项目定位与目标

### 1.1 独立 RAG 项目

**rag-server** 是一条完整的 RAG 工程链路：

- **入库（Indexing）**：文档解析 → 分块 → 可选增强 → 写入 Chroma 向量库与本项目 **BM25 文件索引**（非 Chroma/ES 内置稀疏检索）  
- **检索（Retrieval）**：行业通用的混合召回（Dense + BM25 + **RRF**）→ 可选 **Rerank** → 返回带引用的 chunk（编排由本项目 `HybridSearch` 实现）  
- **对外暴露**：以 MCP 协议注册自定义 Tools，供 Copilot、Claude、自研 Agent 等 Client 调用  
- **可运维**：Streamlit Dashboard 管理数据、回放链路、跑评估

生成最终自然语言回答由上层 Client / Agent 完成；本服务聚焦**把知识建好、搜得准、调得动**。

### 1.2 ContextBridge 知识检索子系统

在 [ContextBridge Agent](https://github.com/fireloop0828/contextbridge-agent) 单体仓库中，rag-server 与 agents-master **同仓邻接部署**：

- agents-master 在 `config.json` 中以子进程方式拉起 `python -m src.mcp_server.server`（`cwd` 指向 `rag-server`）  
- Agent 经 MCP stdio 调用 rag-server 注册的三个 Tool（`list_collections` / `query_knowledge_hub` / `get_document_summary`），检索已入库的 `travel_plan` 等 collection  
- 旅行规划、知识库问答等模式把 RAG 当作**可信依据来源**，与高德地图、时间等 MCP 能力并列

集成细节见 [外接集成设计.md](./mcp-server.md)。

注：以上三个 Tool 名与职责由 rag-server 定义（项目内称「三件套」），非 MCP 或 RAG 行业标准 API：

1. `list_collections` — 发现有哪些知识库（如 `travel_plan`）
2. `query_knowledge_hub` — 主检索（调用本项目 Hybrid Search 链路；**仅返回 chunk，不生成回答**）
3. `get_document_summary` — 按需拉单篇文档摘要/元数据

### 1.3 要达成的目标

1. **双路召回**：语义检索（Dense / Embedding）与关键词检索（本项目 BM25）互补，RRF 融合。  
2. **白盒可观测**：每次入库、检索按**本项目定义的 Trace stage** 写入 `logs/traces.jsonl`，Dashboard 回放。  
3. **可插拔后端**：LLM、Embedding、向量库、重排、评估等通过配置切换 Provider，适配本地与云端。  
4. **标准协议外接**：以 **MCP stdio**（行业标准传输与 Tool Calling 机制）接入；暴露哪些 Tool、返回何种 citation 格式由 **rag-server 自定义**。  
5. **数据驱动迭代**：本项目 Golden Test Set + **Custom**（检索指标，项目定义）/ **Ragas**（回答指标，社区库）/ **Composite**（项目编排）评估迭代。

---

## 2. 解决什么问题


| 痛点                    | 本系统的回应                                            |
| --------------------- | ------------------------------------------------- |
| 私有文档无法被 AI 安全、可控地引用   | 本地入库 + MCP 暴露**检索**（非生成），数据留在自有环境                          |
| 纯向量检索对专名、产品缩写、中英混排不敏感 | 通用 **BM25 算法** + **RRF** 与 Dense 融合（本项目自研文件索引与 `HybridSearch` 编排）         |
| 粗排 Top-K 里「看着相关但不是最准」 | 可选 Cross-Encoder / LLM **Rerank**（通用技术，本项目可插拔接入）                  |
| PDF 内图片、图表无法被文本检索命中   | Vision LLM 生成 Image Caption 并写入 chunk（本项目入库增强）             |
| RAG 链路像黑盒，出问题只能猜      | **本项目** Trace schema → `logs/traces.jsonl`，Dashboard 回放     |
| 改分块/改模型后不知道有没有变好      | **本项目** Golden Set + Custom（`hit_rate`/`mrr`）+ Ragas（`faithfulness` 等社区指标）            |
| Agent 与知识库之间缺少标准调用方式    | **MCP 协议**（标准）+ rag-server 三件套 Tool 与 **自定义 citation 格式**（`[1][2]` + JSON `citations`） |


---

## 3. 使用方


| 类型                         | 典型诉求                              | 主要入口                                        |
| -------------------------- | --------------------------------- | ------------------------------------------- |
| **人**（开发者 / 运维）            | 入库文档、浏览 chunk、看 Trace、跑评估、调配置     | Streamlit Dashboard、`scripts/ingest.py` 等   |
| **程序**（Agent / MCP Client） | 经 MCP 调用 rag-server Tool：发现 collection、检索 chunk、取文档摘要（**不生成最终回答**） | MCP stdio：`python -m src.mcp_server.server` |


---

## 4. 模块与可观测性目标

技术实现与选型见 [系统架构与模块选型.md](./architecture.md)；评估闭环见 [评估体系设计.md](./evaluation.md)。

### 4.1 入库

**模块目标**

- 将 PDF / TXT / MD / DOCX 等文档解析为带元数据的 **Chunk**  
- 同步写入 **Chroma 向量库**（当前默认向量后端）与 **本项目 BM25 文件索引**（`data/db/bm25/{collection}/`，按 collection 隔离）  
- 支持 SHA256 **幂等**：未变更文件可跳过重复处理  
- 可选：分块精炼、元数据增强、图片描述（Vision LLM）

**期望产出**：指定 collection 内文档可检索；每条 chunk 有稳定 **`chunk_id`**（本项目 `DocumentChunker` 规则）、`doc_id`（文件 SHA256）、来源路径、页码等元数据。

**可观测性（界面）目标**


| 界面                          | 要支撑的判断                                                                  |
| --------------------------- | ----------------------------------------------------------------------- |
| **文档入库**（Ingestion Manager） | 选了哪些文件、入到哪个 collection、是否 force 重跑                                      |
| **入库记录**（Ingestion Traces）  | 各 stage（load / chunk / transform / embed / upsert）是否成功、耗时、chunk 数 / 向量数 |
| **知识浏览**（Data Browser）      | 抽查分块正文、元数据、关联图片是否符合预期                                                   |


### 4.2 检索

**模块目标**

- 对自然语言 Query 做预处理（含中文分词关键词，本项目 `QueryProcessor` + jieba）  
- **Dense**（Embedding 相似度，通用 Bi-Encoder 思路）与 **Sparse**（本项目 BM25 文件检索）并行召回  
- **RRF**（通用融合算法）融合为统一排序列表；可选 **Rerank** 精排  
- 返回 Top-K chunk，附带分数、来源、chunk_id，供**上层 Agent** 生成或展示引用

**期望产出**：给定 query 与 collection，返回相关且可核对出处的片段列表。

**可观测性（界面）目标**


| 界面                     | 要支撑的判断                                   |
| ---------------------- | ---------------------------------------- |
| **检索记录**（Query Traces） | Dense / Sparse 各自命中几条、融合前后变化、Rerank 是否执行 |
| **知识浏览**               | 对照「搜到的 chunk」与库内原文是否一致                   |
| **系统总览**（Overview）     | 库内文档量、collection 概况等健康度一览                |


### 4.3 评估

**模块目标**

- 用 **本项目 Golden Test Set**（`tests/fixtures/*.json`）对固定 query 集合做回归  
- **Custom**（本项目）：基于 `expected_chunk_ids` 计算 **hit_rate**、**MRR**  
- **Ragas**（社区库）：LLM-as-Judge 的 **faithfulness** / **answer_relevancy** / **context_precision**  
- **Composite**（本项目编排）：一次跑通 Custom + Ragas，合并 metrics  
- 结果写入 `logs/eval_history.jsonl`，支持对比历次迭代

**期望产出**：用一组数字和个案说明「这次改动让检索/回答变好了还是变差了」。

**可观测性（界面）目标**


| 界面                          | 要支撑的判断                                   |
| --------------------------- | ---------------------------------------- |
| **效果评测**（Evaluation Panel）  | 选 backend / collection、看聚合指标与单题明细、浏览历史曲线 |
| **检索记录**（单条 Trace 上的 Ragas） | 对单次真实查询做轻量评判，与全量 Golden Set 评估互补         |


### 4.4 MCP 对外服务

**模块目标**

- 以 **MCP stdio**（标准协议传输）进程对外提供 Tool 接口  
- 对外暴露三个**自定义** Tool（项目内称「三件套」）：`list_collections`、`query_knowledge_hub`、`get_document_summary`  
- 检索路径与 Dashboard / CLI **共用 Core**（本项目 `HybridSearch` + `Reranker`），保证行为一致  
- MCP 返回体经 `ResponseBuilder` 组装为**本项目 citation 格式**（Markdown `[1][2]` + 结构化 `citations` JSON），便于 Agent 标注依据

**期望产出**：任意合规 MCP Client 注册后即可发现知识库、发起检索、拉取文档摘要。

**可观测性（界面）目标**


| 界面       | 要支撑的判断                                        |
| -------- | --------------------------------------------- |
| **检索记录** | MCP 触发的 query 是否与手动调试时同一套 stage、同一 collection |
| **系统总览** | MCP 相关配置、服务是否按预期连上数据目录                        |

---

## 关联

- 相关：[[rag/architecture]]
- 相关：[[rag/flow]]
- 相关：[[overview/project]]
