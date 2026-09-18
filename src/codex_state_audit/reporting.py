"""JSON and Markdown report rendering for local audit results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import ValidationResult


TOOL_INFO = {
    "name": "codex-state-audit",
    "version": "0.1.0",
    "mode": "offline",
    "network_access": False,
}


def build_report(result: ValidationResult, *, fixture_name: str | None = None) -> dict[str, Any]:
    """Build a report that contains the redacted fixture, never the original."""

    return {
        "tool": TOOL_INFO,
        "scope": [
            "仅处理本地、用户自备的 JSON fixture",
            "292/312 只作为 unknown 标签",
            "不连接在线服务，不读取环境凭据",
        ],
        "fixture": {
            "name": Path(fixture_name).name if fixture_name else None,
            "redacted": True,
        },
        "validation": result.as_dict(),
        "redacted_fixture": result.redacted_fixture,
    }


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def _md_cell(value: Any) -> str:
    text = str(value).replace("|", "\\|").replace("\n", " ")
    return text


def render_markdown(report: dict[str, Any]) -> str:
    validation = report.get("validation", {})
    observations = validation.get("observations", {})
    lines = [
        "# Codex State Audit 离线报告",
        "",
        "> 本报告只描述本地 fixture 的结构性观察。它不证明任何在线服务的内部语义。",
        "",
        "## 范围",
        "",
        "- 运行模式：离线；不连接 ChatGPT/OpenAI。",
        "- 不代理、不拦截、不注入、不切换 IP，也不读取环境变量中的凭据。",
        "- 292/312 只作为 unknown 标签，不触发任何状态转换。",
        "",
        "## 校验结果",
        "",
        f"- 结构有效：{validation.get('valid')}",
        f"- 可安全分享：{validation.get('safe_to_share')}",
        f"- fixture：{report.get('fixture', {}).get('name')}",
        "",
        "## 观测字段",
        "",
        "| 字段 | 值 | 解释 |",
        "| --- | --- | --- |",
        f"| status_code | {_md_cell(observations.get('status_code'))} | "
        f"{_md_cell(observations.get('status_semantics'))} |",
        f"| current_turn_state | {_md_cell(observations.get('current_turn_state_present'))} | "
        f"{_md_cell(observations.get('current_turn_state_interpretation'))} |",
        f"| expires_at | {_md_cell(observations.get('expires_at_present'))} | "
        "只记录字段存在性；不推断服务器有效期 |",
        f"| declared_duration_seconds | "
        f"{_md_cell(observations.get('declared_duration_seconds'))} | fixture 时间算术 |",
        "",
        "## 错误",
        "",
    ]

    errors = validation.get("errors") or []
    lines.extend([f"- {error}" for error in errors] or ["- 无"])
    lines.extend(["", "## 警告", ""])
    warnings = validation.get("warnings") or []
    lines.extend([f"- {warning}" for warning in warnings] or ["- 无"])
    lines.extend(["", "## 敏感字段发现", ""])
    findings = validation.get("findings") or []
    if findings:
        lines.extend(
            f"- {item.get('path')}：{item.get('kind')}；{item.get('message')}"
            for item in findings
        )
    else:
        lines.append("- 未发现未脱敏的常见凭据格式。")

    lines.extend(["", "## 证据分层", ""])
    evidence = validation.get("evidence") or []
    if evidence:
        lines.extend(
            [
                "| claim | evidence_level | confidence |",
                "| --- | --- | --- |",
            ]
        )
        for row in evidence:
            lines.append(
                f"| {_md_cell(row.get('claim'))} | "
                f"{_md_cell(row.get('evidence_level'))} | "
                f"{_md_cell(row.get('confidence', '未提供'))} |"
            )
    else:
        lines.append("- fixture 未提供 claim。")

    lines.extend(
        [
            "",
            "## 脱敏后的 fixture 摘要",
            "",
            "JSON 代码摘要：",
            json.dumps(report.get("redacted_fixture"), ensure_ascii=False, indent=2),
            "",
        ]
    )
    return "\n".join(lines)


def write_text(path: str | Path, content: str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
