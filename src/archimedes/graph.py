import ast
import rustworkx as rx
from pathlib import Path
from typing import Dict, Any, Tuple, List

class DependencyVisitor(ast.NodeVisitor):
    """
    Visits an AST to extract exports (classes, functions, variables)
    and imports (edges) for graph construction.
    """
    def __init__(self):
        self.exports = {"classes": [], "functions": [], "variables": []}
        self.imports = []  # List of (module_name, imported_names, line_no)

    def visit_ClassDef(self, node):
        self.exports["classes"].append(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        # Only capture top-level functions (ignoring methods for now to keep exports clean)
        # But generic_visit will traverse inside classes, so we might get methods too.
        # For MVP, capturing all is fine, but ideally we'd filter. Let's capture all for now.
        self.exports["functions"].append(node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.exports["functions"].append(node.name)
        self.generic_visit(node)

    def visit_Assign(self, node):
        # Attempt to capture top-level constants
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.exports["variables"].append(target.id)
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append((alias.name, [], node.lineno))
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            names = [alias.name for alias in node.names]
            self.imports.append((node.module, names, node.lineno))
        self.generic_visit(node)

def build_project_graph(files: List[Path], base_path: Path) -> rx.PyDiGraph:
    """
    Builds a rustworkx DAG representing the project modules and their dependencies.
    """
    graph = rx.PyDiGraph()
    module_to_node_idx = {}
    
    # Pre-compute module names for all files
    for file_path in files:
        try:
            rel_path = file_path.relative_to(base_path)
            # e.g., src/engine/parser.py -> src.engine.parser
            module_name = str(rel_path.with_suffix("")).replace("/", ".").replace("\\", ".")
            
            # Extract metadata via AST
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
            visitor = DependencyVisitor()
            visitor.visit(tree)
            
            node_data = {
                "id": module_name,
                "type": "module",
                "file_path": str(rel_path),
                "exports": visitor.exports,
                "raw_imports": visitor.imports # Keep for edge resolution
            }
            
            idx = graph.add_node(node_data)
            module_to_node_idx[module_name] = idx
        except Exception as e:
            # Skip unparseable files or those outside base_path
            continue

    # Add Edges based on imports
    for node_idx in graph.node_indices():
        node_data = graph[node_idx]
        source_module = node_data["id"]
        
        for imported_module, imported_names, line_no in node_data.get("raw_imports", []):
            # Attempt to match imported_module to our known local modules
            # E.g., if target is 'src.engine.base', does it exist in module_to_node_idx?
            # Note: This is a best-effort static resolution.
            
            # Exact match
            target_idx = module_to_node_idx.get(imported_module)
            
            # If not found, it might be a relative import or external package.
            # For this MVP, we only create edges for explicitly known local modules.
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
                # To prevent multiple edges between same nodes, check if edge exists
                # rustworkx allows multi-edges, so we just add them. 
                # Later we can condense them if needed.
                graph.add_edge(node_idx, target_idx, edge_data)
                
        # Clean up raw_imports from node data as it's no longer needed for final output
        node_data.pop("raw_imports", None)

    return graph

def graph_to_json(graph: rx.PyDiGraph) -> Dict[str, Any]:
    """
    Serializes the rustworkx graph to a dictionary for JSON output.
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
