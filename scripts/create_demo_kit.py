"""Use case: Creates a local fictional starter kit for the ExecPlus user.

What it does: Writes versioned CSVs, their guide and checksums while preserving edited files.
"""

import argparse
import json
from hashlib import sha256
from pathlib import Path

from execplus.domain.samples import sample_csv


def create(destination: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    files = {
        "execplus-retail-daily-v1.csv": sample_csv("retail-v1"),
        "execplus-actions-v1.csv": sample_csv("actions-v1"),
        "START-HERE.md": (root / "docs/demo-data-guide.md").read_bytes(),
    }
    manifest = {
        "version": "execplus-demo-kit-v1",
        "synthetic": True,
        "files": {name: sha256(content).hexdigest() for name, content in files.items()},
    }
    files["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        path = destination / name
        if path.exists() and path.read_bytes() != content:
            raise FileExistsError(
                f"Preserve {path}; choose a new destination for changed examples."
            )
    for name, content in files.items():
        (destination / name).write_bytes(content)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the fictional ExecPlus starter kit.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/demo-kit",
    )
    args = parser.parse_args()
    create(args.output)
    print(f"Fictional demo files and instructions are ready in {args.output}")


if __name__ == "__main__":
    main()
