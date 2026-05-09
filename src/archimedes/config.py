"""
Configuration and File Scanning Module.

This module handles reading the `archimedes.yaml` configuration file to determine
which files should be included or excluded from the MCP server's analysis. It uses
`pathspec` to process gitignore-style matching rules.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import pathspec
import yaml


def load_config(config_path: str = "archimedes.yaml") -> Dict[str, Any]:
    """
    Loads the indexing configuration from the specified YAML file.

    If the file does not exist or fails to parse, a default configuration is returned
    which includes all Python files in `src/` and excludes common virtual environments
    and cache directories.

    Args:
        config_path: The relative or absolute path to the configuration file.

    Returns:
        A dictionary containing the 'indexing' configuration block.
    """
    default_config: Dict[str, List[str]] = {
        "include": ["src/**/*.py"],
        "exclude": ["tests/**", "**/__pycache__/**", "venv/**", ".git/**", ".venv/**"]
    }

    path = Path(config_path)
    if not path.exists():
        return default_config

    try:
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config.get("indexing", default_config)
    except Exception:
        return default_config

def get_exclude_spec(config_path: str = "archimedes.yaml") -> pathspec.PathSpec:
    """
    Reads the configuration and compiles a pathspec matcher for the exclude patterns.

    Args:
        config_path: The path to the configuration file.

    Returns:
        A compiled `pathspec.PathSpec` object ready for file matching.
    """
    config: Dict[str, Any] = load_config(config_path)
    return pathspec.PathSpec.from_lines(
        'gitignore',
        config.get("exclude", [])
    )

def is_file_tracked(
    file_path: Path,
    base_path: Path,
    exclude_spec: Optional[pathspec.PathSpec] = None
) -> bool:
    """
    Determines whether a specific file should be tracked and processed by Archimedes.

    A file is tracked if it is a Python file (`.py`) and its relative path does not
    match any of the exclude patterns defined in the configuration.

    Args:
        file_path: The absolute path of the file to check.
        base_path: The root project directory, used to calculate the relative path.
        exclude_spec: An optional pre-compiled pathspec matcher. If not provided, it will be loaded.

    Returns:
        True if the file should be tracked, False otherwise.
    """
    if file_path.suffix != ".py":
        return False

    if exclude_spec is None:
        exclude_spec = get_exclude_spec()

    try:
        rel_path = str(file_path.relative_to(base_path))
        # Ensure path uses forward slashes for cross-platform pathspec matching
        rel_path = rel_path.replace('\\', '/')
    except ValueError:
        # File is not under the base path
        return False

    return not exclude_spec.match_file(rel_path)

def scan_files(target_dir: str, config_path: str = "archimedes.yaml") -> List[Path]:
    """
    Performs a full directory scan to find all tracked Python files.

    This function walks the directory tree recursively and filters files based on
    the `is_file_tracked` rules.

    Args:
        target_dir: The root directory to scan.
        config_path: The path to the configuration file.

    Returns:
        A sorted list of `Path` objects representing the tracked Python files.
    """
    base_path = Path(target_dir).resolve()

    if not base_path.exists() or not base_path.is_dir():
        return []

    exclude_spec = get_exclude_spec(config_path)

    # Using rglob to find all python files.
    # Note: For V1, the 'include' config is simplified to assume we want all .py files,
    # and we rely primarily on 'exclude' rules to filter unwanted ones.
    all_py_files = list(base_path.rglob("*.py"))
    valid_files = []

    for file_path in all_py_files:
        if is_file_tracked(file_path, base_path, exclude_spec):
            valid_files.append(file_path)

    return sorted(valid_files)

