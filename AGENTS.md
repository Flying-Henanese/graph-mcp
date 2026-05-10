# Archimedes Codex Guidelines

## Project Vision

Archimedes is a local MCP server that gives LLM clients a compact structural view of Python codebases. It extracts code skeletons, computes structural hashes, builds dependency graphs, and exposes cache-friendly context blocks so agents can understand large projects without reading every implementation first.

## Technical Stack

- **Language**: Python 3.10+.
- **Package management**: Use `uv` for dependency installation, virtual environments, and command execution.
- **MCP framework**: `mcp` with FastMCP.
- **Parsing**: Python's built-in `ast` module.
- **Graph engine**: `rustworkx`.
- **File watching**: `watchdog`.
- **Configuration**: `pyyaml` and `pathspec` for `archimedes.yaml`.
- **Tests and linting**: `pytest` and `ruff`.

## Repository Layout

Use the existing `src` layout:

```text
graph-mcp/
├── src/archimedes/
│   ├── __init__.py
│   ├── config.py      # archimedes.yaml loading and include/exclude scanning
│   ├── graph.py       # AST export/import extraction and dependency graph building
│   ├── server.py      # FastMCP tool surface
│   ├── skeleton.py    # AST skeleton extraction and structural hashing
│   ├── state.py       # thread-safe runtime cache state
│   └── watcher.py     # watchdog initialization and incremental state updates
├── tests/
├── scripts/
├── archimedes.yaml
├── README.md
├── README_CN.md
└── pyproject.toml
```

## Development Rules

- Prefer descriptive names over generic names. When several values have the same shape, use prefixes such as `source_`, `target_`, `current_`, or `resolved_`.
- Use snake_case for variable names and function names. Use PascalCase for class names.
- Be sure to document your code with clear docstrings.
- Prefer dataclasses or explicit classes for fixed internal schemas. Avoid raw dictionaries for core graph or state entities unless the value is deliberately JSON-like output.
- Use strict type hints on function signatures, class attributes, and non-trivial local variables.
- Keep file operations scoped to the monitored project root and respect `archimedes.yaml` include/exclude filters.
- Preserve deterministic output ordering for skeletons, manifests, and dependency graph JSON because downstream clients may cache by hash or prompt prefix.
- When extracting skeletons, strip function and async function bodies to `pass` while preserving useful docstrings and nested definitions.
- When changing README content, update both `README.md` and `README_CN.md` in the same turn.

## Current MCP Tools

- `get_dependency_graph()`: returns cached or rebuilt dependency graph JSON.
- `get_codebase_skeleton()`: returns all tracked Python skeletons with `GLOBAL_STRUCTURAL_HASH`.
- `check_cache_status()`: returns the global structural hash, tracked file count, and readiness status.
- `read_full_implementation(file_path: str)`: reads a specific source file for targeted deep dives.
- `get_context_manifest()`: returns stable metadata for cacheable context blocks.
- `get_context_block(block_id: str)`: returns `codebase_skeleton` or `dependency_graph` as hash-addressed context blocks.

## Testing

- Run linting with `uv run ruff check .`.
- Run the test suite with `uv run pytest`.
- Add or update tests for every behavior change. Important coverage areas are AST stripping, structural hashing, include/exclude scanning, dependency graph resolution, MCP tool responses, context block metadata, and watcher updates.
- For token experiments, use `scripts/gemini_token_ab.sh`; raw logs are written under `.tmp/gemini-token-ab/`.

## Config Schema

Respect this shape for `archimedes.yaml`:

```yaml
version: "1.0"
project_name: "Archimedes"
indexing:
  include:
    - "src/**/*.py"
  exclude:
    - "tests/**"
    - "**/__pycache__/**"
    - "venv/**"
    - ".venv/**"
    - ".git/**"
```

