# Archimedes 项目方案书 (V2.0 - 实时缓存与图拓扑阶段)

## 1. 项目定位

一个极其轻量、专注的本地 **MCP Server**。它的核心职责只有一个：**作为大模型的“透视眼镜”**。当大模型需要了解 Python 代码库时，负责在本地动态剥离代码的血肉（实现细节），只把骨架（接口、签名、依赖）作为上下文通过 MCP 协议返回给大模型编程工具（如 Gemini-CLI）。

本项目利用 AST（抽象语法树）技术对复杂的 Python 工程进行深度扫描，动态剥离函数与类的内部实现逻辑，仅向 AI 暴露极简的接口签名与依赖拓扑；结合基于 `watchdog` 的后台实时监控和内存状态管理，巧妙绕过大模型的长上下文窗口瓶颈，以极低的 Token 消耗和 O(1) 的响应延迟，赋予 AI 瞬间洞悉超大型项目“宏观骨架”的能力，从而实现更精准、高效且低成本的局部代码读取与系统级重构。

## 2. 核心技术栈 (高效与实时)

* **开发语言：** Python 3.10+
* **通信协议：** `FastMCP` (构建标准的 MCP Server)
* **核心解析器：** `ast` (Python 原生抽象语法树模块，用于提取结构)
* **依赖图谱构建：** `rustworkx` (用于构建和序列化高性能的有向无环依赖图 DAG)
* **实时状态管理：** `watchdog` (后台监听文件系统事件，实现增量哈希和结构缓存)
* **配置管理：** `pyyaml` (用于读取忽略/包含范围) 与 `pathspec` (支持 `.gitignore` 规则)

## 3. 暴露的核心 Tools（MCP 工具）

我们将通过 MCP 协议暴露以下核心工具，形成大模型的“状态感知 -> 宏观寻路 -> 微观操作”闭环：

### Tool 1: `check_cache_status` (检查缓存状态)
* **作用：** 极速返回当前代码库全局结构哈希值 (Global Structural Hash) 和文件数量。O(1) 内存读取。
* **参数：** 无。客户端可利用此哈希判断本地缓存的骨架是否过期。

### Tool 2: `get_codebase_skeleton` (获取代码骨架)
* **作用：** 从内存中直接提取全量或被过滤后的 Python 代码骨架，包含所有类、方法、文档字符串签名。
* **参数：** 无 (基于服务器启动时的监控目录工作)。
* **执行逻辑：**
  直接读取 `ProjectState` 内存中由后台 `watchdog` 实时维护的骨架缓存，并在响应头附带 `GLOBAL_STRUCTURAL_HASH`。

### Tool 3: `get_dependency_graph` (获取依赖图谱)
* **作用：** 将项目宏观架构作为 JSON 格式的依赖图 (Dependency Graph) 返回。节点代表模块及导出的类/函数，边代表模块间的 `import` 关系。
* **参数：** 无。
* **执行逻辑：** 懒加载模式。当代码结构发生变化时，利用 `rustworkx` 重新构建图并缓存 JSON；若无变化，则直接返回内存缓存 (O(1))。

### Tool 4: `read_full_implementation` (精读源码)
* **作用：** 当大模型通过“骨架”或“依赖图”发现目标模块时，调用此工具获取该文件的完整源码。
* **参数：**
  * `file_path` (string): 目标文件的相对路径。

---

## 4. 业务流转示例 (实时缓存版)

1. **用户：** `gemini-cli "梳理一下项目的解析流程并重构其中的高并发模块。"`
2. **Gemini 思考：** "我需要了解当前项目的整体结构，首先检查状态。"
3. **Tool Call:** `check_cache_status()`
4. **Archimedes 响应：** 返回全局哈希 `abcd123...` 和文件数。
5. **Gemini 思考：** "发现新项目或哈希有变，拉取最新骨架和依赖图。"
6. **Tool Call:** `get_codebase_skeleton()` 和 `get_dependency_graph()`
7. **Archimedes 响应：** 秒级 (O(1)) 返回全项目骨架文本及 JSON 拓扑图。
8. **Gemini 思考：** "看懂了，通过依赖图发现入口在 `server.py`，并发依赖在 `watcher.py`。我需要看看 `watcher.py` 的具体逻辑。"
9. **Tool Call:** `read_full_implementation(file_path="src/archimedes/watcher.py")`
10. **Archimedes 响应：** 返回该文件的全量代码。
11. **Gemini 输出：** 结合宏观视野与局部源码，给出精准重构方案。

---

## 5. 配置文件设计 (`archimedes.yaml`)

黑白名单配置依然是核心，用于精确控制被监控和分析的文件范围。

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
    - ".git/**"
    - ".venv/**"
```

---

## 6. Phase 3: 未来演进计划

V2.0 已经通过内存级 `watchdog` 缓存和 `rustworkx` 拓扑图实现了极致的性能与结构化感知。下一步的演进方向将专注于更精细的语义分析和上下文应用：

* **函数级提取精度 (Function-level Precision)：** 允许大模型直接查询某个具体函数或类的完整实现，而无需读取整个文件，进一步压缩 Token 消耗。
* **架构图生成 (Architecture Diagram Generation)：** 将底层的 `rustworkx` 图数据直接转换为 Mermaid 语法，供 AI 生成可视化的项目架构图。
* **本地代码语义检索 (Local Codebase Search)：** 结合结构化图谱，实现简单的本地代码关键词和符号检索引擎。

---

## 7. 配置加载性能优化 (v2.1 补充)

为了进一步提升大规模文件扫描时的性能，并确保在长期运行的 MCP 服务中能够实时感知配置变更，我们将对 `config.py` 进行如下优化：

### 7.1 智能缓存策略 (Smart Caching)
*   **痛点：** `is_file_tracked` 在单个文件检查时可能频繁触发磁盘 I/O 和 YAML 解析。
*   **方案：** 引入基于 **(路径 + 修改时间 mtime)** 的双重校验缓存机制。
*   **逻辑：**
    1.  利用 `functools.lru_cache` 缓存编译后的 `PathSpec` 对象。
    2.  每次调用 `get_exclude_spec` 时，先获取 `archimedes.yaml` 的 `st_mtime`。
    3.  将 `(config_path, mtime)` 作为缓存键。只有当文件内容真正发生变化时，才会触发重新解析和正则编译。
    4.  对于 `scan_files` 等批量操作，保持现有的“单次加载，多次复用”模式，确保 O(N) 扫描效率。

### 7.2 性能与实时的平衡
*   **极速响应：** `os.stat` 获取 mtime 是极轻量级的系统调用，远快于文件读取和正则重新编译。
*   **零配置感知：** 用户修改 `exclude` 规则后，下一次文件扫描或状态检查将自动应用新规则，无需重启 MCP Server。