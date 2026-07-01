---
name: project-learn
description: "面试教练式项目学习：自动发现代码结构，按 10 大知识域 45 个知识点出题追问（≤4 轮）、评分、给出学习路径并记录进度。用户说「学习项目」「了解项目」「检验项目」「项目学习」「面试准备」「learn project」「study project」「knowledge check」时使用。"
---

# 项目学习（Project Learn）

通过引导式问答帮助用户掌握本项目。与用户的**所有交互使用中文**。

## 流程概览

```
项目发现 → 检查历史 → 用户意图 → 选知识域 → 选知识点
→ 生成题目 → 互动问答（≤4 轮追问）→ 评价
→ 学习指南 → 保存进度 → 继续或结束
```

---

## 阶段 1：项目发现

自主建立项目理解，**此阶段不向用户提问**。

1. 读 `DEV_SPEC.md` — 目标、架构、技术栈、模块设计
2. 读 `config/settings.yaml` — 配置系统
3. 列出 `src/` 目录树 — 模块结构（`core/`、`ingestion/`、`libs/`、`mcp_server/`、`observability/`）
4. 读关键入口：`main.py`、`scripts/ingest.py`、`scripts/query.py`
5. 列出 `tests/` — 测试策略概览

建立涵盖 **10 大知识域、45 个知识点** 的内部模型（见下表）。

### 知识域与知识点地图

| ID | 知识域 / 知识点 | 关键代码路径 |
|----|----------------|-------------|
| **D1** | **RAG Pipeline 整体架构** | |
| D1.1 | 端到端数据流：从文档上传到生成回答的完整链路 | `DEV_SPEC.md`, `main.py`, `scripts/` |
| D1.2 | 三层架构：core/ingestion/libs 各层职责与依赖方向 | `src/core/`, `src/ingestion/`, `src/libs/` |
| D1.3 | Pipeline 组装：配置驱动的组件组合 | `main.py`, `config/settings.yaml`, `src/core/settings.py` |
| D1.4 | 核心数据类型：Document、Chunk、QueryResult 等 | `src/core/types.py` |
| D1.5 | 入口脚本：CLI 职责划分与参数传递 | `scripts/ingest.py`, `scripts/query.py`, `scripts/evaluate.py` |
| **D2** | **Ingestion Pipeline** | |
| D2.1 | Pipeline 整体流程：加载到向量存储的阶段设计 | `src/ingestion/pipeline.py` |
| D2.2 | Chunking：RecursiveSplitter 分割逻辑与参数调优 | `src/ingestion/chunking/`, `src/libs/splitter/` |
| D2.3 | Transform 链：ChunkRefiner、MetadataEnricher 职责与顺序 | `src/ingestion/transform/` |
| D2.4 | Embedding：Dense/Sparse 双编码与 BatchProcessor | `src/ingestion/embedding/` |
| D2.5 | 存储层：VectorUpserter、BM25Indexer、ImageStorage 协同 | `src/ingestion/storage/` |
| **D3** | **Hybrid Search & Retrieval** | |
| D3.1 | Dense Retrieval：向量检索与 DenseRetriever | `src/core/query_engine/dense_retriever.py` |
| D3.2 | Sparse Retrieval：BM25 与 SparseRetriever | `src/core/query_engine/sparse_retriever.py` |
| D3.3 | Hybrid Search：RRF 算法与 Fusion 模块 | `src/core/query_engine/hybrid_search.py`, `fusion.py` |
| D3.4 | QueryProcessor：查询预处理与扩展 | `src/core/query_engine/query_processor.py` |
| D3.5 | Response：ResponseBuilder、CitationGenerator、MultimodalAssembler | `src/core/response/` |
| **D4** | **Rerank 机制** | |
| D4.1 | Reranker 抽象与工厂：BaseReranker、RerankerFactory | `src/libs/reranker/` |
| D4.2 | CrossEncoder Reranker：原理与实现 | `src/libs/reranker/cross_encoder_reranker.py` |
| D4.3 | LLM Reranker：重排序方案与 Prompt | `src/libs/reranker/llm_reranker.py` |
| D4.4 | Rerank 在检索 Pipeline 中的集成 | `src/core/query_engine/reranker.py` |
| **D5** | **MCP Server 协议** | |
| D5.1 | MCP 概述：JSON-RPC 交互模型 | `src/mcp_server/server.py` |
| D5.2 | Tool 注册：三个工具的定义与执行 | `src/mcp_server/tools/` |
| D5.3 | ProtocolHandler：路由、分发、能力协商 | `src/mcp_server/protocol_handler.py` |
| D5.4 | Server 生命周期与异常处理 | `src/mcp_server/server.py` |
| **D6** | **可插拔架构 & 配置** | |
| D6.1 | 五大工厂：LLM/Embedding/Reranker/VectorStore/Evaluator | `src/libs/*/factory*.py` |
| D6.2 | settings.yaml 与 Settings 加载 | `config/settings.yaml`, `src/core/settings.py` |
| D6.3 | LLM 多厂商：Azure/OpenAI/DeepSeek/Ollama | `src/libs/llm/` |
| D6.4 | Embedding 多后端对比与选型 | `src/libs/embedding/` |
| D6.5 | Base 类设计：接口抽象与扩展点 | `src/libs/*/base_*.py` |
| **D7** | **多模态处理** | |
| D7.1 | PDF 解析与 FileIntegrity 校验 | `src/libs/loader/` |
| D7.2 | Vision LLM 集成 | `src/libs/llm/azure_vision_llm.py`, `openai_vision_llm.py` |
| D7.3 | ImageCaptioner 与 Prompt 模板 | `src/ingestion/transform/image_captioner.py`, `config/prompts/` |
| D7.4 | 多模态 Chunk 存储与检索 | `src/ingestion/storage/image_storage.py`, `src/core/response/multimodal_assembler.py` |
| **D8** | **可观测性 & 评估** | |
| D8.1 | Trace：TraceCollector、TraceContext | `src/core/trace/` |
| D8.2 | Dashboard：Streamlit 分页与 Services | `src/observability/dashboard/` |
| D8.3 | 评估指标：Recall、Precision、MRR 等 | `src/observability/evaluation/`, `scripts/evaluate.py` |
| D8.4 | 评估框架：Composite/Custom/RAGAS | `src/libs/evaluator/`, `src/observability/evaluation/` |
| D8.5 | 日志系统 | `src/observability/logger.py` |
| **D9** | **测试 & 工程化** | |
| D9.1 | 测试分层：Unit/Integration/E2E | `tests/unit/`, `tests/integration/`, `tests/e2e/` |
| D9.2 | Fixtures 与 conftest：Mock 与测试数据 | `tests/conftest.py`, `tests/fixtures/` |
| D9.3 | pyproject.toml 工程配置 | `pyproject.toml` |
| D9.4 | 脚本入口设计 | `scripts/` |
| **D10** | **Document Manager & 幂等性** | |
| D10.1 | 文档去重：Hash 与重复检测 | `src/ingestion/document_manager.py`, `src/libs/loader/file_integrity.py` |
| D10.2 | 增量 Ingestion 与幂等性 | `src/ingestion/document_manager.py`, `pipeline.py` |
| D10.3 | Collection 管理与文档生命周期 | `src/ingestion/document_manager.py` |
| D10.4 | 文档状态追踪 | `src/ingestion/document_manager.py` |

