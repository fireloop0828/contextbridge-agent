# 旅行模式 MCP 与 RAG 能力展示优化建议

> 文档版本：v1.0  
> 更新日期：2026-06-12  
> 适用项目：`agents-master`（Streamlit + LangGraph ReAct + 旅行规划工作流）  
> 关联文档：[旅行模式 Token 消耗分析与优化](./旅行模式Token消耗分析与优化.md)、[多模式 Agent 架构选型](../project-design/多模式Agent架构选型.md)

---

## 1. 背景与问题

旅行模式在工程上已是一套完整工作流（阶段机、intake、Token 优化、自动导出），但**产品感知**上更像「一个会调工具的聊天 Agent」，**MCP 与 RAG 的差异化价值未充分外显**。

用户实际感受到的与通用模式差别，主要是「多问几轮 + 输出更长」，而非「有真实数据支撑的可信规划」。

---

## 2. 现状：能力在，展示不在

### 2.1 三层分工

```text
Python 编排（travel_mode.py）→ 算阶段、注入 [TRAVEL_CONTEXT]
Prompt checklist            → 建议 LLM 按序调 RAG / 高德
ReAct Agent                 → 实际调 MCP，把结果写进 Markdown
```

### 2.2 用户实际看到什么

| 环节 | 当前展示 |
|------|----------|
| POI 推荐 | 文字列表，来源标注依赖 LLM 自觉写「高德/RAG」 |
| 生成攻略 | 完整 Markdown；工具调用藏在 `🔧 工具调用详情` 折叠里 |
| 数据依据 | `## 数据依据` 章节，仍是 LLM 叙述，非结构化溯源 |
| RAG | `query_knowledge_hub` 返回片段，用户几乎看不到原文 |
| 高德 | 路线/天气变成正文「约 X 分钟」，无地图/卡片 |

### 2.3 结论

**串联做到了，差异化没做出来。** MCP/RAG 仍是实现细节，而非用户可感知、可点击、可信任的产品能力。

### 2.4 相关实现文件（速查）

| 模块 | 文件 |
|------|------|
| 阶段机与工具 checklist | `travel_mode.py` |
| 工具记忆与 RAG 集合缓存 | `travel_tool_memory.py` |
| 聊天与工具折叠 | `ui/chat.py`、`app.py`（`get_streaming_callback`） |
| Prompt | `prompts/general_system_travel.md`、`prompts/travel-planner.md` |
| 耗时拆分（含 RAG/高德） | `timing_log.py`、`ui/sidebar.py` |

---

## 3. 优化方向总览

| # | 方向 | 核心目标 | 投入 | 收益 |
|---|------|----------|------|------|
| 3.1 | 证据层（RAG 可见） | 用户能回答「这句话从哪来」 | 低 | 高 |
| 3.2 | MCP 结果卡片化 | 工具输出可扫读，非 JSON 墙 | 中 | 高 |
| 3.3 | 数据管道 + 写作 Agent | MCP/RAG 成为一等公民数据层 | 中高 | 高 |
| 3.4 | 交互式 RAG | 用户主动探索知识库 | 中 | 中 |
| 3.5 | 可信度 UI | 与纯 LLM 拉开差距 | 低 | 高 |
| 3.6 | 知识库运营 | RAG 有料才显得强 | 持续 | 高 |
| 3.7 | 对比演示模式 | 展示 Agent+MCP+RAG 组合价值 | 低 | 中（演示向） |

---

## 4. 分项建议

### 4.1 证据层——让 RAG 可见（P0，性价比最高）

**做法：**

1. **编排层预取 RAG**：在 `poi_selection` / `generating` 阶段，Python 直接调 `query_knowledge_hub`，结果写入 `travel_facts`（或 `st.session_state.rag_evidence`），再注入 Agent。RAG 调用确定发生，且 UI 可复用。
2. **攻略正文加可点击引用**：如 `故宫建议早到 [RAG-1]`，侧边栏或文末展开对应 chunk（文档名、collection、原文摘要）。
3. **POI 阶段双源对照表**：

   | 景点 | 高德检索 | 知识库经典线路 | 用户选择 |
   |------|----------|----------------|----------|
   | 西湖 | ✓ 热门 | ✓ 必玩 | 必去 |

