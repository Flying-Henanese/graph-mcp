import threading
from pathlib import Path

class ProjectState:
    def __init__(self):
        self.lock = threading.Lock()
        self.file_hashes: dict[Path, str] = {}
        self.file_skeletons: dict[Path, str] = {}
        self.global_hash: str = ""
        self.cached_graph_json: str = ""
        self.graph_needs_rebuild: bool = True
        self.is_initialized: bool = False
        self.base_path: Path = Path(".")

# Global singleton
state = ProjectState()
