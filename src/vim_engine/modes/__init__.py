"""Mode manager, operator pipeline, and dispatch logic."""

from .base_mode import KeyInput, Mode, ModeBus, ModeContext, ModeResult
from .normal_mode import NormalMode
from .insert_mode import InsertMode
from .visual_mode import VisualMode
from .command_mode import CommandMode
from .operator_pipeline import (
    ExecutionPlan,
    OperatorContext,
    OperatorDraft,
    OperatorPipeline,
)

__all__ = [
    "KeyInput",
    "Mode",
    "ModeBus",
    "ModeContext",
    "ModeResult",
    "NormalMode",
    "InsertMode",
    "VisualMode",
    "CommandMode",
    "OperatorPipeline",
    "OperatorContext",
    "ExecutionPlan",
    "OperatorDraft",
]
