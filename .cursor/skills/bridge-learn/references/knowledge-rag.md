# rag-server 知识域地图（B 轨）

> 45 个知识点（10 域）。工作目录：`rag-server/`。规格见 `DEV_SPEC.md`。

| ID | 知识域 / 知识点 | 关键代码路径 |
|----|----------------|-------------|
| **D1** | **RAG Pipeline 整体架构** | |
| D1.1 | 端到端数据流 | `rag-server/DEV_SPEC.md`, `main.py`, `scripts/` |
| D1.2 | 三层架构：core/ingestion/libs | `rag-server/src/core/`, `src/ingestion/`, `src/libs/` |
| D1.3 | Pipeline 组装与配置驱动 | `main.py`, `config/settings.yaml`, `src/core/settings.py` |
| D1.4 | 核心数据类型 Document/Chunk/QueryResult | `src/core/types.py` |
| D1.5 | CLI 入口脚本 | `scripts/ingest.py`, `scripts/query.py`, `scripts/evaluate.py` |
| **D2** | **Ingestion Pipeline** | |
| D2.1 | Pipeline 五阶段流程 | `src/ingestion/pipeline.py` |
| D2.2 | Chunking 与 RecursiveSplitter | `src/ingestion/chunking/`, `src/libs/splitter/` |
| D2.3 | Transform 链 Refiner/Enricher/Captioner | `src/ingestion/transform/` |
| D2.4 | Dense/Sparse 双编码 | `src/ingestion/embedding/` |
| D2.5 | VectorUpserter、BM25Indexer、ImageStorage | `src/ingestion/storage/` |
| **D3** | **Hybrid Search & Retrieval** | |
| D3.1 | Dense Retrieval | `src/core/query_engine/dense_retriever.py` |
| D3.2 | Sparse / BM25 | `src/core/query_engine/sparse_retriever.py` |
| D3.3 | Hybrid Search + RRF Fusion | `src/core/query_engine/hybrid_search.py`, `fusion.py` |
| D3.4 | QueryProcessor | `src/core/query_engine/query_processor.py` |
| D3.5 | ResponseBuilder / Citation / Multimodal | `src/core/response/` |
| **D4** | **Rerank** | |
| D4.1 | BaseReranker + Factory | `src/libs/reranker/` |
| D4.2 | CrossEncoder Reranker | `src/libs/reranker/cross_encoder_reranker.py` |
| D4.3 | LLM Reranker | `src/libs/reranker/llm_reranker.py` |
| D4.4 | Rerank 在检索链中的集成 | `src/core/query_engine/reranker.py` |
| **D5** | **MCP Server（rag-server 侧）** | |
| D5.1 | JSON-RPC + Stdio | `src/mcp_server/server.py` |
| D5.2 | 三工具定义与执行 | `src/mcp_server/tools/` |
| D5.3 | ProtocolHandler | `src/mcp_server/protocol_handler.py` |
| D5.4 | Server 生命周期与异常 | `src/mcp_server/server.py` |
| **D6** | **可插拔架构 & 配置** | |
| D6.1 | 五大工厂 | `src/libs/*/factory*.py` |
| D6.2 | settings.yaml 加载 | `config/settings.yaml`, `src/core/settings.py` |
| D6.3 | LLM 多厂商 | `src/libs/llm/` |
| D6.4 | Embedding 多后端 | `src/libs/embedding/` |
| D6.5 | Base 类与扩展点 | `src/libs/*/base_*.py` |
| **D7** | **多模态** | |
| D7.1 | PDF 解析与 FileIntegrity | `src/libs/loader/` |
| D7.2 | Vision LLM | `src/libs/llm/*_vision_llm.py` |
| D7.3 | ImageCaptioner | `src/ingestion/transform/image_captioner.py` |
| D7.4 | 多模态存储与检索 | `src/ingestion/storage/image_storage.py`, `src/core/response/multimodal_assembler.py` |
| **D8** | **可观测性 & 评估** | |
| D8.1 | Trace 系统 | `src/core/trace/` |
| D8.2 | Dashboard Streamlit | `src/observability/dashboard/` |
| D8.3 | 评估指标 | `src/observability/evaluation/`, `scripts/evaluate.py` |
| D8.4 | Composite/RAGAS/Custom | `src/libs/evaluator/` |
| D8.5 | 日志 | `src/observability/logger.py` |
| **D9** | **测试 & 工程化** | |
| D9.1 | Unit/Integration/E2E | `tests/unit/`, `tests/integration/`, `tests/e2e/` |
| D9.2 | Fixtures / conftest | `tests/conftest.py`, `tests/fixtures/` |
| D9.3 | pyproject.toml | `pyproject.toml` |
| D9.4 | scripts 入口 | `scripts/` |
| **D10** | **Document Manager & 幂等** | |
| D10.1 | 文档去重 Hash | `src/ingestion/document_manager.py`, `src/libs/loader/file_integrity.py` |
| D10.2 | 增量 Ingestion | `document_manager.py`, `pipeline.py` |
| D10.3 | Collection 管理 | `document_manager.py` |
| D10.4 | 文档状态追踪 | `document_manager.py` |

## 项目发现清单（B 轨）

触发 B 轨时静默读取：

1. `rag-server/DEV_SPEC.md`（架构、模块、排期概览）
2. `rag-server/config/settings.yaml` 或 example
3. `rag-server/src/` 目录树
4. `rag-server/main.py`, `scripts/ingest.py`, `scripts/query.py`
5. `rag-server/tests/` 结构概览
