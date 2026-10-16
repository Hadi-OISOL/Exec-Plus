"""Use case: Combines explicitly mapped company ledgers into a reviewable worksheet.

What it does: Applies declared currency rates and balanced internal eliminations with
exact arithmetic, retaining each contribution and unresolved balance for inspection.
"""

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, Inexact, localcontext
from fractions import Fraction
from typing import Any

from execplus.domain.decision_analysis import fail, number

VERSION = "company-consolidation-v1"
RATE_BASES = {"closing", "transaction_average", "historical"}


@dataclass(frozen=True)
class LedgerRow:
    account: str
    amount: Decimal
    counterparty: str | None = None


@dataclass(frozen=True)
class CompanyLedger:
    company_id: str
    name: str
    currency: str
    period_start: date
    period_end: date
    sign_convention: str
    rows: tuple[LedgerRow, ...]


def text(value: object, limit: int = 200) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or any(ord(char) < 32 for char in value)
    ):
        fail("consolidation_text", "Use nonempty bounded names and account codes.")
    return value


def currency(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch("[A-Z]{3}", value):
        fail("consolidation_currency", "Declare a three-letter uppercase currency code.")
    return value


def amount(value: object, *, source: bool = False) -> Fraction:
    if not isinstance(value, Decimal if source else str):
        fail("consolidation_amount", "Supply complete exact amounts; floats are not accepted.")
    parsed = number(value)
    exponent = parsed.as_tuple().exponent
    if not isinstance(exponent, int) or not -38 <= exponent <= 38:
        fail("consolidation_amount", "Use bounded decimal amounts and rates.")
    return Fraction(parsed)


def exact(value: Fraction) -> str:
    with localcontext() as context:
        context.prec = 200
        context.traps[Inexact] = True
        result = Decimal(value.numerator) / Decimal(value.denominator)
    rendered = format(result, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if result == 0 else rendered


def fields(value: object, expected: set[str], code: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        fail(code, "Complete the declared fields without extra settings.")
    return value


def rates_for(company: CompanyLedger, raw: object, reporting: str) -> dict[str, dict[str, str]]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= 256:
        fail("consolidation_rates", "Declare one to 256 named rates per company.")
    rates = {}
    for item in raw:
        record = fields(
            item, {"key", "basis", "value", "as_of", "reference"}, "consolidation_rates"
        )
        key = text(record["key"], 80)
        if (
            key in rates
            or not isinstance(record["basis"], str)
            or record["basis"] not in RATE_BASES
        ):
            fail("consolidation_rates", "Use unique rate names and a declared rate basis.")
        value = amount(record["value"])
        if value <= 0 or (company.currency == reporting and value != 1):
            fail("consolidation_rates", "Rates must be positive; same-currency rates must be one.")
        try:
            day = date.fromisoformat(record["as_of"])
        except (TypeError, ValueError):
            fail("consolidation_rates", "Give every rate an explicit calendar date.")
        if day.isoformat() != record["as_of"]:
            fail("consolidation_rates", "Use YYYY-MM-DD rate dates.")
        rates[key] = {
            "key": key,
            "basis": record["basis"],
            "value": exact(value),
            "as_of": day.isoformat(),
            "reference": text(record["reference"], 500),
        }
    return rates


def validate_companies(companies: tuple[CompanyLedger, ...]) -> set[str]:
    if not isinstance(companies, tuple) or not 2 <= len(companies) <= 8:
        fail("consolidation_companies", "Choose two to eight company ledgers.")
    ids = set()
    periods = set()
    signs = set()
    for company in companies:
        if not isinstance(company, CompanyLedger):
            fail("consolidation_companies", "Use prepared company ledgers.")
        ids.add(text(company.company_id, 80))
        text(company.name)
        currency(company.currency)
        if (
            type(company.period_start) is not date
            or type(company.period_end) is not date
            or company.period_start > company.period_end
        ):
            fail("consolidation_period", "Declare a valid reporting period for every company.")
        periods.add((company.period_start, company.period_end))
        if not isinstance(company.sign_convention, str):
            fail("consolidation_signs", "Declare a common debit/credit sign convention.")
        signs.add(company.sign_convention)
        if not isinstance(company.rows, tuple) or not 1 <= len(company.rows) <= 10000:
            fail("consolidation_population", "Use complete ledgers of one to 10,000 rows each.")
        for row in company.rows:
            if not isinstance(row, LedgerRow):
                fail(
                    "consolidation_population", "Every source row needs a prepared account balance."
                )
            text(row.account)
            amount(row.amount, source=True)
            if row.counterparty is not None:
                text(row.counterparty)
                if row.counterparty == company.company_id:
                    fail("consolidation_counterparty", "A company cannot be its own counterparty.")
    if len(ids) != len(companies):
        fail("consolidation_companies", "Each company must appear only once.")
    if len(periods) != 1:
        fail(
            "consolidation_period", "Prepare the same explicit reporting period for all companies."
        )
    if len(signs) != 1 or not signs <= {"debit_positive", "credit_positive"}:
        fail("consolidation_signs", "Confirm one common debit/credit sign convention.")
    return ids


def eliminate(
    raw: object,
    ids: set[str],
    balances: dict[tuple[str, str, str | None], Fraction],
) -> tuple[dict[tuple[str, str, str | None], Fraction], list[dict[str, Any]]]:
    if not isinstance(raw, list) or len(raw) > 100:
        fail("consolidation_eliminations", "Declare at most 100 explicit elimination journals.")
    remaining = dict(balances)
    journals = []
    names = set()
    for value in raw:
        journal = fields(value, {"name", "entries"}, "consolidation_eliminations")
        name = text(journal["name"])
        if name.casefold() in names:
            fail("consolidation_eliminations", "Use distinct journal names.")
        names.add(name.casefold())
        entries = journal["entries"]
        if not isinstance(entries, list) or not 2 <= len(entries) <= 64:
            fail("consolidation_eliminations", "Each journal needs two to 64 explicit entries.")
        pairs: dict[tuple[str, str], Fraction] = defaultdict(Fraction)
        directions: dict[tuple[str, str], set[str]] = defaultdict(set)
        prepared = []
        for entry in entries:
            entry = fields(
                entry,
                {"company_id", "account", "counterparty", "amount"},
                "consolidation_eliminations",
            )
            company = text(entry["company_id"], 80)
            counterparty = text(entry["counterparty"], 80)
            key = (company, text(entry["account"]), counterparty)
            change = amount(entry["amount"])
            if company not in ids or counterparty not in ids or company == counterparty:
                fail(
                    "consolidation_eliminations",
                    "Eliminate only declared reciprocal internal balances.",
                )
            current = remaining.get(key, Fraction())
            if not change or current * change >= 0 or abs(change) > abs(current):
                fail(
                    "consolidation_eliminations",
                    "An entry must reduce an existing internal balance without exceeding it.",
                )
            remaining[key] = current + change
            pair = (min(company, counterparty), max(company, counterparty))
            pairs[pair] += change
            directions[pair].add(company)
            prepared.append({**entry, "amount": exact(change)})
        if any(value != 0 or len(directions[pair]) != 2 for pair, value in pairs.items()):
            fail(
                "consolidation_balance",
                "Every reciprocal company pair must balance exactly within each journal.",
            )
        journals.append({"name": name, "entries": prepared})
    return remaining, journals


def consolidate(companies: tuple[CompanyLedger, ...], request: dict[str, Any]) -> dict[str, Any]:
    ids = validate_companies(companies)
    fields(
        request,
        {"reporting_currency", "assumptions_confirmed", "mappings", "rates", "eliminations"},
        "consolidation_request",
    )
    reporting = currency(request["reporting_currency"])
    if request["assumptions_confirmed"] is not True:
        fail(
            "consolidation_confirmation",
            "Confirm the reporting period, signs, mapping and rate assumptions.",
        )
    for setting in ("mappings", "rates"):
        if not isinstance(request[setting], dict) or set(request[setting]) != ids:
            fail("consolidation_mapping", "Declare complete settings for each selected company.")
    groups: dict[tuple[str, str], str] = {}
    rates_used: dict[tuple[str, str], str] = {}
    balances: dict[tuple[str, str, str | None], Fraction] = defaultdict(Fraction)
    originals: dict[tuple[str, str, str | None], Fraction] = defaultdict(Fraction)
    contributions = []
    combined: dict[str, Fraction] = defaultdict(Fraction)
    for company in sorted(companies, key=lambda item: item.company_id):
        cid = company.company_id
        rate_map = rates_for(company, request["rates"][cid], reporting)
        mappings = request["mappings"][cid]
        accounts = {row.account for row in company.rows}
        if not isinstance(mappings, list) or not 1 <= len(mappings) <= 256:
            fail("consolidation_mapping", "Map one to 256 source accounts per company.")
        mapped = {}
        for mapping in mappings:
            item = fields(
                mapping, {"account", "group_account", "rate_key"}, "consolidation_mapping"
            )
            account = text(item["account"])
            rate_key = text(item["rate_key"], 80)
            if account in mapped or rate_key not in rate_map:
                fail("consolidation_mapping", "Map each account once to an existing named rate.")
            mapped[account] = item
            groups[cid, account] = text(item["group_account"])
            rates_used[cid, account] = item["rate_key"]
        if set(mapped) != accounts or set(rate_map) != {
            item["rate_key"] for item in mapped.values()
        }:
            fail(
                "consolidation_mapping",
                "Map every source account and use only declared rates needed by those accounts.",
            )
        company_groups: dict[str, Fraction] = defaultdict(Fraction)
        source_total = Fraction()
        for row in company.rows:
            key = (cid, row.account, row.counterparty)
            value = amount(row.amount, source=True)
            converted = value * amount(rate_map[rates_used[cid, row.account]]["value"])
            originals[key] += value
            balances[key] += converted
            company_groups[groups[cid, row.account]] += converted
            source_total += value
        for group, value in company_groups.items():
            combined[group] += value
        contributions.append(
            {
                "company_id": cid,
                "name": company.name,
                "currency": company.currency,
                "source_total": exact(source_total),
                "translated_total": exact(sum(company_groups.values(), Fraction())),
                "accounts": [
                    {"group_account": key, "amount": exact(value)}
                    for key, value in sorted(company_groups.items())
                ],
                "rates": [rate_map[key] for key in sorted(rate_map)],
            }
        )
    remaining, journals = eliminate(request["eliminations"], ids, dict(balances))
    final: dict[str, Fraction] = defaultdict(Fraction)
    source_balances = []
    internal = []
    for key in sorted(balances, key=lambda item: (item[0], item[1], item[2] or "")):
        cid, account, counterparty = key
        group = groups[cid, account]
        final[group] += remaining[key]
        record = {
            "company_id": cid,
            "account": account,
            "group_account": group,
            "counterparty": counterparty,
            "internal": counterparty in ids,
            "source_amount": exact(originals[key]),
            "rate_key": rates_used[cid, account],
            "translated_amount": exact(balances[key]),
            "elimination": exact(remaining[key] - balances[key]),
            "remaining": exact(remaining[key]),
        }
        source_balances.append(record)
        if counterparty in ids and remaining[key]:
            internal.append(record)
    combined_total = sum(combined.values(), Fraction())
    final_total = sum(final.values(), Fraction())
    return {
        "version": VERSION,
        "reporting_currency": reporting,
        "period_start": companies[0].period_start.isoformat(),
        "period_end": companies[0].period_end.isoformat(),
        "sign_convention": companies[0].sign_convention,
        "contributions": contributions,
        "source_balances": source_balances,
        "combined": [
            {"group_account": key, "amount": exact(value)}
            for key, value in sorted(combined.items())
        ],
        "eliminations": journals,
        "elimination_totals": [
            {"group_account": key, "amount": exact(final[key] - combined[key])}
            for key in sorted(combined)
        ],
        "consolidated": [
            {"group_account": key, "amount": exact(value)} for key, value in sorted(final.items())
        ],
        "totals": {
            "combined": exact(combined_total),
            "eliminations": exact(final_total - combined_total),
            "consolidated": exact(final_total),
        },
        "remaining_internal_balances": internal,
        "warnings": (["reporting_balance_not_zero"] if final_total else [])
        + (["remaining_internal_balances"] if internal else []),
        "limitation": (
            "A worksheet using your declared mappings, rates and eliminations; "
            "unresolved balances are retained. No statutory accounting compliance is inferred."
        ),
    }
