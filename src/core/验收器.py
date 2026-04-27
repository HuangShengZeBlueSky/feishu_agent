from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from src.workflows.mock_examples import run_all_mock


ROOT = Path(__file__).resolve().parents[2]
OPENCLAW = Path("C:/openclaw-npm/openclaw.cmd")
LARK_CLI = Path.home() / "AppData/Roaming/npm/lark-cli.cmd"
TEST_CHAT_ID = "oc_17a66849f49461ef2b6f42f89e0f48f4"


def run_xiaolongxia_acceptance(project_id: str = "pay_project") -> dict[str, Any]:
    mock = run_all_mock(project_id)
    mock_checks = _check_mock_outputs(mock["results"])
    openclaw_checks = _check_openclaw()
    lark_checks = _check_lark_cli()

    result = {
        "summary": _summary(mock_checks + openclaw_checks + lark_checks),
        "checks": {
            "mock业务链路": mock_checks,
            "OpenClaw飞书通道": openclaw_checks,
            "飞书CLI与skills": lark_checks,
        },
        "mock_output_file": mock["file"],
        "next_manual_test": {
            "where": "飞书测试群",
            "chat_id": TEST_CHAT_ID,
            "message": "@小龙虾项目上下文管家 请只回复：验收收到",
            "pass_standard": "Gateway 日志不再出现 not in groupAllowFrom，且群里收到模型回复。",
        },
    }
    _write_outputs(result)
    return result


def _check_mock_outputs(results: dict[str, Any]) -> list[dict[str, Any]]:
    context = results["0_context"]
    post = results["1_post_meeting"]
    pre = results["2_pre_meeting"]["card"]
    reconcile = results["3_reconcile"]
    risk = results["4_risk_weekly"]
    schedule = results["5_schedule"]
    document = results["6_document"]

    source_types = set(context["sources_count_by_type"])
    reconcile_summary = reconcile["summary"]

    return [
        _check("上下文清单覆盖至少 5 类来源", len(source_types) >= 5, f"当前来源类型：{sorted(source_types)}"),
        _check("会后闭环能抽取行动项/决策/风险", post["counts"]["action_items"] >= 3 and post["counts"]["decisions"] >= 1 and post["counts"]["risks"] >= 1, f"计数：{post['counts']}"),
        _check("会前背景卡片有历史决策、未完成事项、风险和 3 个确认问题", bool(pre["last_decisions"]) and bool(pre["unfinished_items"]) and bool(pre["risks"]) and len(pre["suggested_questions"]) >= 3, f"确认问题数：{len(pre['suggested_questions'])}"),
        _check("项目推进总表对账输出新增/更新/合并/关闭/人工确认 diff", all(key in reconcile_summary for key in ["新增", "更新", "合并", "关闭", "需要人工确认"]), f"diff 计数：{reconcile_summary}"),
        _check("风险巡检与周报洞察能识别风险", risk["risk_count"] >= 3, f"风险数：{risk['risk_count']}"),
        _check("角色忙闲模拟能给出候选会议时间", len(schedule["candidate_times"]) >= 1, f"候选时间：{schedule['candidate_times']}"),
        _check("文档生成先出预览，不直接创建真实文档", Path(document["file"]).exists(), f"预览文件：{document['file']}"),
    ]


