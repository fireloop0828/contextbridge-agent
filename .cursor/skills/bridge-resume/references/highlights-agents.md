# agents-master 技术亮点（简历用）

> 主应用（LangGraph + MCP Host）。按需选取 2-4 条写入简历。

---

## 亮点 A1：LangGraph ReAct + MCP Host 工作台

**技术要点**：
- Streamlit 承载 LangGraph ReAct Agent，流式展示回答与工具调用
- `MultiServerMCPClient` 动态加载多 MCP Server 工具，无需改核心代码
- 侧边栏支持 Smithery JSON 增删 MCP，热重连生效

**简历话术**：
- "构建基于 LangGraph ReAct 的 MCP Host 工作台，通过标准 MCP Client 动态编排时间、地图、文档导出与 RAG 等工具"
- "实现 Streamlit 流式对话与工具调用可视化，支持运行时增删 MCP Server"

**可量化**：预置 MCP 数量（4）、支持模型数、工具调用成功率

---

## 亮点 A2：三模式应用架构

**技术要点**：
- **通用模式**：开放问答 + 全量工具
- **旅行规划模式**：高德 MCP + RAG + 状态机流水线，攻略自动导出
- **知识库问答模式**：聚焦 `list_collections` / `query_knowledge_hub` / `get_document_summary`

**简历话术**：
- "设计可插拔多模式架构（通用/旅行/知识库），按场景裁剪工具集与 Prompt，降低误调用与 Token 浪费"
- "旅行模式实现 POI/路线/天气工具链与 RAG 知识库联合规划，支持 Markdown 攻略一键导出"

**可量化**：模式数（3）、旅行模式工具链步骤数、导出成功率

---

## 亮点 A3：会话与长期记忆

**技术要点**：
- `session_store` 对话归档与恢复
- `memory_store` + `memory_recall`：Embedding 画像、跨会话召回
- 记忆面板与对话流程集成

**简历话术**：
- "实现会话持久化与基于向量召回的长期用户画像，支持跨轮对话上下文增强"

**可量化**：记忆条目数、召回命中率（建议值需用户确认）

---

## 亮点 A4：MCP 配置解析与安全

**技术要点**：
- `config.json` 声明 stdio MCP；`resolve_mcp_config` 解析相对路径、优先子项目 venv
- API Key 从 `.env` 注入，不入库 `config.json`
- `tool_truncation` 控制工具结果长度，优化 Token

**简历话术**：
- "设计 MCP 配置解析层，支持 monorepo 子进程 cwd、venv 优先与密钥环境变量注入，满足本地开发与合规要求"

---

## 亮点 A5：旅行模式工程化

**技术要点**：
- `modes/travel/`：pipeline、state_machine、facts 抽取、tool_memory
- `travel_evidence` UI 展示证据链
- 与 `export_service` 服务端写盘，减少 Agent 重复输出

**简历话术**：
- "实现旅行规划专用状态机与证据展示链路，服务端自动导出攻略 Markdown，优化 Token 与用户体验"

**可量化**：规划阶段数、平均对话轮数、导出耗时

---

## 岗位倾向

| 岗位 | 优先亮点 |
|------|----------|
| Agent Engineer | A1 → A2 → A4 → A5 |
| LLM Application | A1 → A2 → A3 → A4 |
| 全栈 AI | A2 → A1 → A3 → A5 |
