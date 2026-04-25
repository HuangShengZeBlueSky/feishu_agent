from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass
class ActionItem:
    project_id: str
    title: str
    description: str
    owner: str
    owner_text: str
    owner_user_id: str
    due_date: str
    priority: str
    status: str
    risk_level: str
    blocker_reason: str
    source_type: str
    source_url: str
    source_quote: str
    task_url: str
    created_by_ai: bool
    confidence: float


@dataclass
class Decision:
    project_id: str
    meeting_title: str
    meeting_time: str
    decision: str
    rationale: str
    participants: str
    source_url: str
    source_quote: str
    confidence: float


@dataclass
class Risk:
    project_id: str
    risk_title: str
    risk_description: str
    risk_level: str
    impact: str
    owner: str
    owner_text: str
    owner_user_id: str
    suggested_action: str
    status: str
    source_url: str
    source_quote: str
    detected_at: str
    last_checked_at: str


@dataclass
class ExtractionResult:
    action_items: list[ActionItem]
    decisions: list[Decision]
    risks: list[Risk]

    def to_jsonable(self) -> dict[str, list[dict[str, object]]]:
        return {
            "action_items": [asdict(item) for item in self.action_items],
            "decisions": [asdict(item) for item in self.decisions],
            "risks": [asdict(item) for item in self.risks],
        }


OWNER_PATTERNS = [
    re.compile(r"(?P<owner>[\u4e00-\u9fa5A-Za-z0-9_]{2,12})(?:负责|来负责|牵头)"),
    re.compile(r"(?:后端|前端|测试|产品|项目经理)(?P<owner>小[\u4e00-\u9fa5])"),
    re.compile(r"(?:后端|前端|测试|产品|项目经理)(?P<owner>[\u4e00-\u9fa5A-Za-z0-9_]{2,4}?)(?:需要|要|负责)"),
    re.compile(r"负责人[:：]\s*(?P<owner>[\u4e00-\u9fa5A-Za-z0-9_]{2,12})"),
]
DATE_PATTERNS = [
    re.compile(r"(?P<date>20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})"),
    re.compile(r"(?P<date>\d{1,2}\s*月\s*\d{1,2}\s*日)"),
    re.compile(r"(?P<date>接口文档完成后一天内|文档完成后一天内|完成后一天内)"),
    re.compile(r"(?P<date>周[一二三四五六日天]|今天|明天|后天|本周[一二三四五六日天]?|下周[一二三四五六日天]?)"),
]


def extract_meeting_notes(
    text: str,
    *,
    project_id: str,
    source_url: str = "",
    meeting_title: str = "本地会议文本",
    meeting_time: str = "",
    detected_at: str = "",
) -> ExtractionResult:
    lines = [_clean_line(line) for line in text.splitlines() if line.strip()]
    action_items: list[ActionItem] = []
    decisions: list[Decision] = []
    risks: list[Risk] = []

    for line in lines:
        if _looks_like_action(line):
            action_items.append(_action_from_line(line, project_id, source_url))
        if _looks_like_decision(line):
            decisions.append(_decision_from_line(line, project_id, source_url, meeting_title, meeting_time))
        if _looks_like_risk(line):
            risks.append(_risk_from_line(line, project_id, source_url, detected_at))

    return ExtractionResult(action_items=dedupe(action_items, "source_quote"), decisions=dedupe(decisions, "source_quote"), risks=dedupe(risks, "source_quote"))


def dedupe(items: list[object], key: str) -> list[object]:
    seen: set[str] = set()
    output: list[object] = []
    for item in items:
        value = str(getattr(item, key))
        if value in seen:
            continue
        seen.add(value)
        output.append(item)
    return output


def _looks_like_action(line: str) -> bool:
    markers = ["负责", "截止", "完成", "补齐", "确认", "跟进", "整理", "同步", "创建", "更新"]
    return any(marker in line for marker in markers) and not _looks_like_decision(line)


