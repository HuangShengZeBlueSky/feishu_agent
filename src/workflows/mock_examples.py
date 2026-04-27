from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.core.extractors import extract_meeting_notes
from src.core.mock_project import enabled_sources, normalize_title, project_table, read_json, read_text, source_summary
from src.core.run_log import write_run_log
from src.outputs.markdown_renderer import render_post_meeting_summary


def context_overview(project_id: str, *, mode: str = "mock") -> dict[str, Any]:
    sources = enabled_sources(project_id)
    table = project_table()
    output = {
        "sources_count_by_type": source_summary(),
        "sources": sources,
        "project_table_fields": sorted(table[0].keys()) if table else [],
        "project_table_count": len(table),
    }
    log = write_run_log(
        workflow="context-overview",
        mode=mode,
        inputs={"project_id": project_id},
        outputs=output,
        write_plan={"dry_run": True},
    )
    output["run_log"] = str(log)
    return output


def post_meeting_mock(project_id: str, *, mode: str = "mock") -> dict[str, Any]:
    minutes = read_text("sample_minutes.txt")
    result = extract_meeting_notes(minutes, project_id=project_id, source_url="mock://minutes/sample_minutes.txt")
    payload = result.to_jsonable()
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    (output_dir / "会后行动项.json").write_text(_json(payload["action_items"]), encoding="utf-8")
    (output_dir / "会议决策.json").write_text(_json(payload["decisions"]), encoding="utf-8")
    (output_dir / "项目风险.json").write_text(_json(payload["risks"]), encoding="utf-8")
    (output_dir / "会后闭环摘要.md").write_text(render_post_meeting_summary(result), encoding="utf-8")
    write_plan = {
        "dry_run": True,
        "tables": ["Project_Action_Items", "Project_Decisions", "Project_Risks"],
        "create_tasks_requires_confirmation": True,
    }
    outputs = {
        "counts": {
            "action_items": len(payload["action_items"]),
            "decisions": len(payload["decisions"]),
            "risks": len(payload["risks"]),
        },
        "files": [
            "output/会后行动项.json",
            "output/会议决策.json",
            "output/项目风险.json",
            "output/会后闭环摘要.md",
        ],
        "task_confirmation_candidates": [
            item for item in payload["action_items"] if item.get("confidence", 0) >= 0.8 and item.get("owner_text") and item.get("due_date")
        ],
    }
    log = write_run_log(workflow="post-meeting", mode=mode, inputs={"minutes": "resources/mock/sample_minutes.txt"}, outputs=outputs, write_plan=write_plan)
    outputs["run_log"] = str(log)
    return outputs


def pre_meeting_card(project_id: str, meeting_title: str, *, mode: str = "mock") -> dict[str, Any]:
    sources = enabled_sources(project_id)
    table = project_table()
    decisions = ["支付接口字段本周冻结，不再临时修改。"]
    unfinished = [row for row in table if row.get("status") != "done"]
    risks = [row for row in table if row.get("risk_level") in {"high", "medium"} or row.get("status") == "blocked"]
    questions = [
        "验收材料负责人今天能否确认？",
        "错误码文档周五能否交付？",
        "联调环境稳定性是否已经恢复？",
    ]
    card = {
        "title": f"{meeting_title} 会前背景卡片",
        "background": "基于项目上下文清单生成，未进行全局搜索。",
        "core_sources": [s["source_name"] for s in sources if s["priority"] == "high"],
        "last_decisions": decisions,
        "unfinished_items": unfinished,
        "risks": risks,
        "suggested_questions": questions,
        "source_policy": "只读取 Project_Context_Sources enabled=true 的来源。",
    }
    path = Path("output/会前背景卡片.md")
    path.parent.mkdir(exist_ok=True)
    path.write_text(_card_markdown(card), encoding="utf-8")
    log = write_run_log(workflow="pre-meeting-card", mode=mode, inputs={"project_id": project_id, "meeting_title": meeting_title}, outputs={"card": card, "file": str(path)}, write_plan={"dry_run": True})
    return {"card": card, "file": str(path), "run_log": str(log)}


