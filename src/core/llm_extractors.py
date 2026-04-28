from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.core.extractors import ActionItem, Decision, ExtractionResult, Risk
from src.llm.client import JsonLlmClient


EXTRACTION_SYSTEM = """你是项目管理信息抽取助手。只根据用户给出的文本抽取信息，不要编造。
必须返回 JSON object，字段固定为 action_items、decisions、risks。
每条记录必须保留 source_quote，source_quote 必须是输入文本中的原句或短片段。
如果负责人不是明确飞书用户 ID，只填写 owner_text，owner_user_id 留空。
日期不确定时可以保留原文表达，例如“本周五”“文档完成后一天内”。
confidence 是 0 到 1 的数字，表示这条抽取有多确定。
"""


def extract_meeting_notes_with_llm(
    text: str,
    *,
    project_id: str,
    source_url: str = "",
    meeting_title: str = "真实会议文本",
    meeting_time: str = "",
    detected_at: str = "",
    client: JsonLlmClient | None = None,
) -> ExtractionResult:
    llm = client or JsonLlmClient()
    data = llm.complete_json(
        system=EXTRACTION_SYSTEM,
        user=f"""项目 ID：{project_id}
会议标题：{meeting_title}
会议时间：{meeting_time}
来源链接：{source_url}

请抽取：
1. action_items：行动项/待办，字段 title、description、owner_text、owner_user_id、due_date、priority、status、risk_level、blocker_reason、source_quote、confidence。
2. decisions：决策，字段 decision、rationale、participants、source_quote、confidence。
3. risks：风险/阻塞，字段 risk_title、risk_description、risk_level、impact、owner_text、owner_user_id、suggested_action、status、source_quote。

输入文本：
{text}
""",
    )
    return _to_result(data, project_id=project_id, source_url=source_url, meeting_title=meeting_title, meeting_time=meeting_time, detected_at=detected_at)


def _to_result(
    data: dict[str, Any],
    *,
    project_id: str,
    source_url: str,
    meeting_title: str,
    meeting_time: str,
    detected_at: str,
) -> ExtractionResult:
    action_items = []
    for row in _list(data.get("action_items")):
        owner_text = str(row.get("owner_text") or row.get("owner") or "")
        action_items.append(
            ActionItem(
                project_id=project_id,
                title=str(row.get("title") or row.get("description") or "")[:80],
                description=str(row.get("description") or row.get("title") or ""),
                owner=owner_text,
                owner_text=owner_text,
                owner_user_id=str(row.get("owner_user_id") or ""),
                due_date=str(row.get("due_date") or ""),
                priority=str(row.get("priority") or "P2"),
                status=str(row.get("status") or "todo"),
                risk_level=str(row.get("risk_level") or "low"),
                blocker_reason=str(row.get("blocker_reason") or ""),
                source_type="meeting",
                source_url=source_url,
                source_quote=str(row.get("source_quote") or row.get("description") or row.get("title") or ""),
                task_url=str(row.get("task_url") or ""),
                created_by_ai=True,
                confidence=_float(row.get("confidence"), 0.75),
            )
        )

    decisions = []
    for row in _list(data.get("decisions")):
        decisions.append(
            Decision(
                project_id=project_id,
                meeting_title=meeting_title,
                meeting_time=meeting_time,
                decision=str(row.get("decision") or ""),
                rationale=str(row.get("rationale") or "由 LLM 根据来源文本抽取，需人工复核。"),
                participants=str(row.get("participants") or ""),
                source_url=source_url,
                source_quote=str(row.get("source_quote") or row.get("decision") or ""),
                confidence=_float(row.get("confidence"), 0.75),
            )
        )

    risks = []
    for row in _list(data.get("risks")):
        owner_text = str(row.get("owner_text") or row.get("owner") or "")
        risks.append(
            Risk(
                project_id=project_id,
                risk_title=str(row.get("risk_title") or row.get("risk_description") or "")[:80],
                risk_description=str(row.get("risk_description") or row.get("risk_title") or ""),
                risk_level=str(row.get("risk_level") or "medium"),
                impact=str(row.get("impact") or "需要人工复核影响范围。"),
                owner=owner_text,
                owner_text=owner_text,
                owner_user_id=str(row.get("owner_user_id") or ""),
                suggested_action=str(row.get("suggested_action") or "请负责人确认风险状态和下一步动作。"),
                status=str(row.get("status") or "open"),
                source_url=source_url,
                source_quote=str(row.get("source_quote") or row.get("risk_description") or row.get("risk_title") or ""),
                detected_at=detected_at,
                last_checked_at=detected_at,
            )
        )
    return ExtractionResult(action_items=action_items, decisions=decisions, risks=risks)


def extraction_to_json(result: ExtractionResult) -> dict[str, list[dict[str, Any]]]:
    return {
        "action_items": [asdict(item) for item in result.action_items],
        "decisions": [asdict(item) for item in result.decisions],
        "risks": [asdict(item) for item in result.risks],
    }


def _list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _float(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default
