"""Operational controls for MedGuard (v2.1): behavior bundles, rollback, kill switch.

Everything that changes behavior — model, prompt, tools, guardrails — is versioned
together as a *behavior bundle* (Chapter 15). The registry keeps a history so you
can roll back to any previous bundle in one call (Chapter 6). The kill switch
disables the agent without a deploy, degrading to human review rather than to an
error.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BehaviorBundle:
    """The full set of behavior-determining artifact versions, versioned as one."""
    version: str
    model: str = "gpt-4o-mini"
    prompt_version: str = "v0"
    tools_version: str = "v0"
    guardrails_version: str = "v0"


class BundleRegistry:
    """Tracks the active bundle and its history; supports one-call rollback."""

    def __init__(self, initial: BehaviorBundle):
        self._history: list[BehaviorBundle] = [initial]

    @property
    def current(self) -> BehaviorBundle:
        return self._history[-1]

    def deploy(self, bundle: BehaviorBundle) -> BehaviorBundle:
        self._history.append(bundle)
        return bundle

    def rollback(self) -> BehaviorBundle:
        """Revert to the previous bundle (no-op if only one exists)."""
        if len(self._history) > 1:
            self._history.pop()
        return self.current


@dataclass
class KillSwitch:
    """When engaged, the agent degrades to human review rather than answering."""
    engaged: bool = False
    reason: str = ""

    def engage(self, reason: str) -> None:
        self.engaged = True
        self.reason = reason

    def disengage(self) -> None:
        self.engaged = False
        self.reason = ""
