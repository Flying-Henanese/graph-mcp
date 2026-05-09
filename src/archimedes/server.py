"""
MCP Server Entry Point.

This module defines the Archimedes MCP Server using the FastMCP framework.
It exposes tools for LLMs to query the codebase skeleton, dependency graph,
and specific file implementations. It relies heavily on the `watchdog`-backed
in-memory `ProjectState` to provide O(1) responses.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP
from watchdog.observers.api import BaseObserver

from archimedes.graph import build_project_graph, graph_to_json
from archimedes.state import state
from archimedes.watcher import start_watcher

# Initialize MCP Server instance
mcp = FastMCP("Archimedes")

# Global reference to observer to keep the background thread alive
_observer: Optional[BaseObserver] = None

@mcp.tool()
def get_dependency_graph() -> str:
    """
    Returns the project's macro architecture as a JSON Dependency Graph.

    Nodes represent modules (with their exported classes/functions).
    Edges represent import dependencies between these modules.

    This tool utilizes a lazy-loading strategy: it only rebuilds the graph
    using rustworkx if the codebase structure has changed since the last call.
    Otherwise, it returns the cached JSON string in O(1) time.
    """
    if not state.is_initialized:
        return "Error: Server state is not yet initialized."

    # Using state.lock to ensure atomic read/check of graph status
    with state.lock:
        needs_rebuild = state.graph_needs_rebuild
        cached_json = state.cached_graph_json

    if needs_rebuild:
        # Rebuild graph from cached files instead of hitting the disk again
        with state.lock:
            files = list(state.file_hashes.keys())

        if not files:
            return "No Python files found to build graph."

        graph = build_project_graph(files, state.base_path)
        new_json = json.dumps(graph_to_json(graph), indent=2)
        state.update_graph(new_json)
        return new_json

    return cached_json

@mcp.tool()
def check_cache_status() -> Dict[str, Any]:
    """
    Returns the current global structural hash of the codebase.

    Clients can use this tool to quickly verify if their locally cached codebase
    skeleton is still valid. Reads directly from memory in O(1) time.

    Returns:
        A dictionary containing the global_structural_hash and file_count.
    """
    if not state.is_initialized:
        return {"error": "Server state is not yet initialized."}

    with state.lock:
        return {
            "global_structural_hash": state.global_hash,
            "file_count": len(state.file_hashes),
            "status": "ready"
        }

@mcp.tool()
def get_codebase_skeleton() -> str:
    """
    Returns the structural interfaces (skeleton) of all tracked Python files.

    Served directly from the actively monitored in-memory state in O(1) time,
    eliminating the need for synchronous disk reads or AST parsing during the request.
    Includes a 'GLOBAL_STRUCTURAL_HASH' header for client-side caching mechanisms.
    """
    if not state.is_initialized:
        return "Error: Server state is not yet initialized."

    result_parts = []

    with state.lock:
        if not state.file_skeletons:
            return "No Python files found after applying filters."

        # Sort paths to ensure consistent output ordering for stable hashing
        for file_path, skeleton in sorted(state.file_skeletons.items()):
            rel_display_path = file_path.relative_to(state.base_path)
            h = state.file_hashes.get(file_path, "Error")

            if "Error" in skeleton:
                result_parts.append(f"### File: {rel_display_path} ###\n{skeleton}\n")
            else:
                result_parts.append(
                    f"### File: {rel_display_path} (Hash: {h[:8]}) ###\n{skeleton}\n"
                )

        global_hash = state.global_hash

    header = f"GLOBAL_STRUCTURAL_HASH: {global_hash}\n"
    header += "=" * 40 + "\n"

    return header + "\n".join(result_parts)

@mcp.tool()
def read_full_implementation(file_path: str) -> str:
    """
    Reads the full, unstripped source code of a specific file directly from disk.

    This is intended to be used for deep-dives *after* the LLM has identified
    a relevant file using the skeleton or dependency graph.

    Args:
        file_path: The relative path to the file to read.
    """
    base_path = Path(os.getcwd())
    path = (base_path / file_path).resolve()

    if not path.exists() or not path.is_file():
        return f"Error: File '{file_path}' does not exist."

    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file '{file_path}': {str(e)}"

def main() -> None:
    """
    Entry point for the application. Starts the background watcher and then
    launches the FastMCP server blocking loop.
    """
    global _observer
    # Start the watchdog observer on the current working directory before running MCP
    _observer = start_watcher(".")
    try:
        mcp.run()
    finally:
        # Ensure clean shutdown of the background thread
        if _observer:
            _observer.stop()
            _observer.join()

if __name__ == "__main__":
    main()
