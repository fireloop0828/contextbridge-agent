---
name: clean-project
description: "清理工程用于分发：删除 __pycache__、.venv、构建产物、数据缓存、日志、IDE 文件、覆盖率报告，并对 config/settings.yaml 做 API Key 脱敏，产出可分享的精简代码库。用户说「打包」「清理项目」「清理缓存」「package」「clean project」「clean up」「prepare for distribution」时使用。"
---

# 清理打包（Clean Project）

一条命令清理项目以便分发：移除缓存、敏感信息与构建产物。

---

## 流程

```
预览 → 确认 → 执行 → 验证
```

> **⚠️ 运行脚本前先激活 `.venv`。**
> - **Windows**：`.\.venv\Scripts\Activate.ps1`
> - **macOS/Linux**：`source .venv/bin/activate`

---

## 步骤 1：预览（Dry Run）

不删除任何文件，仅展示将清理的内容：

```powershell
python skills/clean-project/scripts/clean.py
```

与用户一起查看输出，脚本会列出：
- 📁 将删除的目录（含大小）
- 📄 将删除的文件（含大小）
- 🔐 将脱敏的配置项（API Key → 占位符）

## 步骤 2：与用户确认

执行前汇总将删除的内容并请用户确认。可选参数：
- `--keep-data` — 保留 `data/` 和 `logs/`（保留已入库文档时有用）
- `--no-sanitize` — 跳过 `config/settings.yaml` 的 API Key 替换

## 步骤 3：执行

```powershell
# 完整清理（含 data）
python skills/clean-project/scripts/clean.py --execute

# 保留数据和日志
python skills/clean-project/scripts/clean.py --execute --keep-data

# 跳过密钥脱敏
python skills/clean-project/scripts/clean.py --execute --no-sanitize
```

## 步骤 4：验证

清理后确认工作区干净：

```powershell
# 检查是否还有 __pycache__
python -c "import pathlib; found=list(pathlib.Path('.').rglob('__pycache__')); print(f'{len(found)} __pycache__ dirs remaining') if found else print('Clean')"

# 检查 .venv 是否已删
python -c "import pathlib; print('.venv still exists') if pathlib.Path('.venv').exists() else print('Clean')"

# 检查 settings.yaml 是否还有真实 API Key
python -c "
import re, pathlib
text = pathlib.Path('config/settings.yaml').read_text()
keys = re.findall(r'api_key:\s*\"([^\"]+)\"', text)
real = [k for k in keys if k not in ('YOUR_API_KEY_HERE', '')]
print(f'{len(real)} real API key(s) found') if real else print('API keys sanitized')
"
```

向用户报告验证结果。

---

## 将删除的内容

| 类别 | 模式 |
|------|------|
| Python 缓存 | `__pycache__/`、`*.pyc`、`*.pyo`、`.pytest_cache/`、`.mypy_cache/`、`.ruff_cache/` |
| 虚拟环境 | `.venv/`、`venv/`、`env/` |
| 构建产物 | `build/`、`dist/`、`*.egg-info/`、`.eggs/`、`wheels/` |
| IDE 文件 | `.idea/`、`.vscode/`、`*.swp`、`*.swo` |
| 覆盖率 | `htmlcov/`、`.coverage`、`coverage.xml`、`.tox/`、`.nox/` |
| 数据与日志 | `data/`、`logs/`、`cache/`（`--keep-data` 时跳过） |
| 密钥文件 | `.env`、`.env.local`、`secrets.yaml`、`test_credentials.yaml` |
| 陈旧产物 | `nonexistent_traces.jsonl/` |
| 配置备份 | `settings.yaml.bak`、`settings.yaml.qa_backup` |
| Skill 缓存 | `skills/auto-dev/.spec_hash` |

## 将脱敏的内容（不删除）

- `config/settings.yaml`：`api_key` → `"YOUR_API_KEY_HERE"`，`azure_endpoint` → 占位符
