# Archimedes A/B Test Results: Deep Architectural Analysis

**Date:** 2026-05-10
**Project:** `RAG-Anything` (~127 files)
**Model:** `gemini-3-flash-preview`
**Task:** "Please draw a system architecture diagram and a data flow diagram."

## 1. Token Usage Comparison

| Metric | MCP Mode (Archimedes) | Direct Mode (File Read) | Difference (Savings) |
| :--- | :--- | :--- | :--- |
| **Total Tokens** | **50,023** | 114,444 | **-56.3%** |
| **Input Tokens** | 48,429 | 110,289 | -56.1% |
| **Output Tokens** | 977 | 2,759 | -64.6% |
| **Cached Tokens** | 23,105 | 55,266 | -58.2% |

## 2. Executive Summary
In this test, the **MCP Mode (Archimedes)** demonstrated a significant efficiency advantage, reducing token consumption by over **56%** compared to traditional direct file reading. This validates Archimedes' core value proposition: providing a high-fidelity "structural map" of a large codebase without the overhead of processing irrelevant implementation details.

## 3. Deep Dive Analysis

### Why Direct Mode Failed to Compete
- **Context Bloat**: To generate accurate diagrams, the model required a deep understanding of class interactions across multiple modules (`raganything.py`, `processor.py`, `modalprocessors.py`, etc.).
- **Manual Traversal**: In Direct Mode, the agent was forced to read the *entire content* of these files. As it traversed the dependency chain, the context window grew uncontrollably, reaching 114k tokens.
- **Redundant Processing**: Much of the tokens were spent on "bloody" implementation details (internal loops, regex patterns, error handling) that are irrelevant to high-level architecture.

### Why Archimedes Won
- **Information Dehydration**: Archimedes provided only the "skeletons" (signatures and docstrings). This allowed the model to see the "connective tissue" of the system (how `RAGAnything` inherits from `QueryMixin` and calls `ModalProcessor`) without reading the underlying math or logic.
- **O(1) Structural Awareness**: Instead of many iterative `read_file` calls, the model obtained the entire project's structural interface in a single context block.
- **Cognitive Clarity**: By stripping the noise, the model could focus entirely on the *relationships* between components, which is the essence of architectural drawing.

## 4. Conclusion
For simple summary tasks, the cost of generating a skeleton might outweigh the benefits. However, for **Deep Analysis (Architecture, Data Flow, Refactoring, Dependency Mapping)** in projects exceeding 100 files, Archimedes is an essential tool for maintaining high model performance while drastically reducing costs and latency.

## 5. Raw Logs
Logs are stored in: `.tmp/gemini-token-ab/20260510-141439/`
- Summary: `summary.jsonl`
- MCP Log: `mcp_1.jsonl`
- Direct Log: `direct_1.jsonl`
