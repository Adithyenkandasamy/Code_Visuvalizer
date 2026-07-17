"""
test_wrapper.py — Unit tests for the Wrapper Generator.

Run:
    python test_wrapper.py
    python -m unittest test_wrapper -v
"""

from __future__ import annotations

import textwrap
import unittest

from engine.planner.models import (
    CallType,
    ExecutionPlan,
    ParameterKind,
    PlannedParameter,
)

from engine.wrapper import (
    GeneratedSource,
    InputGenerator,
    InvalidPlanError,
    TemplateRenderer,
    WrapperError,
    WrapperGenerator,
)


# =============================================================================
# Helpers
# =============================================================================


def _make_plan(
    entry_function: str = "solve",
    call_type: CallType = CallType.FUNCTION,
    parameters: list[PlannedParameter] | None = None,
    entry_class: str | None = None,
    module_name: str = "__main__",
) -> ExecutionPlan:
    """Build an ExecutionPlan for testing."""
    return ExecutionPlan(
        module_name=module_name,
        entry_function=entry_function,
        call_type=call_type,
        parameters=parameters or [],
        entry_class=entry_class,
    )


# =============================================================================
# Test: InputGenerator
# =============================================================================


class TestInputGenerator(unittest.TestCase):
    """Verify default value generation for all annotation types."""

    gen = InputGenerator()

    def test_int(self) -> None:
        self.assertEqual(self.gen.default_for_annotation("int"), "42")

    def test_float(self) -> None:
        self.assertEqual(self.gen.default_for_annotation("float"), "3.14")

    def test_str(self) -> None:
        self.assertEqual(self.gen.default_for_annotation("str"), '"hello"')

    def test_bool(self) -> None:
        self.assertEqual(self.gen.default_for_annotation("bool"), "True")

    def test_list_int(self) -> None:
        self.assertEqual(self.gen.default_for_annotation("list[int]"), "[42]")

    def test_list_str(self) -> None:
        self.assertEqual(self.gen.default_for_annotation("list[str]"), '["hello"]')

    def test_List_int_capital(self) -> None:
        self.assertEqual(self.gen.default_for_annotation("List[int]"), "[42]")

    def test_tuple(self) -> None:
        self.assertEqual(self.gen.default_for_annotation("Tuple[int, int]"), "(42, 42)")

    def test_set_int(self) -> None:
        self.assertEqual(self.gen.default_for_annotation("Set[int]"), "{42}")

    def test_dict_str_int(self) -> None:
        self.assertEqual(
            self.gen.default_for_annotation("Dict[str, int]"),
            '{"hello": 42}',
        )

    def test_optional_int(self) -> None:
        self.assertEqual(self.gen.default_for_annotation("Optional[int]"), "42")

    def test_any(self) -> None:
        self.assertEqual(self.gen.default_for_annotation("Any"), "None")

    def test_none_annotation(self) -> None:
        self.assertEqual(self.gen.default_for_annotation(None), "None")

    def test_empty_annotation(self) -> None:
        self.assertEqual(self.gen.default_for_annotation(""), "None")

    def test_unknown_annotation(self) -> None:
        self.assertEqual(self.gen.default_for_annotation("CustomType"), "None")

    def test_generate_variables(self) -> None:
        params = [
            PlannedParameter(name="nums", annotation="list[int]"),
            PlannedParameter(name="target", annotation="int"),
        ]
        variables = self.gen.generate_variables(params)
        self.assertEqual(len(variables), 2)
        self.assertEqual(variables[0].name, "nums")
        self.assertEqual(variables[0].value, "[42]")
        self.assertEqual(variables[1].name, "target")
        self.assertEqual(variables[1].value, "42")


# =============================================================================
# Test: TemplateRenderer
# =============================================================================


