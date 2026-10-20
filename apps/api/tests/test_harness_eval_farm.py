"""Use case: Evaluates the conversation harness on realistic farm-data questions.

What it does: Replays each fixture question through the real thread API with a scripted
planner reply, then checks the delivered route, executed operation and presentation.
"""

import json
import random
from pathlib import Path

import pytest

from execplus.application.contracts import ModelResponse
from execplus.application.services.document_answers import DocumentAnswerService
from execplus.application.services.intent_router import IntentRouterService
from execplus.application.services.threads import ThreadService
from execplus.infrastructure.models.disabled import DisabledLanguageModel
from execplus.presentation.routes.analytics import get_intent_router_service
from execplus.presentation.routes.threads import get_thread_service
from test_context_reuse import saved
from test_dataset_guidance import ask
from test_workspace_integration import dataset, identity, upload, workspace

CASES = json.loads((Path(__file__).parent / "fixtures" / "harness_eval_farm.json").read_text())[
    "cases"
]
BY_ID = {case["id"]: case for case in CASES}
CATEGORIES = {
    "Soil_Type": ("Sandy", "Silt", "Clay", "Loamy"),
    "Crop_Type": ("Cotton", "Sugarcane", "Maize", "Rice", "Potato", "Wheat"),
    "Crop_Growth_Stage": ("Sowing", "Flowering", "Harvest", "Vegetative"),
    "Season": ("Rabi", "Kharif", "Zaid"),
    "Irrigation_Type": ("Canal", "Sprinkler", "Rainfed", "Drip"),
    "Water_Source": ("Rainwater", "Groundwater", "River", "Reservoir"),
    "Mulching_Used": ("Yes", "No"),
    "Region": ("South", "East", "West", "North", "Central"),
}
MEASURES = {
    "Soil_pH": (4.5, 8.5),
    "Soil_Moisture": (8, 60),
    "Organic_Carbon": (0.3, 1.6),
    "Electrical_Conductivity": (0.1, 3.5),
    "Temperature_C": (12, 42),
    "Humidity": (30, 95),
    "Rainfall_mm": (300, 2500),
    "Sunlight_Hours": (4, 11),
    "Wind_Speed_kmh": (1, 20),
    "Field_Area_hectare": (0.5, 15),
    "Previous_Irrigation_mm": (5, 120),
}
HEADER = (
    "id,Soil_Type,Soil_pH,Soil_Moisture,Organic_Carbon,Electrical_Conductivity,Temperature_C,"
    "Humidity,Rainfall_mm,Sunlight_Hours,Wind_Speed_kmh,Crop_Type,Crop_Growth_Stage,Season,"
    "Irrigation_Type,Water_Source,Field_Area_hectare,Mulching_Used,Previous_Irrigation_mm,Region"
)


def farm_csv() -> bytes:
    rng = random.Random(630000)
    lines = [HEADER]
    for index in range(100):
        row = {"id": str(630000 + index)}
        row.update({name: rng.choice(values) for name, values in CATEGORIES.items()})
        row.update({name: f"{rng.uniform(*bounds):.2f}" for name, bounds in MEASURES.items()})
        lines.append(",".join(row[name] for name in HEADER.split(",")))
    return ("\n".join(lines) + "\n").encode()


class PlannerByQuestion:
    def __init__(self, replies):
        self.replies = replies
        self.planner_prompts = []

    async def complete(self, request):
        system, user = request.messages[0].content, request.messages[-1].content
        if not system.startswith("You help someone explore one dataset."):
            return ModelResponse("{}", "test-model", "scripted")
        self.planner_prompts.append(user)
        question = user.rsplit("Question: ", 1)[-1]
        return ModelResponse(json.dumps(self.replies.get(question)), "test-model", "scripted")


