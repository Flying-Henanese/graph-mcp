from mcp.server.fastmcp import FastMCP
from pathlib import Path
import os

import hashlib
from archimedes.config import scan_files
from archimedes.skeleton import get_structural_code, calculate_structural_hash

# Initialize MCP Server
mcp = FastMCP("Archimedes")

@mcp.tool()
def check_cache_status(target_dir: str = ".") -> dict:
    """
    Calculates a global structural hash of the codebase to check if the cache is still valid.
    Use this to avoid re-downloading the entire skeleton if nothing has changed.
    
    Returns:
        A dictionary containing the global_hash and file_count.
    """
    base_path = Path(os.getcwd())
    target_path = (base_path / target_dir).resolve()
    
    if not target_path.exists() or not target_path.is_dir():
        return {"error": f"Directory '{target_dir}' does not exist."}

    files = scan_files(str(target_path))
    hashes = []
    
    for file in files:
        try:
            content = file.read_text(encoding="utf-8")
            skeleton = get_structural_code(content)
            hashes.append(calculate_structural_hash(skeleton))
        except Exception:
            continue
            
    # Compute a global hash from all individual file hashes
    global_hash = hashlib.sha256("".join(sorted(hashes)).encode("utf-8")).hexdigest() if hashes else ""
    
    return {
        "global_structural_hash": global_hash,
        "file_count": len(files),
        "status": "ready"
    }

@mcp.tool()
def get_codebase_skeleton(target_dir: str = ".") -> str:
    """
    Scans the target directory and returns the skeleton/interfaces of all Python files.
    Includes a 'Global-Hash' header for client-side caching.
    """
    base_path = Path(os.getcwd())
    target_path = (base_path / target_dir).resolve()
    
    if not target_path.exists() or not target_path.is_dir():
        return f"Error: Directory '{target_dir}' does not exist or is not a directory."

    files = scan_files(str(target_path))
    if not files:
        return f"No Python files found in '{target_dir}' after applying filters."

    result_parts = []
    all_hashes = []
    
    for file in files:
        try:
            content = file.read_text(encoding="utf-8")
            skeleton = get_structural_code(content)
            h = calculate_structural_hash(skeleton)
            all_hashes.append(h)
            
            rel_display_path = file.relative_to(target_path)
            result_parts.append(f"### File: {rel_display_path} (Hash: {h[:8]}) ###\n{skeleton}\n")
        except Exception as e:
            rel_display_path = file.relative_to(target_path) if target_path in file.parents else file.name
            result_parts.append(f"### File: {rel_display_path} ###\n# [Error] {str(e)}\n")
            
    global_hash = hashlib.sha256("".join(sorted(all_hashes)).encode("utf-8")).hexdigest() if all_hashes else ""
    header = f"GLOBAL_STRUCTURAL_HASH: {global_hash}\n"
    header += "=" * 40 + "\n"
    
    return header + "\n".join(result_parts)

@mcp.tool()
def read_full_implementation(file_path: str) -> str:
    """
    Reads the full source code of a specific file.
    Use this after identifying a relevant file via 'get_codebase_skeleton'.
    
    Args:
        file_path: The relative path to the file to read.
    """
    base_path = Path(os.getcwd())
    path = (base_path / file_path).resolve()
    
    if not path.exists() or not path.is_file():
        return f"Error: File '{file_path}' does not exist."
    
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file '{file_path}': {str(e)}"

def main():
    mcp.run()

if __name__ == "__main__":
    main()
