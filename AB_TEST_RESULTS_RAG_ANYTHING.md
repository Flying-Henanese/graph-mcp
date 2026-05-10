# Archimedes A/B Test Results: RAG-Anything

**Date:** 2026-05-10
**Project:** `RAG-Anything` (~127 files)
**Model:** `gemini-3-flash-preview`
**Task:** "Analyze the core RAG pipeline in this project. Identify the key classes involved in document loading, embedding generation, and retrieval, and explain their interactions."

## Token Usage Comparison

| Metric | MCP Mode (Archimedes) | Direct Mode (File Read) |
| :--- | :--- | :--- |
| **Total Tokens** | 90,075 | 246,937 |
| **Input Tokens** | 86,529 | 243,260 |
| **Output Tokens** | 1,118 | 1,055 |
| **Cached Tokens** | 43,053 | 173,190 |
| **Token Savings** | **~63.5% Savings** | 基准 |

## Analysis
- **The Tipping Point**: 与之前的微型项目测试不同，在 `RAG-Anything` 这样中等规模的项目中，Archimedes 的优势开始显现。
- **Direct Mode 行为**: 模型在直接读取模式下，为了回答“核心 Pipeline”这种深度问题，被迫读取了大量的实现代码（Implementation），导致 Token 飙升至 24.7 万。
- **Archimedes 优势**:
    - **Skeleton 提取**: 仅通过接口和签名，模型就理清了 `raganything` 核心库中的类关系。
    - **精准信息**: 避免了模型加载数千行具体的数学计算、日志处理等无关实现逻辑。
- **结论**: 对于超过 100 个文件或存在复杂深度逻辑的项目，Archimedes 能显著降低上下文压力，不仅省钱，还能让模型更聚焦于架构设计而非底层细节。

## Raw Logs
Logs are stored in: `.tmp/gemini-token-ab/20260510-121930/`
