"""Use case: Checks date-free daily assumptions without inventing time-series evidence.

What it does: Verifies exact arithmetic, bounded inputs, private replay and old-method stability.
"""

from decimal import Decimal
from fractions import Fraction

import pytest

from execplus.domain.ingestion import IngestionError
from execplus.domain.scenarios import DAILY_METHOD, compare_scenarios
from test_scenarios_integration import create
from test_studies import add_member, prepare


def request(change="0.1", days=7):
    return dict(
        metric="amount",
        aggregation="avg",
        assumptions_confirmed=True,
        alternatives=[
            dict(
                name="Assumed daily change",
                operation="daily_change",
                daily_change=change,
                days=days,
            )
        ],
    )


@pytest.mark.parametrize(
    "base,rate,days",
    [
        ("9007199254740993.123456789012345678", "0.000000000000000001", 3650),
        ("0", "-0.1", 1),
        ("10.2", "0.13", 7),
        ("4.9", "-0.7", 7),
    ],
)
def test_daily_paths_match_independent_rational_arithmetic(base, rate, days):
    result = compare_scenarios(request(rate, days), ((Decimal(base), 100, 100),))
    alternative = result["alternatives"][0]
    assert result["method_version"] == DAILY_METHOD
    assert Fraction(alternative["result"]) == Fraction(base) + Fraction(rate) * days
    assert Fraction(alternative["difference"]) == Fraction(rate) * days
    assert 2 <= len(alternative["path"]) <= 5
    assert alternative["path"][0]["day"] == 0
    assert Fraction(alternative["path"][0]["value"]) == Fraction(base)
    assert alternative["path"][-1]["day"] == days
    for point in alternative["path"]:
        assert Fraction(point["value"]) == Fraction(base) + Fraction(rate) * point["day"]
    assert "not rates learned" in " ".join(result["limitations"])


@pytest.mark.parametrize(
    "rate,days",
    [
        ("1", True),
        ("1", "7"),
        ("1", 0),
        ("1", 3651),
        (1, 7),
        ("NaN", 7),
        ("Infinity", 7),
        ("1e37", 100),
    ],
)
def test_daily_invalid_inputs_and_overflow_refuse(rate, days):
    with pytest.raises(IngestionError):
        compare_scenarios(request(rate, days), ((Decimal(100), 10, 10),))


def test_daily_negative_path_warns_and_never_clips_values():
    result = compare_scenarios(request("-3", 4), ((Decimal(10), 10, 10),))
    alternative = result["alternatives"][0]
    assert alternative["result"] == "-2"
    assert alternative["warnings"] and alternative["path"][-1]["value"] == "-2"
    old = request()
    old["alternatives"] = [dict(name="Existing", operation="percent_change", value="10")]
    previous = compare_scenarios(old, ((Decimal(10), 10, 10),))
    assert previous["method_version"] == "aggregate-scenarios-v1"
    assert "path" not in previous["alternatives"][0]


def test_daily_http_saved_replay_successor_and_private_evidence(integration):
    env = integration
    headers, _, wid, _, _, root = prepare(env)
    before = env.client.get(root + "/understanding", headers=headers).json()
    response = create(env, headers, root, **request("-0.1", 7))
    assert response.status_code == 201, response.text
    run = response.json()["run"]
    assert Decimal(run["result"]["alternatives"][0]["result"]) == Decimal("-0.55")
    url = root.split("/uploads/")[0] + "/decision-analysis/" + run["id"]
    assert env.client.get(url, headers=headers).json()["run"] == run
    successor = create(env, headers, root, parent_run_id=run["id"], **request("0.1", 3))
    assert successor.status_code == 201, successor.text
    member, _ = add_member(env, headers, wid, "admin")
    assert env.client.get(url, headers=member).status_code == 404
    receipt = f"/workspaces/{wid}/queries/{run['evidence']['query_id']}/replay"
    assert env.client.post(receipt, headers=member).status_code == 404
    assert env.client.post(receipt, headers=headers).status_code == 200
    assert env.client.get(root + "/understanding", headers=headers).json() == before


@pytest.mark.parametrize("days", [True, "7", 0, 3651])
def test_daily_http_requires_an_explicit_bounded_integer(integration, days):
    env = integration
    headers, _, _, _, _, root = prepare(env)
    response = create(env, headers, root, **request(days=days))
    assert response.status_code == 422, response.text
