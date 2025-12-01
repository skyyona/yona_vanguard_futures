# Rename Scan Report

Target: change project folder name to `yona_vanguard_futures`

Scanned items related to the original folder name `YONA Vanguard Futures(new)`:

- Executable scripts that hardcode absolute paths (need fixing):
  - `run_backend.bat` (contains `cd /d "C:\Users\User\new\YONA Vanguard Futures(new)\"` and an absolute python path). This is a real execution script — patching recommended.

- venv internal activation scripts (DO NOT automatically edit):
  - `.venv_backtest\Scripts\activate.bat` (contains VIRTUAL_ENV with absolute path)
  - `.venv_new\Scripts\activate.bat`
  - `Vanguard\Scripts\activate.bat` (backup/old venv)

  These files are part of virtual environments and contain absolute paths that will become invalid if the folder is renamed. Best practice: recreate venvs after renaming rather than editing these activation scripts manually.

- Docs and markdown files with absolute paths or project name (safe to leave but will not match new name): many `.md` files contain the old name; those do not affect runtime but can be updated for consistency.

- Other scripts:
  - `system_manager.bat` — already patched to be more robust (uses `launch_backend.cmd`), but still relies on relative `%~dp0` and the presence of `launch_backend.cmd`.
  - `backtesting_backend\run_uvicorn_monitor.ps1` — uses `$PSScriptRoot` and candidates for venvs; if it selects `python` (system) instead of the intended venv python, that can cause mismatch. It is safe but logs show it sometimes picked `python`.

Recommendations:

1. Patch execution scripts to use relative paths and `%~dp0` (or `$PSScriptRoot` in PowerShell) rather than absolute paths. I will patch `run_backend.bat` to use `%~dp0` and detect the venv python.

2. Do NOT edit virtualenv activation files directly. After renaming the folder, recreate or re-run `python -m venv` to regenerate activation scripts.

3. After renaming folder, recreate virtual environments and reinstall dependencies using pinned requirements (or use the `requirements.lock` if deploying on same platform).

4. Optionally update docs and README to reflect new folder name.

Next steps performed:
- I will patch `run_backend.bat` to be folder-name-safe and write the change into the repo now.
- After patching, I will provide explicit, copy-paste CMD commands to rename the directory and recreate virtual environments — but I will not rename the working directory automatically until you confirm.


