"""Canonical Action data contract for the deterministic sequencer."""

from pydantic import BaseModel, Field
from enum import Enum


class ActionType(str, Enum):
    RUNWAY_NOW = "RUNWAY_NOW"
    LONG_LATENCY = "LONG_LATENCY"
    ADMIN = "ADMIN"


class Action(BaseModel):
    """A single recommended action in the 30-minute action plan."""

    id: str
    title: str
    type: ActionType
    time_to_execute_min: int = Field(
        ..., description="Estimated minutes to complete this action"
    )
    runway_gain_days: float = Field(
        ..., description="Heuristic days of runway gained by completing this action"
    )
    success_prob: float = Field(
        ..., ge=0.0, le=1.0, description="Heuristic probability of success (0-1)"
    )
    requires: list[str] = Field(
        default_factory=list,
        description="Files or fields required to complete this action",
    )
    produces: list[str] = Field(
        default_factory=list,
        description="Artifacts produced (letter PDF, application, etc.)",
    )
    copy_text: str | None = Field(
        None, description="Ready-to-use copyable text (email body, script, etc.)"
    )


class ChecklistItem(BaseModel):
    """A single step in the 30-minute action plan checklist."""

    step_number: int
    title: str
    why: str = Field(..., description="Why this step matters, e.g. 'buys ~14 days runway'")
    time_estimate_min: int
    copy_text: str | None = None
    attached_file: str | None = Field(
        None, description="Reference to an attached letter or document"
    )
