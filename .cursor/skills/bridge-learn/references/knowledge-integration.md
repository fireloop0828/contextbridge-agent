# 全栈串联知识域（C 轨）

> 15 个知识点（5 组）。工作目录：仓库根 + `agents-master/` + `rag-server/`。  
> **标识（互斥，每点最多一个）**：**◆** 重亮点（面试开场必讲，全轨 3 处）｜**◇** 亮点（技术差异化，可写简历 bullet，全轨 2 处）｜**★** 重点（优先学习、常考，全轨 4 处）。  
> **本文档按「整体→局部、贴合联调主链路」的顺序排列**：自上而下 = 先全景串联 → 职责边界 → 模式×工具 → 进程生命周期 → 联调排障。  
> 域/组编号（**A1–A8、B1–B10、C1–C5**）与阅读顺序一致。  
> **边界**：入库实现细节、RAG 配置细项、混合检索算法 → **B 轨**。

## C1 基础串联

| ID | 知识点 | 关键路径 / 文档 |
|----|--------|----------------|
| C1.1 | monorepo 双项目职责划分 ◆ | 根 `README.md`, `agents-master/README.md` |
| C1.2 | 双 venv：agents-master 与 rag-server 为何分开 | 根 `README.md`, `agents-master/README.md` |
| C1.3 | 双配置对应：Host LLM（`.env`）vs RAG LLM/Embedding（`settings.yaml`）★ | 根 `README.md`「两套主配置如何对应」 |
| C1.4 | `config.json` 拉起 rag-server（`cwd`、stdio、`python -m`）★ | `agents-master/config.json`, `config/mcp_config.py`, `wiki/10-host/mcp-client.md` |
| C1.5 | 端到端调用链：提问 → ReAct → MCP → 检索 → Host 生成回答 ◆ | `agents-master/README.md`「完整 RAG 流程」 |

## C2 职责边界

| ID | 知识点 | 关键路径 / 文档 |
|----|--------|----------------|
| C2.1 | Host 与 rag-server 边界：谁检索、谁生成、为何不互相 import ◆ | `wiki/10-host/mcp-client.md` §1.5, `QA/integration-qa.md` C1.4 |
| C2.2 | 三链路区分：入库（B 轨）/ 检索（MCP）/ 导出（document-export）◇ | `agents-master/README.md`, `mcp_server_export.py`, `QA/integration-qa.md` |

## C3 模式 × 工具

| ID | 知识点 | 关键路径 / 文档 |
|----|--------|----------------|
| C3.1 | 三模式工具策略总览（全量 vs 裁剪 vs 强流程）★ | `wiki/10-host/mcp-client.md` §5, `wiki/10-host/modes.md` |
| C3.2 | 知识库问答：RAG 三工具与推荐调用顺序 ◇ | `modes/knowledge_qa/system.md`, `modes/knowledge_qa/mode.py`, `QA/integration-qa.md` |
| C3.3 | 旅行模式：高德 + RAG + 时间 + 导出组合 | `modes/travel/`, `config.json`, `wiki/10-host/travel-product.md` §2.5 |

## C4 进程与生命周期

| ID | 知识点 | 关键路径 / 文档 |
|----|--------|----------------|
| C4.1 | stdio 子进程 spawn；Host 退出时 MCP 子进程行为 ★ | `wiki/10-host/mcp-client.md` §4, `QA/integration-qa.md` |
| C4.2 | rag-server MCP 子进程 vs RAG dashboard 独立 Streamlit | 根 `README.md`, `agents-master/README.md`, `rag-server/dashboard.py` |
| C4.3 | 双 Streamlit 默认 8501 与端口冲突处理 | 根 `README.md`, `rag-server/scripts/start_dashboard.py` |

## C5 联调与排障

| ID | 知识点 | 关键路径 / 文档 |
|----|--------|----------------|
| C5.1 | 联调快速检查清单（Key / venv / cwd / 是否已入库有数据） | `agents-master/README.md` 常见问题, `wiki/10-host/mcp-client.md` §6.2 |
| C5.2 | 常见故障：chromadb 未装、检索无结果、embedding 模型不一致 | `agents-master/README.md`, `wiki/50-analysis/tool-failures.md` |

## 面试讲法速查

**◆ 重亮点（3）— 开场主线**

| ID | 一句话 |
|----|--------|
| C1.1 | Host 编排对话与工具，rag-server 负责入库与检索，MCP 解耦、互不 import |
| C1.5 | 主链路：提问 → ReAct → MCP stdio → 混合检索 → Host 生成回答 |
| C2.1 | 边界：rag-server 只检索不生成，Host 不直接操作向量库 |

**◇ 亮点（2）— 追问展开**

| ID | 一句话 |
|----|--------|
| C2.2 | 入库 / 检索 / 导出三链路职责分离，不可混用 |
| C3.2 | 知识库模式 RAG 三工具推荐顺序与误调防护 |

> 全栈岗四句话：**C1.1 → C1.5 → C2.1 → C2.2**；排障实操看 C1.4、C5.1。

## 与 B 轨的衔接提示

| C 轨问题 | 深入学 B 轨 |
|----------|-------------|
| collection 从哪来、如何入库 | B2 文档入库、B9 文档生命周期 |
| `query_knowledge_hub` 内部怎么检索 | B3 混合检索、B4 重排序 |
| `settings.yaml` vision/rerank/evaluation | B6 可插拔配置、B8 评估 |
