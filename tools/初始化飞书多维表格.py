#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config.settings import load_local_env  # noqa: E402


LOCAL_ENV = ROOT / "resources" / "config" / "本地飞书密钥.env"
OUTPUT = ROOT / "output" / "飞书多维表格初始化结果.json"

TABLES = {
    "FEISHU_CONTEXT_TABLE_ID": {
        "name": "Project_Context_Sources",
        "fields": ["project_id", "source_name", "source_type", "source_url", "source_id", "priority", "owner_text", "enabled", "description"],
    },
    "FEISHU_ACTION_TABLE_ID": {
        "name": "Project_Action_Items",
        "fields": [
            "project_id",
            "title",
            "description",
            "owner_text",
            "owner_user_id",
            "due_date",
            "priority",
            "status",
            "risk_level",
            "blocker_reason",
            "source_type",
            "source_url",
            "source_quote",
            "task_url",
            "created_by_ai",
            "confidence",
        ],
    },
    "FEISHU_DECISION_TABLE_ID": {
        "name": "Project_Decisions",
        "fields": ["project_id", "meeting_title", "meeting_time", "decision", "rationale", "participants", "source_url", "source_quote", "confidence"],
    },
    "FEISHU_RISK_TABLE_ID": {
        "name": "Project_Risks",
        "fields": [
            "project_id",
            "risk_title",
            "risk_description",
            "risk_level",
            "impact",
            "owner_text",
            "owner_user_id",
            "suggested_action",
            "status",
            "source_url",
            "source_quote",
            "detected_at",
            "last_checked_at",
        ],
    },
}


class Client:
    def __init__(self) -> None:
        load_local_env()
        self.base = os.environ.get("FEISHU_BASE_URL", "https://open.larksuite.com/open-apis").rstrip("/")
        self.app_id = os.environ.get("FEISHU_APP_ID", "")
        self.app_secret = os.environ.get("FEISHU_APP_SECRET", "")
        if not self.app_id or not self.app_secret:
            raise RuntimeError("缺 FEISHU_APP_ID 或 FEISHU_APP_SECRET")
        self.token = self._tenant_token()

    def _tenant_token(self) -> str:
        data = self.request(
            "POST",
            "/auth/v3/tenant_access_token/internal",
            body={"app_id": self.app_id, "app_secret": self.app_secret},
            auth=False,
        )
        token = data.get("tenant_access_token")
        if data.get("code") != 0 or not token:
            raise RuntimeError(f"获取 tenant_access_token 失败: {data}")
        return str(token)

    def request(self, method: str, path: str, *, body: dict[str, Any] | None = None, auth: bool = True) -> dict[str, Any]:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if auth:
            headers["Authorization"] = f"Bearer {self.token}"
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=payload, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", "replace")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                data = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                data = {"raw": raw}
            data["_http_status"] = exc.code
            return data


def main() -> int:
    client = Client()
    app_token = os.environ.get("FEISHU_BITABLE_APP_TOKEN", "")
    created_app = False
    if not app_token:
        app = client.request("POST", "/bitable/v1/apps", body={"name": f"小龙虾项目上下文管家_{int(time.time())}"})
        if app.get("code") != 0:
            raise RuntimeError(f"创建多维表格 app 失败: {app}")
        app_token = (((app.get("data") or {}).get("app") or {}).get("app_token") or (app.get("data") or {}).get("app_token") or "")
        created_app = True
    if not app_token:
        raise RuntimeError("没有拿到 FEISHU_BITABLE_APP_TOKEN")

    existing = client.request("GET", f"/bitable/v1/apps/{app_token}/tables")
    if existing.get("code") != 0:
        raise RuntimeError(f"读取表列表失败: {existing}")
    tables = {item.get("name"): item.get("table_id") for item in ((existing.get("data") or {}).get("items") or [])}

    env_updates = {"FEISHU_BITABLE_APP_TOKEN": app_token}
    created_tables = []
    reused_tables = []
    for env_name, spec in TABLES.items():
        table_id = os.environ.get(env_name, "") or tables.get(spec["name"])
        if table_id:
            env_updates[env_name] = table_id
            reused_tables.append({"name": spec["name"], "table_id": table_id})
            continue
        body = {
            "table": {
                "name": spec["name"],
                "default_view_name": "Grid",
                "fields": [{"field_name": field, "type": 1} for field in spec["fields"]],
            }
        }
        created = client.request("POST", f"/bitable/v1/apps/{app_token}/tables", body=body)
        if created.get("code") != 0:
            raise RuntimeError(f"创建表 {spec['name']} 失败: {created}")
        table_id = (((created.get("data") or {}).get("table") or {}).get("table_id") or (created.get("data") or {}).get("table_id") or "")
        env_updates[env_name] = table_id
        created_tables.append({"name": spec["name"], "table_id": table_id})

    update_env_file(env_updates)
    result = {
        "ok": True,
        "created_app": created_app,
        "app_token_present": bool(app_token),
        "created_tables": created_tables,
        "reused_tables": reused_tables,
        "env_file": str(LOCAL_ENV),
        "note": "真实 token/table_id 已写入本地忽略配置文件，未写入仓库文档。",
    }
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def update_env_file(updates: dict[str, str]) -> None:
    LOCAL_ENV.parent.mkdir(parents=True, exist_ok=True)
    lines = LOCAL_ENV.read_text(encoding="utf-8-sig").splitlines() if LOCAL_ENV.exists() else []
    current: dict[str, str] = {}
    order: list[str] = []
    for line in lines:
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        current[key] = value
        order.append(key)
    current.update({k: v for k, v in updates.items() if v})
    for key in updates:
        if key not in order:
            order.append(key)
    output = [f"{key}={current[key]}" for key in order if key in current]
    LOCAL_ENV.write_text("\n".join(output) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
