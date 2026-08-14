"""Typed failures. Anything the projector cannot handle must raise, never skip."""


class MindGraphError(Exception):
    """Base for everything raised by this package."""


class UnknownEventType(MindGraphError):
    """The projector met an event type it has no handler for.

    Deliberately fatal: silently skipping an unknown event makes replay
    non-deterministic across versions, which is the one thing that must not
    happen (Backend/02 §5.3 rule 4).
    """


class ChainBroken(MindGraphError):
    """The ledger hash chain does not verify — the log was edited or reordered."""


class KeyDestroyed(MindGraphError):
    """Content was requested for a user whose key has been shredded."""