class TestTemplateRenderer(unittest.TestCase):

    r = TemplateRenderer()

    def test_render_imports(self) -> None:
        result = self.r.render_imports(["asyncio"])
        self.assertEqual(result, "import asyncio\n")

    def test_render_no_imports(self) -> None:
        self.assertEqual(self.r.render_imports([]), "")

    def test_render_variables(self) -> None:
        result = self.r.render_variables([("x", "42"), ("y", '"hello"')])
        self.assertEqual(result, 'x = 42\ny = "hello"\n')

    def test_render_instantiation(self) -> None:
        result = self.r.render_instantiation("Solution", "solution")
        self.assertEqual(result, "solution = Solution()\n")

    def test_render_call_simple(self) -> None:
        result = self.r.render_call("solve", ["n"])
        self.assertEqual(result, "result = solve(n)\n")

    def test_render_call_with_receiver(self) -> None:
        result = self.r.render_call("twoSum", ["nums", "target"], receiver="solution")
        self.assertEqual(result, "result = solution.twoSum(nums, target)\n")

    def test_render_call_async(self) -> None:
        result = self.r.render_call("fetch", ["url"], is_async=True)
        self.assertEqual(result, "result = asyncio.run(fetch(url))\n")

    def test_render_print(self) -> None:
        self.assertEqual(self.r.render_print(), "print(result)\n")


# =============================================================================
# Test: Top-level function
# =============================================================================


class TestTopLevelFunction(unittest.TestCase):

    def test_simple_function(self) -> None:
        plan = _make_plan(
            entry_function="solve",
            parameters=[PlannedParameter(name="n", annotation="int")],
        )
        result = WrapperGenerator.create(plan)
        expected = textwrap.dedent("""\
            n = 42

            result = solve(n)

            print(result)
        """)
        self.assertEqual(result.source_code, expected)

    def test_no_parameters(self) -> None:
        plan = _make_plan(entry_function="run")
        result = WrapperGenerator.create(plan)
        self.assertIn("result = run()", result.source_code)
        self.assertIn("print(result)", result.source_code)

    def test_multiple_parameters(self) -> None:
        plan = _make_plan(
            entry_function="add",
            parameters=[
                PlannedParameter(name="a", annotation="int"),
                PlannedParameter(name="b", annotation="int"),
            ],
        )
        result = WrapperGenerator.create(plan)
        self.assertIn("a = 42", result.source_code)
        self.assertIn("b = 42", result.source_code)
        self.assertIn("result = add(a, b)", result.source_code)


# =============================================================================
# Test: Instance method (CLASS_METHOD)
# =============================================================================


class TestInstanceMethod(unittest.TestCase):

    def test_instance_method(self) -> None:
        plan = _make_plan(
            entry_function="twoSum",
            call_type=CallType.CLASS_METHOD,
            entry_class="Solution",
            parameters=[
                PlannedParameter(name="nums", annotation="list[int]"),
                PlannedParameter(name="target", annotation="int"),
            ],
        )
        result = WrapperGenerator.create(plan)
        expected = textwrap.dedent("""\
            nums = [42]
            target = 42

            solution = Solution()

            result = solution.twoSum(nums, target)

            print(result)
        """)
        self.assertEqual(result.source_code, expected)

    def test_instance_var_name(self) -> None:
        """Variable name is lowercase first letter of class."""
        plan = _make_plan(
            entry_function="run",
            call_type=CallType.CLASS_METHOD,
            entry_class="MyService",
        )
        result = WrapperGenerator.create(plan)
        self.assertIn("myService = MyService()", result.source_code)


# =============================================================================
# Test: Static method
# =============================================================================


class TestStaticMethod(unittest.TestCase):

    def test_static_method(self) -> None:
        plan = _make_plan(
            entry_function="add",
            call_type=CallType.STATIC_METHOD,
            entry_class="MathUtils",
            parameters=[
                PlannedParameter(name="a", annotation="int"),
                PlannedParameter(name="b", annotation="int"),
            ],
        )
        result = WrapperGenerator.create(plan)
        self.assertIn("result = MathUtils.add(a, b)", result.source_code)
        # No instantiation for static methods.
        self.assertNotIn("mathUtils = MathUtils()", result.source_code)


