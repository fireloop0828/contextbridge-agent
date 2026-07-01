# 全栈串联知识域（C 轨）

> 第一期 8 个知识点。工作目录：仓库根 + `agents-master/` + `rag-server/`。

| ID | 知识点 | 关键路径 / 文档 |
|----|--------|----------------|
| C1.1 | monorepo 双项目职责划分 | 根 `README.md` |
| C1.2 | `config.json` 如何拉起 `rag-server`（`cwd`、stdio、`python -m`） | `agents-master/config.json`, `config/mcp_config.py` |
| C1.3 | 双 venv：agents-master 与 rag-server 为何分开 | 根 `README.md`, `agents-master/README.md` |
| C1.4 | 双配置对应：`.env` vs `settings.yaml`，百炼 Key 两处填 | 根 `README.md`「两套主配置如何对应」 |
| C1.5 | 端到端 RAG 调用链：用户提问 → ReAct → MCP → Hybrid Search → 回答 | `agents-master/README.md`「完整 RAG 流程」 |
| C1.6 | 三模式与工具集：知识库问答如何聚焦 RAG 三工具 | `modes/knowledge_qa/mode.py` |
| C1.7 | 旅行模式如何组合高德 MCP + RAG + 时间/导出 | `modes/travel/`, `config.json` |
| C1.8 | 双 Streamlit（主应用 8501 vs RAG 控制台）与端口冲突处理 | 根 `README.md`, `rag-server/scripts/start_dashboard.py` |

## 串联追问示例角度

- Host 与 Server 的职责边界（谁做检索、谁做生成）  
- 改 RAG 配置是否影响主应用聊天模型  
- ingest 后 Agent 如何知道 collection 名称  
- 旅行攻略导出与 MCP `document-export` 的分工
