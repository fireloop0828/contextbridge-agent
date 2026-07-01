---
name: auto-dev
description: "按 DEV_SPEC.md 规格自动推进开发：同步 spec 分章、从排期表取下一任务、按架构实现代码、pytest 测试（≤3 轮自动修复）、更新进度（可选提交）。用户说「自动开发」「自动写代码」「一键开发」「auto code」「auto dev」「autopilot」或需要规格驱动全自动开发时使用。"
---

# 自动开发（Auto Dev）

一次触发完成：**读 spec → 找任务 → 写代码 → 跑测试 → 落盘进度**。

可选修饰：指定任务 ID（如 `自动开发 B2`），或加 `--no-commit` 跳过 git 提交。

---

## 流程

```
同步 Spec → 找任务 → 实现 → 测试（≤3 轮修复）→ 落盘
```

仅在结束时暂停等待用户确认是否提交；其余步骤自动执行。

> **⚠️ 关键：任何 `python`/`pytest` 命令前必须先激活 `.venv`（可重复执行）。**
> - **Windows**：`.\.venv\Scripts\Activate.ps1`
> - **macOS/Linux**：`source .venv/bin/activate`

## 参考文档索引

`skills/auto-dev/references/` 下各文件：

| 文件 | 内容 | 何时阅读 |
|------|------|----------|
| `01-overview.md` | 项目概览与目标 | 首个任务或需要项目背景时 |
| `02-features.md` | 功能规格 | 实现功能相关任务时 |
| `03-tech-stack.md` | 技术栈与依赖 | 选型或确定实现模式时 |
| `04-testing.md` | 测试规范 | 编写测试时 |
| `05-architecture.md` | 架构与模块设计 | 新建/修改模块时 |
| `06-schedule.md` | 任务排期与状态 | 每轮同步 Spec 时 |
| `07-future.md` | 未来路线图 | 规划或评估范围时 |

---

### 1. 同步 Spec

```powershell
python skills/auto-dev/scripts/sync_spec.py
```

然后读取排期文件获取任务状态：
- 读 `skills/auto-dev/references/06-schedule.md`

任务标记：

| 标记 | 状态 |
|------|------|
| `[ ]` / `⬜` | 未开始 |
| `[~]` / `🔶` / `(进行中)` | 进行中 |
| `[x]` / `✅` / `(已完成)` | 已完成 |

---

### 2. 找任务

优先取第一个「进行中」任务，否则取第一个「未开始」。用户指定了任务 ID 则直接用该 ID。

快速检查前置产物是否存在（仅文件级）。不一致时记警告并继续 — 仅当目标任务本身被阻塞时才停止。

---

### 3. 实现

1. **阅读相关 spec**（`skills/auto-dev/references/`）：
   - 架构：`05-architecture.md`
   - 技术细节：`03-tech-stack.md`
   - 测试规范：`04-testing.md`

2. **提取**：输入/输出、设计原则（可插拔？配置驱动？工厂？）、文件清单、验收标准。

3. **规划**：写代码前先列出要创建/修改的文件。

4. **编码** — 项目规则：
   - 以 spec 为唯一事实来源
   - 使用 `config/settings.yaml` 配置值，禁止硬编码
   - 匹配现有代码风格与模式

5. **同步写测试**：
   - 按 spec 放入 `tests/unit/` 或 `tests/integration/`
   - 单元测试 mock 外部依赖

6. **自审**：跑测试前确认计划内文件齐全、测试可 import。

---

### 4. 测试与自动修复

```
第 0..2 轮：
  对相关测试文件运行 pytest
  通过 → 进入步骤 5
  失败 → 分析错误、修复、重跑

第 3 轮仍失败 → 停止，向用户展示失败报告
```

---

### 5. 落盘

1. **更新 `DEV_SPEC.md`**（全局文件）：任务标记 `[ ]` → `[x]`
2. **重新同步**：`python skills/auto-dev/scripts/sync_spec.py --force`
3. **展示摘要并询问**：

```
✅ [A3] 配置加载与校验 — 完成
   文件: src/core/settings.py, tests/unit/test_settings.py
   测试: 8/8 passed
   提交: feat(config): [A3] implement config loader

   "commit" → git add + commit
   "skip"   → 结束
   "next"   → 提交并继续下一任务
```

用户回复 `next` 时，回到步骤 1 处理下一任务。