def reconcile_project_table(project_id: str, *, mode: str = "mock") -> dict[str, Any]:
    table = project_table()
    existing = {normalize_title(row["title"]): row for row in table}
    chat_result = extract_meeting_notes(read_text("sample_chat_history.txt"), project_id=project_id, source_url="mock://chat/sample_chat_history.txt")
    comments_result = extract_meeting_notes(read_text("sample_doc_comments.txt"), project_id=project_id, source_url="mock://comments/sample_doc_comments.txt")
    tasks = read_json("sample_tasks.json")
    candidates = chat_result.to_jsonable()["action_items"] + comments_result.to_jsonable()["action_items"]
    diff = {"新增": [], "更新": [], "合并": [], "关闭": [], "需要人工确认": []}
    for task in tasks:
        matched = _match_existing(task["title"], table)
        if matched:
            diff["更新"].append({"title": task["title"], "from_task_status": task.get("status"), "matched": matched["title"]})
        else:
            diff["新增"].append(task)
    for item in candidates:
        matched = _match_existing(item["title"], table)
        if matched:
            diff["合并"].append({"candidate": item["title"], "matched": matched["title"], "source_quote": item["source_quote"]})
        else:
            diff["新增"].append(item)
        if not item.get("owner_text") or not item.get("due_date"):
            diff["需要人工确认"].append(item)
    diff["关闭"] = [row for row in table if row.get("status") == "done"]
    outputs = {"diff": diff, "summary": {k: len(v) for k, v in diff.items()}}
    path = Path("output/项目推进对账diff.json")
    path.write_text(_json(outputs), encoding="utf-8")
    log = write_run_log(workflow="reconcile-project-table", mode=mode, inputs={"chat": "sample_chat_history.txt", "comments": "sample_doc_comments.txt", "tasks": "sample_tasks.json"}, outputs=outputs, write_plan={"dry_run": True, "target": "Project_Action_Items"})
    return {"file": str(path), "summary": outputs["summary"], "run_log": str(log)}


def risk_and_weekly_insight(project_id: str, *, mode: str = "mock") -> dict[str, Any]:
    today = date(2026, 4, 25)
    table = project_table()
    risks = []
    for row in table:
        if row.get("status") == "done":
            continue
        reasons = []
        due = row.get("due_date")
        if due:
            try:
                if datetime.strptime(due, "%Y-%m-%d").date() < today:
                    reasons.append("延期")
            except ValueError:
                pass
        else:
            reasons.append("缺截止时间")
        if not row.get("owner_text"):
            reasons.append("缺负责人")
        if row.get("status") == "blocked":
            reasons.append("阻塞")
        if row.get("risk_level") == "high":
            reasons.append("高风险")
        if reasons:
            risks.append({"title": row["title"], "reasons": reasons, "source_quote": row.get("source_quote", "")})
    weekly = {
        "本周完成": [row for row in table if row.get("status") == "done"],
        "本周新增事项": [row for row in table if row.get("status") != "done"],
        "本周关键决策": ["支付接口字段本周冻结。"],
        "本周风险": risks,
        "下周重点关注": ["错误码文档交付", "联调环境稳定性", "验收材料负责人确认"],
    }
    outputs = {"today_risk_card": risks, "weekly_insight": weekly}
    path = Path("output/每日风险与周报洞察.json")
    path.write_text(_json(outputs), encoding="utf-8")
    log = write_run_log(workflow="risk-weekly-insight", mode=mode, inputs={"project_table": "sample_project_table.json"}, outputs=outputs, write_plan={"dry_run": True})
    return {"file": str(path), "risk_count": len(risks), "run_log": str(log)}


def schedule_meeting_mock(project_id: str, meeting_title: str, *, mode: str = "mock") -> dict[str, Any]:
    calendar = read_json("sample_calendar.json")["roles"]
    counts: dict[str, int] = defaultdict(int)
    for slots in calendar.values():
        for slot in slots:
            counts[slot] += 1
    required = len(calendar)
    candidates = [slot for slot, count in counts.items() if count == required]
    draft = {
        "mode_note": "当前是角色模拟，不是真实飞书用户忙闲。",
        "title": meeting_title,
        "candidate_times": candidates[:3],
        "roles": list(calendar.keys()),
        "agenda": ["确认错误码文档", "确认联调环境", "确认验收材料负责人"],
        "background_links": [s["source_url"] for s in enabled_sources(project_id) if s["source_type"] == "doc"],
    }
    path = Path("output/会议时间候选与草稿.json")
    path.write_text(_json(draft), encoding="utf-8")
    log = write_run_log(workflow="schedule-meeting", mode=mode, inputs={"calendar": "sample_calendar.json"}, outputs=draft, write_plan={"dry_run": True, "create_real_calendar_event": False})
    return {"file": str(path), "candidate_times": candidates[:3], "run_log": str(log)}


