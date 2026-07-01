---
name: run-qa
description: "全自动 QA 测试：按 QA_TEST_PLAN.md 串行执行 CLI、Dashboard AppTest、MCP JSON-RPC、Provider 切换、数据生命周期等测试；失败自动诊断修复（≤3 轮）；结果写入 QA_TEST_PROGRESS.md。用户说「跑测试」「执行测试」「QA 测试」「run QA」「QA test」「test and fix」或需要执行 QA 测试计划时使用。"
---

# QA 测试（Run QA）

CLI / Dashboard UI / MCP 协议等**全部自动执行**，无需人工介入。

可选修饰：指定章节（如 `跑测试 G`）或用例 ID（如 `跑测试 G-01`）。

---

> ## ⛔ 铁律
>
> ### 规则 1：严格串行
> 选一个测试 → 跑一条命令 → 等输出 → 在 `skills/run-qa/QA_TEST_PROGRESS.md` 记一行 → 再选下一个。
> 禁止一次跑两个测试、一次改两行进度、并行 tool call、未记录就规划下一题。
>
> ### 规则 2：通过 = 终端输出证据
> ✅ 表示**本会话**已跑命令，且 Note 含从输出复制的**具体数值**。
> 无终端输出 → 标 ⬜，禁止标 ✅。
>
> ### 规则 3：禁止交叉引用
> 禁止写「已在 X-YZ 验证」「同 C-02」「类似…」。
> 即使 G-05 与 C-02 测同一开关，也必须独立跑 G-05 并粘贴自己的输出。
>
> ### 规则 4：禁止推断
> **禁止的 Note 写法**（会被 validator 检出）：
> 「Code uses…」「Dataclass validates…」「auto-creates…」→ 读代码 ≠ 测试。
> 「Should work…」「Would raise…」「Expected behavior…」→ 推测 ≠ 测试。
> 「Parameter accepted」「Config controls behavior」→ 含糊，无输出不算通过。
> 未跑命令、未见输出 → 标 ⬜。
>
> ### 规则 5：对抗心态
> 目标是找 bug，不是凑通过。连续 10+ 通过零 bug → 复查是否过于宽松。
>
> ### 规则 6：章节结束校验
> 每完成一章，运行 `python skills/run-qa/scripts/qa_validate_notes.py`。
> 被标记的用例必须重跑，0 标记后才能进入下一章。

---

## 流程（严格串行）

```
1. 按 ID 顺序选一个待测用例
2. 按需设置系统状态
3. 跑一条命令 — 等待输出
4. 对照 Expected Result 逐条验证实际输出
5. 失败则修复（≤3 轮）
6. ⛔ 门禁：编辑 skills/run-qa/QA_TEST_PROGRESS.md（一行 + 计数器），每次只改一行
7. 完成后才回到步骤 1
```

> 任何 `python` 命令前先激活 `.venv`：`source .venv/bin/activate`（Windows：`.\.venv\Scripts\Activate.ps1`）

---

## 步骤 1：选择目标

1. 读 `skills/run-qa/QA_TEST_PLAN.md` 获取步骤与预期结果。
2. 读 `skills/run-qa/QA_TEST_PROGRESS.md` 获取当前状态。
3. 用户指定章节/ID → 限定范围；否则 → 第一个 ⬜ 待测用例。
4. 若有 🔧 用例，优先重测。
5. 按章节顺序 A→O，章内按 ID 顺序。

### 测试分类

| 章节 | 类型 | 执行方式 |
|------|------|----------|
| A–F | Dashboard UI | AppTest 无头渲染 — 见 [references/test_patterns.md](references/test_patterns.md) |
| G, H, I | CLI | 终端命令，检查 exit code + stdout |
| J | MCP 协议 | JSON-RPC 子进程 — 见 [references/test_patterns.md](references/test_patterns.md) |
| K, L | Provider 切换 | `qa_config.py apply <profile>` → 跑 CLI/Dashboard |
| M | 配置与容错 | 改 settings → 跑 CLI → 验证错误处理 |
| N, O | 数据生命周期 | `qa_multistep.py <TEST_ID>` |

