from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_local_env(path: str | Path = "resources/config/本地飞书密钥.env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def load_model_env(path: str | Path = "resources/config/本地模型secret.env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class FeishuSettings:
    app_id: str
    app_secret: str
    base_url: str
    bitable_app_token: str
    context_table_id: str
    action_table_id: str
    decision_table_id: str
    risk_table_id: str

    @classmethod
    def from_env(cls) -> "FeishuSettings":
        load_local_env()
        return cls(
            app_id=os.environ.get("FEISHU_APP_ID", ""),
            app_secret=os.environ.get("FEISHU_APP_SECRET", ""),
            base_url=os.environ.get("FEISHU_BASE_URL", "https://open.larksuite.com/open-apis").rstrip("/"),
            bitable_app_token=os.environ.get("FEISHU_BITABLE_APP_TOKEN", ""),
            context_table_id=os.environ.get("FEISHU_CONTEXT_TABLE_ID", ""),
            action_table_id=os.environ.get("FEISHU_ACTION_TABLE_ID", ""),
            decision_table_id=os.environ.get("FEISHU_DECISION_TABLE_ID", ""),
            risk_table_id=os.environ.get("FEISHU_RISK_TABLE_ID", ""),
        )

    def missing_for_bitable_write(self) -> list[str]:
        required = {
            "FEISHU_APP_ID": self.app_id,
            "FEISHU_APP_SECRET": self.app_secret,
            "FEISHU_BITABLE_APP_TOKEN": self.bitable_app_token,
            "FEISHU_ACTION_TABLE_ID": self.action_table_id,
            "FEISHU_DECISION_TABLE_ID": self.decision_table_id,
            "FEISHU_RISK_TABLE_ID": self.risk_table_id,
        }
        return [name for name, value in required.items() if not value]


@dataclass(frozen=True)
class LlmSettings:
    base_url: str
    api_key: str
    model: str

    @classmethod
    def from_env(cls) -> "LlmSettings":
        load_model_env()
        base_url = os.environ.get("ARK_BASE_URL") or os.environ.get("OPENAI_BASE_URL", "")
        api_key = os.environ.get("ARK_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        model = os.environ.get("ARK_MODEL") or os.environ.get("OPENAI_MODEL", "")
        return cls(base_url=base_url.rstrip("/"), api_key=api_key, model=model)

    def missing(self) -> list[str]:
        required = {
            "ARK_BASE_URL or OPENAI_BASE_URL": self.base_url,
            "ARK_API_KEY or OPENAI_API_KEY": self.api_key,
            "ARK_MODEL or OPENAI_MODEL": self.model,
        }
        return [name for name, value in required.items() if not value]
