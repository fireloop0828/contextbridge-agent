# rag-server Skills 简介

本目录存放可复用的 Agent 工作流（skills）。每个 skill 一个文件夹，入口为 `SKILL.md`；部分 skill 还带有 `scripts/`（可执行脚本）和 `references/`（按需阅读的参考资料）。

**使用方式**：在 Cursor 对话中用自然语言触发（见下表「触发口令」），Agent 会读取对应 `SKILL.md` 并按步骤执行。命令与路径保持英文原文。

## Skills 一览

| 目录 | 功能 | 适用场景 | 用法 |
|------|------|----------|------|
| `setup` | **首次环境配置向导**。交互式引导：选择 LLM / Embedding / Vision / Rerank Provider → 收集 API Key → 生成 `config/settings.yaml` → 安装依赖 → 校验配置 → 后台启动 Dashboard；未内置的 Provider 可按插件架构自动脚手架；任一步失败自动诊断重试（≤3 轮）。 | 新机器或新环境第一次跑 `rag-server`；需要快速配好多厂商 Provider 并验证能启动控制台；换了一套 API Key 想重新生成配置。 | **触发口令**：「初始化」「环境配置」「项目配置」「setup」「configure」「get started」等。<br>**执行**：在 `rag-server/` 下对 Agent 说「按 setup skill 配置环境」；完成后常用 `python scripts/start_dashboard.py` 启动面板。详见 `setup/SKILL.md`。 |
| `auto-dev` | **按规格自动开发**。读取 `DEV_SPEC.md`，同步分章到 `references/`，从排期表取下一待办任务，按架构实现代码并写测试，`pytest` 失败自动修复（≤3 轮），更新 spec 进度，结束时可选 git 提交。 | 按 `DEV_SPEC` 持续迭代功能；想自动「找任务 → 写代码 → 跑测试 → 勾进度」；指定某个任务 ID（如 B2）单独推进。 | **触发口令**：「自动开发」「自动写代码」「一键开发」「auto code」「auto dev」「autopilot」等。<br>**入口命令**：`python skills/auto-dev/scripts/sync_spec.py`（同步 spec 后读 `references/06-schedule.md` 找任务）。详见 `auto-dev/SKILL.md`。 |
| `create-skill` | **创建或维护 Skill**。提供 skill 结构规范（`SKILL.md` + `scripts/` / `references/` / `assets/`）、触发描述写法、渐进式披露原则，以及脚手架脚本一键生成目录模板。 | 想为本项目或其它项目新增可复用工作流；现有 skill 触发不准或步骤混乱需要重写；学习如何写好 Agent Skill。 | **触发口令**：「创建 skill」「新建 skill」「写 skill」「create skill」「new skill」等。<br>**脚手架**：`python skills/create-skill/scripts/init_skill.py <skill-name> --path skills`。详见 `create-skill/SKILL.md`。 |
| `clean-project` | **清理并脱敏打包**。预览后将删除 Python 缓存、`.venv`、构建产物、`data/`/`logs/`（可选保留）、IDE 配置等；对 `config/settings.yaml` 中的 API Key 替换为占位符，产出可分享的精简代码库。 | 要把代码发给别人或归档前清理本地产物；提交前去掉缓存与敏感配置；发布前确认无真实 Key 残留。 | **触发口令**：「打包」「清理项目」「清理缓存」「package」「clean project」「prepare for distribution」等。<br>**预览**：`python skills/clean-project/scripts/clean.py`<br>**执行**：`python skills/clean-project/scripts/clean.py --execute`（可加 `--keep-data` 保留数据目录）。详见 `clean-project/SKILL.md`。 |
| `run-qa` | **全自动 QA 测试**。严格串行执行 `QA_TEST_PLAN.md` 中的用例：CLI、Dashboard AppTest、MCP JSON-RPC、Provider 切换、数据生命周期等；每条必须有终端输出证据；失败自动修复（≤3 轮）；结果写入 `QA_TEST_PROGRESS.md`，每章结束运行 note 校验脚本。 | 发版前全量或分段回归；排查检索/入库/面板/MCP 质量问题；需要可追溯、可审计的测试记录（非「读代码觉得能过」）。 | **触发口令**：「跑测试」「执行测试」「QA 测试」「run QA」「test and fix」等；可指定章节或用例 ID（如「跑测试 G」「跑测试 G-01」）。<br>**辅助脚本**：`skills/run-qa/scripts/` 下 `qa_bootstrap.py`、`qa_config.py`、`qa_multistep.py`、`qa_validate_notes.py`。详见 `run-qa/SKILL.md`。 |
| `project-review` | **老师式项目复习**。按 9 章 71 道题库苏格拉底式提问：先问后评、给参考答案与延伸思考；记录各章掌握度；每次开场回顾 `review_progress.md` 并建议继续或补弱项。 | 系统复盘 RAG 项目知识点（架构、摄取、检索、MCP、评估等）；考前集中复习；分章节巩固，支持断点续学。 | **触发口令**：「复习项目」「帮我复习」「带我复习」「开始复习」「项目复习」「复盘」「review project」等。<br>**执行**：对 Agent 说「开始项目复习」；题库在 `project-review/references/question_bank.md`，进度保存在 `project-review/review_progress.md`。详见 `project-review/SKILL.md`。 |
| `project-learn` | **面试教练式学习**。自动阅读 `DEV_SPEC`、配置与 `src/` 结构，按 10 大知识域 45 个知识点动态出题；每题最多 4 轮追问；四维评分 + 学习指南（代码路径、文档、可运行命令）；进度写入 `LEARNING_PROGRESS.md`。 | 想按知识点逐步掌握项目而非一次看完；检验自己对某模块（如 Hybrid Search、MCP）的理解深度；面试前针对性补强薄弱知识点。 | **触发口令**：「学习项目」「了解项目」「检验项目」「项目学习」「面试准备」「learn project」「knowledge check」等。<br>**执行**：对 Agent 说「开始学习项目」并选择模式（新学 / 复习 / 查看进度 / Agent 推荐）；进度文件 `project-learn/references/LEARNING_PROGRESS.md`。详见 `project-learn/SKILL.md`。 |
| `write-resume` | **写简历项目经历**。结合 `project_highlights.md` 与用户画像（岗位、业务背景、技术侧重），输出四段式描述（背景 → 目标 → 过程 bullet → 结果量化）；可中英双语；附带面试追问预测与反模式检查。 | 把本 RAG 项目写进简历；按 RAG / Backend / Agent 等岗位调整技术亮点；需要合理量化指标与可自圆其说的表述。 | **触发口令**：「写简历」「简历」「项目经历」「resume」「write resume」「project experience」等。<br>**执行**：对 Agent 说「帮我写简历项目经历」，按提问提供岗位与业务场景；参考 `write-resume/references/resume_principles.md`、`project_highlights.md`。详见 `write-resume/SKILL.md`。 |
| `mock-interview` | **模拟技术面试**。可选 5 种面试官风格（FAST / DEEP / CODE / HARD / MIX）；掷骰选题避免重复；三方向考察（项目综述、简历深挖、技术深挖）；逐字记录问答；结束后生成含参考答案、包装识别与五维评分的报告文件。 | 面试前模拟演练；验证简历项目描述能否经得住追问；练习源码级或压力面试场景。 | **触发口令**：「模拟面试」「面试练习」「帮我面试」「考我」「开始面试」「mock interview」「interview practice」等。<br>**执行**：对 Agent 说「开始模拟面试」，先选风格，可粘贴简历；报告落盘为 `interview_report_YYYYMMDD_HHMMSS.md`。题库在 `mock-interview/references/`。详见 `mock-interview/SKILL.md`。 |

## 目录结构

```
skills/
├── README.md          # 本文件
├── setup/             # 环境配置
├── auto-dev/          # 自动开发
├── create-skill/      # 创建 skill
├── clean-project/     # 清理打包
├── run-qa/            # QA 测试
├── project-review/    # 老师式复习
├── project-learn/     # 教练式学习
├── write-resume/      # 写简历
└── mock-interview/    # 模拟面试
```