---

## 步骤 2：设置系统状态

```
Empty           → python skills/run-qa/scripts/qa_bootstrap.py clear
Baseline        → python skills/run-qa/scripts/qa_bootstrap.py baseline
DeepSeek        → python skills/run-qa/scripts/qa_config.py apply deepseek
Rerank_LLM      → python skills/run-qa/scripts/qa_config.py apply rerank_llm
NoVision        → python skills/run-qa/scripts/qa_config.py apply no_vision
InvalidKey      → python skills/run-qa/scripts/qa_config.py apply invalid_llm_key
InvalidEmbedKey → python skills/run-qa/scripts/qa_config.py apply invalid_embed_key
Any             → 无需改状态
```

配置 profile 测试后 → `python skills/run-qa/scripts/qa_config.py restore`
查看状态 → `python skills/run-qa/scripts/qa_bootstrap.py status`

---

## 步骤 3：执行与验证

### CLI 测试（G, H, I，及 K/L/M 部分）

1. 从 `skills/run-qa/QA_TEST_PLAN.md` 读取该用例 **Steps** 列。
2. 在终端执行确切命令。
3. 对照 **Expected Result**：
   - **Ingest**：exit=0，输出含阶段名（load/split/transform/embed/upsert）
   - **Query**：exit=0，结果含 source_file 和 score
   - **Error**：exit≠0，stderr 有描述性错误（非裸堆栈）
   - **幂等**：第二次运行显示 "skipped"，无重复数据

### Dashboard 测试（A–F）

见 [references/test_patterns.md](references/test_patterns.md) 中的 AppTest 模板、交互模式、文件上传变通。

要点：
- 每题写一个内联 Python 脚本，用 `AppTest.from_function` 渲染
- 打印具体元素值（metric 标签、selectbox 选项、expander 标签）
- 文件上传：先 CLI ingest，再用 AppTest 验证
- 数据变更：直接调 `DataService`，再用 AppTest/CLI 验证

#### ⚠️ AppTest `st.tabs()` 限制 — 测 Tab 内容前必读

AppTest 会**同时渲染所有 Tab 内容**到扁平元素列表，**无法区分**元素属于哪个 Tab。

**后果**：若步骤要求「点 Tab X → 在 Tab X 内看到内容 Y」，AppTest **无法确认空间归属**；内容 Y 可能来自 Tab 上方诊断区或其他 Tab。

**所有 Tab 内容测试的必做检查：**

1. **先确认 Tab 标签存在**：打印 `[t.label for t in at.tabs]` 或检查页面源码；标签缺失 → 立即标 ❌。
2. **再确认内容元素存在于输出中**。
3. **在 Note 中注明限制**：追加 `[AppTest: tab isolation unverifiable]`。

**示例 — Tab 不存在：**
```python
# 期望「🟪 Rerank」Tab 含 "skipped" 消息：
tab_labels = [el.value for el in at.markdown if '🟪' in el.value or 'Rerank' in el.value]
print('Rerank tab label found:', tab_labels)
# 若为空 → Tab 未渲染 → 标 ❌，Note 写 "Rerank tab not rendered (stage absent)"
```

**禁止**：在输出中找到某元素（如 "Rerank skipped"）就判 Tab 测试通过 — 该元素可能来自诊断区而非 Tab 内。

### MCP 测试（J）

见 [references/test_patterns.md](references/test_patterns.md) 的 JSON-RPC 模板与断言矩阵。

主路径：`pytest tests/e2e/test_mcp_client.py -v` 覆盖大部分 J-* 用例。

### 多步测试（N, O, M 配置, L-07）

3 步及以上**必须**用 runner：

```
python skills/run-qa/scripts/qa_multistep.py <TEST_ID>
```

