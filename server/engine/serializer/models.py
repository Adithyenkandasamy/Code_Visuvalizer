"""
models.py — Configuration and output models for the Serializer.

Frozen dataclasses that control serialization behaviour and
describe the output shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SerializerConfig:
    """
    Immutable configuration for the ``TraceSerializer``.

    Attributes:
        max_depth:          Maximum recursion depth for nested structures.
        max_repr_len:       Truncation limit for repr() fallback strings.
        filter_internals:   Whether to strip dunder / runtime variables.
        include_timestamps: Whether to include nanosecond timestamps.
        include_globals:    Whether to include global-variable snapshots.
    """

    max_depth: int = 5
    max_repr_len: int = 200
    filter_internals: bool = True
    include_timestamps: bool = True
    include_globals: bool = True


# Names that should never appear in serialized variable snapshots.
INTERNAL_NAMES: frozenset[str] = frozenset({
    "__builtins__",
    "__loader__",
    "__cached__",
    "__spec__",
    "__package__",
    "__name__",
    "__doc__",
    "__file__",
    "__annotations__",
    "__all__",
    "__path__",
    "__import__",
})