> 共 10 域 × 3-5 知识点 = **45 个知识点**；每点可多次不同角度提问，题库 100+ 题。

---

## 阶段 2：检查学习历史

1. 尝试读取 `skills/project-learn/references/LEARNING_PROGRESS.md`
2. **文件不存在** → 首次学习，进入阶段 3
3. **文件存在** → 解析两张表：
   - **Domain Summary**：各域 ⬜/🔴/🔶/✅
   - **Sub-topic Progress**：各知识点状态（⬜ 未学、🔴 薄弱 ≤3、🔶 学习中 4-6、✅ 掌握 ≥7）
   - 统计已掌握数 / 45，找出最低分知识点供推荐

---

## 阶段 3：用户意图

用 `ask_questions`（中文）确认用户想做什么：

**问题 1 — 学习模式**（单选）：

| 选项 | 说明 |
|------|------|
| 🆕 学习新知识点 | 从未学/薄弱知识点中选 |
| 📖 复习已学内容 | 复习低分知识点 |
| 📋 查看学习进度 | 展示进度表后结束 |
| 🎯 Agent 推荐 | 自动选最优下一知识点 |

选 📋 → 展示 `LEARNING_PROGRESS.md` 全文后停止。

选 🎯 → 自动选知识点（优先：最弱域的 ⬜ → 🔴 → 最低分 🔶），跳过问题 2、3，直接进入阶段 4。

