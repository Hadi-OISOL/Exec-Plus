"""Use case: Independently verifies declared consolidation arithmetic and boundaries.

What it does: Checks currency translation and cumulative reciprocal eliminations with
Fraction oracles, preserving external balances, input ledgers and unresolved differences.
"""

import copy
from dataclasses import replace
from datetime import date
from decimal import Decimal, localcontext
from fractions import Fraction
from random import Random

import pytest

from execplus.domain.company_consolidation import CompanyLedger, LedgerRow, consolidate
from execplus.domain.ingestion import IngestionError


def fixture():
    companies = tuple(
        CompanyLedger(
            company_id,
            "Company " + company_id,
            currency,
            date(2026, 1, 1),
            date(2026, 1, 31),
            "debit_positive",
            tuple(
                LedgerRow(account, Decimal(value), counterparty)
                for account, value, counterparty in rows
            ),
        )
        for company_id, currency, rows in (
            (
                "A",
                "USD",
                [
                    ("cash", "100", None),
                    ("capital", "-100", None),
                    ("receivable", "10", "B"),
                    ("sale", "-10", None),
                ],
            ),
            (
                "B",
                "EUR",
                [
                    ("cash", "50", None),
                    ("capital", "-50", None),
                    ("payable", "-8", "A"),
                    ("expense", "8", None),
                ],
            ),
        )
    )
    request = {
        "reporting_currency": "USD",
        "assumptions_confirmed": True,
        "mappings": {
            company.company_id: [
                {"account": row.account, "group_account": row.account, "rate_key": "period"}
                for row in company.rows
            ]
            for company in companies
        },
        "rates": {
            company.company_id: [
                {
                    "key": "period",
                    "basis": "closing",
                    "value": "1" if company.currency == "USD" else "1.25",
                    "as_of": "2026-01-31",
                    "reference": "Explicit fictional rate",
                }
            ]
            for company in companies
        },
        "eliminations": [
            {
                "name": "Reciprocal balances",
                "entries": [
                    {
                        "company_id": "A",
                        "account": "receivable",
                        "counterparty": "B",
                        "amount": "-10",
                    },
                    {"company_id": "B", "account": "payable", "counterparty": "A", "amount": "10"},
                ],
            }
        ],
    }
    return companies, request


def test_exact_translation_and_balanced_eliminations_preserve_every_layer():
    companies, request = fixture()
    before = copy.deepcopy((companies, request))
    result = consolidate(companies, request)
    assert result["version"] == "company-consolidation-v1"
    combined = {row["group_account"]: row["amount"] for row in result["combined"]}
    final = {row["group_account"]: row["amount"] for row in result["consolidated"]}
    assert combined == {
        "cash": "162.5",
        "capital": "-162.5",
        "receivable": "10",
        "sale": "-10",
        "payable": "-10",
        "expense": "10",
    }
    assert final == {**combined, "receivable": "0", "payable": "0"}
    assert result["totals"] == {"combined": "0", "eliminations": "0", "consolidated": "0"}
    assert result["remaining_internal_balances"] == [] and result["warnings"] == []
    assert len(result["source_balances"]) == 8
    assert (companies, request) == before
    assert consolidate(tuple(reversed(companies)), request) == result


def test_missing_eliminations_and_translation_imbalance_are_reported_without_balancing():
    companies, request = fixture()
    request["eliminations"] = []
    request["rates"]["B"].append(
        {
            "key": "old",
            "basis": "historical",
            "value": "1.1",
            "as_of": "2020-01-01",
            "reference": "Declared historical rate",
        }
    )
    request["mappings"]["B"][1]["rate_key"] = "old"
    result = consolidate(companies, request)
    assert result["totals"]["consolidated"] == "7.5"
    assert result["warnings"] == ["reporting_balance_not_zero", "remaining_internal_balances"]
    assert len(result["remaining_internal_balances"]) == 2
    assert result["contributions"][1]["source_total"] == "0"
    assert result["contributions"][1]["translated_total"] == "7.5"
    assert len(result["consolidated"]) == 6


