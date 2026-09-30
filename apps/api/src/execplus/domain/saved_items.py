"""Use case: Defines a named, reusable saved question, prompt, or dashboard configuration.

What it does: Scopes each saved item to a workspace, dataset upload, and owner, with
an explicit flag for whether it is shared with the rest of the workspace.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID


class SavedItemKind(str, Enum):
    QUESTION = "question"
    PROMPT = "prompt"
    DASHBOARD = "dashboard"
    ANALYSIS = "analysis"


@dataclass(frozen=True, slots=True)
class SavedItem:
    id: UUID
    workspace_id: UUID
    dataset_id: UUID
    upload_id: UUID
    owner_id: UUID
    kind: str
    name: str
    description: str
    payload: dict[str, Any]
    shared: bool
    created_at: datetime
    updated_at: datetime
