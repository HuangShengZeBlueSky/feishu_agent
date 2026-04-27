#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.验收器 import run_xiaolongxia_acceptance  # noqa: E402


def main() -> int:
    result = run_xiaolongxia_acceptance()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
