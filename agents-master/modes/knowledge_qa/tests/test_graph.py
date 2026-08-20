"""知识库问答图（LangGraph 编排）测试用例。

覆盖:
- 正常 RAG 检索回答流程（工具按序调用、参数正确）
- 空结果自动改写检索词重试（命中 / 重试耗尽如实回答）
- 非 RAG 问题直答（不调用工具）
- needs_summary 分支（get_document_summary）
- collection_hint 跳过选库 LLM 决策
- list_collections session 缓存
- rag_tools 解析两种返回格式（markdown 块 / JSON citations）
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modes.knowledge_qa import rag_tools  # noqa: E402
from modes.knowledge_qa.mode import build_agent  # noqa: E402

SYSTEM_PROMPT = "你是知识库问答助手，回答必须基于检索结果并标注来源。"

RAG_JSON = '{"needs_rag": true, "collection_hint": "", "needs_summary": false}'
NON_RAG_JSON = '{"needs_rag": false, "collection_hint": "", "needs_summary": false}'


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class FakeTool:
    def __init__(self, name: str):
        self.name = name
        self.calls: list[dict] = []

    async def ainvoke(self, args: dict):
        self.calls.append(args)
        return self._respond(args)

    def _respond(self, args: dict):
        raise NotImplementedError


class FakeListCollections(FakeTool):
    def __init__(self, names=None):
        super().__init__("list_collections")
        self._names = names or ["travel_plan", "company_manual"]

    def _respond(self, args):
        return {
            "collections": [
                {"name": n, "id": n, "document_count": 12} for n in self._names
            ]
        }


class FakeQueryHub(FakeTool):
    def __init__(self, empty_until: int = 0, results=None):
        """empty_until: 前 N 次调用返回空结果（用于测试重试）。"""
        super().__init__("query_knowledge_hub")
        self._empty_until = empty_until
        self._results = results or [
            [{"content": "故宫位于北京中轴线中心，是明清两代皇宫。",
              "source": "travel_plan/beijing_guide.md", "score": 0.92}]
        ]

    def _respond(self, args):
        idx = len(self.calls) - 1
        if idx < self._empty_until:
            return {"citations": [], "notice": "未找到与查询相关的内容"}
        results = self._results[min(idx, len(self._results) - 1)]
        return {"citations": results}


class FakeDocSummary(FakeTool):
    def __init__(self):
        super().__init__("get_document_summary")

    def _respond(self, args):
        return {"summary": "beijing_guide.md：北京攻略，涵盖故宫、长城、天坛。"}


class FakeModel:
    """可控假模型：按 system prompt 关键词返回固定决策。"""

    def __init__(self, classify_json: str, pick_collection: str = "travel_plan",
                 rewrite_query: str = "北京故宫"):
        self._classify_json = classify_json
        self._pick = pick_collection
        self._rewrite = rewrite_query
        self.classify_calls = 0
        self.pick_calls = 0
        self.rewrite_calls = 0

    async def ainvoke(self, messages):
        sys_text = next(
            (m.content for m in messages if getattr(m, "type", "") == "system"), ""
        )
        if "问题分类器" in sys_text:
            self.classify_calls += 1
            return _Msg(self._classify_json)
        if "选择最相关的集合" in sys_text:
            self.pick_calls += 1
            return _Msg(self._pick)
        if "检索词改写器" in sys_text:
            self.rewrite_calls += 1
            return _Msg(self._rewrite)
        return _Msg("unexpected")

    def astream(self, messages):
        sys_text = next(
            (m.content for m in messages if getattr(m, "type", "") == "system"), ""
        )

        async def gen():
            # 判断顺序很重要：system_prompt 本身可能含"检索结果"字样，
            # 需用更精确的分隔标记"【检索结果】"（仅检索有结果时出现）
            if "未检索到相关内容" in sys_text:
                yield AIMessageChunk(content="知识库中没有找到与问题相关的内容。")
            elif "【检索结果】" in sys_text:
                for token in ["故宫", "在", "北京。"]:
                    yield AIMessageChunk(content=token)
            else:
                yield AIMessageChunk(content="直答内容。")

        return gen()


class _Msg:
    def __init__(self, content: str):
        self.content = content


def _build(tools, model):
    return build_agent(tools=tools, model=model, system_prompt=SYSTEM_PROMPT)


async def _run_stream(graph, question: str) -> str:
    """跑图，收集 answer 节点产出的最终回答文本。"""
    texts: list[str] = []
    async for event in graph.astream(
        {"messages": [HumanMessage(content=question)]}, stream_mode="updates"
    ):
        for _node, update in event.items():
            for m in update.get("messages", []):
                if isinstance(m, (AIMessage, AIMessageChunk)):
                    texts.append(str(m.content))
    return "".join(texts)


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# 正常 RAG 流程
# ---------------------------------------------------------------------------
class TestRagFlow:
    def test_normal_rag_flow_tool_order_and_args(self):
        """正常 RAG：classify→list→select→query→answer，工具按序调用、参数正确。"""
        list_tool = FakeListCollections()
        query_tool = FakeQueryHub()
        model = FakeModel(classify_json=RAG_JSON)
        graph = _build([list_tool, query_tool, FakeDocSummary()], model)

        answer_text = _run(_run_stream(graph, "故宫在哪里？"))

        # 工具调用与参数
        assert list_tool.calls, "应调用 list_collections"
        assert query_tool.calls, "应调用 query_knowledge_hub"
        qargs = query_tool.calls[0]
        assert qargs["query"] == "故宫在哪里？"
        assert qargs["top_k"] == 5
        assert qargs["collection"] == "travel_plan", "应选定 travel_plan 集合"
        assert model.pick_calls == 1, "无 hint 时应调用选库 LLM 一次"
        # 流式回答基于检索结果
        assert "故宫" in answer_text and "北京" in answer_text

    def test_collection_hint_skips_pick_llm(self):
        """问题中带集合名：select_collection 直接用 hint，不再调选库 LLM。"""
        list_tool = FakeListCollections()
        query_tool = FakeQueryHub()
        model = FakeModel(
            classify_json='{"needs_rag": true, "collection_hint": "travel_plan", "needs_summary": false}'
        )
        graph = _build([list_tool, query_tool], model)

        _run(_run_stream(graph, "查询 travel_plan 集合：故宫在哪里？"))

        assert model.pick_calls == 0, "有 hint 时不应调用选库 LLM"
        assert query_tool.calls[0]["collection"] == "travel_plan"

    def test_summary_branch_calls_doc_summary(self):
        """needs_summary=True：query 后走 summarize 再 answer。"""
        list_tool = FakeListCollections()
        query_tool = FakeQueryHub()
        summary_tool = FakeDocSummary()
        model = FakeModel(
            classify_json='{"needs_rag": true, "collection_hint": "", "needs_summary": true}'
        )
        graph = _build([list_tool, query_tool, summary_tool], model)

        _run(_run_stream(graph, "总结一下故宫那篇文档的内容"))

        assert summary_tool.calls, "应调用 get_document_summary"
        sargs = summary_tool.calls[0]
        assert sargs["doc_id"] == "beijing_guide.md"
        assert sargs["collection"] == "travel_plan"


# ---------------------------------------------------------------------------
# 空结果重试
# ---------------------------------------------------------------------------
class TestRetryFlow:
    def test_empty_result_rewrites_query_and_retries(self):
        """首次检索为空→改写检索词重试→命中→回答。"""
        list_tool = FakeListCollections()
        query_tool = FakeQueryHub(empty_until=1)  # 仅第 1 次空
        model = FakeModel(classify_json=RAG_JSON)
        graph = _build([list_tool, query_tool], model)

        answer_text = _run(_run_stream(graph, "故宫在什么地方？"))

        assert len(query_tool.calls) == 2, "应检索两次"
        assert model.rewrite_calls == 1, "应改写一次检索词"
        assert query_tool.calls[1]["query"] == "北京故宫", "第二次应使用改写后的检索词"
        assert "故宫" in answer_text

    def test_empty_result_exhausted_tells_user_honestly(self):
        """检索一直为空→重试耗尽→如实告知，不编造。"""
        list_tool = FakeListCollections()
        query_tool = FakeQueryHub(empty_until=99)
        model = FakeModel(classify_json=RAG_JSON)
        graph = _build([list_tool, query_tool], model)

        answer_text = _run(_run_stream(graph, "故宫在哪里？"))

        # 初始 1 次 + 改写后重试直到耗尽（MAX_QUERY_RETRIES=2 → 共 3 次检索）
        assert len(query_tool.calls) == 3
        assert model.rewrite_calls == 2
        assert "知识库中没有找到" in answer_text or "未检索到" in answer_text


# ---------------------------------------------------------------------------
# 非 RAG / 工具缺失
# ---------------------------------------------------------------------------
class TestNonRag:
    def test_non_rag_question_skips_all_tools(self):
        """classify 判定非 RAG→直接 answer，不调用任何工具。"""
        list_tool = FakeListCollections()
        query_tool = FakeQueryHub()
        model = FakeModel(classify_json=NON_RAG_JSON)
        graph = _build([list_tool, query_tool], model)

        answer_text = _run(_run_stream(graph, "你好，今天天气怎么样？"))

        assert not list_tool.calls, "不应调用 list_collections"
        assert not query_tool.calls, "不应调用 query_knowledge_hub"
        assert "直答内容" in answer_text

    def test_no_rag_tool_connected_degrades_gracefully(self):
        """RAG 工具未连接（空工具列表）→图仍能跑完并给出回复。"""
        model = FakeModel(classify_json=RAG_JSON)
        graph = _build([], model)

        answer_text = _run(_run_stream(graph, "故宫在哪里？"))
        assert answer_text, "应有流式输出，不崩溃"


# ---------------------------------------------------------------------------
# 缓存
# ---------------------------------------------------------------------------
class TestCollectionCache:
    def test_collections_cached_after_first_fetch(self, monkeypatch):
        """list_collections 结果进 session 缓存，第二次不再调工具。"""
        import streamlit as st

        state: dict = {}
        monkeypatch.setattr(st, "session_state", state)

        tool = FakeListCollections()

        names1 = _run(rag_tools.fetch_collections({"list_collections": tool}))
        names2 = _run(rag_tools.fetch_collections({"list_collections": tool}))

        assert names1 == ["travel_plan", "company_manual"]
        assert names2 == ["travel_plan", "company_manual"]
        assert len(tool.calls) == 1, "第二次应命中缓存，不再调用工具"


class TestCollectionListParsing:
    def test_parse_markdown_output(self):
        """解析 rag-server list_collections 的 markdown 输出（1. **name** 行）。"""
        text = (
            "## Available Collections (2 total)\n\n"
            "选库提示：根据「说明」选择最匹配的 **collection**。\n\n"
            "1. **travel_plan** - 5 documents\n"
            "   - 说明：旅行攻略知识库\n"
            "   - 主题：travel, visa\n\n"
            "2. **agent_notes** - 8 documents\n"
        )
        assert rag_tools.parse_collections_from_tool_output(text) == [
            "travel_plan",
            "agent_notes",
        ]

    def test_parse_json_output(self):
        """兼容 JSON 形态（collections 数组 / 对象数组）。"""
        text = '{"collections": [{"name": "travel_plan"}, {"name": "agent_notes"}]}'
        assert rag_tools.parse_collections_from_tool_output(text) == [
            "travel_plan",
            "agent_notes",
        ]
        text = '[{"collection": "travel_plan"}]'
        assert rag_tools.parse_collections_from_tool_output(text) == ["travel_plan"]

    def test_parse_empty_or_unrelated(self):
        """空输入 / 无集合名内容返回空列表，不报错。"""
        assert rag_tools.parse_collections_from_tool_output("") == []
        assert rag_tools.parse_collections_from_tool_output("No collections found") == []

    def test_markdown_dedups(self):
        """同一集合名出现多次只保留一次。"""
        text = "1. **travel_plan** - 5 documents\n2. **travel_plan** - 5 documents"
        assert rag_tools.parse_collections_from_tool_output(text) == ["travel_plan"]


# ---------------------------------------------------------------------------
# rag_tools 解析
# ---------------------------------------------------------------------------
class TestParsing:
    def test_parse_markdown_block_format(self):
        """解析 rag-server 的 markdown 检索块（### [N] 格式）。"""
        raw = (
            "针对查询 '故宫' 找到 1 条相关结果\n"
            "### [1]\n"
            "**来源:** `travel_plan/beijing_guide.md`\n"
            "**相关度:** 0.92\n"
            "\n"
            "> 故宫位于北京中轴线中心，是明清两代皇宫，是世界文化遗产。\n"
        )
        items, meta = rag_tools.parse_rag_results(raw, query="故宫", collection="travel_plan")

        assert len(items) == 1
        assert items[0]["source_doc"] == "beijing_guide.md"
        assert items[0]["collection"] == "travel_plan"
        assert items[0]["score"] == "0.92"
        assert "故宫" in items[0]["excerpt"]

    def test_parse_json_citations_format(self):
        """解析 JSON citations 格式。"""
        raw = {
            "citations": [
                {"content": "长城全长两万余公里，是古代军事防御工程。",
                 "source": "travel_plan/great_wall.md", "score": 0.87},
                {"content": "登城建议避开节假日。",
                 "source": "travel_plan/visitor_tips.md", "score": 0.61},
            ]
        }
        items, _ = rag_tools.parse_rag_results(raw, query="长城", collection="travel_plan")

        assert len(items) == 2
        assert items[0]["source_doc"] == "great_wall.md"
        assert "长城" in items[0]["excerpt"]

    def test_parse_no_result_notice(self):
        """无结果：返回空列表 + notice 元信息。"""
        raw = {"citations": [], "notice": "未找到与查询相关的内容"}
        items, meta = rag_tools.parse_rag_results(raw, query="xxx", collection="c")

        assert items == []
        assert "未找到" in meta["notice"]

    def test_boilerplate_excerpt_filtered(self):
        """跳过检索摘要头 / 过短片段。"""
        raw = (
            "针对查询 'x' 找到 1 条相关结果\n"
            "### [1]\n"
            "**来源:** `a/b.md`\n"
            "\n"
            "> 针对查询\n"
        )
        items, _ = rag_tools.parse_rag_results(raw, query="x", collection="c")
        assert items == []


