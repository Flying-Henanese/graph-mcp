import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from archimedes.server import get_codebase_skeleton, read_full_implementation

def test_get_codebase_skeleton_invalid_dir():
    result = get_codebase_skeleton("non_existent_dir_xyz")
    assert "Error: Directory" in result

@patch("archimedes.server.scan_files")
@patch("archimedes.server.get_structural_code")
def test_get_codebase_skeleton_success(mock_skeleton, mock_scan, tmp_path):
    # Setup mock files
    file1 = tmp_path / "app.py"
    file1.write_text("def main(): pass")
    
    mock_scan.return_value = [file1]
    mock_skeleton.return_value = "def main(): pass"
    
    with patch("os.getcwd", return_value=str(tmp_path)):
        result = get_codebase_skeleton(".")
        assert "### File: app.py ###" in result
        assert "def main(): pass" in result

def test_read_full_implementation_success(tmp_path):
    file1 = tmp_path / "logic.py"
    content = "class A:\n    pass"
    file1.write_text(content)
    
    with patch("os.getcwd", return_value=str(tmp_path)):
        result = read_full_implementation("logic.py")
        assert result == content

def test_read_full_implementation_fail():
    result = read_full_implementation("missing.py")
    assert "Error: File" in result
