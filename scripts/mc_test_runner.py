#!/usr/bin/env python3
"""Tiny test runner used by the CI smoke test for `run_mc_background.sh`.

This script prints a few lines to stdout/stderr and sleeps briefly, then exits.
"""
import sys
import time

def main():
    print("MC_TEST_RUNNER: start")
    print("argv:", sys.argv)
    print("env PYTHONPATH sample (if set):", end=' ')
    import os
    print(os.environ.get('PYTHONPATH', '<unset>'))
    # simulate some work
    print("MC_TEST_RUNNER: writing to stderr now", file=sys.stderr)
    time.sleep(1)
    print("MC_TEST_RUNNER: done")

if __name__ == '__main__':
    main()
