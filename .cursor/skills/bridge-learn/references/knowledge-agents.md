# agents-master 知识域地图（A 轨）

> 31 个知识点（8 域）。工作目录：`agents-master/`。★ = 重点/亮点。  
> **本文档按「整体→局部、贴合主链路」的顺序排列**：自上而下 = 先 Host 全景 → ReAct 核心 → MCP 接工具 → 多模式 → Prompt → 旅行深挖 → 记忆 → 导出/Token 优化。  
> 域编号 A1–A8 与阅读顺序一致。

## A1 Host 整体架构

| ID | 知识点 | 关键路径 |
|----|--------|----------|
| A1.1 | monorepo 中主应用定位：MCP Host + Streamlit 工作台 ★ | `agents-master/README.md`, 根 `README.md` |
| A1.2 | 启动链：`app.py` → Agent 初始化 → MCP 连接 | `agents-master/app.py`, `docs/project-design/app.py架构说明与拆分建议.md` |
| A1.3 | UI 分层：sidebar / chat / 模式切换 | `agents-master/ui/sidebar.py`, `ui/chat.py` |

## A2 LangGraph ReAct Agent

| ID | 知识点 | 关键路径 |
|----|--------|----------|
| A2.1 | ReAct 循环与工具调用在对话中的体现 ★ | `agents-master/app.py` |
| A2.2 | 流式输出与工具调用详情展示 | `agents-master/ui/chat.py` |
| A2.3 | 模型列表与切换（`config/models.py` + `.env`） | `agents-master/config/models.py` |

## A3 MCP Client 与配置

| ID | 知识点 | 关键路径 |
|----|--------|----------|
| A3.1 | `config.json` 结构与四类预置 MCP ★ | `config.json`, `docs/project-design/MCP设计与管理.md` |
| A3.2 | `resolve_mcp_config`：路径解析、venv 优先、密钥注入 ★ | `config/mcp_config.py`, `docs/project-design/MCP设计与管理.md` |
| A3.3 | MCP Session 状态与重连策略 ★ | `app.py`, `ui/sidebar.py`, `docs/project-design/MCP设计与管理.md` §1.3–1.4 |
| A3.4 | stdio vs HTTP/SSE 传输差异 | `docs/project-design/MCP设计与管理.md` §4 |
| A3.5 | 侧边栏动态增删 MCP（Smithery JSON） | `ui/sidebar.py`, `docs/project-design/MCP设计与管理.md` §3.2 |
| A3.6 | 本地 MCP Server：`mcp_server_time` / `mcp_server_export` | `mcp_server_time.py`, `mcp_server_export.py` |

## A4 多模式设计

| ID | 知识点 | 关键路径 |
|----|--------|----------|
| A4.1 | 三种模式职责：通用 / 旅行规划 / 知识库问答 ★ | `modes/general/`, `modes/travel/`, `modes/knowledge_qa/` |
| A4.2 | 模式注册、`AgentMode` 接口与切换 | `modes/registry.py`, `modes/types.py` |
| A4.3 | 轻/重模式包选型（为何旅行用强流程） | `docs/project-design/多模式Agent架构选型.md` |
| A4.4 | 知识库模式：RAG 三工具策略与 `system.md` ★ | `modes/knowledge_qa/mode.py`, `modes/knowledge_qa/system.md` |
| A4.5 | `ModeBranding`、`on_enter`/`on_exit` 与 Agent 重建 | `modes/types.py`, 各 `modes/*/mode.py` |

## A5 Prompt 与意图识别

| ID | 知识点 | 关键路径 |
|----|--------|----------|
| A5.1 | Prompt 分层：通用 / 旅行 / 知识库三套 system ★ | `prompts/general_system.md`, `modes/travel/general_system_travel.md`, `modes/knowledge_qa/system.md` |
| A5.2 | `detect_intent` 与模式路由启发式 | `modes/knowledge_qa/mode.py`, `modes/travel/mode.py` |
| A5.3 | `prompts` 加载机制（`prompts/__init__.py`） | `prompts/__init__.py`, `docs/project-design/app.py架构说明与拆分建议.md` §2 |

## A6 旅行模式

| ID | 知识点 | 关键路径 |
|----|--------|----------|
| A6.1 | 五阶段状态机与各阶段职责 ★ | `modes/travel/state_machine.py`, `docs/project-design/旅行规划-职责分层与步骤依据(实现).md` |
| A6.2 | `pipeline` / `handler` 编排与 `[TRAVEL_CONTEXT]` | `modes/travel/pipeline.py`, `modes/travel/handler.py` |
| A6.3 | `facts` 抽取与 `tool_memory` | `modes/travel/facts.py`, `modes/travel/tool_memory.py` |
| A6.4 | 旅行证据展示 UI | `ui/travel_evidence.py`, `docs/project-design/旅行规划-需求与架构(产品).md` §2.6 |

## A7 记忆与会话

| ID | 知识点 | 关键路径 |
|----|--------|----------|
| A7.1 | 会话存储与恢复 | `session_store.py` |
| A7.2 | 长期记忆画像（Embedding + 召回）★ | `memory_store.py`, `memory_recall.py`, `memory_pipeline.py` |
| A7.3 | 记忆写入/召回触发条件与集成点 ★ | `app.py`, `ui/sidebar.py`, `docs/test-analysis/记忆系统现状与优化.md` |
| A7.4 | 记忆 Embedding 模型配置（`.env`） | `memory_store.py`, `.env.example` |

## A8 导出与 Token 优化

| ID | 知识点 | 关键路径 |
|----|--------|----------|
| A8.1 | `export_service` 服务端写盘 vs `document-export` MCP ★ | `export_service.py`, `mcp_server_export.py`, `modes/travel/pipeline.py` |
| A8.2 | `tool_truncation` 工具结果截断策略 ★ | `tool_truncation.py`, `docs/test-analysis/Token消耗分析与优化.md` |
| A8.3 | `timing_log` 与性能观测 | `timing_log.py`, `docs/test-analysis/MCP初始化性能分析与优化.md` |

## 追问深度要求（A 轨每题）

1. **架构**：在 ContextBridge 中扮演什么角色  
2. **功能设计**：解决什么问题、边界在哪  
3. **技术设计**：关键类/函数、数据流  
4. **亮点**：为何这样设计、替代方案对比  
5. **验证**：可运行命令或配置入口