**问题 2 — 知识域**（单选，仅 🆕/📖）：列出 10 个域及完成度，如 `D1 RAG Pipeline [2/5 ✅] 🔶`。

**问题 3 — 知识点**（单选，问题 2 之后）：列出该域下各知识点状态；含「🎯 Agent 推荐」选项。

---

## 阶段 4：生成面试题

基于所选**知识点**（非整个域）：

1. **深读**该知识点对应源码（类定义、关键函数、配置段）
2. **动态生成**一道主题目（中文），必须锚定本项目真实代码
3. **内部准备**最多 4 道递进追问（暂不展示）
4. **避免重复**：查 Detailed History，换角度出题

### 出题原则

- 必须引用本项目真实代码/架构，禁止泛泛而谈
- 题目聚焦当前知识点，非整个域
- 追问递进：为什么这样设计 → 与替代方案对比 → 边界/异常 → 若重新设计怎么做
- 根据用户实际回答动态调整追问

### 多角度（重复学习同一知识点时换角度）

What / How / Why / Compare / Debug / Extend

### 展示格式

```
## 🎯 面试问题

**知识域**: [域名] > **知识点**: [知识点名]

**面试官问**: [结合本项目组件的具体问题]

请回答：
```

---

## 阶段 5：互动问答（≤4 轮追问）

```
第 0 轮：主题目 → 用户回答
第 1-4 轮：简要反馈 + 追问 → 用户回答
提前结束：用户说「结束」「pass」「跳过」，或回答已足够全面
```

每轮：
1. 肯定答对的部分（1-2 句，中文）
2. 提示遗漏点（1 句，不直接给答案）
3. 基于回答方向追问

追问格式：
```
### 第 N 轮追问

✅ **答得好**: [...]
💡 **提示**: [...]

**追问**: [...]
```

---

## 阶段 6：评价

问答结束后输出结构化评价报告（中文）：

- 知识域、知识点、追问轮数
- 回答亮点、需加强点
- 四维度评分：准确性、深度、代码关联、设计思维（各 X/10）
- 综合评分 X/10
- 学习进度：X/45 知识点已掌握

**评分规则**：四维平均，四舍五入到 0.5
- 9-10：专家级，能讲清设计取舍
- 7-8：扎实，知道怎么做和为什么
- 4-6：基础，知道是什么但不深
- 1-3：表面，需大量学习

---

## 阶段 7：学习指南

评价后立即给出针对性学习资源（中文）：

- 📂 相关代码（带路径与行号，3-5 个关键文件）
- 📄 相关文档（`DEV_SPEC.md`、`config/settings.yaml` 对应段）
- 🔗 外部概念（仅本项目未解释的，如 RRF、BM25，一句话说明）
- 💡 建议学习路径（含至少一条可运行的 hands-on 命令）

---

## 阶段 8：保存进度

更新 `skills/project-learn/references/LEARNING_PROGRESS.md`。

不存在则从 [references/LEARNING_PROGRESS.md](references/LEARNING_PROGRESS.md) 模板创建。

### 更新规则

1. **追加** Detailed History 一行（含 Sub-topic ID）
2. **更新** Sub-topic Progress：已学次数、最高分、最近分、状态（≥7 ✅、4-6 🔶、≤3 🔴、0 次 ⬜）
3. **重算** Domain Summary：已掌握数、已学习数、平均分、域状态
4. 更新 `Last updated`、会话 `#` 自增、`总进度: X/45 知识点已掌握`

---

## 阶段 9：继续或结束

保存后询问用户（中文）：

| 选项 | 动作 |
|------|------|
| 🔄 继续学习下一个知识点 | 回到阶段 3 |
| 🎯 Agent 推荐下一个 | 自动选题，进入阶段 4 |
| 📋 查看当前学习进度 | 展示进度表 |
| 🏁 结束本次学习 | 展示本次总结后停止 |

结束时的总结含：完成知识点数、平均得分、最强/最弱知识点、总进度百分比、下次建议学习的知识点。

---

## 关键路径

| 文件 | 用途 |
|------|------|
| `skills/project-learn/references/LEARNING_PROGRESS.md` | 学习进度（45 知识点） |
| `DEV_SPEC.md` | 项目规格与架构 |
| `config/settings.yaml` | 配置参考 |
| `src/` | 全部源码模块 |
| `tests/` | 测试策略 |
| `scripts/` | CLI 入口 |
