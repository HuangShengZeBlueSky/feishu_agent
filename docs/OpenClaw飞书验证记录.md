# OpenClaw + 飞书能力验证记录

验证时间：2026-04-25  
工作目录：`C:\Users\黄胜泽\Desktop\feishu_agent`

## 1. 安装结论

已通过 npm 安装 OpenClaw：

```powershell
npm install -g openclaw@latest
& "$env:APPDATA\npm\openclaw.cmd" --version
```

实测版本：

```text
OpenClaw 2026.4.23 (a979721)
```

注意：当前 PowerShell 会话的 `PATH` 没有自动包含 npm 全局 bin 目录，所以直接输入 `openclaw` 会找不到命令。可先用完整路径：

```powershell
& "$env:APPDATA\npm\openclaw.cmd" --help
```

或者把下面目录加入用户 `PATH`：

```text
C:\Users\黄胜泽\AppData\Roaming\npm
```

## 2. OpenClaw 飞书插件状态

OpenClaw 官方文档说明，当前版本已经内置 Feishu bundled plugin，不需要单独安装；旧版本或自定义安装才需要 `openclaw plugins install @openclaw/feishu`。

本机已把飞书通道写入 OpenClaw 配置：

```powershell
& "$env:APPDATA\npm\openclaw.cmd" channels add --channel feishu --account main --name "Feishu Main" --use-env
```

