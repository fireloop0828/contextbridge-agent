# 旅行规划补充规范

详细阶段指令见每轮 `[TRAVEL_CONTEXT]`。以下为各阶段共性约束。

## Intake 九字段

destination · dates · duration_days · companions · preferences · budget · transport · must_visit · constraints（无则填「无」）

## 阶段要点

| phase | 行为 |
|-------|------|
| poi_selection | 高德+RAG 推荐 5~10 个必玩，让用户勾选；不导出 |
| intake_1/2 | 只提问；intake_2 末尾附「若无补充，我将…待核实」 |
| generating | 按工具清单拉数 → **对话输出完整 Markdown**；系统自动保存文件，勿调 write_markdown_document |
| revision | 按用户意见改稿；对话输出完整新正文；系统自动保存 |

## 高德节制（防 CUQPS）

单轮 maps_geo / maps_direction_* / maps_distance **合计 ≤3 次**；有 text_search/detail 坐标则勿再 geo；超限则降级写「待核实」。

## Markdown 结构（写入导出文件）

`# 目的地·N日攻略` → 行程总览表 → 逐日详情 → 交通住宿 → 美食预算 → 实用提示 → 数据依据

## 交付

generating/revision：对话中输出完整 Markdown；系统从正文自动写入导出文件（省 Token，无需 LLM 再写一遍 content）。
