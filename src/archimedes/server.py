from mcp.server.fastmcp import FastMCP
from pathlib import Path
import os
import json

from archimedes.state import state
from archimedes.watcher import start_watcher
from archimedes.graph import build_project_graph, graph_to_json

# Initialize MCP Server
mcp = FastMCP("Archimedes")

# Global reference to observer to keep it alive
_observer = None

@mcp.tool()
def get_dependency_graph() -> str:
    """
    Returns the project's macro architecture as a JSON Dependency Graph.
    Nodes represent modules (with their exported classes/functions).
    Edges represent import dependencies between these modules.
    
    Use this to understand the high-level topology before reading skeletons.
    """
    if not state.is_initialized:
        return "Error: Server state is not yet initialized."

    with state.lock:
        if state.graph_needs_rebuild:
            # Rebuild graph from cached files instead of disk
            files = list(state.file_hashes.keys())
            if not files:
                return "No Python files found to build graph."
                
            graph = build_project_graph(files, state.base_path)
            state.cached_graph_json = json.dumps(graph_to_json(graph), indent=2)
            state.graph_needs_rebuild = False
            
        return state.cached_graph_json

@mcp.tool()
def check_cache_status() -> dict:
    """
    Returns the current global structural hash of the codebase to check if the client cache is valid.
    Reads directly from memory (O(1)), no disk scanning involved.
    
    Returns:
        A dictionary containing the global_hash and file_count.
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
    Returns the skeleton/interfaces of all tracked Python files directly from memory.
    Includes a 'Global-Hash' header for client-side caching.
    """
    if not state.is_initialized:
        return "Error: Server state is not yet initialized."

    result_parts = []
    
    with state.lock:
        if not state.file_skeletons:
            return "No Python files found after applying filters."
            
        for file_path, skeleton in sorted(state.file_skeletons.items()):
            rel_display_path = file_path.relative_to(state.base_path)
            h = state.file_hashes.get(file_path, "Error")
            
            if "Error" in skeleton:
                result_parts.append(f"### File: {rel_display_path} ###\n{skeleton}\n")
            else:
                result_parts.append(f"### File: {rel_display_path} (Hash: {h[:8]}) ###\n{skeleton}\n")
                
        global_hash = state.global_hash

    header = f"GLOBAL_STRUCTURAL_HASH: {global_hash}\n"
    header += "=" * 40 + "\n"
    
    return header + "\n".join(result_parts)

@mcp.tool()
def read_full_implementation(file_path: str) -> str:
    """
    Reads the full source code of a specific file from disk.
    Use this after identifying a relevant file via 'get_codebase_skeleton'.
    
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

def main():
    global _observer
    # Start the watchdog observer on the current working directory before running MCP
    _observer = start_watcher(".")
    try:
        mcp.run()
    finally:
        if _observer:
            _observer.stop()
            _observer.join()

if __name__ == "__main__":
    main()
