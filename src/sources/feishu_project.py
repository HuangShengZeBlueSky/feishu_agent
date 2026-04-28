from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.adapters.bitable_adapter import FeishuBitableAdapter
from src.config.settings import FeishuSettings
from src.core.extractors import ExtractionResult


REAL_SEED_CONTEXT = [
    {
        "project_id": "pay_project",
        "source_name": "支付项目真实种子会议纪要",
        "source_type": "minutes",
        "source_url": "feishu-seed://minutes/pay-project-review-20260428",
        "source_id": "pay-project-review-20260428",
        "priority": "high",
        "owner_text": "项目经理",
        "enabled": "true",
        "description": "由脚本写入真实飞书多维表格的项目会议输入，用于替代本地 mock 文件。",
    },
    {
        "project_id": "pay_project",
        "source_name": "支付项目推进总表",
        "source_type": "bitable",
        "source_url": "feishu-bitable://Project_Action_Items",
        "source_id": "Project_Action_Items",
        "priority": "high",
        "owner_text": "项目经理",
        "enabled": "true",
        "description": "真实飞书多维表格中的行动项、决策、风险数据。",
    },
]


REAL_SEED_MINUTES = """支付项目评审会真实种子纪要：
1. 本次确定支付接口字段本周冻结，不再临时修改。
2. 后端小王需要在本周五前补齐错误码文档，并同步给前端和测试。
3. 前端小李在错误码文档完成后一天内完成接口联调。
4. 测试反馈联调环境今天仍不稳定，可能影响下周客户验收。
5. 验收材料负责人尚未明确，需要产品今天确认。
"""


REAL_SEED_ACTIONS = [
    {
        "project_id": "pay_project",
        "title": "补齐错误码文档",
        "description": "后端小王需要在本周五前补齐错误码文档，并同步给前端和测试。",
        "owner_text": "小王",
        "owner_user_id": "",
        "due_date": "本周五",
        "priority": "P1",
        "status": "doing",
        "risk_level": "medium",
        "blocker_reason": "",
        "source_type": "seed",
        "source_url": "feishu-seed://minutes/pay-project-review-20260428",
        "source_quote": "后端小王需要在本周五前补齐错误码文档，并同步给前端和测试。",
        "task_url": "",
        "created_by_ai": "false",
        "confidence": "0.95",
    },
    {
        "project_id": "pay_project",
        "title": "确认验收材料负责人",
        "description": "验收材料负责人尚未明确，需要产品今天确认。",
        "owner_text": "产品",
        "owner_user_id": "",
        "due_date": "今天",
        "priority": "P0",
        "status": "todo",
        "risk_level": "high",
        "blocker_reason": "负责人尚未明确",
        "source_type": "seed",
        "source_url": "feishu-seed://minutes/pay-project-review-20260428",
        "source_quote": "验收材料负责人尚未明确，需要产品今天确认。",
        "task_url": "",
        "created_by_ai": "false",
        "confidence": "0.95",
    },
]


class FeishuProjectStore:
    def __init__(self, settings: FeishuSettings | None = None) -> None:
        self.settings = settings or FeishuSettings.from_env()
        self.adapter = FeishuBitableAdapter(self.settings)

    def read_context_sources(self, project_id: str) -> list[dict[str, Any]]:
        return [row for row in self._read_fields(self.settings.context_table_id) if row.get("project_id") == project_id and str(row.get("enabled", "")).lower() == "true"]

    def read_action_items(self, project_id: str) -> list[dict[str, Any]]:
        return [row for row in self._read_fields(self.settings.action_table_id) if row.get("project_id") == project_id]

    def read_decisions(self, project_id: str) -> list[dict[str, Any]]:
        return [row for row in self._read_fields(self.settings.decision_table_id) if row.get("project_id") == project_id]

    def read_risks(self, project_id: str) -> list[dict[str, Any]]:
        return [row for row in self._read_fields(self.settings.risk_table_id) if row.get("project_id") == project_id]

    def write_context_sources(self, rows: list[dict[str, Any]], *, dry_run: bool) -> dict[str, Any]:
        return self.adapter.write_records(self.settings.context_table_id, rows, dry_run=dry_run)

    def replace_context_sources_by_ids(self, rows: list[dict[str, Any]], *, dry_run: bool) -> dict[str, Any]:
        source_ids = {str(row.get("source_id")) for row in rows if row.get("source_id")}
        existing = self.adapter.read_table(self.settings.context_table_id) if not dry_run else []
        delete_ids = [
            str(record.get("record_id"))
            for record in existing
            if str((record.get("fields") or {}).get("source_id")) in source_ids and record.get("record_id")
        ]
        deleted = self.adapter.delete_records(self.settings.context_table_id, delete_ids, dry_run=dry_run) if delete_ids else {"count": 0, "deleted": []}
        written = self.write_context_sources(rows, dry_run=dry_run)
        return {"deleted": deleted, "written": written}

    def write_extraction(self, result: ExtractionResult, *, dry_run: bool) -> dict[str, Any]:
        payload = {
            "action_items": [asdict(item) for item in result.action_items],
            "decisions": [asdict(item) for item in result.decisions],
            "risks": [asdict(item) for item in result.risks],
        }
        return self.adapter.write_all(payload, dry_run=dry_run)

    def seed_real_project(self, project_id: str, *, dry_run: bool) -> dict[str, Any]:
        context = self.read_context_sources(project_id) if not dry_run else []
        actions = self.read_action_items(project_id) if not dry_run else []
        context_to_write = [] if context else REAL_SEED_CONTEXT
        actions_to_write = [] if actions else REAL_SEED_ACTIONS
        result = {
            "context": self.write_context_sources(context_to_write, dry_run=dry_run) if context_to_write else {"count": 0, "reason": "已有真实上下文来源"},
            "actions": self.adapter.write_records(self.settings.action_table_id, actions_to_write, dry_run=dry_run) if actions_to_write else {"count": 0, "reason": "已有真实行动项"},
            "seed_minutes_text": REAL_SEED_MINUTES,
        }
        return result

    def _read_fields(self, table_id: str) -> list[dict[str, Any]]:
        records = self.adapter.read_table(table_id)
        return [dict(record.get("fields") or {}) for record in records]
