---
id: analysis/token-optimization
title: 旅行模式 Token 消耗分析与优化
tags: [analysis, token, travel, performance]
sources:
  - agents-master/modes/travel/tool_memory.py
  - agents-master/modes/travel/pipeline.py
  - agents-master/modes/travel/facts.py
  - agents-master/export_service.py
  - agents-master/tool_truncation.py
related: [analysis/mcp-init-performance, host/travel-impl, host/memory]
updated: 2026-09-10
---
# 旅行模式 Token 消耗分析与优化

> **TL;DR**：旅行模式 Token 消耗高，根因是 Prompt 冗余、checkpoint 历史累积、导出双份全文、工具返回过长与改稿上下文重复；本文给出 O1–O13 优化项、瓶颈排序与回归测试建议。

> 文档版本：v1.6  
> 更新日期：2026-06-09  
> 适用项目：`agents-master`（Streamlit + LangGraph ReAct + 旅行规划工作流）

---

## 1. 现象

用户反馈：**使用旅行模式生成攻略时 Token 消耗过大**，表现为：

- 百炼免费额度在「生成阶段」容易耗尽（403 / AllocationQuota）
- 单次生成回合 LLM 调用次数多、耗时长
- 与通用问答相比，同等对话轮数下账单或配额消耗明显偏高

---

## 2. 根因分析

旅行模式的 Token 消耗并非来自单一环节，而是 **System Prompt + Checkpoint 历史 + 输出 + ToolMessage** 四类叠加。

### 根因结论（速查）

| # | 根因 | 结论 |
|---|------|------|
| 2.1 | System Prompt 冗余 | 每跳 ReAct 多带约 1200–2000 input tokens |
| 2.2 | Checkpoint 累积 POI/intake 的 ToolMessage | generating 阶段输入膨胀最重 |
| 2.3 | 对话 + 导出双份长文输出 | 输出 Token 近似翻倍（已改版） |
| 2.4 | 工具返回过长 × ReAct 步数过多 | 每跳带上千字符级 ToolMessage |
| 2.5 | 改稿上下文与 checkpoint 重复 | 改稿输入重复占 Token（已用 6A 缓解） |

### 2.1 System Prompt 冗余

**原状：** `general_system.md` + `travel-planner.md` 全量叠加，约 4800 字符/跳。

**现状（O1）：** `general_system_travel.md` + 精简 `travel-planner.md`；阶段细节交给 `[TRAVEL_CONTEXT]`。

### 2.2 Checkpoint 历史累积

- 每轮只发一条 `HumanMessage`，但 `MemorySaver` + `thread_id` 会累积全部 tool 消息。
- **UI `history` 与 Agent checkpoint 分离**；降 Token 靠换 `thread_id`，不靠删 UI 气泡。

### 2.3 双份全文输出

**现状（O5）：** 对话输出完整 MD 一次；`export_service` 服务端写文件（0 Token），不再让 LLM 通过 `write_markdown_document` 传第二遍 `content`。

### 2.4 工具返回过长

RAG/高德 JSON 单次可达数千字符 × ReAct 多跳；旅行阶段 `recursion_limit` 已按 phase 收紧（O8）。

### 2.5 改稿上下文重复

**现状（O11/6A）：** 改稿全文在 `[PREVIOUS_PLAN]`（优先导出文件），`[TRAVEL_CONTEXT]` 不再塞 12000 字 excerpt。

---

## 3. 优化前瓶颈排序

1. 生成阶段双份长文输出（§2.3）→ **已改版 O5**
2. generating 携带 POI/intake 工具历史（§2.2）→ **O2**
3. 工具返回过长 × 多步 ReAct（§2.4）→ **O7/O8/O10**
4. 冗长 System Prompt（§2.1）→ **O1**

---

## 4. 优化措施总览

> 图例：**✅ 已实现** · **🔄 改版** · **↩ 回退/不做** · **⏸ 暂缓/部分**  
> 编号 O1～O11 按 §2 根因顺序；O12 为调研项；**O13** 为记忆持久化（与 Token 正交）。

### 4.1 优化项总表

**节省估算口径：** 基线 = 优化前一次完整行程（poi + intake×2 + generating），总 Token 锚点 **~30 万**（in+out）；`scripts/estimate_travel_token_savings.py`。**各项不可简单相加。**

