#!/usr/bin/env python
"""Quality baseline validation script - run after any code changes."""

import os
import subprocess
import sys
from pathlib import Path


QUALITY_DIR = Path(__file__).resolve().parent
REPO_ROOT = QUALITY_DIR.parent


def run_command(cmd: list[str], name: str) -> bool:
    """Run a command and report status."""
    print(f"\n{'='*60}")
    print(f"[CHECK] {name}")
    print(f"{'='*60}")
    try:
        env = os.environ.copy()
        if "--cov=modules" in cmd:
            env["COVERAGE_FILE"] = str(QUALITY_DIR / ".coverage")

        result = subprocess.run(cmd, cwd=REPO_ROOT, env=env)
        return result.returncode == 0
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False


def main():
    """Run all quality checks."""
    checks = [
        (["ruff", "check", ".", "--select=F,W,E"], "Ruff (unused imports, line length)"),
        ([sys.executable, "-m", "pytest", "-v", "--tb=short"], "Pytest (unit tests)"),
        (
            [sys.executable, "-m", "pytest", "--cov=modules", "--cov-report=term-missing"],
            "Coverage (baseline tracking)",
        ),
    ]

    results = []
    for cmd, name in checks:
        results.append(run_command(cmd, name))

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for (_, name), passed in zip(checks, results):
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {name}")

    all_passed = all(results)
    print(f"\n{'='*60}")
    if all_passed:
        print("[SUCCESS] All quality checks passed!")
        return 0

    print("[ERROR] Some checks failed - fix errors above")
    return 1


if __name__ == "__main__":
    sys.exit(main())
