from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.adapters.bitable_adapter import FeishuBitableAdapter
from src.config.settings import FeishuSettings
from src.core.extractors import extract_meeting_notes
from src.core.run_log import write_run_log
from src.outputs.markdown_renderer import render_post_meeting_summary


@dataclass
class PostMeetingLocalResult:
    output_dir: Path
    files: list[Path]
    counts: dict[str, int]
    bitable_result: dict[str, Any] | None


def run_post_meeting_local(
    *,
    minutes_file: Path,
    project_id: str,
    output_dir: Path,
    source_url: str,
    write_bitable: bool,
    dry_run: bool,
) -> PostMeetingLocalResult:
    text = minutes_file.read_text(encoding="utf-8")
    now = datetime.now().isoformat(timespec="seconds")
    result = extract_meeting_notes(text, project_id=project_id, source_url=source_url, detected_at=now)
    payload = result.to_jsonable()

    output_dir.mkdir(parents=True, exist_ok=True)
    files = [
        _write_json(output_dir / "action_items.json", payload["action_items"]),
        _write_json(output_dir / "decisions.json", payload["decisions"]),
        _write_json(output_dir / "risks.json", payload["risks"]),
    ]
    summary_path = output_dir / "post_meeting_summary.md"
    summary_path.write_text(render_post_meeting_summary(result), encoding="utf-8")
    files.append(summary_path)

    bitable_result = None
    if write_bitable:
        adapter = FeishuBitableAdapter(FeishuSettings.from_env())
        bitable_result = adapter.write_all(payload, dry_run=dry_run)
        bitable_path = output_dir / "bitable_write_preview.json"
        bitable_path.write_text(json.dumps(bitable_result, ensure_ascii=False, indent=2), encoding="utf-8")
        files.append(bitable_path)

    run_log_path = write_run_log(
        workflow="post-meeting-local",
        mode="mock" if not source_url or source_url.startswith("mock://") else "feishu",
        inputs={"minutes_file": str(minutes_file), "project_id": project_id, "source_url": source_url},
        outputs={"counts": {"action_items": len(payload["action_items"]), "decisions": len(payload["decisions"]), "risks": len(payload["risks"])}, "files": [str(path) for path in files]},
        write_plan={"write_bitable": write_bitable, "dry_run": dry_run},
        actual_writes=bitable_result if bitable_result and not bitable_result.get("dry_run") else {},
    )
    files.append(run_log_path)

    return PostMeetingLocalResult(
        output_dir=output_dir,
        files=files,
        counts={
            "action_items": len(payload["action_items"]),
            "decisions": len(payload["decisions"]),
            "risks": len(payload["risks"]),
        },
        bitable_result=bitable_result,
    )


def _write_json(path: Path, data: Any) -> Path:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
