#!/usr/bin/env bash
"${0%/*}/../" >/dev/null 2>&1 || true
set -euo pipefail

# Cross-platform Bash helper to launch mc_robustness.py (or another Python script)
# in the background with stdout/stderr redirected to `results/`.
# Behavior mirrors `scripts/run_mc_background.ps1` used on Windows.
#
# Usage examples:
#   ./scripts/run_mc_background.sh --script scripts/mc_robustness.py --extra-args "--symbol PIPPINUSDT --mc-iter 20"
#   ./scripts/run_mc_background.sh --name pippinusdt_mc --extra-args "--symbol PIPPINUSDT --mc-iter 20 --workers 4"

progname=$(basename "$0")
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

PYTHON_EXEC=python
SCRIPT="${SCRIPT_DIR}/mc_robustness.py"
RESULTS_DIR=results
NAME="mc_bg"
EXTRA_ARGS=""

print_usage() {
  cat <<EOF
Usage: $progname [--python-exec PATH] [--script PATH] [--results-dir DIR] [--name PREFIX] [--extra-args "..."]

Defaults:
  --script    : ${SCRIPT} (mc_robustness.py in scripts/)
  --results-dir: ${RESULTS_DIR}
  --name      : ${NAME}

Examples:
  $progname --script scripts/mc_robustness.py --extra-args "--symbol PIPPINUSDT --mc-iter 20 --workers 4"
EOF
}

while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --python-exec)
      PYTHON_EXEC="$2"; shift 2;;
    --script)
      SCRIPT="$2"; shift 2;;
    --results-dir)
      RESULTS_DIR="$2"; shift 2;;
    --name)
      NAME="$2"; shift 2;;
    --extra-args)
      EXTRA_ARGS="$2"; shift 2;;
    -h|--help)
      print_usage; exit 0;;
    *)
      echo "Unknown arg: $1" >&2; print_usage; exit 2;
      ;;
  esac
done

mkdir -p "${RESULTS_DIR}"

# Build timestamped log filenames. Use name + timestamp to avoid collisions.
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
stdout_log="${RESULTS_DIR}/${NAME}_${timestamp}_stdout.log"
stderr_log="${RESULTS_DIR}/${NAME}_${timestamp}_stderr.log"

# Ensure the script path is resolved relative to the repo when given as relative path.
if [[ ! "$SCRIPT" = /* ]]; then
  SCRIPT="$(cd "${SCRIPT_DIR}" && cd "$(dirname "$SCRIPT")" 2>/dev/null || true && printf "%s/%s" "$(pwd)" "$(basename "$SCRIPT")")"
fi

if [[ ! -f "$SCRIPT" ]]; then
  echo "Error: script not found: $SCRIPT" >&2
  exit 2
fi

# Assemble the command: python <script> <extra-args>
IFS=' ' read -r -a script_args <<< "$EXTRA_ARGS"
cmd=("$PYTHON_EXEC" "$SCRIPT")
if [[ ${#script_args[@]} -gt 0 ]]; then
  for a in "${script_args[@]}"; do
    cmd+=("$a")
  done
fi

# Launch detached: prefer setsid, fall back to nohup, otherwise background with &
if command -v setsid >/dev/null 2>&1; then
  setsid "${cmd[@]}" >"$stdout_log" 2>"$stderr_log" &
  pid=$!
elif command -v nohup >/dev/null 2>&1; then
  nohup "${cmd[@]}" >"$stdout_log" 2>"$stderr_log" &
  pid=$!
else
  "${cmd[@]}" >"$stdout_log" 2>"$stderr_log" &
  pid=$!
fi

echo "Started background process: PID=${pid}"
echo "Stdout -> ${stdout_log}"
echo "Stderr -> ${stderr_log}"

exit 0
