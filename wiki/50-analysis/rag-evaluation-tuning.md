---
id: analysis/rag-evaluation-tuning
title: RAG 评估调优专题
tags: [analysis, rag, evaluation]
sources:
  - rag-server/src/observability/evaluation/
  - rag-server/src/libs/evaluator/
  - rag-server/scripts/evaluate.py
related: [rag/evaluation, analysis/rag-issues]
updated: 2026-09-10
---
# RAG 评估调优专题

> **TL;DR**：评估链路调优台账——含评估迭代时间线、指标演进、排障路径，以及 Ragas / Custom Evaluator / Golden Set / 评估面板四类踩坑。

> 开发笔记 · 记录评估链路的排障、指标迭代与调优。体系设计见 [评估体系设计.md](wiki/20-rag/evaluation.md)；主链路入库/检索/MCP 问题见 [RAG测试问题与优化记录.md](./rag-issues.md)。

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
2. **问题与优化记录** — 评估链路上的设计缺陷、兼容问题及对应改法；新条目追加在对应节末尾。

**读历史记录时看什么**：`backend`、`collection`、聚合五项指标、`warnings`、`total_elapsed_ms`、单题 `retrieved_chunk_ids` / `generated_answer`。

## 评估迭代时间线

Golden Set 与面板路径：早期 `tests/fixtures/golden_test_set.json`（6 题）；稳定期起增加 `tests/fixtures/golden_test_set_20.json`（20 题，2026-06-25 校准）。评测时 **collection 固定** `travel_plan`，与入库一致。

### 阶段总览


