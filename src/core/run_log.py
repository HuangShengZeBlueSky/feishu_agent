from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def write_run_log(
    *,
    workflow: str,
    mode: str,
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    write_plan: dict[str, Any] | None = None,
    actual_writes: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    run_logs_dir: Path = Path("run_logs"),
) -> Path:
    run_logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = run_logs_dir / f"{timestamp}_{workflow}_{mode}.json"
    payload = {
        "workflow": workflow,
        "mode": mode,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "inputs": inputs,
        "outputs": outputs,
        "write_plan": write_plan or {},
        "actual_writes": actual_writes or {},
        "errors": errors or [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

