---
name: bridge-learn
description: "ContextBridge Agent 深度学习教练：分 A(agents-master)/B(rag-server)/C(全栈串联) 三轨，按知识点读代码出题、≤4 轮追问、五层深度（架构/功能/技术/亮点/验证）、评分与学习指南、记录进度。用户说「学习项目」「bridge learn」「了解 ContextBridge」「agents 学习」「rag 学习」「全栈串联」「learn project」「knowledge check」时使用。"
---

# Bridge Learn

通过引导式问答掌握 **ContextBridge Agent** monorepo。与用户的**所有交互使用中文**。

## 三轨说明

| 轨 | 范围 | 知识点数 | 知识地图 |
|----|------|----------|----------|
| **A** | agents-master（LangGraph Host、多模式、记忆、MCP Client） | 15 | [references/knowledge-agents.md](references/knowledge-agents.md) |
| **B** | rag-server（RAG 流水线、检索、MCP Server） | 45 | [references/knowledge-rag.md](references/knowledge-rag.md) |
| **C** | 双项目串联（配置、调用链、模式组合） | 8 | [references/knowledge-integration.md](references/knowledge-integration.md) |

## 流程概览

```
选轨(A/B/C) → 项目发现 → 检查进度 → 用户意图 → 选知识域/点
→ 深读代码 → 出题 → 互动问答(≤4轮) → 五层评价 → 学习指南 → 保存进度
```

---

## 阶段 0：选轨

用 `ask_questions`（中文）让用户选择：

| 选项 | 说明 |
|------|------|
| A agents-master | 主应用、多模式、记忆、MCP Client |
| B rag-server | RAG 摄取/检索/MCP Server（内容最完整） |
| C 全栈串联 | monorepo 如何拼起来 |
| 查看进度 | 读 `references/LEARNING_PROGRESS.md` 后停止 |

选定轨后，读取对应 `knowledge-*.md`，后续流程仅在该轨知识点范围内进行。

---

## 阶段 1：项目发现（静默，不向用户提问）

**A 轨**：

1. 根 `README.md`、`agents-master/README.md`
2. `agents-master/app.py`、`config.json`、`config/mcp_config.py`
3. `agents-master/modes/` 目录树
4. `agents-master/docs/project-design/` 文件名列表（按需深读）

**B 轨**：按 [knowledge-rag.md](references/knowledge-rag.md)「项目发现清单」执行。

**C 轨**：根 `README.md` + `agents-master/README.md`「完整 RAG 流程」+ [knowledge-integration.md](references/knowledge-integration.md)。

---

## 阶段 2：检查学习历史

读取 `.cursor/skills/bridge-learn/references/LEARNING_PROGRESS.md`（路径相对于仓库根）。

解析当前轨的 Domain Summary / Sub-topic Progress；统计已掌握数，找出最弱知识点供推荐。

---

## 阶段 3：用户意图

**问题 1 — 学习模式**（单选）：🆕 新学 / 📖 复习 / 📋 查看进度 / 🎯 Agent 推荐

选 📋 → 展示进度全文后停止。选 🎯 → 自动选最弱 ⬜ 或 🔴 知识点，跳过域选择。

**问题 2 — 知识域**（单选，仅 🆕/📖）：列出当前轨各域及完成度。

**问题 3 — 知识点**（单选）：列出该域下各点状态；含「🎯 Agent 推荐」。

---

## 阶段 4：生成题目

1. **深读**该知识点对应源码（类、关键函数、配置）
2. **动态生成**一道中文主题目，锚定本项目真实路径
3. 内部准备最多 4 道递进追问
4. 查 Detailed History，避免重复角度

### 五层深度（评价与学习指南须覆盖）

1. **架构** — 在 monorepo 中的位置  
2. **功能设计** — 解决什么问题、边界  
3. **技术/代码设计** — 关键模块与调用链  
4. **亮点** — 设计取舍、与常见方案对比  
5. **验证** — 至少一条可运行命令或配置入口

### 展示格式

```
## 面试问题

**轨**: [A/B/C] > **知识域**: [名] > **知识点**: [名]

**问**: [结合真实代码/配置的具体问题]

请回答：
```

---

## 阶段 5：互动问答（≤4 轮追问）

每轮：肯定答对部分 → 提示遗漏 → 基于回答追问。用户说「结束」「pass」「跳过」则进入评价。

---

## 阶段 6：评价（中文）

- 五层深度各 X/10 + 综合分 X/10
- 回答亮点、需加强点
- 当前轨进度：X/N 知识点已掌握

评分：9-10 专家级；7-8 扎实；4-6 基础；1-3 需重学。

---

## 阶段 7：学习指南

- 相关代码路径（3-5 个，带文件路径）
- 相关文档段落
- 外部概念（仅必要时，一句话）
- **Hands-on**：至少一条可在对应子目录运行的命令

---

## 阶段 8：保存进度

更新 `references/LEARNING_PROGRESS.md`：

1. Detailed History 追加一行（含轨 + 知识点 ID）
2. 更新对应 Sub-topic：已学次数、最高分、状态（≥7 ✅、4-6 🔶、≤3 🔴）
3. 重算 Domain Summary；更新 Last updated 与三轨汇总行

---

## 阶段 9：继续或结束

询问：继续下一知识点 / Agent 推荐 / 查看进度 / 结束本次学习。

---

## 关键路径

| 文件 | 用途 |
|------|------|
| `references/LEARNING_PROGRESS.md` | 三轨学习进度 |
| `references/knowledge-agents.md` | A 轨 15 点 |
| `references/knowledge-rag.md` | B 轨 45 点 |
| `references/knowledge-integration.md` | C 轨 8 点 |
