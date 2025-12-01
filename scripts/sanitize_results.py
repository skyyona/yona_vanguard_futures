#!/usr/bin/env python3
"""
Sanitize result CSV files by removing sensitive columns (`initial_balance`, `leverage`).

Instrumented: when an in-place write fails with a Windows sharing violation
(WinError 32) this script will try to run `scripts/tools/handle.exe` (if present)
and append its output to `results/handle_capture_<timestamp>.log` so orchestrators
can capture the PID/process that held the handle at the failure moment.

Usage:
  python scripts/sanitize_results.py [--results-dir PATH] [--inplace] [--backup-dir PATH] [--dry-run]
"""
from __future__ import annotations
import argparse
import csv
import subprocess
import os
import shutil
import json
import time
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

SENSITIVE = {"initial_balance", "leverage"}


def find_csv_files(results_dir: Path):
    for p in results_dir.rglob('*.csv'):
        yield p


def has_sensitive_header(path: Path) -> bool:
    try:
        with path.open('r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, [])
            header_set = set(h.strip() for h in header)
            return not SENSITIVE.isdisjoint(header_set)
    except Exception:
        return False


def sanitize_file_copy(orig: Path, dry_run: bool = False) -> Optional[Path]:
    try:
        with orig.open('r', encoding='utf-8', newline='') as inf:
            reader = csv.DictReader(inf)
            headers = [h for h in (reader.fieldnames or []) if h is not None]
            new_headers = [h for h in headers if h not in SENSITIVE]
            if headers == new_headers:
                return None
            out_path = orig.with_name(orig.stem + '_sanitized' + orig.suffix)
            if dry_run:
                return out_path
            with out_path.open('w', encoding='utf-8', newline='') as outf:
                writer = csv.DictWriter(outf, fieldnames=new_headers)
                writer.writeheader()
                for row in reader:
                    out_row = {k: v for k, v in row.items() if k in new_headers}
                    writer.writerow(out_row)
            return out_path
    except Exception as e:
        print(f"Error sanitizing (copy) {orig}: {e}")
        return None


def _write_handle_capture_for_file(orig: Path, note: Optional[str] = None) -> None:
    tools_dir = Path(__file__).parent / 'tools'
    handle_exe = tools_dir / 'handle.exe'
    ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    capture_root = Path.cwd() / 'results'
    capture_root.mkdir(parents=True, exist_ok=True)
    # Implement rate limiting and consolidate captures to avoid log explosion.
    capture_index = capture_root / 'handle_capture_index.json'
    daily_date = datetime.utcnow().strftime('%Y%m%d')
    cooldown_seconds = 60 * 60  # 1 hour cooldown per-file to avoid repeats
    max_daily_failures = 10

    # load or initialize index
    index = {'date': daily_date, 'files': {}, 'daily_failures': 0}
    try:
        if capture_index.exists():
            with capture_index.open('r', encoding='utf-8') as ix:
                raw = json.load(ix)
                # reset if day changed
                if raw.get('date') == daily_date:
                    index = raw
    except Exception:
        # ignore parse errors and proceed with fresh index
        index = {'date': daily_date, 'files': {}, 'daily_failures': 0}

    capture_key = os.path.relpath(str(orig), str(capture_root.resolve()))
    now_ts = int(time.time())
    last = index.get('files', {}).get(capture_key, 0)
    if last and (now_ts - int(last) < cooldown_seconds):
        print(f"Skipping handle capture for {orig} due to cooldown ({int(now_ts - int(last))}s elapsed)")
        return

    # run handle attempts
    capture_root_resolved = str(capture_root.resolve())
    local_handle = Path(capture_root_resolved) / 'handle.exe'
    try:
        if handle_exe.exists() and not local_handle.exists():
            try:
                shutil.copy2(str(handle_exe), str(local_handle))
            except Exception as ce:
                print(f"Failed to copy handle.exe to results/: {ce}")

        rel_target = os.path.relpath(str(orig), capture_root_resolved)
        cmd = [str(local_handle) if local_handle.exists() else str(handle_exe), '-accepteula', '-nobanner', rel_target]
        out = ''
        err = ''
        timeout_per_attempt = 40
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=capture_root_resolved)
                o, e = proc.communicate(timeout=timeout_per_attempt)
                out += (o or '')
                err += (e or '')
                # heuristic: look for pid-like tokens
                if re.search(r"\bpid\b[:\s]*\d+", out, flags=re.IGNORECASE) or re.search(r"\bprocess\b", out, flags=re.IGNORECASE):
                    break
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except Exception:
                    pass
                out += f"\n# attempt {attempt} timed out after {timeout_per_attempt}s\n"
            except Exception as he2:
                err += f"\n# handle.exe attempt {attempt} failed: {he2}\n"
                break

        # decide whether to write a full capture
        pid_found = bool(re.search(r"\bpid\b[:\s]*\d+", out, flags=re.IGNORECASE) or re.search(r"\bprocess\b", out, flags=re.IGNORECASE))
        if pid_found:
            capture_path = capture_root / f'handle_capture_daily_{daily_date}.log'
            try:
                with capture_path.open('a', encoding='utf-8') as cf:
                    cf.write(f"# Captured: {datetime.utcnow().isoformat()}\n")
                    cf.write(f"File: {orig}\n")
                    if note:
                        cf.write(f"Note: {note}\n")
                    cf.write(out or '')
                    if err:
                        cf.write('\n# handle.exe stderr:\n')
                        cf.write(err)
                print(f"Wrote handle capture to {capture_path}")
            except Exception as e:
                print(f"Failed to write handle capture for {orig}: {e}")
        else:
            # no PID found; record attempt and write a small failure line only up to a daily cap
            index['daily_failures'] = int(index.get('daily_failures', 0)) + 1
            if index['daily_failures'] <= max_daily_failures:
                fail_path = capture_root / f'handle_capture_failures_{daily_date}.log'
                try:
                    with fail_path.open('a', encoding='utf-8') as ff:
                        ff.write(f"# Attempted: {datetime.utcnow().isoformat()} File: {orig} Note: {note or ''}\n")
                        if err:
                            ff.write(f"# err: {err}\n")
                    print(f"Wrote short failure capture to {fail_path}")
                except Exception as e:
                    print(f"Failed to write short failure capture: {e}")
            else:
                print("Daily failure cap reached; not writing more failure captures.")

        # update index last-attempt time for this file to enforce cooldown
        index.setdefault('files', {})[capture_key] = now_ts
        try:
            with capture_index.open('w', encoding='utf-8') as ix:
                json.dump(index, ix)
        except Exception:
            pass
    except Exception as e:
        print(f"Failed running handle capture for {orig}: {e}")


