import ast

class SkeletonTransformer(ast.NodeTransformer):
    """
    Traverses the AST and strips the implementation logic of functions and methods,
    while preserving docstrings for interface clarity.
    """
    def _strip_body(self, node):
        if not node.body:
            return node
            
        new_body = []
        # Check for docstring
        first_stmt = node.body[0]
        if (isinstance(first_stmt, ast.Expr) and 
            isinstance(first_stmt.value, ast.Constant) and 
            isinstance(first_stmt.value.value, str)):
            new_body.append(first_stmt)
            
        # Preserve nested definitions (already processed by generic_visit)
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                new_body.append(stmt)
        
        # If the body is empty or only contains docstrings, add 'pass'
        if not any(not isinstance(s, ast.Expr) for s in new_body):
            new_body.append(ast.Pass())
            
        node.body = new_body
        return node

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        return self._strip_body(node)

    def visit_AsyncFunctionDef(self, node):
        self.generic_visit(node)
        return self._strip_body(node)
    
    def visit_ClassDef(self, node):
        # We keep the class definition but we can also process its body 
        # to ensure nested functions are stripped.
        self.generic_visit(node)
        return node

import hashlib

def get_structural_code(source_code: str) -> str:
    """
    Parses original code and returns a stripped skeleton version.
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
    Calculates a SHA256 hash of the skeleton code to detect structural changes.
    """
    return hashlib.sha256(skeleton_code.encode("utf-8")).hexdigest()
