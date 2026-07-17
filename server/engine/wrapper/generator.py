"""
generator.py — WrapperGenerator and InputGenerator for Code Vision.

Pipeline::

    ExecutionPlan
        → InputGenerator   (default values for each parameter)
        → TemplateRenderer  (formatted code blocks)
        → GeneratedSource   (final runnable source string)

The generator NEVER executes code.  It only produces source strings.
"""

from __future__ import annotations

import re

from engine.planner.models import CallType, ExecutionPlan, PlannedParameter

from engine.wrapper.exceptions import InvalidPlanError, UnsupportedCallTypeError
from engine.wrapper.models import GeneratedSource, GeneratedVariable
from engine.wrapper.templates import TemplateRenderer


# =============================================================================
# InputGenerator
# =============================================================================

# Mapping of normalised annotation strings → Python literal defaults.
_SIMPLE_DEFAULTS: dict[str, str] = {
    "int": "42",
    "float": "3.14",
    "str": '"hello"',
    "bool": "True",
    "bytes": 'b"data"',
    "none": "None",
    "nonetype": "None",
    "any": "None",
}

# Patterns for generic container types (case-insensitive).
# Each entry is (regex, builder_function_that_takes_inner_matches).
_GENERIC_PATTERNS: list[tuple[re.Pattern[str], callable]] = []


def _register_pattern(pattern: str, builder: callable) -> None:
    """Register a regex → builder pair."""
    _GENERIC_PATTERNS.append((re.compile(pattern, re.IGNORECASE), builder))


# ── Pattern builders ───────────────────────────────────────────────────

def _list_builder(m: re.Match) -> str:
    inner = m.group(1).strip()
    elem = InputGenerator.default_for_annotation(inner)
    return f"[{elem}]"


def _tuple_builder(m: re.Match) -> str:
    inner_parts = m.group(1).split(",")
    elems = [InputGenerator.default_for_annotation(p.strip()) for p in inner_parts]
    return f"({', '.join(elems)})"


def _set_builder(m: re.Match) -> str:
    inner = m.group(1).strip()
    elem = InputGenerator.default_for_annotation(inner)
    return "{" + elem + "}"


def _dict_builder(m: re.Match) -> str:
    key_type = m.group(1).strip()
    val_type = m.group(2).strip()
    key = InputGenerator.default_for_annotation(key_type)
    val = InputGenerator.default_for_annotation(val_type)
    return "{" + f"{key}: {val}" + "}"


def _optional_builder(m: re.Match) -> str:
    inner = m.group(1).strip()
    return InputGenerator.default_for_annotation(inner)


# Register patterns (order matters — first match wins).
_register_pattern(r"^(?:list|List)\[(.+)\]$", _list_builder)
_register_pattern(r"^(?:tuple|Tuple)\[(.+)\]$", _tuple_builder)
_register_pattern(r"^(?:set|Set)\[(.+)\]$", _set_builder)
_register_pattern(r"^(?:dict|Dict)\[(.+?),\s*(.+)\]$", _dict_builder)
_register_pattern(r"^(?:optional|Optional)\[(.+)\]$", _optional_builder)


class InputGenerator:
    """
    Produces sensible default Python literal values for parameter
    annotations.  Used to populate input variables in generated code.

    All methods are static — no instance state is required.
    """

    @staticmethod
    def default_for_annotation(annotation: str | None) -> str:
        """
        Return a Python literal string for the given type annotation.

        Args:
            annotation: The annotation string (e.g. ``"list[int]"``).
                        ``None`` or empty → ``"None"``.

        Returns:
            A valid Python literal as a string.
        """
        if not annotation:
            return "None"

        cleaned = annotation.strip()

        # 1. Simple / scalar types.
        if cleaned.lower() in _SIMPLE_DEFAULTS:
            return _SIMPLE_DEFAULTS[cleaned.lower()]

        # 2. Generic container types via regex.
        for pattern, builder in _GENERIC_PATTERNS:
            match = pattern.match(cleaned)
            if match:
                return builder(match)

        # 3. Unknown annotation → None.
        return "None"

    @staticmethod
    def generate_variables(
        parameters: list[PlannedParameter],
    ) -> list[GeneratedVariable]:
        """
        Produce a ``GeneratedVariable`` for every parameter.

        Args:
            parameters: The planned parameters (``self``/``cls`` already
                        filtered out by the planner).

        Returns:
            Ordered list of ``GeneratedVariable`` objects.
        """
        return [
            GeneratedVariable(
                name=p.name,
                value=InputGenerator.default_for_annotation(p.annotation),
            )
            for p in parameters
        ]


