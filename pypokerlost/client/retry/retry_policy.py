"""Validated opt-in retry policy for one PokerLost API call."""

from __future__ import annotations

from typing import Annotated, ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

type _MaxAttempts = Annotated[int, Field(strict=True, ge=1, le=10)]
type _DelaySeconds = Annotated[
    float,
    Field(strict=True, ge=0.0, le=60.0, allow_inf_nan=False),
]
type _BackoffMultiplier = Annotated[
    float,
    Field(strict=True, ge=1.0, le=100.0, allow_inf_nan=False),
]
type _TotalBudgetSeconds = Annotated[
    float,
    Field(strict=True, gt=0.0, le=600.0, allow_inf_nan=False),
]


class RetryPolicy(BaseModel):
    """Bound attempts and delays for an explicitly replay-safe call."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    retryable_statuses: ClassVar[frozenset[int]] = frozenset(
        {408, 425, 429, 500, 502, 503, 504},
    )

    max_attempts: _MaxAttempts = 3
    initial_delay: _DelaySeconds = 0.2
    max_delay: _DelaySeconds = 2.0
    backoff_multiplier: _BackoffMultiplier = 2.0
    total_budget: _TotalBudgetSeconds | None = None
    respect_retry_after: bool = True

    @model_validator(mode="after")
    def validate_delay_bounds(self) -> Self:
        """Keep the initial jitter cap within the configured maximum."""
        if self.initial_delay > self.max_delay:
            raise ValueError("initial_delay must not exceed max_delay")
        return self
