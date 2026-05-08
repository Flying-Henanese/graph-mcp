from mcp.server.fastmcp import FastMCP
from pathlib import Path
import os

from archimedes.config import scan_files
from archimedes.skeleton import get_structural_code

# Initialize MCP Server
mcp = FastMCP("Archimedes")

@mcp.tool()
def get_codebase_skeleton(target_dir: str = ".") -> str:
    """
    Scans the target directory and returns the skeleton/interfaces of all Python files.
    Use this first to understand the project architecture without reading implementation details.
    
    Args:
        target_dir: The relative path to the directory to scan (e.g., "src/"). Defaults to current directory.
    """
    # Resolve target_dir relative to the current working directory
    base_path = Path(os.getcwd())
    target_path = (base_path / target_dir).resolve()
    
    if not target_path.exists() or not target_path.is_dir():
        return f"Error: Directory '{target_dir}' does not exist or is not a directory."

    # Perform the scan
    files = scan_files(str(target_path))
    if not files:
        return f"No Python files found in '{target_dir}' after applying filters."

    result_parts = []
    for file in files:
        try:
            content = file.read_text(encoding="utf-8")
            skeleton = get_structural_code(content)
            # Use path relative to the target_path for better readability
            rel_display_path = file.relative_to(target_path)
            result_parts.append(f"### File: {rel_display_path} ###\n{skeleton}\n")
        except Exception as e:
            rel_display_path = file.relative_to(target_path) if target_path in file.parents else file.name
            result_parts.append(f"### File: {rel_display_path} ###\n# [Error] {str(e)}\n")
            
    return "\n".join(result_parts)

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
