from __future__ import annotations

from src.core.extractors import ExtractionResult


def render_post_meeting_summary(result: ExtractionResult) -> str:
    lines = [
        "# 会后闭环摘要",
        "",
        "## 识别结果",
        "",
        f"- 决策：{len(result.decisions)} 条",
        f"- 行动项：{len(result.action_items)} 条",
        f"- 风险：{len(result.risks)} 条",
        "",
        "## 需要人工确认",
        "",
    ]
    needs_review = []
    for item in result.action_items:
        if not item.owner:
            needs_review.append(f"- 行动项缺负责人：{item.title}")
        if not item.due_date:
            needs_review.append(f"- 行动项缺截止时间：{item.title}")
    if not needs_review:
        needs_review.append("- 暂无明显缺口。")
    lines.extend(needs_review)

    lines.extend(["", "## 来源证据", ""])
    for item in result.action_items:
        lines.append(f"- 行动项：{item.source_quote}")
    for item in result.decisions:
        lines.append(f"- 决策：{item.source_quote}")
    for item in result.risks:
        lines.append(f"- 风险：{item.source_quote}")
    lines.append("")
    return "\n".join(lines)