# =============================================================================
# Test: Class method (@classmethod)
# =============================================================================


class TestClassMethodDecorator(unittest.TestCase):

    def test_classmethod(self) -> None:
        plan = _make_plan(
            entry_function="create",
            call_type=CallType.CLASS_METHOD_DECORATOR,
            entry_class="Factory",
            parameters=[PlannedParameter(name="name", annotation="str")],
        )
        result = WrapperGenerator.create(plan)
        self.assertIn('name = "hello"', result.source_code)
        self.assertIn("result = Factory.create(name)", result.source_code)
        # No instantiation for classmethods.
        self.assertNotIn("factory = Factory()", result.source_code)


# =============================================================================
# Test: Async function
# =============================================================================


class TestAsyncFunction(unittest.TestCase):

    def test_async_function(self) -> None:
        plan = _make_plan(
            entry_function="fetch",
            call_type=CallType.ASYNC_FUNCTION,
            parameters=[PlannedParameter(name="url", annotation="str")],
        )
        result = WrapperGenerator.create(plan)
        expected = textwrap.dedent("""\
            import asyncio

            url = "hello"

            result = asyncio.run(fetch(url))

            print(result)
        """)
        self.assertEqual(result.source_code, expected)


# =============================================================================
# Test: Unknown annotation
# =============================================================================


class TestUnknownAnnotation(unittest.TestCase):

    def test_unknown_defaults_to_none(self) -> None:
        plan = _make_plan(
            entry_function="process",
            parameters=[PlannedParameter(name="data", annotation="DataFrame")],
        )
        result = WrapperGenerator.create(plan)
        self.assertIn("data = None", result.source_code)


# =============================================================================
# Test: Exceptions
# =============================================================================


class TestExceptions(unittest.TestCase):

    def test_none_plan_raises(self) -> None:
        with self.assertRaises(InvalidPlanError):
            WrapperGenerator(None).generate()  # type: ignore[arg-type]

    def test_empty_function_raises(self) -> None:
        plan = _make_plan(entry_function="")
        with self.assertRaises(InvalidPlanError):
            WrapperGenerator(plan).generate()

    def test_all_exceptions_inherit_wrapper_error(self) -> None:
        self.assertTrue(issubclass(InvalidPlanError, WrapperError))
        self.assertTrue(issubclass(WrapperError, Exception))


# =============================================================================
# Test: GeneratedSource is frozen
# =============================================================================


class TestFrozenDataclasses(unittest.TestCase):

    def test_generated_source_is_frozen(self) -> None:
        plan = _make_plan(entry_function="f")
        result = WrapperGenerator.create(plan)
        with self.assertRaises(AttributeError):
            result.source_code = "modified"  # type: ignore[misc]

    def test_generated_variable_is_frozen(self) -> None:
        plan = _make_plan(
            entry_function="f",
            parameters=[PlannedParameter(name="x", annotation="int")],
        )
        result = WrapperGenerator.create(plan)
        with self.assertRaises(AttributeError):
            result.variables[0].name = "changed"  # type: ignore[misc]


# =============================================================================
# Test: Full pipeline (Analyzer → Planner → Wrapper)
# =============================================================================


class TestFullPipeline(unittest.TestCase):
    """End-to-end: source code → analysis → plan → generated wrapper."""

    def test_solution_twosum(self) -> None:
        from analyzer import CodeAnalyzer
        from engine.planner import ExecutionPlanner

        source = textwrap.dedent("""\
            class Solution:
                def twoSum(self, nums: list[int], target: int) -> list[int]:
                    pass
        """)
        module_info = CodeAnalyzer(source).analyze()
        plan = ExecutionPlanner.create(module_info)
        result = WrapperGenerator.create(plan)

        self.assertIn("nums = [42]", result.source_code)
        self.assertIn("target = 42", result.source_code)
        self.assertIn("solution = Solution()", result.source_code)
        self.assertIn("result = solution.twoSum(nums, target)", result.source_code)
        self.assertIn("print(result)", result.source_code)


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
