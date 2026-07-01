# rag-server Skills 简介

本目录存放可复用的 Agent 工作流（skills）。每个 skill 一个文件夹，入口为 `SKILL.md`；部分 skill 带有 `scripts/`（可执行脚本）和 `references/`（参考资料）。

在 Cursor 对话中用自然语言触发即可，Agent 会读取对应 `SKILL.md` 并按步骤执行。下文命令路径保持英文原文。

## Skills 一览


| 目录               | 功能                                     | 适用场景                   | 触发口令（示例）                |
| ---------------- | -------------------------------------- | ---------------------- | ----------------------- |
| `setup`          | 交互式生成 `config/settings.yaml` 并校验环境可运行。 | 第一次在本地跑起 rag-server。   | 初始化、setup、环境配置          |
| `auto-dev`       | 按 `DEV_SPEC.md` 排期自动写代码、跑测试、更新进度。      | 规格驱动地继续开发或补某个任务（如 B2）。 | 自动开发、auto dev、autopilot |
| `create-skill`   | 按规范脚手架新建或维护 Agent Skill。               | 为本项目或其它项目增加工作流。        | 创建 skill、new skill      |
| `clean-project`  | 清理缓存与本地产物，脱敏 API Key 便于分享。             | 打包发他人或提交前去掉脏文件与密钥。     | 清理项目、打包、package         |
| `run-qa`         | 按测试计划串行执行用例并记录可追溯结果。                   | 发版前回归或排查 MCP/检索/面板问题。  | 跑测试、QA 测试、run QA        |
| `project-review` | 按题库逐章提问复习，记录掌握度。                       | 系统复盘项目知识点，考前集中复习。      | 复习项目、复盘、review project  |
| `project-learn`  | 按知识域动态出题、追问并评分，跟踪学习进度。                 | 逐块吃透项目，检验理解深度。         | 学习项目、面试准备、learn project |
| `write-resume`   | 根据岗位画像生成四段式简历项目描述。                     | 把本项目写进简历并突出匹配亮点。       | 写简历、resume、项目经历         |
| `mock-interview` | 模拟面试问答，结束后输出评分报告。                      | 面试前演练，检验简历能否经得住追问。     | 模拟面试、mock interview、考我  |


## 各 Skill 说明

### setup — 环境配置

**功能**  
引导你选择 LLM / Embedding / Vision / Rerank 等 Provider，收集 API Key，生成 `config/settings.yaml`，安装依赖并校验能否启动 Dashboard。未内置的 Provider 可按项目插件架构脚手架扩展；单步失败会自动诊断重试（最多 3 轮）。

**适用场景**

- 新机器、新克隆仓库，第一次把项目跑起来
- 更换 API Key 或切换厂商，需要重新生成配置
- 不确定 `settings.yaml` 该怎么填

**用法**

1. 在 `rag-server/` 目录下对 Agent 说：**「按 setup 配置环境」** 或 **「setup」**
2. 按提示选择 Provider 并填写 Key
3. 完成后启动面板：`python scripts/start_dashboard.py` 或 `streamlit run dashboard.py`

详见 `setup/SKILL.md`；Provider 说明见 `setup/references/`。

---

### auto-dev — 规格驱动自动开发

**功能**  
读取 `DEV_SPEC.md`，用 `sync_spec.py` 拆成 `references/` 分章；从 `06-schedule.md` 取下一待办任务，按架构实现代码与测试；`pytest` 失败自动修复（≤3 轮）；完成后更新 spec 进度，可选 git 提交。

**适用场景**

- 按 DEV_SPEC 持续迭代，不想手动找「下一项该做什么」
- 指定某个任务 ID（如「自动开发 C14」）单独推进
- 改完 DEV_SPEC 后，让 Agent 按新规格写代码

**用法**

1. 对 Agent 说：**「自动开发」** 或 **「auto dev B2」**（可带任务 ID）
2. 仅同步文档、不写代码时（安全，不改 `src/`）：
  ```bash
   python3 skills/auto-dev/scripts/sync_spec.py --force
  ```
   该命令只更新 `auto-dev/references/*.md` 与 `.spec_hash`，不影响运行中的服务。
3. Agent 流程：同步 → 读排期 → 实现 → 测试 → 勾进度

详见 `auto-dev/SKILL.md`。

---

### create-skill — 创建 Skill

**功能**  
提供 Skill 结构规范（`SKILL.md` + `scripts/` / `references/` / `assets/`）、触发描述写法与脚手架脚本，一键生成目录模板。

**适用场景**

- 为 rag-server 或其它项目新增 Agent 工作流
- 现有 skill 触发不准、步骤混乱，需要重写
- 学习如何写好可复用的 Skill

**用法**

1. 对 Agent 说：**「创建 skill」** 或 **「new skill」**
2. 脚手架（生成空目录模板）：
  ```bash
   python3 skills/create-skill/scripts/init_skill.py <skill-name> --path skills
  ```

详见 `create-skill/SKILL.md`。

---

### clean-project — 清理与脱敏打包

**功能**  
预览并删除 Python 缓存、`.venv`、构建产物、`data/` / `logs/`（可选保留）、IDE 配置等；将 `config/settings.yaml` 中的 API Key 替换为占位符，产出可分享的精简代码库。

