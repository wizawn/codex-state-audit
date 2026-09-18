"""Deterministic, local-only sensitive-value detection and redaction."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .models import Finding


# Key names are intentionally broad.  A false positive is safer than carrying
# a credential into a report, and the replacement never includes the value.
_SENSITIVE_KEY_RE = re.compile(
    r"(?:^|[_-])(authorization|api[_-]?key|access[_-]?key|token|secret|password|"
    r"cookie|session|credential|private[_-]?key|current[_-]?turn[_-]?state)(?:$|[_-])",
    re.IGNORECASE,
)
_BEARER_RE = re.compile(r"^Bearer\s+[A-Za-z0-9._~+/=-]{8,}$", re.IGNORECASE)
_JWT_RE = re.compile(r"^[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}$")
_PREFIXED_KEY_RE = re.compile(
    r"^(?:sk|pk|rk|ghp|gho|github_pat|xox[baprs])[-_][A-Za-z0-9._-]{8,}$",
    re.IGNORECASE,
)
_QUERY_SECRET_RE = re.compile(
    r"(?:^|[?&\s])(?:api[_-]?key|access[_-]?token|token|secret|password)="
    r"[^&\s]{8,}",
    re.IGNORECASE,
)
_PLACEHOLDER_RE = re.compile(
    r"^(?:\[\s*(?:redacted|masked|removed|unknown|opaque)(?::[^\]]*)?\s*\]"
    r"|<\s*(?:redacted|masked|removed|unknown|opaque)[^>]*>"
    r"|\*{3,}|N/?A)$",
    re.IGNORECASE,
)


def _path_for_key(path: str, key: str) -> str:
    """Return a JSON-pointer-like path without exposing values."""

    escaped = str(key).replace("~", "~0").replace("/", "~1")
    return f"{path}/{escaped}" if path else f"$/{escaped}"


def _path_for_index(path: str, index: int) -> str:
    return f"{path}[{index}]" if path else f"$[{index}]"


def _stable_digest(value: Any) -> str:
    """Return a short deterministic digest without retaining the input."""

    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]


def is_redaction_placeholder(value: Any) -> bool:
    return isinstance(value, str) and bool(_PLACEHOLDER_RE.fullmatch(value.strip()))


def is_sensitive_key(key: str) -> bool:
    return bool(_SENSITIVE_KEY_RE.search(key.replace(" ", "_")))


def is_sensitive_string(value: str) -> bool:
    """Detect common credential formats without attempting to decode them."""

    candidate = value.strip()
    if not candidate or is_redaction_placeholder(candidate):
        return False
    return bool(
        _BEARER_RE.fullmatch(candidate)
        or _JWT_RE.fullmatch(candidate)
        or _PREFIXED_KEY_RE.fullmatch(candidate)
        or _QUERY_SECRET_RE.search(candidate)
    )


def _replacement(value: Any, key_hint: str | None = None) -> str:
    digest = _stable_digest(value)
    label = "VALUE" if not key_hint else key_hint.upper().replace("-", "_")
    return f"[REDACTED:{label}:{digest}]"


def redact_json(value: Any, *, findings: list[Finding] | None = None, path: str = "$") -> Any:
    """Return a JSON-compatible copy with sensitive values deterministically masked.

    The function never mutates the input.  A supplied findings list receives
    only paths and categories, never the original value.
    """

    sink = findings if findings is not None else []

    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            child_path = _path_for_key(path, key)
            if is_sensitive_key(key):
                if is_redaction_placeholder(raw_value):
                    output[key] = raw_value
                else:
                    sink.append(
                        Finding(
                            path=child_path,
                            kind="sensitive_key",
                            message="敏感字段已确定性脱敏；原值不会进入报告",
                        )
                    )
                    output[key] = _replacement(raw_value, key)
                continue
            output[key] = redact_json(raw_value, findings=sink, path=child_path)
        return output

    if isinstance(value, list):
        return [
            redact_json(item, findings=sink, path=_path_for_index(path, index))
            for index, item in enumerate(value)
        ]

    if isinstance(value, str) and is_sensitive_string(value):
        sink.append(
            Finding(
                path=path,
                kind="sensitive_value",
                message="疑似凭据格式已确定性脱敏；原值不会进入报告",
            )
        )
        return _replacement(value)

    return value


def redact_and_find(value: Any) -> tuple[Any, list[Finding]]:
    findings: list[Finding] = []
    redacted = redact_json(value, findings=findings)
    return redacted, findings
