# Gemini CLI 项目索引与上下文 management 机制

Gemini CLI 通过以下四个层级来构建和利用本地项目的“索引”：

## 1. 结构化快照 (The Map) - 会话级
在每个会话开始时，CLI 会自动扫描当前目录：
- **目录树 (File Tree)**: 递归生成所有文件和文件夹的列表。
- **环境元数据**: 包括 OS、当前路径、日期。
- **排除逻辑**: 自动忽略 `.geminiignore` 和 `.gitignore` 中的内容（如 `node_modules`, `.git`）。
- **目的**: 让 AI 知道“项目里有什么文件”，但不包括“文件里有什么内容”。

## 2. 启发式预读 (Heuristic Pre-reading) - 会话级
CLI 会自动将一些关键文件的内容注入到初始上下文中：
- **README.md / README_CN.md**: 项目的说明书。
- **配置文件**: 如 `pyproject.toml`, `package.json`, `archimedes.yaml`。
- **GEMINI.md**: 专门为 AI 准备的项目规范指南。

## 3. 按需工具检索 (On-Demand Retrieval) - 动态级
当初始信息不足以回答问题时，AI 会自主调用工具：
- **`grep_search`**: 像程序员一样在全量代码中搜索特定关键词。
- **`read_file`**: 仅在需要时读取特定文件的具体行。
- **实现**: 这种方式保证了只有**相关的**代码片段会占用 Token。

## 4. 本地语义索引 (RAG / Labs) - 持久化级 (可选)
对于超大型项目，可以使用 `gemini labs rag index` 命令：
- **分片 (Chunking)**: 将代码切成 1000 字符左右的小块。
- **向量化 (Embeddings)**: 将代码块转化为多维向量。
- **本地数据库**: 存储在本地 SQLite 或向量库中，支持语义搜索（通过意义而不是关键词来查找）。

## 总结：为什么 A/B 测试中“直接读取”Token 更少？
在本次测试中，由于项目规模较小，**层级 1 和层级 2** 提供的上下文已经足以让模型完成“总结项目结构”的任务。模型识别到了 `README` 和 `pyproject.toml` 中的信息，因此无需再调用工具读取每一个 `.py` 文件的源码，从而极大地节省了 Token。

---

## 5. 数据存储位置 (Storage Locations)

Gemini CLI 的索引与缓存数据不会污染你的项目源码，它们主要分布在以下位置：

### A. 项目临时数据 (Temporary Data)
**路径**: `~/.gemini/tmp/[项目名]/`
- **内容**: 
    - `chats/`: 存储每一次对话的详细 JSONL 日志。
    - `logs.json`: 记录会话的元数据。
- **特性**: 随用随生，通常不需要手动清理。

### B. 全局持久化数据 (Persistent Data)
**路径**: `~/.gemini/`
- **内容**: 
    - `skills/`: 已安装的智能技能（Agent Skills）。
    - `extensions/`: MCP 插件及其配置。
    - `projects.json`: 记录所有已知项目的路径。
    - `settings.json`: 全局偏好设置。
- **特性**: 跨项目共享。

### C. 项目内配置 (Local Config)
**路径**: 当前项目根目录 `./`
- **内容**: 
    - `GEMINI.md`: 被 Git 追踪的项目级指令（AI 必读）。
    - `.gemini/`: 项目特定的安全策略（Policy）或本地环境覆盖。
- **特性**: 随代码分发。
