#!/usr/bin/env python3
"""Probe Feishu/OpenClaw integration prerequisites without printing secrets.

Default mode is read-only. Set FEISHU_ENABLE_WRITES=1 to send messages or
create/update Bitable objects.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

try:
    from src.config.settings import load_local_env
except Exception:
    load_local_env = None

if load_local_env:
    load_local_env()


READ_ENV = {
    "chat_id": ["FEISHU_TEST_CHAT_ID", "FEISHU_CHAT_ID"],
    "doc_id": ["FEISHU_TEST_DOC_ID", "FEISHU_DOC_ID", "FEISHU_DOCUMENT_ID"],
    "task_guid": ["FEISHU_TEST_TASK_GUID", "FEISHU_TASK_GUID"],
    "calendar_id": ["FEISHU_TEST_CALENDAR_ID", "FEISHU_CALENDAR_ID"],
    "bitable_app_token": ["FEISHU_TEST_BITABLE_APP_TOKEN", "FEISHU_BITABLE_APP_TOKEN"],
    "bitable_table_id": ["FEISHU_TEST_BITABLE_TABLE_ID", "FEISHU_BITABLE_TABLE_ID"],
    "minute_token": ["FEISHU_TEST_MINUTE_TOKEN", "FEISHU_MEETING_MINUTE_TOKEN", "FEISHU_MINUTE_TOKEN"],
}


@dataclass
class ProbeResult:
    name: str
    status: str
    detail: str
    http_status: int | None = None
    code: int | None = None
    data: dict[str, Any] = field(default_factory=dict)


class FeishuClient:
    def __init__(self, base_url: str, app_id: str, app_secret: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = ""

    def tenant_token(self) -> dict[str, Any]:
        data = self.request(
            "POST",
            "/auth/v3/tenant_access_token/internal",
            body={"app_id": self.app_id, "app_secret": self.app_secret},
            auth=False,
        )
        token = data.get("tenant_access_token")
        if token:
            self.token = token
        return data

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        auth: bool = True,
        timeout: int = 20,
    ) -> dict[str, Any]:
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if auth:
            headers["Authorization"] = f"Bearer {self.token}"
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                data = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                data = {"raw": raw[:1000]}
            data["_http_status"] = exc.code
            return data
        except Exception as exc:  # Keep probes running; report the failure.
            return {"_exception": repr(exc)}


def first_env(names: list[str]) -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return ""


def summarize_response(name: str, data: dict[str, Any], ok_detail: str) -> ProbeResult:
    if "_exception" in data:
        return ProbeResult(name, "error", data["_exception"])
    code = data.get("code")
    http_status = data.get("_http_status")
    if code == 0:
        return ProbeResult(name, "ok", ok_detail, http_status=http_status, code=code)
    if http_status in (401, 403) or code in (99991663, 99991664, 99991668, 99991672):
        return ProbeResult(name, "permission_or_auth_blocked", data.get("msg", "permission/auth blocked"), http_status, code)
    if http_status == 404:
        return ProbeResult(name, "endpoint_or_object_missing", data.get("msg", "not found"), http_status, code)
    if code is not None or http_status is not None:
        return ProbeResult(name, "api_failed", data.get("msg", json.dumps(data, ensure_ascii=False)[:500]), http_status, code)
    return ProbeResult(name, "unknown", json.dumps(data, ensure_ascii=False)[:500])


def skip(name: str, detail: str) -> ProbeResult:
    return ProbeResult(name, "skipped", detail)


def send_message(client: FeishuClient, chat_id: str, msg_type: str, content: dict[str, Any]) -> dict[str, Any]:
    return client.request(
        "POST",
        "/im/v1/messages",
        query={"receive_id_type": "chat_id"},
        body={
            "receive_id": chat_id,
            "msg_type": msg_type,
            "content": json.dumps(content, ensure_ascii=False),
        },
    )


def card(title: str, body: str, template: str) -> dict[str, Any]:
    return {
        "config": {"wide_screen_mode": True},
        "header": {"template": template, "title": {"tag": "plain_text", "content": title}},
        "elements": [{"tag": "markdown", "content": body}],
    }


def run(args: argparse.Namespace) -> list[ProbeResult]:
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    base_url = os.environ.get("FEISHU_BASE_URL", "https://open.larksuite.com/open-apis")
    if not app_id or not app_secret:
        return [ProbeResult("auth.tenant_access_token", "error", "Missing FEISHU_APP_ID or FEISHU_APP_SECRET")]

    client = FeishuClient(base_url, app_id, app_secret)
    results: list[ProbeResult] = []

    token_data = client.tenant_token()
    token_ok = token_data.get("code") == 0 and bool(token_data.get("tenant_access_token"))
    results.append(
        ProbeResult(
            "auth.tenant_access_token",
            "ok" if token_ok else "api_failed",
            f"token_present={bool(token_data.get('tenant_access_token'))}; expire={token_data.get('expire')}; base={base_url}",
            code=token_data.get("code"),
        )
    )
    if not token_ok:
        return results

    env = {key: first_env(names) for key, names in READ_ENV.items()}
    writes = args.enable_writes or os.environ.get("FEISHU_ENABLE_WRITES") == "1"
    card_push = writes and (args.enable_card_push or os.environ.get("FEISHU_ENABLE_CARD_PUSH") == "1")

    results.append(summarize_response("bot.info", client.request("GET", "/bot/v3/info"), "bot info readable"))

    if env["chat_id"]:
        data = client.request(
            "GET",
            "/im/v1/messages",
            query={"container_id_type": "chat", "container_id": env["chat_id"], "page_size": 5},
        )
        results.append(summarize_response("im.messages.read", data, "recent chat messages readable"))
        if writes:
            text = f"OpenClaw/Feishu probe text message at {time.strftime('%Y-%m-%d %H:%M:%S')}"
            results.append(summarize_response("im.message.send_text", send_message(client, env["chat_id"], "text", {"text": text}), "text sent"))
        else:
            results.append(skip("im.message.send_text", "Set FEISHU_ENABLE_WRITES=1 and FEISHU_TEST_CHAT_ID to send"))
        if card_push:
            cards = [
                ("im.card.pre_meeting", "OpenClaw 会前卡片测试", "目标：确认议程、材料、风险点。", "blue"),
                ("im.card.post_meeting", "OpenClaw 会后卡片测试", "结论：沉淀纪要、行动项、负责人。", "green"),
                ("im.card.risk", "OpenClaw 风险卡片测试", "风险：需要人工确认后再执行写操作。", "red"),
            ]
            for probe_name, title, body, template in cards:
                results.append(summarize_response(probe_name, send_message(client, env["chat_id"], "interactive", card(title, body, template)), "card sent"))
        else:
            results.append(skip("im.cards.push", "Set FEISHU_ENABLE_WRITES=1, FEISHU_ENABLE_CARD_PUSH=1, and FEISHU_TEST_CHAT_ID"))
    else:
        results.append(skip("im.messages.read", "Missing FEISHU_TEST_CHAT_ID or FEISHU_CHAT_ID"))
        results.append(skip("im.cards.push", "Missing FEISHU_TEST_CHAT_ID or FEISHU_CHAT_ID"))

    if env["doc_id"]:
        data = client.request("GET", f"/docx/v1/documents/{env['doc_id']}/raw_content")
        results.append(summarize_response("docx.raw_content.read", data, "document raw content readable"))
    else:
        results.append(skip("docx.raw_content.read", "Missing FEISHU_TEST_DOC_ID or FEISHU_DOC_ID"))

    if env["task_guid"]:
        data = client.request("GET", f"/task/v2/tasks/{env['task_guid']}", query={"user_id_type": "open_id"})
        results.append(summarize_response("task.get", data, "task readable"))
    else:
        results.append(skip("task.get", "Missing FEISHU_TEST_TASK_GUID or FEISHU_TASK_GUID"))

    if env["calendar_id"]:
        data = client.request("GET", f"/calendar/v4/calendars/{env['calendar_id']}", query={"user_id_type": "open_id"})
        results.append(summarize_response("calendar.get", data, "calendar readable"))
    else:
        data = client.request("GET", "/calendar/v4/calendars", query={"page_size": 50})
        results.append(summarize_response("calendar.list", data, "calendar list readable"))

    app_token = env["bitable_app_token"]
    table_id = env["bitable_table_id"]
    if app_token:
        tables = client.request("GET", f"/bitable/v1/apps/{app_token}/tables", query={"page_size": 20})
        results.append(summarize_response("bitable.tables.list", tables, "bitable tables readable"))
    else:
        results.append(skip("bitable.tables.list", "Missing FEISHU_TEST_BITABLE_APP_TOKEN or FEISHU_BITABLE_APP_TOKEN"))

    if writes:
        if not app_token:
            created = client.request("POST", "/bitable/v1/apps", body={"name": f"openclaw_probe_{int(time.time())}"})
            results.append(summarize_response("bitable.app.create", created, "bitable app created"))
            app_token = (((created.get("data") or {}).get("app") or {}).get("app_token") or (created.get("data") or {}).get("app_token") or "")
        if app_token and not table_id:
            table_body = {
                "table": {
                    "name": "OpenClawProbe",
                    "default_view_name": "Grid",
                    "fields": [
                        {"field_name": "状态", "type": 1},
                        {"field_name": "说明", "type": 1},
                    ],
                }
            }
            created_table = client.request("POST", f"/bitable/v1/apps/{app_token}/tables", body=table_body)
            results.append(summarize_response("bitable.table.create", created_table, "table created"))
            table_id = (((created_table.get("data") or {}).get("table") or {}).get("table_id") or (created_table.get("data") or {}).get("table_id") or "")
        if app_token and table_id:
            record = client.request(
                "POST",
                f"/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                body={"fields": {"状态": "待确认", "说明": "OpenClaw Feishu probe record"}},
            )
            results.append(summarize_response("bitable.record.create", record, "record created"))
            record_id = (((record.get("data") or {}).get("record") or {}).get("record_id") or "")
            if record_id:
                updated = client.request(
                    "PUT",
                    f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
                    body={"fields": {"状态": "已验证", "说明": "OpenClaw Feishu probe record updated"}},
                )
                results.append(summarize_response("bitable.record.update_status", updated, "record status updated"))
    else:
        results.append(skip("bitable.write_flow", "Set FEISHU_ENABLE_WRITES=1 to create app/table/record/update status"))

    if env["minute_token"]:
        minute = client.request("GET", f"/minutes/v1/minutes/{env['minute_token']}", query={"user_id_type": "open_id"})
        transcript = client.request("GET", f"/minutes/v1/minutes/{env['minute_token']}/transcript", query={"user_id_type": "open_id"})
        results.append(summarize_response("minutes.info.read", minute, "minute metadata readable"))
        results.append(summarize_response("minutes.transcript.read", transcript, "minute transcript readable"))
    else:
        results.append(skip("minutes.info.read", "Missing FEISHU_TEST_MINUTE_TOKEN or FEISHU_MEETING_MINUTE_TOKEN"))
        results.append(skip("minutes.transcript.read", "Missing FEISHU_TEST_MINUTE_TOKEN or FEISHU_MEETING_MINUTE_TOKEN"))

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Feishu API capabilities for OpenClaw integration.")
    parser.add_argument("--enable-writes", action="store_true", help="Enable write probes. Same as FEISHU_ENABLE_WRITES=1.")
    parser.add_argument("--enable-card-push", action="store_true", help="Send pre/post/risk interactive cards.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args()

    results = run(args)
    if args.json:
        print(json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=2))
    else:
        for item in results:
            bits = [item.name, item.status, item.detail]
            if item.http_status is not None:
                bits.append(f"http={item.http_status}")
            if item.code is not None:
                bits.append(f"code={item.code}")
            print(" | ".join(bits))
    return 0 if all(r.status in {"ok", "skipped"} for r in results) else 2


if __name__ == "__main__":
    sys.exit(main())
