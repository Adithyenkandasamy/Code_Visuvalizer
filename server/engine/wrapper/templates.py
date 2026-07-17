"""
templates.py — TemplateRenderer for the Wrapper Generator.

Produces formatted Python source-code blocks from plain values.
This class knows NOTHING about the planner or analyzer — it only
receives strings, lists, and booleans.
"""

from __future__ import annotations

from engine.wrapper.exceptions import TemplateRenderError


class TemplateRenderer:
    """
    Renders isolated Python code blocks and assembles them into
    a complete source string.

    Every public method returns a ``str`` fragment.  The ``render``
    method combines fragments into the final source.
    """

    # ── Individual Block Renderers ─────────────────────────────────────

    @staticmethod
    def render_imports(modules: list[str]) -> str:
        """
        Render import statements.

        Args:
            modules: Module names to import (e.g. ``["asyncio"]``).

        Returns:
            One ``import`` line per module, or empty string.
        """
        if not modules:
            return ""
        lines = [f"import {m}" for m in modules]
        return "\n".join(lines) + "\n"

    @staticmethod
    def render_variables(variables: list[tuple[str, str]]) -> str:
        """
        Render variable assignments.

        Args:
            variables: List of ``(name, value_literal)`` pairs.

        Returns:
            Assignment lines, e.g. ``nums = [2, 7, 11, 15]``.
        """
        if not variables:
            return ""
        lines = [f"{name} = {value}" for name, value in variables]
        return "\n".join(lines) + "\n"

    @staticmethod
    def render_instantiation(class_name: str, var_name: str) -> str:
        """
        Render a class instantiation line.

        Args:
            class_name: The class to instantiate.
            var_name:   The variable to assign to.

        Returns:
            e.g. ``solution = Solution()``
        """
        return f"{var_name} = {class_name}()\n"

    @staticmethod
    def render_call(
        func_name: str,
        arg_names: list[str],
        *,
        receiver: str | None = None,
        is_async: bool = False,
    ) -> str:
        """
        Render a function / method call with result capture.

        Args:
            func_name:  Function or method name.
            arg_names:  Argument variable names.
            receiver:   Object or class the method is called on (if any).
            is_async:   Wrap in ``asyncio.run(...)`` when ``True``.

        Returns:
            e.g. ``result = solution.twoSum(nums, target)``
        """
        args_str = ", ".join(arg_names)
        if receiver:
            call = f"{receiver}.{func_name}({args_str})"
        else:
            call = f"{func_name}({args_str})"

        if is_async:
            call = f"asyncio.run({call})"

        return f"result = {call}\n"

    @staticmethod
    def render_print() -> str:
        """Render the result-printing line."""
        return "print(result)\n"

    # ── Full Assembly ──────────────────────────────────────────────────

    @staticmethod
    def render(blocks: list[str]) -> str:
        """
        Assemble code blocks into a single source string.

        Inserts a blank line between non-empty blocks for readability.

        Args:
            blocks: Ordered list of code fragments.

        Returns:
            Complete Python source string.

        Raises:
            TemplateRenderError: If no blocks produce any content.
        """
        non_empty = [b for b in blocks if b.strip()]
        if not non_empty:
            raise TemplateRenderError("No code blocks to render.")
        return "\n".join(non_empty) + "\n"
