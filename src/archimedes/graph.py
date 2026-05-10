"""
Dependency Graph Construction Module.

This module is responsible for analyzing the AST of Python files to extract
exported symbols (classes, functions) and import statements. It then uses the
`rustworkx` library to build a directed acyclic graph (DAG) representing the
macro-level topology of the codebase.
"""

import ast
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import rustworkx as rx


@dataclass
class ExportEntity:
    """Represents a single symbol (class, function, variable) exported by a module."""
    name: str
    kind: str  # "class", "function", "variable"
    line_no: int


@dataclass
class ImportInteraction:
    """Represents a single import dependency between modules."""
    module: str
    entities: List[str]
    line_no: int
    level: int = 0


@dataclass
class ModuleNode:
    """Represents a module node in the dependency graph."""
    id: str  # Python module notation (e.g., 'src.utils')
    file_path: str
    exports: List[ExportEntity]
    type: str = "module"
    # raw_imports is used during construction and cleared afterwards
    raw_imports: List[ImportInteraction] = field(default_factory=list, repr=False)


@dataclass
class ImportDetail:
    """Represents the detailed information of a single import interaction."""
    caller: str
    callee: str
    imported_entities: List[str]
    line_no: int


@dataclass
class DependencyEdge:
    """Represents the metadata of a dependency edge in the graph."""
    interactions: List[ImportDetail]
    dependency_type: str = "import"


class DependencyVisitor(ast.NodeVisitor):
    """
    AST Visitor that extracts structural metadata for graph construction.

    It captures exported entities (classes, top-level functions, top-level variables)
    and module dependencies (imports). This data is later used as node and edge
    attributes in the rustworkx graph.
    """
    def __init__(self) -> None:
        # A list of ExportEntity objects representing symbols defined in the file
        self.exports: List[ExportEntity] = []

        # A list of ImportInteraction objects representing outgoing dependencies
        self.imports: List[ImportInteraction] = []

    # override visit_ClassDef to capture class definitions
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Captures class definitions as exported entities."""
        self.exports.append(ExportEntity(name=node.name, kind="class", line_no=node.lineno))
        self.generic_visit(node)

    # override visit_FunctionDef to capture function definitions
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """
        Captures standard function definitions.
        Note: For this MVP, we capture all functions encountered. Ideally,
        we would filter out class methods if we only wanted top-level exports.
        """
        self.exports.append(ExportEntity(name=node.name, kind="function", line_no=node.lineno))
        self.generic_visit(node)

    # override visit_AsyncFunctionDef to capture async function definitions
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Captures asynchronous function definitions."""
        self.exports.append(ExportEntity(name=node.name, kind="function", line_no=node.lineno))
        self.generic_visit(node)

    # override visit_Assign to capture top-level constants and variables
    def visit_Assign(self, node: ast.Assign) -> None:
        """Attempt to capture top-level constants and variables."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.exports.append(
                    ExportEntity(name=target.id, kind="variable", line_no=node.lineno)
                )
        self.generic_visit(node)

    # override visit_Import to capture absolute module imports
    def visit_Import(self, node: ast.Import) -> None:
        """Captures absolute module imports (e.g., `import os`)."""
        for alias in node.names:
            # We don't know the exact names being used yet, just the module
            self.imports.append(
                ImportInteraction(module=alias.name, entities=[], line_no=node.lineno)
            )
        self.generic_visit(node)

    # override visit_ImportFrom to capture specific entity imports from a module
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Captures specific entity imports from a module (e.g., `from os import path`)."""
        entities = [alias.name for alias in node.names]
        self.imports.append(
            ImportInteraction(
                module=node.module or "",
                entities=entities,
                line_no=node.lineno,
                level=node.level,
            )
        )
        self.generic_visit(node)


def _module_name_from_path(file_path: Path, base_path: Path) -> str:
    """Converts a project file path into a normalized Python module name."""
    rel_path = file_path.relative_to(base_path)
    module_name = str(rel_path.with_suffix("")).replace("/", ".").replace("\\", ".")
    if module_name.endswith(".__init__"):
        return module_name[: -len(".__init__")]
    return module_name


def _module_aliases(module_name: str) -> List[str]:
    """Returns alternate import names for common src-layout packages."""
    if module_name == "src":
        return []

    if module_name.startswith("src."):
        return [module_name.removeprefix("src.")]

    return []


def _package_name(module_name: str, file_path: str) -> str:
    """Returns the package namespace used to resolve relative imports."""
    if file_path.endswith("__init__.py"):
        return module_name
    return module_name.rsplit(".", 1)[0] if "." in module_name else ""


def _resolve_relative_module(source_package: str, imp: ImportInteraction) -> str:
    """Converts an import interaction into an absolute module namespace candidate."""
    if imp.level == 0:
        return imp.module

    package_parts = source_package.split(".") if source_package else []
    parent_count = max(imp.level - 1, 0)
    if parent_count:
        package_parts = package_parts[:-parent_count]

    if imp.module:
        package_parts.extend(imp.module.split("."))

    return ".".join(part for part in package_parts if part)


