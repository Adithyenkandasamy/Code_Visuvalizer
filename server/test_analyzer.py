"""
test_analyzer.py — Comprehensive Unit Tests for the Static Code Analyzer

Run with:
    python -m pytest test_analyzer.py -v

Or directly:
    python test_analyzer.py
"""

from __future__ import annotations

import textwrap
import unittest

from analyzer import (
    AnalyzerError,
    ClassInfo,
    CodeAnalyzer,
    EmptySourceError,
    FunctionInfo,
    ImportInfo,
    ImportKind,
    InvalidSyntaxError,
    ModuleInfo,
    ParameterInfo,
    ParameterKind,
)


# =============================================================================
# Test: Custom Exceptions
# =============================================================================


class TestExceptions(unittest.TestCase):
    """Verify that custom exceptions are raised for invalid inputs."""

    def test_invalid_syntax_raises(self) -> None:
        """Malformed Python code must raise InvalidSyntaxError."""
        source = "def broken(:"
        with self.assertRaises(InvalidSyntaxError) as ctx:
            CodeAnalyzer(source).analyze()
        exc = ctx.exception
        self.assertIsNotNone(exc.lineno)
        # Ensure the exception message contains useful location info.
        self.assertIn("line", str(exc))

    def test_invalid_syntax_preserves_details(self) -> None:
        """InvalidSyntaxError should carry lineno, offset, and text."""
        source = "x = 1 +\n"
        with self.assertRaises(InvalidSyntaxError) as ctx:
            CodeAnalyzer(source).analyze()
        exc = ctx.exception
        self.assertIsNotNone(exc.lineno)

    def test_empty_source_raises(self) -> None:
        """Empty source code must raise EmptySourceError."""
        with self.assertRaises(EmptySourceError):
            CodeAnalyzer("").analyze()

    def test_whitespace_only_source_raises(self) -> None:
        """Whitespace-only source code must raise EmptySourceError."""
        with self.assertRaises(EmptySourceError):
            CodeAnalyzer("   \n\t\n  ").analyze()

    def test_exceptions_inherit_from_analyzer_error(self) -> None:
        """All custom exceptions must be subclasses of AnalyzerError."""
        self.assertTrue(issubclass(InvalidSyntaxError, AnalyzerError))
        self.assertTrue(issubclass(EmptySourceError, AnalyzerError))


# =============================================================================
# Test: Module-Level Docstrings
# =============================================================================


class TestModuleDocstring(unittest.TestCase):
    """Verify extraction of module-level docstrings."""

    def test_module_docstring_extracted(self) -> None:
        source = '"""This is the module docstring."""\n\nx = 1\n'
        info = CodeAnalyzer(source).analyze()
        self.assertEqual(info.docstring, "This is the module docstring.")

    def test_module_without_docstring(self) -> None:
        source = "x = 1\ny = 2\n"
        info = CodeAnalyzer(source).analyze()
        self.assertIsNone(info.docstring)

    def test_source_lines_counted(self) -> None:
        source = "a = 1\nb = 2\nc = 3\n"
        info = CodeAnalyzer(source).analyze()
        self.assertGreaterEqual(info.source_lines, 3)


# =============================================================================
# Test: Imports
# =============================================================================


class TestImports(unittest.TestCase):
    """Verify extraction of import statements."""

    def test_plain_import(self) -> None:
        source = "import os\n"
        info = CodeAnalyzer(source).analyze()
        self.assertEqual(len(info.imports), 1)
        imp = info.imports[0]
        self.assertEqual(imp.module, "os")
        self.assertIsNone(imp.name)
        self.assertIsNone(imp.alias)
        self.assertEqual(imp.kind, ImportKind.IMPORT)

    def test_import_with_alias(self) -> None:
        source = "import numpy as np\n"
        info = CodeAnalyzer(source).analyze()
        imp = info.imports[0]
        self.assertEqual(imp.module, "numpy")
        self.assertEqual(imp.alias, "np")

    def test_from_import(self) -> None:
        source = "from os.path import join, exists\n"
        info = CodeAnalyzer(source).analyze()
        self.assertEqual(len(info.imports), 2)
        self.assertEqual(info.imports[0].module, "os.path")
        self.assertEqual(info.imports[0].name, "join")
        self.assertEqual(info.imports[1].name, "exists")
        self.assertTrue(all(i.kind == ImportKind.FROM_IMPORT for i in info.imports))

    def test_from_import_with_alias(self) -> None:
        source = "from collections import OrderedDict as OD\n"
        info = CodeAnalyzer(source).analyze()
        imp = info.imports[0]
        self.assertEqual(imp.name, "OrderedDict")
        self.assertEqual(imp.alias, "OD")

    def test_multiple_imports(self) -> None:
        source = "import os, sys\n"
        info = CodeAnalyzer(source).analyze()
        self.assertEqual(len(info.imports), 2)
        self.assertEqual(info.imports[0].module, "os")
        self.assertEqual(info.imports[1].module, "sys")