**已支持**：`N-01`, `N-03`, `N-04`, `N-05`, `N-06`, `O-07`, `M-03`, `M-04`, `M-05`, `M-06`, `M-10`, `M-11`, `L-07`

脚本逐步执行、打印每步实际值、输出 `VERDICT: PASS/FAIL`；将 VERDICT 与关键步骤值写入 Note。

脚本未覆盖的用例，按 `QA_TEST_PLAN.md` 手动执行并粘贴输出。

---

## 步骤 4：修复与重试（≤3 轮）

1. **诊断**：代码 bug / 配置问题 / 缺数据 / 测试计划错误？
2. **修复**：最小改动，在 Note 记录文件/行号。
3. **重试**：重跑同一命令。
4. 3 轮仍失败 → 标 ❌ 并写详细 Note。
5. 修复涉及共享代码 → 重跑同章已通过的用例。

---

## 步骤 5：记录结果

**⛔ 门禁 — 选下一题之前必须完成。**

编辑 `skills/run-qa/QA_TEST_PROGRESS.md`：更新一行用例 + 汇总计数器，每次编辑只改一行。

### ✅ 通过条件

须同时满足：
1. **本会话**已跑命令
2. 观察到**该命令**的实际输出
3. **逐条**验证 Expected Result 中的断言
4. Note 含终端输出中 **≥2 个具体值**

### Note 格式

```
<method>: <value_1>, <value_2>[, ...]
```

- **CLI**：`exit=0, stdout: 'Total chunks: 3', source_file=simple.pdf`
- **AppTest**：`at.metric[0].label='Total traces', at.metric[0].value=6`
- **多步**：`Step1: exit=0, chunks=3. Step2: sources=[simple.pdf]. Step3: deleted=1. Step4: sources=[]`
- **禁止**：`"Already verified in C-02"`、`"Code uses yaml.safe_load"`、`"Should work because..."`、`"Parameter accepted"`

### 状态图标

| 图标 | 含义 |
|------|------|
| ✅ | 通过 — 所有断言已对照实际输出验证 |
| ❌ | 失败 — 3 轮修复后仍失败 |
| ⏭️ | 跳过 — 缺第三方 API Key（仅 K 系列） |
| 🔧 | 已修复 — 待重测 |
| ⬜ | 待测 |

### 计数器

同一次编辑更新：`✅ Pass: X | ❌ Fail: Y | ⏭️ Skip: Z | 🔧 Fix: W | ⬜ Pending: P`（总和须等于 Total）。

### 章节结束门禁

每章完成后：
```
python skills/run-qa/scripts/qa_validate_notes.py
```
重跑被标记用例，0 标记后才能继续。

---

## 关键路径

| 文件 | 用途 |
|------|------|
| `skills/run-qa/QA_TEST_PLAN.md` | 测试步骤与预期结果 |
| `skills/run-qa/QA_TEST_PROGRESS.md` | 执行状态与 Note |
| `config/settings.yaml` | 系统配置 |
| `scripts/ingest.py` / `query.py` / `evaluate.py` | CLI 命令 |
| `tests/e2e/test_mcp_client.py` | MCP E2E 测试 |
| `tests/e2e/test_dashboard_smoke.py` | Dashboard 冒烟测试 |
| `tests/fixtures/sample_documents/` | 测试 PDF |
| `tests/fixtures/golden_test_set.json` | 评测黄金集 |

## 测试文档

| 文件 | 语言 | 页数 | 图片 |
|------|------|------|------|
| `simple.pdf` | EN | 1 | 0 |
| `with_images.pdf` | EN | 1 | 1 |
| `complex_technical_doc.pdf` | EN | ~8 | 3 |
| `chinese_technical_doc.pdf` | ZH | ~8 | 0 |
| `chinese_table_chart_doc.pdf` | ZH | ~6 | 3 |
| `chinese_long_doc.pdf` | ZH | 30+ | 0 |
| `blogger_intro.pdf` | ZH | ~4 | 2 |

均在 `tests/fixtures/sample_documents/`。
