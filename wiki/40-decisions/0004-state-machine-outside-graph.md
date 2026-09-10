---
id: decisions/0004-state-machine-outside-graph
title: ADR-0004 旅行状态机放在 LangGraph 之外
tags: [adr, travel, state-machine, langgraph]
sources:
  - agents-master/modes/travel/state_machine.py
  - agents-master/modes/travel/handler.py
  - QA/fast-qa.md
related: [host/travel-impl, host/modes, host/react-agent, analysis/token-optimization]
updated: 2026-09-10
---

# ADR-0004 · 旅行状态机为何放在 LangGraph 之外

> **TL;DR**：旅行步骤多且**顺序敏感**，纯 ReAct 由 LLM 自行决定下一步会跳步、漏步、重复调工具；因此把阶段编排做成 LangGraph **图外**的 Python 状态机 + handler，图内仍保持单个 ReAct Agent。

## 背景

旅行模式要依次完成「POI 选点 → 需求采集 → 生成 → 改稿 → 导出」这类多步流程，且步骤之间有**硬依赖**（先有 POI 才谈路线，先有路线才谈天气，数据齐了才整合成稿）。纯 ReAct 让 LLM 每轮自行决定调用哪个工具，实际会出现：

- **跳步**：还没查 POI 就开始写行程。
- **漏步**：忘记查天气。
- **重复调工具**：同一 POI 反复查询，既慢又费 Token。

## 选项

| 选项 | 说明 |
| --- | --- |
| A. 把阶段编排做成 LangGraph 节点 | 用图结构表达流程，但节点增多、图复杂度上升 |
| B. 图外用 Python 状态机 + handler（**采用**） | 阶段规则与回合编排放在 `agent.invoke` 前后，图内仍是单个 ReAct |

## 决策

采用 **B**，职责拆成三块（见 [[host/travel-impl]]）：

- `state_machine.py`：管**阶段与规则**——定义阶段、合法跳转、intake 字段合并与推进条件。
- `handler.py`：管**回合编排**——在 `ui/chat.py` 中于 LangGraph 调用**前后**介入。`prepare_before_agent()` 推进 phase、决定本轮给 Agent 的输入；`process_after_agent()` 清洗回复、判定 `plan_ready`、组装导出正文。
- `pipeline.py`：管**阶段内 MCP 预取**——按当前 phase 异步调 RAG、高德等，解析结果写入 `facts`。

## 后果

**收益**

- **硬保顺序**：阶段只能按顺序推进，LLM 无法跳步；每阶段绑定工具与 handler，流程可预期、可调试、可展示进度。
- **图结构不变**：LangGraph 里始终是**单个 ReAct Agent**，复杂度外置而不改图。
- **Token 更省**：编排层预取把原始工具输出解析成结构化 `travel_facts`（如 RAG excerpt ≤400 字），不必把上万字 tool result 全塞进上下文（见 [[analysis/token-optimization]]）。

**代价**

- **编排逻辑分散**：状态机、handler、pipeline、facts 各自一个文件，理解成本高于单点逻辑，必须靠文档串起来。
- **阶段门禁依赖 facts 抽取质量**：`facts.py` 抽不准（目的地、天数、预算）会影响阶段推进判断。
- **ReAct 并未消失**：阶段内部仍由 ReAct 决定调用哪些工具与文案，因此是「硬编排 + 软推理」的组合，需要分别调试两层。

## 关联

- 相关：[[host/travel-impl]]
- 相关：[[host/modes]]
- 相关：[[host/react-agent]]
- 相关：[[analysis/token-optimization]]
