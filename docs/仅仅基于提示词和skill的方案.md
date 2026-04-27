可以实现，但要把它设计成**“多 Skill 编排系统”**，而不是一个超长提示词。

你的方案可以成立：

> **小龙虾 = OpenClaw Agent + 多个 Skill + 飞书 CLI / OpenClaw 飞书插件 + 飞书多维表格 + 飞书文档。**

飞书 CLI 官方说明它面向人和 AI Agent，覆盖消息、文档、多维表格、日历、任务、会议等业务域，并提供 200+ 命令和 22 个 AI Agent Skills；OpenClaw 飞书插件也支持读写消息、文档、多维表格、日历、任务等能力。也就是说，从能力面上看，方向 A、B、D 都有实现基础。([GitHub](https://github.com/larksuite/cli))

但是要注意一句话：

> **提示词负责“决策和编排”，飞书 CLI 负责“执行飞书操作”，飞书多维表格负责“保存长期状态”。**

不能只靠提示词记忆项目，否则过一两周一定乱。

------

# 1. 总体架构

建议这样设计：

```text
飞书群 / 飞书私聊 / 妙搭页面 / 定时任务
        ↓
OpenClaw Feishu Channel
        ↓
小龙虾 Agent
        ↓
多个 Skill
        ↓
飞书 CLI / OpenClaw 飞书插件
        ↓
飞书文档、飞书任务、飞书日历、飞书妙记、多维表格、群消息
        ↓
写回：周报、任务、推进总表、同步日志、风险卡片
```

其中：

```text
飞书多维表格 = 系统状态库
飞书文档 = 项目叙事、周报、会议制度、项目进度说明
飞书任务 = 执行动作
飞书群消息 = 通知与交互入口
OpenClaw Skill = AI 的操作手册
飞书 CLI = 实际调用飞书能力
```

------

# 2. 能不能只用“提示词 + 飞书 CLI Skill”实现？

## 可以实现 MVP

可以实现：

```text
方向 A：手动或定时生成团队周报
方向 B：会前背景卡片、会后行动项转任务
方向 D：重点事项推进总表维护
```

## 但周期性和长期稳定需要外部状态

三个方向里，最关键的问题不是“AI 会不会总结”，而是：

```text
它怎么知道本周处理哪些项目？
它怎么知道哪些文档属于哪个项目？
它怎么知道上次同步到哪里？
它怎么避免重复创建任务？
它怎么知道某个 Todo 已经完成？
它怎么解释自己为什么更新了某条事项？
```

所以必须有这些表：

```text
1. 项目表
2. 项目上下文源表
3. 重点事项推进总表
4. 会议表
5. 周报表
6. 同步日志表
7. AI 待确认表
```

飞书多维表格 API 支持新增和批量更新记录，这适合承载这些结构化状态。([飞书开放平台](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/create?utm_source=chatgpt.com))

------

# 3. 多 Skill 架构

不要只写一个 `xiaolongxia/SKILL.md`。

建议拆成 10 个 Skill。

```text
xiaolongxia-core-context
xiaolongxia-source-bind
xiaolongxia-weekly-report
xiaolongxia-meeting-prep
xiaolongxia-meeting-followup
xiaolongxia-todo-center
xiaolongxia-risk-insight
xiaolongxia-notification
xiaolongxia-audit-log
xiaolongxia-permission-check
```

每个 Skill 只做一类事情。

------

## Skill 1：core-context，项目上下文管理

### 作用

负责让 AI 每次先知道：

```text
当前处理哪个项目？
这个项目有哪些上下文来源？
哪些来源是 active？
哪些来源最近同步过？
哪些规则文档需要遵守？
```

### 读取对象

```text
项目表
项目上下文源表
项目进度文档
飞阅会 / 会议制度文档
同步日志表
```

### 核心提示词规则

```text
每次处理项目，必须先读取项目表。
找到 project_id 后，必须读取项目上下文源表。
只能处理 status = active 的上下文源。
不得凭记忆判断项目上下文。
不得把没有证据链接的内容写入正式结果。
每次执行必须写同步日志。
```

这是所有方向的基础 Skill。

------

## Skill 2：source-bind，上下文源绑定

### 作用

负责把飞书文档、会议纪要、任务清单、日历、群聊等绑定到项目。

### 用户指令示例

```text
@小龙虾 把这篇文档绑定到项目：小龙虾，作为主需求文档。
```

### AI 执行

```text
1. 根据“小龙虾”找到 project_id
2. 解析当前飞书文档链接
3. 获取 resource_token
4. 检查读取权限
5. 写入项目上下文源表
6. 返回绑定结果
```

------

## Skill 3：weekly-report，周期性周报

对应方向 A。

### 作用

自动生成：

```text
每周工作总结
本周关键进展
任务流转情况
会议决议
下周风险
需要管理层介入的问题
```

### 输入来源

```text
项目上下文源表
本周变更过的文档
本周完成 / 延期 / 新增的任务
本周会议纪要
重点事项推进总表
上周周报
同步日志
```

### 输出

```text
周报文档
部门群卡片
周报表记录
```

------

## Skill 4：meeting-prep，会前背景卡片

对应方向 B 的会前部分。

### 作用

在会议前，根据日历事件自动准备背景资料。

飞书开放平台的日历能力支持管理日历与日程、查询忙闲等能力；飞书 CLI 也覆盖日历相关能力。([飞书开放平台](https://open.feishu.cn/document/event-subscription-guide/event-subscriptions/event-callback-optimization-guide?lang=zh-CN&utm_source=chatgpt.com))

### 输入来源

```text
日历事件标题
参会人
会议描述
关联项目
历史会议纪要
相关文档
未完成 Todo
上次会议决议
```

### 输出

```text
会前背景卡片
发送到会议群 / 参会人私聊
```

------

## Skill 5：meeting-followup，会后行动项闭环

对应方向 B 的会后部分。

### 作用

会后自动读取会议纪要或飞书妙记，抽取行动项，创建飞书任务。

飞书开放平台提供创建任务 API，可以设置任务基本信息、负责人、时间提醒、自定义字段，并可以把任务加入清单；飞书妙记也有获取妙记信息的接口。([飞书开放平台](https://open.feishu.cn/document/task-v2/task/create?lang=zh-CN&utm_source=chatgpt.com))

### 输入来源

```text
会议纪要 / 妙记
会议参会人
项目上下文源表
会议制度文档
重点事项推进总表
```

### 输出

```text
飞书任务
重点事项推进总表更新
会后行动项卡片
同步日志
```

------

## Skill 6：todo-center，团队待办中枢

对应方向 D。

### 作用

维护“重点事项推进总表”。

### 输入来源

```text
飞书文档正文
文档评论
会议纪要
飞书任务
任务清单
上一次推进总表
```

### 输出

```text
新增 Todo
更新 Todo 状态
补齐负责人
补齐截止时间
识别阻塞原因
识别延期风险
合并重复事项
写入待确认表
```

飞书任务本身支持任务、清单、评论等接口能力，适合用于同步负责人、截止时间、完成状态等执行信息。([飞书开放平台](https://open.feishu.cn/document/task-v2/overview?lang=zh-CN&utm_source=chatgpt.com))

------

## Skill 7：risk-insight，风险洞察

### 作用

从周报、会议纪要、延期任务、阻塞描述里识别风险。

### 输出风险类型

```text
进度风险
负责人不明确风险
跨团队依赖风险
权限 / 系统接入风险
需求变更风险
长期未更新风险
会议决议未落地风险
```

------

## Skill 8：notification，消息通知

### 作用

统一负责把结果发到飞书。

输出形式：

```text
部门群周报卡片
会前背景卡片
会后行动项卡片
风险预警卡片
待确认提醒
同步失败提醒
```

------

## Skill 9：audit-log，同步日志

### 作用

每次 AI 执行后必须写日志。

日志内容：

```text
执行时间
触发人
触发方式
处理项目
读取了哪些来源
新增了几条事项
更新了几条事项
失败了哪些来源
AI 判断依据
需要人工确认的问题
```

这是你黑盒验收小龙虾的关键。

------

## Skill 10：permission-check，权限检查

### 作用

检查机器人是否能读文档、读任务、写表、发消息。

飞书开放平台事件订阅可以让应用及时响应飞书中的变更事件；但权限不足、资源不存在、限流等失败也需要在同步日志和上下文源表里显式记录。([飞书开放平台](https://open.feishu.cn/document/server-docs/event-subscription-guide/overview?lang=zh-CN&utm_source=chatgpt.com))

------

# 4. 上下文管理怎么做

你提到“通过提示词，用飞书表格管理项目，用文档管理进度和飞阅会的开会制度”，这个思路是对的。

建议分三层。

------

## 第一层：飞书多维表格管结构化状态

这是机器看的。

### 项目表

```text
project_id
project_name
aliases
owner
members
stage
main_table_url
weekly_report_doc_url
progress_doc_url
meeting_policy_doc_url
sync_policy
status
created_at
updated_at
```

### 项目上下文源表

```text
source_id
project_id
source_type
relation_type
title
feishu_url
resource_token
include_scope
trust_level
sync_policy
last_sync_at
last_cursor_or_version
permission_status
status
```

### 重点事项推进总表

```text
todo_id
project_id
title
owner
priority
deadline
status
blocker
source_ids
evidence_urls
confidence
last_seen_at
last_updated_by_ai_at
need_human_confirm
```

### 会议表

```text
meeting_id
project_id
calendar_event_id
meeting_title
meeting_time
participants
minutes_url
status
pre_card_sent
followup_done
```

### 周报表

```text
report_id
project_id
week_start
week_end
report_doc_url
summary
risks
sent_to_chat
status
```

### 同步日志表

```text
run_id
skill_name
project_id
trigger_type
started_at
finished_at
read_sources
created_count
updated_count
skipped_count
failed_sources
ai_summary
status
```

------

## 第二层：飞书文档管叙事和制度

这是人看的，也给 AI 提供规则。

每个项目建议有一个“项目进度文档”：

```text
项目目标
当前阶段
本周进展
关键决策
重要风险
里程碑
关联文档
关联任务清单
最近会议
```

还要有一个“飞阅会 / 会议制度文档”：

```text
什么会议需要会前卡片
会前卡片提前多久发送
会前卡片包含哪些内容
会后行动项如何判定
什么行动项必须创建飞书任务
任务默认截止时间怎么处理
低置信度行动项怎么进入待确认
```

AI 每次处理会议前，必须读取会议制度文档，不能自由发挥。

------

## 第三层：Skill 管执行规则

Skill 里写死：

```text
先读项目表
再读上下文源表
再读制度文档
再读具体来源
最后写表和日志
```

这样小龙虾就不会变成“会聊天但不稳定”的机器人。

------

# 5. 方向 A：周期性智能总结与洞察，实现路径

## 能否实现

可以实现。

但“周期性”最好不要只靠聊天触发。建议有两种模式：

```text
MVP：手动触发
正式版：定时任务触发
```

定时触发可以放在：

```text
OpenClaw 外部 cron
飞书低代码 / 妙搭流程
自建轻量服务
CI 定时任务
```

飞书低代码平台支持 HTTP 连接器，可以在流程中向外部系统发送 HTTP 请求；也支持云函数，适合做轻量调度或中间逻辑。([feishu.cn](https://www.feishu.cn/content/759627620534?utm_source=chatgpt.com))

------

## 实现步骤

### A1. 建周报配置表

```text
team_id
team_name
project_ids
report_day
report_time
target_chat_id
report_template_doc_url
enabled
```

### A2. 周报 Skill 执行流程

```text
1. 读取周报配置表
2. 找到本周需要总结的项目
3. 对每个项目读取项目表
4. 读取项目上下文源表
5. 拉取本周文档变化、任务变化、会议纪要
6. 读取上周周报
7. 生成本周总结和下周风险
8. 写入周报文档
9. 写入周报表
10. 发送部门群卡片
11. 写同步日志
```

### A3. 周报输出模板

```text
# 团队每周工作总结

## 一、本周关键进展
- ...

## 二、重点事项推进情况
- 新增事项：
- 完成事项：
- 延期事项：
- 阻塞事项：

## 三、重要会议决议
- ...

## 四、下周风险洞察
- 风险：
- 影响：
- 建议动作：

## 五、需要管理者介入的事项
- ...
```

### A4. 第一版验收

```text
手动输入：@小龙虾 生成本周团队周报
预期：
1. 生成一篇飞书周报文档
2. 部门群收到摘要卡片
3. 周报表新增记录
4. 同步日志记录读取了哪些来源
```

------

# 6. 方向 B：会议与项目全链路伴侣，实现路径

方向 B 拆成两个闭环：

```text
B1：会前背景卡片
B2：会后行动项闭环
```

------

## B1. 会前背景卡片

### 实现步骤

```text
1. 定时扫描未来 24 小时日历事件
2. 根据会议标题、描述、参会人匹配 project_id
3. 读取项目上下文源表
4. 读取最近会议纪要、项目进度文档、未完成 Todo
5. 生成会前背景卡片
6. 发给会议群或参会人
7. 更新会议表 pre_card_sent = true
```

### 会前卡片内容

```text
会议主题
会议目标
上次会议结论
当前未完成事项
相关文档
本次需要拍板的问题
潜在风险
```

### 匹配项目规则

```text
优先级 1：日历描述里显式写 project_id
优先级 2：会议标题命中项目别名
优先级 3：参会人和文档来源高度重合
优先级 4：无法确定则进入待确认
```

### 飞书指令示例

```text
@小龙虾 为明天 10 点的“小龙虾项目周会”生成会前背景卡片。
```

------

## B2. 会后行动项闭环

### 实现步骤

```text
1. 找到会议对应的会议纪要或妙记
2. 读取会议内容
3. 按会议制度文档抽取行动项
4. 为高置信度行动项创建飞书任务
5. 写入重点事项推进总表
6. 将任务链接、知识库链接分发给负责人
7. 发送会后总结卡片
8. 写同步日志
```

### 行动项判定规则

```text
必须包含动作
最好包含负责人
最好包含截止时间
如果没有负责人，进入待确认
如果没有截止时间，根据会议制度处理
如果只是讨论内容，不创建任务
```

### 输出示例

```text
会后行动项已处理：

新增飞书任务：
1. 李四：4 月 30 日前完成文档读取接口
2. 王五：5 月 2 日前完成推进总表字段配置

进入待确认：
1. “补一下权限失败提示”——缺负责人
```

------

# 7. 方向 D：团队待办中枢与进展自动对账，实现路径

这是三个方向里最重要，也是最复杂的。

## 实现步骤

### D1. 建重点事项推进总表

字段：

```text
todo_id
project_id
title
owner
priority
deadline
status
blocker
source_ids
evidence_urls
related_task_ids
confidence
need_human_confirm
last_seen_at
last_status_check_at
```

### D2. Todo Center Skill 执行流程

```text
1. 读取项目表
2. 读取项目上下文源表
3. 读取 active 来源
4. 从文档、评论、会议纪要、任务中抽取候选 Todo
5. 读取已有推进总表
6. 做语义去重
7. 判断新增、更新、合并、完成、阻塞
8. 写回推进总表
9. 对低置信度内容写入待确认
10. 写同步日志
```

### D3. 对账规则

```text
飞书任务状态 > 会议纪要状态 > 文档描述 > AI 推断
```

也就是说：

如果飞书任务已经完成，推进总表应更新为完成。
如果会议纪要说“卡住”，但任务状态未完成，推进总表应记录阻塞原因。
如果文档里删除了某个 Todo，不要直接删推进总表，而是标记“需复核”。

### D4. 第一版不要做全自动群聊

群聊先只处理两类：

```text
1. @小龙虾 的消息
2. 明确包含飞书文档 / 任务 / 会议链接的消息
```

不要第一版就全量读群聊，否则噪声会非常高。

------

# 8. 三个方向之间怎么联动

这三个方向不是三个独立机器人，而是共享同一套上下文。

```text
方向 D 维护重点事项推进总表
        ↓
方向 B 会前读取推进总表，生成会前背景卡片
        ↓
方向 B 会后创建任务，反写推进总表
        ↓
方向 A 每周读取推进总表、会议表、周报表，生成周报和风险洞察
```

也就是说，核心应该先做 D。

推荐顺序：

```text
第一优先级：方向 D
第二优先级：方向 B 会后
第三优先级：方向 B 会前
第四优先级：方向 A 周报
```

原因：

```text
没有 D 的推进总表，A 的周报没有稳定事实基础。
没有 D 的项目上下文源表，B 的会前卡片容易乱检索。
```

------

# 9. 推荐落地路线

## 阶段 0：环境打通

目标：

```text
OpenClaw 能在飞书里回复
飞书 CLI 能读取文档
飞书 CLI 能写多维表格
飞书 CLI 能读写任务
飞书 CLI 能发送消息
```

验收：

```text
1. @小龙虾 ping，能回复
2. 读取一篇测试文档，能摘要
3. 往测试多维表格写一条记录
4. 创建一个测试飞书任务
5. 往测试群发送一条消息
```

------

## 阶段 1：先做方向 D 的骨架

目标：

```text
手动创建项目
手动绑定上下文源
手动同步项目
写入重点事项推进总表
写同步日志
```

必须先把这件事跑通。

验收：

```text
PRD 文档里写 5 条 Todo
会议纪要里写 3 条行动项
任务清单里建 2 个任务

同步后：
推进总表出现正确事项
重复事项被合并
每条事项有证据链接
低置信度进入待确认
同步日志有记录
```

------

## 阶段 2：做方向 B 的会后闭环

目标：

```text
会议纪要 → 行动项 → 飞书任务 → 推进总表 → 通知负责人
```

验收：

```text
会议纪要里写：
“李四 4 月 30 日前完成文档读取能力。”

同步后：
1. 创建飞书任务
2. 负责人是李四
3. 截止时间是 4 月 30 日
4. 推进总表出现该事项
5. 李四收到通知
```

------

## 阶段 3：做方向 B 的会前卡片

目标：

```text
日历事件 → 匹配项目 → 读取上下文 → 推送会前卡片
```

验收：

```text
创建一个“小龙虾项目周会”的日历事件。

会前触发后：
1. 能匹配到小龙虾项目
2. 能列出最近未完成事项
3. 能列出相关文档
4. 能列出上次会议决议
5. 能推送会前卡片
```

------

## 阶段 4：做方向 A 的周报

目标：

```text
每周读取 D 和 B 的结果，生成团队周报。
```

验收：

```text
周报中必须包含：
1. 本周完成事项
2. 本周新增事项
3. 延期事项
4. 阻塞事项
5. 重要会议决议
6. 下周风险
7. 需要管理者介入的问题
```

------

## 阶段 5：从手动触发升级为自动触发

触发方式：

```text
手动触发：
@小龙虾 同步项目：小龙虾

半自动触发：
妙搭按钮触发同步

自动触发：
定时任务 / 事件订阅 / OpenClaw 外部调度
```

飞书事件订阅可以让应用及时响应飞书变更事件；正式版可以用它接收文档、任务、消息等变化，再进入异步处理流程。([飞书开放平台](https://open.feishu.cn/document/server-docs/event-subscription-guide/overview?lang=zh-CN&utm_source=chatgpt.com))

------

# 10. 具体目录结构

建议把小龙虾做成这样：

```text
xiaolongxia/
  skills/
    core-context/
      SKILL.md
    source-bind/
      SKILL.md
    todo-center/
      SKILL.md
    meeting-prep/
      SKILL.md
    meeting-followup/
      SKILL.md
    weekly-report/
      SKILL.md
    risk-insight/
      SKILL.md
    notification/
      SKILL.md
    audit-log/
      SKILL.md
    permission-check/
      SKILL.md

  prompts/
    extract_todos.md
    merge_todos.md
    extract_meeting_actions.md
    generate_weekly_report.md
    generate_meeting_brief.md
    detect_risks.md

  schemas/
    project.schema.json
    source.schema.json
    todo.schema.json
    meeting.schema.json
    weekly_report.schema.json
    sync_log.schema.json

  examples/
    prd_doc_example.md
    meeting_minutes_example.md
    weekly_report_example.md
    todo_table_example.md

  scripts/
    check_lark_cli.sh
    create_project.sh
    bind_source.sh
    sync_project.sh
    generate_weekly_report.sh
    process_meeting_followup.sh
```

------

# 11. Skill 之间的调用关系

```text
用户说：同步项目
  ↓
core-context
  ↓
todo-center
  ↓
risk-insight
  ↓
audit-log
  ↓
notification
用户说：生成周报
  ↓
core-context
  ↓
weekly-report
  ↓
risk-insight
  ↓
notification
  ↓
audit-log
用户说：处理会后纪要
  ↓
core-context
  ↓
meeting-followup
  ↓
todo-center
  ↓
notification
  ↓
audit-log
日历触发：会前准备
  ↓
meeting-prep
  ↓
core-context
  ↓
notification
  ↓
audit-log
```

------

# 12. 关键实现原则

## 原则 1：D 先于 A 和 B

先做“重点事项推进总表”。
它是 A 的周报事实基础，也是 B 的会前背景基础。

## 原则 2：所有输出必须有证据链接

没有来源链接的内容不能进入正式表。

## 原则 3：AI 不直接删除事项

AI 可以标记：

```text
需复核
疑似已失效
来源已删除
长期未更新
```

但不要直接删。

## 原则 4：低置信度进入待确认

比如：

```text
“下周补一下接口”
```

没有负责人、没有明确截止时间，不能直接变成正式任务。

## 原则 5：每次执行都写日志

否则你无法黑盒验收。

------

# 13. 最终实现路径

我建议你按这个顺序让 Codex / OpenClaw 做：

```text
第 1 步：打通 OpenClaw + 飞书 CLI
第 2 步：建 7 张多维表格
第 3 步：写 core-context Skill
第 4 步：写 source-bind Skill 
第 5 步：写 todo-center Skill，实现方向 D 的手动同步
第 6 步：写 meeting-followup Skill，实现方向 B 会后闭环
第 7 步：写 meeting-prep Skill，实现方向 B 会前卡片
第 8 步：写 weekly-report Skill，实现方向 A 周报
第 9 步：写 risk-insight、notification、audit-log
第 10 步：把手动触发升级成定时 / 事件触发
```

一句话总结：

> **这三个方向可以用“小龙虾提示词引导 + 飞书 CLI / OpenClaw 飞书插件 + 多 Skill + 飞书多维表格状态管理”实现。先做 D，形成项目事实底座；再做 B，把会议转成任务和上下文；最后做 A，用前两者沉淀的数据生成高质量周报和风险洞察。**