**与现有代码衔接：** 可沿用 `travel_tool_memory` 的跨回合摘要思路，升级为结构化 `travel_facts`，而非仅 500 字规则截断。

---

### 4.2 MCP 工具结果卡片化（P0～P1）

**做法：**

在流式回调或生成结束后，按工具类型渲染：

| 工具 | 卡片内容 |
|------|----------|
| `maps_weather` | 城市、日期、温度区间 |
| `maps_direction_*` | 起点→终点、距离、时长、交通方式 |
| `maps_text_search` / `maps_search_detail` | POI 名称、地址、评分（若有） |

生成完成后，攻略上方增加 **「本行程数据摘要」** 折叠区：多日天气 + 关键路段 2～3 条。

**进阶：** 高德静态图 API 或 embed 链接，在「逐日详情」旁放当日动线示意图。

**改动点：** `app.py`（`get_streaming_callback`）或新增 `ui/travel_evidence.py`；解析已有 `timing_log` / tool 输出 JSON。

---

### 4.3 数据管道 + 写作 Agent（P2，架构演进）

从「Agent 全程自主调工具」演进为：

```text
intake 齐全
  → 编排层：RAG 预检索 + 高德 POI/天气/路线
  → travel_facts.json（结构化中间产物）
  → 写作 Agent：编排成 Markdown + 引用
  → 证据面板 UI（与正文并行展示）
```

| 模式 | 优点 | 缺点 |
|------|------|------|
| 现状：ReAct 全程自主 | 灵活、实现简单 | 工具顺序不稳定、难结构化、用户看不见中间产物 |
| 演进：编排预取 + Agent 写作 | MCP/RAG 可测、可展示、省 Token | 需 Python 直调 MCP |

**建议：** `generating` 阶段由编排层拉齐 `travel_facts`，Agent 专注「可读攻略 + 可行性自检」。与《多模式 Agent 架构选型》中「单 Agent + Skill + handler」方向一致。

---

### 4.4 交互式 RAG（P3）

- 景点旁 **「查攻略详情」**：对该 POI 单独 `query_knowledge_hub`，侧边弹出片段。
- 侧边栏 **「本目的地可用知识库」**：展示 O10 已缓存的 `list_collections` 结果，用户可勾选优先 collection。
- 改稿 **「用知识库替换这一段」**：用户指出「第 2 天下午太赶」→ 定向重查 RAG + 重算路线。

RAG 从「生成时偷偷调一次」变为**用户可感知、可操控**的能力。

---

### 4.5 可信度 UI（P1）

对攻略内容打标（由编排层根据 `travel_facts` 是否有对应字段决定，**不靠 LLM 自说自话**）：

| 标记 | 含义 |
|------|------|
| 🟢 有工具依据 | 天气、路线、RAG 片段已命中 |
| 🟡 经验推荐 | RAG 弱相关或仅常识推断 |
| ⚪ 待核实 | 工具失败或未查到 |

侧边栏汇总示例：**12 处有高德数据 / 8 处来自知识库 / 3 处待核实**。

---

### 4.6 知识库运营（持续）

MCP 能力 = 工具 + 数据。RAG showcase 一半在 UI，一半在库质量。

- 按目的地建 collection（如 `travel_杭州`、`travel_大理`）。
- POI 阶段默认路由到对应 collection（编排层决定，不全靠 LLM 猜）。
- UI 提示：**「知识库覆盖：杭州 ✓ / 小众县城 ✗ → 将更多依赖高德」**。

---

### 4.7 对比演示模式（可选）

一次生成两个折叠版本：

- **仅 LLM**（禁用工具）
- **工具增强版**（完整流程）

