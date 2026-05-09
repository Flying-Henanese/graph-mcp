import pytest
from unittest.mock import patch
from pathlib import Path
import os
from archimedes.server import get_codebase_skeleton, read_full_implementation, check_cache_status, get_dependency_graph
from archimedes.state import state

@pytest.fixture(autouse=True)
def reset_state():
    """Reset the global state before each test."""
    with state.lock:
        state.is_initialized = False
        state.file_hashes.clear()
        state.file_skeletons.clear()
        state.global_hash = ""
        state.cached_graph_json = ""
        state.graph_needs_rebuild = True
        state.base_path = Path(".")

def test_uninitialized_state():
    """Test that endpoints return errors when state is not initialized."""
    assert "Error: Server state is not yet initialized" in get_codebase_skeleton()
    assert "error" in check_cache_status()
    assert "Error: Server state is not yet initialized" in get_dependency_graph()

def test_get_codebase_skeleton_success(tmp_path):
    """Test getting codebase skeleton from populated state."""
    with state.lock:
        state.is_initialized = True
        state.base_path = tmp_path
        file_path = tmp_path / "app.py"
        state.file_skeletons[file_path] = "def main(): pass"
        state.file_hashes[file_path] = "hash123"
        state.global_hash = "global_hash_456"

    result = get_codebase_skeleton()
    assert "### File: app.py (Hash: hash123) ###" in result
    assert "GLOBAL_STRUCTURAL_HASH: global_hash_456" in result
    assert "def main(): pass" in result

def test_check_cache_status_success(tmp_path):
    """Test cache status reads from state correctly."""
    with state.lock:
        state.is_initialized = True
        state.base_path = tmp_path
        file_path = tmp_path / "app.py"
        state.file_hashes[file_path] = "hash123"
        state.global_hash = "global_hash_456"

    result = check_cache_status()
    assert result["global_structural_hash"] == "global_hash_456"
    assert result["file_count"] == 1
    assert result["status"] == "ready"

def test_read_full_implementation_success(tmp_path):
    """Test reading full implementation from disk."""
    file1 = tmp_path / "logic.py"
    content = "class A:\n    pass"
    file1.write_text(content)
    
    with patch("os.getcwd", return_value=str(tmp_path)):
        result = read_full_implementation("logic.py")
        assert result == content

def test_read_full_implementation_fail():
    """Test reading a non-existent file."""
    result = read_full_implementation("missing.py")
    assert "Error: File" in result
