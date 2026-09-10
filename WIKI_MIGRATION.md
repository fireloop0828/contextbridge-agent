# Wiki 迁移执行计划

> **状态：迁移已完成；本文档为过程记录**（已移出 `wiki/`，不参与知识检索）。
> 迁移产出 41 页，批次 4（合并去重）经评估不建议执行；其后做过一轮精简，最终 40 页。
> 原则：先建框架、再迁内容；**原文件不删除**，用 `git mv` 移动，可随时回滚。

## 一、目标与原则

- **目标**：把分散的项目文档重构为「一页一主题」的 LLM wiki，**不改变既有结论与事实**。
- **原则**：正文只做「搬家 + 加壳 + 拆分」，不做重写（除非进入档位 3）。
- **边界**：只新增 `wiki/` 目录，不改动 `agents-master/`、`rag-server/` 的运行代码。

## 二、改动档位

| 档位 | 做什么 | 是否改正文 | 风险 | 默认 |
| --- | --- | --- | --- | --- |
| **1 纯重组** | `git mv` 移动/改名 + 加 frontmatter + 建索引 | 否 | 极低 | ✅ |
| **2 轻度改写** | 页首加 TL;DR、按章节拆分大文件、补「关联」区 | 否（只增结构） | 低 | ✅ |
| **3 合并去重** | 同主题多文件合并为一份权威页 | 是 | 中 | 逐页确认后做 |

默认执行 **档位 1 + 2**；档位 3 逐页经你确认后单独做。

## 三、批次划分

### 批次 0 · 框架（本次已完成 ✅）

产出：`wiki/README.md`、`wiki/PLAN.md`、`wiki/_templates/page.md`、`wiki/scripts/build_index.py`、`wiki/llms.txt`、6 个域 `index.md`。

### 批次 1 · 全局 + 集成（档位 1+2）✅ 已完成

- 迁移：`00-overview/*`、`30-integration/*`
- 理由：最基础、复用最多，先验证模板手感。

### 批次 2 · Host 与 RAG 主体（档位 1+2）✅ 已完成

- 迁移：`10-host/*`、`20-rag/*`（含拆分 `DEV_SPEC.md`）
- 理由：体量最大，需按域逐页推进。

### 批次 3 · 决策与分析（档位 1+2）✅ 已完成

- 迁移：`40-decisions/*`、`50-analysis/*`

### 批次 4 · 合并去重（档位 3，可选）❌ 评估后不执行

- 对重复主题逐页合并，每页先出方案再执行。
- 结论：**不执行**。理由见「八、执行结果」第 3 条。

## 四、逐域迁移映射

