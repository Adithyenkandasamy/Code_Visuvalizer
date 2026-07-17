"""
analyzer.py — Static Python Source Code Analyzer

A production-ready module that uses Python's `ast` module to statically
analyze Python source code WITHOUT executing it. Extracts structural
information including imports, classes, functions, parameters, annotations,
decorators, and docstrings.

Requires Python 3.12+.

Usage:
    >>> from analyzer import CodeAnalyzer
    >>> source = '''
    ... def greet(name: str) -> str:
    ...     \"\"\"Return a greeting.\"\"\"
    ...     return f"Hello, {name}"
    ... '''
    >>> analyzer = CodeAnalyzer(source)
    >>> module_info = analyzer.analyze()
    >>> module_info.functions[0].name
    'greet'
"""

from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


# =============================================================================
# Custom Exceptions
# =============================================================================


class AnalyzerError(Exception):
    """Base exception for all analyzer-related errors."""


class InvalidSyntaxError(AnalyzerError):
    """
    Raised when the provided source code contains syntax errors
    and cannot be parsed into a valid AST.

    Attributes:
        message:  Human-readable description of the error.
        lineno:   Line number where the syntax error was detected (1-indexed).
        offset:   Column offset within the line (1-indexed), if available.
        text:     The source line that triggered the error, if available.
    """

    def __init__(
        self,
        message: str,
        lineno: int | None = None,
        offset: int | None = None,
        text: str | None = None,
    ) -> None:
        self.lineno = lineno
        self.offset = offset
        self.text = text
        # Build a rich, informative error string.
        parts: list[str] = [message]
        if lineno is not None:
            parts.append(f"line {lineno}")
        if offset is not None:
            parts.append(f"column {offset}")
        if text is not None:
            parts.append(f"near: {text.strip()!r}")
        super().__init__(" | ".join(parts))


class EmptySourceError(AnalyzerError):
    """Raised when the provided source string is empty or whitespace-only."""


# =============================================================================
# Enumerations
# =============================================================================


class ParameterKind(Enum):
    """
    Mirrors the parameter kinds found in Python function signatures.

    POSITIONAL_ONLY      — before the `/` separator
    POSITIONAL_OR_KEYWORD — normal parameters (most common)
    VAR_POSITIONAL       — *args
    KEYWORD_ONLY         — after the `*` separator
    VAR_KEYWORD          — **kwargs
    """

    POSITIONAL_ONLY = auto()
    POSITIONAL_OR_KEYWORD = auto()
    VAR_POSITIONAL = auto()
    KEYWORD_ONLY = auto()
    VAR_KEYWORD = auto()


class ImportKind(Enum):
    """Distinguishes between `import X` and `from X import Y`."""

    IMPORT = auto()
    FROM_IMPORT = auto()


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True, slots=True)
class ImportInfo:
    """
    Represents a single import statement.

    Attributes:
        module:  The module being imported (e.g. ``os.path``).
                 For ``import X``, this is ``X``.
                 For ``from X import Y``, this is ``X``.
        name:    The specific name imported (``Y`` in ``from X import Y``).
                 ``None`` for plain ``import X`` statements.
        alias:   The alias if ``as`` is used (e.g. ``import numpy as np`` → ``np``).
        kind:    Whether this is a plain import or a from-import.
        lineno:  Source line number (1-indexed).
    """

    module: str
    name: str | None = None
    alias: str | None = None
    kind: ImportKind = ImportKind.IMPORT
    lineno: int = 0


@dataclass(frozen=True, slots=True)
class ParameterInfo:
    """
    Represents a single parameter in a function/method signature.

    Attributes:
        name:          The parameter name.
        annotation:    String representation of the type annotation, or ``None``.
        default_value: String representation of the default value, or ``None``.
        kind:          The parameter kind (positional-only, keyword-only, etc.).
    """

    name: str
    annotation: str | None = None
    default_value: str | None = None
    kind: ParameterKind = ParameterKind.POSITIONAL_OR_KEYWORD


