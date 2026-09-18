import json
from pathlib import Path

from codex_state_audit.cli import main


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "observed-292.json"


def test_validate_writes_both_report_formats(tmp_path: Path) -> None:
    json_out = tmp_path / "audit.json"
    markdown_out = tmp_path / "audit.md"

    code = main(
        [
            "validate",
            str(FIXTURE),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    assert code == 0
    report = json.loads(json_out.read_text(encoding="utf-8"))
    assert report["validation"]["valid"] is True
    assert "离线" in markdown_out.read_text(encoding="utf-8")


def test_validate_fails_closed_on_sensitive_input(tmp_path: Path) -> None:
    fixture = tmp_path / "unsafe.json"
    fixture.write_text(
        json.dumps(
            {
                "fixture_version": 1,
                "source": "user-supplied-redacted",
                "response": {
                    "status_code": 200,
                    "headers": {"authorization": "Bearer abcdefghijklmnop"},
                },
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "unsafe-report.json"

    code = main(["validate", str(fixture), "--output", str(output)])

    assert code == 2
    assert output.exists()
    assert "abcdefghijklmnop" not in output.read_text(encoding="utf-8")


def test_report_command_can_render_markdown(capsys) -> None:
    code = main(["report", str(FIXTURE), "--format", "markdown"])

    assert code == 0
    assert "# Codex State Audit 离线报告" in capsys.readouterr().out


def test_simulate_command_keeps_label_opaque(capsys) -> None:
    code = main(
        [
            "simulate",
            "--ttl-seconds",
            "60",
            "--elapsed-seconds",
            "10",
            "--label",
            "312",
        ]
    )

    assert code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["phase"] == "observed"
    assert output["label_semantics"].startswith("unknown")
