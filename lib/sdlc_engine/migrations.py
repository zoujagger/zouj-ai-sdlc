"""Migrations `sdlc upgrade` lists when a repo moves to a new plugin version.

Each migration says whether it is still pending (`applies`, idempotent detection) and whether only the human may run
it. `upgrade` never runs a human-only migration: it prints the command. A migration is recorded in install-state
as applied once `applies` turns false.
"""
from typing import Callable, NamedTuple

from . import approvals


class Migration(NamedTuple):
    id: str
    applies: Callable
    human_only: bool
    command: str
    why: str


def _legacy_pending(root):
    """Unsigned approval commits of open gates (that predate signing on main) not yet in the legacy list."""
    try:
        _, _, legacy = approvals.trust(root)
        return [sha for sha, _ in approvals.unsigned_approvals(root) if sha not in legacy]
    except approvals.BaseRefError:
        return []


MIGRATIONS = [
    Migration("legacy-approvals", lambda root: bool(_legacy_pending(root)), True, "sdlc legacy-approvals --write",
              "approval commits made before signing was required: CI accepts them only once a human lists them in "
              ".aiops/config/legacy-approvals (human-owned)"),
]
