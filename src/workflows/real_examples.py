from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.llm_extractors import extract_meeting_notes_with_llm
from src.core.run_log import write_run_log
from src.llm.client import JsonLlmClient
from src.outputs.markdown_renderer import render_post_meeting_summary
from src.sources.feishu_project import REAL_SEED_MINUTES, FeishuProjectStore


def seed_real_project(project_id: str, *, dry_run: bool) -> dict[str, Any]:
    store = FeishuProjectStore()
    result = store.seed_real_project(project_id, dry_run=dry_run)
    log = write_run_log(
        workflow="seed-real-project",
        mode="feishu",
        inputs={"project_id": project_id},
        outputs={"seeded": {k: v for k, v in result.items() if k != "seed_minutes_text"}},
        write_plan={"dry_run": dry_run, "target": "real Feishu Bitable"},
        actual_writes={} if dry_run else {k: v for k, v in result.items() if k != "seed_minutes_text"},
    )
    return {"result": result, "run_log": str(log)}


def context_overview_real(project_id: str) -> dict[str, Any]:
    store = FeishuProjectStore()
    sources = store.read_context_sources(project_id)
    actions = store.read_action_items(project_id)
    decisions = store.read_decisions(project_id)
    risks = store.read_risks(project_id)
    output = {
        "source_count_by_type": dict(Counter(str(row.get("source_type")) for row in sources)),
        "sources": sources,
        "counts": {
            "context_sources": len(sources),
            "action_items": len(actions),
            "decisions": len(decisions),
            "risks": len(risks),
        },
    }
    log = write_run_log(workflow="context-overview", mode="feishu", inputs={"project_id": project_id}, outputs=output, write_plan={"dry_run": True})
    output["run_log"] = str(log)
    return output


def post_meeting_real(
    *,
    project_id: str,
    minutes_file: Path | None,
    source_url: str,
    write_bitable: bool,
    dry_run: bool,
    output_dir: Path = Path("output"),
) -> dict[str, Any]:
    text = _read_minutes(minutes_file)
    now = datetime.now().isoformat(timespec="seconds")
    result = extract_meeting_notes_with_llm(text, project_id=project_id, source_url=source_url, detected_at=now)
    payload = result.to_jsonable()

    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "action_items": output_dir / "real_action_items.json",
        "decisions": output_dir / "real_decisions.json",
        "risks": output_dir / "real_risks.json",
        "summary": output_dir / "real_post_meeting_summary.md",
    }
    files["action_items"].write_text(json.dumps(payload["action_items"], ensure_ascii=False, indent=2), encoding="utf-8")
    files["decisions"].write_text(json.dumps(payload["decisions"], ensure_ascii=False, indent=2), encoding="utf-8")
    files["risks"].write_text(json.dumps(payload["risks"], ensure_ascii=False, indent=2), encoding="utf-8")
    files["summary"].write_text(render_post_meeting_summary(result), encoding="utf-8")

    writes = None
    if write_bitable:
        writes = FeishuProjectStore().write_extraction(result, dry_run=dry_run)
        preview = output_dir / "real_bitable_write_preview.json"
        preview.write_text(json.dumps(writes, ensure_ascii=False, indent=2), encoding="utf-8")
        files["bitable"] = preview

    log = write_run_log(
        workflow="post-meeting",
        mode="feishu-llm",
        inputs={"project_id": project_id, "minutes_file": str(minutes_file) if minutes_file else "real-seed", "source_url": source_url},
        outputs={"counts": {"action_items": len(result.action_items), "decisions": len(result.decisions), "risks": len(result.risks)}, "files": {k: str(v) for k, v in files.items()}},
        write_plan={"write_bitable": write_bitable, "dry_run": dry_run},
        actual_writes=writes if writes and not dry_run else {},
    )
    return {"counts": {"action_items": len(result.action_items), "decisions": len(result.decisions), "risks": len(result.risks)}, "files": {k: str(v) for k, v in files.items()}, "run_log": str(log)}