def harness(env, model):
    owner, _ = identity(env, "farm-eval@example.test")
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    result = upload(env, owner, wid, did, farm_csv(), "farm.csv", "text/csv")
    assert result.status_code == 201, result.text
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{result.json()['id']}"
    saved(env, owner, root)
    router = IntentRouterService(
        model,
        env.runtime.analytics,
        documents=DocumentAnswerService(env.runtime.knowledge, model),
        interpretation_enabled=True,
        patterns=env.runtime.intent_router.patterns,
        context_enabled=True,
        orchestration_enabled=True,
    )
    threads = ThreadService(env.runtime.threads.uow, router)
    env.client.app.dependency_overrides[get_intent_router_service] = lambda: router
    env.client.app.dependency_overrides[get_thread_service] = lambda: threads
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    return owner, f"/workspaces/{wid}/threads/{tid}"


def observe(response) -> dict:
    turn, answer = response["turn"], response["answer"] or {}
    if turn["status"] != "complete":
        return {"outcome": "failed:" + str(turn["message"])}
    if turn["kind"] in {"ambiguous", "unsupported"}:
        return {"outcome": turn["kind"], "message": turn["message"]}
    if answer.get("kind") == "mixed" and answer.get("data"):
        answer = answer["data"]
    if answer.get("kind") == "overview":
        focus = answer["guidance"]["focus"]
        return {"outcome": "conversation" if focus == "conversation" else "guide"}
    if answer.get("kind") == "patterns":
        return {"outcome": "patterns"}
    lineage = answer.get("lineage") or {}
    presentation = answer.get("presentation") or {}
    return {
        "outcome": "answer",
        "aggregation": lineage.get("aggregation"),
        "metric": lineage.get("metric"),
        "group_by": list(lineage.get("grouping", [])),
        "filters": len(lineage.get("filters", [])),
        "rows": len(answer["rows"]) if "rows" in answer else None,
        "chart": (presentation.get("chart") or {}).get("type"),
        "shares": bool(presentation.get("share_of_total")),
        "follow_ups": presentation.get("follow_ups", []),
    }


def mismatches(expect: dict, seen: dict, prompts: list[str]) -> list[str]:
    problems = []
    outcome = expect["outcome"]
    allowed = {"guide", "unsupported"} if outcome == "guide_or_unsupported" else {outcome}
    if seen["outcome"] not in allowed:
        return [f"outcome {seen}"]
    for key in ("aggregation", "metric", "group_by", "filters", "rows", "chart", "shares"):
        if key in expect and seen.get(key) != expect[key]:
            problems.append(f"{key}: expected {expect[key]!r}, got {seen.get(key)!r}")
    if outcome == "answer" and not 2 <= len(seen["follow_ups"]) <= 3:
        problems.append(f"follow_ups: {seen['follow_ups']!r}")
    for text in expect.get("prompt_contains", ()):
        if not prompts or text not in prompts[-1]:
            problems.append(f"planner prompt lacks {text!r}")
    return problems


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_farm_question_reaches_the_expected_governed_outcome(integration, case):
    sequence = [BY_ID[case["after"]], case] if case.get("after") else [case]
    model = PlannerByQuestion({item["question"]: item["plan"] for item in sequence})
    owner, path = harness(integration, model)
    for item in sequence:
        response = ask(integration, owner, path, item["question"])
    seen = observe(response)
    problems = mismatches(case["expect"], seen, model.planner_prompts)
    assert not problems, (problems, seen)


@pytest.mark.parametrize(
    "case",
    [case for case in CASES if case["expect"].get("offline")],
    ids=[case["id"] for case in CASES if case["expect"].get("offline")],
)
def test_offered_question_templates_answer_without_a_language_model(integration, case):
    owner, path = harness(integration, DisabledLanguageModel())
    response = ask(integration, owner, path, case["question"])
    seen = observe(response)
    expect = case["expect"].get("offline_expect", case["expect"])
    problems = mismatches({**expect, "prompt_contains": ()}, seen, [])
    if expect.get("choices_vary"):
        choices = response["turn"]["clarification"]["choices"]
        assert len({choice.split()[-1] for choice in choices}) >= 3, choices
        assert any("Rainfall_mm" in choice for choice in choices), choices
    assert not problems, (problems, seen)
