from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from src.workflows.real_examples import context_overview_real


ROOT = Path(__file__).resolve().parents[2]
OPENCLAW = Path("C:/openclaw-npm/openclaw.cmd")
LARK_CLI = Path.home() / "AppData/Roaming/npm/lark-cli.cmd"
TEST_CHAT_ID = "oc_17a66849f49461ef2b6f42f89e0f48f4"
EXPECTED_OPENCLAW_MODEL = "volcengine/ep-20260423222827-6lcn6"


def run_xiaolongxia_acceptance(project_id: str = "pay_project") -> dict[str, Any]:
    real_context = context_overview_real(project_id)
    real_checks = _check_real_outputs(real_context)
    openclaw_checks = _check_openclaw()
    lark_checks = _check_lark_cli()

    result = {
        "summary": _summary(real_checks + openclaw_checks + lark_checks),
        "checks": {
            "真实业务链路": real_checks,
            "OpenClaw飞书通道": openclaw_checks,
            "飞书CLI与skills": lark_checks,
        },
        "real_context_run_log": real_context["run_log"],
        "next_manual_test": {
            "where": "飞书测试群",
            "chat_id": TEST_CHAT_ID,
            "message": "@会议 现在支付项目整体状态怎么样？",
            "pass_standard": "Gateway 日志不再出现 not in groupAllowFrom，且群里收到模型回复。",
        },
    }
    _write_outputs(result)
    return result


def _check_real_outputs(context: dict[str, Any]) -> list[dict[str, Any]]:
    source_urls = [str(item.get("source_url", "")) for item in context.get("sources", [])]
    counts = context.get("counts", {})
    return [
        _check("真实上下文不含 mock URL", all(not url.startswith("mock://") for url in source_urls), f"来源：{source_urls}"),
        _check("真实 Base 有行动项", int(counts.get("action_items", 0)) >= 1, f"计数：{counts}"),
        _check("真实 Base 有决策", int(counts.get("decisions", 0)) >= 1, f"计数：{counts}"),
        _check("真实 Base 有风险", int(counts.get("risks", 0)) >= 1, f"计数：{counts}"),
        _check("LLM 会后抽取文件存在", Path("output/real_action_items.json").exists() and Path("output/real_decisions.json").exists() and Path("output/real_risks.json").exists(), "output/real_* 抽取文件"),
        _check("LLM 会前卡片文件存在", Path("output/real_pre_meeting_card.json").exists(), "output/real_pre_meeting_card.json"),
        _check("LLM 对账 diff 文件存在", Path("output/real_project_reconcile_diff.json").exists(), "output/real_project_reconcile_diff.json"),
        _check("LLM 风险周报文件存在", Path("output/real_risk_weekly_insight.json").exists(), "output/real_risk_weekly_insight.json"),
        _check("LLM 文档预览文件存在", Path("output/real_document_preview.md").exists(), "output/real_document_preview.md"),
    ]


def _check_openclaw() -> list[dict[str, Any]]:
    if not OPENCLAW.exists():
        return [_check("OpenClaw CLI 存在", False, str(OPENCLAW))]

    gateway_auth = _openclaw_gateway_auth_args()
    health = _run([str(OPENCLAW), "gateway", *gateway_auth, "health"], timeout=60)
    status = _run([str(OPENCLAW), "channels", "status", "--deep"], timeout=90)
    capabilities = _run([str(OPENCLAW), "channels", "capabilities", "--channel", "feishu"], timeout=120)
    models = _run([str(OPENCLAW), "models", "status", "--plain"], timeout=60)
    group_allow = _read_openclaw_group_allow()

    return [
        _check("OpenClaw Gateway 可达", "Gateway Health" in health["stdout"] and "OK" in health["stdout"], _brief(health)),
        _check("小龙虾飞书账号运行中", ("main (会议)" in status["stdout"] or "main (小龙虾项目上下文管家)" in status["stdout"]) and "running" in status["stdout"], _brief(status)),
        _check("OpenClaw 飞书能力可用", _feishu_capability_available(capabilities), _brief(capabilities)),
        _check("默认模型是豆包 Seed 2.0 Pro Ark endpoint", EXPECTED_OPENCLAW_MODEL in models["stdout"], _brief(models)),
        _check("测试群已加入 OpenClaw 群白名单", TEST_CHAT_ID in group_allow, group_allow or "未读取到白名单"),
    ]


def _check_lark_cli() -> list[dict[str, Any]]:
    if not LARK_CLI.exists():
        return [_check("lark-cli 可执行文件存在", False, str(LARK_CLI))]

    version = _run([str(LARK_CLI), "--version"], timeout=30)
    doctor = _run([str(LARK_CLI), "doctor", "--offline"], timeout=60)
    config = _run([str(LARK_CLI), "config", "show"], timeout=60)
    auth = _run([str(LARK_CLI), "auth", "status"], timeout=60)

    doctor_data = _loads(doctor["stdout"])
    checks = doctor_data.get("checks", []) if isinstance(doctor_data, dict) else []
    passed = {item.get("name"): item.get("status") for item in checks if isinstance(item, dict)}
    auth_data = _loads(auth["stdout"])
    user_oauth_ok = isinstance(auth_data, dict) and auth_data.get("identity") == "user" and auth_data.get("tokenStatus") == "valid"

    return [
        _check("lark-cli 已安装但当前 PATH 需补充", version["returncode"] == 0, _brief(version)),
        _check("lark-cli 已绑定当前飞书应用", passed.get("config_file") == "pass" and passed.get("app_resolved") == "pass", _brief(config)),
        _check("用户身份 OAuth 已登录", user_oauth_ok, _brief(auth)),
    ]


def _read_openclaw_group_allow() -> str:
    path = Path.home() / ".openclaw/openclaw.json"
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return ""
    if TEST_CHAT_ID in text:
        return TEST_CHAT_ID
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return ""
    values = data.get("channels", {}).get("feishu", {}).get("groupAllowFrom", [])
    return ", ".join(str(item) for item in values)


def _openclaw_gateway_auth_args() -> list[str]:
    path = Path.home() / ".openclaw/openclaw.json"
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return []
    marker = '"password": "'
    start = text.find(marker)
    if start < 0:
        return []
    start += len(marker)
    end = text.find('"', start)
    if end < 0:
        return []
    return ["--password", text[start:end]]


def _feishu_capability_available(result: dict[str, Any]) -> bool:
    stdout = result.get("stdout") or ""
    if "Probe: ok" in stdout:
        return True
    return (
        ("Feishu main (会议)" in stdout or "Feishu main (小龙虾项目上下文管家)" in stdout)
        and "Actions:" in stdout
        and "send" in stdout
        and "read" in stdout
    )


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
    (ROOT / "docs" / "真实链路验收结果.md").write_text("\n".join(lines), encoding="utf-8")
