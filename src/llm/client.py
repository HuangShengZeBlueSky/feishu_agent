from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from src.config.settings import LlmSettings


class LlmError(RuntimeError):
    pass


class JsonLlmClient:
    def __init__(self, settings: LlmSettings | None = None) -> None:
        self.settings = settings or LlmSettings.from_env()
        missing = self.settings.missing()
        if missing:
            raise LlmError("缺少 LLM 配置: " + ", ".join(missing))

    def complete_json(self, *, system: str, user: str, temperature: float = 0.1) -> dict[str, Any]:
        payload = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        try:
            data = self._post("/chat/completions", payload)
        except LlmError as exc:
            if "response_format" not in str(exc):
                raise
            payload.pop("response_format", None)
            data = self._post("/chat/completions", payload)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmError(f"LLM 返回格式异常: {data}") from exc
        try:
            return _parse_json_object(content)
        except json.JSONDecodeError as exc:
            raise LlmError(f"LLM 未返回合法 JSON: {content[:1000]}") from exc

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            self.settings.base_url + path,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                raw = response.read().decode("utf-8", "replace")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            raise LlmError(f"LLM HTTP {exc.code}: {raw[:1000]}") from exc
        except urllib.error.URLError as exc:
            raise LlmError(f"LLM 连接失败: {exc}") from exc


def _parse_json_object(content: str) -> dict[str, Any]:
    try:
        value = json.loads(content)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, flags=re.DOTALL)
    if match:
        value = json.loads(match.group(1))
        if isinstance(value, dict):
            return value
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        value = json.loads(content[start : end + 1])
        if isinstance(value, dict):
            return value
    raise json.JSONDecodeError("No JSON object found", content, 0)
