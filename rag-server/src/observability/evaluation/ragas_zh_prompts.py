"""Chinese-localized prompts for Ragas metrics (DashScope / 百炼场景)."""

from __future__ import annotations

import json
import typing as t


def zh_statement_generator_prompt(question: str, answer: str) -> str:
    """将回答拆成可验证的原子陈述（保持中文，禁止臆造原文没有的事实）。"""
    safe_question = json.dumps(question, ensure_ascii=False)
    safe_answer = json.dumps(answer, ensure_ascii=False)

    return f"""你是 RAG 质量评估助手。根据「问题」和「回答」，把回答拆成若干条可独立验证的**中文**陈述句。
要求：
1. 只拆分回答中**已经出现**的信息，不要补充、推断或翻译后添加新景点/新事实。
2. 不要使用代词，每条陈述应自洽完整。
3. 保留原文关键专名与表述（如景点名、数字）。

请仅输出 JSON，格式：
{{"statements": ["陈述1", "陈述2", ...]}}

--------示例-----------
输入: {{
  "question": "北京有哪些值得去的景点？",
  "answer": "北京值得去的景点包括故宫博物院和八达岭长城。"
}}
输出: {{
  "statements": [
    "北京值得去的景点包括故宫博物院。",
    "北京值得去的景点包括八达岭长城。"
  ]
}}
-----------------------------

输入: {{
  "question": {safe_question},
  "answer": {safe_answer}
}}
输出: """


def zh_nli_statement_prompt(context: str, statements: t.List[str]) -> str:
    """判断各陈述是否可由检索上下文直接支持。"""
    safe_context = json.dumps(context, ensure_ascii=False)
    safe_statements = json.dumps(statements, ensure_ascii=False, indent=2)

    return f"""根据「检索上下文」判断每条「陈述」是否可被上下文**直接支持**。
- verdict=1：上下文中有明确依据，或同义转述可推出。
- verdict=0：上下文未提及、相矛盾，或属于无依据推断。

请仅输出 JSON：
{{"statements": [{{"statement": "原陈述", "reason": "简短理由", "verdict": 0或1}}, ...]}}

检索上下文：
{safe_context}

待判断陈述：
{safe_statements}

输出: """


def zh_answer_relevancy_prompt(response: str) -> str:
    """从回答反推问题，并识别是否属于推脱式回答。"""
    safe_response = json.dumps(response, ensure_ascii=False)

    return f"""根据「回答」生成一个能用该回答作答的**中文**问题，并判断回答是否属于推脱/含糊（noncommittal）。
- noncommittal=1：仅当回答主要是「不知道」「无法确定」「没有相关信息」等推脱内容。
- noncommittal=0：回答给出了具体事实、景点、说明或列举（即使不完整也不算推脱）。

请仅输出 JSON：{{"question": "...", "noncommittal": 0或1}}

--------示例-----------
输入: {{"response": "我不知道。"}}
输出: {{"question": "（任意相关问题）", "noncommittal": 1}}

输入: {{"response": "北京值得去的景点包括故宫博物院和八达岭长城。"}}
输出: {{"question": "北京有哪些值得去的景点？", "noncommittal": 0}}
-----------------------------

输入: {{"response": {safe_response}}}
输出: """
