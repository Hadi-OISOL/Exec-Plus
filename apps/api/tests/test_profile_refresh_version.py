"""Use case: Keeps refresh snapshots on the source's historical profiling version.

What it does: Prevents a refresh from silently upgrading or downgrading interpretation.
"""

from uuid import UUID

import pytest
from sqlalchemy import update

from execplus.infrastructure.persistence import schema as s
from test_refresh import setup, stage


@pytest.mark.parametrize("algorithm", ["profile-v1", "profile-v2"])
def test_refresh_candidate_preserves_profile_algorithm(integration, algorithm):
    env = integration
    owner, _, wid, did, _, path, feed = setup(env)
    rid = UUID(feed["source"]["revision_id"])
    with env.runtime.analytics.uow() as repo:
        source = repo.revision(UUID(wid), UUID(did), UUID(feed["source"]["upload_id"]), rid)
    metadata = {**source.profile, "algorithm": algorithm}
    with env.engine.begin() as connection:
        connection.execute(
            update(s.revisions)
            .where(s.revisions.c.id == rid)
            .values(algorithm=algorithm, profile=metadata)
        )
    candidate = stage(env, owner, path).json()
    assert candidate["status"] == "queued", candidate
    uid = candidate["details"]["output_upload_id"]
    result = env.client.get(path + f"/uploads/{uid}/profile", headers=owner)
    assert result.status_code == 200, result.text
    assert result.json()["algorithm"] == algorithm
    assert result.json()["profile"]["algorithm"] == algorithm