@dataclass(frozen=True, slots=True)
class FunctionInfo:
    """
    Represents a function or method definition.

    Attributes:
        name:              The function/method name.
        parameters:        Ordered list of ``ParameterInfo`` objects.
        return_annotation: String representation of the return type, or ``None``.
        decorators:        List of decorator strings (e.g. ``["staticmethod", "cache"]``).
        docstring:         The function's docstring, or ``None``.
        is_async:          ``True`` if declared with ``async def``.
        is_method:         ``True`` if nested directly inside a class body.
        lineno:            Start line in source (1-indexed).
        end_lineno:        End line in source (1-indexed), or ``None``.
    """

    name: str
    parameters: list[ParameterInfo] = field(default_factory=list)
    return_annotation: str | None = None
    decorators: list[str] = field(default_factory=list)
    docstring: str | None = None
    is_async: bool = False
    is_method: bool = False
    lineno: int = 0
    end_lineno: int | None = None


@dataclass(frozen=True, slots=True)
class ClassInfo:
    """
    Represents a class definition.

    Attributes:
        name:        The class name.
        bases:       List of base-class strings (e.g. ``["Base", "MixinA"]``).
        methods:     List of ``FunctionInfo`` objects defined in the class body.
        decorators:  List of decorator strings.
        docstring:   The class's docstring, or ``None``.
        lineno:      Start line in source (1-indexed).
        end_lineno:  End line in source (1-indexed), or ``None``.
    """

    name: str
    bases: list[str] = field(default_factory=list)
    methods: list[FunctionInfo] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    docstring: str | None = None
    lineno: int = 0
    end_lineno: int | None = None


