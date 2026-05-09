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
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.exclude_spec = get_exclude_spec()

    def process_file(self, file_path: Path):
        if not is_file_tracked(file_path, self.base_path, self.exclude_spec):
            return
            
        try:
            content = file_path.read_text(encoding="utf-8")
            skeleton = get_structural_code(content)
            file_hash = calculate_structural_hash(skeleton)
            
            with state.lock:
                # Only update and mark dirty if structure actually changed
                if file_path not in state.file_hashes or state.file_hashes[file_path] != file_hash:
                    state.file_skeletons[file_path] = skeleton
                    state.file_hashes[file_path] = file_hash
                    state.graph_needs_rebuild = True
                    self._update_global_hash()
                    
        except Exception as e:
            with state.lock:
                # Handle unparseable files
                if file_path in state.file_hashes or file_path not in state.file_skeletons:
                    state.file_skeletons[file_path] = f"# [Error] {str(e)}"
                    state.file_hashes.pop(file_path, None)
                    state.graph_needs_rebuild = True
                    self._update_global_hash()

    def _update_global_hash(self):
        # Assumes caller holds state.lock
        sorted_hashes = [h for p, h in sorted(state.file_hashes.items())]
        state.global_hash = hashlib.sha256("".join(sorted_hashes).encode("utf-8")).hexdigest() if sorted_hashes else ""

    def on_created(self, event):
        if not event.is_directory:
            self.process_file(Path(event.src_path))

    def on_modified(self, event):
        if not event.is_directory:
            self.process_file(Path(event.src_path))

    def on_deleted(self, event):
        if not event.is_directory:
            file_path = Path(event.src_path)
            with state.lock:
                if file_path in state.file_hashes or file_path in state.file_skeletons:
                    state.file_hashes.pop(file_path, None)
                    state.file_skeletons.pop(file_path, None)
                    state.graph_needs_rebuild = True
                    self._update_global_hash()

def initialize_state(target_dir: str = "."):
    """
    Perform initial scan and populate state synchronously.
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
        
        # We don't pre-build the graph here to save startup time, 
        # let it be lazy-loaded on the first get_dependency_graph call.
        state.graph_needs_rebuild = True
        state.is_initialized = True

def start_watcher(target_dir: str = ".") -> Observer:
    """
    Initializes state and starts the watchdog observer in a background thread.
    """
    initialize_state(target_dir)
    
    base_path = Path(target_dir).resolve()
    event_handler = ArchimedesEventHandler(base_path)
    observer = Observer()
    observer.schedule(event_handler, str(base_path), recursive=True)
    observer.start()
    return observer