| 阶段       | 时间          | 评测器                            | 规模                  | 指标与叙事要点                                                                                                                                               |
| -------- | ----------- | ------------------------------ | ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **基线差**  | 6/5 – 6/10  | custom / ragas **分开跑**         | 1、3、6 题穿插           | `hit_rate` 偏低；`answer_relevancy` **多为 0**；常未填 Answer、未校准 `expected_chunk_ids` 或 collection 不一致                                                        |
| **间歇**   | 6/12、6/15   | 各跑 1 次                         | 1、3 题               | 指标仍不理想，确认问题在「检索标注 + Ragas 输入」而不只是偶发                                                                                                                   |
| **优化起步** | 6/20 – 6/21 | **composite**                  | 3、6 题               | 一次跑通检索 + 回答两类指标；整体仍弱，但历史里开始同时出现 hit_rate 与 Ragas 三项                                                                                                   |
| **中文修复** | 6/22        | composite / ragas              | 6 题                 | `**faithfulness` 不再系统性偏低**；与人工 spot-check 方向一致 → 见 [Ragas · 中文评判失真](#2026-06-22-中文知识库跑-ragasfaithfulness-与人工感受对不上)                                    |
| **额度回落** | 6/24        | composite                      | 6 题                 | 聚合**只剩 `hit_rate` / `mrr`**，`warnings` 含百炼额度或 tool_choice；下午修复后 Ragas 项恢复 → 见 [Ragas · 百炼兼容](#2026-06-24-百炼不兼容-ragas-调用composite-面板只显示-hit_rate--mrr) |
| **稳定期**  | 6/24 – 6/25 | 混合（custom / ragas / composite） | 6 → **20×2 + 30×1** | 指标稳定；全量 Ragas / composite **约 30–44 分钟**；发版前以 20/30 题回归为准                                                                                             |


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
  - 早期面板不展示、不可编辑每题 Answer，Golden Set 缺 `reference_answer` 时链路静默用 chunk 拼接，`answer_relevancy` 长期为 0 → [Ragas · 面板未展示回答](#2026-06-18-面板未解析-golden-set-回答ragas-answer_relevancy-长期为-0)。
3. **用 composite 做日常迭代**（6/20 起）
  - 检索与回答指标需一并对比，增加 composite 一次跑两类 → [评估面板 · composite](#2026-06-20-想同时对比检索与回答指标需跑两遍评测)。
4. **中文场景评判对齐**（6/22 下午，分水岭）
  - Ragas 默认英文评判与中文知识库不匹配，本项目为 faithfulness / answer_relevancy 接入中文评判链并做答案清洗；历史里 **faithfulness 不再系统性偏低**。
5. **基础设施踩坑修完**（6/24）
  - 百炼 JSON 模式 + `format_ragas_error()`；上午 composite 曾「只有 hit_rate/mrr」，下午同一套 6 题可打出完整 5 项。
6. **扩大回归规模**（6/24 晚 – 6/25）
  - 6 题冒烟 → 20 题两轮 + 30 题一轮；新增用例须逐题标注 `expected_chunk_ids` → [Golden Set · 新题未标注](#2026-06-27-新增用例未写-expected_chunk_ids新题-hit_rate-恒为-0)；重入库后须重校准 → [Golden Set · 重入库未同步](#2026-06-25-知识库重入库后测试集-expected_chunk_ids-未同步hit_rate-骤降)。

### 和评测历史怎么对照

在 Dashboard「效果评测」底部 **评测历史表** 或打开 `logs/eval_history.jsonl`：


| 你想确认的事      | 在历史里看                                                                                                                        |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------- |
| 检索有没有变好     | 同 `collection`、custom/composite 下 `hit_rate`、`mrr` 是否逐次升高或持平                                                                 |
| 回答评判有没有变好   | `faithfulness`、`answer_relevancy`、`context_precision`；**faithfulness** 在 6/22 中文评判前后对比最明显；**answer_relevancy** 须先确保已填 Answer |
| 某次为什么「只有两项」 | 该条 `warnings` 是否含 RagasEvaluator / 额度 / tool_choice                                                                          |
| 全量是否跑完      | `total_elapsed_ms`、查询数是否等于 Golden Set 题数                                                                                     |


---

## 排障路径

评估跑不起来或分数异常时，**按序**勾选排查（跳过已确认项）：

- [ ] **1. 环境与 Key**  
  `rag-server/config/settings.yaml` 里 `evaluation` 段的 LLM Key 是否有效；百炼是否勾选「仅免费额度」且已耗尽；`evaluation.llm_model` 建议 `qwen-plus` / `qwen-turbo`。

- [ ] **2. 数据前提**  
  目标 `collection` 已入库；Golden Set 与面板「知识库」一致（`travel_plan`）。

- [ ] **3. Backend 与必填字段**  
  `custom` → `expected_chunk_ids`；`ragas` → 每题应有实质 Answer（手填或 `reference_answer` 预填，勿依赖空框时的 chunk 拼接）；`composite` → 两者都要。

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

### [2026-06-18] 面板未解析 Golden Set 回答，Ragas answer_relevancy 长期为 0

- **现象**：选 `ragas` / `composite` 跑完，`answer_relevancy` 长期为 0 或接近 0；当时误以为 Ragas 库坏了。
- **原因**：Ragas 必须有 Answer 才能评 relevancy。早期效果评测页**只选 Golden Set 路径就开跑**，不解析、不展示测试 JSON 里的 query / `reference_answer`，也无法在跑前修改。文档里回答缺失时，`EvalRunner` **静默**用检索 chunk 拼接占位，不阻断评测——faithfulness 等仍可能有数，但 relevancy 对碎片原文会系统性塌到 0。
- **优化**：面板在 ragas / composite 下**解析 Golden Set**，逐题展示 query 与回答输入框（`reference_answer` 预填），支持跑前修改；未填满时提示将回退 chunk 拼接。Golden Set 侧补全 `reference_answer`，减少每轮手抄。
- **结果/效果**：时间线 **基线差 / 间歇** 阶段主因之一；面板能看清「评的是哪段回答」后，`answer_relevancy` 脱离长期 0。

---

### [2026-06-22] 中文知识库跑 Ragas，faithfulness 与人工感受对不上

- **误区**：Answer 已填、检索也正常，就把 Ragas 聚合分当成「中文问答质量」的直接结论；没意识到 **评判 prompt 的语言** 与 query / 知识库语言不一致时，分数会系统性失真。
- **现象**：中文 query + 中文 chunk 场景下，`**faithfulness` 系统性偏低**；答案若带「根据知识库检索结果…」等 Agent 套话，faithfulness 更低，与人工 spot-check 方向相反。
- **本质**：
  - **Ragas（社区库）提供什么**：`faithfulness`、`answer_relevancy`、`context_precision` 三项指标的定义，以及默认 **英文** LLM-as-Judge 流程（例如 faithfulness：拆陈述 → 用 context 做 NLI 核对；answer_relevancy：从回答反推问题再算相似度）。Ragas **没有**针对本项目中文旅行知识库的现成适配。
  - **本项目缺什么**：`travel_plan` 全是中文 query 与中文检索结果，却直接走 Ragas 英文评判链，专名、地名、表述对不齐，faithfulness 被整体压低。另有两处**输入噪声**：Agent 答案里的固定套话被当成待核对陈述；Top-K 全量 context 带入跨主题 chunk，进一步干扰评判。
- **处理**（`RagasEvaluator` 外包 Ragas，在 `settings.yaml` → `evaluation` 段配置）：
  1. **中文评判链**（`ragas_chinese_prompts: true`，默认开启）：`faithfulness`、`answer_relevancy` 改走本项目自写的中文 prompt——faithfulness 为「中文陈述拆分 → 中文 NLI 核对」；answer_relevancy 为「从回答反推中文问题 → 与 query 做向量相似度」。关闭该配置则回退 Ragas 内置英文路径，中文场景 faithfulness 往往会再次失真。
  2. **答案清洗**：评测前自动剥掉「根据知识库检索结果…」等套话前缀，避免无信息陈述参与忠实度计算。
  3. **Context 截断**：`ragas_max_context_chunks`（默认 3）只把前 N 条检索 chunk 送入评判，降低跨主题噪声。
  - 说明：`context_precision` 当前仍走 Ragas 默认评判，未接中文链；排障 faithfulness / answer_relevancy 时优先看以上三项。
- **结果/效果**：时间线 **中文修复** 分水岭；6/22 下午起 faithfulness 与人工 spot-check 方向一致。与 [上条](#2026-06-18-面板未解析-golden-set-回答ragas-answer_relevancy-长期为-0) 分工：上条是**面板未提供 Answer 输入**；本条是**Answer 已有，但评判链与中文场景不匹配**。

---

### [2026-06-24] 百炼不兼容 Ragas 调用，composite 面板只显示 hit_rate / mrr

- **现象**：composite 跑完聚合**只有** `hit_rate` / `mrr`，缺 Ragas 三项；面板上不易看出 Ragas 子链路失败原因（`warnings` 含 tool_choice、FreeTierOnly 或 DashScope 403）。
- **原因**：百炼 API 不支持 Ragas 默认的 `tool_choice` 调用，需改 JSON 结构化输出；免费额度用尽直接 403。Composite 在 Ragas 失败时仍输出 Custom 结果，失败只写入 `warnings`，主界面又像「跑成功了」。
- **优化**：
  - **兼容**：百炼场景 Ragas LLM 走 JSON 模式；`format_ragas_error` 将额度/鉴权错误译为中文。
  - **面板**：结果区展示 `warnings`；聚合缺 Ragas 指标时显性提示「回答评测未产出，请查看 warnings」；子后端错误写入单题明细，避免只看到 hit_rate / mrr 却不知 Ragas 侧挂了。
- **结果/效果**：时间线 **额度回落**；兼容修复且额度可用后，同批 6 题可打出 5 项聚合；面板能直接看到失败原因，不必先猜「是不是 Ragas 坏了」。

---

## Custom Evaluator

### [2026-06-16] 检索有结果但 hit_rate / MRR 全 0，误以为「没搜到」

- **误区**：`retrieved_chunk_ids` 非空，以为检索正常；或改检索策略后 hit_rate 仍 0，以为算法完全失效。
- **现象**：`custom` / composite 检索部分聚合 `hit_rate: 0.0`、`mrr: 0.0`，单题 `retrieved_chunk_ids` **非空**。
- **本质**：Custom **只问一件事**：召回 ID 是否命中 Golden Set 里的 `expected_chunk_ids`。检索有结果 ≠ 命中标注。全 0 常见三种：**未标注**、**collection 评错库**、**重 ingest 后 chunk ID 前缀变了标注仍是旧的**（本项目 chunk ID 含文档哈希前缀，重入库必过期）。
- **处理**：
  - **用法**：对每题跑 live 检索，把**当前**应命中的 chunk ID 写入 `expected_chunk_ids`；面板 collection 与入库库名一致（`travel_plan`）；重入库后必须整集重校准。
  - **改动**：面板 custom 模式下检测未填 `expected_chunk_ids` 的条数并预警；collection 改下拉减少拼错。
- **结果/效果**：时间线 **基线差** 阶段修完后，hit_rate / mrr 才表示「是否命中期望 chunk」，不再与「有没有召回」混为一谈。

---

## Golden Test Set

### [2026-06-25] 知识库重入库后测试集 expected_chunk_ids 未同步，hit_rate 骤降

- **现象**：文档重新 ingest 或调整知识库后，Custom / composite 的 `hit_rate`、`mrr` 大面积变 0；单题 `retrieved_chunk_ids` 仍有值，容易误判为「检索算法变差了」。
- **原因**：`expected_chunk_ids` 存的是**上一次索引里**的 chunk ID。本项目 chunk ID 带文档内容哈希前缀，**同一文档重入库会生成新 ID**，旧标注与当前召回结果对不上；Custom 只比 ID 是否相等，不比语义，故全判未命中。
- **优化**：每次 re-ingest 或换 collection 后，对 Golden Set **全量**跑 live 检索，把当前应命中的 chunk ID 写回 `expected_chunk_ids`；在 JSON 的 `version` / `description` 记录校准日期（6 题集 2026-06-25 做过一轮）。
- **结果/效果**：hit_rate / mrr 重新反映「当前索引下是否命中期望 chunk」；未同步前指标不可用于对比检索改动。

---

### [2026-06-27] 新增用例未写 expected_chunk_ids，新题 hit_rate 恒为 0

- **现象**：Golden Set 从 6 题扩到 20 题（或早期从 1～2 题扩到 6 题）后，**老题**可能正常，**新加的题** `hit_rate` 一直是 0，但 `retrieved_chunk_ids` 非空。
- **原因**：每条用例除 `query` 外，Custom 还需要 `expected_chunk_ids`——即「这道题**当前检索下**应命中的标准 chunk ID」。只新增 query、不跑检索把 ID 写进去，Custom 没有 ground truth 可比，该题 hit_rate 固定为 0；**不是新题搜不到，是根本没标注**。
- **优化**：每加一条用例：用同一 `collection` 跑 live 检索 → 将 top 命中 chunk 的 ID 写入 `expected_chunk_ids`；形成 `golden_test_set_20.json`（20 题，2026-06-27 校准），6 题集保留作冒烟。
- **结果/效果**：新题纳入回归统计，发版级 20 题全量（时间线 **稳定期 20×2 + 30×1**）才有意义；只扩 query 不标 ID，题数增加但 hit_rate 对新题无参考价值。

---

## 评估面板

### [2026-06-20] 想同时对比检索与回答指标，需跑两遍评测

- **现象**：迭代时要同时看 `hit_rate` / `mrr`（检索）和 Ragas 三项（回答），只能先跑 `custom` 再跑 `ragas`，同一 Golden Set 跑两轮，对比成本高。
- **原因**：`custom` 与 `ragas` 各自只输出一类指标，面板早期没有「一次跑完」的 backend。
- **优化**：增加 `**composite`** backend，单轮评测顺序执行 custom + ragas，聚合报告里同时出现检索与回答指标；面板补充各 backend 职责说明。
- **结果/效果**：时间线 **优化起步**；日常迭代改为 composite 一轮看两类指标，历史记录里 hit_rate 与 Ragas 三项开始同条出现。

---

### [2026-06-20] collection 手输易拼错，评测查错知识库

- **现象**：效果评测里手输 collection 名称，拼写或与入库不一致时，检索落空或查到别的库，`hit_rate` 全 0 或与预期不可比。
- **原因**：collection 决定查哪套向量/BM25 索引；自由文本输入易与 `travel_plan` 等实际库名不一致。
- **优化**：collection 改为**下拉**，选项来自已入库知识库列表（与数据浏览等页面一致），默认选中配置中的库名。
- **结果/效果**：减少库名输错导致的「假全 0」；评测与入库 collection 对齐更容易。

---

### [2026-06-23] composite 缺 Ragas 项或全量耗时长，误判为卡死或检索变好

- **误区**：（1）composite 只有 hit_rate，以为评测成功、回答也不错。（2）全量 20～30 题 spinner 转 30+ 分钟，以为进程卡死杀掉。
- **现象**：（1）聚合缺 Ragas 三项。（2）长时间无界面更新。
- **本质**：（1）同 [百炼兼容](#2026-06-24-百炼不兼容-ragas-调用composite-面板只显示-hit_rate--mrr)。（2）Ragas 每题多次 LLM 调用，20～30 题 **30～44 分钟是正常量级**，非 hang。
- **处理**：
  - **用法**：（1）跑完必看 `warnings`。（2）先 1 / 6 题冒烟再全量；用 `total_elapsed_ms` 判断是否跑完。
  - **改动**：历史表展示耗时与 warnings；面板 ragas 模式注明单题约 2–5 分钟。
- **结果/效果**：能区分「Ragas 子项挂了」与「全量在慢跑」，与 **额度回落**、**稳定期耗时** 记录一致。

## 关联

- 相关：[[rag/evaluation]]
- 相关：[[analysis/rag-issues]]
