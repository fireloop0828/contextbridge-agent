# Evaluation 方法

## 1. 分层评估

Agent 的评估分两层，分别用不同指标：

| 层 | 评什么 | 核心指标 |
|----|--------|----------|
| 检索层 | 召回的文档对不对 | Hit Rate@K、MRR、NDCG@K、Recall@K |
| 生成层 | 生成的答案好不好 | Faithfulness、Answer Relevancy、Context Precision |

正例（`rag-server/DEV_SPEC.md` 4.3 节）目标基线：

- 检索指标：Hit Rate@K ≥ 90%、MRR ≥ 0.8、NDCG@K ≥ 0.85
- 生成指标：Faithfulness ≥ 0.9、Answer Relevancy ≥ 0.85

## 2. 评估器抽象（可插拔）

正例（`DEV_SPEC.md` 3.3.4 节）：

- 统一 `Evaluator` 接口：`evaluate(query, retrieved_chunks, generated_answer, ground_truth) -> metrics`。
- 各评估框架实现该接口，输出标准化的指标字典。
- 组合模式：可挂多个评估器并行执行汇总（如配置 `evaluation.backends: [ragas, custom_metrics]`）。

| 框架 | 特点 | 场景 |
|------|------|------|
| Ragas | RAG 专用、指标丰富 | 全面评估 RAG 质量 |
| DeepEval | LLM-as-Judge | 主观质量判断、复杂业务规则 |
| 自定义指标 | Hit Rate / MRR / Latency P99 | 快速回归、上线前 Sanity Check |

## 3. 黄金测试集（Golden Test Set）

- 结构：「问题 - 答案 - 来源文档」JSON（`tests/fixtures/golden_test_set.json`）。
- 初期人工标注核心场景，后期持续积累坏 Case。
- 坏 Case 必须沉淀进回归集，防止退化。

## 4. 测试分层（对应 TDD）

正例（`rag-server/tests/`）：

- `unit/`：单函数/单模块（拆分器、检索器、评估器）。
- `integration/`：模块间协作（入库 → 检索）。
- `e2e/`：端到端（MCP client → 工具 → 结果）。
- `fixtures/`：黄金集、测试文档。

**原则**：秒级反馈跑 unit，完整回归跑 integration，上线前跑 e2e + 质量评估。

## 5. 指标达标与回归

- 定期运行评估，监控指标是否回归（Dashboard 历史趋势，见 `DEV_SPEC.md` Dashboard 设计）。
- 检索与生成分开看，避免「整体分掩盖检索退化」。
- 每次策略调整（Chunk Size、Reranker 更换）都要有量化分数支撑，拒绝「凭感觉调优」。

## 6. Agent 级评估（对话型）

对 ReAct / 状态机类 Agent，除 RAG 指标外，还要评：

1. **工具选择正确率**：是否选了对的工具（人工标注或规则判断）。
2. **工具调用效率**：是否有多余/重复调用（正例：travel 的「勿重复调用」约束就是为了控制这个）。
3. **任务完成率**：强流程 Agent 的 phase 是否按预期走完。
4. **降级健壮性**：工具失败后能否降级继续（对照 `_mcp_tool_error_message` 的设计意图）。
5. **意图路由正确率**：多模式 Agent 的 `detect_intent` 是否路由到正确模式。

**要点**：对话型 Agent 的评估要「可复现」——用黄金集 + 固定工具桩（mock 外部 API/LLM），而非真实高德/LLM（不可控、不可复现）。

## 7. 检查清单

- [ ] 检索与生成指标分开定义，各自有目标基线
- [ ] 评估器实现统一 `Evaluator` 接口，可插拔、可组合
- [ ] 有黄金测试集，坏 Case 沉淀进回归集
- [ ] 测试分层：unit / integration / e2e，反馈速度有梯度
- [ ] 指标定期运行并监控回归，调优有数据支撑
- [ ] Agent 级指标覆盖：工具选择、调用效率、完成率、降级健壮性
- [ ] 评估可复现：黄金集 + 工具桩，不依赖真实外部服务
