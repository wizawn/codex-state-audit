"""Command-line entry points for the offline audit tool."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .reporting import build_report, render_json, render_markdown, write_text
from .simulation import run_simulation
from .validation import validate_path


def _format_report(report: dict, output_format: str) -> str:
    return render_markdown(report) if output_format == "markdown" else render_json(report)


def _emit_validation(
    fixture: str,
    *,
    output_format: str,
    output: str | None,
    json_out: str | None = None,
    markdown_out: str | None = None,
) -> int:
    result = validate_path(fixture)
    report = build_report(result, fixture_name=fixture)
    rendered = _format_report(report, output_format)

    if output:
        write_text(output, rendered)
    elif not json_out and not markdown_out:
        print(rendered, end="")

    if json_out:
        write_text(json_out, render_json(report))
    if markdown_out:
        write_text(markdown_out, render_markdown(report))

    # Fail closed: a likely credential is never treated as a successful audit,
    # even though a redacted copy is available for local inspection.
    if result.findings:
        print(
            f"检测到 {len(result.findings)} 个疑似敏感字段；已脱敏但拒绝以成功状态结束。",
            file=sys.stderr,
        )
        return 2
    if not result.valid:
        return 1
    return 0


def _emit_simulation(
    *,
    ttl_seconds: int,
    elapsed_seconds: int,
    event: str,
    label: str | None,
    output_format: str,
    output: str | None,
) -> int:
    try:
        simulation = run_simulation(
            ttl_seconds,
            elapsed_seconds=elapsed_seconds,
            event=event,
            label=label,
        )
    except (TypeError, ValueError) as exc:
        print(f"模拟参数错误：{exc}", file=sys.stderr)
        return 1

    if output_format == "markdown":
        lines = [
            "# 离线状态机模拟",
            "",
            "该结果只来自本地整数算术，不代表任何在线服务的状态。",
            "",
            f"- phase：{simulation['phase']}",
            f"- remaining_seconds：{simulation['remaining_seconds']}",
            f"- elapsed_seconds：{simulation['elapsed_seconds']}",
            f"- label：{simulation.get('label', '未提供')}（unknown）",
            "",
            "事件历史：",
            "",
        ]
        lines.extend(f"- {row}" for row in simulation["history"])
        rendered = "\n".join(lines) + "\n"
    else:
        rendered = json.dumps(simulation, ensure_ascii=False, indent=2) + "\n"

    if output:
        write_text(output, rendered)
    else:
        print(rendered, end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex-state-audit",
        description="离线审计本地 JSON fixture；不会连接在线服务。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="校验 fixture 并生成报告")
    validate.add_argument("fixture", help="本地 JSON 文件路径")
    validate.add_argument("--format", choices=("json", "markdown"), default="json")
    validate.add_argument("--output", help="将主报告写入文件")
    validate.add_argument("--json-out", help="额外写入 JSON 报告")
    validate.add_argument("--markdown-out", help="额外写入 Markdown 报告")

    report = subparsers.add_parser("report", help="只渲染报告，不改变 fixture")
    report.add_argument("fixture", help="本地 JSON 文件路径")
    report.add_argument("--format", choices=("json", "markdown"), default="markdown")
    report.add_argument("--output", help="将报告写入文件")

    simulate = subparsers.add_parser("simulate", help="运行本地 TTL/状态机模拟")
    simulate.add_argument("--ttl-seconds", required=True, type=int)
    simulate.add_argument("--elapsed-seconds", default=0, type=int)
    simulate.add_argument("--event", choices=("none", "revoke", "expire"), default="none")
    simulate.add_argument("--label", help="可选不透明标签，例如 292 或 312；不会改变状态")
    simulate.add_argument("--format", choices=("json", "markdown"), default="json")
    simulate.add_argument("--output", help="将模拟结果写入文件")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        return _emit_validation(
            args.fixture,
            output_format=args.format,
            output=args.output,
            json_out=args.json_out,
            markdown_out=args.markdown_out,
        )
    if args.command == "report":
        return _emit_validation(
            args.fixture,
            output_format=args.format,
            output=args.output,
        )
    if args.command == "simulate":
        return _emit_simulation(
            ttl_seconds=args.ttl_seconds,
            elapsed_seconds=args.elapsed_seconds,
            event=args.event,
            label=args.label,
            output_format=args.format,
            output=args.output,
        )
    parser.error("未知命令")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
