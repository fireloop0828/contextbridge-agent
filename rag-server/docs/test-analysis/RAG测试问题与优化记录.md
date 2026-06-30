# RAG 测试问题与优化记录

> 开发笔记 · 记录入库、检索、Dashboard、MCP 联调过程中的排障与优化，体现项目迭代轨迹。评估专项见 [RAG评估调优专题.md](./RAG评估调优专题.md)。

## 目录

- [记录说明](#记录说明)
- [检索](#检索)
- [入库](#入库)
- [Dashboard](#dashboard)
- [MCP联调](#mcp联调)

---

## 记录说明

每条采用统一结构，**新条目追加在对应节末尾**。

```markdown
### [YYYY-MM-DD] 简短标题

- **现象**：
- **原因**：
- **处理**：
  - 方案要点
  - **使用的技术 / 改动文件**：
- **结果 / 待验证**：
```

---

## 检索

### [2026-06-10] 未入库就 query，Trace 里 dense / sparse 全空

- **现象**：服务能启动、MCP 工具也能调，但 `query_knowledge_hub` 永远返回「未找到相关内容」；打开「检索记录」，该条 Trace 的稠密、稀疏阶段 `output_count` 均为 0，融合阶段被跳过。
- **原因**：Chroma 与 `data/db/bm25/{collection}/` 尚无数据；空库时 Dense 查不到向量，BM25 索引文件也不存在或为空，Hybrid 两路都落空。
- **处理**：
  - 先对目标 collection 跑 ingest（Dashboard「入库管理」或 `python scripts/ingest.py --collection <name>`）。
  - 再用 `list_collections` 确认该库 `chunk_count > 0`。
  - 排障时看 Trace 诊断条：「稠密检索返回 0 条」即数据前提未满足。
  - **使用的技术 / 改动文件**：`query_traces.py` 中 `_render_diagnostics()` 对空结果的提示；`hybrid_search.py` 两路检索 + 融合前置条件。
- **结果 / 待验证**：入库后同 query 的 dense/sparse 均有命中，融合 (RRF) 阶段出现在 Trace 中。

---

### [2026-06-12] 文档 ingest 到 `travel_plan`，查询 `default`，怎么搜都是 0

- **现象**：Dashboard「数据浏览」里 `travel_plan` 有上千条分块；Agent 或 CLI 用默认库查询仍为空。`eval_history` 早期也出现 Custom 指标全 0。
- **原因**：**collection 不一致**。向量与 BM25 按 collection 分目录存储；`query_knowledge_hub` 未传 `collection` 时回退 MCP 配置默认 `travel_plan`，而 Dashboard / `settings.yaml` 的 `vector_store.collection_name` 可能是 `default`；两边默认值来源不同，容易查错库。
- **处理**：
  - 约定业务库名（旅行场景用 `travel_plan`），入库、评测、MCP 调用**显式传同一 collection**。
  - Agent 侧先 `list_collections` 再 `query_knowledge_hub(..., collection="travel_plan")`（见 [外接集成设计.md](../project-design/外接集成设计.md) §3.5）。
  - 历史库从 `knowledge_hub` 迁移时用 `scripts/rename_collection.py --old knowledge_hub --new travel_plan` 保留数据。
  - **使用的技术 / 改动文件**：`query_knowledge_hub.py`（`default_collection="travel_plan"`）；`evaluation_panel.py` collection 下拉；`rename_collection.py`。
- **结果 / 待验证**：三处（入库、评测、MCP）collection 对齐后检索与 hit_rate 恢复正常。

---

### [2026-06-14] 检索记录里 sparse 一直 0，dense 有结果

- **现象**：Trace 瀑布图里「稠密」有 5～10 条，「稀疏 (BM25)」始终 0；融合提示「仅稠密检索返回了结果」，RRF 未生效。
- **原因**：常见两类——(1) 该 collection **从未成功写入 BM25**，`data/db/bm25/{collection}/` 目录空或缺失；(2) `SparseRetriever.default_collection` 与当前查询库不一致（检索组件绑了 A 库，BM25 却在读 B 库索引）。
- **处理**：
  - 确认 `data/db/bm25/{collection}/` 在 ingest 后存在且非空。
  - 评估面板、MCP、CLI 构建 `SparseRetriever` 时统一设置 `sparse_retriever.default_collection = collection`。
  - `SparseRetriever._ensure_index_loaded()` 每次查询从磁盘重载 BM25，Dashboard 新入库后**不必重启** MCP 即可看到稀疏命中（向量库侧 MCP 也会按请求重建 store）。
  - **使用的技术 / 改动文件**：`sparse_retriever.py`、`bm25_indexer.py`；`evaluation_panel.py` / `query_knowledge_hub.py` 中 `default_collection` 赋值。
- **结果 / 待验证**：稀疏阶段 `output_count > 0`，融合阶段出现且 final 列表与纯 Dense 有差异。

---

### [2026-05-28] 专名 / 缩写纯向量排不进 Top-K → Hybrid Search（BM25 + RRF）

- **现象**：问「全球旅行治安等级分为几级」等含专名、政策术语的 query，纯 Dense 检索常把泛化段落排在前面，标注 chunk 在 Top-10 外。
- **原因**：Embedding 对罕见专名、中英混排、缩写的字面匹配弱；单向量语义检索单独扛不住「旅行知识库」类文档。
- **处理**：
  - 增加 **Sparse 路**：jieba 分词 + 自研 `BM25Indexer` 落盘。
  - **RRF 融合** `HybridSearch` 合并 Dense / Sparse 排名，再截断 `fusion_top_k`。
  - 入库时 Dense（Chroma）与 Sparse（BM25）**同 collection 同步写入**。
  - **使用的技术 / 改动文件**：`hybrid_search.py`、`sparse_retriever.py`、`dense_retriever.py`、`bm25_indexer.py`；架构说明见 [系统架构与模块选型.md](../project-design/系统架构与模块选型.md) §2.6、§3.2。
- **结果 / 待验证**：Golden Set 上专名类 query 的 hit_rate 明显提升；Trace 可对比两路候选差异。

---

### [2026-06-08] 粗排 Top-10 看着相关，最准那条总排不进前三 → 两段式 Rerank

- **现象**：Hybrid 融合后前 10 条「沾边」但排序靠后；期望 chunk 在 4～7 位，线上只展示 Top-3 时用户感觉「没搜到」。
- **原因**：RRF 只做排名融合，不理解细粒度语义；Top-K 截断放大了粗排误差。
- **处理**：
  - **两段式**：`initial_top_k` 放大候选（如 `top_k * 2`），再经 `CoreReranker` 重排后取最终 `top_k`。
  - `settings.yaml` 配置 `reranker`（LLM / CrossEncoder）；失败时 `fallback_on_error` 保持原序，避免整条 query 挂掉。
  - MCP、评估 Runner、检索记录页单题 Ragas 均走同一套 Rerank 开关。
  - **使用的技术 / 改动文件**：`reranker.py`（Core 编排）、`libs/reranker/` 工厂；`query_knowledge_hub.py` 中 `initial_top_k` 逻辑。
- **结果 / 待验证**：开启 Rerank 后 Trace 出现「重排序」阶段；Golden Set MRR 有可见提升（依模型与延迟权衡）。

---

## 入库

### [2026-06-11] 同一份 PDF 重复 ingest，chunk 数翻倍

- **现象**：「数据浏览」里同一来源文档的分块数约为预期的 2 倍；重复 query 会命中内容相同、ID 不同的 chunk。
- **原因**：`IngestionPipeline` 的完整性检查默认**跳过已成功文件**；但 `force=True`（或面板「强制重跑」）会绕过跳过，**直接再次 upsert**，且不会先按 `source_hash` 删除旧分块。新一次分块若 ID 规则含随机/时间因素，会与旧 chunk 并存。
- **处理**：
  - 日常重跑：优先在「数据浏览」用 **按文档删除** 再 ingest，而非盲目 `force`。
  - 需要全量重建时：先 `DocumentManager` 删文档或清空 collection，再 ingest。
  - 理解 `ingestion_history.db` 按 **文件 SHA256** 记成功，与 collection 字段更新有关，但 `force` 仍可能叠 chunk。
  - **使用的技术 / 改动文件**：`pipeline.py`（`force` / `should_skip`）；`document_manager.py`（按 `source_hash` 删除）；`vector_upserter.py`（按 chunk id upsert）。
- **结果 / 待验证**：删后重入库 chunk 数稳定；Golden Set `expected_chunk_ids` 需在重入库后重新校准。

---

### [2026-06-13] 面板显示入库成功，Agent 仍搜不到

- **现象**：Dashboard 显示某 PDF「入库成功」、Chroma 统计有增量；agents-master 里 `query_knowledge_hub` 仍 0 命中。
- **原因**：多因素叠加——**(1)** Agent 查的 collection 与入库时不一致；**(2)** 文件曾在**另一 collection** 入库成功，完整性表标记 `success`，本次改库名 ingest 被 **skip**（`should_skip` 只看 hash，不看目标库）；**(3)** MCP 子进程缓存的 collection 与刚入库库名不同（较少见，向量 store 已按请求重建）。
- **处理**：
  - 入库页与 MCP 调用统一库名；用 `list_collections` 核对 **chunk_count**。
  - 若需把已成功文件导入新库：先删旧库文档或 `force=True` 并配合删除旧 chunk，避免静默 skip。
  - MCP `query_knowledge_hub` 每次按请求的 collection 重建 vector store，ingest 后**一般无需重启** rag-server 进程。
  - **使用的技术 / 改动文件**：`file_integrity.py`（`should_skip`）；`query_knowledge_hub.py`（`_ensure_initialized`）；`ingestion_manager.py`。
- **结果 / 待验证**：`list_collections` 与 Dashboard 分块数一致，Agent 指定 collection 后可命中。

---

### [2026-06-06] 正文能搜到，架构图 / 截图永远搜不到 → Image Caption

- **现象**：PDF 里流程图、截图类信息，用图中文字或场景描述去搜，Dense / BM25 均无命中；只有邻近正文提到时才能间接召回。
- **原因**：图片内容未进入可检索文本；纯文本分块不包含视觉语义。
- **处理**：
  - 入库链路增加 **ImageCaptioner**：识别 chunk 内 `[IMAGE: id]` 占位，对引用图片调 Vision LLM 生成描述，**拼回 chunk 文本 / metadata** 再 embedding 与 BM25 索引。
  - 仅处理 chunk **实际引用**的图片，caption 缓存避免重复调 Vision API；`vision_llm.enabled=false` 时优雅跳过。
  - **使用的技术 / 改动文件**：`image_captioner.py`、`config/prompts/image_captioning.txt`；`pipeline.py` Transform 阶段；`llm_factory.create_vision_llm`。
- **结果 / 待验证**：含示意图的复杂 PDF（如 `complex_technical_doc.pdf`）对图示相关 query 可召回；Vision 关闭时行为与旧版一致。

---

### [2026-06-30] PDF 明明有图，入库却显示 0 图片（PyMuPDF 未安装）

- **现象**：`面试八股笔记.pdf` 等含大量截图/示意图的 PDF，在「文档入库」成功后列表显示 **图片：0**；入库 Trace / 终端日志为 `Images extracted: 0`、`Indexed 0 images`；「知识浏览」展开该文档也无图片预览。
- **原因**：`PdfLoader` 依赖 **PyMuPDF**（`import fitz`）做图片抽取；当前运行环境未安装时 `PYMUPDF_AVAILABLE=False`，加载阶段直接跳过抽图并打 warning：`PyMuPDF not available, skipping image extraction`。文本仍正常入库，但不会产生 `[IMAGE: id]` 占位，后续 `ImageCaptioner` 也找不到可 caption 的图片。
- **处理**：
  - 在 **与 Streamlit / ingest 相同的 Python 环境** 安装：`python3 -m pip install -U pymupdf`，验证 `python3 -c "import fitz"` 无报错。
  - 安装后需 **重新入库** 该 PDF：因 `ingestion_history.db` 已将该文件 hash 记为 `success`，直接再传可能被 `should_skip` 跳过；推荐在「文档入库」列表 **先删除该文档**（清向量/BM25/图片索引/入库记录），再上传入库到目标 collection。
  - 或 CLI 强制：`python scripts/ingest.py --path <pdf> --collection <name> --force`（若仍遇 skip，配合先删文档更稳）。
  - **使用的技术 / 改动文件**：`pdf_loader.py`（`_extract_and_process_images`、PyMuPDF 可用性检测）；`pipeline.py` Stage 2 加载 + Stage 6c 图片索引；`image_captioner.py`（依赖 chunk 内 `[IMAGE: id]`）。
- **结果 / 待验证**：重装依赖并删后重入库后，日志出现 `Extracted N images`；面板文档行 **图片数 > 0**；`data/images/{collection}/{doc_hash}/` 有落盘文件；含图 query 可经 caption 进入检索（需 `vision_llm.enabled=true`）。

---

## Dashboard

### [2026-06-15] 改了 `settings.yaml` 里 rerank 开关，行为没变

- **现象**：本地把 `reranker.enabled` 改为 `true` 并保存，Streamlit 检索仍无「重排序」阶段，或 MCP Agent 侧排序与预期不符。
- **原因**：**进程与配置作用域不同**。Dashboard 页面每次 `load_settings()` 读盘，**本页内**新开查询会吃到新配置；但 **agents-master 已连接的 MCP 子进程**在会话期间持有旧 Settings 实例，且 Rerank / Hybrid 组件在工具内缓存；仅改 yaml **不会**热更新到已运行的 MCP Server。
- **处理**：
  - 改 `settings.yaml` 后：**重启 agents-master**（或重连 MCP Client），使 rag-server 子进程重新拉起。
  - 在 Dashboard 内验证：用「检索调试」或触发新 query 写 Trace，看是否出现 rerank stage。
  - 确认改的是 `rag-server/config/settings.yaml`，而非 agents-master 目录下的副本。
  - **使用的技术 / 改动文件**：`load_settings()`；`query_knowledge_hub.py` 组件缓存策略；`reranker.py` `enabled` 开关。
- **结果 / 待验证**：重启 MCP 后 Trace 出现重排序；Dashboard 直查与 Agent 行为一致。

---

### [2026-06-09] 不知道慢在 embed 还是 fusion，只能靠猜 → 用 stage 耗时定位

- **现象**：一次 query 端到端 2～3 秒，无法判断是 Embedding API 慢、BM25 慢还是 Rerank LLM 拖尾。
- **原因**：早期只有总耗时日志；缺少分阶段埋点，优化无从下手。
- **处理**：
  - 检索全链路挂 **TraceContext**：`query_processing` → `dense_retrieval` → `sparse_retrieval` → `fusion` → `rerank`，每阶段记录 `elapsed_ms` 与 `output_count`。
  - 「检索记录」页展示 **stage 瀑布条** + 各 Tab 明细；入库流水线同样在 `pipeline.py` 各 stage 写 trace。
  - **使用的技术 / 改动文件**：`trace_context.py`；`hybrid_search.py`、`dense_retriever.py`、`sparse_retriever.py`；`query_traces.py`（`get_stage_timings`、柱状耗时表）。
- **结果 / 待验证**：能直接读出「稠密 800ms、重排 1200ms」等，指导是降 `top_k` 还是换 Rerank 后端。

---

### [2026-06-07] 出问题只能翻 `traces.jsonl` → 检索记录页按 stage 回放

- **现象**：`logs/traces.jsonl` 单行 JSON 很长，肉眼对 dense/sparse 候选与融合前后顺序很困难。
- **原因**：缺少结构化 UI，Trace 能力无法发挥。
- **处理**：
  - 新增 **「检索记录」** 页：列表选 Trace → 总览指标（各路命中数）→ 耗时瀑布 → **分 Tab 回放**各阶段候选 chunk（含文本预览、score、chunk_id）。
  - 内嵌 **诊断提示**（空库、BM25 空、融合跳过、Rerank 未启用）。
  - 支持单条 **Ragas 评估**（需用户填 Answer），与批量 Golden Set 评估互补。
  - **使用的技术 / 改动文件**：`query_traces.py`；`data_service.py`（读 `traces.jsonl`）；`dashboard.py` 路由。
- **结果 / 待验证**：主链路排障基本不必手抠 JSONL；评估类问题仍见 [RAG评估调优专题.md](./RAG评估调优专题.md)。

---

### [2026-06-30] 知识浏览切到 agent_notes，分块内容却像 travel_plan

- **现象**：「知识浏览」先打开 `travel_plan` 看过分块，再切换到 `agent_notes` 时，文档列表文件名/分块数正确，但展开后 **分块正文全是旅行库内容**；元数据 JSON 与当前文档一致，仅 `text_area` 展示文本错位。
- **原因**：分块展示使用 `st.text_area(..., key=f"chunk_text_{idx}_{cidx}")`。Streamlit 组件 key 在 `session_state` 中跨 rerun 保留；切换 collection 后 **文档序号 idx 仍从 0 起**，key 与上一轮相同，控件复用旧 state 中的 value，导致显示上一库文本。后端 `DataService.get_chunks(source_hash, collection)` 实际取数正确，属 **展示层 widget state 污染**，非入库串库。
- **处理**：
  - 将 `text_area` 的 key 改为包含 **collection + doc_hash + chunk_id**，避免跨库/跨文档复用，例如 `chunk_text_{collection}_{source_hash[:8]}_{chunk_id}`。
  - 用户侧若未更新代码：切换知识库后 **硬刷新页面** 可临时规避。
  - 排障时可对照「入库记录」该文档的 split 阶段 chunk 文本，或查 Chroma `agent_notes` metadata 的 `source_path`，确认数据层无误。
  - **使用的技术 / 改动文件**：`data_browser.py`（分块 `st.text_area` 的 `key`）；读路径 `DataService.get_chunks` → `DocumentManager` / Chroma `where={"doc_hash": source_hash}`。
- **结果 / 待验证**：修复后 `travel_plan` ↔ `agent_notes` 来回切换，分块正文与元数据、文件名一致；`agent_notes` 下 `面试八股笔记.pdf` 等显示 Agent 笔记内容而非旅行文档。

---

## MCP联调

### [2026-06-05] agents-master 里 rag-server 子进程起不来：`cwd` 指错目录

- **现象**：Agent 初始化 MCP 时报 `No module named src.mcp_server` 或找不到 `config/settings.yaml`；单独在 `rag-server` 目录跑 `python -m src.mcp_server.server` 却正常。
- **原因**：`config.json` 里 `cwd` 指向仓库根或 `agents-master`，而非 **rag-server 项目根**；相对模块路径与配置文件解析基准错误。
- **处理**：
  - `cwd` 设为 `../rag-server`（与 agents-master 同级）。
  - `resolve_mcp_config()` 将相对路径解析为基于 agents-master 的绝对路径，并优先使用 `rag-server/.venv/bin/python`。
  - **使用的技术 / 改动文件**：`agents-master/config.json`；`agents-master/config/mcp_config.py`；说明见 [外接集成设计.md](../project-design/外接集成设计.md) §5。
- **结果 / 待验证**：`get_tools()` 能列出 rag-server 经 MCP 注册的三件套 Tool（含 `query_knowledge_hub`）。

---

### [2026-06-06] 第一次 `query_knowledge_hub` 卡很久像死锁

- **现象**：MCP Server 启动正常，首次调用检索工具 hang 住 30s+，Copilot / Agent 侧超时；之后再调又变快。
- **原因**：MCP SDK 用 anyio 在**后台线程**读 stdin；工具 handler 里 `asyncio.to_thread()` 在**工作线程**首次 `import chromadb`（连带 onnxruntime、numpy 等）时，与 stdin 线程争抢 Python **import lock**，可能死锁。
- **处理**：
  - 在 `run_stdio_server_async()` 启动 I/O 线程之前，主线程 **预加载** chromadb 及检索相关内部模块（`_preload_heavy_imports()`）。
  - 工具内仍 lazy import 业务代码，但 heavy 依赖已进 `sys.modules`。
  - **使用的技术 / 改动文件**：`src/mcp_server/server.py`（`_preload_heavy_imports` 及注释中的死锁说明）。
- **结果 / 待验证**：首次 query 延迟降为正常冷启动（主要是模型与索引加载），不再无限卡住。

---

### [2026-06-04] 调试 `print` 打到 stdout，Copilot 侧 MCP 报解析错

- **现象**：本地加 `print()` 调试后，MCP Client 报 JSON-RPC 解析失败、协议错乱；去掉 print 恢复。
- **原因**：stdio 传输规定 **stdout 仅用于 JSON-RPC 消息**；任何日志或 print 写入 stdout 都会污染帧，破坏协议。
- **处理**：
  - MCP 入口 `_redirect_all_loggers_to_stderr()`，把所有 `StreamHandler` 指到 **stderr**。
  - 项目统一 `observability/logger.py` 默认 `stream=sys.stderr`；CLI `ingest.py` / `query.py` / `evaluate.py` 错误信息也写 stderr。
  - 调试只用 `logger.debug()` 或 `print(..., file=sys.stderr)`。
  - **使用的技术 / 改动文件**：`server.py`；`observability/logger.py`；`main.py`。
- **结果 / 待验证**：开 INFO 日志时 MCP 连接稳定；Agent 多轮调用无协议错误。

---

### [2026-06-27] Agent 选库只靠 collection 名不靠谱 → 注册表 + 分场景定库

- **现象**：
  - 计划扩 `**agent_notes`** 等多库后，知识库问答模式靠 `list_collections` 选库，但返回只有 **库名 + 分块数**，模型常凭 `travel_plan` 等名字猜，易选错或漏传 `collection`。
  - 同一轮对话里若模型**不传** `collection`：`query_knowledge_hub` 默认 `**travel_plan`（硬编码）**，`get_document_summary` 默认 `**settings.yaml` 的 collection_name`**——两工具可能查**不同库**。
  - 旅行模式与问答模式行为不一致：旅行预取由代码传参，问答依赖模型自选，缺少统一「库说明」。
- **原因**：
  - **MCP 连接参数不含 collection**（`config.json` 只有 cwd/command）；库名在**每次工具调用**里指定。
  - `list_collections` 原输出为 Markdown 列表，无业务 **description**；Chroma metadata 也未写入领域说明。
  - 架构约定 **一次 `query_knowledge_hub` 只查一个 collection**，多库场景必须「先选库再检索」，但选库信息不足。
- **处理**：
  - **厘清三种定库方式（最终形态）**：

    | 场景                  | 谁定 collection                            | 行为                                                                                                                        |
    | ------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
    | **旅行模式预取**          | agents-master 代码 `pick_rag_collection()` | `list_collections`（可缓存）→ 优先 `travel_plan` → `travel` → `default` → 列表首项；**显式**传入 `query_knowledge_hub(..., collection=…)` |
    | **知识库问答**           | ReAct 模型按 prompt                         | 先 `list_collections` 看**说明与适用场景** → 再 `query_knowledge_hub` **每次只选一个库**；跨库则多次 query                                       |
    | **模型漏传 collection** | rag-server 工具默认                          | 检索 → `travel_plan`；摘要 → yaml（待后续统一为同一配置源）                                                                                 |

  - **最小改动落地：知识库注册表**
    - 新增 `config/collections.yaml`：`description`（必填）、`use_when`、`topics`。
    - `src/core/collection_catalog.py` 加载注册表。
    - `list_collections` 输出合并 Chroma 实库 + 注册说明，并提示 Agent「按说明选库再 query」。
  - **新增库维护**：入库（`--collection <名>`）→ yaml 增加同名条目 → 重启 MCP → `list_collections` 验证；详见 [知识库扩展计划.md](../知识库扩展计划.md) §8。
  - **使用的技术 / 改动文件**：
    - rag-server：`config/collections.yaml`、`collection_catalog.py`、`list_collections.py`
    - agents-master（既有）：`modes/travel/pipeline.py`、`facts.py`（`pick_rag_collection`）；`modes/knowledge_qa/system.md`（list → query 流程）
  - **后续可选**：`query_knowledge_hub` / `get_document_summary` 默认 collection 统一读 settings；库很多时加 LLM Router。
- **结果 / 待验证**：
  - `list_collections` 对 `travel_plan`、`agent_notes` 展示说明/适用/主题；问答模式选库不再仅靠库名。
  - 旅行预取仍走代码绑 `travel_plan`（当前单库数据下行为不变）。
  - `agent_notes` 入库并注册后，用项目类问题（如「Hybrid Search 怎么做的」）抽测是否选中正确库。