@dataclass(frozen=True, slots=True)
class ModuleInfo:
    """
    Top-level container for all analysis results of a Python module.

    Attributes:
        imports:      All import statements found at module level.
        classes:      All class definitions found at module level.
        functions:    All function definitions found at module level
                      (excludes methods inside classes).
        docstring:    The module-level docstring, or ``None``.
        source_lines: Total number of source lines.
    """

    imports: list[ImportInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    docstring: str | None = None
    source_lines: int = 0


# =============================================================================
# AST Helper Utilities
# =============================================================================


def _unparse_node(node: ast.expr | None) -> str | None:
    """
    Convert an AST expression node back into its source-code string.

    Uses ``ast.unparse`` (available since Python 3.9) to reconstruct
    a human-readable representation.  Returns ``None`` when ``node``
    is ``None``.
    """
    if node is None:
        return None
    return ast.unparse(node)


def _extract_decorator_name(node: ast.expr) -> str:
    """
    Extract a readable decorator string from a decorator AST node.

    Handles the following decorator forms:
        @decorator              → "decorator"
        @module.decorator       → "module.decorator"
        @decorator(args)        → "decorator(args)"
        @module.decorator(args) → "module.decorator(args)"
    """
    return ast.unparse(node)


def _extract_docstring(node: ast.AST) -> str | None:
    """
    Extract the docstring from a module, class, or function AST node.

    A docstring is defined as the first statement in the body that is
    an ``ast.Expr`` containing an ``ast.Constant`` with a ``str`` value.
    Returns ``None`` if no docstring is present.
    """
    # Guard: the node must have a body attribute with at least one statement.
    body: list[ast.stmt] = getattr(node, "body", [])
    if not body:
        return None

    first_stmt = body[0]
    if (
        isinstance(first_stmt, ast.Expr)
        and isinstance(first_stmt.value, ast.Constant)
        and isinstance(first_stmt.value.value, str)
    ):
        return first_stmt.value.value
    return None


# =============================================================================
# Parameter Extraction
# =============================================================================


def _classify_parameters(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ParameterInfo]:
    """
    Extract and classify all parameters from a function definition node.

    Python function signatures have five zones, separated by ``/`` and ``*``:

        def f(pos_only, /, normal, *, kw_only, **kwargs): ...

    This function maps each parameter to the correct ``ParameterKind``
    and extracts its annotation and default value (if any).
    """
    args: ast.arguments = func_node.args
    params: list[ParameterInfo] = []

    # ── Helper: build a ParameterInfo from an ast.arg ──────────────────
    def _make_param(
        arg: ast.arg,
        default: ast.expr | None,
        kind: ParameterKind,
    ) -> ParameterInfo:
        return ParameterInfo(
            name=arg.arg,
            annotation=_unparse_node(arg.annotation),
            default_value=_unparse_node(default),
            kind=kind,
        )

    # ── 1. Positional-only parameters (before `/`) ─────────────────────
    # Defaults for positional-only params are stored at the *end* of
    # ``args.defaults``, shared with positional-or-keyword params.
    # We need to align them carefully.
    posonlyargs = args.posonlyargs
    regular_args = args.args
    all_positional = posonlyargs + regular_args
    defaults = args.defaults  # shared across posonlyargs + args
    # Pad defaults with None so they align 1-to-1 with all_positional.
    num_no_default = len(all_positional) - len(defaults)
    padded_defaults: list[ast.expr | None] = [None] * num_no_default + list(defaults)

    for i, arg in enumerate(posonlyargs):
        params.append(
            _make_param(arg, padded_defaults[i], ParameterKind.POSITIONAL_ONLY)
        )

    # ── 2. Positional-or-keyword parameters ────────────────────────────
    for i, arg in enumerate(regular_args):
        idx = len(posonlyargs) + i
        params.append(
            _make_param(arg, padded_defaults[idx], ParameterKind.POSITIONAL_OR_KEYWORD)
        )

    # ── 3. *args (variadic positional) ─────────────────────────────────
    if args.vararg is not None:
        params.append(
            ParameterInfo(
                name=args.vararg.arg,
                annotation=_unparse_node(args.vararg.annotation),
                default_value=None,
                kind=ParameterKind.VAR_POSITIONAL,
            )
        )

    # ── 4. Keyword-only parameters (after `*` or `*args`) ─────────────
    kw_defaults = args.kw_defaults  # same length as kwonlyargs; None = no default
    for arg, default in zip(args.kwonlyargs, kw_defaults):
        params.append(
            _make_param(arg, default, ParameterKind.KEYWORD_ONLY)
        )

    # ── 5. **kwargs (variadic keyword) ─────────────────────────────────
    if args.kwarg is not None:
        params.append(
            ParameterInfo(
                name=args.kwarg.arg,
                annotation=_unparse_node(args.kwarg.annotation),
                default_value=None,
                kind=ParameterKind.VAR_KEYWORD,
            )
        )

    return params


# =============================================================================
# Node Visitors
# =============================================================================


def _analyze_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    is_method: bool = False,
) -> FunctionInfo:
    """
    Analyze a single function/method AST node and return a ``FunctionInfo``.

    Parameters:
        node:      The ``FunctionDef`` or ``AsyncFunctionDef`` AST node.
        is_method: Pass ``True`` when the function is defined inside a class body.
    """
    return FunctionInfo(
        name=node.name,
        parameters=_classify_parameters(node),
        return_annotation=_unparse_node(node.returns),
        decorators=[_extract_decorator_name(d) for d in node.decorator_list],
        docstring=_extract_docstring(node),
        is_async=isinstance(node, ast.AsyncFunctionDef),
        is_method=is_method,
        lineno=node.lineno,
        end_lineno=node.end_lineno,
    )


def _analyze_class(node: ast.ClassDef) -> ClassInfo:
    """
    Analyze a single class AST node and return a ``ClassInfo``.

    Iterates over the class body to discover methods (both sync and async).
    Only direct children of the class body are considered methods.
    """
    methods: list[FunctionInfo] = []
    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(_analyze_function(child, is_method=True))

    return ClassInfo(
        name=node.name,
        bases=[ast.unparse(base) for base in node.bases],
        methods=methods,
        decorators=[_extract_decorator_name(d) for d in node.decorator_list],
        docstring=_extract_docstring(node),
        lineno=node.lineno,
        end_lineno=node.end_lineno,
    )


