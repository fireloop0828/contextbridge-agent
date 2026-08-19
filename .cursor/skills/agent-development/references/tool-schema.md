# Tool Schema 规范

## 1. 核心目标

Tool 是 Agent 与外部世界的接口。Schema 质量直接决定：

- Agent 能否**正确选择**工具 → 靠 `description`
- Agent 能否**正确传参** → 靠 `input schema` 的类型、约束、描述
- Agent 能否**从失败恢复** → 靠错误回传

## 2. description 写法

必须回答三件事：**做什么、何时用、参数含义**。

正例（`rag-server/src/mcp_server/tools/query_knowledge_hub.py`）——第一段讲做什么，第二段讲何时用与返回特点，最后列出参数：

```python
TOOL_DESCRIPTION = """Search the knowledge base for relevant documents.

This tool uses hybrid search (semantic + keyword) to find the most relevant
documents matching your query. Results include source citations for reference.

Parameters:
- query: Your search question or keywords
- top_k: Maximum number of results (default: 3, capped by config rerank.top_k)
- collection: Limit search to a specific document collection
"""
```

反例：只有一句「查询知识库」。Agent 不知道何时该用它、参数怎么填、返回长什么样。

## 3. input schema 规范

每个参数写清 `type`、`description`；有范围给 `minimum/maximum`；必填进 `required`；有默认值写 `default`。

正例：

```python
TOOL_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "检索问题或关键词"},
        "top_k": {"type": "integer", "default": 3, "minimum": 1, "maximum": 20},
        "collection": {"type": "string", "description": "限定检索的文档集合"},
    },
    "required": ["query"],
}
```

**要点**：

- 有默认值就写 `default`，减少 Agent 必须决策的维度。
- 有边界就写 `minimum/maximum`，避免越界值。
- `required` 只放真正必填的，可选参数不要强制。
- 参数描述写「值域语义」，不要重复参数名。

## 4. 参数校验与错误回传

分层处理（对照 `query_knowledge_hub` 的 handler 与 `_build_error_response`）：

1. **参数层**（`ValueError`）→ 返回 `isError=True` + 参数错误说明（哪个参数、为什么错）。
2. **业务层**（执行异常）→ 返回「错误信息 + 排查提示」（限流 / 配额 / 配置）。
3. **兜底层**（未知异常）→ 返回通用「内部错误」，不泄露堆栈与内部细节。

**原则**：错误信息是给 Agent（或人）看的，要能据此采取下一步动作，而不是一句「出错了」。

## 5. 返回内容设计

正例要点（`query_knowledge_hub`）：

- 返回结构含**引用（citations）**，Agent 能据此标注来源。
- 空结果用 `is_empty` 显式标记，而非返回空字符串让 Agent 猜。
- 多模态支持：`to_mcp_content()` 统一 text + image 块。

**原则**：返回内容「结构化 + 可引用 + 显式空态」。

## 6. 工具注册

- 每个工具独立文件（`tools/query_knowledge_hub.py`）。
- 模块级常量：`TOOL_NAME / TOOL_DESCRIPTION / TOOL_INPUT_SCHEMA`。
- `register_tool(protocol_handler)` 统一注册入口。

**原则**：工具定义与业务逻辑分离，schema 可单独审视、单独测试。

## 7. FastMCP 简化写法

轻量工具可用装饰器（正例 `agents-master/mcp_server_rag.py`）：

```python
@mcp.tool()
async def retrieve(query: str) -> str:
    """根据用户问题检索相关文档内容。"""
    ...
```

**适用判断**：

- 简单工具（单参数、字符串返回）→ 装饰器即可。
- 复杂工具（多参数、多态返回、错误分类、需要校验）→ 显式 schema + handler。

## 8. 检查清单

- [ ] `description` 回答了「做什么、何时用、参数含义」三件事
- [ ] 每个参数有 `type` + `description`；有边界/默认值已标注
- [ ] `required` 只含真正必填项
- [ ] 参数错误 → 可读说明（哪个参数、为什么错）
- [ ] 业务失败 → 可读 + 排查提示，不裸抛
- [ ] 未知异常 → 通用文案，不泄露堆栈
- [ ] 空结果显式标记（`is_empty` 等），不返回歧义空串
- [ ] 返回内容结构化、可引用
- [ ] 工具定义与业务分离，schema 可单独测试
