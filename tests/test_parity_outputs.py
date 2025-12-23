import os
from scripts import output_config


def test_parity_dir_exists():
    p = output_config.parity_dir()
    assert p and os.path.isdir(p), f"parity_dir() missing or not a directory: {p}"


def test_parity_report_locations():
    p = os.path.normpath(os.path.abspath(output_config.parity_dir()))
    found = []
    for root, _dirs, files in os.walk('.'):
        for f in files:
            if f == 'parity_report.json':
                found.append(os.path.normpath(os.path.join(root, f)))
    assert found, 'No parity_report.json files found in workspace'
    # all found files must be under parity_dir() or parity_dir()/legacy
    allowed_prefix = p
    allowed_legacy = os.path.join(p, 'legacy')
    for fn in found:
        fn_abs = os.path.normpath(os.path.abspath(fn))
        if not (fn_abs.startswith(allowed_prefix) or fn_abs.startswith(os.path.normpath(allowed_legacy))):
            raise AssertionError(f'parity_report.json found outside allowed parity dir: {fn_abs}')
