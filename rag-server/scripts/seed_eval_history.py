#!/usr/bin/env python3
"""Seed realistic evaluation history for dashboard demo.

Usage (from rag-server/):
    python scripts/seed_eval_history.py
    python scripts/seed_eval_history.py --out logs/eval_history.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_OUT = Path("logs/eval_history.jsonl")
TEST_SET = "tests/fixtures/golden_test_set.json"

# evaluator, query_count, elapsed_ms, metrics, optional warnings
SeedRow = Tuple[str, int, float, Dict[str, float], Optional[List[str]]]

# timestamp 与 (evaluator, query_count, elapsed_ms, metrics, warnings?)
SEED_RUNS: List[Tuple[str, SeedRow]] = [
    # ── 6/5–6/10：仅 custom / ragas，指标普遍偏差 ──
    ("2026-06-05 10:18:22", ("CustomEvaluator", 1, 16200, {"hit_rate": 0.0, "mrr": 0.0}, None)),
    ("2026-06-05 15:42:08", ("RagasEvaluator", 1, 92800, {
        "faithfulness": 0.32, "answer_relevancy": 0.0, "context_precision": 0.38,
    }, None)),
    ("2026-06-06 09:35:17", ("CustomEvaluator", 3, 41800, {"hit_rate": 0.3333, "mrr": 0.1944}, None)),
    ("2026-06-06 14:20:55", ("RagasEvaluator", 3, 268500, {
        "faithfulness": 0.38, "answer_relevancy": 0.0, "context_precision": 0.44,
    }, None)),
    ("2026-06-07 10:08:33", ("CustomEvaluator", 6, 78200, {"hit_rate": 0.3333, "mrr": 0.2361}, None)),
    ("2026-06-07 16:55:41", ("RagasEvaluator", 6, 598000, {
        "faithfulness": 0.41, "answer_relevancy": 0.0, "context_precision": 0.47,
    }, None)),
    ("2026-06-09 09:48:14", ("CustomEvaluator", 3, 43500, {"hit_rate": 0.5, "mrr": 0.2917}, None)),
    ("2026-06-09 15:33:52", ("RagasEvaluator", 3, 281200, {
        "faithfulness": 0.43, "answer_relevancy": 0.0, "context_precision": 0.49,
    }, None)),
    ("2026-06-10 10:25:08", ("CustomEvaluator", 6, 76800, {"hit_rate": 0.5, "mrr": 0.3125}, None)),
    ("2026-06-10 17:10:37", ("RagasEvaluator", 6, 612000, {
        "faithfulness": 0.45, "answer_relevancy": 0.08, "context_precision": 0.51,
    }, None)),
    # ── 中间间歇 2 次 ──
    ("2026-06-12 11:08:19", ("CustomEvaluator", 1, 15800, {"hit_rate": 0.0, "mrr": 0.0}, None)),
    ("2026-06-15 14:22:44", ("RagasEvaluator", 3, 275800, {
        "faithfulness": 0.48, "answer_relevancy": 0.15, "context_precision": 0.53,
    }, None)),
    # ── 6/20 起：composite 上线，初期仍不理想 ──
    ("2026-06-20 09:34:12", ("CompositeEvaluator", 3, 312000, {
        "hit_rate": 0.6667, "mrr": 0.3889,
        "faithfulness": 0.46, "answer_relevancy": 0.18, "context_precision": 0.5,
    }, None)),
    ("2026-06-20 14:18:55", ("CustomEvaluator", 6, 75400, {"hit_rate": 0.8333, "mrr": 0.5833}, None)),
    ("2026-06-21 10:03:28", ("CompositeEvaluator", 6, 648000, {
        "hit_rate": 0.8333, "mrr": 0.5625,
        "faithfulness": 0.52, "answer_relevancy": 0.32, "context_precision": 0.54,
    }, None)),
    ("2026-06-21 16:47:03", ("RagasEvaluator", 3, 292400, {
        "faithfulness": 0.55, "answer_relevancy": 0.38, "context_precision": 0.56,
    }, None)),
    ("2026-06-22 09:22:14", ("CustomEvaluator", 6, 72100, {"hit_rate": 1.0, "mrr": 0.75}, None)),
    # 6/22 下午：启用中文 Ragas 提示词，answer_relevancy 明显回升
    ("2026-06-22 14:38:47", ("CompositeEvaluator", 6, 625000, {
        "hit_rate": 1.0, "mrr": 0.7292,
        "faithfulness": 0.64, "answer_relevancy": 0.78, "context_precision": 0.61,
    }, None)),
    ("2026-06-23 10:16:38", ("RagasEvaluator", 6, 568000, {
        "faithfulness": 0.71, "answer_relevancy": 0.86, "context_precision": 0.67,
    }, None)),
    ("2026-06-23 15:42:11", ("CompositeEvaluator", 6, 582000, {
        "hit_rate": 1.0, "mrr": 0.8125,
        "faithfulness": 0.74, "answer_relevancy": 0.89, "context_precision": 0.7,
    }, None)),
    # 6/24 上午：百炼额度用尽，Ragas 子评估失败，仅保留检索指标
    ("2026-06-24 09:08:33", ("CompositeEvaluator", 6, 198000, {
        "hit_rate": 1.0, "mrr": 0.875,
    }, ["RagasEvaluator failed: 百炼免费额度已用尽（403）。请开通按量付费或关闭「仅使用免费额度」"])),
    ("2026-06-24 11:52:07", ("RagasEvaluator", 1, 112500, {
        "faithfulness": 0.76, "answer_relevancy": 0.9, "context_precision": 0.72,
    }, None)),
    ("2026-06-24 15:31:44", ("CompositeEvaluator", 6, 571000, {
        "hit_rate": 1.0, "mrr": 0.8958,
        "faithfulness": 0.77, "answer_relevancy": 0.91, "context_precision": 0.73,
    }, None)),
    # ── 6/24 晚–6/25：稳定期（含 2×20 题、1×30 题大规模回归）──
    ("2026-06-24 19:15:28", ("CompositeEvaluator", 6, 558000, {
        "hit_rate": 1.0, "mrr": 0.9167,
        "faithfulness": 0.78, "answer_relevancy": 0.92, "context_precision": 0.74,
    }, None)),
    ("2026-06-25 09:28:16", ("CustomEvaluator", 6, 69800, {"hit_rate": 1.0, "mrr": 0.9375}, None)),
    ("2026-06-25 11:14:52", ("CompositeEvaluator", 6, 542000, {
        "hit_rate": 1.0, "mrr": 0.9271,
        "faithfulness": 0.79, "answer_relevancy": 0.93, "context_precision": 0.75,
    }, None)),
    ("2026-06-25 13:47:33", ("RagasEvaluator", 6, 551000, {
        "faithfulness": 0.8, "answer_relevancy": 0.94, "context_precision": 0.76,
    }, None)),
    ("2026-06-25 15:06:18", ("CompositeEvaluator", 20, 1825000, {
        "hit_rate": 1.0, "mrr": 0.9333,
        "faithfulness": 0.805, "answer_relevancy": 0.945, "context_precision": 0.768,
    }, None)),
    ("2026-06-25 17:38:09", ("RagasEvaluator", 20, 1582000, {
        "faithfulness": 0.808, "answer_relevancy": 0.948, "context_precision": 0.772,
    }, None)),
    ("2026-06-25 19:12:53", ("CompositeEvaluator", 30, 2645000, {
        "hit_rate": 1.0, "mrr": 0.9361,
        "faithfulness": 0.81, "answer_relevancy": 0.95, "context_precision": 0.775,
    }, None)),
]


def _entry(
    timestamp: str,
    evaluator_name: str,
    query_count: int,
    elapsed_ms: float,
    aggregate_metrics: Dict[str, float],
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    rounded = {k: round(v, 4) for k, v in aggregate_metrics.items()}
    return {
        "timestamp": timestamp,
        "evaluator_name": evaluator_name,
        "test_set_path": TEST_SET,
        "total_elapsed_ms": round(elapsed_ms, 1),
        "aggregate_metrics": rounded,
        "query_count": query_count,
        "query_results": [],
        "warnings": list(warnings or []),
        "seeded": True,
    }


def build_seed_history() -> List[Dict[str, Any]]:
    return [
        _entry(ts, ev, qc, ms, metrics, warns)
        for ts, (ev, qc, ms, metrics, warns) in SEED_RUNS
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed eval_history.jsonl with demo data")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    entries = build_seed_history()
    with args.out.open("w", encoding="utf-8") as f:
        for item in entries:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Wrote {len(entries)} entries to {args.out}")


if __name__ == "__main__":
    main()
