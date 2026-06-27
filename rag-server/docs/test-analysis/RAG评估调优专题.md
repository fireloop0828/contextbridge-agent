# RAG 评估调优专题

> 开发笔记 · 记录评估链路的排障、指标迭代与调优。体系设计见 [评估体系设计.md](../project-design/评估体系设计.md)；主链路入库/检索/MCP 问题见 [RAG测试问题与优化记录.md](./RAG测试问题与优化记录.md)。

## 目录

- [记录说明](#记录说明)
- [评估迭代时间线](#评估迭代时间线)
- [排障路径](#排障路径)
- [Ragas](#ragas)
- [Custom Evaluator](#custom-evaluator)
- [Golden Test Set](#golden-test-set)
- [评估面板](#评估面板)

---

## 记录说明

本文档两层内容：

1. **评估迭代时间线** — 对照 Dashboard「效果评测」→ 评测历史与 `logs/eval_history.jsonl`，说明指标如何分阶段变好。  
2. **分主题踩坑条目** — 单点排障与改法；新条目追加在对应节末尾。

单条踩坑模板：

```markdown
### [YYYY-MM-DD] 简短标题

- **现象**：
- **原因**：
- **处理**：
  - 方案要点
  - **使用的技术 / 改动文件**：
- **结果 / 待验证**：
```

**读历史记录时看什么**：`backend`、`collection`、聚合 `hit_rate` / `mrr` / `faithfulness` / `answer_relevancy` / `context_precision`、`warnings`、`total_elapsed_ms`、单题 `retrieved_chunk_ids`。

---

## 评估迭代时间线

Golden Set 与面板路径：早期 `tests/fixtures/golden_test_set.json`（6 题）；稳定期起增加 `tests/fixtures/golden_test_set_20.json`（20 题，2026-06-27 校准）。评测时 **collection 固定 `travel_plan`**，与入库一致。

### 阶段总览

| 阶段 | 时间 | 评测器 | 规模 | 指标与叙事要点 |
|------|------|--------|------|----------------|
| **基线差** | 6/5 – 6/10 | custom / ragas **分开跑** | 1、3、6 题穿插 | `hit_rate` 偏低；`answer_relevancy` **多为 0**；常未填 Answer、未校准 `expected_chunk_ids` 或 collection 不一致 |
| **间歇** | 6/12、6/15 | 各跑 1 次 | 1、3 题 | 指标仍不理想，确认问题在「检索标注 + Ragas 输入」而不只是偶发 |
| **优化起步** | 6/20 – 6/21 | **composite** | 3、6 题 | 一次跑通检索 + 回答两类指标；整体仍弱，但历史里开始同时出现 hit_rate 与 Ragas 三项 |
| **中文修复** | 6/22 下午起 | composite / ragas | 6 题 | **`answer_relevancy` 明显回升**；`faithfulness` 与人工 spot-check 方向一致 → 见 [Ragas · 中文评判](#2026-06-22-中文-query--英文评判--答案套话faithfulness-偏低) |
| **额度回落** | 6/24 上午 | composite | 6 题 | 聚合**只剩 `hit_rate` / `mrr`**，`warnings` 含百炼额度或 tool_choice；下午修复后 Ragas 项恢复 → 见 [Ragas · 百炼 403](#2026-06-24-百炼-tool_choice--免费额度-403面板只有英文堆栈) |
| **稳定期** | 6/24 晚 – 6/25 | 混合（custom / ragas / composite） | 6 → **20×2 + 30×1** | 指标稳定；全量 Ragas / composite **约 30–44 分钟**；发版前以 20/30 题回归为准 |

### 指标怎么一步步变好（口述用）

```mermaid
flowchart LR
  A[基线: hit_rate低 relevancy≈0] --> B[补标注+填Answer+对齐collection]
  B --> C[composite 一次看两类指标]
  C --> D[6/22 中文Ragas prompt]
  D --> E[6/24 修百炼兼容]
  E --> F[6/25 20/30题稳定回归]
```

1. **先让 Custom「有意义」**（6/5–6/15）  
   - 补全 Golden Set 的 `expected_chunk_ids`，面板 collection 选 `travel_plan`。  
   - 否则 hit_rate / MRR 全 0，无法判断检索改动是否有效 → [Custom · hit_rate 全 0](#2026-06-16-custom-跑完-hit_rate--mrr-全是-0)。

2. **再让 Ragas「有意义」**（同期）  
   - 面板为每题填写 Answer（可用 `reference_answer` 预填）；勿用 chunk 拼接当正式结论 → [Ragas · answer_relevancy 为 0](#2026-06-18-answer_relevancy-长期为-0误以为-ragas-坏了)。

3. **用 composite 做日常迭代**（6/20 起）  
   - 一次评测同时看「搜没搜对」和「答得像不像」；子后端失败看 `warnings` → [评估面板 · composite 缺项](#2026-06-23-composite-只出-hit_rate或全量-ragas-十几分钟像卡死)。

4. **中文场景评判对齐**（6/22 下午，分水岭）  
   - `ragas_zh_prompts.py` + `_normalize_answer` + `ragas_chinese_prompts`；历史里 **answer_relevancy 从长期 0 回到可解释区间**，faithfulness 不再系统性偏低。

5. **基础设施踩坑修完**（6/24）  
   - 百炼 JSON 模式 + `format_ragas_error()`；上午 composite 曾「只有 hit_rate/mrr」，下午同一套 6 题可打出完整 5 项。

6. **扩大回归规模**（6/24 晚 – 6/25）  
   - 6 题冒烟 → 20 题两轮 + 30 题一轮；`eval_history` 里 `total_elapsed_ms` 与全量耗时体感一致（30–44 min）。  
   - 20 题集见 `golden_test_set_20.json` → [Golden Set · 扩题与校准](#2026-06-27-golden-set-扩至-20-题并校准-chunk_id)。

### 和评测历史怎么对照

在 Dashboard「效果评测」底部 **评测历史表** 或打开 `logs/eval_history.jsonl`：

| 你想确认的事 | 在历史里看 |
|--------------|------------|
| 检索有没有变好 | 同 `collection`、custom/composite 下 `hit_rate`、`mrr` 是否逐次升高或持平 |
| 回答评判有没有变好 | `faithfulness`、`answer_relevancy`、`context_precision`；6/22 前后对比最明显 |
| 某次为什么「只有两项」 | 该条 `warnings` 是否含 RagasEvaluator / 额度 / tool_choice |
| 全量是否跑完 | `total_elapsed_ms`、查询数是否等于 Golden Set 题数 |

---

## 排障路径

评估跑不起来或分数异常时，**按序**勾选排查（跳过已确认项）：

- [ ] **1. 环境与 Key**  
  `rag-server/config/settings.yaml` 里 `evaluation` 段的 LLM Key 是否有效；百炼是否勾选「仅免费额度」且已耗尽；`evaluation.llm_model` 建议 `qwen-plus` / `qwen-turbo`。

- [ ] **2. 数据前提**  
  目标 `collection` 已入库；Golden Set 与面板「知识库」一致（`travel_plan`）。

- [ ] **3. Backend 与必填字段**  
  `custom` → `expected_chunk_ids`；`ragas` → 非空 Answer；`composite` → 两者都要。

- [ ] **4. 先验证检索**  
  单题 `query.py --verbose` 或「检索记录」能否命中期望 chunk。

- [ ] **5. 先单题后全量**  
  Ragas 单题约 2–5 分钟；20 题 composite 可达 **30–44 分钟**。

- [ ] **6. 读 warnings / eval_history**  
  `warnings`、`total_elapsed_ms`、单题 metrics 是否为空。

- [ ] **7. 指标怎么解读**  
  Custom → hit_rate / mrr；Ragas → faithfulness 等；勿用 Ragas 判断「有没有召回到 chunk」。

**典型排查**：composite 只有 hit_rate → `warnings` 里 Ragas 子后端失败 → 修 Key/额度后 Ragas 三项出现（对应时间线 **6/24 上午**）。

---

## Ragas

### [2026-06-18] answer_relevancy 长期为 0，误以为 Ragas 坏了

- **现象**：选 `ragas` 或 `composite` 跑完，聚合里 `faithfulness` 有数但 `answer_relevancy` 恒为 0；或三指标都极低。
- **原因**：面板未填 Answer，回退为 chunk 拼接；或拼接答案不适合 relevancy 计算。
- **处理**：面板「填写回答」区填入真实回答；`reference_answer` 可作基线预填。
  - **使用的技术 / 改动文件**：`evaluation_panel.py`、`eval_runner.py`、`ragas_evaluator.py`。
- **结果 / 待验证**：属于时间线 **基线差 / 间歇** 阶段主因之一；填答后 relevancy 脱离「长期 0」。

---

### [2026-06-22] 中文 query + 英文评判 + 答案套话，Faithfulness 偏低

- **现象**：中文场景 `faithfulness` 系统性偏低；套话「根据知识库检索结果…」加重失真。
- **原因**：英文评判与中文专名不匹配；套话干扰陈述拆分。
- **处理**：`ragas_zh_prompts.py`；`ragas_chinese_prompts: true`；`_normalize_answer()`；`ragas_max_context_chunks`。
  - **使用的技术 / 改动文件**：`ragas_zh_prompts.py`、`ragas_evaluator.py`。
- **结果 / 待验证**：时间线 **中文修复** 分水岭；`eval_history` 中 6/22 下午起 `answer_relevancy` 明显回升。

---

### [2026-06-24] 百炼 tool_choice / 免费额度 403，面板只有英文堆栈

- **现象**：composite 跑完聚合只剩 `hit_rate` / `mrr`；`warnings` 含 tool_choice 或 FreeTierOnly。
- **原因**：百炼不支持默认 tool_choice；免费额度用尽；错误未翻译。
- **处理**：`instructor.Mode.JSON`；`format_ragas_error()`；`CompositeEvaluator.last_errors` → 单题 warnings。
  - **使用的技术 / 改动文件**：`ragas_evaluator.py`、`composite_evaluator.py`、`query_traces.py`。
- **结果 / 待验证**：对应时间线 **额度回落**；下午修复后同批 6 题恢复完整 5 项指标。

---

## Custom Evaluator

### [2026-06-16] Custom 跑完 hit_rate / MRR 全是 0

- **现象**：`hit_rate: 0.0`、`mrr: 0.0`；`retrieved_chunk_ids` 却非空。
- **原因**：未填 `expected_chunk_ids`；collection 选错；chunk ID 入库后过期。
- **处理**：校准 Golden Set；面板 collection 对齐 `travel_plan`。
  - **使用的技术 / 改动文件**：`custom_evaluator.py`、`eval_runner.py`、`golden_test_set.json`。
- **结果 / 待验证**：时间线 **基线差** 阶段修完后 hit_rate 才有回归意义。

---

## Golden Test Set

### [2026-06-25] 从冒烟 1～2 条扩到 travel_plan 六场景，并校准 expected_chunk_ids

- **现象**：1～2 题无法支撑回归；扩题后部分 hit_rate 仍为 0。
- **原因**：用例过少；重新 ingest 后 chunk 前缀变化。
- **处理**：`golden_test_set.json` **6 题**（`version: 2.1`）；2026-06-25 live 检索校准 ID。
  - **使用的技术 / 改动文件**：`golden_test_set.json`、`eval_runner.load_test_set()`。
- **结果 / 待验证**：时间线 **稳定期** 之前的冒烟集；6 题仍用于快速冒烟。

---

### [2026-06-27] Golden Set 扩至 20 题并校准 chunk_id

- **现象**：6 题覆盖 8 份文档但统计仍偏少；稳定期历史出现 **20×2、30×1** 全量跑法，需要更大固定集。
- **原因**：发版级回归需要更多 query 分布（线路、灾害、签证、主题、特殊人群等）；题量增加后须重新 top-1 校准。
- **处理**：
  - 新增 `tests/fixtures/golden_test_set_20.json`（20 题，覆盖全部 8 份 `travel_plan` 文档）。
  - 2026-06-27 对照 live 检索写入 `expected_chunk_ids`；保留原 6 题 query，新增 14 题。
  - 面板全量回归时选 20 题集；6 题集仍作快速验证。
  - **使用的技术 / 改动文件**：`golden_test_set_20.json`。
- **结果 / 待验证**：与时间线 **稳定期 20×2 + 30×1** 对齐；重新 ingest 后需再校准。

---

## 评估面板

### [2026-06-20] backend 含义不清、collection 手输易错

- **现象**：选 ragas 却期待 hit_rate；collection 拼错导致全 0。
- **原因**：三种 backend 职责未在 UI 区分；手输易与 yaml 默认不一致。
- **处理**：backend 说明文案；`METRIC_INFO` 中文释义；collection **下拉**；Ragas「填写回答」区。
  - **使用的技术 / 改动文件**：`evaluation_panel.py`。
- **结果 / 待验证**：时间线 **优化起步** 前后；减少误读导致的「假差/假好」。

---

### [2026-06-23] composite 只出 hit_rate，或全量 Ragas 十几分钟像卡死

- **现象**：聚合只有 hit_rate / mrr；或 spinner 很久无响应。
- **原因**：Ragas 子后端失败仅进 warnings；全量 LLM 评判耗时长（20–30 题约 30–44 分钟）。
- **处理**：先看 warnings；先 1 题再全量；历史表看 `total_elapsed_ms`。
  - **使用的技术 / 改动文件**：`composite_evaluator.py`、`evaluation_panel.py`、`eval_history.jsonl`。
- **结果 / 待验证**：与 **额度回落**、**稳定期耗时** 两条时间线记录一致。

---

**文档状态**：✅ 已撰写（含评估迭代时间线 · 踩坑条目 · 与 eval_history 对照说明）