def sanitize_file_inplace(orig: Path, backup_dir: Path, dry_run: bool = False) -> Optional[Path]:
    try:
        with orig.open('r', encoding='utf-8', newline='') as inf:
            reader = csv.DictReader(inf)
            headers = [h for h in (reader.fieldnames or []) if h is not None]
            new_headers = [h for h in headers if h not in SENSITIVE]
            if headers == new_headers:
                return None
            if dry_run:
                return orig
            # make backup
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / orig.relative_to(orig.anchor)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            # move original to backup location
            orig.replace(backup_path)
            # write sanitized file at original path
            with backup_path.open('r', encoding='utf-8', newline='') as inf2:
                reader2 = csv.DictReader(inf2)
                with orig.open('w', encoding='utf-8', newline='') as outf:
                    writer = csv.DictWriter(outf, fieldnames=new_headers)
                    writer.writeheader()
                    for row in reader2:
                        out_row = {k: v for k, v in row.items() if k in new_headers}
                        writer.writerow(out_row)
            return orig
    except Exception as e:
        # detect Windows sharing violation
        winerr = getattr(e, 'winerror', None)
        is_sharing_violation = (winerr == 32) or ('WinError 32' in str(e))
        print(f"Error sanitizing (inplace) {orig}: {e}")
        if is_sharing_violation:
            _write_handle_capture_for_file(orig, note=str(e))
        return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--results-dir', default='results')
    p.add_argument('--inplace', action='store_true')
    p.add_argument('--backup-dir', default=None)
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        print(f"Results dir not found: {results_dir}")
        return 2

    files = list(find_csv_files(results_dir))
    found: list[Path] = []
    for f in files:
        if has_sensitive_header(f):
            found.append(f)

    print(f"Found {len(found)} CSV files containing sensitive headers.")
    if not found:
        return 0

    processed: list[tuple[str, str]] = []
    timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    backup_dir = Path(args.backup_dir) if args.backup_dir else results_dir.parent / f'results_backup_{timestamp}'

    for f in found:
        if args.inplace:
            out = sanitize_file_inplace(f, backup_dir, dry_run=args.dry_run)
        else:
            out = sanitize_file_copy(f, dry_run=args.dry_run)
        if out is not None:
            processed.append((str(f), str(out)))
            print(f"Sanitized: {f} -> {out}")
        else:
            print(f"No change: {f}")

    # write a small summary
    summary_path = results_dir / f'sanitize_summary_{timestamp}.csv'
    try:
        with summary_path.open('w', encoding='utf-8', newline='') as sf:
            writer = csv.writer(sf)
            writer.writerow(['orig', 'sanitized'])
            for a, b in processed:
                writer.writerow([a, b])
        print(f"Wrote summary to {summary_path}")
    except Exception as e:
        print(f"Failed writing summary: {e}")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())


