"""Use case: Prepares eight individual identities and fictional data for private demonstrations.

What it does: Seeds through authorized services and writes sessions only to a private file.
"""

import argparse
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from create_demo_corpus import DOCUMENTS

from execplus.bootstrap import Runtime, build_runtime
from execplus.config import Settings
from execplus.domain.samples import SAMPLES
from execplus.infrastructure.identity import LocalSessionIdentity

WORKSPACE_NAME = "ExecPlus investor demo (fictional)"


async def provision(runtime: Runtime) -> dict[str, Any]:
    identity = runtime.identity
    if not isinstance(identity, LocalSessionIdentity):
        raise ValueError("The private demo requires local session identity")
    accounts = []
    actors = []
    for number in range(1, 9):
        email = f"demo{number}@example.test"
        token = identity.provision(email, f"Demo user {number}")
        accounts.append({"email": email, "token": token})
        actors.append(identity.authenticate(token))
    owner = actors[0]
    service = runtime.service
    workspace = next(
        (item for item in service.list_workspaces(owner) if item.name == WORKSPACE_NAME), None
    )
    if workspace is None:
        workspace = service.create_workspace(owner, WORKSPACE_NAME, 8)
    members = {item.user_id for item in service.list_members(owner, workspace.id)}
    for actor in actors[1:]:
        if actor.id not in members:
            invitation = service.invite(owner, workspace.id, actor.email, "member")
            service.accept_invitation(actor, workspace.id, invitation.id)
    uploads = [
        upload
        for dataset in service.list_datasets(owner, workspace.id)
        for upload in service.list_uploads(owner, workspace.id, dataset.id)
    ]
    for sample in SAMPLES:
        if not any(upload.sample_id == sample["id"] for upload in uploads):
            uploads.append(service.import_sample(owner, workspace.id, str(sample["id"])))
    finance = next(upload for upload in uploads if upload.sample_id == "finance-v1")
    documents = await runtime.knowledge.list_documents(owner, workspace.id, finance.dataset_id)
    names = {item["name"] for item in documents}
    for key, (title, content) in DOCUMENTS.items():
        name = f"{key}.md"
        if name not in names:
            await runtime.knowledge.ingest(
                owner,
                workspace.id,
                finance.dataset_id,
                name,
                f"# Fictional demo: {title}\n\n{content}\n".encode(),
                True,
            )
    return {
        "scope": "private-fictional-demo",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
        "workspace_id": str(workspace.id),
        "dataset_id": str(finance.dataset_id),
        "upload_id": str(finance.id),
        "accounts": accounts,
    }


def save_private(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".new")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w") as output:
            json.dump(value, output, indent=2)
            output.write("\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confirm-fictional-demo", action="store_true", required=True)
    args = parser.parse_args()
    settings = Settings()
    if settings.environment != "local" or settings.object_store_bucket != "execplus-demo":
        parser.exit(2, "This command is restricted to the private execplus-demo environment.\n")
    previous = json.loads(args.output.read_text()) if args.output.exists() else None
    runtime = build_runtime(settings)
    try:
        value = asyncio.run(provision(runtime))
        save_private(args.output, value)
        if previous and previous.get("scope") == "private-fictional-demo":
            for account in previous["accounts"]:
                runtime.identity.revoke(account["token"])
    finally:
        runtime.engine.dispose()
    print("Eight demo sessions saved privately; they expire in eight hours.")


if __name__ == "__main__":
    main()
