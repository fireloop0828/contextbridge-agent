---
name: bridge-resume
description: "为 ContextBridge Agent monorepo 生成简历项目经历（Agent 岗 + RAG 岗）：四段式结构、从 agents-master/rag-server/串联三份亮点库匹配、量化建议与面试追问。用户说「写简历」「bridge resume」「项目经历」「resume」「write resume」「ContextBridge 简历」时使用。"
---

# Bridge Resume

基于「写作原则 + 三份亮点库 + 用户画像」生成 **ContextBridge Agent** 定制化简历。

## 阶段 1：加载知识

1. [references/resume_principles.md](references/resume_principles.md) — 四段式、技术标签、反模式
2. [references/highlights-agents.md](references/highlights-agents.md) — 主应用（A 轨）
3. [references/highlights-rag.md](references/highlights-rag.md) — RAG 子系统（B 轨）
4. [references/highlights-integration.md](references/highlights-integration.md) — monorepo 串联叙事
5. 按需深读根 `README.md`、`agents-master/README.md`、`rag-server/DEV_SPEC.md` 对应章节

## 阶段 2：用户画像（ask_questions，中文，最多 5 题）

**问题 1 — 岗位侧重**（单选）：
- Agent Engineer / RAG Engineer / LLM Application / 全栈 AI / 两者兼顾（Agent+RAG 各写一条线）

**问题 2 — 目标岗位细项**（单选，与问题 1 联动）：决定关键词与亮点排序

**问题 3 — 业务背景**（自由文本）：必须引导用户描述真实场景；可选「通用框架」模式

**问题 4 — 技术侧重**（多选）：
- Host & ReAct / 多模式 / 记忆 / MCP 编排 / Hybrid Search / Ingestion / 可插拔架构 / 可观测性 / Skill 工程化 / monorepo 串联

**问题 5 — 特殊要求**（自由文本）：中英双语、bullet 数量、量化由 Agent 建议等

## 阶段 3：亮点匹配

| 岗位侧重 | 优先顺序 |
|----------|----------|
| Agent | highlights-agents A1→A2→A4 → integration I1→I2 → rag 选 1 条（如 MCP Server） |
| RAG | highlights-rag 1→3→4→6 → integration I2 → agents 选 1 条（如 A1 Host） |
| 兼顾 | integration I1→I2 + agents A2 + rag 1→2 + 各 2 bullet |

用户「技术侧重」多选覆盖默认排序。

## 阶段 4：四段式生成

严格遵循 `resume_principles.md`：

1. **背景** — ContextBridge 定位：多模式 Agent 工作台 + 可选 RAG 知识库；融入用户业务场景  
2. **目标** — Agent 能力 / 检索精度 / MCP 集成等可衡量目标  
3. **过程** — 4-6 条 bullet：动词开头，Host 与 RAG 分线或交织，夹带岗位关键词  
4. **结果** — 至少 3 个量化指标（标注建议值时需用户确认）

默认项目名称：**ContextBridge Agent — 多模式智能体与 RAG 工作台**（可改）。

### 量化参考

| 类型 | 建议范围 | 来源 |
|------|----------|------|
| Hit Rate@K | 85%-92% | rag-server 能力 |
| 端到端延迟 | 500ms-1500ms | 检索+生成 |
| MCP 预置数 | 4 | config.json |
| 模式数 | 3 | agents-master |
| 测试用例 | 1200+ | rag-server |
| Skill 体系 | 项目级 + rag-server 工程 skill | 本仓库 |

## 阶段 5：输出与迭代

按四段式模板输出；展示后征求反馈。

**面试追问预测**（3-5 条）：Agent 岗偏 MCP/多模式/记忆；RAG 岗偏 Hybrid/Rerank/幂等；兼顾岗各半。

## 放大策略与底线

| 允许 | 禁止 |
|------|------|
| 合理业务包装 | 伪造公司/产品名 |
| 建议量化（标注待确认） | 夸大未实现能力 |
| 「设计并实现」 | 虚构团队规模 |

不声称未实现技术（如 CLIP、未启用的 vision）；不声称 DEV_SPEC「未来扩展」已完工。

## 反模式检查

输出前确认无：泛化描述、工具堆砌、缺量化、被动语态、面试无法自圆的说法。
