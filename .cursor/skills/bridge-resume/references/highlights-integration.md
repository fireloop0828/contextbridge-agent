# 全栈串联亮点（简历用）

> monorepo 叙事：ContextBridge Agent = 主应用 + RAG 子系统。用于背景段或整合 bullet。

---

## 亮点 I1：Monorepo 双项目协作

**技术要点**：
- `agents-master/`：MCP Host、多模式 Agent UI
- `rag-server/`：生产级 RAG MCP Server（Hybrid Search + Chroma）
- 根 README 统一联调与密钥约定

**简历话术**：
- "采用 monorepo 架构，主应用通过 MCP stdio 子进程调用同级 RAG 服务，实现 Agent 与知识库解耦部署"

---

## 亮点 I2：端到端私有知识问答

**技术要点**：
- 用户 → Streamlit → LangGraph → MCP Client → rag-server 三工具 → 百炼 LLM 生成
- ingest 后 Agent 通过 `list_collections` / `query_knowledge_hub` 检索私有文档

**简历话术**：
- "打通从文档入库、混合检索到 Agent 对话的端到端链路，支持企业私有知识库问答与旅行场景知识增强"

**可量化**：支持文档规模、Hit Rate@K、端到端延迟（见 RAG 亮点）

---

## 亮点 I3：双配置与双 venv 工程实践

**技术要点**：
- 聊天模型：`agents-master/.env` + `config/models.py`
- RAG LLM/Embedding：`rag-server/config/settings.yaml`
- 百炼 Key 通常两处同源；rag-server 独立 venv 含 chromadb/mcp

**简历话术**：
- "设计主应用与 RAG 子系统分离配置与依赖隔离，兼顾 Host 轻量与检索栈重型依赖"

---

## 亮点 I4：Skill 驱动工程化（可选写入）

**技术要点**：
- 项目级 `.cursor/skills/`（bridge-learn、bridge-resume、create-skill）
- rag-server 工程 skill：setup、auto-dev、run-qa 等
- DEV_SPEC 驱动 RAG 模块迭代

**简历话术**：
- "建立 Agent Skill 工作流体系，覆盖环境配置、规格驱动开发、QA 与学习/简历生成，体现 AI 辅助工程化方法论"

---

## 整合叙事建议

**背景段**：多模式 Agent 工作台 + 可插拔 RAG 知识库，服务旅行规划与企业文档问答。

**过程段**：一条 bullet 写 Host/多模式（A 轨），一条写 RAG 检索（B 轨），一条写 MCP 串联（I2）。

**岗位**：
- **Agent 岗**：I1、I2 为主，RAG 作「知识中枢」一条
- **RAG 岗**：I2 为主，Host 作「MCP 集成场景」一条