# ---------------------------------------------------------------------------
# 来源块格式化（界面回答后程序化追加）
# ---------------------------------------------------------------------------
class TestSourcesBlock:
    def test_format_sources_block_dedups_by_doc_keeps_highest_score(self):
        """同一文档多条命中取相关度最高的一条，其他文档各保留一条。"""
        results = [
            {"source_doc": "beijing_guide.md",
             "excerpt": "故宫位于北京中轴线中心，是明清两代皇宫。", "score": "0.61"},
            {"source_doc": "beijing_guide.md",
             "excerpt": "故宫是世界文化遗产，占地七十二万平方米。", "score": "0.92"},
            {"source_doc": "great_wall.md",
             "excerpt": "长城全长两万余公里，是古代军事防御工程。", "score": "0.87"},
        ]
        block = rag_tools.format_sources_block(results)

        assert block.startswith("\n---\n（来源：\n")
        assert block.endswith("）")
        assert "beijing_guide.md（故宫是世界文化遗产" in block
        assert "故宫位于北京中轴线" not in block, "同文档应取高分条目"
        assert "great_wall.md（长城全长两万余公里" in block
        assert block.count("- ") == 2

    def test_format_sources_block_empty_inputs(self):
        """空结果 / 无来源文档 → 返回空串，界面不追加。"""
        assert rag_tools.format_sources_block([]) == ""
        assert rag_tools.format_sources_block(
            [{"source_doc": "", "excerpt": "x", "score": "0.5"}]
        ) == ""

    def test_format_sources_block_strips_markdown_and_truncates(self):
        """要点去掉 markdown 符号并截前 N 字。"""
        results = [
            {"source_doc": "manual.md",
             "excerpt": "**标题**：这是一段非常长的说明文字，用于验证要点截断逻辑，超过二十四个字。",
             "score": 0.5}
        ]
        block = rag_tools.format_sources_block(results)

        assert "**" not in block
        assert "…" in block
        assert "manual.md（" in block