def _looks_like_decision(line: str) -> bool:
    if "没有明确负责人" in line:
        return False
    markers = ["决定", "决策", "确认采用", "明确", "字段先冻结", "字段本周冻结", "暂不", "本次确定"]
    return any(marker in line for marker in markers)


def _looks_like_risk(line: str) -> bool:
    markers = ["风险", "阻塞", "延期", "未就绪", "来不及", "缺少", "缺负责人", "缺截止", "可能影响", "无法访问"]
    return any(marker in line for marker in markers)


def _clean_line(line: str) -> str:
    cleaned = line.strip(" -\t")
    return re.sub(r"^\d+[.、]\s*", "", cleaned)


def _owner(line: str) -> str:
    if "缺少" in line and "负责人" in line:
        return ""
    if "没有明确负责人" in line:
        return ""
    if "缺负责人" in line:
        return ""
    for pattern in OWNER_PATTERNS:
        match = pattern.search(line)
        if match:
            return match.group("owner")
    return ""


def _due_date(line: str) -> str:
    for pattern in DATE_PATTERNS:
        match = pattern.search(line)
        if match:
            return match.group("date").replace(" ", "")
    return ""


def _risk_level(line: str) -> str:
    if any(word in line for word in ["高风险", "阻塞", "延期", "无法", "严重"]):
        return "high"
    if any(word in line for word in ["风险", "可能", "缺少", "缺负责人", "缺截止"]):
        return "medium"
    return "low"


def _priority(line: str) -> str:
    if any(word in line for word in ["P0", "紧急", "阻塞", "今天"]):
        return "P0"
    if any(word in line for word in ["P1", "本周", "高风险", "截止"]):
        return "P1"
    return "P2"


def _short_title(line: str, max_len: int = 36) -> str:
    cleaned = re.sub(r"^(行动项|TODO|待办|风险|决策|决定)[:：]\s*", "", line, flags=re.IGNORECASE)
    return cleaned[:max_len]


def _confidence(line: str) -> float:
    score = 0.62
    if _owner(line):
        score += 0.12
    if _due_date(line):
        score += 0.12
    if any(word in line for word in ["来源", "明确", "负责", "截止", "决定"]):
        score += 0.08
    return min(round(score, 2), 0.95)


def _action_from_line(line: str, project_id: str, source_url: str) -> ActionItem:
    owner = _owner(line)
    return ActionItem(
        project_id=project_id,
        title=_short_title(line),
        description=line,
        owner=owner,
        owner_text=owner,
        owner_user_id="",
        due_date=_due_date(line),
        priority=_priority(line),
        status="todo",
        risk_level=_risk_level(line),
        blocker_reason="",
        source_type="meeting",
        source_url=source_url,
        source_quote=line,
        task_url="",
        created_by_ai=True,
        confidence=_confidence(line),
    )


def _decision_from_line(line: str, project_id: str, source_url: str, meeting_title: str, meeting_time: str) -> Decision:
    return Decision(
        project_id=project_id,
        meeting_title=meeting_title,
        meeting_time=meeting_time,
        decision=re.sub(r"^(决策|决定)[:：]\s*", "", line),
        rationale="规则抽取阶段暂未推断决策原因，请人工复核或接入 LLM 后补全。",
        participants="",
        source_url=source_url,
        source_quote=line,
        confidence=_confidence(line),
    )


def _risk_from_line(line: str, project_id: str, source_url: str, detected_at: str) -> Risk:
    owner = _owner(line)
    return Risk(
        project_id=project_id,
        risk_title=_short_title(line),
        risk_description=line,
        risk_level=_risk_level(line),
        impact="待人工复核影响范围。",
        owner=owner,
        owner_text=owner,
        owner_user_id="",
        suggested_action="请项目负责人确认风险状态、负责人和截止时间。",
        status="open",
        source_url=source_url,
        source_quote=line,
        detected_at=detected_at,
        last_checked_at=detected_at,
    )
