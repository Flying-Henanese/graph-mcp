from pathlib import Path
from unittest.mock import patch

import pytest

from archimedes.server import (
    check_cache_status,
    get_codebase_skeleton,
    get_context_block,
    get_context_manifest,
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
    assert "error" in get_context_manifest()
    assert "error" in get_context_block("codebase_skeleton")

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

def test_get_context_manifest_success(tmp_path):
    """Test context manifest exposes stable cacheable block metadata."""
    state.clear(tmp_path)
    file_path = tmp_path / "app.py"
    state.update_file(file_path, "def main(): pass", "hash123")

    with state.lock:
        state.is_initialized = True
        expected_hash = state.global_hash

    result = get_context_manifest()

    assert result["schema_version"] == "1"
    assert result["global_structural_hash"] == expected_hash
    assert result["file_count"] == 1
    assert [block["id"] for block in result["blocks"]] == [
        "codebase_skeleton",
        "dependency_graph",
    ]
    assert result["blocks"][0]["hash"].startswith("codebase_skeleton:1:")

def test_get_context_block_skeleton_success(tmp_path):
    """Test skeleton context block wraps the existing skeleton output."""
    state.clear(tmp_path)
    file_path = tmp_path / "app.py"
    state.update_file(file_path, "def main(): pass", "hash123")

    with state.lock:
        state.is_initialized = True
        expected_hash = state.global_hash

    result = get_context_block("codebase_skeleton")

    assert result["id"] == "codebase_skeleton"
    assert result["kind"] == "skeleton"
    assert result["mime_type"] == "text/plain"
    assert result["hash"] == f"codebase_skeleton:1:{expected_hash}"
    assert result["content"] == get_codebase_skeleton()

def test_get_context_block_dependency_graph_success(tmp_path):
    """Test dependency graph context block returns graph content and clears dirty flag."""
    state.clear(tmp_path)
    file_path = tmp_path / "app.py"
    file_path.write_text("def main():\n    pass\n", encoding="utf-8")
    state.update_file(file_path, "def main(): pass", "hash123")

    with state.lock:
        state.is_initialized = True
        expected_hash = state.global_hash

    result = get_context_block("dependency_graph")

    assert result["id"] == "dependency_graph"
    assert result["kind"] == "graph"
    assert result["mime_type"] == "application/json"
    assert result["hash"] == f"dependency_graph:1:{expected_hash}"
    assert '"nodes"' in result["content"]

    with state.lock:
        assert not state.graph_needs_rebuild

def test_get_context_block_unknown_id(tmp_path):
    """Test unknown context block ids return a structured error."""
    state.clear(tmp_path)
    with state.lock:
        state.is_initialized = True

    result = get_context_block("missing")

    assert "error" in result
    assert result["available_blocks"] == ["codebase_skeleton", "dependency_graph"]

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
