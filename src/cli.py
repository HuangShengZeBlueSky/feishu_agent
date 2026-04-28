from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.core.验收器 import run_xiaolongxia_acceptance
from src.workflows.real_examples import (
    context_overview_real,
    document_preview_real,
    post_meeting_real,
    pre_meeting_card_real,
    reconcile_project_table_real,
    risk_weekly_insight_real,
    run_all_real,
    schedule_meeting_real,
    seed_real_project,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="小龙虾项目上下文管家 CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    local = subparsers.add_parser("post-meeting-local", help="兼容入口：用 LLM 抽取本地真实会议文本")
    local.add_argument("--minutes-file", required=True, type=Path, help="本地会议文本路径")
    local.add_argument("--project-id", default="pay_project", help="项目唯一标识")
    local.add_argument("--source-url", default="", help="来源链接，可选")
    local.add_argument("--output-dir", default=Path("output"), type=Path, help="输出目录")
    local.add_argument("--write-bitable", action="store_true", help="写入或 dry-run 到飞书多维表格")
    local.add_argument("--dry-run", action="store_true", help="只打印将写入的数据，不调用飞书写接口")
    local.set_defaults(func=handle_post_meeting_local)

    seed = subparsers.add_parser("seed-real-project", help="向真实飞书多维表格写入最小项目数据，不读取 mock 文件")
    seed.add_argument("--project-id", default="pay_project")
    seed.add_argument("--dry-run", action="store_true")
    seed.set_defaults(func=lambda args: print_json(seed_real_project(args.project_id, dry_run=args.dry_run)))

    real_post = subparsers.add_parser("post-meeting-real", help="用 LLM 从真实会议文本抽取行动项、决策和风险")
    real_post.add_argument("--project-id", default="pay_project")
    real_post.add_argument("--minutes-file", type=Path, help="真实会议纪要文本；不传则使用已写入真实 Base 的 seed 输入")
    real_post.add_argument("--source-url", default="feishu-seed://minutes/pay-project-review-20260428")
    real_post.add_argument("--write-bitable", action="store_true")
    real_post.add_argument("--dry-run", action="store_true")
    real_post.set_defaults(func=lambda args: print_json(post_meeting_real(project_id=args.project_id, minutes_file=args.minutes_file, source_url=args.source_url, write_bitable=args.write_bitable, dry_run=args.dry_run)))

    context = subparsers.add_parser("context-overview", help="从真实飞书多维表格检查项目上下文清单和项目推进总表")
    context.add_argument("--project-id", default="pay_project")
    context.set_defaults(func=lambda args: print_json(context_overview_real(args.project_id)))

    pre = subparsers.add_parser("pre-meeting-card", help="用真实飞书数据 + LLM 生成会前背景知识卡片")
    pre.add_argument("--project-id", default="pay_project")
    pre.add_argument("--meeting-title", default="支付项目评审会")
    pre.set_defaults(func=lambda args: print_json(pre_meeting_card_real(args.project_id, args.meeting_title)))

    reconcile = subparsers.add_parser("reconcile-project-table", help="用真实飞书数据 + LLM 做项目推进总表对账")
    reconcile.add_argument("--project-id", default="pay_project")
    reconcile.set_defaults(func=lambda args: print_json(reconcile_project_table_real(args.project_id)))

    risk = subparsers.add_parser("risk-weekly-insight", help="用真实飞书数据 + LLM 做周期性风险巡检与周报洞察")
    risk.add_argument("--project-id", default="pay_project")
    risk.set_defaults(func=lambda args: print_json(risk_weekly_insight_real(args.project_id)))

    schedule_real = subparsers.add_parser("schedule-meeting", help="用真实飞书数据 + LLM 生成会议议程；缺日历授权时输出依赖缺口")
    schedule_real.add_argument("--project-id", default="pay_project")
    schedule_real.add_argument("--meeting-title", default="支付项目评审会")
    schedule_real.set_defaults(func=lambda args: print_json(schedule_meeting_real(args.project_id, args.meeting_title)))

    doc = subparsers.add_parser("document-preview", help="用真实飞书数据 + LLM 生成文档预览")
    doc.add_argument("--project-id", default="pay_project")
    doc.add_argument("--doc-type", default="post_meeting", choices=["post_meeting", "weekly"])
    doc.set_defaults(func=lambda args: print_json(document_preview_real(args.project_id, args.doc_type)))

    all_real = subparsers.add_parser("run-all-real", help="一次运行真实飞书数据 + LLM 主链路")
    all_real.add_argument("--project-id", default="pay_project")
    all_real.add_argument("--dry-run", action="store_true")
    all_real.set_defaults(func=lambda args: print_json(run_all_real(args.project_id, dry_run=args.dry_run)))

    acceptance = subparsers.add_parser("validate-xiaolongxia", help="验收真实业务链路、OpenClaw、飞书 CLI 能力")
    acceptance.add_argument("--project-id", default="pay_project")
    acceptance.set_defaults(func=lambda args: print_json(run_xiaolongxia_acceptance(args.project_id)))
    return parser


def handle_post_meeting_local(args: argparse.Namespace) -> int:
    result = post_meeting_real(
        project_id=args.project_id,
        minutes_file=args.minutes_file,
        source_url=args.source_url,
        write_bitable=args.write_bitable,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
    )
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
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
