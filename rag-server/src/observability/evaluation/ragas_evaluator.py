"""Ragas-based evaluator for RAG quality assessment.

This evaluator wraps the Ragas framework to compute LLM-as-Judge metrics:
- Faithfulness: Does the answer stick to the retrieved context?
- Answer Relevancy: Is the answer relevant to the query?
- Context Precision: Are the retrieved chunks relevant and well-ordered?

Design Principles:
- Pluggable: Implements BaseEvaluator interface, swappable via factory.
- Config-Driven: LLM/Embedding backend read from settings.yaml.
- Graceful Degradation: Clear ImportError if ragas not installed.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Sequence

from src.libs.evaluator.base_evaluator import BaseEvaluator

logger = logging.getLogger(__name__)

# Metric name constants
FAITHFULNESS = "faithfulness"
ANSWER_RELEVANCY = "answer_relevancy"
CONTEXT_PRECISION = "context_precision"

SUPPORTED_METRICS = {FAITHFULNESS, ANSWER_RELEVANCY, CONTEXT_PRECISION}

# 评测前剥离的 RAG 套话（避免干扰 Ragas）
_ANSWER_META_PREFIXES = (
    "根据知识库检索结果，",
    "根据知识库检索结果：",
    "根据检索结果，",
    "根据检索结果：",
    "根据知识库内容，",
    "根据知识库内容：",
)


def _import_ragas() -> None:
    """Validate that ragas and its metric APIs are importable."""
    try:
        from ragas.metrics.collections import Faithfulness  # noqa: F401
        from ragas.llms import llm_factory  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Ragas 评估依赖未就绪。请在 rag-server 虚拟环境中执行："
            " pip install 'ragas>=0.3.9,<0.4' datasets"
            f"（原始错误: {exc}）"
        ) from exc


def format_ragas_error(raw: str) -> str:
    """Translate common Ragas / DashScope errors into actionable Chinese hints."""
    lower = raw.lower()
    if "tool_choice" in lower:
        return (
            "百炼 API 不支持 Ragas 默认的 tool_choice 结构化调用。"
            "请重启 dashboard 以加载 DashScope JSON 模式修复；"
            "若仍失败，将 evaluation.llm_model 改为 qwen-plus 或 qwen-turbo。"
        )
    if "allocationquota.freetieronly" in lower or "free quota has been exhausted" in lower:
        return (
            "百炼免费额度已用尽（403）。请开通按量付费或关闭「仅使用免费额度」，"
            "或在 evaluation.llm_model 中换用仍有额度的模型。"
        )
    if len(raw) > 300:
        return raw[:300] + "…"
    return raw


class RagasEvaluator(BaseEvaluator):
    """Evaluator that uses the Ragas framework for LLM-as-Judge metrics.

    Ragas does NOT require ground-truth labels.  It uses an LLM to judge
    the quality of the generated answer against the retrieved context.

    Supported metrics:
        - faithfulness: Measures factual consistency with context.
        - answer_relevancy: Measures how relevant the answer is to the query.
        - context_precision: Measures relevance/ordering of retrieved chunks.

    Example::

        evaluator = RagasEvaluator(settings=settings)
        metrics = evaluator.evaluate(
            query="What is RAG?",
            retrieved_chunks=[{"id": "c1", "text": "RAG is ..."}],
            generated_answer="RAG stands for ...",
        )
        # metrics == {"faithfulness": 0.95, "answer_relevancy": 0.88, ...}
    """

    def __init__(
        self,
        settings: Any = None,
        metrics: Optional[Sequence[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize RagasEvaluator.

        Args:
            settings: Application settings (used to configure LLM backend).
            metrics: Metric names to compute. Defaults to all supported.
            **kwargs: Additional parameters (reserved).

        Raises:
            ImportError: If ragas is not installed.
            ValueError: If unsupported metric names are requested.
        """
        _import_ragas()

        self.settings = settings
        self.kwargs = kwargs

        if metrics is None:
            metrics = self._metrics_from_settings(settings)

        normalised = [m.strip().lower() for m in (metrics or [])]
        if not normalised:
            normalised = sorted(SUPPORTED_METRICS)

        unsupported = [m for m in normalised if m not in SUPPORTED_METRICS]
        if unsupported:
            raise ValueError(
                f"Unsupported ragas metrics: {', '.join(unsupported)}. "
                f"Supported: {', '.join(sorted(SUPPORTED_METRICS))}"
            )

        self._metric_names = normalised
        self._wrappers_cache: tuple | None = None

    # ── public API ────────────────────────────────────────────────

    def evaluate(
        self,
        query: str,
        retrieved_chunks: List[Any],
        generated_answer: Optional[str] = None,
        ground_truth: Optional[Any] = None,
        trace: Optional[Any] = None,
        **kwargs: Any,
    ) -> Dict[str, float]:
        """Evaluate RAG quality using Ragas LLM-as-Judge metrics.

        Args:
            query: The user query string.
            retrieved_chunks: Retrieved chunks (dicts with 'text' key or strings).
            generated_answer: The generated answer text. Required for Ragas.
            ground_truth: Ignored by Ragas (not needed for LLM-as-Judge).
            trace: Optional TraceContext for observability.
            **kwargs: Additional parameters.

        Returns:
            Dictionary mapping metric names to float scores (0.0 – 1.0).

        Raises:
            ValueError: If query/chunks are invalid or generated_answer is missing.
        """
        self.validate_query(query)
        self.validate_retrieved_chunks(retrieved_chunks)

        if not generated_answer or not generated_answer.strip():
            raise ValueError(
                "RagasEvaluator requires a non-empty 'generated_answer'. "
                "Ragas uses LLM-as-Judge and needs the answer text to evaluate."
            )

        contexts = self._extract_texts(retrieved_chunks)
        answer = self._normalize_answer(generated_answer)
        contexts = self._limit_contexts(contexts)

        try:
            result = self._run_ragas(query, contexts, answer)
        except Exception as exc:
            logger.error("Ragas evaluation failed: %s", exc, exc_info=True)
            raise RuntimeError(f"Ragas evaluation failed: {format_ragas_error(str(exc))}") from exc

        return result

    # ── private helpers ───────────────────────────────────────────

    def _run_ragas(
        self,
        query: str,
        contexts: List[str],
        answer: str,
    ) -> Dict[str, float]:
        """Execute Ragas collections metrics and return normalised scores.

        Ragas 0.4+ collections metrics use per-metric ``score()`` instead of
        the legacy ``evaluate()`` pipeline.  Each metric has its own signature:
        - Faithfulness / ContextPrecision: (user_input, response, retrieved_contexts)
        - AnswerRelevancy: (user_input, response)
        """
        from ragas.metrics.collections import (
            Faithfulness,
            AnswerRelevancy,
            ContextPrecisionWithoutReference,
        )

        # Build LLM / Embedding wrappers from settings
        llm, embeddings = self._build_wrappers()
        use_zh = self._use_chinese_prompts()

        scores: Dict[str, float] = {}

        for metric_name in self._metric_names:
            if metric_name == FAITHFULNESS:
                if use_zh:
                    score = self._run_async(
                        self._faithfulness_zh(llm, query, answer, contexts)
                    )
                    scores[metric_name] = float(score) if score == score else 0.0
                else:
                    m = Faithfulness(llm=llm)
                    result = m.score(
                        user_input=query, response=answer, retrieved_contexts=contexts,
                    )
                    scores[metric_name] = float(result.value) if result.value is not None else 0.0
            elif metric_name == ANSWER_RELEVANCY:
                if use_zh:
                    score = self._run_async(
                        self._answer_relevancy_zh(llm, embeddings, query, answer)
                    )
                    scores[metric_name] = float(score)
                else:
                    m = AnswerRelevancy(llm=llm, embeddings=embeddings)
                    result = m.score(user_input=query, response=answer)
                    scores[metric_name] = float(result.value) if result.value is not None else 0.0
            elif metric_name == CONTEXT_PRECISION:
                m = ContextPrecisionWithoutReference(llm=llm)
                result = m.score(
                    user_input=query, response=answer, retrieved_contexts=contexts,
                )
                scores[metric_name] = float(result.value) if result.value is not None else 0.0
            else:
                continue

        return scores

    @staticmethod
    def _run_async(coro: Any) -> Any:
        """Run async Ragas helper from sync evaluate()."""
        try:
            asyncio.get_running_loop()
            raise RuntimeError("RagasEvaluator.evaluate cannot run inside an active event loop")
        except RuntimeError as exc:
            if "active event loop" in str(exc):
                raise
            return asyncio.run(coro)

    async def _faithfulness_zh(
        self,
        llm: Any,
        query: str,
        answer: str,
        contexts: List[str],
    ) -> float:
        """Faithfulness with Chinese prompts (no statement hallucination)."""
        from ragas.metrics.collections._faithfulness import (
            NLIStatementOutput,
            StatementGeneratorOutput,
        )

        from src.observability.evaluation.ragas_zh_prompts import (
            zh_nli_statement_prompt,
            zh_statement_generator_prompt,
        )

        sg = await llm.agenerate(
            zh_statement_generator_prompt(query, answer),
            StatementGeneratorOutput,
        )
        if not sg.statements:
            return float("nan")

        context_str = "\n".join(contexts)
        nli = await llm.agenerate(
            zh_nli_statement_prompt(context_str, sg.statements),
            NLIStatementOutput,
        )
        if not nli.statements:
            return float("nan")

        faithful = sum(1 for item in nli.statements if item.verdict)
        return faithful / len(nli.statements)

    async def _answer_relevancy_zh(
        self,
        llm: Any,
        embeddings: Any,
        query: str,
        answer: str,
    ) -> float:
        """Answer relevancy: Chinese question generation + cosine only (no noncommittal zeroing)."""
        import numpy as np
        from ragas.metrics.collections._answer_relevancy import AnswerRelevanceOutput

        from src.observability.evaluation.ragas_zh_prompts import zh_answer_relevancy_prompt

        prompt = zh_answer_relevancy_prompt(answer)
        generated_questions: List[str] = []
        for _ in range(3):
            result = await llm.agenerate(prompt, AnswerRelevanceOutput)
            if result.question:
                generated_questions.append(result.question.strip())

        if not generated_questions:
            return 0.0

        question_vec = np.asarray(embeddings.embed_text(query)).reshape(1, -1)
        gen_question_vec = np.asarray(
            embeddings.embed_texts(generated_questions)
        ).reshape(len(generated_questions), -1)

        norm = np.linalg.norm(gen_question_vec, axis=1) * np.linalg.norm(
            question_vec, axis=1
        )
        cosine_sim = (
            np.dot(gen_question_vec, question_vec.T).reshape(-1,) / norm
        )
        return float(np.clip(cosine_sim.mean(), 0.0, 1.0))

    @staticmethod
    def _normalize_answer(answer: str) -> str:
        """Strip common RAG meta prefixes and extra blank lines."""
        text = answer.strip()
        for prefix in _ANSWER_META_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix):].lstrip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text

    def _limit_contexts(self, contexts: List[str]) -> List[str]:
        """Keep only top-N chunks for Ragas (reduces cross-topic noise)."""
        if not contexts:
            return contexts
        max_chunks = 3
        evaluation = getattr(self.settings, "evaluation", None)
        if evaluation is not None:
            max_chunks = int(getattr(evaluation, "ragas_max_context_chunks", 3) or 3)
        max_chunks = max(1, max_chunks)
        limited = contexts[:max_chunks]
        if len(contexts) > len(limited):
            logger.info(
                "Ragas using top %d/%d retrieved chunks for evaluation",
                len(limited),
                len(contexts),
            )
        return limited

    def _use_chinese_prompts(self) -> bool:
        evaluation = getattr(self.settings, "evaluation", None)
        if evaluation is None:
            return True
        return bool(getattr(evaluation, "ragas_chinese_prompts", True))

    @staticmethod
    def _make_async_openai_client(*, api_key: str, base_url: str | None) -> Any:
        """Build AsyncOpenAI client, honouring OpenAI-compatible base_url (e.g. DashScope)."""
        from openai import AsyncOpenAI

        kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return AsyncOpenAI(**kwargs)

    def _instructor_mode_for_llm(self, llm_cfg: Any) -> Any:
        """Pick instructor mode: DashScope needs JSON mode (no tool_choice=required)."""
        from instructor import Mode

        base_url = (getattr(llm_cfg, "base_url", None) or "").lower()
        if "dashscope.aliyuncs.com" in base_url or "aliyuncs.com" in base_url:
            logger.info("Ragas LLM: using instructor Mode.JSON for DashScope-compatible API")
            return Mode.JSON
        return Mode.TOOLS

    def _create_ragas_llm(self, llm_client: Any, model: str) -> Any:
        """Build Ragas InstructorLLM; JSON mode for百炼 compatibility."""
        import instructor
        from ragas.llms import InstructorLLM

        mode = self._instructor_mode_for_llm(self.settings.llm)
        patched_client = instructor.from_openai(llm_client, mode=mode)
        return InstructorLLM(
            client=patched_client,
            model=model,
            provider="openai",
            max_tokens=8192,
        )

    def _build_wrappers(self) -> tuple:
        """Build Ragas LLM and Embedding wrappers from project settings.

        Uses Ragas 0.4+ native API (InstructorLLM + OpenAIEmbeddings)
        instead of deprecated LangchainLLMWrapper.

        Returns:
            Tuple of (llm_wrapper, embeddings_wrapper).
        """
        if self._wrappers_cache is not None:
            return self._wrappers_cache

        from openai import AsyncAzureOpenAI
        from ragas.embeddings import OpenAIEmbeddings

        if self.settings is None:
            raise ValueError("Settings required to create LLM for Ragas evaluation")

        # ── LLM ──
        llm_cfg = self.settings.llm
        provider = llm_cfg.provider.lower()
        llm_azure_endpoint = getattr(llm_cfg, "azure_endpoint", None)

        # Azure-compatible mode: if azure_endpoint is configured, use Azure
        # client even when provider is "openai" (matches project convention).
        use_azure_llm = (
            provider == "azure"
            or (provider == "openai" and llm_azure_endpoint)
        )

        if use_azure_llm:
            llm_client = AsyncAzureOpenAI(
                api_key=llm_cfg.api_key,
                azure_endpoint=llm_azure_endpoint or llm_cfg.azure_endpoint,
                api_version=getattr(llm_cfg, "api_version", None) or "2024-02-15-preview",
            )
        elif provider == "openai":
            llm_client = self._make_async_openai_client(
                api_key=llm_cfg.api_key,
                base_url=getattr(llm_cfg, "base_url", None),
            )
        else:
            raise ValueError(
                f"Unsupported LLM provider for Ragas: '{provider}'. "
                "Supported: azure, openai"
            )

        ragas_model = self._resolve_ragas_llm_model(llm_cfg)
        llm = self._create_ragas_llm(llm_client, ragas_model)

        # ── Embeddings ──
        emb_cfg = self.settings.embedding
        emb_provider = emb_cfg.provider.lower()
        emb_azure_endpoint = getattr(emb_cfg, "azure_endpoint", None)

        # Same Azure-compatible mode detection for embeddings
        use_azure_emb = (
            emb_provider == "azure"
            or (emb_provider == "openai" and emb_azure_endpoint)
        )

        if use_azure_emb:
            emb_client = AsyncAzureOpenAI(
                api_key=emb_cfg.api_key,
                azure_endpoint=emb_azure_endpoint or emb_cfg.azure_endpoint,
                api_version=getattr(emb_cfg, "api_version", None) or "2024-02-15-preview",
            )
        elif emb_provider == "openai":
            emb_client = self._make_async_openai_client(
                api_key=emb_cfg.api_key,
                base_url=getattr(emb_cfg, "base_url", None),
            )
        else:
            raise ValueError(
                f"Unsupported embedding provider for Ragas: '{emb_provider}'. "
                "Supported: azure, openai"
            )

        embeddings = OpenAIEmbeddings(model=emb_cfg.model, client=emb_client)

        self._wrappers_cache = (llm, embeddings)
        return self._wrappers_cache

    def _resolve_ragas_llm_model(self, llm_cfg: Any) -> str:
        """Pick LLM model for Ragas (supports evaluation.llm_model override)."""
        evaluation = getattr(self.settings, "evaluation", None)
        override = getattr(evaluation, "llm_model", None) if evaluation else None
        if override and str(override).strip():
            model = str(override).strip()
            if model != llm_cfg.model:
                logger.info(
                    "Ragas using evaluation.llm_model=%s (main llm.model=%s)",
                    model,
                    llm_cfg.model,
                )
            return model
        return llm_cfg.model

    def _extract_texts(self, chunks: List[Any]) -> List[str]:
        """Extract text strings from various chunk representations.

        Args:
            chunks: List of chunk dicts, strings, or objects with .text.

        Returns:
            List of text strings.
        """
        texts: List[str] = []
        for chunk in chunks:
            if isinstance(chunk, str):
                texts.append(chunk)
            elif isinstance(chunk, dict):
                text = chunk.get("text") or chunk.get("content") or chunk.get("page_content", "")
                texts.append(str(text))
            elif hasattr(chunk, "text"):
                texts.append(str(getattr(chunk, "text")))
            else:
                texts.append(str(chunk))
        return texts

    def _metrics_from_settings(self, settings: Any) -> List[str]:
        """Extract metrics list from settings if available."""
        if settings is None:
            return []
        evaluation = getattr(settings, "evaluation", None)
        if evaluation is None:
            return []
        raw_metrics = getattr(evaluation, "metrics", None)
        if raw_metrics is None:
            return []
        # Filter to only ragas-supported metrics
        return [m for m in raw_metrics if m.lower() in SUPPORTED_METRICS]
