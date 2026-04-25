from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


MOCK_DIR = Path("resources/mock")


def read_text(name: str) -> str:
    return (MOCK_DIR / name).read_text(encoding="utf-8")


def read_json(name: str) -> Any:
    return json.loads((MOCK_DIR / name).read_text(encoding="utf-8"))


def enabled_sources(project_id: str = "pay_project") -> list[dict[str, Any]]:
    rows = read_json("sample_context_sources.json")
    return [row for row in rows if row.get("project_id") == project_id and row.get("enabled")]


def project_table() -> list[dict[str, Any]]:
    return read_json("sample_project_table.json")


def normalize_title(title: str) -> str:
    text = re.sub(r"[，。,.！!？?\s]", "", title)
    for word in ["补齐", "确认", "完成", "整理", "负责", "需要", "文档"]:
        text = text.replace(word, "")
    return text[:18]


def source_summary() -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in enabled_sources():
        counts[row["source_type"]] = counts.get(row["source_type"], 0) + 1
    return counts

