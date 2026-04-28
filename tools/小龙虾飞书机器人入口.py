#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sources.feishu_project import FeishuProjectStore  # noqa: E402
from src.workflows.real_examples import (  # noqa: E402
    context_overview_real,
    document_preview_real,
    post_meeting_real,
    pre_meeting_card_real,
    reconcile_project_table_real,
    risk_weekly_insight_real,
    schedule_meeting_real,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="小龙虾飞书机器人自然语言入口")
    parser.add_argument("--message", required=True, help="飞书群里的用户自然语言消息")
    parser.add_argument("--project-id", default="pay_project")
    parser.add_argument("--meeting-title", default="支付项目评审会")
    parser.add_argument("--minutes-file", type=Path, help="本地真实会议纪要文件")
    parser.add_argument("--json", action="store_true", help="输出 JSON 而不是群聊文本")
    args = parser.parse_args()

    result = route_message(args.message, project_id=args.project_id, meeting_title=args.meeting_title, minutes_file=args.minutes_file)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["reply"])
    return 0


def route_message(message: str, *, project_id: str, meeting_title: str, minutes_file: Path | None) -> dict[str, Any]:
    text = _strip_bot_mention(message)
    if _has_any(text, ["会前", "背景卡", "背景", "开会前", "评审会准备"]):
        data = pre_meeting_card_real(project_id, meeting_title)
        return {"intent": "B.pre_meeting_card", "reply": _reply_pre_meeting(data)}

    if _has_any(text, ["会后", "纪要", "妙记", "行动项", "抽取", "写入推进表", "写入表格"]):
        data = post_meeting_real(
            project_id=project_id,
            minutes_file=minutes_file,
            source_url="feishu-message://manual",
            write_bitable=True,
            dry_run=False,
        )
        return {"intent": "B.post_meeting", "reply": _reply_post_meeting(data)}

    if _has_any(text, ["对账", "推进表", "重复", "合并", "同步任务", "待办中枢"]):
        data = reconcile_project_table_real(project_id)
        return {"intent": "D.reconcile", "reply": _reply_reconcile(data)}

    if _has_any(text, ["约会", "约会议", "日程", "会议时间", "忙闲", "排期"]):
        data = schedule_meeting_real(project_id, meeting_title)
        return {"intent": "B.schedule", "reply": _reply_schedule(data)}

    if _has_any(text, ["创建文档", "飞书文档", "沉淀", "文档预览", "生成文档"]):
        data = document_preview_real(project_id, "weekly")
        created = _create_feishu_doc_if_requested(text, data, project_id)
        return {"intent": "A_B_D.document", "reply": _reply_document(data, created)}

    if _has_any(text, ["风险", "周报", "延期", "阻塞", "洞察", "巡检"]):
        data = risk_weekly_insight_real(project_id)
        return {"intent": "A.risk_weekly", "reply": _reply_risk(data)}

    data = context_overview_real(project_id)
    return {"intent": "overview", "reply": _reply_overview(data)}


def _reply_overview(data: dict[str, Any]) -> str:
    counts = data.get("counts", {})
    types = ", ".join(f"{k}:{v}" for k, v in (data.get("source_count_by_type") or {}).items())
    return "\n".join(
        [
            "我现在已接入真实飞书项目上下文。",
            f"来源类型：{types}",
            f"上下文 {counts.get('context_sources', 0)} 条，行动项 {counts.get('action_items', 0)} 条，决策 {counts.get('decisions', 0)} 条，风险 {counts.get('risks', 0)} 条。",
            "你可以让我：生成会前卡片、抽取会后行动项、做推进表对账、生成风险周报、创建飞书文档。",
        ]
    )


def _reply_pre_meeting(data: dict[str, Any]) -> str:
    card = data["card"]
    lines = [f"已生成《{card.get('title', '会前背景卡片')}》。", "", "历史决策："]
    lines.extend([f"- {item}" for item in card.get("last_decisions", [])[:5]] or ["- 暂无"])
    lines.append("")
    lines.append("未完成事项：")
    lines.extend([f"- {item}" for item in card.get("unfinished_items", [])[:5]] or ["- 暂无"])
    lines.append("")
    lines.append("当前风险：")
    lines.extend([f"- {item}" for item in card.get("risks", [])[:5]] or ["- 暂无"])
    lines.append("")
    lines.append("建议会议确认：")
    for item in card.get("suggested_questions", [])[:5]:
        if isinstance(item, dict):
            lines.append(f"- {item.get('question')}：{item.get('reason')}")
        else:
            lines.append(f"- {item}")
    return "\n".join(lines)


