# agents-master 知识域地图（A 轨）

> 第一期 15 个知识点（5 域 × 3）。工作目录：`agents-master/`。设计文档见 `docs/project-design/`。

## A1 Host 整体架构

| ID | 知识点 | 关键路径 |
|----|--------|----------|
| A1.1 | monorepo 中主应用定位：MCP Host + Streamlit 工作台 | `agents-master/README.md`, 根 `README.md` |
| A1.2 | 启动链：`app.py` → Agent 初始化 → MCP 连接 | `agents-master/app.py` |
| A1.3 | UI 分层：sidebar / chat / 模式切换 | `agents-master/ui/sidebar.py`, `ui/chat.py` |

## A2 LangGraph ReAct Agent

| ID | 知识点 | 关键路径 |
|----|--------|----------|
| A2.1 | ReAct 循环与工具调用在对话中的体现 | `agents-master/app.py`, LangGraph 相关初始化 |
| A2.2 | 流式输出与工具调用详情展示 | `agents-master/ui/chat.py` |
| A2.3 | 模型列表与切换（`config/models.py` + `.env`） | `agents-master/config/models.py` |

## A3 多模式设计

| ID | 知识点 | 关键路径 |
|----|--------|----------|
| A3.1 | 三种模式职责：通用 / 旅行规划 / 知识库问答 | `agents-master/modes/general/`, `modes/travel/`, `modes/knowledge_qa/` |
| A3.2 | 模式注册与切换机制 | `agents-master/modes/registry.py`, `modes/types.py` |
| A3.3 | 旅行模式流水线（状态机、事实抽取、证据展示） | `agents-master/modes/travel/pipeline.py`, `state_machine.py`, `ui/travel_evidence.py` |

## A4 记忆与会话

| ID | 知识点 | 关键路径 |
|----|--------|----------|
| A4.1 | 会话存储与恢复 | `agents-master/session_store.py` |
| A4.2 | 长期记忆画像（Embedding + 召回） | `agents-master/memory_store.py`, `memory_recall.py`, `memory_pipeline.py` |
| A4.3 | 记忆与对话的集成点（何时写入/召回） | `agents-master/app.py`, `ui/sidebar.py` |

## A5 MCP Client 与配置

| ID | 知识点 | 关键路径 |
|----|--------|----------|
| A5.1 | `config.json` 结构与四类预置 MCP | `agents-master/config.json`, `docs/project-design/MCP设计与管理.md` |
| A5.2 | `resolve_mcp_config`：路径解析、venv 优先、密钥注入 | `agents-master/config/mcp_config.py`, `docs/project-design/MCP设计与管理.md` |
| A5.3 | 工具截断、导出服务、侧边栏动态增删 MCP | `agents-master/tool_truncation.py`, `export_service.py`, `ui/sidebar.py` |

## 追问深度要求（A 轨每题）

1. **架构**：在 ContextBridge 中扮演什么角色  
2. **功能设计**：解决什么问题、边界在哪  
3. **技术设计**：关键类/函数、数据流  
4. **亮点**：为何这样设计、替代方案对比  
5. **验证**：可运行命令或配置入口