def test_repeated_partial_journals_cannot_over_remove_a_balance():
    companies, request = fixture()
    first = request["eliminations"][0]
    first["entries"][0]["amount"] = "-5"
    first["entries"][1]["amount"] = "5"
    request["eliminations"].append({**copy.deepcopy(first), "name": "Remaining half"})
    assert consolidate(companies, request)["remaining_internal_balances"] == []
    request["eliminations"].append({**copy.deepcopy(first), "name": "Exceeds remaining"})
    with pytest.raises(IngestionError, match="without exceeding"):
        consolidate(companies, request)


@pytest.mark.parametrize(
    "change",
    [
        "confirmation",
        "unmapped",
        "extra_account",
        "duplicate_account",
        "missing_rate",
        "negative_rate",
        "zero_rate",
        "same_currency_rate",
        "rate_date",
        "rate_basis",
        "float_rate",
        "external",
        "same_company",
        "unknown_account",
        "over_remove",
        "unbalanced",
        "wrong_direction",
        "float_entry",
        "extra_field",
        "one_sided_pair",
    ],
)
def test_incomplete_or_unsafe_declared_inputs_are_rejected(change):
    companies, request = fixture()
    entry = request["eliminations"][0]["entries"][0]
    rate = request["rates"]["B"][0]
    if change == "confirmation":
        request["assumptions_confirmed"] = False
    elif change == "unmapped":
        request["mappings"]["A"].pop()
    elif change == "extra_account":
        request["mappings"]["A"].append(
            {"account": "absent", "group_account": "cash", "rate_key": "period"}
        )
    elif change == "duplicate_account":
        request["mappings"]["A"].append(copy.deepcopy(request["mappings"]["A"][0]))
    elif change == "missing_rate":
        request["mappings"]["A"][0]["rate_key"] = "missing"
    elif change == "negative_rate":
        rate["value"] = "-1"
    elif change == "zero_rate":
        rate["value"] = "0"
    elif change == "same_currency_rate":
        request["rates"]["A"][0]["value"] = "2"
    elif change == "rate_date":
        rate["as_of"] = "2026-02-30"
    elif change == "rate_basis":
        rate["basis"] = []
    elif change == "float_rate":
        rate["value"] = 1.25
    elif change == "external":
        entry["counterparty"] = "External supplier"
    elif change == "same_company":
        entry["counterparty"] = "A"
    elif change == "unknown_account":
        entry["account"] = "absent"
    elif change == "over_remove":
        entry["amount"] = "-11"
    elif change == "unbalanced":
        entry["amount"] = "-9"
    elif change == "wrong_direction":
        entry["amount"] = "10"
    elif change == "float_entry":
        entry["amount"] = -10.0
    elif change == "extra_field":
        entry["sql"] = "select anything"
    else:
        company = companies[0]
        companies = (
            replace(
                company,
                rows=tuple(
                    replace(row, counterparty="B") if row.account == "sale" else row
                    for row in company.rows
                ),
            ),
            companies[1],
        )
        request["eliminations"][0]["entries"][1] = {
            "company_id": "A",
            "account": "sale",
            "counterparty": "B",
            "amount": "10",
        }
    with pytest.raises(IngestionError):
        consolidate(companies, request)


@pytest.mark.parametrize(
    "change",
    [
        "period",
        "period_order",
        "sign",
        "duplicate_company",
        "one_company",
        "empty",
        "missing_account",
        "missing_amount",
        "float_amount",
        "nan",
        "huge_exponent",
        "self_counterparty",
        "too_many_rows",
    ],
)
def test_source_boundaries_are_explicit_and_no_rows_are_silently_dropped(change):
    companies, request = fixture()
    company = companies[0]
    if change == "period":
        company = replace(company, period_start=date(2025, 1, 1))
    elif change == "period_order":
        company = replace(company, period_end=date(2025, 1, 1))
    elif change == "sign":
        company = replace(company, sign_convention="credit_positive")
    elif change == "duplicate_company":
        companies = (companies[1], companies[1])
    elif change == "one_company":
        companies = (company,)
    elif change == "empty":
        company = replace(company, rows=())
    elif change == "too_many_rows":
        company = replace(company, rows=(company.rows[0],) * 10001)
    else:
        row = company.rows[0]
        values = {
            "missing_account": {"account": ""},
            "missing_amount": {"amount": None},
            "float_amount": {"amount": 0.1},
            "nan": {"amount": Decimal("NaN")},
            "huge_exponent": {"amount": Decimal("0E+999999")},
            "self_counterparty": {"counterparty": "A"},
        }
        company = replace(company, rows=(replace(row, **values[change]), *company.rows[1:]))
    if change not in {"duplicate_company", "one_company"}:
        companies = (company, companies[1])
    with pytest.raises(IngestionError):
        consolidate(companies, request)


