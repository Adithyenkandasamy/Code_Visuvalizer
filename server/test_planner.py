"""
test_planner.py — Unit tests for the Execution Planner.

Run with:
    python test_planner.py
    python -m unittest test_planner -v
"""

from __future__ import annotations

import textwrap
import unittest

from analyzer import CodeAnalyzer

from engine.planner import (
    CallType,
    ExecutionPlan,
    ExecutionPlanner,
    InvalidModuleError,
    NoExecutableFoundError,
    ParameterKind,
    PlannerError,
    PlannedParameter,
)


# =============================================================================
# Helpers
# =============================================================================


def _plan(source: str, **kwargs: str) -> ExecutionPlan:
    """Shortcut: analyze source → build plan."""
    module_info = CodeAnalyzer(textwrap.dedent(source)).analyze()
    return ExecutionPlanner.create(module_info, **kwargs)


# =============================================================================
# 1. Top-level function → FUNCTION
# =============================================================================


class TestTopLevelFunction(unittest.TestCase):

    def test_simple_function(self) -> None:
        plan = _plan("def solve(n: int) -> int:\n    return n * 2\n")
        self.assertEqual(plan.entry_function, "solve")
        self.assertEqual(plan.call_type, CallType.FUNCTION)
        self.assertIsNone(plan.entry_class)

    def test_function_parameters_preserved(self) -> None:
        plan = _plan("def add(a: int, b: int) -> int:\n    return a + b\n")
        self.assertEqual(len(plan.parameters), 2)
        self.assertEqual(plan.parameters[0].name, "a")
        self.assertEqual(plan.parameters[0].annotation, "int")
        self.assertEqual(plan.parameters[1].name, "b")

    def test_prefers_main(self) -> None:
        source = """\
            def helper():
                pass
            def main():
                pass
        """
        plan = _plan(source)
        self.assertEqual(plan.entry_function, "main")

    def test_module_name_default(self) -> None:
        plan = _plan("def f(): pass\n")
        self.assertEqual(plan.module_name, "__main__")

    def test_module_name_custom(self) -> None:
        plan = _plan("def f(): pass\n", module_name="my_module")
        self.assertEqual(plan.module_name, "my_module")


# =============================================================================
# 2. Instance method → CLASS_METHOD
# =============================================================================


class TestInstanceMethod(unittest.TestCase):

    def test_class_method_detected(self) -> None:
        source = """\
            class Solution:
                def twoSum(self, nums, target):
                    pass
        """
        plan = _plan(source)
        self.assertEqual(plan.entry_class, "Solution")
        self.assertEqual(plan.entry_function, "twoSum")
        self.assertEqual(plan.call_type, CallType.CLASS_METHOD)

    def test_self_filtered_out(self) -> None:
        source = """\
            class Solution:
                def twoSum(self, nums: list[int], target: int) -> list[int]:
                    pass
        """
        plan = _plan(source)
        names = [p.name for p in plan.parameters]
        self.assertNotIn("self", names)
        self.assertEqual(names, ["nums", "target"])

    def test_annotations_preserved(self) -> None:
        source = """\
            class Solution:
                def solve(self, data: list[int]) -> int:
                    pass
        """
        plan = _plan(source)
        self.assertEqual(plan.parameters[0].annotation, "list[int]")


# =============================================================================
# 3. @staticmethod → STATIC_METHOD
# =============================================================================


class TestStaticMethod(unittest.TestCase):

    def test_static_method_detected(self) -> None:
        source = """\
            class MathUtils:
                @staticmethod
                def add(a: int, b: int) -> int:
                    return a + b
        """
        plan = _plan(source)
        self.assertEqual(plan.call_type, CallType.STATIC_METHOD)
        self.assertEqual(plan.entry_class, "MathUtils")
        self.assertEqual(plan.entry_function, "add")

    def test_no_self_in_params(self) -> None:
        source = """\
            class Utils:
                @staticmethod
                def compute(x: int) -> int:
                    return x
        """
        plan = _plan(source)
        self.assertEqual(len(plan.parameters), 1)
        self.assertEqual(plan.parameters[0].name, "x")


# =============================================================================
# 4. @classmethod → CLASS_METHOD_DECORATOR
# =============================================================================


class TestClassMethodDecorator(unittest.TestCase):

    def test_classmethod_detected(self) -> None:
        source = """\
            class Factory:
                @classmethod
                def create(cls, name: str) -> 'Factory':
                    pass
        """
        plan = _plan(source)
        self.assertEqual(plan.call_type, CallType.CLASS_METHOD_DECORATOR)
        self.assertEqual(plan.entry_class, "Factory")
        self.assertEqual(plan.entry_function, "create")

    def test_cls_filtered_out(self) -> None:
        source = """\
            class Factory:
                @classmethod
                def build(cls, config: dict) -> 'Factory':
                    pass
        """
        plan = _plan(source)
        names = [p.name for p in plan.parameters]
        self.assertNotIn("cls", names)
        self.assertEqual(names, ["config"])


# =============================================================================
# 5. async function → ASYNC_FUNCTION
# =============================================================================