这个命令使用现有环境变量 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`，没有把密钥打印到终端。

实测结果：

| 项目 | 结果 | 说明 |
|---|---:|---|
| OpenClaw CLI 安装 | 通过 | `OpenClaw 2026.4.23` 可执行 |
| Feishu channel 配置 | 通过 | `channels list --json --no-usage` 能看到 `feishu/main` |
| Gateway 服务 | 未通过 | `gateway status` 显示 Scheduled Task missing，runtime stopped |
| Feishu bundled plugin 加载 | 未通过 | 原生 Windows 下反复出现 runtime deps staging 错误 |
| 直接飞书 OpenAPI 凭证 | 通过 | tenant token 和 bot info 都能读取 |

关键错误：

```text
[channels] failed to load bundled channel feishu:
EIO, Access is denied.
...\openclaw\dist\extensions\feishu\.openclaw-runtime-deps-copy-...\node_modules
```

判断：这不是飞书 App ID / Secret 错误，而是 OpenClaw 原生 Windows runtime dependencies staging 问题。官方 Windows 文档也建议通过 WSL2 跑 OpenClaw Gateway。当前本机 `wsl -l -v` 显示 WSL 尚未安装完成。

## 3. 飞书 OpenAPI 实测

新增脚本：

```text
tools/feishu_capability_probe.py
```

默认只读运行：

```powershell
python tools\feishu_capability_probe.py --json
```

写入测试需要显式打开：

```powershell
$env:FEISHU_ENABLE_WRITES="1"
python tools\feishu_capability_probe.py --json
```

### 3.1 已通过

| 能力 | 结果 | 证据 |
|---|---:|---|
| `tenant_access_token`，租户访问令牌 | 通过 | `code=0`, token present |
| `bot.info`，机器人信息 | 通过 | `code=0` |
| 多维表格 app 创建 | 通过 | `bitable.app.create code=0` |
| 多维表格 table 创建 | 通过 | `bitable.table.create code=0` |
| 多维表格 record 创建 | 通过 | `bitable.record.create code=0` |
| 多维表格状态更新 | 通过 | `bitable.record.update_status code=0` |

多维表格写入链路结论：当前飞书 App 至少具备创建多维表格、创建表、创建记录、更新记录字段的能力。

### 3.2 未完成或被权限挡住

| 能力 | 当前结果 | 缺什么 |
|---|---:|---|
| 群消息读取 | 跳过 | 缺 `FEISHU_TEST_CHAT_ID` 或 `FEISHU_CHAT_ID` |
| 群消息/卡片推送 | 跳过 | 缺 `chat_id`；脚本已支持 text 和 interactive card |
| 文档读取 | 跳过 | 缺 `FEISHU_TEST_DOC_ID` 或 `FEISHU_DOC_ID` |
| 任务读取 | 跳过 | 缺 `FEISHU_TEST_TASK_GUID` 或 `FEISHU_TASK_GUID` |
| 日历读取 | 未通过 | 当前 App 缺 `calendar:calendar:readonly` 或同类日历权限 |
| 会议妙记读取 | 跳过 | 缺 `FEISHU_TEST_MINUTE_TOKEN` 或 `FEISHU_MEETING_MINUTE_TOKEN`，且通常需要用户授权 token |

日历接口实测返回：

```text
Access denied. One of the following scopes is required:
[calendar:calendar:readonly, calendar:calendar, calendar:calendar.calendar:readonly, calendar:calendar:read]
```

## 4. 六项能力逐项判断

### 1. OpenClaw 飞书插件读取数据源

当前结论：未能证明稳定。

原因分两层：

1. OpenClaw Gateway / bundled plugin 在原生 Windows 下没有稳定启动。
2. 直接 OpenAPI 层只证明了 bot info 和多维表格写入；消息、文档、任务、会议妙记还缺真实对象 ID 或用户授权。

需要补齐的对象：

```powershell
$env:FEISHU_TEST_CHAT_ID="oc_xxx"
$env:FEISHU_TEST_DOC_ID="docx_xxx"
$env:FEISHU_TEST_TASK_GUID="..."
$env:FEISHU_TEST_MINUTE_TOKEN="obcn..."
```

### 2. 飞书 CLI 的会议妙记能力

当前结论：未通过。

实测：

```powershell
& "$env:APPDATA\npm\openclaw.cmd" skills install feishu-minutes
```

返回：

```text
ClawHub /api/v1/skills/feishu-minutes failed (404): Skill not found
Assertion failed: !(handle->flags & UV_HANDLE_CLOSING)
```

同时，直接 OpenAPI 脚本也因为缺 `minute_token` 跳过。会议妙记通常至少要有妙记 URL 里的 `obcn...` token；如果要按用户权限读取逐字稿，还需要用户身份授权，而不只是机器人 tenant token。

### 3. 多维表格写入

当前结论：通过。

已实测：

1. 创建多维表格 app。
2. 创建 table。
3. 创建字段。
4. 创建 record。
5. 更新 record 的 `状态` 字段。

这部分可以作为 MVP 的结构化状态库。

### 4. 群消息或卡片推送

当前结论：脚本能力已准备，真实推送未跑。

原因：当前环境没有 `chat_id`。脚本支持三类卡片：

1. 会前卡片：议程、材料、风险点。
2. 会后卡片：结论、行动项、负责人。
3. 风险卡片：需要人工确认的高风险操作。

复跑命令：

```powershell
$env:FEISHU_TEST_CHAT_ID="oc_xxx"
$env:FEISHU_ENABLE_WRITES="1"
$env:FEISHU_ENABLE_CARD_PUSH="1"
python tools\feishu_capability_probe.py --json
```

### 5. 事件触发

MVP 建议先不要依赖 WebSocket。

当前可落地路径：

1. 手动命令：用 `tools/feishu_capability_probe.py` 或后续业务脚本手动跑。
2. 定时任务：用 Windows Task Scheduler 定时拉取消息、日历、文档、妙记，再写入多维表格。
3. WebSocket 事件：等 OpenClaw Gateway 在 WSL2 或 Linux 环境稳定后，再接 `im.message.receive_v1` 和 `drive.notice.comment_add_v1`。

官方 OpenClaw Feishu 文档建议事件订阅使用长连接 WebSocket，并至少配置 `im.message.receive_v1`；文档评论工作流还需要 `drive.notice.comment_add_v1`。

### 6. 权限边界

建议把权限分成三层写清楚：

| 身份 | 能看什么 | 能写什么 | 是否需要确认 |
|---|---|---|---|
| 机器人身份 tenant token | bot info、机器人可见群消息、被授权的文档/多维表格/日历对象 | 发送消息、写多维表格、创建任务或文档 | 中高风险写操作需要确认 |
| 用户身份 user access token | 用户本人可访问的妙记、日历、文档、任务 | 代表用户改文档、任务、日历 | 必须确认，且要记录操作者 |
| OpenClaw Agent 本地身份 | 本机文件、命令、网络工具 | 可能执行本地命令或改文件 | 高风险操作必须卡片确认 |

写操作确认规则：

1. 低风险：只读查询、汇总、草稿生成，可以直接执行。
2. 中风险：发群消息、写多维表格状态、创建任务，需要在日志里记录。
3. 高风险：删除/覆盖文档、批量通知群、代表用户改日历、执行本地命令，必须先发确认卡片。

## 5. 下一步最短路径

1. 在飞书开放平台补齐日历权限，并发布/审批应用版本。
2. 提供一个测试群 `chat_id`，复跑群消息和三类卡片。
3. 提供一个测试文档 ID、任务 GUID、妙记 token，复跑读取能力。
4. 安装 WSL2/Ubuntu 后，在 WSL 内安装 OpenClaw 并启动 Gateway，验证 bundled Feishu plugin 是否稳定。
5. 把 `tools/feishu_capability_probe.py` 拆成业务脚本：会前读取、会后总结、风险推送、多维表格状态更新。