def test_fifty_populations_match_independent_rational_currency_oracles():
    rng = Random(610016)
    base, original = fixture()
    for trial in range(50):
        request = copy.deepcopy(original)
        request["eliminations"] = []
        companies = []
        oracle = {}
        for company in base:
            rows = []
            for old in company.rows:
                numerator = rng.randint(-(10**20), 10**20)
                denominator = 10 ** (trial % 12)
                with localcontext() as context:
                    context.prec = 80
                    value = Decimal(numerator) / Decimal(denominator)
                rows.append(replace(old, amount=value, counterparty=None))
                rate = Fraction(1) if company.currency == "USD" else Fraction(5, 4)
                oracle[old.account] = (
                    oracle.get(old.account, Fraction()) + Fraction(numerator, denominator) * rate
                )
            companies.append(replace(company, rows=tuple(rows)))
        with localcontext() as context:
            context.prec = 6
            result = consolidate(tuple(companies), request)
        actual = {
            row["group_account"]: Fraction(Decimal(row["amount"])) for row in result["consolidated"]
        }
        assert actual == oracle
        assert Fraction(Decimal(result["totals"]["consolidated"])) == sum(oracle.values())


def test_maximum_scale_and_magnitude_remain_exact_without_context_rounding():
    companies, request = fixture()
    request["eliminations"] = []
    request["rates"]["B"][0]["value"] = "1e-38"
    large = Decimal("9" * 38 + "." + "9" * 38)
    small = Decimal("1e-38")
    companies = (
        replace(
            companies[0], rows=(replace(companies[0].rows[0], amount=small), *companies[0].rows[1:])
        ),
        replace(
            companies[1], rows=(replace(companies[1].rows[0], amount=large), *companies[1].rows[1:])
        ),
    )
    with localcontext() as context:
        context.prec = 6
        result = consolidate(companies, request)
    cash = next(row["amount"] for row in result["consolidated"] if row["group_account"] == "cash")
    assert Fraction(Decimal(cash)) == Fraction(small) + Fraction(large) * Fraction(small)


def test_globally_balanced_journal_cannot_hide_unbalanced_company_pairs():
    companies, request = fixture()
    third = replace(
        companies[0],
        company_id="C",
        name="Company C",
        rows=(LedgerRow("payable", Decimal("-10"), "A"),),
    )
    first = replace(
        companies[0], rows=(*companies[0].rows, LedgerRow("receivable", Decimal("10"), "C"))
    )
    request["mappings"]["C"] = [
        {"account": "payable", "group_account": "payable", "rate_key": "period"}
    ]
    request["rates"]["C"] = copy.deepcopy(request["rates"]["A"])
    request["eliminations"] = [
        {
            "name": "Globally balanced but mismatched",
            "entries": [
                {"company_id": "A", "account": "receivable", "counterparty": "B", "amount": "-4"},
                {"company_id": "B", "account": "payable", "counterparty": "A", "amount": "3"},
                {"company_id": "A", "account": "receivable", "counterparty": "C", "amount": "-2"},
                {"company_id": "C", "account": "payable", "counterparty": "A", "amount": "3"},
            ],
        }
    ]
    with pytest.raises(IngestionError) as error:
        consolidate((first, companies[1], third), request)
    assert error.value.code == "consolidation_balance"
