# Archimedes A/B Test Results

**Date:** 2026-05-10
**Model:** `gemini-3-flash-preview`
**Task:** "Summarize the project module structure and key responsibilities in 120 words or fewer."

## Token Usage Comparison

| Metric | MCP Mode (Archimedes) | Direct Mode (File Read) |
| :--- | :--- | :--- |
| **Total Tokens** | 50,733 | 14,327 |
| **Input Tokens** | 50,326 | 12,529 |
| **Output Tokens** | 407 | 180 |
| **Cached Tokens** | 23,154 | 0 |

## Analysis
- **Token Count**: In this run, the **Direct Mode** was significantly more efficient in terms of raw token count.
- **Why?**:
    - For smaller projects, the overhead of calling `get_context_manifest` and retrieving multiple skeletons can sometimes exceed the tokens saved by stripping implementation details.
    - Archimedes is designed for large-scale codebases where stripping thousands of lines of implementation logic provides exponential savings.
- **Cache Benefit**: MCP mode utilized significant caching (23,154 tokens), which would reduce costs/latency in repeated queries.

## Raw Logs
Logs are stored in: `.tmp/gemini-token-ab/20260510-120352/`
- Summary: `summary.jsonl`
- MCP Log: `mcp_1.jsonl`
- Direct Log: `direct_1.jsonl`
