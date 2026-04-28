# 小龙虾项目上下文管家

真实飞书数据 + LLM 的项目上下文、会议闭环和风险洞察工具。

当前主路径已经从 `resources/mock` 切到真实飞书多维表格。缺少真实业务对象时，使用 `seed-real-project` 向真实飞书 Base 写入最小项目数据，不再从 mock 文件读取。

## 当前主线

```text
真实飞书多维表格
  -> LLM 结构化抽取/生成
  -> 行动项、决策、风险、会前卡片、对账 diff、周报洞察、文档预览
  -> run_logs 留痕
```

## 初始化真实 Base

强制创建新的飞书多维表格和 4 张业务表：

```powershell
python tools\初始化飞书多维表格.py --force-new
```

写入真实种子项目数据：

```powershell
python -m src.cli seed-real-project --project-id pay_project
```

## 运行示例

查看真实上下文：

```powershell
python -m src.cli context-overview --project-id pay_project
```

用 LLM 抽取会议行动项、决策和风险，并写入真实 Base：

```powershell
python -m src.cli post-meeting-real --project-id pay_project --write-bitable
```

生成会前背景卡片：

```powershell
python -m src.cli pre-meeting-card --project-id pay_project --meeting-title 支付项目评审会
```

生成项目推进对账 diff：

```powershell
python -m src.cli reconcile-project-table --project-id pay_project
```

生成风险巡检和周报洞察：

```powershell
python -m src.cli risk-weekly-insight --project-id pay_project
```

生成会议议程和日历依赖缺口：

```powershell
python -m src.cli schedule-meeting --project-id pay_project --meeting-title 支付项目评审会
```

生成文档预览：

```powershell
python -m src.cli document-preview --project-id pay_project --doc-type weekly
```

## 旧 mock 入口

旧 mock 入口已经从 CLI 主路径移除，`resources/mock` 样例数据也已删除。