def _reply_post_meeting(data: dict[str, Any]) -> str:
    counts = data["counts"]
    return "\n".join(
        [
            "已完成会后闭环抽取，并写入真实飞书 Base。",
            f"- 行动项：{counts.get('action_items', 0)} 条",
            f"- 决策：{counts.get('decisions', 0)} 条",
            f"- 风险：{counts.get('risks', 0)} 条",
            "我保留了 source_quote 作为每条结论的来源证据。",
        ]
    )


def _reply_reconcile(data: dict[str, Any]) -> str:
    diff = data["diff"]
    summary = diff.get("summary", "已生成项目推进表对账 diff。")
    lines = [str(summary), "", "需要人工确认："]
    for item in diff.get("需要人工确认", [])[:6]:
        lines.append(f"- {item if isinstance(item, str) else item.get('内容', item)}")
    lines.append(f"\n详情文件：{data['file']}")
    return "\n".join(lines)


def _reply_risk(data: dict[str, Any]) -> str:
    insight = data["insight"]
    lines = ["已完成风险巡检和周报洞察。", "", "今日风险："]
    for item in insight.get("today_risk_card", [])[:6]:
        if isinstance(item, dict):
            lines.append(f"- {item.get('risk_title') or item.get('title')}：{item.get('risk_desc') or item.get('risk_description') or item.get('impact')}")
        else:
            lines.append(f"- {item}")
    lines.append("")
    lines.append("下周关注：")
    lines.extend([f"- {item}" for item in insight.get("next_week_focus", [])[:6]] or ["- 暂无"])
    return "\n".join(lines)


def _reply_schedule(data: dict[str, Any]) -> str:
    draft = data["draft"]
    lines = [f"已生成《{draft.get('title', '会议')}》筹备方案。", "", "议程："]
    lines.extend([f"- {item}" for item in draft.get("agenda", [])])
    lines.append("")
    lines.append("排期依赖：")
    lines.append(str(draft.get("calendar_dependency", "")))
    if draft.get("cannot_schedule_reason"):
        lines.append(f"当前不能自动给出候选时间：{draft['cannot_schedule_reason']}")
    return "\n".join(lines)


def _reply_document(data: dict[str, Any], created: dict[str, Any] | None) -> str:
    lines = ["已生成项目文档预览。", f"本地预览：{data.get('markdown')}"]
    if created and created.get("url"):
        lines.append(f"已创建飞书文档：{created['url']}")
    elif created and created.get("error"):
        lines.append(f"飞书文档创建失败：{created['error']}")
    else:
        lines.append("如果你要我创建飞书文档，请说：创建飞书文档。")
    return "\n".join(lines)


def _create_feishu_doc_if_requested(message: str, data: dict[str, Any], project_id: str) -> dict[str, Any] | None:
    if not _has_any(message, ["创建", "新建", "写到飞书", "飞书文档"]):
        return None
    cli = Path(os.environ.get("APPDATA", "")) / "npm" / "lark-cli.cmd"
    if not cli.exists():
        return {"error": f"找不到 lark-cli: {cli}"}
    markdown = str(data["markdown"])
    proc = subprocess.run(
        [
            str(cli),
            "docs",
            "+create",
            "--api-version",
            "v2",
            "--as",
            "bot",
            "--doc-format",
            "markdown",
            "--content",
            f"@{markdown}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if proc.returncode != 0:
        return {"error": (proc.stdout + proc.stderr).strip()[:1000]}
    payload = json.loads(proc.stdout)
    document = ((payload.get("data") or {}).get("document") or {})
    doc_id = document.get("document_id")
    url = document.get("url")
    if doc_id and url:
        FeishuProjectStore().write_context_sources(
            [
                {
                    "project_id": project_id,
                    "source_name": "小龙虾生成的项目周报文档",
                    "source_type": "doc",
                    "source_url": url,
                    "source_id": doc_id,
                    "priority": "high",
                    "owner_text": "小龙虾项目上下文管家",
                    "enabled": "true",
                    "description": "由飞书机器人自然语言请求生成的真实飞书文档。",
                }
            ],
            dry_run=False,
        )
    return {"document_id": doc_id, "url": url}


def _strip_bot_mention(message: str) -> str:
    return message.replace("@小龙虾项目上下文管家", "").replace("@会议", "").strip()


def _has_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


if __name__ == "__main__":
    raise SystemExit(main())
