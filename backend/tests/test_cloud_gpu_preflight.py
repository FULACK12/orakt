"""Offline GPU cost guard: no credentials, databases, or cloud calls needed."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "cloud_gpu_preflight.py"
SPEC = importlib.util.spec_from_file_location("cloud_gpu_preflight", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)
NOW = datetime(2026, 10, 5, 12, tzinfo=UTC)


@pytest.fixture
def plan() -> dict[str, Any]:
    # CAD is only test data; production currency must be explicitly verified.
    return {
        "currency": "CAD", "quote_currency": "CAD", "credit_currency": "CAD",
        "currency_verified": True,
        "credit_balance": "415.91", "plan_spent": "0", "reserve_buffer": "115.91",
        "hourly_cost": "4.2", "storage_network_reserve": "2", "batch_cost_limit": "20",
        "credit_checked_at": "2026-10-05T11:50:00Z",
        "credit_expires_at": "2026-12-27T10:00:00Z",
        "quote_at": "2026-10-05T11:50:00Z",
        "quote_valid_until": "2026-10-05T18:00:00Z",
        "start_at": "2026-10-05T12:05:00Z", "terminate_at": "2026-10-05T14:05:00Z",
        "all_resources_included": True, "max_instances": 1, "automatic_restart": False,
    }


def test_valid_plan_reports_decimal_cost_boundaries(plan: dict[str, Any]) -> None:
    report = preflight.evaluate_plan(plan, now=NOW)
    assert report["approved"] is True
    assert report["reasons"] == []
    assert report["dry_run"] is True
    assert report["execution_permitted"] is False
    assert report["enforces_cloud_spending"] is False
    assert report["currency"] == "CAD"
    assert report["cost_boundaries"]["batch_estimate_ceiling"] == "10.750000"
    assert report["cost_boundaries"]["available_for_batch"] == "300"
    assert report["effective_credit_cutoff_utc"] == "2026-12-27T00:00:00+00:00"


@pytest.mark.parametrize("field", sorted(preflight.KNOWN_FIELDS))
def test_every_field_is_explicitly_required(plan: dict[str, Any], field: str) -> None:
    del plan[field]
    report = preflight.evaluate_plan(plan, now=NOW)
    assert report["approved"] is False
    assert report["reasons"]


@pytest.mark.parametrize("value", ["0", "-1", "NaN", "Infinity", "-Infinity", True, None,
                                   "1e999999", "0.0000000000001", 0.1, [], {}])
@pytest.mark.parametrize("field", ["credit_balance", "reserve_buffer", "hourly_cost",
                                   "storage_network_reserve", "batch_cost_limit"])
def test_invalid_amounts_fail_closed(plan: dict[str, Any], field: str, value: Any) -> None:
    plan[field] = value
    assert preflight.evaluate_plan(plan, now=NOW)["approved"] is False


@pytest.mark.parametrize(("field", "value"), [
    ("plan_spent", "-1"), ("plan_spent", "NaN"), ("plan_spent", "301"),
    ("credit_balance", "415.92"), ("credit_balance", "120"),
    ("reserve_buffer", "115.90"), ("reserve_buffer", "500"),
    ("max_instances", 0), ("max_instances", 2), ("max_instances", True),
    ("max_instances", "1"), ("max_instances", Decimal("1")),
    ("automatic_restart", True), ("automatic_restart", "false"),
    ("automatic_restart", 0), ("all_resources_included", False),
    ("currency_verified", False), ("currency_verified", "true"),
    ("currency", "UNKNOWN"), ("currency", "ZZZ"), ("currency", "cad"),
    ("quote_currency", "USD"), ("credit_currency", "USD"),
    ("hourly_cost", "1000"), ("batch_cost_limit", "301"),
])
def test_unsafe_or_unverified_facts_fail_closed(
    plan: dict[str, Any], field: str, value: Any,
) -> None:
    plan[field] = value
    assert preflight.evaluate_plan(plan, now=NOW)["approved"] is False


@pytest.mark.parametrize("field", ["quote_at", "credit_checked_at"])
@pytest.mark.parametrize("value", ["2026-10-05T10:59:59Z", "2026-10-05T12:00:01Z",
                                   "2026-10-05T11:00:00Z"])
def test_stale_future_and_stale_at_startup_facts_are_rejected(
    plan: dict[str, Any], field: str, value: str,
) -> None:
    plan[field] = value
    assert preflight.evaluate_plan(plan, now=NOW)["approved"] is False


@pytest.mark.parametrize(("field", "value"), [
    ("start_at", "2026-10-05T11:59:59Z"),
    ("start_at", "2026-10-05T14:06:00Z"),
    ("terminate_at", "2026-10-05T12:05:00Z"),
    ("terminate_at", "2026-10-05T11:00:00Z"),
    ("terminate_at", "2026-12-27T00:00:00Z"),
    ("terminate_at", "2026-12-27T12:00:00Z"),
    ("credit_expires_at", "2026-10-05T11:59:59Z"),
    ("credit_expires_at", "2026-10-05T14:05:00Z"),
    ("quote_valid_until", "2026-10-05T14:04:59Z"),
    ("quote_valid_until", "2026-10-05T11:40:00Z"),
    ("terminate_at", "2026-10-05T14:05:00"),
    ("terminate_at", "2026-10-05T14:05:00-04:00"),
    ("terminate_at", "2026-10-05"), ("terminate_at", "2026-02-31T14:05:00Z"),
    ("terminate_at", "9999-12-31T23:59:59Z"),
])
def test_unsafe_timing_fails_closed(plan: dict[str, Any], field: str, value: str) -> None:
    plan[field] = value
    assert preflight.evaluate_plan(plan, now=NOW)["approved"] is False


def test_cumulative_plan_and_credit_headroom_both_constrain_batch(plan: dict[str, Any]) -> None:
    plan.update(plan_spent="289", batch_cost_limit="11", hourly_cost="4")
    report = preflight.evaluate_plan(plan, now=NOW)
    assert report["approved"] is True
    assert report["cost_boundaries"]["cumulative_plan_after_batch_estimate"] == "299.333334"
    plan["credit_balance"] = "125.90"
    report = preflight.evaluate_plan(plan, now=NOW)
    assert report["approved"] is False
    assert report["cost_boundaries"]["available_for_batch"] == "9.99"


def test_fractional_seconds_and_repeating_cost_are_rounded_up(plan: dict[str, Any]) -> None:
    plan.update(hourly_cost="1", terminate_at="2026-10-05T12:05:00.000001Z")
    report = preflight.evaluate_plan(plan, now=NOW)
    assert report["approved"] is True
    assert report["cost_boundaries"]["planned_runtime_seconds"] == "1"
    assert report["cost_boundaries"]["billable_seconds_ceiling"] == "301"
    assert report["cost_boundaries"]["batch_estimate_ceiling"] == "2.083612"


def test_quote_and_credit_must_cover_shutdown_allowance(plan: dict[str, Any]) -> None:
    plan["quote_valid_until"] = plan["terminate_at"]
    assert preflight.evaluate_plan(plan, now=NOW)["approved"] is False
    plan["quote_valid_until"] = "2026-10-05T18:00:00Z"
    plan["credit_expires_at"] = "2026-10-05T14:06:00Z"
    assert preflight.evaluate_plan(plan, now=NOW)["approved"] is False


@pytest.mark.parametrize("bad_plan", [None, [], "plan", {"unknown": 1}])
def test_malformed_plan_cannot_approve(bad_plan: Any) -> None:
    assert preflight.evaluate_plan(bad_plan, now=NOW)["approved"] is False


def test_naive_clock_cannot_approve(plan: dict[str, Any]) -> None:
    assert preflight.evaluate_plan(plan, now=NOW.replace(tzinfo=None))["approved"] is False


@pytest.mark.parametrize("raw", ['{"currency":"CAD","currency":"USD"}',
                                 '{"hourly_cost":NaN}', "not JSON", "[]"])
def test_cli_malformed_json_is_structured_denial(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], raw: str,
) -> None:
    path = tmp_path / "plan.json"
    path.write_text(raw, encoding="utf-8")
    assert preflight.main(["--plan", str(path)]) == 2
    assert json.loads(capsys.readouterr().out)["approved"] is False


def test_cli_flags_and_json_are_equivalent(
    plan: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    evaluate = preflight.evaluate_plan
    monkeypatch.setattr(preflight, "evaluate_plan", lambda value: evaluate(value, now=NOW))
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    assert preflight.main(["--plan", str(path), "--dry-run"]) == 0
    json_report = json.loads(capsys.readouterr().out)
    argv = ["--currency-verified", "--all-resources-included", "--no-automatic-restart"]
    for name, value in plan.items():
        if name not in preflight.FLAG_FIELDS:
            argv.extend(["--" + name.replace("_", "-"), str(value)])
    assert preflight.main(argv) == 0
    assert json.loads(capsys.readouterr().out) == json_report


@pytest.mark.parametrize("argv", [[], ["--max-instances", "many"], ["--launch"],
                                  ["--plan", "missing.json"],
                                  ["--plan", "missing.json", "--currency", "CAD"]])
def test_cli_missing_or_conflicting_input_is_denied(
    capsys: pytest.CaptureFixture[str], argv: list[str],
) -> None:
    assert preflight.main(argv) == 2
    assert json.loads(capsys.readouterr().out)["approved"] is False