def pre_meeting_card_real(project_id: str, meeting_title: str, *, output_dir: Path = Path("output")) -> dict[str, Any]:
    store = FeishuProjectStore()
    data = _project_snapshot(store, project_id)
    card = JsonLlmClient().complete_json(
        system="你是会前背景卡片助手。只根据输入的真实飞书多维表格数据生成 JSON，不要编造。",
        user=f"""会议标题：{meeting_title}
真实项目数据：
{json.dumps(data, ensure_ascii=False, indent=2)}

返回 JSON 字段：
title、background、last_decisions、unfinished_items、risks、suggested_questions、source_evidence。
suggested_questions 至少 3 个，每个问题要说明为什么要问。
""",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "real_pre_meeting_card.json"
    path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    log = write_run_log(workflow="pre-meeting-card", mode="feishu-llm", inputs={"project_id": project_id, "meeting_title": meeting_title}, outputs={"file": str(path), "card": card}, write_plan={"dry_run": True})
    return {"file": str(path), "card": card, "run_log": str(log)}


def reconcile_project_table_real(project_id: str, *, output_dir: Path = Path("output")) -> dict[str, Any]:
    store = FeishuProjectStore()
    data = _project_snapshot(store, project_id)
    diff = JsonLlmClient().complete_json(
        system="你是项目推进表对账助手。只根据输入的真实飞书多维表格数据判断新增、更新、合并、关闭、需要人工确认。",
        user=f"""真实项目数据：
{json.dumps(data, ensure_ascii=False, indent=2)}

请返回 JSON 字段：新增、更新、合并、关闭、需要人工确认、summary。
每条 diff 必须解释依据，并引用 source_quote 或 source_url。
""",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "real_project_reconcile_diff.json"
    path.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    log = write_run_log(workflow="reconcile-project-table", mode="feishu-llm", inputs={"project_id": project_id}, outputs={"file": str(path), "diff": diff}, write_plan={"dry_run": True})
    return {"file": str(path), "diff": diff, "run_log": str(log)}


def risk_weekly_insight_real(project_id: str, *, output_dir: Path = Path("output")) -> dict[str, Any]:
    store = FeishuProjectStore()
    data = _project_snapshot(store, project_id)
    insight = JsonLlmClient().complete_json(
        system="你是项目风险巡检和周报助手。只根据输入的真实飞书数据生成风险巡检和周报洞察，不要编造。",
        user=f"""今天：{datetime.now().date().isoformat()}
真实项目数据：
{json.dumps(data, ensure_ascii=False, indent=2)}

返回 JSON 字段：today_risk_card、weekly_insight、next_week_focus、needs_manager_attention。
风险原因必须覆盖延期、缺负责人、缺截止时间、阻塞、高风险这些维度中实际存在的项。
""",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "real_risk_weekly_insight.json"
    path.write_text(json.dumps(insight, ensure_ascii=False, indent=2), encoding="utf-8")
    log = write_run_log(workflow="risk-weekly-insight", mode="feishu-llm", inputs={"project_id": project_id}, outputs={"file": str(path), "insight": insight}, write_plan={"dry_run": True})
    return {"file": str(path), "insight": insight, "run_log": str(log)}


def schedule_meeting_real(project_id: str, meeting_title: str, *, output_dir: Path = Path("output")) -> dict[str, Any]:
    store = FeishuProjectStore()
    data = _project_snapshot(store, project_id)
    draft = JsonLlmClient().complete_json(
        system="你是会议筹备助手。只能根据真实飞书项目数据生成会议目标和议程；没有真实日历忙闲时，必须明确列出依赖缺口，不要编造候选时间。",
        user=f"""会议标题：{meeting_title}
真实项目数据：
{json.dumps(data, ensure_ascii=False, indent=2)}

返回 JSON 字段：title、agenda、required_attendee_roles、calendar_dependency、cannot_schedule_reason、next_steps。
calendar_dependency 必须说明需要真实日历 ID、参会人 open_id 或用户 OAuth 授权。
""",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "real_schedule_meeting_dependency.json"
    path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    log = write_run_log(workflow="schedule-meeting", mode="feishu-llm", inputs={"project_id": project_id, "meeting_title": meeting_title}, outputs={"file": str(path), "draft": draft}, write_plan={"dry_run": True, "create_real_calendar_event": False})
    return {"file": str(path), "draft": draft, "run_log": str(log)}


def document_preview_real(project_id: str, doc_type: str, *, output_dir: Path = Path("output")) -> dict[str, Any]:
    store = FeishuProjectStore()
    data = _project_snapshot(store, project_id)
    doc = JsonLlmClient().complete_json(
        system="你是项目文档生成助手。只根据输入的真实飞书数据生成结构化文档预览 JSON，不创建真实文档。",
        user=f"""文档类型：{doc_type}
真实项目数据：
{json.dumps(data, ensure_ascii=False, indent=2)}

返回 JSON 字段：title、sections、source_evidence、write_back_plan。
sections 是数组，每项包含 heading 和 bullets。
""",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "real_document_preview.json"
    md_path = output_dir / "real_document_preview.md"
    json_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_doc_markdown(doc), encoding="utf-8")
    log = write_run_log(workflow="document-preview", mode="feishu-llm", inputs={"project_id": project_id, "doc_type": doc_type}, outputs={"json": str(json_path), "markdown": str(md_path)}, write_plan={"dry_run": True, "create_feishu_doc_requires_confirmation": True})
    return {"json": str(json_path), "markdown": str(md_path), "run_log": str(log)}


def run_all_real(project_id: str, *, dry_run: bool) -> dict[str, Any]:
    results = {
        "0_seed": seed_real_project(project_id, dry_run=dry_run),
        "1_context": context_overview_real(project_id),
        "2_post_meeting": post_meeting_real(project_id=project_id, minutes_file=None, source_url="feishu-seed://minutes/pay-project-review-20260428", write_bitable=True, dry_run=dry_run),
        "3_pre_meeting": pre_meeting_card_real(project_id, "支付项目评审会"),
        "4_reconcile": reconcile_project_table_real(project_id),
        "5_risk_weekly": risk_weekly_insight_real(project_id),
        "5_schedule": schedule_meeting_real(project_id, "支付项目评审会"),
        "6_document": document_preview_real(project_id, "weekly"),
    }
    path = Path("output/真实链路总览.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"file": str(path), "results": results}


def _project_snapshot(store: FeishuProjectStore, project_id: str) -> dict[str, Any]:
    return {
        "context_sources": store.read_context_sources(project_id),
        "action_items": store.read_action_items(project_id),
        "decisions": store.read_decisions(project_id),
        "risks": store.read_risks(project_id),
    }


def _read_minutes(minutes_file: Path | None) -> str:
    if minutes_file:
        return minutes_file.read_text(encoding="utf-8")
    return REAL_SEED_MINUTES


def _doc_markdown(doc: dict[str, Any]) -> str:
    lines = [f"# {doc.get('title') or '项目文档预览'}", ""]
    for section in doc.get("sections") or []:
        if not isinstance(section, dict):
            continue
        lines.extend([f"## {section.get('heading') or '未命名章节'}", ""])
        for bullet in section.get("bullets") or []:
            lines.append(f"- {bullet}")
        lines.append("")
    lines.append("## 来源证据")
    for item in doc.get("source_evidence") or []:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)
