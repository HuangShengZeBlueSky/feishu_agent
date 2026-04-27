#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config.settings import load_local_env  # noqa: E402


def request(method: str, url: str, token: str, body: dict | None = None) -> dict:
    payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method=method, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", "replace")
        return json.loads(raw) if raw else {}


def main() -> int:
    load_local_env()
    base = os.environ.get("FEISHU_BASE_URL", "https://open.larksuite.com/open-apis").rstrip("/")
    app_id = os.environ["FEISHU_APP_ID"]
    app_secret = os.environ["FEISHU_APP_SECRET"]
    app_token = os.environ["FEISHU_BITABLE_APP_TOKEN"]
    table_id = os.environ["FEISHU_CONTEXT_TABLE_ID"]

    token_data = request("POST", f"{base}/auth/v3/tenant_access_token/internal", "", {"app_id": app_id, "app_secret": app_secret})
    token = token_data["tenant_access_token"]
    rows = json.loads((ROOT / "resources/mock/sample_context_sources.json").read_text(encoding="utf-8"))
    created = []
    for row in rows:
        fields = {key: ("true" if value is True else "false" if value is False else str(value)) for key, value in row.items()}
        data = request("POST", f"{base}/bitable/v1/apps/{app_token}/tables/{table_id}/records", token, {"fields": fields})
        if data.get("code") != 0:
            raise RuntimeError(data)
        created.append((data.get("data") or {}).get("record", {}).get("record_id"))
    result = {"ok": True, "count": len(created), "record_ids": created}
    out = ROOT / "output/上下文清单飞书同步结果.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