def simulate_agents_meeting(project_id: str, meeting_title: str, *, mode: str = "mock") -> dict[str, Any]:
    agents = read_json("sample_agents.json")
    lines = [
        f"# {meeting_title} 多智能体模拟会议",
        "",
        "说明：当前是 mock 模式，角色是模拟智能体，不是真实飞书用户。",
        "",
    ]
    dialogue = [
        ("项目经理", "今天目标是确认错误码文档、联调环境、验收材料负责人。"),
        ("产品", "验收材料这周要准备好，不然下周客户评审会受影响。"),
        ("后端", "错误码文档我还没整理，预计周五给。"),
        ("前端", "我这边等错误码文档，文档完成后一天内可以完成联调。"),
        ("测试", "联调环境今天又挂了，测试进度可能要延后。"),
        ("项目经理", "结论：字段本周冻结；小王周五前补齐错误码；验收材料负责人需要今天确认。"),
    ]
    for role, text in dialogue:
        lines.append(f"- **{role}**：{text}")
    transcript = "\n".join(lines) + "\n"
    path = Path("output/多智能体模拟会议.md")
    path.write_text(transcript, encoding="utf-8")
    extraction = extract_meeting_notes("\n".join(text for _, text in dialogue), project_id=project_id, source_url="mock://agents/meeting")
    outputs = {
        "file": str(path),
        "agents": agents,
        "counts": {
            "action_items": len(extraction.action_items),
            "decisions": len(extraction.decisions),
            "risks": len(extraction.risks),
        },
        "note": "角色只填写 role/owner_text，不编造 owner_user_id。",
    }
    log = write_run_log(workflow="simulate-agents-meeting", mode=mode, inputs={"project_id": project_id, "meeting_title": meeting_title}, outputs=outputs, write_plan={"dry_run": True, "create_real_meeting": False})
    outputs["run_log"] = str(log)
    return outputs


def document_preview(project_id: str, doc_type: str = "post_meeting", *, mode: str = "mock") -> dict[str, Any]:
    table = project_table()
    title = "支付项目会后总结" if doc_type == "post_meeting" else "支付项目周报与下周风险洞察"
    content = [
        f"# {title}",
        "",
        "## 关键决策",
        "- 支付接口字段本周冻结，不再临时修改。",
        "",
        "## 行动项",
    ]
    content.extend([f"- {row['title']}（负责人：{row.get('owner_text') or '待确认'}，状态：{row.get('status')}）" for row in table if row.get("status") != "done"])
    content.extend(["", "## 风险与阻塞"])
    content.extend([f"- {row['title']}：{row.get('source_quote', '')}" for row in table if row.get("risk_level") in {"high", "medium"}])
    content.extend(["", "## 来源证据", "- mock://bitable/sample_project_table.json", "- mock://minutes/sample_minutes.txt"])
    path = Path("output/文档预览.md")
    path.write_text("\n".join(content) + "\n", encoding="utf-8")
    write_plan = {"dry_run": True, "create_feishu_doc_requires_confirmation": True, "update_context_sources_after_create": True}
    log = write_run_log(workflow="document-preview", mode=mode, inputs={"doc_type": doc_type}, outputs={"title": title, "file": str(path)}, write_plan=write_plan)
    return {"file": str(path), "title": title, "run_log": str(log)}


def run_all_mock(project_id: str) -> dict[str, Any]:
    results = {
        "0_context": context_overview(project_id),
        "1_post_meeting": post_meeting_mock(project_id),
        "2_pre_meeting": pre_meeting_card(project_id, "支付项目评审会"),
        "3_reconcile": reconcile_project_table(project_id),
        "4_risk_weekly": risk_and_weekly_insight(project_id),
        "5_schedule": schedule_meeting_mock(project_id, "支付项目评审会"),
        "5b_agents_meeting": simulate_agents_meeting(project_id, "支付项目评审会"),
        "6_document": document_preview(project_id),
    }
    path = Path("output/六个例子总览.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(_json(results), encoding="utf-8")
    return {"file": str(path), "results": results}


def _json(data: Any) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, indent=2)


def _match_existing(title: str, table: list[dict[str, Any]]) -> dict[str, Any] | None:
    title_key = normalize_title(title)
    for row in table:
        row_key = normalize_title(row["title"])
        if title_key and row_key and (title_key in row_key or row_key in title_key):
            return row
        if _keyword_overlap(title, row["title"]) >= 2:
            return row
    return None


def _keyword_overlap(left: str, right: str) -> int:
    keywords = ["错误码", "验收", "联调", "环境", "负责人", "文档", "接口", "材料", "测试"]
    return sum(1 for keyword in keywords if keyword in left and keyword in right)


def _card_markdown(card: dict[str, Any]) -> str:
    lines = [f"# {card['title']}", "", f"背景：{card['background']}", "", "## 历史决策"]
    lines.extend([f"- {item}" for item in card["last_decisions"]])
    lines.append("")
    lines.append("## 未完成事项")
    lines.extend([f"- {item['title']}（{item.get('status')}）" for item in card["unfinished_items"]])
    lines.append("")
    lines.append("## 当前风险")
    lines.extend([f"- {item['title']}（{item.get('risk_level')}）" for item in card["risks"]])
    lines.append("")
    lines.append("## 建议确认问题")
    lines.extend([f"- {item}" for item in card["suggested_questions"]])
    lines.append("")
    lines.append(f"来源策略：{card['source_policy']}")
    return "\n".join(lines) + "\n"