def _check_openclaw() -> list[dict[str, Any]]:
    if not OPENCLAW.exists():
        return [_check("OpenClaw CLI 存在", False, str(OPENCLAW))]

    health = _run([str(OPENCLAW), "gateway", "health"], timeout=60)
    status = _run([str(OPENCLAW), "channels", "status", "--deep"], timeout=90)
    capabilities = _run([str(OPENCLAW), "channels", "capabilities", "--channel", "feishu"], timeout=120)
    models = _run([str(OPENCLAW), "models", "status", "--plain"], timeout=60)
    group_allow = _read_openclaw_group_allow()

    return [
        _check("OpenClaw Gateway 可达", "Gateway Health" in health["stdout"] and "OK" in health["stdout"], _brief(health)),
        _check("小龙虾飞书账号运行中", "main (小龙虾项目上下文管家)" in status["stdout"] and "running" in status["stdout"], _brief(status)),
        _check("OpenClaw 飞书能力探针通过", "Probe: ok" in capabilities["stdout"], _brief(capabilities)),
        _check("默认模型是火山 Ark Seed2.0 endpoint", "volcengine/ep-20260423222827-6lcn6" in models["stdout"], _brief(models)),
        _check("测试群已加入 OpenClaw 群白名单", TEST_CHAT_ID in group_allow, group_allow or "未读取到白名单"),
    ]


def _check_lark_cli() -> list[dict[str, Any]]:
    if not LARK_CLI.exists():
        return [_check("lark-cli 可执行文件存在", False, str(LARK_CLI))]

    version = _run([str(LARK_CLI), "--version"], timeout=30)
    doctor = _run([str(LARK_CLI), "doctor", "--offline"], timeout=60)
    config = _run([str(LARK_CLI), "config", "show"], timeout=60)

    doctor_data = _loads(doctor["stdout"])
    checks = doctor_data.get("checks", []) if isinstance(doctor_data, dict) else []
    passed = {item.get("name"): item.get("status") for item in checks if isinstance(item, dict)}

    return [
        _check("lark-cli 已安装但当前 PATH 需补充", version["returncode"] == 0, _brief(version)),
        _check("lark-cli 已绑定当前飞书应用", passed.get("config_file") == "pass" and passed.get("app_resolved") == "pass", _brief(config)),
        _check("用户身份 OAuth 尚未登录，不阻塞 bot MVP", passed.get("token_exists") == "fail", "需要读用户日历/个人妙记/个人任务时再做 auth login。"),
    ]


def _read_openclaw_group_allow() -> str:
    path = Path.home() / ".openclaw/openclaw.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return ""
    values = data.get("channels", {}).get("feishu", {}).get("groupAllowFrom", [])
    return ", ".join(str(item) for item in values)


def _run(command: list[str], *, timeout: int) -> dict[str, Any]:
    try:
        proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    except subprocess.TimeoutExpired as exc:
        return {"returncode": 124, "stdout": exc.stdout or "", "stderr": exc.stderr or "timeout"}


def _loads(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _check(name: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {"name": name, "passed": passed, "evidence": evidence}


def _summary(checks: list[dict[str, Any]]) -> dict[str, int]:
    passed = sum(1 for item in checks if item["passed"])
    return {"passed": passed, "failed": len(checks) - passed, "total": len(checks)}


def _brief(result: dict[str, Any], limit: int = 600) -> str:
    text = (result.get("stdout") or "") + ("\n" + result.get("stderr", "") if result.get("stderr") else "")
    return text.strip()[:limit]


def _write_outputs(result: dict[str, Any]) -> None:
    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "小龙虾验收结果.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 小龙虾验收结果",
        "",
        f"- 通过：{result['summary']['passed']}",
        f"- 失败：{result['summary']['failed']}",
        f"- 总数：{result['summary']['total']}",
        "",
    ]
    for group, checks in result["checks"].items():
        lines.extend([f"## {group}", ""])
        for item in checks:
            mark = "通过" if item["passed"] else "未通过"
            lines.append(f"- {mark}：{item['name']}")
            lines.append(f"  - 证据：{item['evidence']}")
        lines.append("")
    manual = result["next_manual_test"]
    lines.extend(
        [
            "## 下一步人工验收",
            "",
            f"- 位置：{manual['where']}",
            f"- 群 ID：`{manual['chat_id']}`",
            f"- 发送：`{manual['message']}`",
            f"- 通过标准：{manual['pass_standard']}",
            "",
        ]
    )
    (ROOT / "docs" / "小龙虾验收结果.md").write_text("\n".join(lines), encoding="utf-8")
