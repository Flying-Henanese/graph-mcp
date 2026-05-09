import os
import time
from pathlib import Path

import pytest

from archimedes.state import state
from archimedes.watcher import start_watcher


@pytest.fixture
def temp_workspace(tmp_path):
    """
    Creates a temporary workspace with some initial Python files.
    """
    # Create src dir
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    # Create a dummy python file
    main_file = src_dir / "main.py"
    main_file.write_text("def hello():\n    print('hello world')", encoding="utf-8")

    # Create config file
    config_file = tmp_path / "archimedes.yaml"
    config_file.write_text('''
version: "1.0"
indexing:
  include: ["src/**/*.py"]
  exclude: ["tests/**"]
''', encoding="utf-8")

    # Change working directory for the test
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path

    # Restore original cwd
    os.chdir(original_cwd)

def test_watcher_initialization(temp_workspace):
    """
    Test that watcher correctly initializes state with existing files.
    """
    observer = start_watcher(".")

    try:
        assert state.is_initialized
        assert len(state.file_hashes) == 1

        main_file = Path("src/main.py").resolve()
        assert main_file in state.file_hashes
        assert state.graph_needs_rebuild
    finally:
        observer.stop()
        observer.join()

def test_watcher_file_modification(temp_workspace):
    """
    Test that modifying a file updates the hash and sets the graph dirty flag.
    """
    observer = start_watcher(".")

    try:
        # Reset dirty flag to simulate clean state after initial graph load
        state.update_graph("{}")
        with state.lock:
            initial_global_hash = state.global_hash
            main_file = Path("src/main.py").resolve()
            initial_file_hash = state.file_hashes[main_file]

        # Modify file structurally
        main_file_path = temp_workspace / "src" / "main.py"
        main_file_path.write_text(
            "def hello():\n    pass\n\ndef new_func():\n    pass", encoding="utf-8"
        )

        # Give watchdog a moment to detect and process
        time.sleep(0.5)

        with state.lock:
            assert state.graph_needs_rebuild
            assert state.global_hash != initial_global_hash
            assert state.file_hashes[main_file] != initial_file_hash
    finally:
        observer.stop()
        observer.join()

def test_watcher_file_addition(temp_workspace):
    """
    Test that adding a new tracked file updates state.
    """
    observer = start_watcher(".")

    try:
        state.update_graph("{}")
        with state.lock:
            initial_count = len(state.file_hashes)

        # Add new file
        new_file_path = temp_workspace / "src" / "utils.py"
        new_file_path.write_text("def util_func():\n    return 42", encoding="utf-8")

        time.sleep(0.5)

        with state.lock:
            assert len(state.file_hashes) == initial_count + 1
            assert state.graph_needs_rebuild
            new_file_resolved = Path("src/utils.py").resolve()
            assert new_file_resolved in state.file_hashes
    finally:
        observer.stop()
        observer.join()

def test_watcher_file_deletion(temp_workspace):
    """
    Test that deleting a tracked file removes it from state.
    """
    observer = start_watcher(".")

    try:
        state.update_graph("{}")
        with state.lock:
            main_file = Path("src/main.py").resolve()
            assert main_file in state.file_hashes

        # Delete file
        main_file_path = temp_workspace / "src" / "main.py"
        main_file_path.unlink()

        time.sleep(0.5)

        with state.lock:
            assert main_file not in state.file_hashes
            assert state.graph_needs_rebuild
            assert len(state.file_hashes) == 0
    finally:
        observer.stop()
        observer.join()
