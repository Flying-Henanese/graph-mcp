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

def scan_files(target_dir: str, config_path: str = "archimedes.yaml") -> list[Path]:
    """
    Scans the target directory for Python files, respecting include/exclude patterns.
    """
    config = load_config(config_path)
    base_path = Path(target_dir).resolve()
    
    if not base_path.exists() or not base_path.is_dir():
        return []

    # Build pattern matchers
    # Use 'gitignore' pattern factory as 'GitWildMatchPattern' is deprecated
    exclude_spec = pathspec.PathSpec.from_lines(
        'gitignore', 
        config.get("exclude", [])
    )
    
    # For 'include', we'll use rglob and then filter by exclude
    # V1 simplification: we use the include patterns if they are glob-like,
    # or just rglob("*.py") if include is broad.
    
    all_py_files = list(base_path.rglob("*.py"))
    valid_files = []
    
    for file_path in all_py_files:
        # Calculate path relative to target_dir for matching
        try:
            rel_path = str(file_path.relative_to(base_path))
        except ValueError:
            # Handle cases where file is not under base_path (unlikely with rglob)
            continue
            
        if not exclude_spec.match_file(rel_path):
            valid_files.append(file_path)
            
    return sorted(valid_files)
