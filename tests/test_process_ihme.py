import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]


def test_ihme_processor_selftest():
    r = subprocess.run([sys.executable, "scripts/process_ihme_daly.py", "--selftest"], cwd=R, capture_output=True, text=True)
    assert r.returncode == 0 and "selftest ok" in r.stdout, r.stdout + r.stderr
