#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sources.feishu_project import FeishuProjectStore  # noqa: E402


VERIFIED_CONTEXT_ROWS = [
    {
        "project_id": "pay_project",
        "source_name": "小龙虾真实项目背景文档 2026-04-28",
        "source_type": "doc",
        "source_url": "https://jcneyh7qlo8i.feishu.cn/docx/NdH6dEvIvoCatixwoLPcH7Vdnqb",
        "source_id": "NdH6dEvIvoCatixwoLPcH7Vdnqb",
        "priority": "high",
        "owner_text": "小龙虾项目上下文管家",
        "enabled": "true",
        "description": "真实飞书文档，已通过 docs +fetch 验证可读取。",
    },
    {
        "project_id": "pay_project",
        "source_name": "小龙虾真实任务验证：确认验收材料负责人",
        "source_type": "task",
        "source_url": "https://applink.feishu.cn/client/todo/detail?guid=94cd2aa5-5f32-48e7-ad19-f558f9613d8b",
        "source_id": "94cd2aa5-5f32-48e7-ad19-f558f9613d8b",
        "priority": "high",
        "owner_text": "小龙虾项目上下文管家",
        "enabled": "true",
        "description": "真实飞书任务，创建成功并返回 GUID。",
    },
    {
        "project_id": "pay_project",
        "source_name": "小龙虾真实日程验证：支付项目评审会",
        "source_type": "calendar",
        "source_url": "https://applink.feishu.cn/client/calendar/event/detail?calendarId=7633647026253138876&key=014485ef-b874-4d42-abd0-07587275b744&originalTime=0&startTime=1777428000",
        "source_id": "014485ef-b874-4d42-abd0-07587275b744_0",
        "priority": "medium",
        "owner_text": "小龙虾项目上下文管家",
        "enabled": "true",
        "description": "真实飞书日程，已通过 calendar +agenda 验证可读取。",
    },
]


def main() -> int:
    result = FeishuProjectStore().replace_context_sources_by_ids(VERIFIED_CONTEXT_ROWS, dry_run=False)
    out = ROOT / "output" / "真实飞书资源登记结果.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
