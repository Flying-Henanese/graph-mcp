# Archimedes Project Guidelines

## 1. Project Vision
Archimedes is a minimalist, local **MCP Server** designed to act as "X-ray glasses" for LLMs. It dynamically strips Python code implementation details, returning only the "skeleton" (interfaces, signatures, dependencies) to provide high-level context with minimal token usage.

## 2. Technical Stack & Standards
- **Language**: Python 3.10+
- **Dependency Management**: **`uv`** is mandatory for all package management, virtual environments, and script execution. Dependencies **must** be logically grouped in `pyproject.toml`. Production-critical libraries go in `dependencies`, while development tools (e.g., `pytest`, `ruff`, `mypy`) must be isolated in a `dev` group (using `[dependency-groups]` or `[project.optional-dependencies]`).
- **MCP Framework**: Anthropic's official `mcp` Python SDK.
- **Core Parser**: Python's native `ast` module.
- **Configuration**: `pyyaml` for `archimedes.yaml` management.
- **Style**: Standard Python (PEP 8), strict type hinting.

## 3. Directory Structure
Adhere to the standard `src` layout:
```text
archimedes/
├── src/
│   └── archimedes/
│       ├── __init__.py
│       ├── server.py      # MCP Server entry point
│       ├── skeleton.py    # AST processing logic
│       └── config.py      # archimedes.yaml parser
├── tests/
├── archimedes.yaml        # Default configuration
├── pyproject.toml
└── README.md
```

## 4. Mandatory Development Rules
- **Strict Type Hinting**: All function signatures (including return types), class attributes, and complex variables MUST have explicit and strict Python type hints. Use the `typing` module (`Dict`, `List`, `Optional`, `Any`, etc.) extensively to ensure static analysis safety and code readability.
- **AST Integrity**: When extracting skeletons, *always* replace the body of `FunctionDef` and `AsyncFunctionDef` with `pass`. Ensure docstrings are preserved if they provide interface clarity.
- **Zero-Dependency V1**: Do not introduce databases, caching layers, or external state management in the MVP.
- **Path Safety**: All file operations must be scoped within the user-provided `target_dir` and respect `archimedes.yaml` filters.
- **Verification & Testing**: 
    - Every new tool or feature must be verified using `uv run`.
    - **Detailed Testing is Mandatory**: Use `pytest` for unit and integration tests. No code change is complete without corresponding test validation.
    - Automated tests must cover: AST stripping logic, config parsing, and MCP tool responses.
- **Bilingual Documentation**: Any modification to `README.md` must be synchronized with `README_CN.md`, and vice-versa, to ensure consistency between English and Chinese documentation.

## 5. Testing Strategy
- **Framework**: `pytest`
- **Location**: `tests/` directory.
- **CI/CD Readiness**: Ensure tests can be run via `uv run pytest`.
- **Coverage**: Focus on edge cases like syntax errors in target files, deep directory structures, and complex AST nodes (nested classes/functions).

## 5. Core MCP Tools (V1)
1. **`get_codebase_skeleton`**:
   - Input: `target_dir` (relative path).
   - Logic: Filter -> AST Parse -> Body Strip -> Concatenate.
2. **`read_full_implementation`**:
   - Input: `file_path`.
   - Logic: Direct read of source code for targeted deep-dives.

## 6. Config Schema (`archimedes.yaml`)
Always respect the following structure:
```yaml
version: "1.0"
project_name: "Archimedes"
indexing:
  include: ["src/**/*.py"]
  exclude: ["tests/**", "**/__pycache__/**", "venv/**", ".git/**"]
```
