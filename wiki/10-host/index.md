---
id: host/index
title: Host 域索引 · 主应用
tags: [index]
sources: []
related: []
updated: 2026-09-10
---

# 10-host · Host（agents-master）

> **TL;DR**：本域覆盖 Host（agents-master）——Streamlit UI + LangGraph ReAct Agent，负责对话、工具编排、多模式、会话与记忆。

## 页面

| 页面 | 主题 |
| --- | --- |
| [[host/architecture]] | 主应用架构与启动入口（`app.py` 拆分） |
| [[host/middleware]] | 中间件化改造方案（TurnMiddleware） |
| [[host/react-agent]] | ReAct Agent 与运行方式 |
| [[host/mcp-client]] | MCP 客户端、注册表与配置解析 |
| [[host/modes]] | 多模式 Agent 架构选型（registry） |
| [[host/prompts]] | Prompt 分层（通用 / 模式 / 动态上下文） |
| [[host/memory]] | 长短期记忆设计（四层） |
| [[host/travel-product]] | 需求与架构（智能行程规划） |
| [[host/travel-impl]] | 职责分层与步骤依据（智能行程规划） |
