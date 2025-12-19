"""Supervisor that starts the backend uvicorn in a separate process group
so console control events sent to the current console are less likely to
terminate the backend. It will auto-restart on unexpected exits.

Run with the project venv Python:
  & '.\.venv_backtest_bak\Scripts\python.exe' run_backend_supervisor.py

Logs are written to `backend_supervisor.log`.
"""
import subprocess
import sys
import time
import os
from datetime import datetime

LOG = "backend_supervisor.log"

def log(msg: str):
    line = f"{datetime.utcnow().isoformat()} {msg}\n"
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="")


def start_backend():
    # Use same python executable (venv) to run uvicorn module
    python = sys.executable
    cmd = [python, "-m", "uvicorn", "backend.app_main:app", "--port", "8200", "--log-level", "debug"]

    # Windows-specific flag to create a new process group
    creationflags = 0
    if os.name == "nt":
        # CREATE_NEW_PROCESS_GROUP = 0x00000200
        creationflags = 0x00000200

    log(f"Starting backend: {' '.join(cmd)} (creationflags={creationflags})")
    with open("backend_supervisor_stdout.log", "ab") as out, open("backend_supervisor_stderr.log", "ab") as err:
        p = subprocess.Popen(cmd, stdout=out, stderr=err, creationflags=creationflags)
    return p


def main():
    log("Supervisor starting")
    try:
        while True:
            p = start_backend()
            # wait for process to exit
            rc = p.wait()
            log(f"Backend exited with code {rc}")
            # if supervisor received KeyboardInterrupt, exit loop
            time.sleep(1)
            log("Restarting backend in 1s...")
            time.sleep(1)
    except KeyboardInterrupt:
        log("Supervisor received KeyboardInterrupt, exiting and not restarting backend")


if __name__ == "__main__":
    main()
