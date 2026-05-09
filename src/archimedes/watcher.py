"""
Background File Monitoring Module.

This module utilizes the `watchdog` library to actively monitor the project
directory for any file modifications, creations, or deletions. It updates the
global `ProjectState` in real-time, ensuring that structural caches and hashes
are always up-to-date without needing synchronous disk reads during client requests.
"""

import time
from pathlib import Path
from typing import Any
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from archimedes.state import state
from archimedes.skeleton import get_structural_code, calculate_structural_hash
from archimedes.config import is_file_tracked, get_exclude_spec, scan_files

class ArchimedesEventHandler(FileSystemEventHandler):
    """
    Handles file system events detected by the watchdog Observer.
    
    It filters events based on the project's configuration (e.g., ignoring .git or venv)
    and updates the central `ProjectState` accordingly.
    """
    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self.exclude_spec = get_exclude_spec()

    def process_file(self, file_path: Path) -> None:
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
            state.update_file(file_path, skeleton, file_hash)
        except Exception as e:
            state.set_file_error(file_path, f"# [Error] {str(e)}")

    def on_created(self, event: FileSystemEvent) -> None:
        """Triggered when a new file or directory is created."""
        if not event.is_directory:
            self.process_file(Path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        """Triggered when a file or directory is modified."""
        if not event.is_directory:
            self.process_file(Path(event.src_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Triggered when a file or directory is deleted."""
        if not event.is_directory:
            state.remove_file(Path(event.src_path))

def initialize_state(target_dir: str = ".") -> None:
    """
    Performs an initial synchronous scan of the directory to populate the state
    before starting the background observer.
    
    Args:
        target_dir: The root directory to monitor.
    """
    base_path = Path(target_dir).resolve()
    state.clear(base_path)
    
    files = scan_files(str(base_path))
    
    for file in files:
        try:
            content = file.read_text(encoding="utf-8")
            skeleton = get_structural_code(content)
            file_hash = calculate_structural_hash(skeleton)
            state.update_file(file, skeleton, file_hash)
        except Exception as e:
            state.set_file_error(file, f"# [Error] {str(e)}")
            
    with state.lock:
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
