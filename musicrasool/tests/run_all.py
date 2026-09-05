"""
Full-suite runner: executes every test file in order and reports a
single pass/fail. Usage:
    python tests/run_all.py
"""
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)

TESTS = [
    "tests/smoke_test.py",
    "tests/test_handlers.py",
    "tests/test_auth.py",
    "tests/test_layout.py",
    "tests/test_panel_buttons.py",
    "tests/test_stream_lifecycle.py",
    "tests/test_regressions.py",
]

failed = []
for t in TESTS:
    print(f"\n{'=' * 60}\nRUN: {t}\n{'=' * 60}")
    r = subprocess.run([sys.executable, "-u", t], capture_output=True, text=True)
    out = "\n".join(
        line for line in r.stdout.splitlines()
        if "TgCrypto" not in line
    )
    err = "\n".join(
        line for line in r.stderr.splitlines()
        if "TgCrypto" not in line
    )
    print(out)
    if err.strip():
        print(err)
    if r.returncode != 0:
        failed.append(t)

print("\n" + "=" * 60)
if failed:
    print(f"FAILED: {failed}")
    sys.exit(1)
print("ALL TESTS PASSED")
sys.exit(0)
