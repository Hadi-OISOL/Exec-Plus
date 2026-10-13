"""Use case: Creates small fictional files for anomaly and allocation walkthroughs.

What it does: Reproduces versioned demo CSVs and refuses to overwrite edited examples.
"""

from pathlib import Path

FILES = {
    "unusual-values.csv": "record_id,department,amount\n"
    + "".join(f"R{i},Sales,10.00\n" for i in range(1, 9))
    + "R9,Sales,100.00\n",
    "allocation.csv": "action,unit_cost,unit_benefit\n"
    "Campaign A,2.50,5.00\nCampaign B,4.00,7.50\nCampaign C,1.50,2.00\n",
}


def create(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, content in FILES.items():
        path = root / name
        if path.exists() and path.read_text() != content:
            raise FileExistsError("Preserve edited examples; use a different demo version.")
    for name, content in FILES.items():
        (root / name).write_text(content)


if __name__ == "__main__":
    destination = Path(__file__).resolve().parents[1] / "data" / "decision-demo-v1"
    create(destination)
    print(f"Fictional decision examples available in {destination}")
