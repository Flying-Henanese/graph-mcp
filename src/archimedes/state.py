"""
State Management Module.

This module defines the global in-memory state for the Archimedes MCP server.
It is responsible for caching the codebase skeleton, structural hashes, and the
dependency graph to provide O(1) response times for client requests.
"""

import threading
import hashlib
from pathlib import Path

class ProjectState:
    """
    Holds the runtime state of the monitored codebase.
    
    This class is designed to be a thread-safe singleton, updated by the background
    watchdog observer and read by the MCP server tools.
    """
    def __init__(self) -> None:
        # Lock to ensure thread-safe updates to the state from the watchdog observer
        self.lock: threading.Lock = threading.Lock()
        
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

    def _recalculate_global_hash(self) -> None:
        """Internal method to recalculate the global hash. Assumes lock is held."""
        sorted_hashes = [h for _, h in sorted(self.file_hashes.items())]
        self.global_hash = hashlib.sha256("".join(sorted_hashes).encode("utf-8")).hexdigest() if sorted_hashes else ""

    def update_file(self, file_path: Path, skeleton: str, file_hash: str) -> None:
        """Atomically updates a file's skeleton and hash, marking the graph as dirty if changed."""
        with self.lock:
            if self.file_hashes.get(file_path) != file_hash:
                self.file_skeletons[file_path] = skeleton
                self.file_hashes[file_path] = file_hash
                self.graph_needs_rebuild = True
                self._recalculate_global_hash()

    def remove_file(self, file_path: Path) -> None:
        """Atomically removes a tracked file from the state."""
        with self.lock:
            if file_path in self.file_hashes or file_path in self.file_skeletons:
                self.file_hashes.pop(file_path, None)
                self.file_skeletons.pop(file_path, None)
                self.graph_needs_rebuild = True
                self._recalculate_global_hash()

    def set_file_error(self, file_path: Path, error_msg: str) -> None:
        """Atomically handles a file that could not be parsed."""
        with self.lock:
            if file_path in self.file_hashes or file_path not in self.file_skeletons:
                self.file_skeletons[file_path] = error_msg
                self.file_hashes.pop(file_path, None)
                self.graph_needs_rebuild = True
                self._recalculate_global_hash()

    def update_graph(self, graph_json: str) -> None:
        """Atomically updates the cached dependency graph and clears the dirty flag."""
        with self.lock:
            self.cached_graph_json = graph_json
            self.graph_needs_rebuild = False

    def clear(self, base_path: Path) -> None:
        """Atomically resets the state to prepare for a fresh directory scan."""
        with self.lock:
            self.base_path = base_path
            self.file_hashes.clear()
            self.file_skeletons.clear()
            self.global_hash = ""
            self.cached_graph_json = ""
            self.graph_needs_rebuild = True
            self.is_initialized = False

# Global singleton instance used across the application
state = ProjectState()
