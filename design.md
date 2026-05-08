# Archimedes 项目方案书 (V1.0 - MVP 阶段)

## 1. 项目定位

一个极其轻量、专注的本地 **MCP Server**。它的核心职责只有一个：**作为大模型的“透视眼镜”**。当大模型需要了解 Python 代码库时，负责在本地动态剥离代码的血肉（实现细节），只把骨架（接口、签名、依赖）作为上下文通过 MCP 协议返回给 `gemini-cli`。
本项目是一个专为大模型编程工具（如 Gemini-CLI）设计的轻量级结构感知中间件（MCP Server），其核心功能是利用 AST（抽象语法树）技术对复杂的 Python 工程进行深度扫描，动态剥离函数与类的内部实现逻辑，仅向 AI 暴露极简的接口签名与依赖拓扑；其终极目标是巧妙绕过大模型的长上下文窗口瓶颈，以极低的 Token 消耗赋予 AI 瞬间洞悉超大型项目“宏观骨架”的能力，从而实现更精准、高效且低成本的局部代码读取与系统级重构

## 2. 核心技术栈 (极致精简)

* **开发语言：** Python 3.10+
* **通信协议：** `mcp` (Anthropic 官方提供的 Python SDK，用于构建标准的 MCP Server)
* **核心解析器：** `ast` (Python 原生抽象语法树模块)
* **配置管理：** `pyyaml` (用于读取忽略/包含范围)
* *(V1.0 移除了所有数据库和状态管理依赖)*

## 3. V1.0 暴露的核心 Tools（MCP 工具）

我们将通过 MCP 协议向 `gemini-cli` 暴露两个最基础但最致命的工具，形成大模型的“宏观寻路 -> 微观操作”闭环：

### Tool 1: `get_codebase_skeleton` (获取代码骨架)

* **作用：** 扫描指定目录，返回剔除了内部逻辑的 Python 代码骨架。
* **参数：**
* `target_dir` (string): 需要扫描的相对目录路径（例如 `src/` 或 `lib/parser/`）。


* **执行逻辑：**
1. 根据 `archimedes.yaml` 的黑白名单过滤文件。
2. 使用 `ast` 解析每个 `.py` 文件。
3. 将所有 `FunctionDef` 和 `AsyncFunctionDef` 的 `body` 替换为 `pass`。
4. 拼接成一份极简的伪代码文本返回。



### Tool 2: `read_full_implementation` (精读源码)

* **作用：** 当 Gemini 通过上面的“骨架”发现某个具体函数存在问题时，调用此工具获取该文件的完整源码。
* **参数：**
* `file_path` (string): 目标文件的相对路径。


* **执行逻辑：** 直接读取文件并返回完整文本。

---

## 4. 业务流转示例 (无缓存版)

1. **用户：** `gemini-cli "梳理一下项目的 PDF 解析流程并重构其中的高并发模块。"`
2. **Gemini 思考：** "我不知道项目长什么样，我先调用工具。"
3. **Tool Call:** `get_codebase_skeleton(target_dir="src/")`
4. **Archimedes 响应：** 返回 `src/` 目录下所有文件的骨架（只有几千 Token）。
5. **Gemini 思考：** "看懂了，入口在 `parser_engine.py`，并发池在 `worker.py`。但我需要看看并发池的具体逻辑。"
6. **Tool Call:** `read_full_implementation(file_path="src/worker.py")`
7. **Archimedes 响应：** 返回 `worker.py` 的全量代码。
8. **Gemini 输出：** 结合骨架的全局视野和 worker 的局部源码，给出重构方案。

---

## 5. 配置文件设计 (`archimedes.yaml`)

即便是 MVP，黑白名单配置也是必须的，否则读取骨架时容易把不需要的测试文件或第三方包扫进去。

```yaml
version: "1.0"
project_name: "Jumo"

indexing:
  include:
    - "src/**/*.py"
    - "api/**/*.py"
  exclude:
    - "tests/**"
    - "**/__pycache__/**"
    - "venv/**"

```

---

## 6. Phase 2: 演进计划 (上下文缓存优化)

正如你所说，如果工程达到几十万行，即使是压缩后的“骨架”，每次都重新通过文本发给大模型也是一种巨大的 Token 浪费，并且会拉高首字延迟（TTFT）。

在 V1.0 跑通逻辑闭环后，我们将启动 **V2.0: 结构哈希与云端缓存 (Structural Hash & Cloud Caching)**：

* **引入状态管理：** 加入 SQLite，记录每一次提取的骨架的“结构哈希值”。
* **MCP 协议扩展：** 增加 `check_cache_status` 工具。
* **桥接 Context Caching：** 当哈希没有变化时，利用 Gemini 官方的 `cachedContents` API 将骨架固化在云端，彻底实现“零 Token 消耗加载项目架构”。

