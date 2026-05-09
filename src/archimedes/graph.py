"""
Dependency Graph Construction Module.

This module is responsible for analyzing the AST of Python files to extract
exported symbols (classes, functions) and import statements. It then uses the
`rustworkx` library to build a directed acyclic graph (DAG) representing the
macro-level topology of the codebase.
"""

import ast
import rustworkx as rx
from pathlib import Path
from typing import Dict, Any, Tuple, List

class DependencyVisitor(ast.NodeVisitor):
    """
    AST Visitor that extracts structural metadata for graph construction.
    
    It captures exported entities (classes, top-level functions, top-level variables)
    and module dependencies (imports). This data is later used as node and edge
    attributes in the rustworkx graph.
    """
    def __init__(self) -> None:
        # A dictionary holding lists of exported symbols from the current file
        self.exports: Dict[str, List[str]] = {"classes": [], "functions": [], "variables": []}
        
        # A list of tuples representing outgoing dependencies:
        # (module_name, list_of_imported_names, line_number)
        self.imports: List[Tuple[str, List[str], int]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Captures class definitions as exported entities."""
        self.exports["classes"].append(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """
        Captures standard function definitions.
        Note: For this MVP, we capture all functions encountered. Ideally,
        we would filter out class methods if we only wanted top-level exports.
        """
        self.exports["functions"].append(node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Captures asynchronous function definitions."""
        self.exports["functions"].append(node.name)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Attempt to capture top-level constants and variables."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.exports["variables"].append(target.id)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Captures absolute module imports (e.g., `import os`)."""
        for alias in node.names:
            # We don't know the exact names being used yet, just the module
            self.imports.append((alias.name, [], node.lineno))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Captures specific entity imports from a module (e.g., `from os import path`)."""
        if node.module:
            names = [alias.name for alias in node.names]
            self.imports.append((node.module, names, node.lineno))
        self.generic_visit(node)

def build_project_graph(files: List[Path], base_path: Path) -> rx.PyDiGraph:
    """
    Builds a directed graph representing the project modules and their dependencies.
    
    It operates in two passes:
    1. Node Creation: Parses all files to extract exports and raw imports, adding them as nodes.
    2. Edge Resolution: Connects nodes based on import statements, attempting to resolve
       target module names to local graph nodes.
       
    Args:
        files: A list of Paths to the Python files to include in the graph.
        base_path: The root project directory, used to calculate module namespaces.
        
    Returns:
        A `rustworkx.PyDiGraph` instance.
    """
    graph = rx.PyDiGraph()
    # Mapping from Python module namespace (e.g., 'src.utils.math') to the rustworkx node index
    module_to_node_idx = {}
    
    # --- Pass 1: Pre-compute module names and create nodes ---
    for file_path in files:
        try:
            rel_path = file_path.relative_to(base_path)
            # Convert file path to Python module notation (e.g., src/engine/parser.py -> src.engine.parser)
            module_name = str(rel_path.with_suffix("")).replace("/", ".").replace("\\", ".")
            
            # Extract metadata via AST Visitor
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
            visitor = DependencyVisitor()
            visitor.visit(tree)
            
            node_data = {
                "id": module_name,
                "type": "module",
                "file_path": str(rel_path),
                "exports": visitor.exports,
                "raw_imports": visitor.imports # Kept temporarily for Pass 2 edge resolution
            }
            
            idx = graph.add_node(node_data)
            module_to_node_idx[module_name] = idx
        except Exception as e:
            # Skip unparseable files or those unexpectedly outside base_path
            continue

    # --- Pass 2: Add Edges based on resolved imports ---
    for node_idx in graph.node_indices():
        node_data = graph[node_idx]
        source_module = node_data["id"]
        
        # Iterate over the raw imports captured in Pass 1
        for imported_module, imported_names, line_no in node_data.get("raw_imports", []):
            # Attempt to match imported_module to our known local modules
            # Note: This is a best-effort static resolution. Dynamic imports or complex
            # relative imports might be missed in this MVP version.
            target_idx = module_to_node_idx.get(imported_module)
            
            # If a local target is found (and it's not a self-import), create an edge
            if target_idx is not None and target_idx != node_idx:
                edge_data = {
                    "dependency_type": "import",
                    "interactions": [{
                        "caller": source_module,
                        "callee": imported_module,
                        "imported_entities": imported_names,
                        "line_no": line_no
                    }]
                }
                # Add the directed edge. Rustworkx allows multi-edges, so we don't strictly
                # need to check for pre-existing edges here unless we want to consolidate them.
                graph.add_edge(node_idx, target_idx, edge_data)
                
        # Clean up raw_imports from node data as it's no longer needed for the final output
        node_data.pop("raw_imports", None)

    return graph

def graph_to_json(graph: rx.PyDiGraph) -> Dict[str, Any]:
    """
    Serializes the rustworkx PyDiGraph into a standard JSON-compatible dictionary.
    
    Args:
        graph: The constructed dependency graph.
        
    Returns:
        A dictionary with 'nodes' and 'edges' arrays, suitable for JSON serialization.
    """
    nodes = [graph[idx] for idx in graph.node_indices()]
    edges = []
    
    for edge_idx in graph.edge_indices():
        source_idx, target_idx = graph.get_edge_endpoints_by_index(edge_idx)
        edge_data = graph.get_edge_data_by_index(edge_idx)
        edges.append({
            "source": graph[source_idx]["id"],
            "target": graph[target_idx]["id"],
            "data": edge_data
        })
        
    return {"nodes": nodes, "edges": edges}
