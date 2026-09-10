---
id: host/prompts
title: Prompt 分层
tags: [host, prompt]
sources:
  - agents-master/prompts/general_system.md
  - agents-master/modes/knowledge_qa/system.md
  - agents-master/modes/travel/general_system_travel.md
  - agents-master/modes/travel/travel-planner.md
  - agents-master/modes/travel/state_machine.py
related: [host/modes, host/architecture, host/travel-impl]
updated: 2026-09-10
---

# Prompt 分层

> **TL;DR**：Prompt 分三层——**通用 System**（`prompts/general_system.md`）、**各模式 System**（`modes/knowledge_qa/system.md`、`modes/travel/*.md`）、**动态回合上下文**（`state_machine` 生成的 `[TRAVEL_CONTEXT]`）；前两者在创建 Agent 时固定，后者每轮注入用户消息前。

## 是什么

| 层级 | 存储位置 | 何时生效 | 内容性质 |
| --- | --- | --- | --- |
| 通用 System Prompt | `prompts/general_system.md`（`prompts.load_general_system_prompt()`） | Agent 创建时 | RAG、导出、通用指令 |
| 知识库问答 System Prompt | `modes/knowledge_qa/system.md` | 知识库模式 Agent 创建时 | 选库策略、回答结构 |
| 旅行 System Prompt | `modes/travel/general_system_travel.md` + `travel-planner.md` | 旅行模式 Agent 创建时 | 阶段行为、MD 模板、工具顺序 |
| 动态回合上下文 | `modes/travel/state_machine.py` → `[TRAVEL_CONTEXT]` | **每一轮**用户消息前 | phase、intake 快照、工具 checklist、工具记忆 |

LLM 每轮实际读到：静态 System（通用或模式专用）+ 历史消息（LangGraph `MemorySaver` + `thread_id`）+ 本轮用户消息（旅行模式下为 `[TRAVEL_CONTEXT]` + 用户原文）。

## 为什么这样设计

- **Prompt 文件化**：通用与各模式提示词都放 `.md`，Python 只负责 `load` 与 `build`，改文案不必动代码。
- **静态与动态分离**：不随回合变化的部分（角色、工具说明）放 System；每轮变化的部分（阶段、已收集字段、工具 checklist）由 `state_machine` 动态拼接，避免把状态写死在提示词里。
- **旅行模式双层**：`travel-planner.md` 管「怎么写」（Markdown 模板、emoji、地图章节位置），`general_system_travel.md` 管「怎么调工具与守规则」（可信度、导出约束）。

## 怎么实现

- **通用模式**：`<ROLE>` 定义身份，`<RAG_TOOLS>` 规定「不确定 collection 先 `list_collections`」，`<DOCUMENT_EXPORT_TOOLS>` 规定导出触发条件与内容要求。
- **知识库问答**：`<RAG_TOOLS>` 强化选库提示（旅行类 → `travel_plan`；本项目 RAG/MCP → `agent_notes`），并规定「结论先行 → 要点分条 → 来源」的回答结构。
- **旅行模式**：`travel-planner.md` 固化 Markdown 章节顺序（`## 🗺️ 行程地图参考` 必须在第一个 Day 之前）与高德调用节制（单轮 ≤3 次，防 CUQPS）；`general_system_travel.md` 要求「查不到标待核实」、生成阶段勿调 `write_markdown_document`（系统自动写盘）。

## 关键代码锚点

| 位置 | 作用 |
| --- | --- |
| `agents-master/prompts/general_system.md` | 通用模式 System Prompt |
| `agents-master/modes/knowledge_qa/system.md` | 知识库问答 System Prompt |
| `agents-master/modes/travel/travel-planner.md` | 旅行 Markdown 与阶段规范 |
| `agents-master/modes/travel/general_system_travel.md` | 旅行角色与工具规则 |
| `agents-master/modes/travel/state_machine.py` | 生成 `[TRAVEL_CONTEXT]` 动态上下文 |

## 关联

- 相关：[[host/modes]]
- 相关：[[host/architecture]]
- 相关：[[host/travel-impl]]
