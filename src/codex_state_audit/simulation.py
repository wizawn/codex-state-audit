"""Deterministic, offline state-machine and TTL simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Phase(StrEnum):
    UNKNOWN = "unknown"
    OBSERVED = "observed"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass
class StateMachine:
    """A deliberately generic state machine.

    It models only local arithmetic.  The revoke method is an explicit test
    event; no HTTP status, including 292 or 312, can trigger it implicitly.
    """

    phase: Phase = Phase.UNKNOWN
    remaining_seconds: int | None = None
    elapsed_seconds: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)

    def _record(self, event: str, **details: Any) -> None:
        row: dict[str, Any] = {"event": event, "phase": self.phase.value}
        row.update(details)
        self.history.append(row)

    def observe(self, ttl_seconds: int) -> "StateMachine":
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int):
            raise TypeError("ttl_seconds 必须是整数")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds 必须大于 0")
        self.phase = Phase.OBSERVED
        self.remaining_seconds = ttl_seconds
        self.elapsed_seconds = 0
        self._record("observe", ttl_seconds=ttl_seconds, remaining_seconds=ttl_seconds)
        return self

    def tick(self, seconds: int) -> "StateMachine":
        if isinstance(seconds, bool) or not isinstance(seconds, int):
            raise TypeError("seconds 必须是整数")
        if seconds < 0:
            raise ValueError("seconds 不能为负数")
        self.elapsed_seconds += seconds
        if self.phase is Phase.OBSERVED and self.remaining_seconds is not None:
            self.remaining_seconds = max(0, self.remaining_seconds - seconds)
            if self.remaining_seconds == 0:
                self.phase = Phase.EXPIRED
        self._record("tick", seconds=seconds, remaining_seconds=self.remaining_seconds)
        return self

    def revoke(self) -> "StateMachine":
        self.phase = Phase.REVOKED
        self.remaining_seconds = None
        self._record("revoke")
        return self

    def reset(self) -> "StateMachine":
        self.phase = Phase.UNKNOWN
        self.remaining_seconds = None
        self.elapsed_seconds = 0
        self._record("reset")
        return self

    def as_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase.value,
            "remaining_seconds": self.remaining_seconds,
            "elapsed_seconds": self.elapsed_seconds,
            "history": list(self.history),
            "semantics": "local simulation only; no server meaning inferred",
        }


def run_simulation(
    ttl_seconds: int,
    *,
    elapsed_seconds: int = 0,
    event: str = "none",
    label: str | None = None,
) -> dict[str, Any]:
    """Run a deterministic scenario without consulting wall-clock time."""

    if isinstance(elapsed_seconds, bool) or not isinstance(elapsed_seconds, int):
        raise TypeError("elapsed_seconds 必须是整数")
    if elapsed_seconds < 0:
        raise ValueError("elapsed_seconds 不能为负数")

    machine = StateMachine().observe(ttl_seconds)
    if elapsed_seconds:
        machine.tick(elapsed_seconds)

    if event == "revoke":
        machine.revoke()
    elif event == "expire":
        if machine.phase is Phase.OBSERVED and machine.remaining_seconds is not None:
            machine.tick(machine.remaining_seconds)
    elif event == "none":
        pass
    else:
        raise ValueError("event 必须是 none、revoke 或 expire")

    output = machine.as_dict()
    output["input"] = {
        "ttl_seconds": ttl_seconds,
        "elapsed_seconds": elapsed_seconds,
        "event": event,
    }
    if label is not None:
        output["label"] = label
        output["label_semantics"] = "unknown (opaque annotation only)"
    return output
