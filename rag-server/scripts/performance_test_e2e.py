"""
端到端性能测试脚本：测量非生成阶段查询链路P50

使用golden_test_set.json的真实查询数据，测量：
  - query_knowledge_hub 执行完成（不含 reranking）的耗时
  - 第一次调用作为 warmup 舍弃
  - 只统计后续稳定态的 P50/P95/P99
"""

import argparse
import asyncio
import csv
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAG_SERVER = PROJECT_ROOT / "rag-server"

# Ensure the rag-server source package is importable
import sys
sys.path.insert(0, str(RAG_SERVER))


def load_golden_test_set() -> List[Dict[str, Any]]:
    test_file = RAG_SERVER / "tests" / "fixtures" / "golden_test_set.json"
    with open(test_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('test_cases', [])


def read_traces_jsonl(filepath: Path) -> List[Dict[str, Any]]:
    traces: List[Dict[str, Any]] = []
    if not filepath.exists():
        return traces
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    traces.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return traces


def calculate_elapsed_without_rerank(trace: Dict[str, Any]) -> float:
    stages = trace.get('stages', [])
    if not stages:
        return float(trace.get('total_elapsed_ms', 0.0) or 0.0)

    total = 0.0
    for stage in stages:
        if stage.get('stage') == 'reranking':
            continue
        total += float(stage.get('elapsed_ms', stage.get('total_elapsed_ms', 0.0) or 0.0))

    if total > 0.0:
        return total
    return float(trace.get('total_elapsed_ms', 0.0) or 0.0)


def _locate_latest_matching_trace(traces: List[Dict[str, Any]], query: str) -> Dict[str, Any] | None:
    query_text = query.strip()
    for trace in reversed(traces):
        meta = trace.get('metadata', {})
        if not isinstance(meta, dict):
            continue
        if meta.get('query', '').strip() == query_text:
            return trace
    return traces[-1] if traces else None


def get_latest_trace_latency(traces_json_path: Path, query: str) -> float:
    traces = read_traces_jsonl(traces_json_path)
    if not traces:
        return 0.0
    trace = _locate_latest_matching_trace(traces, query)
    if not trace:
        return 0.0
    return calculate_elapsed_without_rerank(trace)


def clear_traces_jsonl(traces_json_path: Path) -> None:
    if traces_json_path.exists():
        traces_json_path.write_text("")


def run_query_and_measure(query: str, traces_json_path: Path) -> float:
    from src.mcp_server.tools.query_knowledge_hub import QueryKnowledgeHubTool

    tool = QueryKnowledgeHubTool()
    start = time.perf_counter()
    response = asyncio.run(tool.execute(query=query, top_k=5, collection="travel_plan"))
    end = time.perf_counter()

    wall_ms = (end - start) * 1000.0
    # 稍等一下，确保 trace 已写入
    time.sleep(0.2)
    trace_ms = get_latest_trace_latency(traces_json_path, query)
    if trace_ms > 0.0:
        return trace_ms
    return wall_ms


def summarize(latencies: List[float]) -> Dict[str, Any]:
    latencies_sorted = sorted(latencies)
    count = len(latencies_sorted)
    result = {
        'count': count,
        'min': latencies_sorted[0] if count else 0.0,
        'max': latencies_sorted[-1] if count else 0.0,
        'mean': sum(latencies_sorted) / count if count else 0.0,
        'median': latencies_sorted[count // 2] if count else 0.0,
        'p50': latencies_sorted[count // 2] if count else 0.0,
        'p95': latencies_sorted[min(int(count * 0.95), count - 1)] if count else 0.0,
        'p99': latencies_sorted[min(int(count * 0.99), count - 1)] if count else 0.0,
    }
    return result


def run_performance_test(repetitions: int, output_csv: str, traces_json: str = None) -> Dict[str, Any]:
    test_cases = load_golden_test_set()
    traces_path = Path(traces_json) if traces_json else RAG_SERVER / "logs" / "traces.jsonl"
    results: List[Dict[str, Any]] = []

    print(f"加载 {len(test_cases)} 个 golden test 查询")
    print(f"Traces log: {traces_path}")
    print(f"每个查询重复 {repetitions} 次，第 1 次 warmup 舍弃\n")

    for idx, test_case in enumerate(test_cases, 1):
        query = test_case.get('query', '')
        print(f"[{idx}/{len(test_cases)}] {query}")
        for rep in range(repetitions):
            clear_traces_jsonl(traces_path)
            latency_ms = run_query_and_measure(query, traces_path)
            if rep == 0:
                print(f"  warmup: {latency_ms:.1f} ms")
            else:
                print(f"  rep {rep:2d}: {latency_ms:.1f} ms")
                results.append({
                    'query_idx': idx - 1,
                    'repetition': rep,
                    'query': query,
                    'latency_ms': round(latency_ms, 1),
                    'timestamp': datetime.now().isoformat(),
                })

    if not results:
        raise RuntimeError("未收集到任何稳定态测试结果")

    summary = summarize([r['latency_ms'] for r in results])
    print("\n===== 性能汇总 =====")
    print(f"样本数: {summary['count']}")
    print(f"P50: {summary['p50']:.1f} ms")
    print(f"P95: {summary['p95']:.1f} ms")
    print(f"P99: {summary['p99']:.1f} ms")
    print(f"Mean: {summary['mean']:.1f} ms")
    print(f"Min: {summary['min']:.1f} ms")
    print(f"Max: {summary['max']:.1f} ms")
    print("===================\n")

    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"结果已保存到 {output_csv}")

    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RAG 端到端性能测试')
    parser.add_argument('--repetitions', type=int, default=15, help='每个查询总调用次数')
    parser.add_argument('--output', default='perf_results.csv', help='输出 CSV 文件')
    parser.add_argument('--traces', default=None, help='traces.jsonl 文件路径')
    args = parser.parse_args()

    summary = run_performance_test(args.repetitions, args.output, args.traces)
    if summary['p50'] <= 800:
        sys.exit(0)
    else:
        sys.exit(1)