class TestAsyncFunction(unittest.TestCase):

    def test_async_function_detected(self) -> None:
        source = """\
            async def fetch(url: str) -> bytes:
                pass
        """
        plan = _plan(source)
        self.assertEqual(plan.call_type, CallType.ASYNC_FUNCTION)
        self.assertEqual(plan.entry_function, "fetch")
        self.assertIsNone(plan.entry_class)

    def test_async_params_preserved(self) -> None:
        source = """\
            async def download(url: str, timeout: int = 30) -> bytes:
                pass
        """
        plan = _plan(source)
        self.assertEqual(len(plan.parameters), 2)
        self.assertEqual(plan.parameters[1].name, "timeout")


# =============================================================================
# 6. Nested classes
# =============================================================================


class TestNestedClasses(unittest.TestCase):

    def test_only_top_level_class_picked(self) -> None:
        """The analyzer only reports top-level classes, so nested ones are ignored."""
        source = """\
            class Outer:
                def process(self, data):
                    class Inner:
                        def helper(self):
                            pass
                    pass
        """
        plan = _plan(source)
        self.assertEqual(plan.entry_class, "Outer")
        self.assertEqual(plan.entry_function, "process")


# =============================================================================
# 7. Multiple classes
# =============================================================================


class TestMultipleClasses(unittest.TestCase):

    def test_first_class_with_public_method_wins(self) -> None:
        source = """\
            class Ignored:
                def __init__(self):
                    pass

            class Solution:
                def solve(self, n: int) -> int:
                    return n
        """
        plan = _plan(source)
        self.assertEqual(plan.entry_class, "Solution")
        self.assertEqual(plan.entry_function, "solve")

    def test_first_class_if_both_have_public(self) -> None:
        source = """\
            class Alpha:
                def run(self):
                    pass

            class Beta:
                def execute(self):
                    pass
        """
        plan = _plan(source)
        self.assertEqual(plan.entry_class, "Alpha")
        self.assertEqual(plan.entry_function, "run")


# =============================================================================
# 8. No executable function → PlannerError
# =============================================================================


class TestNoExecutable(unittest.TestCase):

    def test_empty_module_raises(self) -> None:
        source = "x = 42\n"
        with self.assertRaises(NoExecutableFoundError):
            _plan(source)

    def test_no_executable_is_planner_error(self) -> None:
        """NoExecutableFoundError must be a subclass of PlannerError."""
        self.assertTrue(issubclass(NoExecutableFoundError, PlannerError))

    def test_none_module_raises(self) -> None:
        with self.assertRaises(InvalidModuleError):
            ExecutionPlanner(None).plan()  # type: ignore[arg-type]

    def test_only_imports_raises(self) -> None:
        source = "import os\nimport sys\n"
        with self.assertRaises(NoExecutableFoundError):
            _plan(source)


# =============================================================================
# 9. Frozen dataclasses
# =============================================================================


class TestFrozenDataclasses(unittest.TestCase):

    def test_execution_plan_is_frozen(self) -> None:
        plan = _plan("def f(): pass\n")
        with self.assertRaises(AttributeError):
            plan.entry_function = "changed"  # type: ignore[misc]

    def test_planned_parameter_is_frozen(self) -> None:
        plan = _plan("def f(x: int): pass\n")
        with self.assertRaises(AttributeError):
            plan.parameters[0].name = "changed"  # type: ignore[misc]


# =============================================================================
# Additional: Parameter kinds
# =============================================================================


class TestParameterKinds(unittest.TestCase):

    def test_positional_only(self) -> None:
        plan = _plan("def f(a, /, b): pass\n")
        self.assertEqual(plan.parameters[0].kind, ParameterKind.POSITIONAL_ONLY)
        self.assertEqual(plan.parameters[1].kind, ParameterKind.POSITIONAL_OR_KEYWORD)

    def test_keyword_only(self) -> None:
        plan = _plan("def f(*, key: str): pass\n")
        self.assertEqual(plan.parameters[0].kind, ParameterKind.KEYWORD_ONLY)

    def test_var_args(self) -> None:
        plan = _plan("def f(*args, **kwargs): pass\n")
        self.assertEqual(plan.parameters[0].kind, ParameterKind.VAR_POSITIONAL)
        self.assertEqual(plan.parameters[1].kind, ParameterKind.VAR_KEYWORD)


# =============================================================================
# Additional: create() class method
# =============================================================================


class TestCreateClassMethod(unittest.TestCase):

    def test_create_returns_plan(self) -> None:
        mi = CodeAnalyzer("def hello(): pass\n").analyze()
        plan = ExecutionPlanner.create(mi)
        self.assertIsInstance(plan, ExecutionPlan)
        self.assertEqual(plan.entry_function, "hello")

    def test_create_equals_plan(self) -> None:
        """create() and plan() must return equivalent results."""
        mi = CodeAnalyzer("def f(x: int): pass\n").analyze()
        plan_a = ExecutionPlanner(mi).plan()
        plan_b = ExecutionPlanner.create(mi)
        self.assertEqual(plan_a, plan_b)


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
