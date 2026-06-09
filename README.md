# ContextBridge Agent

基于 **LangGraph + MCP** 的多模式智能体工作台：Streamlit 聊天界面、旅行规划、RAG 检索与工具编排。本仓库为 **monorepo**，包含主应用与 RAG 服务两个子项目。

## 仓库结构

```
ContextBridge Agent/
├── agents-master/     # 主应用（Streamlit + LangGraph ReAct Agent）
├── rag-server/        # 模块化 RAG MCP Server（被 agents-master 通过 config.json 引用）
└── README.md
```

## 快速开始

### 1. 主应用（agents-master）

```bash
cd agents-master
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 填入 DASHSCOPE_API_KEY、AMAP_MAPS_API_KEY 等
streamlit run app.py
```

默认访问：http://localhost:8501

### 2. RAG 服务（rag-server，可选但推荐）

主应用 `config.json` 已配置 `rag-server` MCP，需先准备 RAG 配置：

```bash
cd rag-server
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config/settings.dashscope.example.yaml config/settings.yaml
# 编辑 settings.yaml，将 api_key 改为你的百炼 Key（与 agents-master/.env 中 DASHSCOPE_API_KEY 一致）
```

### 3. 高德地图 MCP（旅行模式）

```bash
cd agents-master
npm install   # 安装 @amap/amap-maps-mcp-server，避免 npx 冷启动
```

在 `.env` 中配置 `AMAP_MAPS_API_KEY`；`config.json` 不再存放密钥，启动时由 `resolve_mcp_config` 从环境变量注入。

## 密钥与配置约定

| 文件 | 是否入库 | 说明 |
|------|----------|------|
| `agents-master/.env` | ❌ | 从 `.env.example` 复制，本地填写 |
| `agents-master/config.json` | ✅ | MCP 服务定义，不含 API Key |
| `rag-server/config/settings.yaml` | ❌ | 从 `settings.dashscope.example.yaml` 复制 |
| `agents-master/data/`、`rag-server/logs/` | ❌ | 运行时数据 |

**切勿将真实 API Key 提交到 Git。**

## 开发文档

- `agents-master/docs/project-design/` — 架构与设计
- `agents-master/docs/test-analysis/` — Token、记忆、MCP 性能等分析与优化记录

## 许可证

个人学习/面试项目，按需自用。