# =============================================================================
# WrapperGenerator
# =============================================================================


class WrapperGenerator:
    """
    Converts an ``ExecutionPlan`` into runnable Python source code.

    The generator NEVER executes code.  It delegates to
    ``InputGenerator`` for default values and ``TemplateRenderer``
    for source formatting.

    Usage::

        gen = WrapperGenerator(plan)
        result = gen.generate()
        print(result.source_code)

    Or via the class-method shortcut::

        result = WrapperGenerator.create(plan)
    """

    def __init__(self, plan: ExecutionPlan) -> None:
        if plan is None:
            raise InvalidPlanError("ExecutionPlan must not be None.")
        if not plan.entry_function:
            raise InvalidPlanError("ExecutionPlan must have an entry_function.")
        self._plan = plan
        self._renderer = TemplateRenderer()
        self._input_gen = InputGenerator()

    # ── Public API ─────────────────────────────────────────────────────

    def generate(self) -> GeneratedSource:
        """
        Generate the complete wrapper source code.

        Returns:
            A ``GeneratedSource`` with the runnable Python code.

        Raises:
            UnsupportedCallTypeError: If ``call_type`` is unrecognised.
        """
        plan = self._plan
        r = self._renderer

        # 1. Imports.
        imports = self._required_imports()
        import_block = r.render_imports(imports)

        # 2. Input variables.
        variables = self._input_gen.generate_variables(plan.parameters)
        var_tuples = [(v.name, v.value) for v in variables]
        var_block = r.render_variables(var_tuples)

        # 3. Instantiation (if needed).
        inst_block, receiver = self._build_instantiation()

        # 4. Function call.
        arg_names = [v.name for v in variables]
        is_async = plan.call_type == CallType.ASYNC_FUNCTION
        call_block = r.render_call(
            func_name=plan.entry_function,
            arg_names=arg_names,
            receiver=receiver,
            is_async=is_async,
        )

        # 5. Print result.
        print_block = r.render_print()

        # 6. Assemble.
        source = r.render([import_block, var_block, inst_block, call_block, print_block])

        # Extract the call expression for metadata.
        call_expr = call_block.replace("result = ", "").strip()

        return GeneratedSource(
            source_code=source,
            variables=variables,
            call_expr=call_expr,
        )

    @classmethod
    def create(cls, plan: ExecutionPlan) -> GeneratedSource:
        """Convenience shortcut: generate in one call."""
        return cls(plan).generate()

    # ── Internals ──────────────────────────────────────────────────────

    def _required_imports(self) -> list[str]:
        """Determine which imports the generated code needs."""
        if self._plan.call_type == CallType.ASYNC_FUNCTION:
            return ["asyncio"]
        return []

    def _build_instantiation(self) -> tuple[str, str | None]:
        """
        Build the class instantiation block if the plan requires one.

        Returns:
            (instantiation_code, receiver_variable_name)
            For top-level functions, returns ``("", None)``.
        """
        plan = self._plan
        r = self._renderer

        if plan.call_type in (CallType.FUNCTION, CallType.ASYNC_FUNCTION):
            # Top-level function — no instantiation needed.
            return "", None

        if plan.entry_class is None:
            raise InvalidPlanError(
                f"Call type {plan.call_type.value} requires an entry_class."
            )

        if plan.call_type == CallType.CLASS_METHOD:
            # Instance method: instantiate the class.
            var_name = plan.entry_class[0].lower() + plan.entry_class[1:]
            inst = r.render_instantiation(plan.entry_class, var_name)
            return inst, var_name

        if plan.call_type in (CallType.STATIC_METHOD, CallType.CLASS_METHOD_DECORATOR):
            # Static / classmethod: call on the class itself.
            return "", plan.entry_class

        raise UnsupportedCallTypeError(plan.call_type.value)
