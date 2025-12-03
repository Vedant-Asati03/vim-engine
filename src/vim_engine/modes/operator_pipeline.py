"""Operator parsing pipeline scaffolding."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from vim_engine.buffer import Buffer, RegisterBank
from vim_engine.runtime import telemetry


@dataclass(slots=True)
class OperatorContext:
    buffer: Buffer
    registers: RegisterBank
    count: Optional[int] = None
    motion_id: Optional[str] = None
    register_name: str = '"'
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionPlan:
    operator_id: str
    motion_id: Optional[str]
    count: Optional[int]
    register_name: str
    raw_input: Tuple[str, ...]


@dataclass(slots=True)
class OperatorDraft:
    count: Optional[int] = None
    motion: Optional[str] = None
    operator: Optional[str] = None
    raw_keys: List[str] = field(default_factory=list)


class CountParser:
    def parse(self, keys: Sequence[str], draft: OperatorDraft) -> Sequence[str]:
        digits = []
        for key in keys:
            if key.isdigit():
                digits.append(key)
                draft.raw_keys.append(key)
            else:
                break
        if digits:
            draft.count = int("".join(digits))
            return keys[len(digits) :]
        return keys


class MotionParser:
    def parse(self, keys: Sequence[str], draft: OperatorDraft) -> Sequence[str]:
        if not keys:
            return keys
        # Placeholder: treat first key as motion identifier for now.
        draft.motion = keys[0]
        draft.raw_keys.append(keys[0])
        return keys[1:]


class OperatorResolver:
    def resolve(
        self, keys: Sequence[str], draft: OperatorDraft
    ) -> Optional[ExecutionPlan]:
        if not keys and not draft.motion:
            return None
        draft.operator = keys[0] if keys else draft.operator
        if draft.operator is None:
            return None
        draft.raw_keys.extend(keys)
        return ExecutionPlan(
            operator_id=draft.operator,
            motion_id=draft.motion,
            count=draft.count,
            register_name='"',
            raw_input=tuple(draft.raw_keys),
        )


class OperatorPipeline:
    def __init__(
        self, *, buffer: Buffer, registers: Optional[RegisterBank] = None
    ) -> None:
        self.buffer = buffer
        self.registers = registers or buffer.registers
        self.count_parser = CountParser()
        self.motion_parser = MotionParser()
        self.resolver = OperatorResolver()

    def parse(self, keys: Sequence[str]) -> Optional[ExecutionPlan]:
        draft = OperatorDraft()
        remaining = keys
        with telemetry.span(
            "operator::parse", component=True, metadata={"keys": "".join(keys)}
        ):
            remaining = self.count_parser.parse(remaining, draft)
            remaining = self.motion_parser.parse(remaining, draft)
            plan = self.resolver.resolve(remaining, draft)
        return plan

    def build_context(self, plan: ExecutionPlan) -> OperatorContext:
        return OperatorContext(
            buffer=self.buffer,
            registers=self.registers,
            count=plan.count,
            motion_id=plan.motion_id,
            register_name=plan.register_name,
            metadata={"operator": plan.operator_id},
        )