**适用场景**

- 代码要发给别人、上传公开仓库或归档前
- 提交前确认无真实 Key、无多余缓存与本地数据

**用法**

1. 对 Agent 说：**「清理项目」** 或 **「打包」**
2. 预览（不删除）：
  ```bash
   python3 skills/clean-project/scripts/clean.py
  ```
3. 执行清理：
  ```bash
   python3 skills/clean-project/scripts/clean.py --execute
   python3 skills/clean-project/scripts/clean.py --execute --keep-data   # 保留 data/
  ```

详见 `clean-project/SKILL.md`。

---

### run-qa — 全自动 QA

**功能**  
严格串行执行 `QA_TEST_PLAN.md` 中的用例（CLI、Dashboard、MCP、Provider 切换、数据生命周期等）；每条需终端输出证据；失败自动修复（≤3 轮）；结果写入 `QA_TEST_PROGRESS.md`。

**适用场景**

- 发版前全量或按章节回归（如「跑测试 G」）
- 排查 ingest / query / MCP / Dashboard 的实际行为问题
- 需要可审计的测试记录，而非「看代码觉得能过」

**用法**

1. 对 Agent 说：**「跑测试」** 或 **「跑测试 G-01」**（可指定章节或用例 ID）
2. 常用辅助脚本（在 `skills/run-qa/scripts/`）：
  - `qa_bootstrap.py` — 准备/清空测试数据
  - `qa_config.py` — 切换 Provider 配置
  - `qa_multistep.py` — 多步骤用例
  - `qa_validate_notes.py` — 校验测试记录格式

详见 `run-qa/SKILL.md`、`run-qa/QA_TEST_PLAN.md`。

---

### project-review — 老师式复习

**功能**  
按 9 章 71 道题库苏格拉底式提问：先问后评、给参考答案与延伸；记录各章掌握度；每次开场回顾 `review_progress.md` 并建议继续或补弱项。

**适用场景**

- 系统复盘架构、摄取、检索、MCP、评估等模块
- 考前按章节巩固，支持断点续学

**用法**

1. 对 Agent 说：**「开始项目复习」** 或 **「复习项目」**
2. 题库：`project-review/references/question_bank.md`
3. 进度：`project-review/review_progress.md`（自动读写）

详见 `project-review/SKILL.md`。

---

### project-learn — 教练式学习

**功能**  
结合 `DEV_SPEC`、`settings.yaml` 与 `src/` 结构，按 10 大知识域 45 个知识点动态出题；每题最多 4 轮追问；四维评分 + 代码路径/文档/命令指引；进度写入 `LEARNING_PROGRESS.md`。

**适用场景**

- 不想一次啃完 DEV_SPEC，想按知识点逐步掌握
- 面试前针对薄弱模块（如 Hybrid Search、Trace）专项补强
- 自检「是否真的懂」，而非只看过文档

**用法**

1. 对 Agent 说：**「开始学习项目」**，选择模式（新学 / 复习 / 查看进度 / Agent 推荐）
2. 进度文件：`project-learn/references/LEARNING_PROGRESS.md`

详见 `project-learn/SKILL.md`。

---

### write-resume — 写简历

**功能**  
结合 `project_highlights.md` 与你的岗位画像（方向、业务背景、技术侧重），输出四段式项目经历（背景 → 目标 → 过程 bullet → 结果量化）；可中英双语；附面试追问预测与反模式检查。

**适用场景**

- 把本 RAG 项目写进简历（校招/社招、RAG/Backend/Agent 等方向）
- 需要合理量化表述，且能经得住面试追问

**用法**

1. 对 Agent 说：**「帮我写简历项目经历」** 或 **「resume」**
2. 按提问提供目标岗位与业务场景
3. 参考：`write-resume/references/resume_principles.md`、`project_highlights.md`

详见 `write-resume/SKILL.md`。

---

### mock-interview — 模拟面试

**功能**  
可选 5 种面试官风格（FAST / DEEP / CODE / HARD / MIX）；掷骰选题；考察项目综述、简历深挖、技术深挖；逐字记录问答；结束后生成含参考答案、包装识别与五维评分的报告。

**适用场景**

- 面试前完整演练一轮
- 验证简历描述与项目理解是否一致、能否扛住深挖

**用法**

1. 对 Agent 说：**「开始模拟面试」**，选择风格，可粘贴简历
2. 报告落盘：`interview_report_YYYYMMDD_HHMMSS.md`
3. 参考资料：`mock-interview/references/question_bank.md`、`project_knowledge.md`

详见 `mock-interview/SKILL.md`。

---

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

## 怎么选 Skill？


| 你想…      | 用哪个                                |
| -------- | ---------------------------------- |
| 第一次跑起来   | `setup`                            |
| 按规格继续写代码 | `auto-dev`                         |
| 发版前验证功能  | `run-qa`                           |
| 搞懂项目在讲什么 | `project-learn` → `project-review` |
| 写简历、练面试  | `write-resume` → `mock-interview`  |
| 分享代码前清理  | `clean-project`                    |
| 新增自己的工作流 | `create-skill`                     |


