# Scripts

This directory contains helper scripts and drivers used to run backtests
and background jobs.

## run_mc_background.sh

- Purpose: launch `scripts/mc_robustness.py` (or another Python script) in the
  background on Unix-like systems, redirecting stdout/stderr to `results/` and
  printing the background PID and log file paths.
- Make executable: `chmod +x scripts/run_mc_background.sh` (or use the git
  chmod command shown below to set it in the repository index).
- Example usage:

```bash
# Default: run mc_robustness.py from `scripts/` with extra arguments
./scripts/run_mc_background.sh --extra-args "--symbol PIPPINUSDT --mc-iter 20 --workers 2"

# Specify python, script path, and custom name/log prefix
./scripts/run_mc_background.sh --python-exec /usr/bin/python3 \
  --script scripts/mc_robustness.py --name pippinusdt_mc \
  --extra-args "--symbol PIPPINUSDT --mc-iter 20 --workers 2"
```

If your CI environment uses Git and you want the executable bit recorded in
the repository, run:

```bash
git update-index --add --chmod=+x scripts/run_mc_background.sh
```