| 现有文件 | 目标页 | 档位 |
| --- | --- | --- |
| 根 `README.md` | `00-overview/project.md` + `repo-map.md` | 1+2 |
| （新建） | `00-overview/glossary.md` | 2 |
| `agents-master/docs/project-design/app.py架构说明与拆分建议.md` | `10-host/architecture.md` | 1+2 |
| `agents-master/docs/project-design/中间件化改造方案.md` | `10-host/architecture.md` | 1+2 |
| `agents-master/README.md` | 拆入 `10-host/react-agent.md` 等 | 1+2 |
| `agents-master/docs/project-design/MCP设计与管理.md` | `10-host/mcp-client.md` | 1+2 |
| `agents-master/docs/project-design/多模式Agent架构选型.md` | `10-host/modes.md` | 1+2 |
| `agents-master/docs/test-analysis/记忆系统现状与优化.md` | `10-host/memory.md` | 1+2 |
| `agents-master/docs/project-design/旅行规划-需求与架构(产品).md` | `10-host/travel.md` | 1+2 |
| `agents-master/docs/project-design/旅行规划-职责分层与步骤依据(实现).md` | `10-host/travel.md` | 1+2 |
| `agents-master/prompts/`、`modes/*/system.md` | `10-host/prompts.md` | 1+2 |
| `rag-server/README.md` | `20-rag/architecture.md`（并入） | 1+2 |
| `rag-server/docs/project-design/系统架构与模块选型.md` | `20-rag/architecture.md` | 1+2 |
| `rag-server/docs/project-design/需求目标与模块设计.md` | `20-rag/architecture.md` | 3（并入） |
| `rag-server/docs/整体设计和流程.md` | `20-rag/index.md` | 1+2 |
| `rag-server/DEV_SPEC.md` | 拆入 `20-rag/ingestion.md` / `retrieval.md` / `rerank.md` 等 | 2 |
| `rag-server/docs/project-design/外接集成设计.md` | `20-rag/mcp-server.md` | 1+2 |
| `rag-server/docs/project-design/评估体系设计.md` | `20-rag/evaluation.md` | 1+2 |
| `rag-server/docs/管理面板指南.md` | `20-rag/observability.md` | 1+2 |
| 根 `README.md`（链路部分） | `30-integration/end-to-end.md` | 1+2 |
| 根 `README.md`（配置部分） | `30-integration/config-and-keys.md` | 1+2 |
| `agents-master/docs/project-design/MCP设计与管理.md`（生命周期部分） | `30-integration/mcp-lifecycle.md` | 1+2 |
| `agents-master/README.md` + `QA/integration-qa.md`（排障部分） | `30-integration/troubleshooting.md` | 1+2 |
| 根 `README.md` + `QA/fast-qa.md`（决策叙事） | `40-decisions/0001~0004` | 2 |
| `agents-master/docs/test-analysis/Token消耗分析与优化.md` | `50-analysis/token-optimization.md` | 1+2 |
| `agents-master/docs/test-analysis/MCP初始化性能分析与优化.md` | `50-analysis/mcp-init-performance.md` | 1+2 |
| `agents-master/docs/test-analysis/工具调用失败案例与处理准则.md` | `50-analysis/tool-failures.md` | 1+2 |
| `agents-master/docs/test-analysis/测试问题与优化总结（2026-06）.md` | `50-analysis/test-summary.md` | 1+2 |
| `rag-server/docs/test-analysis/*.md`（3 篇） | `50-analysis/rag-analysis.md` | 1+2 |
| `agents-master/docs/test-analysis/MCP与RAG能力展示优化建议.md` | `50-analysis/`（待定） | 1 |
| `agents-master/docs/project-design/GitHub推送模式目标分析.md` | `50-analysis/` 或归档 | 1 |
| `rag-server/docs/知识库扩展计划.md` | `20-rag/`（未来规划，待定） | 1 |
| `QA/*.md` | **保留原位**，由 wiki 页 `related` 反向链接 | — |
| `.cursor/skills/*/references/knowledge-*.md` | **保留原位**，作为知识来源反链 | — |

> 说明：源文件被 `git mv` 后，原路径消失。若希望「原文档保留 + wiki 引用」两种模式并存，可改为**复制**而非移动（副本会与 wiki 版本并存，需接受一定冗余）。执行前请确认采用哪种。

## 五、每批验收标准

1. 每页含完整 frontmatter，`id` 全局唯一。
2. 每页有自足的 `> TL;DR`。
3. 正文小节统一为「是什么 / 为什么这样设计 / 怎么实现 / 关键代码锚点 / 关联」。
4. `sources` 指向真实存在的路径。
5. 运行 `python3 wiki/scripts/build_index.py`：`llms.txt` 生成成功且无死链。
6. `git status` 能看清「移动 + 新增」；抽查 1~2 页正文与原文件一致（档位 1+2 不应丢内容）。

## 六、回滚方式

- 全部用 `git mv`，回滚即 `git checkout .` 或 `git mv` 回原路径。
- 建议每批完成后单独 commit（如 `wiki: migrate 00-overview`），便于逐批回退。
- **不执行**任何删除操作；档位 3 的合并也保留原文件至确认后。

## 七、关键问题的最终选择

1. **移动 vs 复制**：采用**移动**（`git mv`），原路径消失；历史保留，可随时 `git mv` 回滚。
2. **是否做档位 3**：**不做**（即默认策略），重复内容靠 `related` 互链而非合并。
3. **执行范围**：批次 1 → 2 → 3 连续推进，未逐批暂停验收。
4. **是否保留 `DEV_SPEC.md`**：**保留原位存档、不拆分**——其内容与 [[rag/architecture]] 互补而非重复，拆分收益低而风险高。记录见 [`wiki/20-rag/index.md`](wiki/20-rag/index.md)。

