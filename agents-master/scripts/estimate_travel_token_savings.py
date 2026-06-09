#!/usr/bin/env python3
"""
旅行模式各优化项 Token 节省估算（相对优化前基线）。

编号按 docs/test-analysis/旅行模式Token消耗分析与优化.md §4.1 根因顺序：
  O1 §2.1 | O2-O4 §2.2 | O5 §2.3 | O6-O10 §2.4 | O11 §2.5 | O12 —

用法（在 agents-master 目录）:
    python scripts/estimate_travel_token_savings.py
"""

from __future__ import annotations

import os
import sys

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_DIR)

from prompts import build_system_prompt  # noqa: E402
import travel_mode as tm  # noqa: E402


def est_tokens(chars: int) -> int:
    return max(1, int(chars / 1.8))


def est_text(text: str) -> int:
    return est_tokens(len(text))


BASELINE_TRAVEL_SYS_CHARS = 4800

HOPS = {
    "poi_selection": 5,
    "intake_1": 2,
    "intake_2": 2,
    "generating": 18,
}
TOTAL_HOPS = sum(HOPS.values())
POST_POI_HOPS = HOPS["intake_1"] + HOPS["intake_2"] + HOPS["generating"]

POI_TOOL_CHARS = 3000 + 5000 + 1500
PLAN_OUTPUT_CHARS = 5500
LIST_COLLECTIONS_CHARS = 600

JOURNEY_BASELINE_TOTAL = 300_000


def main() -> None:
    current_sys = build_system_prompt(tm.APP_MODE_TRAVEL)
    old_sys_tok = est_tokens(BASELINE_TRAVEL_SYS_CHARS)
    new_sys_tok = est_text(current_sys)
    per_hop_sys_save = old_sys_tok - new_sys_tok

    poi_baggage_once = est_tokens(POI_TOOL_CHARS)
    plan_tok = est_tokens(PLAN_OUTPUT_CHARS)

    estimates: dict[str, dict[str, object]] = {
        "O1": {
            "root": "§2.1",
            "tokens": per_hop_sys_save * TOTAL_HOPS,
            "note": f"System Prompt {BASELINE_TRAVEL_SYS_CHARS}→{len(current_sys)} 字符，×{TOTAL_HOPS} 跳",
        },
        "O2": {
            "root": "§2.2",
            "tokens": poi_baggage_once * POST_POI_HOPS,
            "note": f"POI ToolMessage ~{poi_baggage_once} tok × {POST_POI_HOPS} 后续跳",
        },
        "O3": {
            "root": "§2.2",
            "tokens": 0,
            "note": "已回退；若 generating 时 reset，本可再省 intake 工具历史 ~5%～15%",
        },
        "O4": {
            "root": "§2.2",
            "tokens": 0,
            "note": "暂缓；估算潜力 ~5万～12万 input（视回合数）",
        },
        "O5": {
            "root": "§2.3",
            "tokens": plan_tok,
            "note": "省 write_markdown_document 的 content 参数（输出侧）",
        },
        "O6": {
            "root": "§2.4",
            "tokens": 0,
            "note": "已回退；若 7k/次截断，估算可省 ~5万～8万（视工具链）",
        },
        "O7": {
            "root": "§2.4",
            "tokens": 0,
            "note": "初版无 O4 时净节省≈0；配合 O4 后潜力大",
        },
        "O8": {
            "root": "§2.4",
            "tokens": 0,
            "note": "正常路径不触发；防失控超 32 步时避免额外数万 input",
        },
        "O9": {
            "root": "§2.4",
            "tokens": 0,
            "note": "质量约束，不直接省 Token",
        },
        "O10": {
            "root": "§2.4",
            "tokens": est_tokens(LIST_COLLECTIONS_CHARS) * 2,
            "note": "少 1～2 次 list_collections 调用及结果",
        },
        "O11": {
            "root": "§2.5",
            "tokens": est_tokens(4000),
            "note": "仅改稿轮生效；少重复 excerpt，全文仍在 [PREVIOUS_PLAN]",
        },
        "O12": {
            "root": "—",
            "tokens": 0,
            "note": "不做；只省费用不省 Token",
        },
    }

    print("旅行模式 Token 节省估算（编号按根因 §2.1→§2.5）")
    print(f"基线行程总 Token（锚点）: ~{JOURNEY_BASELINE_TOTAL:,} (in+out)")
    print(f"当前 System Prompt: {len(current_sys)} chars (~{new_sys_tok} tok)\n")
    print(f"{'项':<4} {'根因':<6} {'节省 tok':>10}  {'占基线':>7}  说明")
    print("-" * 78)

    for key in [
        "O1", "O2", "O3", "O4", "O5", "O6", "O7", "O8", "O9", "O10", "O11", "O12"
    ]:
        row = estimates[key]
        tok = int(row["tokens"])
        pct = 100.0 * tok / JOURNEY_BASELINE_TOTAL if tok else 0.0
        pct_s = f"{pct:.0f}%" if tok else "—"
        tok_s = f"~{tok:,}" if tok else "—"
        print(
            f"{key:<4} {row['root']:<6} {tok_s:>10}  {pct_s:>7}  {row['note']}"
        )

    major = sum(int(estimates[k]["tokens"]) for k in ("O1", "O2", "O5", "O10"))
    print("-" * 78)
    print(
        f"已落地主项合计 O1+O2+O5+O10: ~{major:,} tok "
        f"（约 {100 * major / JOURNEY_BASELINE_TOTAL:.0f}% 基线；各项非严格可加）"
    )


if __name__ == "__main__":
    main()
