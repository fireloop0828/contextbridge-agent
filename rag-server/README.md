# RAG Server

> 一个可插拔、可观测的模块化 RAG（检索增强生成）服务框架，通过 MCP（Model Context Protocol）协议对外暴露工具接口，支持 Cursor / Copilot / Claude 等 AI 助手直接调用。同时也是一份专为**大模型相关岗位学习与面试求职**设计的实战项目与配套教学资源。

> **仓库位置**：本目录为 [ContextBridge Agent](https://github.com/fireloop0828/contextbridge-agent) monorepo 的 `rag-server/` 子项目；主应用 `agents-master/` 通过 `config.json` 以 MCP 方式引用本服务。完整 Skills 说明见 [skills/README.md](skills/README.md)。

---

## 📖 目录

- [项目概述](#-项目概述)
- [仓库位置](#-仓库位置)
- [快速开始](#-快速开始)
- [谁适合用这个项目 & 怎么用](#-谁适合用这个项目--怎么用)
- [简历参考](#-简历参考)
- [常见问题](#-常见问题)

---

## 🏗️ 项目概述

### 这个项目是什么

本项目将 RAG 面试中最常见的核心环节——**检索（Hybrid Search + Rerank）**、**多模态视觉处理（Image Captioning）**、**RAG 评估（Ragas + Custom）**、**生成（LLM Response）**——以及当下热门的应用协议 **MCP（Model Context Protocol）** 串联为一个完整的、可运行的工程项目。

**项目的一大亮点是极易适配到你自己的业务中**。得益于全链路可插拔架构，你可以快速将它结合到自己已有的项目里，无论你的背景和需求如何，都能找到适合自己的使用方式。具体的使用策略会在后文 [谁适合用这个项目 & 怎么用](#-谁适合用这个项目--怎么用) 中详细展开。

### 不只是项目，更是一整套思路

**比这个项目本身更有价值的，是它背后蕴含的一整套工程化思路**：

- 如何编写 **DEV_SPEC**（开发规格文档）来驱动开发
- 如何用 **Skill** 基于 Spec 自动完成代码编写
- 如何用 **Skill** 进行自动化测试、打包、环境配置
- 如何基于可插拔架构进行扩展（比如扩展到 Agent）

**学会了思路，你可以自己做全新的项目和扩展**。以上每一步的具体做法、设计思路，在笔记中都有对应的视频讲解，建议配合观看。

### 核心能力一览


| 模块                     | 能力                                                      | 说明                                                                                                                   |
| ---------------------- | ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| **Ingestion Pipeline** | PDF → Markdown → Chunk → Transform → Embedding → Upsert | 全链路数据摄取，支持多模态图片描述（Image Captioning）                                                                                  |
| **Hybrid Search**      | Dense (向量) + Sparse (BM25) + RRF Fusion + Rerank        | 粗排召回 + 精排重排的两段式检索架构                                                                                                  |
| **MCP Server**         | 标准 MCP 协议暴露 Tools                                       | `query_knowledge_hub`、`list_collections`、`get_document_summary`                                                      |
| **Dashboard**          | Streamlit 六页面管理平台                                       | 运行概览 / 知识浏览 / 文档入库 / 入库记录 / 检索记录 / 效果评测                                                                              |
| **Evaluation**         | Ragas + Custom 评估体系                                     | 支持 golden test set 回归测试，拒绝"凭感觉"调优                                                                                    |
| **Observability**      | 全链路白盒化追踪                                                | Ingestion 与 Query 两条链路的每一个中间状态透明可见                                                                                   |
| **Skill 驱动全流程**        | 从编写到测试、打包、配置一键完成                                        | setup / auto-dev / run-qa / clean-project / write-resume 等 Skill 覆盖完整开发生命周期（详见 [skills/README.md](skills/README.md)） |


### 技术亮点

**🔌 全链路可插拔架构**：LLM / Embedding / Reranker / Splitter / VectorStore / Evaluator 每一个核心环节均定义了抽象接口，支持"乐高积木式"替换，通过配置文件一键切换后端，零代码修改。

**🔍 混合检索 + 重排**：BM25 稀疏检索解决专有名词精确匹配 + Dense Embedding 解决同义词语义匹配，RRF 融合后可选 Cross-Encoder / LLM Rerank 精排，平衡查全率与查准率。

**🖼️ 多模态图像处理**：采用 Image-to-Text 策略，利用 Vision LLM 自动生成图片描述并缝合进 Chunk，复用纯文本 RAG 链路即可实现"搜文字出图"。

**📡 MCP 生态集成**：遵循 Model Context Protocol 标准，可直接对接 GitHub Copilot、Claude Desktop 等 MCP Client，零前端开发，一次开发处处可用。

**📊 可视化管理 + 自动化评估**：Streamlit Dashboard 提供完整的数据管理与链路追踪能力，集成 Ragas 等评估框架，建立基于数据的迭代反馈回路。

**🧪 三层测试体系**：Unit / Integration / E2E 分层测试，覆盖独立模块逻辑、模块间交互、完整链路（MCP Client / Dashboard）。

**🤖 Skill 驱动全流程**：内置 setup（环境配置）、auto-dev（规格驱动编码）、run-qa（回归测试）、clean-project（清理打包）、write-resume / mock-interview（求职辅助）等 Agent Skill，覆盖从代码编写到测试、打包、部署的完整开发生命周期。详见 [skills/README.md](skills/README.md)。

> 📖 详细架构设计、模块说明和任务排期请参阅 [DEV_SPEC.md](DEV_SPEC.md)

---

## 📂 仓库位置

本仓库为 **ContextBridge Agent** monorepo，RAG 服务位于 `rag-server/` 子目录：

```
ContextBridge Agent/
├── agents-master/     # 主应用（Streamlit + LangGraph Agent，通过 MCP 调用本服务）
├── rag-server/        # 本 README 所在目录
└── README.md          # 顶层快速开始（主应用 + RAG 联调）
```

- **克隆**：`git clone https://github.com/fireloop0828/contextbridge-agent.git`，进入 `cd rag-server`
- **与主应用联调**：先在本目录配置 `config/settings.yaml` 并启动 Dashboard；再在 `agents-master/` 启动主应用（`config.json` 已预置 `rag-server` MCP）
- **从零开发体验**：使用 `auto-dev` Skill 按 [DEV_SPEC.md](DEV_SPEC.md) 排期迭代；`skills/dev/` 下保留早期 Skill 目录，**以 `skills/` 根目录下的 Skill 为准**（见 [skills/README.md](skills/README.md)）

---

## 🚀 快速开始

### 1. 克隆并进入目录

```bash
git clone https://github.com/fireloop0828/contextbridge-agent.git
cd contextbridge-agent/rag-server
```

### 2. 环境配置（二选一）

**方式 A — Setup Skill（推荐）**

在 Cursor / VS Code 中打开 `rag-server/`，对 Agent 说 `**setup`** 或 **「按 setup 配置环境」**。Skill 会引导：Provider 选择 → API Key → `pip install -e ".[dev]"` → 生成 `config/settings.yaml` → 校验能否启动 Dashboard。

**方式 B — 手动配置**

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cp config/settings.dashscope.example.yaml config/settings.yaml
# 编辑 config/settings.yaml，填入 api_key 等
```

> `config/settings.yaml` 含真实 Key 时**勿提交 Git**；可与 `agents-master/.env` 中的 `DASHSCOPE_API_KEY` 使用同一把百炼 Key。

### 3. 启动服务

```bash
# RAG 控制台（Streamlit）
streamlit run dashboard.py

# 与 agents-master 同机时换端口
python scripts/start_dashboard.py --port 8502

# MCP Server（stdio，供 Cursor / agents-master 调用）
python main.py
# 或安装后：mcp-server
```

更多面板说明见 [docs/管理面板指南.md](docs/管理面板指南.md)；Skills 用法见 [skills/README.md](skills/README.md)。

---

## 🎯 谁适合用这个项目 & 怎么用

大家的背景不同——有的校招、有的社招；基础也不同——有的有 AI 项目经验、有的是转方向。因此对于这个项目的使用策略也应该不同，**请一定灵活使用，切忌生搬硬套**。

不过有一点是通用的：**整套项目背后的思路**——如何写 Spec 快速拉起一个项目、如何用 Skill 驱动 AI 自动编码和测试——这些工程化方法论适用于任何项目，值得所有人参考学习。

对于项目本身在不同场景下的使用策略，我会提供一些具体的例子，并以我自己的亲身经历展开——**如果是我自己，面对不同的情况，我会怎么使用这个项目**——给大家作为参考。

### 1. 纯学习 RAG —— 把项目当作 RAG 全流程的学习材料

这个项目本身就是一个完整的 RAG 系统，可以作为学习 RAG 的配套实战项目。

我最开始学习 RAG 的时候，看的是这本书：**《大模型RAG实战：RAG原理、应用与系统构建》**（汪鹏、谷清水、卞龙鹏等人工智能领域专家编著）。你完全可以结合这本书来学习 RAG，书中涉及的典型环节——检索、生成、向量数据库、分块策略、重排序等——其实不管你看哪本 RAG 相关的书，核心内容都是这些。

**这个项目就是把这些步骤串起来了**，所以它可以作为一个通用的 RAG 全流程项目来学习整个过程。你可以配这本书，我相信你也可以配其它的 RAG 书籍，因为流程是通的。面试 RAG 其实也无非是这些过程的组合、原理，以及在实际中遇到的困难和优化。

### 2. 时间紧迫 —— 缺一个项目拿去面试

如果你现在没有 AI 相关项目、急需一个项目去面试，那么可以：

1. **直接使用本项目**，克隆仓库后进入 `rag-server/`，用 Setup Skill 跑起来
2. **结合 write-resume Skill** 写自己的简历（Skill 会根据你的背景定制化生成项目描述）
3. **尝试理解项目**，跑通核心流程，结合我后续总结的该项目面试问题，先去面试
4. **随着面试深入理解、扩展项目**——面试本身就是最好的学习驱动力

比如现在 3 月份，需要找暑期实习的同学，时间紧迫——先写上去，一边面试一边学习，有时间再扩展。解决你着急面试没有项目的燃眉之急。思路就是：**先写上去 → 去面试 → 根据面试反馈改进项目**。

通常暑期实习从 3 月到 7 月都有机会。找到了实习、有了一个大模型项目经验后，再以此为跳板继续学习——7~10 月秋招，甚至到明年 3 月春招，你有大量的时间持续积累。现在开始虽然看起来有点晚，但其实不晚。如果你能保持学习节奏，从现在到明年 3 月，学习整整一年，校招上岸大模型方向绝对没有问题。**关键在于你自己能不能保持这么长时间的学习力。**

### 3. 时间相对充分 —— 以本项目为起点进行扩展

你可以把这个项目作为起点，根据自己的发展方向进行针对性扩展。DEV_SPEC 中也写了扩展方向，这里列几个常见的：

- **想补充 Agent 知识**：自己实现 Agent 端，做一些上下文处理、Tool Calling、ReAct 逻辑，把本项目作为 Agent 的一个模块和能力，变成一个 **Agent + RAG** 的项目
- **想展示后端工程能力**：加上后端部署能力，写 Dockerfile，做 CI/CD 流水线，加上监控和日志收集
- **想把 RAG 做深入**：扩展到 Agentic RAG、Graph RAG 等高级形态，或者在检索策略上做更多优化实验

每个人发展方向不一样——就像项目配套的 write-resume Skill，它写简历的时候会先问你的背景和情况。你定位大模型应用开发工程师、RAG 工程师、全栈工程师，校招、社招的要求都是不一样的（具体大模型不同岗位介绍和技术栈可以看笔记的**大模型岗位介绍**部分），所以需要自己进行针对性扩展。

> **强烈建议**：不管你什么背景、怎么扩展，你大概率需要结合自己的业务来写简历。所以**至少试一下**——把你自己领域的文档（金融、法律、医疗，或者你的业务文档）丢进去，看一下检索效果。如果效果不好，再去调整和改进。这个过程本身就是最好的学习，也是面试时最有说服力的实战经验。

### 4. 时间特别充分 —— 从零体验完整工作流

如果你时间充足，我建议你基于 [DEV_SPEC.md](DEV_SPEC.md) 用 `**auto-dev` Skill** 从零体验完整工作流，甚至在现有规格上**自行改写 DEV_SPEC**，从文档设计开始，一点点体验：

**文档设计 → AI 写代码 → 改进迭代 → 测试 → 部署**

整个过程的方法论。其中 DEV_SPEC 怎么写、Skill 怎么设计，这些都在笔记项目部分的对应视频中有讲解。你可以重新设计文档、改进文档，甚至直接做 Agent 方向的东西，来走完整个流程。

这样做你会学习到**开发一个项目的完整思路**。这套方法最大的好处是**下限极低**——几乎你都能设计出来、完成整个项目。这样你既学会了思路，又学会了过程，而且项目可以高度定制。群里已经有很多朋友都这么做了。

### 5. 融入现有项目 —— 把 RAG 能力集成到你已有的项目中

这其实也是一种很好的策略，我自己可能也会用这种方式。以我亲身经历现身说法：

我之前找工作时，其实已经有 2 个 Agent 项目了，只是 RAG 流程跑得很粗。我简历上大概的写法是"Agent 项目做了啥，其中涉及了一些 RAG 的知识"。面试的时候，面试官多少都会问 RAG 的内容，然后我和他讲，但因为之前项目的 RAG 系统很浅——其实就是做了一个基本的 Embedding 向量匹配，没有粗排、重排等策略——所以面试官一问就比较浅。

做了这个项目之后，一种处理方式是**把本项目的 RAG 能力融入到之前的 Agent 项目中**，在简历上不作为独立项目，而是作为 Agent 项目的一部分来描述。例如：

> *"……项目中使用自研的模块化 RAG 系统进行知识检索，采用 BM25 + Dense Embedding 混合召回并通过 RRF 融合排序，结合 Cross-Encoder 重排序提升 Top-K 精准度；支持多模态文档处理（PDF 解析 + Image Captioning），通过 MCP 协议暴露标准化工具接口供 Agent 调用。集成 Ragas 评估框架，建立 Golden Test Set 回归测试机制，持续优化检索质量……"*

这样你原有的 Agent 项目就有了 RAG 深度，面试官再问你就有东西可讲了。

### 6. 产品经理 —— 对，你没看错，PM 也可以用这个项目

大模型产品经理面试越来越多地会考 RAG 相关知识，有些公司甚至要求产品经理自己写一个 POC（Proof of Concept）再交给开发。**这个项目和背后的方法论，完全可以帮你做到这一点。**

**为什么 PM 可以用：**

1. **面试需要**：大模型产品岗会考 RAG 的基本原理和流程，你通过这个项目可以直观感受 RAG 的整个过程——从文档摄取、分块、向量化、检索、重排到最终生成，建立起产品层面的理解
2. **POC 能力**：你完全可以用这套方法构建出整个项目——写文档（DEV_SPEC），或者直接用现有的文档，然后用 Skill 让 AI 帮你生成代码。面试的时候你说的是你的思路和产品设计，代码是 AI 帮你写的，这在当下完全合理
3. **不需要关心技术细节**：产品不用关心每一行代码怎么写，但通过跑通这个流程，你能从产品层面思考痛点——比如检索不准怎么定义指标、用户体验上怎么设计反馈机制、数据质量如何影响 RAG 效果等

**具体怎么做：**

- 克隆仓库，进入 `rag-server/`，用 Setup Skill 跑起来，体验完整流程
- 把你自己业务领域的文档丢进去，看检索效果，思考产品层面的优化方向
- 面试时讲你的产品思路和设计思考，技术实现部分说明是用 AI 辅助完成的

> 💡 笔记中也提供了 **Vibe Coding** 相关教程（如 Tina Huang 老师的讲解），非常适合非技术背景的同学参考，用 AI 快速构建原型。

### 关于"项目浅"这件事

最后我想独立提一点（这一点适用于上面所有情况）：

**所有项目的深入优化不是一步到位的。**

如果你是转行，项目都是自己做的，多少会遇到面试官觉得你项目浅的问题。我之前也提到过这一点，但不用害怕：

1. **项目深度不是入行的必要条件。** 我去年拿了 6 个 offer，其中包括大厂 offer，即使这样，还是有面试官觉得我项目浅。面试还会考虑很多其他方面——理论基础、算法能力、背景匹配、知识广度等等。不要因为觉得自己转行项目浅就觉得自己转不了。
2. **项目是在不断优化和深入的。** 面试官说你项目浅，你听他的反馈，一定能听出来他为什么觉得浅——比如觉得你数据不够复杂，那你就造一些复杂数据；觉得你图片处理太简单，那你可以扩展多模态策略。我自己也是在面试过程中不断往项目里加东西：我之前做的 Agent 项目，随着面试推进，我往里加了部署、训练、反思数据、评估模块——整个过程都是随着面试同步进行的。

**给自己预留多一点面试时间，一边面试，一边改进和加深。** 所以这里就又提到了整套项目的思路——学会这些思路，你才能持续扩展，而且扩展的门槛很低，都是想好想法让 AI 写嘛，所以不用怕。

说一个真实数据：**这个项目从立项到完成，是我下班后用了大概 2 个月时间做的**，期间我还要上班、做自媒体、自媒体也有其他内容要产出。所以我希望你不要完全指望这个项目作为一个不用扩展就特别深入的项目，特别是社招的同学。但反过来想——两个月的下班时间就做出了这些，如果你学会了这套方法，自己扩展的速度会有多快？

方法都有了，所有的方案、过程、记录都有留档和视频讲解。**最终一定要靠你自己去扩展、迭代，做成最适合你自己的项目。**

---

## 📝 简历参考

> ⚠️ **强烈建议**：请使用项目内置的 **write-resume Skill** 来生成你的简历项目经历，而不是直接复制下面的示例。
>
> 简历项目经历**一定是针对性的**——需要结合你自己的业务背景、目标岗位、技术侧重来定制化生成。下面的示例仅用于展示 Skill 的输出效果和不同场景的写法参考，**直接照搬没有任何意义**。
>
> **如何使用 write-resume Skill**：在 Cursor / VS Code 中对 Agent 说 `**写简历`** 或 `**resume**`，Skill 会引导你完成画像采集并自动生成四段式简历。详见 [skills/write-resume/SKILL.md](skills/write-resume/SKILL.md)。

### write-resume Skill 工作方式

Skill 采用 **"写作原则 + 项目亮点 + 用户画像 = 定制化简历"** 的三角模型，流程如下：

1. **画像采集**：Skill 会询问你的目标岗位（RAG Engineer / Backend / Agent 等）、业务背景、技术侧重、特殊要求
2. **亮点匹配**：根据你的岗位方向，从项目 10 大技术亮点中筛选 3-5 个最匹配的写入 bullet points
3. **四段式生成**：严格按 **背景 → 目标 → 过程 → 结果** 结构输出，每条 bullet 遵循"动词开头 + 技术细节 + 量化效果"
4. **面试追问预测**：自动生成 3-5 条面试官可能的追问，帮你提前准备

### 示例一：校招 · RAG Engineer 方向

> 以下为 Skill 基于"校招、RAG 方向、通用框架模式"生成的示例输出：

**智能知识检索与问答系统** | 2024.09 - 2025.02 | 独立设计与开发

**背景**：针对企业级知识库场景中文档分散、检索精度不足、AI 应用难以接入私有知识的共性痛点，设计并实现了模块化 RAG 检索框架。

**目标**：构建基于混合检索 + MCP 协议的智能知识问答系统，实现精准语义检索与 AI Agent 直接调用私有知识库的能力，将文档问答准确率提升至 90% 以上。

**过程**：

- 设计 BM25 + Dense Embedding 混合召回架构，通过 RRF 融合排序平衡查全率与查准率，结合 Cross-Encoder 重排序将 Top-10 命中率提升约 25%
- 构建全链路 Ingestion Pipeline（PDF 解析 → Markdown → 语义分块 → Metadata 增强 → Embedding → Upsert），集成 Vision LLM 实现图片自动描述并缝合进 Chunk，复用纯文本链路即可"搜文字出图"
- 实现 LLM / Embedding / Reranker / VectorStore 全链路可插拔架构，定义统一抽象接口，通过配置文件一键切换后端 Provider，支持 4+ LLM Provider 零代码切换
- 集成 Ragas + Custom 双评估体系，建立 Golden Test Set 回归测试机制，覆盖 Faithfulness / Relevancy / Recall 等维度，拒绝"凭感觉"调优
- 基于 Skill 驱动全流程开发，通过 setup / auto-dev / run-qa / clean-project 等 Agent Skill 覆盖编码、测试、配置、打包完整生命周期，2 个月业余时间完成 68 个子任务的全量交付

**结果**：系统支撑 5000+ 篇文档的实时语义检索，检索准确率（Hit Rate@10）达 92%，端到端查询延迟控制在 800ms 以内，三层测试体系（Unit / Integration / E2E）覆盖 1300+ 测试用例。

**技术栈**：Python / LangChain / ChromaDB / BM25 / Cross-Encoder / MCP Protocol / Streamlit / Ragas / Azure OpenAI

### 示例二：社招 · 已有 Agent 项目，融入 RAG 深度

> 以下为 Skill 基于"社招、Agent 方向、Windows 平台开发业务背景"生成的示例输出（将 RAG 能力融入已有 Agent 项目）：

**Windows 平台智能知识助手** | 2024.06 - 2025.02 | 核心开发

**背景**：在 Windows 平台开发团队中，版本发布相关信息（Release Notes、变更日志、补丁公告、兼容性说明等）分散于多个 Wiki、文档仓库和内部系统，工程师排查版本差异或回答客户问题时需跨系统翻找，现有关键词搜索无法理解语义，导致检索效率低、信息遗漏频发。

**目标**：为团队构建基于 Agent + RAG 架构的智能知识助手，实现跨系统文档的语义检索与自动问答，通过 MCP 协议集成至工程师日常工具链（VS Code / Claude Desktop），将文档查找时间缩短 60% 以上。

**过程**：

- 设计 Agent + RAG 分层架构，Agent 端负责意图识别与 Tool Calling，RAG 端提供 BM25 + Dense Embedding 混合召回 + Cross-Encoder 精排的两段式检索能力，通过 MCP 协议暴露标准化工具接口供 Agent 调用
- 实现全链路 Ingestion Pipeline，支持 PDF / Markdown 多格式文档解析，集成 Vision LLM 自动生成图片描述（架构图、截图等），解决"搜文字出图"的多模态检索需求
- 构建可插拔后端架构，LLM / Embedding / Reranker / VectorStore 均定义抽象接口，支持 Azure OpenAI ↔ DeepSeek ↔ Ollama 一键切换，适配团队不同网络环境
- 搭建 Streamlit Dashboard 管理平台，提供运行概览、知识浏览、文档入库、入库/检索记录、效果评测六大功能页，实现全链路白盒化可观测
- 集成 Ragas 评估框架 + Golden Test Set 回归测试，在版本迭代中持续监控检索质量，Faithfulness 评分稳定在 0.85 以上
- 采用 Skill 驱动全流程开发模式，编写 DEV_SPEC 规格文档驱动 auto-dev 自动编码、run-qa 自动测试与修复、setup 一键环境配置，5 大 Agent Skill 覆盖完整开发生命周期，2 个月业余时间完成 68 个子任务交付

**结果**：系统覆盖团队 8000+ 篇技术文档，工程师日均文档查询时间从 15 分钟缩短至 3 分钟，检索准确率 Hit Rate@10 达 90%，已通过 MCP 协议接入 3 个内部 AI 工具，累计处理查询 2 万+ 次。

**技术栈**：Python / Agent / Tool Calling / RAG / BM25 / Dense Retrieval / Cross-Encoder / MCP Protocol / ChromaDB / Streamlit / Ragas / Skill-Driven Development / Azure OpenAI

### 示例三：社招 · 后端工程师转 AI 方向

> 以下为 Skill 基于"社招转 AI、后端/架构方向、金融合规业务背景"生成的示例输出：

**合规智能文档检索系统** | 2024.10 - 2025.02 | 设计与主导开发

**背景**：在某金融机构合规部门，法规文件和内部政策文档持续增长至万级规模，合规团队在审查和咨询场景中需要快速定位特定条款，但现有全文搜索系统只能精确匹配关键词，无法理解"反洗钱"与"AML"等语义近义表达，条款定位效率低下。

**目标**：设计并实现模块化 RAG 检索系统，将语义检索能力引入合规文档管理流程，支持近义词、跨语言条款匹配，目标将合规条款定位准确率提升至 90% 以上。

**过程**：

- 主导系统架构设计，采用全链路可插拔架构，LLM / Embedding / Reranker / Splitter / VectorStore 均定义抽象接口与工厂模式，通过 YAML 配置一键切换后端，零代码修改即可适配不同部署环境
- 实现 BM25 稀疏检索 + Dense Embedding 语义检索的混合召回策略，通过 RRF 融合排序兼顾专有名词精确匹配与语义近义匹配，检索准确率较纯向量方案提升 22%
- 构建完整的数据摄取管线，支持 PDF 解析 → 语义分块 → Chunk Refinement → Metadata Enrichment → 向量化存储，实现 DocumentManager 幂等管理，保证文档更新时的数据一致性
- 搭建三层测试体系（Unit / Integration / E2E），覆盖 1300+ 测试用例，集成 Ragas 评估框架建立自动化回归机制，确保迭代过程中检索质量不退化
- 基于 MCP 协议暴露标准化工具接口，支持 GitHub Copilot / Claude Desktop 等 AI 助手直接调用，实现"一次开发、多端调用"的服务化部署
- 实践 Skill 驱动全流程工程化方法，基于 DEV_SPEC 规格文档驱动 AI Agent 自动完成编码（auto-dev）、测试（run-qa）、环境配置（setup）、清理打包（clean-project），68 个子任务全量由 Agent 交付，开发周期压缩至 2 个月业余时间

**结果**：系统上线后支撑 12000+ 篇合规文档的实时语义检索，条款定位准确率从 68% 提升至 91%，单次查询延迟控制在 700ms，合规团队文档审查效率提升约 50%。

**技术栈**：Python / 可插拔架构 / 工厂模式 / BM25 / Dense Retrieval / RRF / Cross-Encoder / ChromaDB / MCP Protocol / Streamlit / Ragas / Skill-Driven Development / Azure OpenAI

---

> 💡 **使用提醒与重要说明**：
>
> **1. 关于放大策略**：write-resume Skill 中内置了我设计的**放大策略**——AI 会在合理范围内对你的项目经历进行包装和放大（例如量化指标、业务规模等）。这是我允许的，也是简历写作的正常做法。但这意味着：**生成简历后，你必须想清楚面试官可能针对每一条追问什么、你该怎么回答**。Skill 在生成简历的同时会自动给出 3-5 条面试追问预测，请认真准备这些问题。
>
> **2. 把简历当作实践清单**：简历中写到的每一个技术点，你都应该**真正去试一下**。比如简历写了"检索准确率提升 XX%"——那你就应该在自己的数据上跑一下，看看实际效果如何，过程中遇到了什么问题，你是怎么调优解决的。这些实践经验才是面试时真正有说服力的内容，也是你真正学到东西的过程。简历里没涉及到的部分（比如你没试过多模态、没跑过评估），也可以以此为契机去做代码实验。
>
> **3. 生成的是初稿，请务必结合自身情况修改**：Skill 生成的简历是**初稿**，不是终稿。你需要根据自己的实际情况进行调整——哪些技术你确实深入用过、哪些只是了解、哪些数据需要换成你自己的。简历写作有一条铁律：**写在简历上的东西，你一定要会讲**。即使某个点是放大的，你也要想清楚面试官会怎么问、你怎么自圆其说。说不清楚的东西宁可不写，写上去就要能扛住追问。
>
> **4. 方法比模板更重要**：整个简历编写的思路是我的——包括放大策略、四段式结构（背景 → 目标 → 过程 → 结果 → 技术栈）、亮点匹配逻辑等，这些都沉淀在 write-resume Skill 里。如果你有自己更信任的简历模板，或者你对项目做了扩展修改，完全可以去修改 Skill 本身来适配。**学会这套"用 Skill 沉淀方法论、让 AI 按规则执行"的逻辑，比简历本身更有价值**——这个思路可以复用到你未来任何项目的简历编写中。
>
> **5. 强烈建议写上 Skill 驱动全流程**：我个人的意见是，**Skill 驱动全流程开发这个闭环，适合写在任何人的简历上**。Skill 是当下非常热门的方向，已经是面试中的必考内容，很多公司内部也在研究如何用 Skill 加速项目构建。讲清楚你是如何使用 Skill 完成整个项目从编码 → 测试 → 修复 → 配置 → 打包的完整闭环，这本身就是一个比较创新和前沿的亮点，面试官会对此印象深刻。关于 Skill 相关内容在面试中怎么讲、怎么回答追问，我后面也会提供一些例子给大家参考。

---

## ❓ 常见问题

### 1. 如何切换 Provider（比如换成 Qwen / DeepSeek / Ollama）？

**非常简单——直接问 AI 帮你完成即可。**

项目从架构设计上使用了**工厂模式（Factory Pattern）**，Provider 的扩展和切换非常方便。你只需要理解内部原理就会发现：不同 API 本质上都是类似的 HTTP 请求，甚至大多数都遵循 OpenAI 的请求格式，切换起来特别容易。

**具体操作方式有两种：**

1. **使用 Setup Skill（推荐）**：运行一键 Setup Skill，AI 会主动询问你想用哪个 Provider，引导你填入 API Key，然后自动帮你完成代码适配和配置生成。
2. **直接让 AI 帮你改**：把你想切换的 Provider 告诉 AI（如 "帮我切换到 Qwen" 或 "帮我配置 DeepSeek"），AI 能根据工厂模式的架构自动完成代码编写。

> **原理说明**：项目的 `src/libs/` 下的 LLM、Embedding、Reranker 等模块都使用工厂模式，新增一个 Provider 只需要：① 新增一个 Provider 类；② 在工厂注册；③ 更新 `settings.yaml` 配置。AI 完全可以自动完成这些步骤。

### 2. 项目评估（Custom Evaluator）与 Cross-Encoder Reranker

这两个模块**已实现并有单元/集成测试**，但在不同 Provider 与本地模型环境下的稳定性仍可能因部署差异而需要自行验证：


| 模块                          | 状态        | 说明                                                                                                                    |
| --------------------------- | --------- | --------------------------------------------------------------------------------------------------------------------- |
| **自定义评估（Custom Evaluator）** | 已实现，含单元测试 | 支持 hit_rate、mrr 等指标；可与 Ragas 组合为 Composite Evaluator                                                                  |
| **Cross-Encoder Reranker**  | 已实现，含单元测试 | 需安装 `sentence-transformers` 并下载本地模型（如 `cross-encoder/ms-marco-MiniLM-L-6-v2`）；Setup Skill 中默认推荐「不启用」或「LLM 重排序」以降低环境差异 |


**扩展或排障时可直接让 AI 协助**。把需求描述清楚，AI 可以帮你调整评估指标、准备数据、下载模型并完成集成测试。

### 3. 项目报错 / Bug 怎么办？

**这不是一个经过广泛测试的生产级项目，而是一个面试导向的实战项目。** 遇到报错是正常的。

- **对面试的影响**：项目的 Bug 对面试几乎没有影响——面试官不会去实际运行你的项目，他们关注的是你对架构、原理和设计决策的理解。
- **如何修复**：最简单的方式是**把错误信息直接丢给 AI**，绝大多数问题 AI 都能帮你修复。
- **参考资源**：笔记中推荐的 Tina Huang 的视频里也介绍了这种用 AI 快速修复错误的方法。

### 4. 想摄取 PDF 以外的文档格式（Word / Markdown / HTML 等）怎么办？

**Loader 层已支持多种格式**，通过 `loader_factory` 按扩展名自动选择：


| 扩展名          | Loader                             |
| ------------ | ---------------------------------- |
| `.pdf`       | PdfLoader（含图片提取与 Image Captioning） |
| `.txt`、`.md` | TxtLoader                          |
| `.docx`      | MarkItDownLoader                   |


如需 **HTML、PPT** 等更多格式，Loader 层采用可插拔的 `BaseLoader` 抽象，让 AI 参考现有实现新增对应 Loader 即可。例如：「帮我新增一个 HTML 文档的 Loader，参考现有的 TxtLoader 实现」。

### 5. 如何集成到 AI 工具中（Copilot / Cursor / Claude Code 等）？

本项目是一个 **MCP Server**（`python main.py` / `mcp-server`），可集成到任何支持 MCP 的 AI 工具与 Agent 中。

**本 monorepo 已预置的集成方式：**

- **agents-master**：`agents-master/config.json` 已配置 `rag-server` MCP（`cwd` 指向 `../rag-server`），启动主应用后即可在对话中调用 `query_knowledge_hub` 等工具
- **Cursor**：在 MCP 设置中添加 stdio 服务，命令指向 `rag-server` 目录下的 `python main.py`（或虚拟环境中的 `mcp-server`）
- **GitHub Copilot（VS Code）**：让 AI 帮你生成 MCP 配置文件即可
- **Claude Desktop / 其他框架**：配置方式因客户端而异，原理相同——stdio 启动本 MCP Server

当然，也推荐你去理解 MCP 协议的原理——了解 Server 和 Client 之间是如何通信的、Tool 是怎么注册和调用的。这些在面试中也是加分项。

---

