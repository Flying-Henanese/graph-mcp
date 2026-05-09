import yaml
from pathlib import Path
import pathspec

def load_config(config_path: str = "archimedes.yaml") -> dict:
    """
    Loads indexing configuration from archimedes.yaml.
    """
    default_config = {
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
    Returns a compiled pathspec based on the exclude configuration.
    """
    config = load_config(config_path)
    return pathspec.PathSpec.from_lines(
        'gitignore', 
        config.get("exclude", [])
    )

def is_file_tracked(file_path: Path, base_path: Path, exclude_spec: pathspec.PathSpec = None) -> bool:
    """
    Checks if a given Python file should be tracked based on configuration.
    """
    if file_path.suffix != ".py":
        return False
        
    if exclude_spec is None:
        exclude_spec = get_exclude_spec()
        
    try:
        rel_path = str(file_path.relative_to(base_path))
        # Ensure path uses forward slashes for matching
        rel_path = rel_path.replace('\\', '/')
    except ValueError:
        return False
        
    return not exclude_spec.match_file(rel_path)

def scan_files(target_dir: str, config_path: str = "archimedes.yaml") -> list[Path]:
    """
    Scans the target directory for Python files, respecting include/exclude patterns.
    """
    base_path = Path(target_dir).resolve()
    
    if not base_path.exists() or not base_path.is_dir():
        return []

    exclude_spec = get_exclude_spec(config_path)
    all_py_files = list(base_path.rglob("*.py"))
    valid_files = []
    
    for file_path in all_py_files:
        if is_file_tracked(file_path, base_path, exclude_spec):
            valid_files.append(file_path)
            
    return sorted(valid_files)
