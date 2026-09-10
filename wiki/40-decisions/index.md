---
id: decisions/index
title: 架构决策记录（域索引）
tags: [index]
sources: []
related: []
updated: 2026-09-10
---

# 40-decisions · 架构决策记录（ADR）

> **TL;DR**：本域记录「为什么这么做」的架构决策，避免结论散落；每篇 ADR 一页，格式为背景 → 选项 → 决策 → 后果。

## 页面

| 页面 | 决策主题 |
| --- | --- |
| [[decisions/0001-monorepo-split]] | 为什么 monorepo 双项目不合并 |
| [[decisions/0002-dual-venv]] | 为什么双 venv 隔离依赖 |
| [[decisions/0003-mcp-stdio]] | 为什么用 MCP stdio 而非 HTTP |
| [[decisions/0004-state-machine-outside-graph]] | 旅行状态机为何放在 LangGraph 之外 |