def _resolve_import_target(
    source_node: ModuleNode,
    imp: ImportInteraction,
    module_to_node_idx: Dict[str, int],
) -> int | None:
    """Resolves an import interaction to a local graph node index when possible."""
    source_package = _package_name(source_node.id, source_node.file_path)
    candidate = _resolve_relative_module(source_package, imp)

    for entity in imp.entities:
        entity_candidate = f"{candidate}.{entity}" if candidate else entity
        if entity_candidate in module_to_node_idx:
            return module_to_node_idx[entity_candidate]

    if candidate in module_to_node_idx:
        return module_to_node_idx[candidate]

    return None


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
    # Initialize the graph object
    graph = rx.PyDiGraph()
    # Mapping from Python module namespace (e.g., 'src.utils.math') to the rustworkx node index
    module_to_node_idx = {}
    node_to_path: Dict[int, str] = {}

    # --- Pass 1: Pre-compute module names and create nodes ---
    for file_path in files:
        try:
            rel_path = file_path.relative_to(base_path)
            module_name = _module_name_from_path(file_path, base_path)

            # Extract metadata via AST Visitor
            # read source code
            content = file_path.read_text(encoding="utf-8")
            # build AST tree from source code
            tree = ast.parse(content)
            visitor = DependencyVisitor()
            # traverse AST tree to capture exports and imports
            # then generate complete exports and imports
            visitor.visit(tree)

            node = ModuleNode(
                id=module_name,
                file_path=str(rel_path),
                exports=visitor.exports,
                raw_imports=visitor.imports
            )

            # add node to graph, with a incremental index as the node ID
            idx = graph.add_node(node)
            module_to_node_idx[module_name] = idx
            for alias in _module_aliases(module_name):
                module_to_node_idx.setdefault(alias, idx)
            node_to_path[idx] = str(rel_path)
        except Exception:
            # Skip unparseable files or those unexpectedly outside base_path
            continue

    # --- Pass 2: Add Edges based on resolved imports ---
    edge_interactions: Dict[tuple[int, int], List[ImportDetail]] = {}
    for node_idx in graph.node_indices(): # traverse all nodes in the graph
        current_node: ModuleNode = graph[node_idx]
        source_module = current_node.id

        # Iterate over the raw imports captured in Pass 1
        for imp in current_node.raw_imports:
            imp: ImportInteraction
            target_idx = _resolve_import_target(current_node, imp, module_to_node_idx)
            if target_idx is None:
                continue

            # If a local target is found (and it's not a self-import), create an edge
            if target_idx != node_idx:
                edge_interactions.setdefault((node_idx, target_idx), []).append(
                    ImportDetail(
                        caller=source_module,
                        callee=graph[target_idx].id,
                        imported_entities=imp.entities,
                        line_no=imp.line_no
                    )
                )

        # Clean up raw_imports from node data as it's no longer needed for the final output
        current_node.raw_imports = []

    for (source_idx, target_idx), interactions in sorted(
        edge_interactions.items(),
        key=lambda item: (node_to_path[item[0][0]], node_to_path[item[0][1]]),
    ):
        graph.add_edge(source_idx, target_idx, DependencyEdge(interactions=interactions))

    return graph

def graph_to_json(graph: rx.PyDiGraph) -> Dict[str, Any]:
    """
    Serializes the rustworkx PyDiGraph into a standard JSON-compatible dictionary.

    Args:
        graph: The constructed dependency graph.

    Returns:
        A dictionary with 'nodes' and 'edges' arrays, suitable for JSON serialization.
    """
    nodes = []
    for idx in graph.node_indices():
        current_node: ModuleNode = graph[idx]

        # Aggregation Phase: Group atomic ExportEntity objects back into
        # categories for LLM consumption
        # This keeps the output compact while the internal data remains rich and atomic.
        raw_exports: List[ExportEntity] = current_node.exports
        aggregated_exports = {
            "classes": [],
            "functions": [],
            "variables": []
        }

        for entity in raw_exports:
            entity: ExportEntity
            # Map kind to the correct list
            # (kind "class" -> "classes", "function" -> "functions", etc.)
            if entity.kind == "class":
                key = "classes"
            elif entity.kind == "function":
                key = "functions"
            else:
                key = "variables"

            if key in aggregated_exports:
                aggregated_exports[key].append(entity.name)

        nodes.append({
            "id": current_node.id,
            "type": current_node.type,
            "file_path": current_node.file_path,
            "exports": aggregated_exports
        })

    edges = []

    for edge_idx in graph.edge_indices():
        source_idx, target_idx = graph.get_edge_endpoints_by_index(edge_idx)
        edge_data: DependencyEdge = graph.get_edge_data_by_index(edge_idx)

        edges.append({
            "source": graph[source_idx].id,
            "target": graph[target_idx].id,
            "data": asdict(edge_data)
        })

    return {"nodes": nodes, "edges": edges}
