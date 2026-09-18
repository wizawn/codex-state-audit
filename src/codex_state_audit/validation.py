"""Schema-light validation for local JSON fixtures."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import EVIDENCE_LEVELS, ValidationResult
from .redaction import redact_and_find


def load_fixture(path: str | Path) -> Any:
    """Load one local JSON file.

    This function intentionally accepts only a filesystem path.  It does not
    interpret URLs, environment variables, or remote references.
    """

    fixture_path = Path(path)
    text = fixture_path.read_text(encoding="utf-8")
    return json.loads(text)


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _find_key(value: Any, wanted: str) -> tuple[Any, str] | None:
    """Find the first key recursively, returning value and safe path."""

    def walk(current: Any, path: str) -> tuple[Any, str] | None:
        if isinstance(current, dict):
            for key, child in current.items():
                child_path = f"{path}/{key}" if path else f"$/{key}"
                if str(key) == wanted:
                    return child, child_path
                found = walk(child, child_path)
                if found is not None:
                    return found
        elif isinstance(current, list):
            for index, child in enumerate(current):
                found = walk(child, f"{path}[{index}]")
                if found is not None:
                    return found
        return None

    return walk(value, "$")


def _status_code(data: dict[str, Any]) -> tuple[int | None, str | None]:
    response = data.get("response")
    if not isinstance(response, dict):
        return None, None
    raw = response.get("status_code")
    if isinstance(raw, bool) or not isinstance(raw, int):
        return None, None
    return raw, "unknown" if raw in (292, 312) else "uninterpreted"


def _evidence_rows(data: dict[str, Any], warnings: list[str]) -> list[dict[str, Any]]:
    claims = data.get("claims", [])
    if claims is None:
        return []
    if not isinstance(claims, list):
        warnings.append("claims 不是数组；已忽略其内容")
        return []

    rows: list[dict[str, Any]] = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            warnings.append(f"claims[{index}] 不是对象；已忽略")
            continue
        text = claim.get("claim")
        level = claim.get("evidence_level", "unknown")
        if not isinstance(text, str) or not text.strip():
            warnings.append(f"claims[{index}] 缺少非空 claim")
            continue
        if level not in EVIDENCE_LEVELS:
            warnings.append(f"claims[{index}] 的 evidence_level 不受支持，已归类为 unknown")
            level = "unknown"
        row: dict[str, Any] = {"claim": text, "evidence_level": level}
        if isinstance(claim.get("confidence"), str):
            row["confidence"] = claim["confidence"]
        if isinstance(claim.get("notes"), str):
            row["notes"] = claim["notes"]
        rows.append(row)
    return rows


def validate_fixture(data: Any) -> ValidationResult:
    """Validate structure and return a redacted, report-safe result."""

    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return ValidationResult(
            valid=False,
            safe_to_share=False,
            errors=["fixture 根值必须是 JSON 对象"],
            redacted_fixture=None,
        )

    redacted, findings = redact_and_find(data)

    version = data.get("fixture_version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        errors.append("fixture_version 必须是大于等于 1 的整数")

    source = data.get("source")
    if not isinstance(source, str) or not source.strip():
        warnings.append("缺少 source；建议标记为 fixture-generated-redacted 或 user-supplied-redacted")
    elif source not in {"fixture-generated-redacted", "user-supplied-redacted"}:
        warnings.append(
            "source 不是 fixture-generated-redacted 或 user-supplied-redacted；请确认 fixture 已脱敏"
        )

    response = data.get("response")
    if not isinstance(response, dict):
        errors.append("response 必须是对象")
        response = {}

    status_code, status_semantics = _status_code(data)
    if status_code is None:
        errors.append("response.status_code 必须是整数")
    elif not 100 <= status_code <= 599:
        errors.append("response.status_code 必须处于 100 到 599 之间")
    elif status_code in (292, 312):
        warnings.append(
            f"status_code={status_code} 仅作为 unknown 标签；工具不推断其服务端语义"
        )

    captured_at = data.get("captured_at")
    captured_dt = _parse_datetime(captured_at)
    if captured_at is not None and captured_dt is None:
        warnings.append("captured_at 不是可解析的 ISO-8601 时间；未进行时间算术")

    state_found = _find_key(data, "current_turn_state")
    expiry_found = _find_key(data, "expires_at")
    expiry_dt = _parse_datetime(expiry_found[0]) if expiry_found else None
    if expiry_found and expiry_dt is None:
        warnings.append("expires_at 不是可解析的 ISO-8601 时间；未进行时间算术")

    declared_duration: int | None = None
    if captured_dt is not None and expiry_dt is not None:
        try:
            declared_duration = int((expiry_dt - captured_dt).total_seconds())
        except TypeError:
            warnings.append("captured_at 与 expires_at 的时区格式不一致；未进行时间算术")
        if declared_duration is not None:
            if declared_duration < 0:
                warnings.append("expires_at 早于 captured_at；仅记录原始算术结果")
            warnings.append("时间差只是 fixture 算术，不代表服务器 TTL 或有效期事实")

    body = response.get("body")
    if body is not None and not isinstance(body, (dict, list, str, int, float, bool)):
        warnings.append("response.body 不是常见 JSON 类型")

    observations: dict[str, Any] = {
        "status_code": status_code,
        "status_semantics": status_semantics,
        "current_turn_state_present": state_found is not None,
        "current_turn_state_interpretation": "unknown"
        if state_found is not None
        else "not_observed",
        "captured_at_present": captured_dt is not None,
        "expires_at_present": expiry_dt is not None,
        "declared_duration_seconds": declared_duration,
        "ttl_inference": "not_performed",
    }

    if state_found is not None:
        warnings.append(
            "发现 current_turn_state 字段；它被视为不透明敏感值，不能据此推断凭据或通行证"
        )

    evidence = _evidence_rows(redacted, warnings)
    valid = not errors
    return ValidationResult(
        valid=valid,
        safe_to_share=valid and not findings,
        errors=errors,
        warnings=warnings,
        findings=findings,
        observations=observations,
        evidence=evidence,
        redacted_fixture=redacted,
    )


def validate_path(path: str | Path) -> ValidationResult:
    """Load and validate a local fixture, converting I/O/JSON errors safely."""

    try:
        data = load_fixture(path)
    except (OSError, UnicodeError) as exc:
        return ValidationResult(
            valid=False,
            safe_to_share=False,
            errors=[f"无法读取本地 fixture：{type(exc).__name__}"],
        )
    except json.JSONDecodeError as exc:
        return ValidationResult(
            valid=False,
            safe_to_share=False,
            errors=[f"fixture 不是合法 JSON（第 {exc.lineno} 行）"],
        )
    return validate_fixture(data)