| # | 优化项 | 决策 | 较原先节省（估算） | 针对根因 | 当前做法 | 关键文件 |
|---|--------|------|-------------------|----------|----------|----------|
| O1 | 旅行专用精简 Prompt | **✅** | ~4.8 万（16%） | §2.1 | `general_system_travel.md` + 精简 `travel-planner.md` | `modes/travel/` |
| O2 | Checkpoint 裁剪（reset thread） | **✅** | ~11.6 万（39%） | §2.2 | 两重触发：①每轮工具后换 `thread_id`（主要）②POI→intake 边界兜底换 `thread_id`；原 O3 已回退 | `modes/travel/state_machine.py`、`modes/travel/tool_memory.py`、`ui/chat.py` |
| O5 | 导出双份输出 | **🔄** | ~0.3 万（1%） | §2.3 | 对话完整 MD + `export_service` 写文件 | `export_service.py`、`ui/chat.py` |
| O6 | MCP 工具返回截断 | **↩** | — | §2.4 | 已回退；改 O7 | `tool_truncation.py`（保留未启用） |
| O7 | 工具跨回合记忆 | **✅** | 配合 O2 才显著 | §2.4 | 回合结束摘要 → 下轮 `[TRAVEL_CONTEXT]` 注入 | `modes/travel/tool_memory.py` |
| O8 | 按阶段 ReAct 上限 | **✅** | 防失控 | §2.4 | intake 12 / poi 22 / 生成 32 | `travel_recursion_limit()` |
| O9 | 生成阶段工具清单 | **✅** | 质量约束 | §2.4 | `GENERATING_TOOL_CHECKLIST` | `modes/travel/state_machine.py` |
| O10 | 缓存 list_collections | **✅** | <1% | §2.4 | `rag_collections_cache` | `modes/travel/tool_memory.py` |
| O11 | 改稿 6A | **✅** | ~1%/次改稿 | §2.5 | `[PREVIOUS_PLAN]` 读导出文件 | `modes/travel/state_machine.py` |
| O12 | 分阶段不同模型 | **↩** | 0（只省费用） | — | 不做 | — |
| O13 | 会话结构化持久化 | **✅** | **0 Token** | — | 快照/归档/恢复；**不进 LLM** | `session_store.py`、`ui/sidebar.py` |

**已落地主项 O1+O2+O5+O10 合计约 ~16.8 万（~56% 基线，非严格可加）。**

---

### 4.2 O1 精简 Prompt

`general_system_travel.md` 替代通用底座；`travel-planner.md` 仅保留共性约束。

---

### 4.3 O2 Checkpoint 裁剪（reset thread）

**机制：** 通过更换 `thread_id` 清空 LangGraph checkpoint，防止工具历史在跨回合 ReAct 中累积。`travel_intake`、O7 工具摘要、UI 聊天历史不受影响。

**两重触发：**

| 触发点 | 位置 | 说明 |
|--------|------|------|
| 每轮工具后（主要） | `tool_memory.py` → `trim_checkpoint_after_tool_ingest()` | 每回合 Agent 回复后，只要有工具调用，先 O7 摘要入库再换 `thread_id` |
| POI→intake 边界（兜底） | `state_machine.py` → `should_reset_agent_thread_o9` | 防止无工具轮遗漏，POI 阶段结束进入 intake/generating 时换 `thread_id` |

**工作流程：**

| 步骤 | 行为 |
|------|------|
| 当轮 ReAct | ToolMessage **全量**（保证当轮推理） |
| 回合结束 | `ingest_tool_round_memory()` → O7 摘要写入 session |
| 随即 | `trim_checkpoint_after_tool_ingest()` → **新 `thread_id`**，清空 LangGraph checkpoint |
| 下轮 | 靠 `[TRAVEL_CONTEXT]` 注入 O7 摘要，而非 checkpoint 全量 tool |

**原 O3（已回退）：** generating 入口 reset 因与 UI/改稿协同未定型而移除。

**与完整 Message Trimmer 差距：** 当前为"全量清空"而非逐条精确删除；未来可升级为 LangGraph Message Trimmer，保留部分有用对话历史。intake **无工具**多轮仍靠 checkpoint 累积 user/assistant（通常 Token 可接受）。

**O7 常量**（改后需重启 Streamlit）：

