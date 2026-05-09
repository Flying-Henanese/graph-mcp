"""
Background File Monitoring Module.

This module utilizes the `watchdog` library to actively monitor the project
directory for any file modifications, creations, or deletions. It updates the
global `ProjectState` in real-time, ensuring that structural caches and hashes
are always up-to-date without needing synchronous disk reads during client requests.
"""

import time
import hashlib
import json
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from archimedes.state import state
from archimedes.skeleton import get_structural_code, calculate_structural_hash
from archimedes.config import is_file_tracked, get_exclude_spec, scan_files
from archimedes.graph import build_project_graph, graph_to_json

class ArchimedesEventHandler(FileSystemEventHandler):
    """
    Handles file system events detected by the watchdog Observer.
    
    It filters events based on the project's configuration (e.g., ignoring .git or venv)
    and updates the central `ProjectState` accordingly.
    """
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.exclude_spec = get_exclude_spec()

    def process_file(self, file_path: Path):
        """
        Reads a modified or newly created file, extracts its skeleton, calculates
        its structural hash, and updates the global state if changes are detected.
        
        Args:
            file_path: Absolute path to the file that triggered the event.
        """
        # Fast exit if the file shouldn't be tracked (e.g., non-Python or excluded)
        if not is_file_tracked(file_path, self.base_path, self.exclude_spec):
            return
            
        try:
            content = file_path.read_text(encoding="utf-8")
            skeleton = get_structural_code(content)
            file_hash = calculate_structural_hash(skeleton)
            
            with state.lock:
                # Only update and mark dirty if the *structural* hash actually changed.
                # This prevents logic-only edits from triggering a heavy graph rebuild.
                if file_path not in state.file_hashes or state.file_hashes[file_path] != file_hash:
                    state.file_skeletons[file_path] = skeleton
                    state.file_hashes[file_path] = file_hash
                    # Mark the dependency graph as dirty so it gets lazily rebuilt later
                    state.graph_needs_rebuild = True
                    self._update_global_hash()
                    
        except Exception as e:
            with state.lock:
                # Handle unparseable files (e.g., during active typing with syntax errors)
                if file_path in state.file_hashes or file_path not in state.file_skeletons:
                    state.file_skeletons[file_path] = f"# [Error] {str(e)}"
                    state.file_hashes.pop(file_path, None)
                    state.graph_needs_rebuild = True
                    self._update_global_hash()

    def _update_global_hash(self):
        """
        Recalculates the global structural hash based on all current individual file hashes.
        Assumes the caller already holds `state.lock`.
        """
        sorted_hashes = [h for p, h in sorted(state.file_hashes.items())]
        state.global_hash = hashlib.sha256("".join(sorted_hashes).encode("utf-8")).hexdigest() if sorted_hashes else ""

    def on_created(self, event):
        """Triggered when a new file or directory is created."""
        if not event.is_directory:
            self.process_file(Path(event.src_path))

    def on_modified(self, event):
        """Triggered when a file or directory is modified."""
        if not event.is_directory:
            self.process_file(Path(event.src_path))

    def on_deleted(self, event):
        """Triggered when a file or directory is deleted."""
        if not event.is_directory:
            file_path = Path(event.src_path)
            with state.lock:
                # If the deleted file was tracked, remove it from state and mark dirty
                if file_path in state.file_hashes or file_path in state.file_skeletons:
                    state.file_hashes.pop(file_path, None)
                    state.file_skeletons.pop(file_path, None)
                    state.graph_needs_rebuild = True
                    self._update_global_hash()

def initialize_state(target_dir: str = "."):
    """
    Performs an initial synchronous scan of the directory to populate the state
    before starting the background observer.
    
    Args:
        target_dir: The root directory to monitor.
    """
    base_path = Path(target_dir).resolve()
    
    with state.lock:
        state.base_path = base_path
        state.file_hashes.clear()
        state.file_skeletons.clear()
    
    files = scan_files(str(base_path))
    
    with state.lock:
        for file in files:
            try:
                content = file.read_text(encoding="utf-8")
                skeleton = get_structural_code(content)
                file_hash = calculate_structural_hash(skeleton)
                state.file_skeletons[file] = skeleton
                state.file_hashes[file] = file_hash
            except Exception as e:
                state.file_skeletons[file] = f"# [Error] {str(e)}"
                
        sorted_hashes = [h for p, h in sorted(state.file_hashes.items())]
        state.global_hash = hashlib.sha256("".join(sorted_hashes).encode("utf-8")).hexdigest() if sorted_hashes else ""
        
        # We don't pre-build the graph here to save startup time.
        # It will be lazy-loaded on the first get_dependency_graph call.
        state.graph_needs_rebuild = True
        state.is_initialized = True

def start_watcher(target_dir: str = ".") -> Observer:
    """
    Initializes the in-memory state and starts the watchdog observer in a background thread.
    
    Args:
        target_dir: The root directory to monitor.
        
    Returns:
        The running `watchdog.observers.Observer` instance.
    """
    initialize_state(target_dir)
    
    base_path = Path(target_dir).resolve()
    event_handler = ArchimedesEventHandler(base_path)
    observer = Observer()
    observer.schedule(event_handler, str(base_path), recursive=True)
    observer.start()
    return observer
