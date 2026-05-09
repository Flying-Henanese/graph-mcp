"""
AST Skeleton Extraction Module.

This module is responsible for parsing Python source code and stripping away the
implementation details (function/method bodies), leaving only the structural "skeleton".
This skeleton includes function signatures, class definitions, and docstrings, which
provides high-level context to LLMs while drastically reducing token usage.
"""

import ast
import hashlib


class SkeletonTransformer(ast.NodeTransformer):
    """
    Traverses the Abstract Syntax Tree (AST) and modifies it in place.
    Specifically, it replaces the logic inside functions and asynchronous functions
    with a simple `pass` statement, while preserving top-level docstrings.
    It also injects line range information using a virtual @line(start, end) decorator.
    """

    def _inject_line_decorator(self, node: ast.AST) -> None:
        """Injects a virtual @line(start, end) decorator into class and function definitions."""
        if (hasattr(node, "lineno") and
            hasattr(node, "end_lineno") and
            hasattr(node, "decorator_list")):
            # Construct: @line(start_line, end_line)
            line_decorator = ast.Call(
                func=ast.Name(id="line", ctx=ast.Load()),
                args=[
                    ast.Constant(value=node.lineno),
                    ast.Constant(value=node.end_lineno)
                ],
                keywords=[]
            )
            # Insert at the beginning of the decorator list
            node.decorator_list.insert(0, line_decorator)

    def _strip_body(self, node: ast.AST) -> ast.AST:
        """
        Helper method to strip the body of a given AST node (like a function).

        It preserves the first statement if it is a docstring, and retains any
        nested class or function definitions. Other executable statements are removed.

        Args:
            node: The AST node whose body needs stripping.

        Returns:
            The modified AST node.
        """
        if not node.body:
            return node

        new_body = []
        # Check if the first statement is a docstring and preserve it
        first_stmt = node.body[0]
        if (isinstance(first_stmt, ast.Expr) and
            isinstance(first_stmt.value, ast.Constant) and
            isinstance(first_stmt.value.value, str)):
            new_body.append(first_stmt)

        # Preserve nested definitions (e.g., inner classes or functions)
        # Note: generic_visit has already processed their internal bodies.
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                new_body.append(stmt)

        # If the body is empty after stripping (or only has a docstring), add 'pass'
        # to ensure the resulting Python code remains syntactically valid.
        if not any(not isinstance(s, ast.Expr) for s in new_body):
            new_body.append(ast.Pass())

        node.body = new_body
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        """Visits standard synchronous function definitions."""
        self._inject_line_decorator(node)
        self.generic_visit(node)
        return self._strip_body(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        """Visits asynchronous function definitions."""
        self._inject_line_decorator(node)
        self.generic_visit(node)
        return self._strip_body(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        """
        Visits class definitions. We keep the class definition intact but process
        its body (methods) to ensure they are stripped.
        """
        self._inject_line_decorator(node)
        self.generic_visit(node)
        return node

def get_structural_code(source_code: str) -> str:
    """
    Parses the raw original code into an AST, applies the SkeletonTransformer,
    and unparses it back into a string.

    Args:
        source_code: The raw Python source code to process.

    Returns:
        A string representing the stripped down "skeleton" of the code.
        Returns an error comment string if a SyntaxError or other exception occurs.
    """
    try:
        tree = ast.parse(source_code)
        transformer = SkeletonTransformer()
        transformed_tree = transformer.visit(tree)
        return ast.unparse(transformed_tree)
    except SyntaxError:
        return "# [Error] Unable to parse syntax for this file."
    except Exception as e:
        return f"# [Error] Unexpected error during parsing: {str(e)}"

def calculate_structural_hash(skeleton_code: str) -> str:
    """
    Calculates a SHA256 hash of the generated skeleton code.

    This is used to detect if the *structure* or *interface* of a file has changed.
    Changes that only affect the implementation logic (which is stripped out)
    will not change this hash.

    Args:
        skeleton_code: The stripped structural code string.

    Returns:
        The hexadecimal SHA256 hash string.
    """
    return hashlib.sha256(skeleton_code.encode("utf-8")).hexdigest()