# =============================================================================
# Test: Functions
# =============================================================================


class TestFunctions(unittest.TestCase):
    """Verify extraction of function definitions."""

    def test_simple_function(self) -> None:
        source = "def hello():\n    pass\n"
        info = CodeAnalyzer(source).analyze()
        self.assertEqual(len(info.functions), 1)
        fn = info.functions[0]
        self.assertEqual(fn.name, "hello")
        self.assertEqual(fn.parameters, [])
        self.assertFalse(fn.is_async)
        self.assertFalse(fn.is_method)

    def test_function_with_docstring(self) -> None:
        source = textwrap.dedent('''\
            def greet(name):
                """Say hello to someone."""
                print(f"Hello, {name}")
        ''')
        info = CodeAnalyzer(source).analyze()
        fn = info.functions[0]
        self.assertEqual(fn.docstring, "Say hello to someone.")

    def test_function_return_annotation(self) -> None:
        source = "def add(a: int, b: int) -> int:\n    return a + b\n"
        info = CodeAnalyzer(source).analyze()
        fn = info.functions[0]
        self.assertEqual(fn.return_annotation, "int")

    def test_async_function(self) -> None:
        source = "async def fetch(url: str) -> bytes:\n    pass\n"
        info = CodeAnalyzer(source).analyze()
        fn = info.functions[0]
        self.assertTrue(fn.is_async)
        self.assertEqual(fn.name, "fetch")
        self.assertEqual(fn.return_annotation, "bytes")

    def test_function_line_numbers(self) -> None:
        source = "\n\ndef foo():\n    pass\n"
        info = CodeAnalyzer(source).analyze()
        fn = info.functions[0]
        self.assertEqual(fn.lineno, 3)
        self.assertIsNotNone(fn.end_lineno)


# =============================================================================
# Test: Parameters
# =============================================================================


class TestParameters(unittest.TestCase):
    """Verify extraction and classification of function parameters."""

    def test_annotated_parameters(self) -> None:
        source = "def f(x: int, y: str = 'hi') -> bool:\n    pass\n"
        info = CodeAnalyzer(source).analyze()
        params = info.functions[0].parameters
        self.assertEqual(len(params), 2)
        # First param: x: int, no default
        self.assertEqual(params[0].name, "x")
        self.assertEqual(params[0].annotation, "int")
        self.assertIsNone(params[0].default_value)
        # Second param: y: str = 'hi'
        self.assertEqual(params[1].name, "y")
        self.assertEqual(params[1].annotation, "str")
        self.assertIsNotNone(params[1].default_value)

    def test_positional_only_params(self) -> None:
        source = "def f(a, b, /, c):\n    pass\n"
        info = CodeAnalyzer(source).analyze()
        params = info.functions[0].parameters
        self.assertEqual(params[0].kind, ParameterKind.POSITIONAL_ONLY)
        self.assertEqual(params[1].kind, ParameterKind.POSITIONAL_ONLY)
        self.assertEqual(params[2].kind, ParameterKind.POSITIONAL_OR_KEYWORD)

    def test_keyword_only_params(self) -> None:
        source = "def f(a, *, key: str, flag: bool = True):\n    pass\n"
        info = CodeAnalyzer(source).analyze()
        params = info.functions[0].parameters
        # `a` is POSITIONAL_OR_KEYWORD
        self.assertEqual(params[0].kind, ParameterKind.POSITIONAL_OR_KEYWORD)
        # `key` and `flag` are KEYWORD_ONLY
        self.assertEqual(params[1].kind, ParameterKind.KEYWORD_ONLY)
        self.assertEqual(params[2].kind, ParameterKind.KEYWORD_ONLY)

    def test_var_positional_and_keyword(self) -> None:
        source = "def f(*args, **kwargs):\n    pass\n"
        info = CodeAnalyzer(source).analyze()
        params = info.functions[0].parameters
        self.assertEqual(len(params), 2)
        self.assertEqual(params[0].name, "args")
        self.assertEqual(params[0].kind, ParameterKind.VAR_POSITIONAL)
        self.assertEqual(params[1].name, "kwargs")
        self.assertEqual(params[1].kind, ParameterKind.VAR_KEYWORD)

    def test_complex_signature(self) -> None:
        """Test a function with all five parameter kinds."""
        source = "def f(a, /, b, *args, c, **kwargs):\n    pass\n"
        info = CodeAnalyzer(source).analyze()
        params = info.functions[0].parameters
        self.assertEqual(len(params), 5)
        self.assertEqual(params[0].kind, ParameterKind.POSITIONAL_ONLY)       # a
        self.assertEqual(params[1].kind, ParameterKind.POSITIONAL_OR_KEYWORD)  # b
        self.assertEqual(params[2].kind, ParameterKind.VAR_POSITIONAL)         # *args
        self.assertEqual(params[3].kind, ParameterKind.KEYWORD_ONLY)           # c
        self.assertEqual(params[4].kind, ParameterKind.VAR_KEYWORD)            # **kwargs

    def test_annotated_args_kwargs(self) -> None:
        source = "def f(*args: int, **kwargs: str):\n    pass\n"
        info = CodeAnalyzer(source).analyze()
        params = info.functions[0].parameters
        self.assertEqual(params[0].annotation, "int")
        self.assertEqual(params[1].annotation, "str")


