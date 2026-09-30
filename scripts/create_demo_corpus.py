"""Use case: Creates fictional documents and known-answer questions for Phase 3 demos.

What it does: Reproducibly writes an ignored local corpus without overwriting edited files.
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

VERSION = "demo-corpus-v1"
DEFAULT_DIRECTORY = Path(__file__).resolve().parents[1] / "data" / "phase3-demo-v1"

DOCUMENTS = {
    "refunds": (
        "Refund policy",
        "Refund requests require the original receipt and the order reference.\n"
        "The customer support lead approves standard refunds.\n"
        "Damaged deliveries must include a photo of the packaging.\n"
        "Approved refunds return through the original payment method.",
    ),
    "expenses": (
        "Expense reimbursement",
        "Expense claims require a receipt, a business purpose, and the project code.\n"
        "The line manager approves expense claims before finance reviews them.\n"
        "Missing receipts require a signed exception from the finance lead.\n"
        "Personal purchases are excluded from reimbursement.",
    ),
    "leave": (
        "Leave requests",
        "Annual leave requests are submitted through the people operations portal.\n"
        "The line manager approves annual leave after checking team coverage.\n"
        "Employees report unexpected sickness to their manager and people operations.\n"
        "Leave balances are available in the people operations portal.",
    ),
    "inventory": (
        "Inventory operations",
        "Warehouse staff record damaged stock in the inventory exception register.\n"
        "The warehouse supervisor signs off inventory count differences.\n"
        "Quarantined stock must not be included in available-to-sell stock.\n"
        "Reorder requests go to the purchasing coordinator.",
    ),
    "access": (
        "Workspace access",
        "Workspace owners and admins can invite teammates.\n"
        "Private documents are visible only to their owner.\n"
        "Shared documents require current membership in the same workspace.\n"
        "Removing a member revokes their access to workspace source passages.",
    ),
    "reports": (
        "Report subscriptions",
        "Each employee subscribes their own account to a saved analysis report.\n"
        "A report contains the saved analysis from its original data revision.\n"
        "Report access is checked again immediately before delivery.\n"
        "Employees unsubscribe through the Saved work section in their workspace.",
    ),
}

QUESTION_ROWS = [
    (
        "What evidence does a refund request require?",
        "refunds",
        "Refund requests require the original receipt and the order reference.",
    ),
    (
        "Who approves standard refunds?",
        "refunds",
        "The customer support lead approves standard refunds.",
    ),
    (
        "What evidence is needed for a damaged delivery?",
        "refunds",
        "Damaged deliveries must include a photo of the packaging.",
    ),
    (
        "What is the payment method for approved refunds?",
        "refunds",
        "Approved refunds return through the original payment method.",
    ),
    (
        "What must an expense claim include?",
        "expenses",
        "Expense claims require a receipt, a business purpose, and the project code.",
    ),
    (
        "Who approves expense claims before finance?",
        "expenses",
        "The line manager approves expense claims before finance reviews them.",
    ),
    (
        "What happens when an expense receipt is missing?",
        "expenses",
        "Missing receipts require a signed exception from the finance lead.",
    ),
    (
        "Where are annual leave requests submitted?",
        "leave",
        "Annual leave requests are submitted through the people operations portal.",
    ),
    (
        "Who approves annual leave?",
        "leave",
        "The line manager approves annual leave after checking team coverage.",
    ),
    (
        "Where can employees find their leave balances?",
        "leave",
        "Leave balances are available in the people operations portal.",
    ),
    (
        "Where is damaged stock recorded?",
        "inventory",
        "Warehouse staff record damaged stock in the inventory exception register.",
    ),
    (
        "Who signs off inventory count differences?",
        "inventory",
        "The warehouse supervisor signs off inventory count differences.",
    ),
    (
        "Is quarantined stock available to sell?",
        "inventory",
        "Quarantined stock must not be included in available-to-sell stock.",
    ),
    (
        "Who can invite teammates to a workspace?",
        "access",
        "Workspace owners and admins can invite teammates.",
    ),
    (
        "Who can read private documents?",
        "access",
        "Private documents are visible only to their owner.",
    ),
    (
        "Where do employees unsubscribe from reports?",
        "reports",
        "Employees unsubscribe through the Saved work section in their workspace.",
    ),
]


def artifacts() -> dict[str, str]:
    files: dict[str, str] = {}
    documents = []
    for key, (title, body) in DOCUMENTS.items():
        name = key + ".md"
        text = (
            "> **File use case:** Fictional Phase 3 evaluation document.\n"
            "> **What it does:** Supplies demo-only source passages, not company policy.\n\n"
            f"# DEMO ONLY — {title}\n\n"
            "Organization: fictional Cedar Demo Company. No customer data.\n\n" + body + "\n"
        )
        files[name] = text
        documents.append(
            {"id": key, "path": name, "sha256": hashlib.sha256(text.encode()).hexdigest()}
        )
    questions: list[dict[str, Any]] = [
        {
            "id": f"q{index:02}",
            "query": query,
            "relevant_ids": [document],
            "expected_kind": "supported",
            "expected_answer": answer,
        }
        for index, (query, document, answer) in enumerate(QUESTION_ROWS, start=1)
    ]
    questions.extend(
        [
            {
                "id": "q17",
                "query": "What is the company's payroll bank account?",
                "relevant_ids": [],
                "expected_kind": "unsupported",
                "expected_answer": "The demo documents do not provide a payroll bank account.",
            },
            {
                "id": "q18",
                "query": "What will next year's revenue be?",
                "relevant_ids": [],
                "expected_kind": "unsupported",
                "expected_answer": "The demo documents cannot forecast revenue.",
            },
            {
                "id": "q19",
                "query": "Who approves requests?",
                "relevant_ids": ["refunds", "expenses", "leave"],
                "expected_kind": "ambiguous",
                "expected_answer": (
                    "Clarify whether this means refunds, expense claims, or annual leave."
                ),
            },
            {
                "id": "q20",
                "query": "Which portal should I use?",
                "relevant_ids": [],
                "expected_kind": "ambiguous",
                "expected_answer": "Clarify the task or process before choosing a portal.",
            },
        ]
    )
    manifest = {
        "file_use_case": "Fictional evaluation manifest",
        "responsibility": "Records source hashes and known answers",
        "version": VERSION,
        "synthetic": True,
        "production_evidence": False,
        "documents": documents,
        "questions": questions,
    }
    files["evaluation.json"] = json.dumps(manifest, indent=2) + "\n"
    lines = [
        "> **File use case:** Human-readable fictional evaluation questions.",
        "> **What it does:** Lists expected answers and citations for manual demo review.",
        "",
        "# Demo questions and expected answers",
        "",
    ]
    for question in questions:
        lines.extend(
            [
                f"## {question['id']}: {question['query']}",
                "",
                f"Expected: **{question['expected_kind']}**",
                "",
                str(question["expected_answer"]),
                "",
                "Sources: " + (", ".join(question["relevant_ids"]) or "No supporting passage"),
                "",
            ]
        )
    files["questions.md"] = "\n".join(lines)

    files["README.md"] = (
        "> **File use case:** Explains the generated fictional demo corpus.\n"
        "> **What it does:** Labels test material and gives local evaluation instructions.\n\n"
        "# Fictional demo documents\n\n"
        "Six policy documents and twenty known-answer questions. "
        "Demo only; not customer evidence.\n"
        "Upload the six policy Markdown files in the workspace Reference documents panel.\n"
        "Keep evaluation.json, questions.md and this README out of the uploaded collection.\n"
        "From the repository root run `make evaluate-demo` for offline retrieval checks.\n"
        "The generator refuses to overwrite edited files. Use a new folder for another version.\n"
    )
    return files


def write_demo(directory: Path) -> Path:
    files = artifacts()
    for name, text in files.items():
        path = directory / name
        if path.exists() and path.read_text() != text:
            raise FileExistsError(f"Refusing to overwrite an edited demo file: {path}")
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        path = directory / name
        if not path.exists():
            path.write_text(text, encoding="utf-8")
    return directory / "evaluation.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_DIRECTORY)
    args = parser.parse_args()
    print(write_demo(args.output).resolve())


if __name__ == "__main__":
    main()
