#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/.tmp/gemini-token-ab/$(date +%Y%m%d-%H%M%S)"
MODEL="${MODEL:-}"
RUNS="${RUNS:-1}"
OUTPUT_FORMAT="${OUTPUT_FORMAT:-stream-json}"
SETUP_MCP=0

TASK_PROMPT="${TASK_PROMPT:-Summarize the project module structure and key responsibilities in 120 words or fewer.}"

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

if ! command -v gemini >/dev/null 2>&1; then
  echo "gemini CLI was not found on PATH." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

if [[ "$SETUP_MCP" == "1" ]]; then
  echo "Configuring Gemini MCP server 'archimedes'..."
  gemini mcp add archimedes zsh -lc "cd '$ROOT_DIR' && uv run python -m archimedes.server" \
    || echo "MCP setup command failed. If archimedes already exists, remove it first with: gemini mcp remove archimedes" >&2
fi

model_args=()
if [[ -n "$MODEL" ]]; then
  model_args=(-m "$MODEL")
fi

run_gemini() {
  local group="$1"
  local run_id="$2"
  local prompt="$3"
  local log_file="$OUT_DIR/${group}_${run_id}.jsonl"

  echo "Running ${group} run ${run_id}..." >&2

  if [[ "$group" == "mcp" ]]; then
    gemini "${model_args[@]}" \
      --skip-trust \
      --approval-mode yolo \
      --allowed-mcp-server-names archimedes \
      --output-format "$OUTPUT_FORMAT" \
      -p "$prompt" \
      >"$log_file" 2>&1
  else
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

for (const line of lines) {
  const trimmed = line.trim();
  if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) continue;
  try {
    objects.push(JSON.parse(trimmed));
  } catch {
    // Some Gemini versions print one pretty JSON object instead of JSONL.
  }
}

if (objects.length === 0) {
  try {
    objects.push(JSON.parse(raw));
  } catch {
    // Keep going; the summary will say usage was not found.
  }
}

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

mcp_prompt=$(cat <<EOF
Use only the Archimedes MCP tools.
First call get_context_manifest, then fetch codebase_skeleton and dependency_graph via get_context_block.
Do not inspect files with shell commands or direct filesystem reads.

Task: $TASK_PROMPT
EOF
)

direct_prompt=$(cat <<EOF
Do not use the Archimedes MCP server or any MCP tools.
Inspect the local repository files directly. Do not modify files.

Task: $TASK_PROMPT
EOF
)

summary_file="$OUT_DIR/summary.jsonl"
: > "$summary_file"

for run_id in $(seq 1 "$RUNS"); do
  mcp_log="$(run_gemini mcp "$run_id" "$mcp_prompt")"
  extract_usage mcp "$run_id" "$mcp_log" >> "$summary_file"

  direct_log="$(run_gemini direct "$run_id" "$direct_prompt")"
  extract_usage direct "$run_id" "$direct_log" >> "$summary_file"
done

node - "$summary_file" <<'NODE'
const fs = require("fs");
const file = process.argv[2];
const rows = fs.readFileSync(file, "utf8").trim().split(/\r?\n/).filter(Boolean).map(JSON.parse);
console.log("\nSummary:");
for (const row of rows) {
  console.log(`- ${row.group} run ${row.run_id}: usage_found=${row.usage_found} log=${row.log_file}`);
  if (row.usage_found) {
    const compact = row.usage_candidates.slice(-3);
    for (const item of compact) {
      console.log(`  ${item.path || "<root>"} ${JSON.stringify(item.value)}`);
    }
  }
}
console.log(`\nWrote summary to ${file}`);
NODE