# =============================================================================
# Test: Decorators
# =============================================================================


class TestDecorators(unittest.TestCase):
    """Verify extraction of decorators on functions and classes."""

    def test_function_decorator(self) -> None:
        source = "@staticmethod\ndef f():\n    pass\n"
        info = CodeAnalyzer(source).analyze()
        fn = info.functions[0]
        self.assertEqual(fn.decorators, ["staticmethod"])

    def test_multiple_decorators(self) -> None:
        source = "@decorator_a\n@decorator_b(arg)\ndef f():\n    pass\n"
        info = CodeAnalyzer(source).analyze()
        fn = info.functions[0]
        self.assertEqual(len(fn.decorators), 2)
        self.assertEqual(fn.decorators[0], "decorator_a")
        self.assertIn("decorator_b", fn.decorators[1])

    def test_class_decorator(self) -> None:
        source = "@dataclass(frozen=True)\nclass Foo:\n    x: int = 0\n"
        info = CodeAnalyzer(source).analyze()
        cls = info.classes[0]
        self.assertEqual(len(cls.decorators), 1)
        self.assertIn("dataclass", cls.decorators[0])

    def test_dotted_decorator(self) -> None:
        source = "@app.route('/home')\ndef index():\n    pass\n"
        info = CodeAnalyzer(source).analyze()
        fn = info.functions[0]
        self.assertIn("app.route", fn.decorators[0])


# =============================================================================
# Test: Classes
# =============================================================================


