#!/usr/bin/env python3
"""Canonical cleanup tool

Usage:
  tools/canonical_cleanup.py --index <index_path> [--dry-run] [--execute] [--archive-dir <dir>] [--days <json>]

This tool reads a SHA index (index.sha.<ts>.json) and produces a dry-run cleanup plan
or executes a safe move-to-archive operation. It never permanently deletes files unless
--execute --purge is supplied (not recommended without review).
"""
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
import shutil
import hashlib
import os


def load_index(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def rank_path(p: str, pref_order):
    first = p.split('/')[0]
    try:
        return pref_order.index(first)
    except ValueError:
        return len(pref_order)


def sha256_of(path: Path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def build_dryrun(index_path: Path, days_thresholds=None, name_patterns_keep=None):
    if days_thresholds is None:
        days_thresholds = {'backtest_results_mtf': 365, 'analysis': 180, 'ui_exports': 90, 'logs': 30, 'other': 30}
    if name_patterns_keep is None:
        name_patterns_keep = []

    idx = load_index(index_path)
    now = datetime.now(timezone.utc)
    canonical_root = index_path.parent

    pref_order = ['backtest_results_mtf', 'analysis', 'ui_exports', 'logs', 'other', 'root']

    summary = {'total_shas': 0, 'groups_multi': 0, 'groups_single': 0, 'move_candidates': 0}
    groups = {}
    samples = []

    for sha, meta in idx.items():
        # meta expected to contain 'paths' (list) and optionally 'keep'
        paths = meta.get('paths') or meta.get('paths', [])
        if not paths:
            continue
        summary['total_shas'] += 1
        if len(paths) > 1:
            summary['groups_multi'] += 1
            # decide keep
            sorted_paths = sorted(paths, key=lambda p: (rank_path(p, pref_order), p.lower()))
            keep = meta.get('keep') or sorted_paths[0]
            moved = [p for p in paths if p != keep]
            groups[sha] = {'keep': keep, 'moved': moved, 'reason': 'duplicate_sha'}
            summary['move_candidates'] += len(moved)
        else:
            summary['groups_single'] += 1
            p = paths[0]
            # determine category
            cat = p.split('/')[0] if '/' in p else 'other'
            days = days_thresholds.get(cat, days_thresholds.get('other', 30))
            # check mtime
            fpath = canonical_root / p
            if not fpath.exists():
                groups[sha] = {'keep': p, 'moved': [], 'reason': 'missing_file'}
                continue
            mtime = datetime.fromtimestamp(fpath.stat().st_mtime, timezone.utc)
            age_days = (now - mtime).days
            # name pattern exceptions
            if any(p.lower().find(k.lower()) >= 0 for k in name_patterns_keep):
                groups[sha] = {'keep': p, 'moved': [], 'reason': 'name_pattern_keep'}
                continue
            if age_days >= days:
                groups[sha] = {'keep': p, 'moved': [p], 'reason': 'age_threshold_exceeded', 'age_days': age_days, 'threshold_days': days}
                summary['move_candidates'] += 1

        if len(samples) < 50 and sha in groups:
            samples.append({ 'sha': sha, **groups[sha] })

    out = {'ts': datetime.now().strftime('%Y%m%d_%H%M%S'), 'index': str(index_path.name), 'summary': summary, 'groups_counted': len(groups), 'samples': samples}
    # include full groups for potential review but keep concise
    out['groups'] = groups
    return out


def execute_move(dryrun, canonical_root: Path, archive_dir: Path):
    moved = []
    errors = []
    archive_dir.mkdir(parents=True, exist_ok=True)
    for sha, g in dryrun.get('groups', {}).items():
        for m in g.get('moved', []):
            src = canonical_root / m
            if not src.exists():
                errors.append({'sha': sha, 'path': str(src), 'err': 'not_found'})
                continue
            rel = Path(m)
            dest = archive_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(src), str(dest))
                # verify sha
                calc = sha256_of(dest)
                moved.append({'sha': sha, 'from': str(src), 'to': str(dest), 'calc_sha': calc})
            except Exception as e:
                errors.append({'sha': sha, 'path': str(src), 'err': str(e)})
    return {'moved': moved, 'errors': errors}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--index', required=True)
    p.add_argument('--dry-run', action='store_true', default=False)
    p.add_argument('--execute', action='store_true', default=False)
    p.add_argument('--archive-dir')
    p.add_argument('--days')
    p.add_argument('--keep-name-pattern', action='append')
    args = p.parse_args()

    index_path = Path(args.index)
    if not index_path.exists():
        raise SystemExit(f'Index not found: {index_path}')

    canonical_root = index_path.parent
    days_thresholds = None
    if args.days:
        try:
            days_thresholds = json.loads(args.days)
        except Exception:
            raise SystemExit('Invalid --days JSON')

    dryrun = build_dryrun(index_path, days_thresholds=days_thresholds, name_patterns_keep=args.keep_name_pattern)
    ts = dryrun['ts']
    out_path = canonical_root / f'cleanup_dryrun_{ts}.json'
    out_path.write_text(json.dumps(dryrun, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Dry-run written to', out_path)

    if args.execute:
        archive_dir = Path(args.archive_dir) if args.archive_dir else canonical_root / f'cleanup_archive_{ts}'
        # make a backup zip before moving
        backup_zip = canonical_root.parent / f'canonical_backup_{ts}.zip'
        shutil.make_archive(str(backup_zip.with_suffix('')), 'zip', str(canonical_root))
        print('Backup created at', backup_zip)
        res = execute_move(dryrun, canonical_root, archive_dir)
        moved_path = canonical_root / f'cleanup_moved_{ts}.json'
        with moved_path.open('w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print('Execute move complete, log:', moved_path)


if __name__ == '__main__':
    main()
