import json
from pathlib import Path

import pytest

from codex_state_audit.redaction import redact_and_find
from codex_state_audit.reporting import build_report, render_json, render_markdown
from codex_state_audit.simulation import Phase, StateMachine, run_simulation
from codex_state_audit.validation import validate_fixture, validate_path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


def test_fixture_is_valid_but_292_is_opaque() -> None:
    result = validate_path(FIXTURES / "observed-292.json")

    assert result.valid is True
    assert result.safe_to_share is True
    assert result.observations["status_code"] == 292
    assert result.observations["status_semantics"] == "unknown"
    assert result.observations["current_turn_state_interpretation"] == "unknown"
    assert result.observations["declared_duration_seconds"] == 3600
    assert result.observations["ttl_inference"] == "not_performed"
    assert any(row["evidence_level"] == "unknown" for row in result.evidence)


def test_312_is_only_a_label() -> None:
    result = validate_path(FIXTURES / "observed-312.json")

    assert result.valid
    assert result.observations["status_semantics"] == "unknown"
    assert any("仅作为 unknown 标签" in warning for warning in result.warnings)


def test_sensitive_values_are_deterministically_redacted() -> None:
    payload = {
        "headers": {"Authorization": "Bearer abcdefghijklmnop"},
        "nested": {"current_turn_state": "opaque-secret-value"},
        "message": "ordinary text",
    }

    first, first_findings = redact_and_find(payload)
    second, second_findings = redact_and_find(payload)

    assert first == second
    assert [item.as_dict() for item in first_findings] == [
        item.as_dict() for item in second_findings
    ]
    assert len(first_findings) == 2
    assert "abcdefghijklmnop" not in json.dumps(first, ensure_ascii=False)
    assert first["message"] == "ordinary text"


def test_unredacted_fixture_is_not_shareable() -> None:
    result = validate_fixture(
        {
            "fixture_version": 1,
            "source": "user-supplied-redacted",
            "response": {
                "status_code": 200,
                "headers": {"authorization": "Bearer abcdefghijklmnop"},
            },
        }
    )

    assert result.valid
    assert result.safe_to_share is False
    assert result.findings
    assert "abcdefghijklmnop" not in json.dumps(result.redacted_fixture)


def test_invalid_fixture_reports_structure_error() -> None:
    result = validate_fixture({"fixture_version": 1, "response": {}})

    assert not result.valid
    assert any("status_code" in error for error in result.errors)


def test_timezone_mismatch_does_not_crash() -> None:
    result = validate_fixture(
        {
            "fixture_version": 1,
            "source": "user-supplied-redacted",
            "captured_at": "2026-09-18T12:00:00+08:00",
            "response": {
                "status_code": 200,
                "body": {"expires_at": "2026-09-18T13:00:00"},
            },
        }
    )

    assert result.valid
    assert result.observations["declared_duration_seconds"] is None
    assert any("时区格式不一致" in warning for warning in result.warnings)


def test_state_machine_uses_explicit_local_events_only() -> None:
    machine = StateMachine().observe(60).tick(10)
    assert machine.phase is Phase.OBSERVED
    assert machine.remaining_seconds == 50

    machine.tick(50)
    assert machine.phase is Phase.EXPIRED
    machine.revoke()
    assert machine.phase is Phase.REVOKED


def test_simulation_label_does_not_change_state() -> None:
    result = run_simulation(100, elapsed_seconds=10, label="312")

    assert result["phase"] == "observed"
    assert result["remaining_seconds"] == 90
    assert result["label_semantics"].startswith("unknown")


@pytest.mark.parametrize("bad_ttl", [0, -1])
def test_simulation_rejects_non_positive_ttl(bad_ttl: int) -> None:
    with pytest.raises(ValueError):
        run_simulation(bad_ttl)


def test_reports_contain_redacted_fixture_and_offline_boundary() -> None:
    result = validate_path(FIXTURES / "observed-292.json")
    report = build_report(result, fixture_name=str(FIXTURES / "observed-292.json"))
    rendered_json = render_json(report)
    rendered_markdown = render_markdown(report)

    assert report["fixture"]["name"] == "observed-292.json"
    assert report["tool"]["network_access"] is False
    assert "292/312 只作为 unknown 标签" in rendered_markdown
    assert "current_turn_state" in rendered_json