class TestClasses(unittest.TestCase):
    """Verify extraction of class definitions."""

    def test_simple_class(self) -> None:
        source = textwrap.dedent('''\
            class Animal:
                """Represents an animal."""

                def speak(self) -> str:
                    """Make a sound."""
                    return "..."
        ''')
        info = CodeAnalyzer(source).analyze()
        self.assertEqual(len(info.classes), 1)
        cls = info.classes[0]
        self.assertEqual(cls.name, "Animal")
        self.assertEqual(cls.docstring, "Represents an animal.")
        self.assertEqual(len(cls.methods), 1)
        method = cls.methods[0]
        self.assertEqual(method.name, "speak")
        self.assertTrue(method.is_method)
        self.assertEqual(method.return_annotation, "str")

    def test_class_with_bases(self) -> None:
        source = "class Dog(Animal, Serializable):\n    pass\n"
        info = CodeAnalyzer(source).analyze()
        cls = info.classes[0]
        self.assertEqual(cls.bases, ["Animal", "Serializable"])

    def test_class_multiple_methods(self) -> None:
        source = textwrap.dedent('''\
            class Calculator:
                def add(self, a: int, b: int) -> int:
                    return a + b

                def subtract(self, a: int, b: int) -> int:
                    return a - b

                async def compute(self) -> None:
                    pass
        ''')
        info = CodeAnalyzer(source).analyze()
        cls = info.classes[0]
        self.assertEqual(len(cls.methods), 3)
        names = [m.name for m in cls.methods]
        self.assertIn("add", names)
        self.assertIn("subtract", names)
        self.assertIn("compute", names)
        # Verify async method
        compute = next(m for m in cls.methods if m.name == "compute")
        self.assertTrue(compute.is_async)
        self.assertTrue(compute.is_method)

    def test_class_not_in_functions(self) -> None:
        """Methods inside a class must NOT appear in module-level functions."""
        source = textwrap.dedent('''\
            class Foo:
                def bar(self):
                    pass

            def baz():
                pass
        ''')
        info = CodeAnalyzer(source).analyze()
        # Module-level functions should only contain `baz`.
        self.assertEqual(len(info.functions), 1)
        self.assertEqual(info.functions[0].name, "baz")
        # The class should contain `bar`.
        self.assertEqual(len(info.classes[0].methods), 1)
        self.assertEqual(info.classes[0].methods[0].name, "bar")


# =============================================================================
# Test: Complex / Real-World Source
# =============================================================================


class TestComplexSource(unittest.TestCase):
    """End-to-end tests with realistic Python source code."""

    SAMPLE_SOURCE = textwrap.dedent('''\
        """Sample module for testing the analyzer."""

        import os
        import sys
        from typing import Optional, List
        from pathlib import Path

        GLOBAL_CONST = 42


        @dataclass
        class Config:
            """Application configuration."""

            host: str = "localhost"
            port: int = 8080

            def url(self) -> str:
                """Build the full URL."""
                return f"http://{self.host}:{self.port}"


        class Server(Config):
            """A simple server class."""

            def __init__(self, name: str, /, *, debug: bool = False) -> None:
                self.name = name
                self.debug = debug

            @staticmethod
            def version() -> str:
                return "1.0.0"

            async def start(self) -> None:
                """Start the server."""
                pass


        def create_server(
            name: str,
            host: str = "0.0.0.0",
            port: int = 8080,
            *,
            debug: bool = False,
        ) -> Server:
            """Factory function to create a server."""
            pass
    ''')

    def setUp(self) -> None:
        self.info = CodeAnalyzer(self.SAMPLE_SOURCE).analyze()

    def test_module_docstring(self) -> None:
        self.assertEqual(self.info.docstring, "Sample module for testing the analyzer.")

    def test_import_count(self) -> None:
        # import os, import sys, from typing import Optional, List (2),
        # from pathlib import Path (1) → total = 5
        self.assertEqual(len(self.info.imports), 5)

    def test_class_count(self) -> None:
        self.assertEqual(len(self.info.classes), 2)

    def test_server_bases(self) -> None:
        server = next(c for c in self.info.classes if c.name == "Server")
        self.assertEqual(server.bases, ["Config"])

    def test_server_methods(self) -> None:
        server = next(c for c in self.info.classes if c.name == "Server")
        method_names = {m.name for m in server.methods}
        self.assertEqual(method_names, {"__init__", "version", "start"})

    def test_server_init_params(self) -> None:
        server = next(c for c in self.info.classes if c.name == "Server")
        init = next(m for m in server.methods if m.name == "__init__")
        # Parameters: self, name (pos-only), *, debug (kw-only)
        param_names = [p.name for p in init.parameters]
        self.assertIn("self", param_names)
        self.assertIn("name", param_names)
        self.assertIn("debug", param_names)
        # `name` should be POSITIONAL_ONLY
        name_param = next(p for p in init.parameters if p.name == "name")
        self.assertEqual(name_param.kind, ParameterKind.POSITIONAL_ONLY)
        # `debug` should be KEYWORD_ONLY
        debug_param = next(p for p in init.parameters if p.name == "debug")
        self.assertEqual(debug_param.kind, ParameterKind.KEYWORD_ONLY)

    def test_static_method_decorator(self) -> None:
        server = next(c for c in self.info.classes if c.name == "Server")
        version = next(m for m in server.methods if m.name == "version")
        self.assertIn("staticmethod", version.decorators)

    def test_async_method_detected(self) -> None:
        server = next(c for c in self.info.classes if c.name == "Server")
        start = next(m for m in server.methods if m.name == "start")
        self.assertTrue(start.is_async)
        self.assertEqual(start.docstring, "Start the server.")

    def test_factory_function(self) -> None:
        fn = next(f for f in self.info.functions if f.name == "create_server")
        self.assertEqual(fn.return_annotation, "Server")
        self.assertEqual(fn.docstring, "Factory function to create a server.")
        # Check keyword-only param
        debug_param = next(p for p in fn.parameters if p.name == "debug")
        self.assertEqual(debug_param.kind, ParameterKind.KEYWORD_ONLY)

    def test_module_level_function_count(self) -> None:
        """Only top-level functions, not class methods."""
        self.assertEqual(len(self.info.functions), 1)


