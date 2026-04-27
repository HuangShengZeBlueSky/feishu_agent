# OpenClaw 飞书验证记录

验证时间：2026-04-25 23:59

## 结论

OpenClaw 已安装并接上飞书机器人“小龙虾项目上下文管家”。当前 Gateway 可达，Feishu main 账号正在运行，能力探针通过。真实群消息已经到达过 Gateway，测试群已加入白名单。

## 安装与配置

为规避 Windows 中文用户名路径下的插件依赖安装问题，本机使用 ASCII 路径安装 OpenClaw：

```powershell
npm install -g --prefix C:\openclaw-npm openclaw@latest
& 'C:\openclaw-npm\openclaw.cmd' --version
```

实测版本：

```text
OpenClaw 2026.4.23 (a979721)
```

OpenClaw 配置文件：

```text
C:\Users\黄胜泽\.openclaw\openclaw.json
```

关键配置：

- `channels.feishu.enabled`：已启用。
- `channels.feishu.accounts.main.appId`：已配置为当前小龙虾机器人 App。
- `channels.feishu.accounts.main.name`：小龙虾项目上下文管家。
- `channels.feishu.groupAllowFrom`：已加入测试群 `oc_17a66849f49461ef2b6f42f89e0f48f4`。
- `agents.defaults.workspace`：已改为 `C:\openclaw-workspace`。
- `channels.whatsapp.enabled`：已临时关闭，避免无关插件影响本次飞书验证。

## Gateway 验证

验证命令：

```powershell
& 'C:\openclaw-npm\openclaw.cmd' config validate
& 'C:\openclaw-npm\openclaw.cmd' gateway health
& 'C:\openclaw-npm\openclaw.cmd' gateway status
```

结果摘要：

```text
Config valid: ~\.openclaw\openclaw.json
Gateway Health
OK
Feishu: ok
Connectivity probe: ok
Capability: admin-capable
Listening: 127.0.0.1:18789
Dashboard: http://127.0.0.1:18789/
```

## Feishu Channel 验证

验证命令：

```powershell
& 'C:\openclaw-npm\openclaw.cmd' channels status --deep
& 'C:\openclaw-npm\openclaw.cmd' channels capabilities --channel feishu
```

结果摘要：

```text
Gateway reachable.
Feishu main (小龙虾项目上下文管家): enabled, configured, running

Support: chatTypes=direct,channel reactions edit reply threads media
Actions: send, broadcast, read, edit, thread-reply, pin, list-pins, unpin, member-info, channel-info, channel-list, react, reactions
Probe: ok
```

## 已观察到的启动特性

OpenClaw 启动后会做插件依赖、模型价格和 sidecar 初始化。刚启动的 1-2 分钟内，`gateway health` 可能因为内部初始化而超时；等待日志出现 `ready` 后复跑即可。

另外，真实飞书消息进入后会触发 agent 回复链路。当前默认模型已切到火山 Ark：`volcengine/ep-20260423222827-6lcn6`，Gateway 启动日志显示 `agent model: volcengine/ep-20260423222827-6lcn6`。本地 agent smoke test 已确认 winner provider 为 `volcengine`，回复为 `ok`。

本次最终可用日志：

```text
run_logs\openclaw_gateway_final_stdout.log
```

关键日志：

```text
[plugins] feishu_doc: Registered feishu_doc, feishu_app_scopes
[plugins] feishu_chat: Registered feishu_chat tool
[plugins] feishu_wiki: Registered feishu_wiki tool
[plugins] feishu_drive: Registered feishu_drive tool
[plugins] feishu_bitable: Registered bitable tools
[gateway] ready
```

## 尚未完成的真实交互

已观察到一条真实群消息进入 Gateway：

```text
feishu[main]: received message ... in oc_17a66849f49461ef2b6f42f89e0f48f4 (group)
group oc_17a66849f49461ef2b6f42f89e0f48f4 not in groupAllowFrom
```

该问题已处理：测试群已加入 `groupAllowFrom` 白名单。下一步需要你在同一个群里再次发送：

```text
@小龙虾项目上下文管家 请只回复：验收收到
```

通过标准：

1. 日志不再出现 `not in groupAllowFrom`。
2. 群里收到小龙虾回复。
3. 回复链路使用火山 Ark 默认模型。

模型资源清单保存在本地忽略文件：`resources/config/本地模型资源secret.json`。密钥保存在 `resources/config/本地模型secret.env`，不进入 git。