并排对比天气是否瞎编、路线是否可执行。适合演示 ContextBridge「Agent + MCP + RAG」组合价值，可不作为常驻产品功能。

---

## 5. 推荐落地顺序

| 阶段 | 内容 | 预期效果 |
|------|------|----------|
| **P0** | `travel_facts` 结构 + 编排层预取 RAG/天气 + 攻略内引用 + 工具结果卡片 | 用户立刻感到「有依据」 |
| **P1** | POI 双源对照表 + 可信度标签 + 侧边「数据摘要」 | 差异化清晰，区别于通用聊天 |
| **P2** | `generating` 改为管道式（预取 → 写作） | 更稳、更省 Token、更好测 |
| **P3** | 地图可视化 + 交互式 RAG 深挖 + 目的地知识库建设 | 完整产品体验 |

---

## 6. 产品定位建议

**从：**

> 一个会帮你规划旅行的 Agent

**到：**

> **知识库 + 地图数据驱动的行程编辑器**——Agent 负责理解和排版，每一句重要结论都能追溯到 RAG 片段或高德查询。

---

## 7. P0 实施草图（供下一步开发参考）

### 7.1 数据结构（示意）

```python
# travel_facts.py（新建）或并入 travel_tool_memory.py
{
  "destination": "杭州",
  "phase": "generating",
  "rag": [
    {"id": "RAG-1", "collection": "travel_杭州", "query": "西湖 必玩", "excerpt": "...", "source_doc": "..."}
  ],
  "amap": {
    "weather": {...},
    "pois": [...],
    "routes": [...]
  },
  "coverage": {"rag_hits": 8, "amap_hits": 12, "unverified": 3}
}
```

### 7.2 调用时机

| phase | 编排层预取 |
|-------|------------|
| `poi_selection` | RAG 必玩/经典线路 + 高德 `maps_text_search` |
| `generating` | RAG 攻略片段 + `maps_weather` + 核心 POI + 2～3 段代表路线 |
| `revision` | 按用户修改项增量重查 |

### 7.3 UI 落点

| 组件 | 位置 |
|------|------|
| 证据折叠面板 | 助手消息下方（与 `render_export_downloads` 并列） |
| 数据摘要 | 侧边栏旅行模式 caption 下方 |
| 引用角标 | 正文 Markdown 后处理或生成时由 Prompt 约束 + 编排层校验 |

### 7.4 与 Token 优化的关系

- 编排层预取可减少 ReAct 多跳与重复 `list_collections`（与 O10 协同）。
- `travel_facts` 注入 `[TRAVEL_CONTEXT]` 替代部分冗长 ToolMessage 复述（与 O7/O4 方向一致）。
- 需实测：预取是否增加固定 MCP 调用 vs 减少 LLM 自主探索步数——见 `scripts/estimate_travel_token_savings.py` 扩展场景。

---

## 8. 验收标准（建议）

| 项 | 标准 |
|----|------|
| RAG 可见性 | 生成攻略中 ≥3 处可展开查看 RAG 原文摘要 |
| 高德可见性 | 天气与 ≥2 条路线以卡片或摘要展示，非仅正文叙述 |
| 可信度 | 侧边栏或文末有依据/待核实统计，与 `travel_facts` 一致 |
| 差异化 | 用户无需展开「工具调用详情」即可感知「非纯 LLM 编造」 |
| 稳定性 | `generating` 阶段核心 MCP 调用由编排层保证执行，不依赖 LLM 是否记得调工具 |

---

## 9. 相关文档

- [旅行规划-需求与架构(产品)](../project-design/旅行规划-需求与架构(产品).md)
- [旅行规划-职责分层与步骤依据(实现)](../project-design/旅行规划-职责分层与步骤依据(实现).md)
- [多模式 Agent 架构选型](../project-design/多模式Agent架构选型.md)
- [Agent 记忆系统现状与优化](./Agent记忆系统现状与优化.md)（L4 用户记忆 vs RAG 领域知识边界）