## 八、执行结果

### 1. 产出

| 项 | 结果 |
| --- | --- |
| 页面总数 | 41 页（不含 `_templates`） |
| 知识域 | 6 个（00-overview / 10-host / 20-rag / 30-integration / 40-decisions / 50-analysis） |
| 正文总行数 | 6,744 行 |
| 文件搬迁 | 22 个 `git mv`，git 全部识别为**重命名**（相似度 R082–R096，佐证正文未丢内容） |
| 链接校验 | `build_index.py`：`[[id]]` 与 markdown 相对链接**均无死链**，无待建链接 |

### 2. 与计划映射的偏差（均为「不合并、拆成独立页」方向）

| 计划 | 实际 | 原因 |
| --- | --- | --- |
| `10-host/travel.md`（两篇合并） | 拆为 `travel-product.md` + `travel-impl.md` | 产品需求 vs 实现依据，职责不同 |
| 中间件方案并入 `10-host/architecture.md` | 独立为 `10-host/middleware.md` | 「已落地现状」vs「未落地提案」，性质不同 |
| 需求文档档位 3 并入 `20-rag/architecture.md` | 独立为 `20-rag/requirements.md` | 需求/目标 vs 技术选型，互补 |
| `整体设计和流程.md` → `20-rag/index.md` | 独立为 `20-rag/flow.md` | 速览页与域索引分离，各自更纯 |
| 3 篇 RAG 测试文档 → `50-analysis/rag-analysis.md` | 拆为 `rag-issues` / `rag-evaluation-tuning` / `rag-e2e-performance` | 避免档位 3 的合并改写 |
| `MCP与RAG能力展示优化建议.md`（计划「待定」） | `50-analysis/display-optimization.md` | 按来源归档 |
| `GitHub推送模式目标分析.md`（计划「或归档」） | `50-analysis/github-push-mode.md` | 按来源归档 |
| `40-decisions/0001~0004` | 新写（档位 2） | 素材取自根 `README.md`、`QA/fast-qa.md` 与已迁移 wiki 页 |

另有两项框架层面的调整：

- `build_index.py` **新增 markdown 相对链接校验**（原仅校验 `[[id]]`）。
- 迁移页**未强行重排小节标题**，保留原有编号（只加壳：frontmatter + TL;DR + 关联区）。验收标准第 3 条「统一小节结构」因此**未对迁移页执行**——强行重排属改正文（档位 3），与「不做重写」原则冲突。

### 3. 批次 4 结论：不执行合并

候选重复对及评估：

| 候选对 | 结论 |
| --- | --- |
| `10-host/architecture` ↔ `middleware` | 现状 vs 提案，**不合并** |
| `10-host/travel-product` ↔ `travel-impl` | 需求 vs 实现依据，**不合并** |
| `20-rag/requirements` ↔ `architecture` | 需求 vs 选型，合并后 671 行，**不合并** |
| `20-rag/flow` ↔ `index` | 速览 vs 域索引，**不合并** |

理由：

1. 每对的**职责边界清晰**，合并会产出 400–670 行巨型页，与「一页一主题、自足」的约定相悖。
2. 真实重复内容已由 `related` 互链解决——已核查上述 4 对**全部双向互链**。
3. 档位 3 需改正文（风险中），而收益为负。

### 4. 有意未迁移的遗留

| 文件 | 处置 |
| --- | --- |
| `rag-server/DEV_SPEC.md` | 保留原位存档（见上文第 7 节第 4 条） |
| `rag-server/docs/知识库扩展计划.md` | 保留原位（未来规划，计划中标注「待定」） |
| `QA/*.md` | 保留原位，由 wiki 页 `related` 反向链接 |
| `.cursor/skills/*/references/knowledge-*.md` | 保留原位，作为知识来源反链 |
| `agents-master/README.md`、`rag-server/README.md` | 保留原位（其要点已拆入 wiki 页，README 内指向 wiki 的引用已同步更新） |
