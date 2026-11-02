import importlib.util
import pathlib
from datetime import datetime, timezone

import CraftifyAIUsage as U

VIEW_PATH = pathlib.Path(__file__).resolve().parents[2] / "craftify-library" / "client_code" / "CraftifyUtils" / "ai_usage_view.py"
_spec = importlib.util.spec_from_file_location("ai_usage_view", VIEW_PATH)
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
USAGE = {"prompt_tokens": 12000, "completion_tokens": 800, "prompt_tokens_details": {"cached_tokens": 2000},
         "completion_tokens_details": {"reasoning_tokens": 0}}


def test_dated_model_names_use_the_longest_matching_price():
    assert U.price_for("gpt-4.1-2025-04-14") == U.PRICES["gpt-4.1"]
    assert U.price_for("gpt-4.1-mini-2025-04-14") == U.PRICES["gpt-4.1-mini"]
    assert U.price_for("mystery-model") is None


def test_cost_bills_cached_input_at_the_cached_rate():
    cost = U.cost_usd("gpt-4.1", 12000, 2000, 800)
    assert abs(cost - (10000 * 2.0 + 2000 * 0.5 + 800 * 8.0) / 1e6) < 1e-12


def test_record_reads_the_openai_usage_block():
    record = U.record_from_usage("Coach review", "gpt-4.1-2025-04-14", USAGE, 3210.4, request_id="req_1", at=NOW)
    assert (record["input_tokens"], record["cached_tokens"], record["output_tokens"]) == (12000, 2000, 800)
    assert record["latency_ms"] == 3210 and record["status"] == "ok" and record["cost_usd"] > 0
    failed = U.record_from_usage("Coach review", "gpt-4.1", None, 900, status="error", error="HTTP 429", at=NOW)
    assert failed["cost_usd"] == 0.0 and failed["input_tokens"] == 0


def _records():
    return [
        U.record_from_usage("Coach review", "gpt-4.1", USAGE, 3000, at=datetime(2026, 11, 2, 9, tzinfo=timezone.utc)),
        U.record_from_usage("DEXA scan reading", "gpt-4.1", USAGE, 9000, at=datetime(2026, 10, 30, 9, tzinfo=timezone.utc)),
        U.record_from_usage("Coach review", "gpt-4.1", None, 500, status="error", error="HTTP 429",
                            at=datetime(2026, 11, 1, 9, tzinfo=timezone.utc)),
        U.record_from_usage("DEXA scan reading", "gpt-4.1", USAGE, 9000, at=datetime(2026, 8, 1, 9, tzinfo=timezone.utc)),
    ]


def test_summary_covers_the_period_and_keeps_month_and_all_time_spend():
    report = U.summarize(_records(), days=7, now=NOW)
    one = U.cost_usd("gpt-4.1", 12000, 2000, 800)
    assert report["totals"]["calls"] == 3 and report["totals"]["errors"] == 1
    assert abs(report["totals"]["cost_usd"] - 2 * one) < 1e-6
    assert abs(report["month_cost_usd"] - one) < 1e-6
    assert abs(report["all_time_cost_usd"] - 3 * one) < 1e-6
    assert len(report["chart"]["bars"]) == 7 and report["chart"]["bars"][-1]["label"] == "2026-11-02"
    assert report["recent"][0]["at"].startswith("2026-11-02")
    assert {row["name"] for row in report["by_feature"]} == {"Coach review", "DEXA scan reading"}


def test_all_time_report_groups_the_chart_by_month():
    report = U.summarize(_records(), days=0, now=NOW)
    assert report["chart"]["unit"] == "month"
    assert [bar["label"] for bar in report["chart"]["bars"]] == ["2026-08", "2026-10", "2026-11"]


def test_report_html_shows_tiles_calls_and_states():
    html = V.report_html(U.summarize(_records(), days=30, now=NOW), fmt_time=lambda iso: iso[:10])
    assert "Spend" in html and "DEXA scan reading" in html and "Failed" in html and "2,000 cached" in html
    assert "not set up" in V.report_html({"ready": False})
    assert "No AI calls" in V.report_html(U.summarize([], days=7, now=NOW))
    assert V.usd(0.00412) == "$0.0041" and V.count(1234567) == "1,234,567"