# =============================================================================
# Test: Dataclass Immutability
# =============================================================================


class TestDataclassProperties(unittest.TestCase):
    """Verify that dataclass instances are frozen (immutable)."""

    def test_function_info_is_frozen(self) -> None:
        source = "def f(): pass\n"
        info = CodeAnalyzer(source).analyze()
        with self.assertRaises(AttributeError):
            info.functions[0].name = "changed"  # type: ignore[misc]

    def test_parameter_info_is_frozen(self) -> None:
        source = "def f(x: int): pass\n"
        info = CodeAnalyzer(source).analyze()
        with self.assertRaises(AttributeError):
            info.functions[0].parameters[0].name = "changed"  # type: ignore[misc]

    def test_class_info_is_frozen(self) -> None:
        source = "class Foo: pass\n"
        info = CodeAnalyzer(source).analyze()
        with self.assertRaises(AttributeError):
            info.classes[0].name = "changed"  # type: ignore[misc]

    def test_module_info_is_frozen(self) -> None:
        source = "x = 1\n"
        info = CodeAnalyzer(source).analyze()
        with self.assertRaises(AttributeError):
            info.docstring = "modified"  # type: ignore[misc]


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestEdgeCases(unittest.TestCase):
    """Cover boundary conditions and unusual but valid Python code."""

    def test_function_no_body_docstring(self) -> None:
        """A function with `pass` as its only body statement has no docstring."""
        source = "def f():\n    pass\n"
        info = CodeAnalyzer(source).analyze()
        self.assertIsNone(info.functions[0].docstring)

    def test_class_with_no_methods(self) -> None:
        source = "class Empty:\n    pass\n"
        info = CodeAnalyzer(source).analyze()
        cls = info.classes[0]
        self.assertEqual(cls.methods, [])
        self.assertEqual(cls.bases, [])

    def test_nested_class_ignored_at_module_level(self) -> None:
        """Classes nested inside functions should not appear at module level."""
        source = textwrap.dedent('''\
            def factory():
                class Inner:
                    pass
                return Inner
        ''')
        info = CodeAnalyzer(source).analyze()
        self.assertEqual(len(info.classes), 0)
        self.assertEqual(len(info.functions), 1)

    def test_lambda_not_extracted(self) -> None:
        """Lambda expressions are not function definitions."""
        source = "double = lambda x: x * 2\n"
        info = CodeAnalyzer(source).analyze()
        self.assertEqual(len(info.functions), 0)

    def test_complex_annotations(self) -> None:
        """Type annotations with generics should be preserved as strings."""
        source = "def f(items: list[dict[str, int]]) -> Optional[str]:\n    pass\n"
        info = CodeAnalyzer(source).analyze()
        param = info.functions[0].parameters[0]
        self.assertEqual(param.annotation, "list[dict[str, int]]")
        self.assertEqual(info.functions[0].return_annotation, "Optional[str]")

    def test_multiline_decorator(self) -> None:
        source = textwrap.dedent('''\
            @app.route(
                '/api/v1/data',
                methods=['GET', 'POST']
            )
            def endpoint():
                pass
        ''')
        info = CodeAnalyzer(source).analyze()
        self.assertEqual(len(info.functions[0].decorators), 1)
        self.assertIn("app.route", info.functions[0].decorators[0])

    def test_from_import_star(self) -> None:
        """from module import * should be captured."""
        source = "from os.path import *\n"
        info = CodeAnalyzer(source).analyze()
        self.assertEqual(len(info.imports), 1)
        self.assertEqual(info.imports[0].name, "*")


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
