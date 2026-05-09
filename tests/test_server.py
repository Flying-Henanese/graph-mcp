from pathlib import Path
from unittest.mock import patch

import pytest

from archimedes.server import (
    check_cache_status,
    get_codebase_skeleton,
    get_dependency_graph,
    read_full_implementation,
)
from archimedes.state import state


@pytest.fixture(autouse=True)
def reset_state():
    """Reset the global state before each test."""
    state.clear(Path("."))

def test_uninitialized_state():
    """Test that endpoints return errors when state is not initialized."""
    assert "Error: Server state is not yet initialized" in get_codebase_skeleton()
    assert "error" in check_cache_status()
    assert "Error: Server state is not yet initialized" in get_dependency_graph()

def test_get_codebase_skeleton_success(tmp_path):
    """Test getting codebase skeleton from populated state."""
    state.clear(tmp_path)
    file_path = tmp_path / "app.py"
    state.update_file(file_path, "def main(): pass", "hash123")

    with state.lock:
        state.is_initialized = True
        expected_hash = state.global_hash

    result = get_codebase_skeleton()
    assert "### File: app.py (Hash: hash123) ###" in result
    assert f"GLOBAL_STRUCTURAL_HASH: {expected_hash}" in result
    assert "def main(): pass" in result

def test_check_cache_status_success(tmp_path):
    """Test cache status reads from state correctly."""
    state.clear(tmp_path)
    file_path = tmp_path / "app.py"
    state.update_file(file_path, "def main(): pass", "hash123")

    with state.lock:
        state.is_initialized = True
        expected_hash = state.global_hash

    result = check_cache_status()
    assert result["global_structural_hash"] == expected_hash
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
