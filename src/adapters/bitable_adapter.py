from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from src.config.settings import FeishuSettings


class BitableWriteError(RuntimeError):
    pass


class FeishuBitableAdapter:
    def __init__(self, settings: FeishuSettings) -> None:
        self.settings = settings
        self._tenant_token = ""

    def validate(self) -> list[str]:
        return self.settings.missing_for_bitable_write()

    def write_all(self, payload: dict[str, list[dict[str, Any]]], *, dry_run: bool) -> dict[str, Any]:
        records = {
            "Project_Action_Items": payload.get("action_items", []),
            "Project_Decisions": payload.get("decisions", []),
            "Project_Risks": payload.get("risks", []),
        }
        if dry_run:
            return {"dry_run": True, "records": records}

        missing = self.validate()
        if missing:
            raise BitableWriteError("Missing env for Bitable write: " + ", ".join(missing))

        self._tenant_token = self._fetch_tenant_token()
        return {
            "dry_run": False,
            "Project_Action_Items": self._write_records(self.settings.action_table_id, records["Project_Action_Items"]),
            "Project_Decisions": self._write_records(self.settings.decision_table_id, records["Project_Decisions"]),
            "Project_Risks": self._write_records(self.settings.risk_table_id, records["Project_Risks"]),
        }

    def read_table(self, table_id: str, *, page_size: int = 100) -> list[dict[str, Any]]:
        missing = [
            name
            for name, value in {
                "FEISHU_APP_ID": self.settings.app_id,
                "FEISHU_APP_SECRET": self.settings.app_secret,
                "FEISHU_BITABLE_APP_TOKEN": self.settings.bitable_app_token,
            }.items()
            if not value
        ]
        if missing:
            raise BitableWriteError("Missing env for Bitable read: " + ", ".join(missing))
        if not self._tenant_token:
            self._tenant_token = self._fetch_tenant_token()
        records: list[dict[str, Any]] = []
        page_token = ""
        while True:
            suffix = f"?page_size={page_size}"
            if page_token:
                suffix += f"&page_token={page_token}"
            data = self._request("GET", f"/bitable/v1/apps/{self.settings.bitable_app_token}/tables/{table_id}/records{suffix}")
            if data.get("code") != 0:
                raise BitableWriteError(f"Failed to read Bitable records: {data}")
            body = data.get("data") or {}
            records.extend((body.get("items") or []))
            if not body.get("has_more"):
                break
            page_token = str(body.get("page_token") or "")
            if not page_token:
                break
        return records

    def write_records(self, table_id: str, rows: list[dict[str, Any]], *, dry_run: bool) -> dict[str, Any]:
        if dry_run:
            return {"dry_run": True, "records": rows}
        missing = [
            name
            for name, value in {
                "FEISHU_APP_ID": self.settings.app_id,
                "FEISHU_APP_SECRET": self.settings.app_secret,
                "FEISHU_BITABLE_APP_TOKEN": self.settings.bitable_app_token,
                "table_id": table_id,
            }.items()
            if not value
        ]
        if missing:
            raise BitableWriteError("Missing env for Bitable write: " + ", ".join(missing))
        if not self._tenant_token:
            self._tenant_token = self._fetch_tenant_token()
        return self._write_records(table_id, rows)

    def delete_records(self, table_id: str, record_ids: list[str], *, dry_run: bool) -> dict[str, Any]:
        if dry_run:
            return {"dry_run": True, "record_ids": record_ids}
        missing = [
            name
            for name, value in {
                "FEISHU_APP_ID": self.settings.app_id,
                "FEISHU_APP_SECRET": self.settings.app_secret,
                "FEISHU_BITABLE_APP_TOKEN": self.settings.bitable_app_token,
                "table_id": table_id,
            }.items()
            if not value
        ]
        if missing:
            raise BitableWriteError("Missing env for Bitable delete: " + ", ".join(missing))
        if not self._tenant_token:
            self._tenant_token = self._fetch_tenant_token()
        deleted = []
        for record_id in record_ids:
            data = self._request("DELETE", f"/bitable/v1/apps/{self.settings.bitable_app_token}/tables/{table_id}/records/{record_id}")
            if data.get("code") != 0:
                raise BitableWriteError(f"Failed to delete Bitable record: {data}")
            deleted.append(record_id)
        return {"count": len(deleted), "deleted": deleted}

    def _fetch_tenant_token(self) -> str:
        data = self._request(
            "POST",
            "/auth/v3/tenant_access_token/internal",
            body={"app_id": self.settings.app_id, "app_secret": self.settings.app_secret},
            auth=False,
        )
        if data.get("code") != 0 or not data.get("tenant_access_token"):
            raise BitableWriteError(f"Failed to get tenant token: {data}")
        return str(data["tenant_access_token"])

    def _write_records(self, table_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        allowed_fields = self._field_names(table_id)
        created = []
        for row in rows:
            data = self._request(
                "POST",
                f"/bitable/v1/apps/{self.settings.bitable_app_token}/tables/{table_id}/records",
                body={"fields": self._normalize_text_fields(row, allowed_fields)},
            )
            if data.get("code") != 0:
                raise BitableWriteError(f"Failed to write Bitable record: {data}")
            created.append(data.get("data", {}))
        return {"count": len(created), "created": created}

    def _field_names(self, table_id: str) -> set[str]:
        data = self._request("GET", f"/bitable/v1/apps/{self.settings.bitable_app_token}/tables/{table_id}/fields?page_size=100")
        if data.get("code") != 0:
            raise BitableWriteError(f"Failed to read Bitable fields: {data}")
        return {str(item.get("field_name")) for item in ((data.get("data") or {}).get("items") or []) if item.get("field_name")}

    def _normalize_text_fields(self, row: dict[str, Any], allowed_fields: set[str]) -> dict[str, str]:
        output: dict[str, str] = {}
        for key, value in row.items():
            if key not in allowed_fields:
                continue
            if value is None:
                output[key] = ""
            elif isinstance(value, bool):
                output[key] = "true" if value else "false"
            elif isinstance(value, (int, float)):
                output[key] = str(value)
            else:
                output[key] = str(value)
        return output

    def _request(self, method: str, path: str, *, body: dict[str, Any] | None = None, auth: bool = True) -> dict[str, Any]:
        url = self.settings.base_url + path
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if auth:
            headers["Authorization"] = f"Bearer {self._tenant_token}"
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                raw = response.read().decode("utf-8", "replace")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {"raw": raw[:1000]}
            payload["_http_status"] = exc.code
            return payload