# ---------------------------------------------------------------------------
# 回答后处理钩子（来源块程序化追加）
# ---------------------------------------------------------------------------
class TestAfterAgentHook:
    def test_process_after_agent_appends_sources(self, monkeypatch):
        """session 中有来源块时追加到正文末尾。"""
        import streamlit as st

        from modes.knowledge_qa import mode as knowledge_qa_mode

        state = {
            "knowledge_qa_last_sources": "\n---\n（来源：\n- beijing_guide.md（故宫是世界文化遗产））"
        }
        monkeypatch.setattr(st, "session_state", state)

        out = knowledge_qa_mode.process_after_agent("故宫是世界文化遗产。")

        assert out.startswith("故宫是世界文化遗产。")
        assert "（来源：" in out
        assert "beijing_guide.md" in out

    def test_process_after_agent_no_sources_returns_unchanged(self, monkeypatch):
        """无来源块 / 正文已含来源 → 原样返回，不重复追加。"""
        import streamlit as st

        from modes.knowledge_qa import mode as knowledge_qa_mode

        monkeypatch.setattr(st, "session_state", {})
        assert knowledge_qa_mode.process_after_agent("正文。") == "正文。"

        state = {
            "knowledge_qa_last_sources": "\n---\n（来源：\n- a.md（要点））"
        }
        monkeypatch.setattr(st, "session_state", state)
        out = knowledge_qa_mode.process_after_agent("正文。\n（来源：- a.md）")
        assert out.count("（来源") == 1


