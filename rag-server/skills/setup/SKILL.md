---
name: setup
description: "首次环境配置向导：引导选择 Provider（OpenAI/Azure/DeepSeek/Ollama/Qwen/Gemini 等）、填写 API Key、安装依赖、生成 config/settings.yaml、启动 Dashboard；未内置的 Provider 可按插件架构自动脚手架；启动失败自动诊断重试（≤3 轮）。用户说「初始化」「环境配置」「项目配置」「setup」「configure」「init project」「first run」「get started」「quick start」时使用。"
---

# 环境配置（Setup）

交互式向导：选择 Provider → 安装依赖 → 生成配置 → 启动 Dashboard → 失败自动修复。

---

## 流程

```
预检 → 询问用户 → 生成配置 → 安装依赖 → 校验 → 启动 → 使用指引
```

> 自动修复循环：任一步失败则诊断 → 修复 → 重试（≤3 轮）。

---

## 步骤 1：预检

在询问用户之前，先确认前置条件：

### 1.1 检查 Python 版本

```powershell
python --version          # 要求 >=3.10
```

若 Python < 3.10，停止并提示用户安装受支持版本。

### 1.2 检查并创建虚拟环境

检查 `.venv` 是否已存在。已存在则跳过创建，仅激活；不存在则创建后激活。

**注意**：使用 `--without-pip` 避免 Windows 上 `ensurepip` 卡住，激活后再手动 `ensurepip`。

```powershell
# 步骤 1：检查 .venv 是否存在
Test-Path ".venv"

# 步骤 2：不存在则创建（不捆绑 pip，更快）
python -m venv .venv --without-pip

# 步骤 3：激活虚拟环境
# Windows:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

# 步骤 4：在 venv 内引导 pip（仅 --without-pip 时需要）
python -m ensurepip --upgrade

# 步骤 5：验证
pip --version             # 应显示 .venv 内的 pip 路径
```

若 `.venv` 已存在，只执行步骤 3（激活）和步骤 5（验证）。

---

## 步骤 2：询问用户配置

使用 `ask_questions` 收集 Provider 选择，每批最多 4 题。

### 批次 1：核心 Provider

一并询问：

1. **LLM Provider** — 使用哪家 LLM？
   - 选项：`OpenAI`、`Azure OpenAI`、`DeepSeek`、`Ollama (local)`、`Qwen (Alibaba Cloud)`、`Gemini (Google)`
   - 推荐：`OpenAI`
   - 已内置：OpenAI、Azure、DeepSeek、Ollama；其余需自动脚手架（见步骤 2.5）。

2. **Embedding Provider** — 使用哪家 Embedding？
   - 选项：同上（无 DeepSeek）
   - 推荐：`OpenAI`（尽量与 LLM 同厂商）
   - 已内置：OpenAI、Azure、Ollama；其余需自动脚手架（见步骤 2.5）。

3. **Vision** — 是否启用图片理解/描述？
   - 选项：`Yes`、`No`
   - 推荐：`Yes`

4. **Rerank** — 是否启用重排序？
   - 选项：`No (fastest)`、`Cross-Encoder (local model)`、`LLM-based`
   - 推荐：`No (fastest)`
   - ⚠️ Cross-Encoder 仅完成本地实现，未充分测试，可能有兼容问题；建议选「不启用」或「LLM 重排序」。

### 批次 2：凭据（依批次 1 答案）

按所选 Provider 询问凭据，各 Provider 必填项见 [references/provider_profiles.md](references/provider_profiles.md)。

**OpenAI：**
- OpenAI API Key
- LLM 模型（默认 `gpt-4o`）
- Embedding 模型（默认 `text-embedding-ada-002`）

**Azure OpenAI：**
- Azure API Key
- Azure Endpoint URL
- LLM deployment name（默认 `gpt-4o`）
- Embedding deployment name（默认 `text-embedding-ada-002`）

**DeepSeek：**
- DeepSeek API Key
- 另选 Embedding Provider（DeepSeek 无 Embedding，需 OpenAI/Ollama）

**Ollama：**
- Ollama base URL（默认 `http://localhost:11434`）
- LLM 模型名（默认 `llama3`）
- Embedding 模型名（默认 `nomic-embed-text`）
- 验证 Ollama 已运行：`curl http://localhost:11434/api/tags`

**Qwen：**
- Qwen API Key（DashScope）
- LLM 模型（默认 `qwen-turbo`）
- Embedding 模型（默认 `text-embedding-v3`，若 Embedding 也选 Qwen）
- Base URL：`https://dashscope.aliyuncs.com/compatible-mode/v1`

**Gemini：**
- Gemini API Key（Google AI Studio）
- LLM 模型（默认 `gemini-2.0-flash`）
- Embedding 模型（默认 `text-embedding-004`，若 Embedding 也选 Gemini）
- Base URL：`https://generativelanguage.googleapis.com/v1beta/openai/`

### 批次 3：Vision 凭据（若启用 Vision）

Vision LLM 有**独立配置段** `vision_llm`（`provider`、`api_key`、`azure_endpoint` 等），不要默认与主 LLM 共用凭据。

最多问 2 题：

1. **Vision Provider** — 图片理解用哪家？选项同 LLM 列表，默认与用户 LLM 选择一致；已内置 Vision：OpenAI、Azure。
2. **Vision 凭据**：
   - 若 Vision Provider == LLM Provider：问「Vision 是否复用同一 API Key/Endpoint？」（默认 Yes）
   - 若不同：单独询问 Vision 的 key / endpoint / model

各 Provider 推荐 Vision 模型（首选列在前）：