| 常量 | 值 | 含义 |
|------|-----|------|
| `TOOL_ENTRY_SUMMARY_MAX` | 500 | 单工具摘要最大字符 |
| `TOOL_MEMORY_INJECT_TURNS` | 6 | 注入最近 N 回合工具记忆 |

---

### 4.4 O5 导出改版

对话输出完整 Markdown → `auto_export_travel_plan_from_chat` / `export_service` 写盘 → UI 下载。

---

### 4.5 O6～O10 工具链

| 时机 | 做法 |
|------|------|
| 当轮 | ToolMessage 全量 |
| 回合结束 | O7 摘要入库 + O2 换 thread（有工具时） |
| 下轮 | `[TRAVEL_CONTEXT]` 注入摘要 + O10 跳过 list |

**O8 阶段上限：**

| 阶段 | recursion_limit |
|------|-----------------|
| intake | 12 |
| poi_selection | 22 |
| generating / revision | 32 |

---

### 4.6 O11 改稿 6A

`resolve_revision_plan_body` + 用户消息 `[PREVIOUS_PLAN]`；优先 `last_export_path` 文件。

---

### 4.7 O13 会话持久化（记忆层，0 Token）

- 每轮成功 → `data/sessions/latest.json`
- 新对话 → 归档至 `archives/`
- 刷新 → 侧边栏恢复

**不影响当轮 LLM 输入**；对话记忆的持久化与恢复见 [记忆系统现状与优化.md](../10-host/memory.md)。

---

## 5. 涉及文件一览

| 文件 | 变更性质 |
|------|----------|
| `modes/travel/general_system_travel.md` | O1 |
| `modes/travel/travel-planner.md` | O1 |
| `export_service.py` | O5 |
| `app.py` | 自动导出、session 初始化 |
| `modes/travel/state_machine.py` | O2、O11、偏好合并 intake |
| `modes/travel/tool_memory.py` | O2 trim、O7、O10 |
| `modes/travel/handler.py` | 回合编排、预取触发 |
| `session_store.py` | O13 快照/归档/恢复 |
| `ui/chat.py` | O2、O5、O7、自动保存 |
| `ui/sidebar.py` | 记忆面板、新对话/重置、恢复 |
| `tool_truncation.py` | O6 保留未启用 |
| `scripts/estimate_travel_token_savings.py` | Token 测算 |

---

## 6. 回归测试建议

| 步骤 | 操作 | 预期 |
|------|------|------|
| 1 | 切旅行模式 → 应用 | O1 Prompt 生效 |
| 2 | 目的地 → POI → 勾选 | 高德/RAG 调用；景点列表 |
| 3 | intake → 生成 | O2：intake 正常，无 POI 原始 JSON 依赖 |
| 4 | 生成攻略 | O5：完整 MD + 下载；无 write_markdown 长 content |
| 5 | 工具详情 | O10 少重复 list；O7 下轮有摘要 |
| 6 | 改稿 | O11：`[PREVIOUS_PLAN]` + 再导出 |
| 7 | POI/intake 有工具后下一回合 | O2：`thread_id` 已变（排障可打印）；回复仍连贯 |
| 8 | 刷新页面 | O13：提示恢复；记忆面板 intake/摘要一致 |
| 9 | 新对话（归档） | archives 有文件；当前页空白 |
| 10 | 触顶 32 步（可选） | O8：临时调高 generating 上限复测 |

---

## 7. 相关文档

| 文档 | 说明 |
|------|------|
| [记忆系统现状与优化.md](../10-host/memory.md) | 全 Agent 记忆类型与存储 |
| [MCP初始化性能分析与优化.md](./mcp-init-performance.md) | MCP 连接耗时 |
| [Agent工具调用失败案例与处理准则.md](./tool-failures.md) | CUQPS 降级 |
| [../project-design/旅行规划-职责分层与步骤依据(实现).md](../10-host/travel-impl.md) | Prompt/编排分工 |

---

## 8. 一句话总结

**O1/O2/O5/O7/O8/O9/O10/O11/O13 已落地**；**O3/O6/O12 不做或回退**；降 Token 主线 = **短 checkpoint（O2）+ 外置工具摘要（O7）+ 精简 Prompt（O1）+ 单份输出（O5）**；持久化（O13）与 Token 正交，支撑刷新恢复与面试演示。

## 关联

- 相关：[[analysis/mcp-init-performance]]
- 相关：[[host/travel-impl]]
- 相关：[[host/memory]]
