@echo off
cd /d %~dp0\..
if not exist results mkdir results
python scripts\mc_test_runner.py --symbol TEST --mc-iter 1 > results\test_mc_bg_stdout.log 2> results\test_mc_bg_stderr.log
exit /b 0
