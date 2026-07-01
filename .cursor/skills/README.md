# ContextBridge Agent — 项目级 Skills

Cursor 在**仓库根**打开时自动发现本目录。在 Agent 对话中用自然语言触发即可。

## Skills 一览

| 目录 | 功能 | 触发口令（示例） |
|------|------|------------------|
| `create-skill` | 创建或维护 Agent Skill 规范与脚手架 | 创建 skill、new skill、create skill |
| `bridge-learn` | 三轨深度学习：A agents-master / B rag-server / C 全栈串联 | 学习项目、bridge learn、rag 学习、agents 学习 |
| `bridge-resume` | monorepo 简历（Agent + RAG 岗） | 写简历、bridge resume、项目经历 |

## Skills 说明

### create-skill

**逻辑设计**

| 环节 | 做什么 |
|------|--------|
| **定位** | 元规范 + 脚手架，教 Agent「如何写好一个 Skill」，本身不执行业务任务 |
| **结构约定** | 每个 skill = `SKILL.md`（frontmatter + 正文）+ 可选 `references/` / `scripts/` / `assets/` |
| **加载策略** | 渐进式披露：① 元数据常驻 ② 触发后读正文 ③ 按需读 references 或执行 scripts |
| **约束分级** | 按任务脆弱度选自由度：文字说明（高）→ 伪代码/模板（中）→ 固定脚本（低） |
| **产出** | `init_skill.py` 生成目录模板；`workflows.md` / `output-patterns.md` 提供流程与输出模式参考 |

**亮点**
- **触发设计**：强调 `description` 是唯一触发入口，WHEN 写进 frontmatter、不写进正文，减少误触发或漏触发
- **上下文管理**：大段知识外置 `references/`，正文控制在 500 行内，避免一次塞满窗口
- **确定性下沉**：反复重写或易错的逻辑放 `scripts/`，省 token 且执行结果一致
- **可复用模式**：workflow / 输出模板拆成独立 reference，新建 skill 时直接套用而非从零想结构

**使用方式**
1. 在仓库根对 Agent 说：**「创建 skill」** 或 **「按 create-skill 新建一个 skill」**
2. 说明 skill 用途与触发场景；Agent 按规范规划 references/scripts，并运行：
   ```bash
   python .cursor/skills/create-skill/scripts/init_skill.py <skill-name> --path .cursor/skills
   ```
3. 编辑生成的 `SKILL.md` 与捆绑资源；可用 `quick_validate.py` 校验结构

---

### bridge-learn

**逻辑设计**

| 环节 | 做什么 |
|------|--------|
| **定位** | 教练式学习，通过问答 + 追问帮用户吃透 monorepo，不是念固定题库 |
| **分流** | 开场选轨：A agents-master / B rag-server / C 全栈串联，各轨独立知识地图 |
| **准备** | 静默读 README、源码、配置，建立该轨上下文（不向用户提问） |
| **选题** | 按 `knowledge-*.md` 知识点 + `LEARNING_PROGRESS.md` 薄弱项选题 |
| **互动** | 动态出题 → ≤4 轮递进追问 → 五层评分 → 输出学习指南（含可跑命令） |
| **持久化** | 进度写入 `LEARNING_PROGRESS.md`，支持断点续学与 Agent 推荐下一题 |
| **资产分层** | 知识点清单、进度表在 `references/`；`SKILL.md` 只写阶段流程 |

**亮点**
- **三轨分流**：A/B/C 各管一块，避免 agents 与 rag 知识点混在一套题里学散
- **动态出题**：题目现场锚定真实文件路径生成，同一知识点可换角度重复学，不依赖死背 71 题
- **五层评价**：架构 / 功能 / 技术 / 亮点 / 验证五维打分，对齐「能讲设计也能指代码」
- **教练闭环**：每题必有学习指南 + hands-on 命令，学完知道「下一步读哪、跑什么」
- **断点续学**：按轨、按知识点记状态（⬜/🔴/🔶/✅），Agent 可推荐最弱项而非随机跳题

**使用方式**
1. **打开仓库根**（ContextBridge Agent），新开 Agent 对话
2. 说：**「开始学习项目」**、**「bridge learn」**；可指定轨，如 **「选 B 轨学 rag-server」**、**「C 轨学端到端 RAG 链」**
3. 按提示选学习模式（新学 / 复习 / 查看进度 / Agent 推荐）→ 选知识域 → 选知识点
4. 回答题目与追问；结束后查看评分、学习指南与进度更新  
   进度文件：`.cursor/skills/bridge-learn/references/LEARNING_PROGRESS.md`

