#!/usr/bin/env python3
"""Promote sanitized CSV files from a copy tree into the live `results` directory.

For each file matching `*_sanitized.csv` under the source tree, this script
will copy it over the corresponding target path under `results`, removing
the `_sanitized` suffix from the filename.

Example:
  python scripts/promote_sanitized.py --source-dir vss_tmp\20251201T204257Z\results_copy --results-dir results --log vss_tmp\20251201T204257Z\promote_out.txt
"""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
import sys
from datetime import datetime


def promote(source_dir: Path, results_dir: Path, log_file: Path) -> int:
    source_dir = source_dir.resolve()
    results_dir = results_dir.resolve()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    promoted = []
    skipped = []

    for p in source_dir.rglob('*_sanitized.csv'):
        try:
            rel = p.relative_to(source_dir)
        except Exception:
            # skip unexpected
            skipped.append((str(p), 'not under source'))
            continue
        target_name = rel.name.replace('_sanitized', '')
        target_rel = rel.with_name(target_name)
        target_path = results_dir / target_rel
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(p, target_path)
            promoted.append((str(p), str(target_path)))
        except Exception as e:
            skipped.append((str(p), f'copy-failed: {e}'))

    # write log
    with log_file.open('w', encoding='utf-8') as lf:
        lf.write(f"Promote run: {datetime.utcnow().isoformat()}\n")
        lf.write(f"Source: {source_dir}\n")
        lf.write(f"Results: {results_dir}\n")
        lf.write(f"Promoted count: {len(promoted)}\n")
        for s, t in promoted[:1000]:
            lf.write(f"PROMOTED: {s} -> {t}\n")
        if skipped:
            lf.write(f"Skipped count: {len(skipped)}\n")
            for s, reason in skipped[:1000]:
                lf.write(f"SKIPPED: {s} ({reason})\n")

    print(f"Promoted {len(promoted)} files; skipped {len(skipped)} entries. Log: {log_file}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--source-dir', required=True)
    p.add_argument('--results-dir', required=True)
    p.add_argument('--log', required=True)
    args = p.parse_args()
    return promote(Path(args.source_dir), Path(args.results_dir), Path(args.log))


if __name__ == '__main__':
    raise SystemExit(main())
