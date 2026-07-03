# rag-server 知识域地图（B 轨）

> 45 个知识点（10 域）。工作目录：`rag-server/`。规格见 `DEV_SPEC.md`。  
> **标识（互斥，每点最多一个）**：**◆** 重亮点（面试开场必讲，全轨 5 处）｜**◇** 亮点（技术差异化，可写简历 bullet，全轨 4 处）｜**★** 重点（优先学习、常考，全轨 4 处）。  
> **本文档按「整体→局部、贴合数据流」的顺序排列**：自上而下 = 先全景 → 文档入库 → 混合检索 → 重排序 → MCP 暴露 → 可插拔配置 → 多模态 → 可观测 → 文档生命周期 → 测试工程化。  
> 域编号 **B1–B10** 与阅读顺序一致（B 轨统一用 B 前缀，与 A/C 轨对齐）。

## B1 RAG 整体架构

| ID | 知识点 | 关键代码路径 |
|----|--------|-------------|
| B1.1 | 端到端数据流（入库 + 检索 + MCP 暴露）★ | `rag-server/DEV_SPEC.md`, `main.py`, `scripts/` |
| B1.2 | 三层架构：core / ingestion（入库）/ libs | `src/core/`, `src/ingestion/`, `src/libs/` |
| B1.3 | Pipeline 组装与配置驱动 | `main.py`, `config/settings.yaml`, `src/core/settings.py` |
| B1.4 | 核心数据类型 Document / Chunk / QueryResult | `src/core/types.py` |
| B1.5 | CLI 入口脚本（ingest / query / evaluate） | `scripts/ingest.py`, `scripts/query.py`, `scripts/evaluate.py` |

## B2 文档入库流水线

> 代码模块名 `ingestion/`，业务含义即**把文档写入知识库**（解析→切分→增强→向量化→存储）。

| ID | 知识点 | 关键代码路径 |
|----|--------|-------------|
| B2.1 | 入库五阶段：Load → Split → Transform → Embed → Upsert ◆ | `src/ingestion/pipeline.py` |
| B2.2 | 文档切分（Chunking / RecursiveSplitter） | `src/ingestion/chunking/`, `src/libs/splitter/` |
| B2.3 | Transform 增强链（Refiner / Enricher / Captioner）◇ | `src/ingestion/transform/` |
| B2.4 | 双路向量化（Dense + Sparse）★ | `src/ingestion/embedding/` |
| B2.5 | 写入存储（向量库 + BM25 + 图片索引） | `src/ingestion/storage/` |

## B3 混合检索

| ID | 知识点 | 关键代码路径 |
|----|--------|-------------|
| B3.1 | 稠密向量检索（Dense Retrieval） | `src/core/query_engine/dense_retriever.py` |
| B3.2 | 稀疏检索（BM25） | `src/core/query_engine/sparse_retriever.py` |
| B3.3 | 混合检索与 RRF 融合 ◆ | `src/core/query_engine/hybrid_search.py`, `fusion.py` |
| B3.4 | 查询预处理（QueryProcessor） | `src/core/query_engine/query_processor.py` |
| B3.5 | 响应构建（Citation / 多模态组装） | `src/core/response/` |

## B4 重排序

| ID | 知识点 | 关键代码路径 |
|----|--------|-------------|
| B4.1 | Reranker 抽象与工厂 | `src/libs/reranker/` |
| B4.2 | CrossEncoder 重排序 | `src/libs/reranker/cross_encoder_reranker.py` |
| B4.3 | LLM 重排序 | `src/libs/reranker/llm_reranker.py` |
| B4.4 | 重排序在检索链中的集成（含 Fallback）◆ | `src/core/query_engine/reranker.py` |

## B5 MCP Server（rag-server 侧）

| ID | 知识点 | 关键代码路径 |
|----|--------|-------------|
| B5.1 | JSON-RPC + Stdio 传输 | `src/mcp_server/server.py` |
| B5.2 | 三工具定义与执行 ◆ | `src/mcp_server/tools/` |
| B5.3 | ProtocolHandler 路由与分发 | `src/mcp_server/protocol_handler.py` |
| B5.4 | Server 生命周期与异常处理 | `src/mcp_server/server.py` |

## B6 可插拔架构与配置

