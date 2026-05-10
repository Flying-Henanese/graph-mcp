#!/usr/bin/env bash
# =============================================================================
# Gemini Token A/B Test Script
# =============================================================================
# Purpose:
#   Compare token usage and output between two approaches for a given task:
#   1. MCP (Model Context Protocol): Uses the local Archimedes MCP server to
#      retrieve structured codebase context (skeleton + dependency graph).
#   2. Direct: Lets the Gemini CLI inspect local files directly without MCP.
#
# Workflow:
#   1. Parse CLI flags (--setup-mcp, --runs, --model, --out).
#   2. Optionally register the Archimedes MCP server with the Gemini CLI.
#   3. Run the same TASK_PROMPT for both groups, repeating RUNS times.
#   4. Capture raw Gemini output (JSON/JSONL) to timestamped log files.
#   5. Extract token-usage metadata and final text length from each log.
#   6. Write a summary JSONL for easy downstream analysis.
#
# Dependencies:
#   - gemini CLI (https://github.com/google-gemini/gemini-cli)
#   - Node.js (for the inline JSON/JSONL log parser)
#   - uv + project Python environment (for the Archimedes MCP server)
#
# Environment Variables:
#   TASK_PROMPT   - The shared prompt sent to both groups (default provided).
#   RUNS          - Number of repetitions per group (default: 1).
#   MODEL         - Gemini model name, e.g. gemini-2.5-flash (optional).
#   OUTPUT_FORMAT - Gemini CLI output format (default: stream-json).
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration & Defaults
# ---------------------------------------------------------------------------

# Resolve the repository root so all paths are absolute and robust to cwd.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Output directory includes a timestamp so repeated runs never collide.
OUT_DIR="$ROOT_DIR/.tmp/gemini-token-ab/$(date +%Y%m%d-%H%M%S)"

# Optional Gemini model override (empty means CLI default).
MODEL="${MODEL:-}"

# How many times to repeat each group (MCP and Direct).
RUNS="${RUNS:-1}"

# Gemini CLI output format; "stream-json" emits newline-delimited JSON chunks.
OUTPUT_FORMAT="${OUTPUT_FORMAT:-stream-json}"

# Whether to register the Archimedes MCP server before running tests.
SETUP_MCP=0

# The shared task prompt. Both groups receive the same instruction so the
# comparison is fair; only the information source differs (MCP vs direct read).
TASK_PROMPT="${TASK_PROMPT:-Summarize the project module structure and key responsibilities in 120 words or fewer.}"

# ---------------------------------------------------------------------------
# Help / Usage
# ---------------------------------------------------------------------------
usage() {
  cat <<'EOF'
Usage:
  scripts/gemini_token_ab.sh [--setup-mcp] [--runs N] [--model MODEL] [--out DIR]

Environment:
  TASK_PROMPT     Override the shared A/B task prompt.
  RUNS            Number of repetitions, default: 1.
  MODEL           Gemini model passed to `gemini -m`, optional.
  OUTPUT_FORMAT   Gemini output format, default: stream-json.

Examples:
  scripts/gemini_token_ab.sh --setup-mcp --runs 1
  MODEL=gemini-2.5-flash scripts/gemini_token_ab.sh --runs 3
EOF
}

# ---------------------------------------------------------------------------
# Argument Parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --setup-mcp)
      SETUP_MCP=1
      shift
      ;;
    --runs)
      RUNS="$2"
      shift 2
      ;;
    --model)
      MODEL="$2"
      shift 2
      ;;
    --out)
      OUT_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------------

# Ensure the Gemini CLI is installed and available on PATH.
if ! command -v gemini >/dev/null 2>&1; then
  echo "gemini CLI was not found on PATH." >&2
  exit 1
fi

# Create the output directory (including parents) if it doesn't exist.
mkdir -p "$OUT_DIR"

# ---------------------------------------------------------------------------
# Optional MCP Server Registration
# ---------------------------------------------------------------------------
# When --setup-mcp is passed, we tell the Gemini CLI about the local
# Archimedes MCP server. The server is started on-demand by gemini via zsh.
# If registration fails (e.g., server already exists), we warn but continue.
if [[ "$SETUP_MCP" == "1" ]]; then
  echo "Configuring Gemini MCP server 'archimedes'..."
  gemini mcp add archimedes zsh -lc "cd '$ROOT_DIR' && uv run python -m archimedes.server" \
    || echo "MCP setup command failed. If archimedes already exists, remove it first with: gemini mcp remove archimedes" >&2
fi

# ---------------------------------------------------------------------------
# Build Dynamic CLI Arguments
# ---------------------------------------------------------------------------
# If a model was specified, forward it to every gemini invocation.
model_args=()
if [[ -n "$MODEL" ]]; then
  model_args=(-m "$MODEL")
fi

# ---------------------------------------------------------------------------
# Core Test Runner
# ---------------------------------------------------------------------------
# Runs one Gemini invocation for a given group (mcp | direct).
# Arguments:
#   $1 - group name (used for logging and file naming)
#   $2 - run identifier (1-based index)
#   $3 - the prompt string to send
# Writes stdout+stderr to a group-specific JSONL file and echoes the file path.
run_gemini() {
  local group="$1"
  local run_id="$2"
  local prompt="$3"
  local log_file="$OUT_DIR/${group}_${run_id}.jsonl"

  echo "Running ${group} run ${run_id}..." >&2

  if [[ "$group" == "mcp" ]]; then
    # MCP run: allow only the 'archimedes' MCP server so the model must use it.
    gemini "${model_args[@]}" \
      --skip-trust \
      --approval-mode yolo \
      --allowed-mcp-server-names archimedes \
      --output-format "$OUTPUT_FORMAT" \
      -p "$prompt" \
      >"$log_file" 2>&1
  else
    # Direct run: explicitly block all MCP servers so the model reads files itself.
    gemini "${model_args[@]}" \
      --skip-trust \
      --approval-mode yolo \
      --allowed-mcp-server-names __none__ \
      --output-format "$OUTPUT_FORMAT" \
      -p "$prompt" \
      >"$log_file" 2>&1
  fi

  echo "$log_file"
}