| 轨 | 范围 | 知识点数 | 适合何时用 |
|----|------|----------|------------|
| A | agents-master（Host、多模式、记忆、MCP Client） | 15 | 吃透主应用设计与代码 |
| B | rag-server（摄取、检索、MCP Server） | 45 | 深入 RAG 模块（内容最完整） |
| C | 双项目串联（配置、调用链、模式组合） | 8 | 理解 monorepo 如何联调 |

---

### bridge-resume

**逻辑设计**

| 环节 | 做什么 |
|------|--------|
| **定位** | 把 ContextBridge monorepo 经历写成可投岗的简历项目描述（Agent 岗 + RAG 岗） |
| **输入** | `ask_questions` 采集岗位侧重、业务背景、技术偏好、格式要求 |
| **选材** | 从三份亮点库按岗位排序选 bullet：`highlights-agents` / `highlights-rag` / `highlights-integration` |
| **生成** | 严格四段式：背景 → 目标 → 过程（4–6 bullet）→ 结果（≥3 量化指标） |
| **校验** | 输出前反模式检查；无量化数据时标「建议值」待用户确认 |
| **延伸** | 附 3–5 条面试追问预测，便于写完即练自圆其说 |
| **资产分层** | 原则与亮点在 `references/`；`SKILL.md` 只写流程与匹配规则 |

**亮点**
- **岗位分流**：同一 monorepo 可按 Agent / RAG / 兼顾三种策略排 bullet，不靠一份模板硬套
- **三库对齐 learn**：亮点库与 `bridge-learn` 三轨对应，学完的主线可直接写进简历
- **画像先行**：先收业务背景再写「背景段」，减少模板腔、提高可读性
- **诚信边界**：放大策略表明确允许包装与建议量化、禁止编造未实现技术，降低面试露馅风险
- **可迭代输出**：初稿 → 反馈改侧重/措辞，而非一次性甩完结束

**使用方式**
1. 在仓库根对 Agent 说：**「写简历」**、**「bridge resume」**、**「帮我写 ContextBridge 项目经历」**
2. 回答画像问题：岗位侧重（Agent / RAG / 兼顾）、业务背景、技术侧重多选、格式要求等
3. Agent 输出四段式初稿 → 根据反馈迭代；需要时可要求英文版或追问预测列表  
   亮点库：`.cursor/skills/bridge-resume/references/highlights-*.md`

---

## 待完成 / 优化

| 模块 | 现状 | 待办 |
|------|------|------|
| **bridge-learn · A 轨** | 15 个核心知识点（简版） | 随 `agents-master/docs/` 与源码增补知识点；旅行/记忆/MCP 等可拆更细 |
| **bridge-learn · B 轨** | 45 点已映射 `knowledge-rag.md` | 与 `rag-server/DEV_SPEC.md` 变更保持同步；子项明细可迁入 `LEARNING_PROGRESS.md` |
| **bridge-learn · C 轨** | 8 个串联点 | 补充联调踩坑、端口/venv/配置故障案例 |
| **bridge-resume · highlights-agents** | 5 条简版亮点 | 对齐 A 轨加厚后的话术与量化角度 |
| **bridge-resume · highlights-rag** | 自 rag-server 亮点迁入 | 随 RAG 实现迭代更新条目 |
| **bridge-resume · highlights-integration** | 4 条 monorepo 叙事 | 与真实联调路径、演示脚本对齐 |
| **mock-interview** | 未建项目级版 | 面试前如需 monorepo 模拟面试再单开 skill |
| **触发与验证** | 依赖 Cursor 自动发现 | 新开 Agent 对话试触发；不稳时可在根 `README` 或 `.cursor/rules` 补充说明 |

## 维护入口

| 改什么 | 编辑哪里 |
|--------|----------|
| A/C 轨知识点 | `bridge-learn/references/knowledge-agents.md`、`knowledge-integration.md` |
| B 轨知识点 | `bridge-learn/references/knowledge-rag.md` |
| 学习进度 | `bridge-learn/references/LEARNING_PROGRESS.md` |
| 简历亮点 | `bridge-resume/references/highlights-*.md` |
| 简历原则 | `bridge-resume/references/resume_principles.md` |