| ID | 知识点 | 关键代码路径 |
|----|--------|-------------|
| B6.1 | 五大工厂（LLM / Embedding / Reranker 等）◆ | `src/libs/*/factory*.py` |
| B6.2 | settings.yaml 配置加载 ★ | `config/settings.yaml`, `src/core/settings.py` |
| B6.3 | LLM 多厂商切换 | `src/libs/llm/` |
| B6.4 | Embedding 多后端 | `src/libs/embedding/` |
| B6.5 | Base 抽象类与扩展点 | `src/libs/*/base_*.py` |

## B7 多模态处理

| ID | 知识点 | 关键代码路径 |
|----|--------|-------------|
| B7.1 | PDF 解析与文件完整性校验 | `src/libs/loader/` |
| B7.2 | Vision LLM 图像理解 | `src/libs/llm/*_vision_llm.py` |
| B7.3 | 图片描述（ImageCaptioner） | `src/ingestion/transform/image_captioner.py` |
| B7.4 | 多模态存储与检索 ◇ | `src/ingestion/storage/image_storage.py`, `src/core/response/multimodal_assembler.py` |

## B8 可观测性与评估

| ID | 知识点 | 关键代码路径 |
|----|--------|-------------|
| B8.1 | Trace 链路追踪 ◇ | `src/core/trace/` |
| B8.2 | Dashboard 管理面板 | `src/observability/dashboard/` |
| B8.3 | 评估指标（Hit Rate / MRR 等） | `src/observability/evaluation/`, `scripts/evaluate.py` |
| B8.4 | 评估框架（RAGAS / Custom / Composite） | `src/libs/evaluator/` |
| B8.5 | 日志系统 | `src/observability/logger.py` |

## B9 文档生命周期与幂等

| ID | 知识点 | 关键代码路径 |
|----|--------|-------------|
| B9.1 | 文档去重（文件 Hash） | `src/ingestion/document_manager.py`, `src/libs/loader/file_integrity.py` |
| B9.2 | 增量入库（内容 Hash 跳过）◇ | `document_manager.py`, `pipeline.py` |
| B9.3 | Collection 管理 | `document_manager.py` |
| B9.4 | 文档状态追踪 | `document_manager.py` |

## B10 测试与工程化

| ID | 知识点 | 关键代码路径 |
|----|--------|-------------|
| B10.1 | 测试分层（Unit / Integration / E2E）★ | `tests/unit/`, `tests/integration/`, `tests/e2e/` |
| B10.2 | Fixtures 与 conftest | `tests/conftest.py`, `tests/fixtures/` |
| B10.3 | pyproject.toml 工程配置 | `pyproject.toml` |
| B10.4 | scripts 脚本入口 | `scripts/` |

## 面试讲法速查

**◆ 重亮点（5）— 开场主线**

| ID | 一句话 |
|----|--------|
| B2.1 | 五阶段入库：Load → Split → Transform → Embed → Upsert |
| B3.3 | Dense + BM25 双路召回，RRF 融合平衡查准与查全 |
| B4.4 | 粗排后精排，Cross-Encoder / LLM 可插拔，失败回退 |
| B5.2 | 三 MCP 工具：`list_collections` / `query_knowledge_hub` / `get_document_summary` |
| B6.1 | 工厂 + YAML 配置驱动，核心组件零代码切换 |

**◇ 亮点（4）— 追问展开**

| ID | 一句话 |
|----|--------|
| B2.3 | LLM 增强链：Chunk 重组、元数据注入、图片描述 |
| B7.4 | 多模态存储与检索，Citation 含图文 |
| B8.1 | Ingestion + Query 双链路 Trace，白盒化定位坏 Case |
| B9.2 | SHA256 文件哈希 + 内容哈希，增量跳过与幂等 Upsert |

> RAG 岗推荐：**B3.3 → B4.4 → B2.1 → B6.1**；与 Host 联调必讲 **B5.2**。

## 项目发现清单（B 轨）

触发 B 轨时静默读取：

1. `rag-server/DEV_SPEC.md`（架构、模块、排期概览）
2. `rag-server/config/settings.yaml` 或 example
3. `rag-server/src/` 目录树
4. `rag-server/main.py`, `scripts/ingest.py`, `scripts/query.py`
5. `rag-server/tests/` 结构概览
