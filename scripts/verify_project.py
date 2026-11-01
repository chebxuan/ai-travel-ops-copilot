"""Current website checks in file mode; no external servers or production database."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULES = ["tests.test_travel_api", "tests.test_menu_content", "tests.test_sales_pricing",
           "tests.test_journey_enquiries", "tests.test_frontend_product_content", "tests.test_operations", "tests.test_operations_configuration"]


def main() -> int:
    env = os.environ.copy()
    env.update(API_KEY="local-verification-only", TRAVEL_DATA_SOURCE="files",
               RUN_DATABASE_TESTS="0", PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, "-B", "-m", "unittest", *MODULES], cwd=ROOT, env=env)
    if result.returncode == 0:
        print("Current catalogue, Menu, sales pricing, enquiries and frontend data checks: PASS")
        print("File mode only; database checks are separate and require an isolated test database.")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
