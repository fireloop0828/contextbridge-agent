# Prompt 模板

## 1. 四段式 System Prompt 结构

ContextBridge 的 `general_system.md` 用显式标签分区：

```
<ROLE>              角色定义
<RAG_TOOLS>         工具说明（按能力域分组）
<DOCUMENT_EXPORT_TOOLS>  工具说明（另一能力域分组）
<INSTRUCTIONS>      步骤化行为准则
<OUTPUT_FORMAT>     输出格式
```

**原则**：

1. 用显式标签分区（`<XXX> ... </XXX>`），而非大段散文。
2. 工具说明按「能力域」分组，每组讲清「何时用 + 怎么用 + 注意事项」。
3. 行为准则用「步骤化」表达，而非泛泛的「请专业回答」。

## 2. 角色段（ROLE）

简洁定义：你是谁、你能做什么、基本语气。

正例：

```
你是一个能够调用工具的智能助手。
你会收到用户问题，并通过工具来回答。
请选择最相关的工具；若无法回答，可尝试其他工具获取信息。
```

## 3. 工具段（TOOLS）

每组工具说明包含三要素：

- **列出工具名 + 一句话用途**
- **使用流程**（先调什么、再调什么）
- **边界约束**（什么情况不要用、不要编造）

正例（RAG 工具段）：明确「不确定 collection 先 list_collections」「回答须基于检索结果，不要编造」。工具说明不是工具清单的复读，而是「决策指南」。

## 4. 指令段（INSTRUCTIONS）

步骤化 + 明确准则：

```
步骤 1：理解问题
步骤 2：选择工具
步骤 3：回答问题
步骤 4：注明来源

准则：
- 使用工具后，回答须以工具输出为准
- ...
```

## 5. 输出段（OUTPUT_FORMAT）

给模板，减少格式漂移：

- 严格场景（强流程、机器解析）→ 固定模板 + 「不要偏离格式」。
- 灵活场景（开放问答）→ 默认格式 + 「用最佳判断」。

## 6. 阶段化上下文注入（强流程）

travel 模式不把 phase 写死在一个 System Prompt，而是**按 phase 动态注入**：

- `build_travel_context` 生成 `[TRAVEL_CONTEXT]` 块，内含 phase、intake、missing_fields、预取数据。
- `_phase_instruction` 按 phase 给出「本轮该做什么、勿做什么」。

正例：POI 阶段明确「勿生成完整攻略、勿调用 write_markdown_document」。

**原则**：把「变的部分」（phase/数据）注入运行时，把「不变的部分」（角色/规则）放 System Prompt。System Prompt 保持稳定，上下文按轮注入。

## 7. 确定性约束的写法

需要严格控制时，用「勿 / 必须 / 固定」等强词，并给 checklist：

正例（`POI_SELECTION_TOOL_CHECKLIST` 风格）：

```
【勿重复调用】maps_text_search、query_knowledge_hub（除非预取区明确为空）
【勿】生成完整攻略、勿调用 write_markdown_document
```

**原则**：自由度高用建议语气（「可以考虑」），自由度低用命令语气 + 清单（「必须 / 勿 / 固定」）。

## 8. 检查清单

- [ ] System Prompt 用显式标签分区（ROLE / TOOLS / INSTRUCTIONS / OUTPUT_FORMAT）
- [ ] 工具说明含三要素：用途、流程、边界
- [ ] 行为准则步骤化，非泛泛而谈
- [ ] 输出格式有模板，严格场景固定格式
- [ ] 变的部分（phase/数据）运行时注入，不变的部分（角色/规则）静态放置
- [ ] 低自由度场景用命令语气 + 清单
- [ ] Prompt 版本化：改动有记录，能回滚对比
