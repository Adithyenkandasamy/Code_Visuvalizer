"""
converters.py — Dataclass → Pydantic response converters.

Pure mapping functions that bridge the compiler's frozen dataclasses
to the API's Pydantic response models.  No business logic lives here.
"""

from __future__ import annotations

from analyzer import ClassInfo, FunctionInfo, ImportInfo, ModuleInfo, ParameterInfo

from engine.planner.models import ExecutionPlan, PlannedParameter

from schemas import (
    ClassInfoResponse,
    ExecutionPlanResponse,
    FunctionInfoResponse,
    ImportInfoResponse,
    ModuleInfoResponse,
    ParameterInfoResponse,
    PlannedParameterResponse,
)


# =============================================================================
# Analyzer Converters
# =============================================================================


def convert_parameter(p: ParameterInfo) -> ParameterInfoResponse:
    return ParameterInfoResponse(
        name=p.name,
        annotation=p.annotation,
        default_value=p.default_value,
        kind=p.kind.name,
    )


def convert_function(f: FunctionInfo) -> FunctionInfoResponse:
    return FunctionInfoResponse(
        name=f.name,
        parameters=[convert_parameter(p) for p in f.parameters],
        return_annotation=f.return_annotation,
        decorators=list(f.decorators),
        docstring=f.docstring,
        is_async=f.is_async,
        is_method=f.is_method,
        lineno=f.lineno,
        end_lineno=f.end_lineno,
    )


def convert_import(i: ImportInfo) -> ImportInfoResponse:
    return ImportInfoResponse(
        module=i.module,
        name=i.name,
        alias=i.alias,
        kind=i.kind.name,
        lineno=i.lineno,
    )


def convert_class(c: ClassInfo) -> ClassInfoResponse:
    return ClassInfoResponse(
        name=c.name,
        bases=list(c.bases),
        methods=[convert_function(m) for m in c.methods],
        decorators=list(c.decorators),
        docstring=c.docstring,
        lineno=c.lineno,
        end_lineno=c.end_lineno,
    )


def convert_module(m: ModuleInfo) -> ModuleInfoResponse:
    return ModuleInfoResponse(
        imports=[convert_import(i) for i in m.imports],
        classes=[convert_class(c) for c in m.classes],
        functions=[convert_function(f) for f in m.functions],
        docstring=m.docstring,
        source_lines=m.source_lines,
    )


# =============================================================================
# Planner Converters
# =============================================================================


def convert_planned_parameter(p: PlannedParameter) -> PlannedParameterResponse:
    return PlannedParameterResponse(
        name=p.name,
        annotation=p.annotation,
        kind=p.kind.name,
    )


def convert_execution_plan(plan: ExecutionPlan) -> ExecutionPlanResponse:
    return ExecutionPlanResponse(
        module_name=plan.module_name,
        entry_function=plan.entry_function,
        call_type=plan.call_type.value,
        parameters=[convert_planned_parameter(p) for p in plan.parameters],
        entry_class=plan.entry_class,
    )
