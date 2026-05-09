"""
State Management Module.

This module defines the global in-memory state for the Archimedes MCP server.
It is responsible for caching the codebase skeleton, structural hashes, and the
dependency graph to provide O(1) response times for client requests.
"""

import threading
from pathlib import Path

class ProjectState:
    """
    Holds the runtime state of the monitored codebase.
    
    This class is designed to be a thread-safe singleton, updated by the background
    watchdog observer and read by the MCP server tools.
    """
    def __init__(self):
        # Lock to ensure thread-safe updates to the state from the watchdog observer
        self.lock = threading.Lock()
        
        # Maps absolute file paths to their structural SHA256 hashes
        self.file_hashes: dict[Path, str] = {}
        
        # Maps absolute file paths to their stripped AST skeleton strings
        self.file_skeletons: dict[Path, str] = {}
        
        # The aggregated hash of the entire codebase's structure
        self.global_hash: str = ""
        
        # The JSON-serialized rustworkx dependency graph
        self.cached_graph_json: str = ""
        
        # Dirty flag indicating if the graph needs to be rebuilt on the next request
        self.graph_needs_rebuild: bool = True
        
        # Flag indicating if the initial full-directory scan has completed
        self.is_initialized: bool = False
        
        # The root directory being monitored
        self.base_path: Path = Path(".")

# Global singleton instance used across the application
state = ProjectState()
