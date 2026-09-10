---
id: analysis/github-push-mode
title: GitHub 推送模式目标分析
tags: [analysis, tooling, git]
sources:
  - .cursor/rules
  - .cursor/skills
related: []
updated: 2026-09-10
---
# GitHub 推送模式目标分析

> **TL;DR**：把「提交并 push」做成可复用工作流的目标分析：两条触发路径（指令触发 / 功能点完成提醒）、分批 commit 划分原则、安全约束与明确不做的事。

> **状态：** 已落地（全局 Skill + 两阶段门禁 + 本项目薄层 Rule）  
> **仓库：** `fireloop0828/contextbridge-agent`（私有，`main` 直推）

## 目录

- [1. 目标](#1-目标)
- [2. 架构](#2-架构)
- [3. 两类核心能力](#3-两类核心能力)
  - [3.1 指令触发：「提交并 push」](#31-指令触发提交并-push)
  - [3.2 习惯触发：功能点完成提醒](#32-习惯触发功能点完成提醒)
- [4. 安全](#4-安全)
- [5. 分批 commit 的划分原则](#5-分批-commit-的划分原则)
- [6. 使用与维护](#6-使用与维护)
- [7. 明确不做](#7-明确不做)

---

## 1. 目标

本地放心改，到节点时一句话归档到远程：**过程可见、可拦截、不泄密**。


| 准则       | 做法                                      |
| -------- | --------------------------------------- |
| **可控**   | 仅当用户说「提交并 push」才动 git；不自动 commit / push |
| **可审**   | 两阶段门禁：先出计划 → 用户确认 → 再执行；不得跳过            |
| **语义清晰** | 按变更意图分批：同一功能一个 commit，无关改动不硬塞一起         |
| **安全**   | 不提交 `.env`、密钥、`data/` 等敏感内容             |
| **全局可用** | 任意 Cursor 项目、对话框口令触发；不必每仓库复制长规则         |


---

## 2. 架构

```text
用户：「提交并 push」 → 阶段 A（扫描+计划） → 「确认」 → 阶段 B（commit+push）

全局（所有项目）
├── ~/.cursor/skills/github-push-workflow/SKILL.md     ← 完整流程（唯一正文）
├── ~/.cursor/rules/github-push-workflow.mdc           ← 全局触发器（辅助）
└── Cursor User Rules                 ← 最稳的口令入口

本项目（contextbridge）
└── .cursor/rules/github-workflow.mdc                  ← 仅项目特例（远程、模块表）
```


| 层级         | 路径                                               | 职责                                                                                                               |
| ---------- | ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| 全局 Skill   | `~/.cursor/skills/github-push-workflow/SKILL.md` | 两阶段门禁、安全红线、分批与 message 规范                                                                                        |
| User Rules | Cursor Settings → Rules                          | 短触发器：口令时必读 Skill                                                                                                 |
| 项目 Rule    | `.cursor/rules/github-workflow.mdc`              | 默认 remote `fireloop0828/contextbridge-agent`、`main`；`rag-server/config/settings.yaml`、`config.json` MCP `env` 禁区 |


**维护原则：** 通用流程只改 Skill；项目 Rule 保持 10～30 行特例。

---

## 3. 两类核心能力

### 3.1 指令触发：「提交并 push」

**触发：** 用户明确说「提交并 push」（或同义表述）。

**Agent 行为：**

1. `git status` / `git diff` / `git log -3` — 看清全部改动
2. **安全扫描** — 排除禁区路径与 diff 中的密钥痕迹（见 §4）
3. **按变更意图分批** — 先读 diff 理解「改了什么、为什么改」，再归为若干逻辑提交（见 §5）
4. **输出提交计划** — 每个 commit 的内容、message 草案、文件清单
5. **用户确认** — 无异议后依次 `git add` → `commit` → 统一 `push`
6. **回报结果** — commit 列表 + 远程分支状态

未要求时：**不** commit、**不** push。

**口令：** `提交并 push` / `提交并推送` / `commit 并 push`  
**确认：** `确认` / `执行` / `好` / `按计划提交` / `OK`

> 「提交并 push」= 启动阶段 A，**不是**确认执行。

#### 阶段 A — 只出计划

同条回复内**禁止** `git add` / `commit` / `push`。

输出顺序：

1. `**## 安全扫描`** — 结论「通过 / 需处理」、风险文件
2. `**## 提交计划（待确认）**` — 分支、推送目标、各 commit 的 message 草案与文件清单

「需处理」时只给扫描结果，不出可执行计划。扫描通过则以「请确认」结尾并**停止**。

#### 阶段 B — 确认后执行

1. `git add`（仅计划内文件）
2. 复核 `git diff --cached`，与计划不一致则中止
3. `git commit`（中文 message，HEREDOC）
4. 明示 `git remote -v` + 当前分支
5. `git push`（禁止默认 `--force`）
6. 回报 commit 列表与 push 结果

### 3.2 习惯触发：功能点完成提醒

**触发：** 当前对话中一个功能点/任务块已落地（实现完成、测试通过或用户表示「这块做完了」）。

**Agent 行为：**

- 用一两句话总结「本段改了什么」  
- 轻量提醒：「若这版想留档，可以说 **提交并 push**」（进入阶段 A，不自动提交）  
- **不**自动提交、不反复催促

同一会话内同一功能点只提醒一次。

---

## 4. 安全

**通用禁区（无例外）：** `.env`、`data/`、`logs/`、`cache/`、`.venv/`、`node_modules/`、含 Key/Token/密码的文件。

**扫描：** `git status` + `git diff` + 密钥关键词检索；命中则停止提交。

**本项目补充：** 见 `.cursor/rules/github-workflow.mdc`。

**工程底座：** 仓库 `.gitignore` 完善；密钥仅放本地 `.env`。

---

## 5. 分批 commit 的划分原则

**主依据：变更意图** — 读 `git diff` / `git status`，回答「这一坨改动在解决什么问题」。  
**辅助参考：目录/模块边界** — 帮助命名、发现漏文件，**不能**仅凭路径机械拆分。

一个功能点常常横跨多个模块（例如同时改 `modes/travel/`、`ui/chat.py`、一篇 `docs/`）——应 **合并为同一 commit**，而不是按目录硬拆。

### 5.1 划分流程（Agent 执行顺序）

1. 通读全部 diff，列出独立的 **变更意图**
2. 将每个文件归入 **唯一** 一个意图；无法归入的，单独成 commit 或向用户确认
3. 检查同一意图是否漏了 prompts / docs / tests
4. 输出提交计划（意图说明 + 文件列表 + message 草案）→ 用户确认 → 执行

### 5.2 合并与拆分


| 规则     | 说明                                            |
| ------ | --------------------------------------------- |
| **合并** | 同一功能意图下的代码 + 对应文档 + 相关 prompt → **一个 commit** |
| **拆分** | 无关意图并存（如旅行优化 + RAG 文档各做各的）→ **多个 commit**     |
| **禁止** | 仅因路径不同就把同一功能拆成多个 commit；或把无关改动塞进一个 commit     |


### 5.3 Commit message

- **全中文**；格式：`类型（作用域）：标题`  
- 类型：`feat` / `fix` / `docs` / `refactor` / `chore` / `test`  （功能 / 修复 / 文档 / 重构 / 任务 / 测试）
- 写 **why**，示例：`chore（git）：强化提交推送两阶段门禁，防止跳过确认`

---

## 6. 使用与维护

### 本机一次性配置

1. 确认 `~/.cursor/skills/github-push-workflow/SKILL.md` 存在
2. User Rules 粘贴 `USER-RULES-粘贴片段.md` 中的触发段

### 日常使用（任意项目）

```text
你：提交并 push  →  Agent：扫描 + 计划
你：确认         →  Agent：commit + push
```

### 新项目

普通项目**不必**加文件；有专属 remote/禁区时再建薄层 `.cursor/rules/github-workflow.mdc`。

### 改哪里


| 改什么   | 位置                                               |
| ----- | ------------------------------------------------ |
| 通用流程  | `~/.cursor/skills/github-push-workflow/SKILL.md` |
| 全局触发  | User Rules                                       |
| 本项目特例 | `.cursor/rules/github-workflow.mdc`              |
| 设计说明  | 本文档                                              |


---

## 7. 明确不做

- 自动 commit / push  
- 未经确认的推送  
- 阶段 A 同条回复里执行 git 写入  
- 单 commit 跳过确认  
- 默认 force push  
- 扫描未通过仍出可执行计划  
- 日常 push 依赖 Automations / GitHub MCP

