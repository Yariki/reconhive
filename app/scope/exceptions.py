"""Exceptions raised by the scope authorization layer."""
from __future__ import annotations


class ScopeError(Exception):
    """Base class for all scope-related failures."""


class OutOfScopeError(ScopeError):
    """Raised when a target is not covered by any active authorization.

    This is the hard gate. If this is raised at scan time, NO packets
    should be sent to the target.
    """

    def __init__(self, target: str, reason: str) -> None:
        self.target = target
        self.reason = reason
        super().__init__(f"Target {target!r} is out of scope: {reason}")


class InvalidTargetError(ScopeError):
    """Raised when a target string cannot be parsed as an IP or network."""