def _analyze_imports(node: ast.Import | ast.ImportFrom) -> list[ImportInfo]:
    """
    Analyze an import statement and return one ``ImportInfo`` per imported name.

    ``import os, sys`` produces two ``ImportInfo`` objects.
    ``from os.path import join, exists`` also produces two.
    """
    results: list[ImportInfo] = []

    if isinstance(node, ast.Import):
        # ``import X, Y as Z``
        for alias in node.names:
            results.append(
                ImportInfo(
                    module=alias.name,
                    name=None,
                    alias=alias.asname,
                    kind=ImportKind.IMPORT,
                    lineno=node.lineno,
                )
            )
    elif isinstance(node, ast.ImportFrom):
        # ``from X import Y, Z as W``
        module_name = node.module or ""
        for alias in node.names:
            results.append(
                ImportInfo(
                    module=module_name,
                    name=alias.name,
                    alias=alias.asname,
                    kind=ImportKind.FROM_IMPORT,
                    lineno=node.lineno,
                )
            )

    return results


# =============================================================================
# Main Analyzer
# =============================================================================


class CodeAnalyzer:
    """
    Static analyzer for Python source code.

    Parses the source into an AST and extracts structural metadata
    without ever executing the code.

    Usage:
        >>> analyzer = CodeAnalyzer("def foo(): pass")
        >>> info = analyzer.analyze()
        >>> info.functions[0].name
        'foo'

    Attributes:
        source:  The raw Python source string.
        _tree:   The parsed AST (populated after ``_parse()``).
    """

    def __init__(self, source: str) -> None:
        """
        Initialize the analyzer with Python source code.

        Args:
            source: A string containing valid Python source code.

        Raises:
            EmptySourceError: If ``source`` is empty or whitespace-only.
        """
        if not source or not source.strip():
            raise EmptySourceError("Source code must not be empty or whitespace-only.")

        # Dedent to handle code blocks that might be indented (e.g. from docstrings).
        self.source: str = textwrap.dedent(source)
        self._tree: ast.Module | None = None

    # ── Parsing ────────────────────────────────────────────────────────

    def _parse(self) -> ast.Module:
        """
        Parse the source string into an AST.

        Returns:
            The root ``ast.Module`` node.

        Raises:
            InvalidSyntaxError: If the source contains a syntax error.
        """
        try:
            tree = ast.parse(self.source, mode="exec", type_comments=True)
        except SyntaxError as exc:
            raise InvalidSyntaxError(
                message=exc.msg if exc.msg else "Invalid syntax",
                lineno=exc.lineno,
                offset=exc.offset,
                text=exc.text,
            ) from exc
        return tree

    # ── Public API ─────────────────────────────────────────────────────

    def analyze(self) -> ModuleInfo:
        """
        Perform full static analysis and return a ``ModuleInfo``.

        This is the primary entry point.  It parses the source (if not
        already parsed), walks the top-level statements, and collects
        imports, classes, and functions.

        Returns:
            A ``ModuleInfo`` dataclass containing all extracted metadata.

        Raises:
            InvalidSyntaxError: If the source code cannot be parsed.
        """
        tree = self._parse()
        self._tree = tree

        imports: list[ImportInfo] = []
        classes: list[ClassInfo] = []
        functions: list[FunctionInfo] = []

        # Walk only the top-level statements of the module.
        # Nested definitions (functions inside functions, classes inside
        # functions, etc.) are intentionally ignored at the module level
        # to keep the output clean and predictable.
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.extend(_analyze_imports(node))
            elif isinstance(node, ast.ClassDef):
                classes.append(_analyze_class(node))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(_analyze_function(node, is_method=False))

        return ModuleInfo(
            imports=imports,
            classes=classes,
            functions=functions,
            docstring=_extract_docstring(tree),
            source_lines=self.source.count("\n") + 1,
        )