# ---------------------------------------------------------------------------
# Log Analysis (Node.js inline script)
# ---------------------------------------------------------------------------
# Parses a Gemini JSONL log to:
#   1. Reconstruct any JSON objects printed by the CLI.
#   2. Recursively search those objects for keys matching token|usage|cached.
#   3. Extract the final response text (looks for text/response/output/content).
#   4. Emit a single JSON summary line for the run.
extract_usage() {
  local group="$1"
  local run_id="$2"
  local log_file="$3"

  node - "$group" "$run_id" "$log_file" <<'NODE'
const fs = require("fs");
const [group, runId, file] = process.argv.slice(2);
const raw = fs.readFileSync(file, "utf8");
const lines = raw.split(/\r?\n/).filter(Boolean);
const objects = [];

// Attempt to parse each non-empty line as JSON (JSONL style).
for (const line of lines) {
  const trimmed = line.trim();
  if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) continue;
  try {
    objects.push(JSON.parse(trimmed));
  } catch {
    // Some Gemini versions print one pretty JSON object instead of JSONL.
  }
}

// Fallback: if no JSONL lines worked, try parsing the entire file as one JSON object.
if (objects.length === 0) {
  try {
    objects.push(JSON.parse(raw));
  } catch {
    // Keep going; the summary will simply report that usage was not found.
  }
}

// Recursively walk parsed objects to find any sub-object whose keys look
// like token counts or usage statistics (e.g., promptTokenCount, cachedContentTokenCount).
const usageCandidates = [];
function walk(value, path = []) {
  if (!value || typeof value !== "object") return;
  if (!Array.isArray(value)) {
    const keys = Object.keys(value);
    const tokenish = keys.filter((key) => /token|usage|cached/i.test(key));
    if (tokenish.length) {
      const picked = {};
      for (const key of tokenish) picked[key] = value[key];
      usageCandidates.push({ path: path.join("."), value: picked });
    }
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => walk(item, path.concat(String(index))));
  } else {
    for (const [key, child] of Object.entries(value)) walk(child, path.concat(key));
  }
}

for (const object of objects) walk(object);

// Best-effort extraction of the final textual answer from the response chunks.
const finalText = objects
  .map((object) => {
    if (typeof object.text === "string") return object.text;
    if (typeof object.response === "string") return object.response;
    if (typeof object.output === "string") return object.output;
    if (typeof object.content === "string") return object.content;
    return "";
  })
  .filter(Boolean)
  .join("\n");

const summary = {
  group,
  run_id: Number(runId),
  log_file: file,
  usage_found: usageCandidates.length > 0,
  usage_candidates: usageCandidates,
  final_text_chars: finalText.length,
};

console.log(JSON.stringify(summary));
NODE
}

# ---------------------------------------------------------------------------
# Prompt Templates
# ---------------------------------------------------------------------------
# Both prompts share the same TASK_PROMPT so the only variable is the source
# of context information (MCP tools vs direct filesystem access).

# MCP prompt: instructs the model to use Archimedes MCP tools exclusively.
# The expected tool sequence is:
#   1. get_context_manifest  -> discover available context blocks
#   2. get_context_block     -> fetch codebase_skeleton and dependency_graph
mcp_prompt=$(cat <<EOF
Use only the Archimedes MCP tools.
First call get_context_manifest, then fetch codebase_skeleton and dependency_graph via get_context_block.
Do not inspect files with shell commands or direct filesystem reads.

Task: $TASK_PROMPT
EOF
)

# Direct prompt: instructs the model to avoid MCP and read files directly.
direct_prompt=$(cat <<EOF
Do not use the Archimedes MCP server or any MCP tools.
Inspect the local repository files directly. Do not modify files.

Task: $TASK_PROMPT
EOF
)

# ---------------------------------------------------------------------------
# Main Execution Loop
# ---------------------------------------------------------------------------
summary_file="$OUT_DIR/summary.jsonl"
: > "$summary_file"  # truncate/create

for run_id in $(seq 1 "$RUNS"); do
  # Run the MCP variant and append its summary.
  mcp_log="$(run_gemini mcp "$run_id" "$mcp_prompt")"
  extract_usage mcp "$run_id" "$mcp_log" >> "$summary_file"

  # Run the Direct variant and append its summary.
  direct_log="$(run_gemini direct "$run_id" "$direct_prompt")"
  extract_usage direct "$run_id" "$direct_log" >> "$summary_file"
done

# ---------------------------------------------------------------------------
# Summary Printer (Node.js inline script)
# ---------------------------------------------------------------------------
# Reads the summary JSONL and prints a human-readable table to stdout.
node - "$summary_file" <<'NODE'
const fs = require("fs");
const file = process.argv[2];
const rows = fs.readFileSync(file, "utf8").trim().split(/\r?\n/).filter(Boolean).map(JSON.parse);
console.log("\nSummary:");
for (const row of rows) {
  console.log(`- ${row.group} run ${row.run_id}: usage_found=${row.usage_found} log=${row.log_file}`);
  if (row.usage_found) {
    // Show up to the last 3 candidate objects to keep output concise.
    const compact = row.usage_candidates.slice(-3);
    for (const item of compact) {
      console.log(`  ${item.path || "<root>"} ${JSON.stringify(item.value)}`);
    }
  }
}
console.log(`\nWrote summary to ${file}`);
NODE

