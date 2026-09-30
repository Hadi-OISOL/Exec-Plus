"""Use case: Runs the mandatory pre-production evidence check.

What it does: Lists unresolved gates and exits unsuccessfully until reviewed evidence is supplied.
"""

import argparse
from pathlib import Path

from execplus.infrastructure.release_gate import REQUIRED_GATES, pending_gates


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        default=str(Path(__file__).resolve().parents[1] / "docs" / "production-readiness.json"),
    )
    args = parser.parse_args()
    pending = pending_gates(args.manifest)
    for key in pending:
        print(f"BLOCKED {key}: {REQUIRED_GATES[key]}")
    if pending:
        parser.exit(1, "Production is blocked. Demo evidence does not clear these gates.\n")
    print("All production evidence checks passed; deployment review is still required.")


if __name__ == "__main__":
    main()
