---
name: create-skill
description: "创建或维护 Agent Skill 的规范与脚手架：结构、触发描述、references/scripts/assets 拆分。用户说「创建 skill」「新建 skill」「写 skill」「更新 skill」「create skill」「new skill」「build a skill」或需要制作可复用工作流包时使用。"
---

# 创建 Skill（Create Skill）

指导如何编写高质量、可触发的 Agent Skill。

## Skill 是什么

Skill 是模块化、自包含的能力包，通过专业知识、工作流和工具扩展 Agent 能力，相当于特定领域任务的「上岗手册」。

### Skill 能提供什么

1. **专用工作流** — 特定领域的多步骤流程
2. **工具集成** — 特定文件格式或 API 的操作说明
3. **领域知识** — 项目特有的 schema、业务逻辑
4. **捆绑资源** — 脚本、参考资料、模板等可复用资产

## 核心原则

### 简洁至上

上下文窗口是公共资源。Skill 与系统提示、对话历史、其他 Skill 元数据、用户请求共享窗口。

**默认假设：Agent 已经足够聪明。** 只补充 Agent 原本没有的信息。对每段内容自问：「Agent 真的需要这段解释吗？值得这些 token 吗？」

优先用简短示例，少用冗长说明。

### 设定合适的自由度

按任务脆弱程度匹配约束强度：

- **高自由度（文字说明）**：多种做法都合理、依赖上下文决策、启发式引导
- **中自由度（伪代码/带参脚本）**：有首选模式、允许一定变化、配置影响行为
- **低自由度（固定脚本、少参数）**：操作易错、一致性关键、必须按固定顺序

窄桥需要护栏（低自由度），开阔地带允许多条路线（高自由度）。

### Skill 结构

每个 skill 包含必需的 `SKILL.md` 和可选捆绑资源：

```
skill-name/
├── SKILL.md（必需）
│   ├── YAML frontmatter（必需）
│   │   ├── name:（必需）
│   │   ├── description:（必需）
│   │   └── license:（可选）
│   └── Markdown 正文（必需）
└── 捆绑资源（可选）
    ├── scripts/          - 可执行代码（Python/Bash 等）
    ├── references/       - 按需加载的参考文档
    └── assets/           - 输出中使用的文件（模板、图标等）
```

#### SKILL.md（必需）

- **Frontmatter（YAML）**：含 `name`、`description`（必需）及可选 `license`。**仅 `name` 和 `description` 用于判断何时触发**，须写清功能与触发场景。
- **正文（Markdown）**：触发后加载的执行说明。

#### 捆绑资源（可选）

##### scripts/

用于需要确定性、或反复重写的逻辑。

- **何时放**：同一逻辑反复重写，或需要确定性执行
- **示例**：`scripts/rotate_pdf.py` 处理 PDF 旋转
- **好处**：省 token、可执行而不必读入上下文
- **注意**：修补或环境适配时 Agent 仍可能需阅读

##### references/

按需加载的参考文档。

- **何时放**：Agent 工作中需查阅的文档
- **示例**：`references/api_docs.md`、`references/finance.md`
- **好处**：保持 SKILL.md 精简，按需加载
- **最佳实践**：大文件（>10k 词）在 SKILL.md 中给出 grep 搜索提示
- **避免重复**：信息只放 SKILL.md 或 references 一处，详细内容优先放 references

##### assets/

不读入上下文、直接用于输出的文件。

- **何时放**：最终产出需要模板、图片、样板代码等
- **示例**：`assets/logo.png`、`assets/frontend-template/`

#### 不要放进 Skill 的内容

不要创建与功能无关的辅助文档：`README.md`、`INSTALLATION_GUIDE.md`、`CHANGELOG.md` 等。只保留 Agent 完成任务所需的信息。

### 渐进式披露

三级加载，管理上下文：

1. **元数据（name + description）** — 始终在上下文中（约 100 词）
2. **SKILL.md 正文** — 触发后加载（<5k 词）
3. **捆绑资源** — 按需加载（脚本可执行而不读入窗口）

**实践**：SKILL.md 正文控制在 500 行以内；接近上限时拆到 references，并在 SKILL.md 中说明何时阅读。

设计模式详见：
- 多步流程：[references/workflows.md](references/workflows.md)
- 输出格式：[references/output-patterns.md](references/output-patterns.md)

## 创建流程

1. 用具体例子理解 skill 用途
2. 规划可复用内容（scripts、references、assets）
3. 初始化 skill（运行 `init_skill.py`）
4. 编辑 skill（实现资源并写 SKILL.md）
5. 根据实际使用迭代

按顺序执行，有明确理由才可跳过。

### 步骤 1：用具体例子理解需求

除非用途已非常清楚，否则不要跳过。通过用户示例或经确认的生成示例，明确 skill 将如何被使用。

例如做 image-editor skill 时问：
- 支持哪些功能？编辑、旋转、还有其他吗？
- 用户会怎么说来触发？
- 能给几个使用场景吗？

明确 skill 应支持的功能后再进入下一步。

### 步骤 2：规划可复用内容

对每个例子分析：
1. 从零执行需要做什么
2. 哪些 scripts、references、assets 能反复帮上忙

例如 `pdf-editor` skill：旋转 PDF 每次都要重写代码 → 放 `scripts/rotate_pdf.py`。

列出要包含的 scripts、references、assets。

### 步骤 3：初始化

除非 skill 已存在仅需迭代，否则运行脚手架：

```bash
python .cursor/skills/create-skill/scripts/init_skill.py <skill-name> --path .cursor/skills
```

脚本会：
- 创建 skill 目录
- 生成带 frontmatter 和 TODO 的 SKILL.md 模板
- 创建 `scripts/`、`references/`、`assets/` 及示例文件

初始化后按需定制或删除示例。

### 步骤 4：编辑 Skill

Skill 是给**另一个 Agent 实例**用的，写入非显而易见的过程知识与领域细节。

#### 先实现捆绑资源

从规划的 `scripts/`、`references/`、`assets/` 开始；可能需要用户输入。

新增脚本必须**实际运行**验证无 bug、输出符合预期。不需要的示例文件应删除。

#### 更新 SKILL.md

**写作风格**：使用祈使句/不定式。

##### Frontmatter

- `name`：小写、连字符（如 `my-skill`）
- `description`：**主要触发机制**
  - 写清 skill 做什么、何时使用
  - **所有「何时使用」信息放 description**，不要放正文（正文触发后才加载）
  - 示例：`"处理 .docx 文档的创建、编辑与分析。用户说「编辑 word」「docx」时使用。"`

除 `name`、`description` 外不要加其他必需 frontmatter 字段。

##### 正文

写使用 skill 及其捆绑资源的说明。

### 步骤 5：迭代

1. 在真实任务上使用
2. 发现卡点或低效之处
3. 更新 SKILL.md 或捆绑资源
4. 再测试
