from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.workflows.mock_examples import (
    context_overview,
    document_preview,
    pre_meeting_card,
    reconcile_project_table,
    risk_and_weekly_insight,
    run_all_mock,
    schedule_meeting_mock,
    simulate_agents_meeting,
)
from src.core.验收器 import run_xiaolongxia_acceptance
from src.workflows.post_meeting_local import run_post_meeting_local


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="小龙虾项目上下文管家 CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    local = subparsers.add_parser("post-meeting-local", help="从本地会议文本抽取行动项、决策和风险")
    local.add_argument("--minutes-file", default=Path("resources/mock/sample_minutes.txt"), type=Path, help="本地会议文本路径")
    local.add_argument("--project-id", default="pay_project", help="项目唯一标识")
    local.add_argument("--source-url", default="", help="来源链接，可选")
    local.add_argument("--output-dir", default=Path("output"), type=Path, help="输出目录")
    local.add_argument("--write-bitable", action="store_true", help="写入或 dry-run 到飞书多维表格")
    local.add_argument("--dry-run", action="store_true", help="只打印将写入的数据，不调用飞书写接口")
    local.set_defaults(func=handle_post_meeting_local)

    context = subparsers.add_parser("context-overview", help="检查项目上下文清单和项目推进总表")
    context.add_argument("--project-id", default="pay_project")
    context.set_defaults(func=lambda args: print_json(context_overview(args.project_id)))

    pre = subparsers.add_parser("pre-meeting-card", help="生成会前背景知识卡片")
    pre.add_argument("--project-id", default="pay_project")
    pre.add_argument("--meeting-title", default="支付项目评审会")
    pre.set_defaults(func=lambda args: print_json(pre_meeting_card(args.project_id, args.meeting_title)))

    reconcile = subparsers.add_parser("reconcile-project-table", help="项目推进总表维护与自动对账")
    reconcile.add_argument("--project-id", default="pay_project")
    reconcile.set_defaults(func=lambda args: print_json(reconcile_project_table(args.project_id)))

    risk = subparsers.add_parser("risk-weekly-insight", help="周期性风险巡检与周报洞察")
    risk.add_argument("--project-id", default="pay_project")
    risk.set_defaults(func=lambda args: print_json(risk_and_weekly_insight(args.project_id)))

    schedule = subparsers.add_parser("schedule-meeting-mock", help="自动约会与角色忙闲模拟")
    schedule.add_argument("--project-id", default="pay_project")
    schedule.add_argument("--meeting-title", default="支付项目评审会")
    schedule.set_defaults(func=lambda args: print_json(schedule_meeting_mock(args.project_id, args.meeting_title)))

    agents = subparsers.add_parser("simulate-agents-meeting", help="多智能体角色开会模拟")
    agents.add_argument("--project-id", default="pay_project")
    agents.add_argument("--meeting-title", default="支付项目评审会")
    agents.set_defaults(func=lambda args: print_json(simulate_agents_meeting(args.project_id, args.meeting_title)))

    doc = subparsers.add_parser("document-preview", help="文档生成、更新与知识沉淀预览")
    doc.add_argument("--project-id", default="pay_project")
    doc.add_argument("--doc-type", default="post_meeting", choices=["post_meeting", "weekly"])
    doc.set_defaults(func=lambda args: print_json(document_preview(args.project_id, args.doc_type)))

    all_mock = subparsers.add_parser("run-all-mock", help="一次运行 6 个 mock 例子")
    all_mock.add_argument("--project-id", default="pay_project")
    all_mock.set_defaults(func=lambda args: print_json(run_all_mock(args.project_id)))

    acceptance = subparsers.add_parser("validate-xiaolongxia", help="验收小龙虾当前 mock、OpenClaw、飞书 CLI 能力")
    acceptance.add_argument("--project-id", default="pay_project")
    acceptance.set_defaults(func=lambda args: print_json(run_xiaolongxia_acceptance(args.project_id)))
    return parser


def handle_post_meeting_local(args: argparse.Namespace) -> int:
    result = run_post_meeting_local(
        minutes_file=args.minutes_file,
        project_id=args.project_id,
        output_dir=args.output_dir,
        source_url=args.source_url,
        write_bitable=args.write_bitable,
        dry_run=args.dry_run,
    )
    print(
        json.dumps(
            {
                "ok": True,
                "output_dir": str(result.output_dir),
                "files": [str(path) for path in result.files],
                "counts": result.counts,
                "bitable": result.bitable_result,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def print_json(data: object) -> int:
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