# ---------------------------------------------------------------------------
# 记忆注入块剥离（[USER_MEMORY] 不进入 question / 检索词 / 状态）
# ---------------------------------------------------------------------------
class TestMemoryBlockStrip:
    def test_strip_user_memory_block_keeps_question(self):
        """剥离 [USER_MEMORY]...[/USER_MEMORY] 块及分隔符，保留真实问题。"""
        from modes.knowledge_qa.graph import _strip_user_memory_block

        raw = (
            "[USER_MEMORY]\n"
            "姓名：小明\n"
            "相关历史摘要：\n"
            "- 上次讨论了故宫\n"
            "[/USER_MEMORY]\n\n"
            "---\n\n"
            "故宫在哪里？"
        )
        assert _strip_user_memory_block(raw) == "故宫在哪里？"

    def test_strip_user_memory_block_no_block_unchanged(self):
        """无记忆块时原样返回。"""
        from modes.knowledge_qa.graph import _strip_user_memory_block

        assert _strip_user_memory_block("故宫在哪里？") == "故宫在哪里？"

    def test_extract_question_strips_memory_block(self):
        """extract_question 返回剥离后的干净问题，记忆不进 question。"""
        from modes.knowledge_qa.graph import extract_question
        from modes.knowledge_qa.graph import _last_human_question

        raw = (
            "[USER_MEMORY]\n姓名：小明\n[/USER_MEMORY]\n\n---\n\n查一下北京攻略"
        )
        state = {"messages": [HumanMessage(content=raw)]}
        out = _run(extract_question(state))
        assert out["question"] == "查一下北京攻略"
        assert "USER_MEMORY" not in out["question"]