| Provider | 推荐 | 其他选项 | 说明 |
|----------|------|----------|------|
| OpenAI | `gpt-4o` | `gpt-4o-mini`, `gpt-4-turbo` | gpt-4o-mini 更便宜，适合简单图片描述 |
| Azure | `gpt-4o` | `gpt-4o-mini`, `gpt-4-turbo` | 需要 deployment_name + azure_endpoint |
| Ollama | `llava` | `llava:13b`, `llava:34b`, `llava-llama3`, `bakllava`, `moondream` | moondream 最轻量，llava:34b 质量最高 |
| Qwen | `qwen-vl-max` | `qwen-vl-plus`, `qwen2.5-vl-72b-instruct`, `qwen2.5-vl-7b-instruct` | qwen-vl-plus 性价比高 |
| Gemini | `gemini-2.0-flash` | `gemini-1.5-pro`, `gemini-2.0-flash-lite`, `gemini-1.5-flash` | gemini-1.5-pro 质量最高但较慢 |
| DeepSeek | ❌ 无 Vision 模型 | — | 需另选 Provider 作为 Vision LLM |

---

## 步骤 2.5：脚手架未内置 Provider（如需要）

用户选了未内置的 Provider（如 Qwen、Gemini）时，在生成配置前先自动脚手架实现。

完整流程见 [references/new_provider_guide.md](references/new_provider_guide.md)。

摘要：
1. 在 `src/libs/llm/{name}_llm.py` 创建 LLM 类（继承 `BaseLLM`）
2. 在 `src/libs/embedding/{name}_embedding.py` 创建 Embedding 类（继承 `BaseEmbedding`）— 如需要
3. 在 `src/libs/llm/{name}_vision_llm.py` 创建 Vision LLM 类（继承 `BaseVisionLLM`）— 如需要
4. 在 `src/libs/llm/__init__.py` 和 `src/libs/embedding/__init__.py` 注册
5. 若 Provider 用自定义 endpoint，在 `LLMSettings` / `EmbeddingSettings` 增加 `base_url`
6. 安装 SDK：`pip install <sdk>`
7. 在 `references/provider_profiles.md` 补充 Provider 配置说明

许多 Provider（Qwen、Gemini、Groq、Mistral 等）兼容 OpenAI API — 可继承 `OpenAILLM` / `OpenAIEmbedding`，覆盖 `DEFAULT_BASE_URL` 与鉴权逻辑即可。

---

## 步骤 3：生成配置

从 [references/settings_template.yaml](references/settings_template.yaml) 读取模板，按用户答案填写。

关键规则：
- `dimensions` 查 [references/provider_profiles.md](references/provider_profiles.md) 中的模型维度表
- Ollama：设 `base_url`，`api_key`/`azure_endpoint`/`deployment_name` 留空
- OpenAI：留空 `azure_endpoint`/`deployment_name`/`api_version`
- 未启用 Vision：`vision_llm.enabled: false`
- Rerank：按选择设 `enabled`、`provider`、`model`

写入 `config/settings.yaml`。

并确保目录存在：

```powershell
python -c "from pathlib import Path; [Path(d).mkdir(parents=True, exist_ok=True) for d in ['data/db/chroma', 'data/images/default', 'logs', 'config/prompts']]"
```

---

## 步骤 4：安装依赖

```powershell
pip install -e ".[dev]"
```

按需额外安装：
- **Cross-Encoder rerank**：`pip install sentence-transformers`
- **Streamlit dashboard**：`pip install streamlit`
- **OpenAI**：`pip install openai`

验证关键导入：

```powershell
python -c "import chromadb; import mcp; import yaml; print('Core deps OK')"
python -c "import streamlit; print('Streamlit OK')"
python -c "import openai; print('OpenAI SDK OK')"
```

---

## 步骤 5：校验配置

确认配置可正常加载：

```powershell
python -c "from src.core.settings import load_settings; s = load_settings(); print(f'Config OK: LLM={s.llm.provider}/{s.llm.model}, Embed={s.embedding.provider}/{s.embedding.model}')"
```

失败则进入**自动修复循环**：

### 自动修复（≤3 轮）

```
第 0..2 轮：
  读取报错信息
  诊断根因（缺字段、类型错误、Provider 名错误等）
  修复 config/settings.yaml 或安装缺失依赖
  重新校验
  通过 → 进入步骤 6
  仍失败 → 下一轮
```

常见修复：
- `SettingsError: Missing required field` → 在 settings.yaml 补字段
- `ModuleNotFoundError` → `pip install <package>`
- `Connection refused`（Ollama）→ 提示用户启动 Ollama
- `dimensions` 错误 → 查 provider_profiles.md 更正

3 轮仍失败，向用户报告诊断结果并请求协助。

---

## 步骤 6：启动 Dashboard

```powershell
python scripts/start_dashboard.py --port 8501
```

以**后台进程**运行，等待数秒后验证可访问：

```powershell
python -c "
import urllib.request
try:
    r = urllib.request.urlopen('http://localhost:8501/_stcore/health')
    print('Dashboard is running!' if r.status == 200 else f'Status: {r.status}')
except Exception as e:
    print(f'Dashboard not yet ready: {e}')
"
```

启动失败则进入自动修复：读后台终端报错；常见原因：缺 `streamlit`、端口占用、import 错误。

---

## 步骤 7：使用指引

启动成功后，向用户展示（用户用中文则用中文）：

```
🎉 配置完成！

Dashboard: http://localhost:8501

快速开始：
  1. 文档入库:  python scripts/ingest.py <pdf或目录路径>
  2. 检索查询:  python scripts/query.py "你的问题"
  3. 控制台:    python scripts/start_dashboard.py
  4. MCP 服务:  python main.py

配置文件: config/settings.yaml
日志:     logs/traces.jsonl

Provider: {provider} / Model: {model}
```
