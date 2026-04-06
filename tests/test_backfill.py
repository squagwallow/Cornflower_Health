"""
Tests for src/backfill.py
Covers: payload parsing, date extraction, per-day payload building,
        dry-run mode, error handling, source_tags override.

Uses existing sample payloads in samples/ directory.
Does NOT call real Notion API — notion_writer.write is mocked.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from backfill import (
    _extract_metrics_list,
    _collect_dates,
    _build_day_payload,
    run_backfill,
)

SAMPLES_DIR = Path(__file__).parent.parent / "samples"
SAMPLE_ARRAY = SAMPLES_DIR / "hae_sample_2026-04-05.json"   # array-wrapped
SAMPLE_DICT = SAMPLES_DIR / "hae_live_2026-04-06.json"      # dict-wrapped


@pytest.fixture(scope="module")
def array_payload():
    return json.loads(SAMPLE_ARRAY.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dict_payload():
    return json.loads(SAMPLE_DICT.read_text(encoding="utf-8"))


# ----------------------------------------------------------------
# _extract_metrics_list
# ----------------------------------------------------------------

class TestExtractMetricsList:
    def test_array_wrapper(self, array_payload):
        metrics = _extract_metrics_list(array_payload)
        assert metrics is not None
        assert isinstance(metrics, list)
        assert len(metrics) > 0
        assert "name" in metrics[0]

    def test_dict_wrapper(self, dict_payload):
        metrics = _extract_metrics_list(dict_payload)
        assert metrics is not None
        assert isinstance(metrics, list)
        assert len(metrics) > 0

    def test_invalid_string(self):
        assert _extract_metrics_list("not a payload") is None

    def test_invalid_empty_list(self):
        assert _extract_metrics_list([]) is None

    def test_invalid_empty_dict(self):
        assert _extract_metrics_list({}) is None

    def test_invalid_none(self):
        assert _extract_metrics_list(None) is None

    def test_invalid_nested(self):
        assert _extract_metrics_list({"data": "nope"}) is None


# ----------------------------------------------------------------
# _collect_dates
# ----------------------------------------------------------------

class TestCollectDates:
    def test_array_sample_has_multiple_dates(self, array_payload):
        metrics = _extract_metrics_list(array_payload)
        dates = _collect_dates(metrics)
        assert len(dates) > 1
        assert "2026-04-05" in dates

    def test_dict_sample_has_dates(self, dict_payload):
        metrics = _extract_metrics_list(dict_payload)
        dates = _collect_dates(metrics)
        assert len(dates) >= 1

    def test_dates_are_sorted(self, array_payload):
        metrics = _extract_metrics_list(array_payload)
        dates = _collect_dates(metrics)
        assert dates == sorted(dates)

    def test_empty_metrics(self):
        assert _collect_dates([]) == []

    def test_metrics_with_no_data(self):
        metrics = [{"name": "test", "data": []}]
        assert _collect_dates(metrics) == []


# ----------------------------------------------------------------
# _build_day_payload
# ----------------------------------------------------------------

class TestBuildDayPayload:
    def test_list_wrapper_format(self, array_payload):
        metrics = _extract_metrics_list(array_payload)
        payload = _build_day_payload(metrics, "2026-04-05", "list")
        assert isinstance(payload, list)
        assert "data" in payload[0]
        assert "metrics" in payload[0]["data"]

    def test_dict_wrapper_format(self, array_payload):
        metrics = _extract_metrics_list(array_payload)
        payload = _build_day_payload(metrics, "2026-04-05", "dict")
        assert isinstance(payload, dict)
        assert "data" in payload
        assert "metrics" in payload["data"]

    def test_filters_to_target_date_only(self, array_payload):
        metrics = _extract_metrics_list(array_payload)
        payload = _build_day_payload(metrics, "2026-04-05", "dict")
        # Every data entry in the built payload should be for the target date
        for metric in payload["data"]["metrics"]:
            for entry in metric["data"]:
                assert entry["date"].startswith("2026-04-05")

    def test_nonexistent_date_returns_empty_metrics(self, array_payload):
        metrics = _extract_metrics_list(array_payload)
        payload = _build_day_payload(metrics, "1999-01-01", "dict")
        assert payload["data"]["metrics"] == []

    def test_built_payload_normalizes_correctly(self, array_payload):
        """A built per-day payload should produce a valid normalized record."""
        from normalize import normalize

        metrics = _extract_metrics_list(array_payload)
        payload = _build_day_payload(metrics, "2026-04-05", "list")
        record = normalize(payload, target_date="2026-04-05")
        assert record["date"] == "2026-04-05"
        assert record["hrv_sdnn_ms"] is not None
        assert record["source_tags"] == ["Apple Health"]


# ----------------------------------------------------------------
# run_backfill — dry run
# ----------------------------------------------------------------

class TestRunBackfillDryRun:
    def test_dry_run_does_not_call_notion(self, tmp_path, array_payload):
        """Dry run should process dates but never call notion_writer.write."""
        export_file = tmp_path / "export.json"
        export_file.write_text(json.dumps(array_payload))

        with patch("backfill.notion_write") as mock_write:
            summary = run_backfill(str(export_file), dry_run=True)

        mock_write.assert_not_called()
        assert summary["written"] > 0
        assert summary["skipped"] == 0
        assert summary["errors"] == 0

    def test_dry_run_with_dict_format(self, tmp_path, dict_payload):
        export_file = tmp_path / "export.json"
        export_file.write_text(json.dumps(dict_payload))

        with patch("backfill.notion_write") as mock_write:
            summary = run_backfill(str(export_file), dry_run=True)

        mock_write.assert_not_called()
        assert summary["written"] > 0


# ----------------------------------------------------------------
# run_backfill — with mocked Notion writes
# ----------------------------------------------------------------

class TestRunBackfillMocked:
    def test_written_status(self, tmp_path, array_payload):
        export_file = tmp_path / "export.json"
        export_file.write_text(json.dumps(array_payload))

        mock_result = {"status": "written", "date": "2026-04-05", "page_id": "abc", "message": "ok"}
        with patch("backfill.notion_write", return_value=mock_result) as mock_write, \
             patch("backfill.time.sleep"):
            summary = run_backfill(str(export_file), dry_run=False)

        assert mock_write.call_count > 0
        assert summary["written"] > 0

    def test_skipped_duplicates(self, tmp_path, array_payload):
        export_file = tmp_path / "export.json"
        export_file.write_text(json.dumps(array_payload))

        mock_result = {"status": "skipped", "date": "x", "page_id": "abc", "message": "dup"}
        with patch("backfill.notion_write", return_value=mock_result), \
             patch("backfill.time.sleep"):
            summary = run_backfill(str(export_file), dry_run=False)

        assert summary["skipped"] > 0
        assert summary["written"] == 0

    def test_error_handling_continues(self, tmp_path, array_payload):
        """If notion_write returns error for one date, processing continues."""
        export_file = tmp_path / "export.json"
        export_file.write_text(json.dumps(array_payload))

        mock_result = {"status": "error", "date": "x", "page_id": None, "message": "fail"}
        with patch("backfill.notion_write", return_value=mock_result), \
             patch("backfill.time.sleep"):
            summary = run_backfill(str(export_file), dry_run=False)

        assert summary["errors"] > 0

    def test_exception_handling_continues(self, tmp_path, array_payload):
        """If notion_write raises, processing continues to next date."""
        export_file = tmp_path / "export.json"
        export_file.write_text(json.dumps(array_payload))

        with patch("backfill.notion_write", side_effect=Exception("boom")), \
             patch("backfill.time.sleep"):
            summary = run_backfill(str(export_file), dry_run=False)

        assert summary["errors"] > 0

    def test_source_tags_overridden(self, tmp_path, array_payload):
        """Backfilled records should have source_tags=["backfill_json"]."""
        export_file = tmp_path / "export.json"
        export_file.write_text(json.dumps(array_payload))

        records_written = []

        def capture_write(record):
            records_written.append(record.copy())
            return {"status": "written", "date": record["date"], "page_id": "x", "message": "ok"}

        with patch("backfill.notion_write", side_effect=capture_write), \
             patch("backfill.time.sleep"):
            run_backfill(str(export_file), dry_run=False)

        assert len(records_written) > 0
        for rec in records_written:
            assert rec["source_tags"] == ["backfill_json"]

    def test_rate_limiting_called(self, tmp_path, array_payload):
        """time.sleep(0.35) should be called between writes."""
        export_file = tmp_path / "export.json"
        export_file.write_text(json.dumps(array_payload))

        mock_result = {"status": "written", "date": "x", "page_id": "abc", "message": "ok"}
        with patch("backfill.notion_write", return_value=mock_result), \
             patch("backfill.time.sleep") as mock_sleep:
            summary = run_backfill(str(export_file), dry_run=False)

        # sleep should be called between writes (N-1 times for N dates)
        if summary["written"] > 1:
            assert mock_sleep.call_count >= summary["written"] - 1
            mock_sleep.assert_called_with(0.35)


# ----------------------------------------------------------------
# run_backfill — error cases
# ----------------------------------------------------------------

class TestRunBackfillErrors:
    def test_missing_file(self):
        summary = run_backfill("/nonexistent/path.json")
        assert summary["errors"] == 1

    def test_invalid_json(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json at all")
        summary = run_backfill(str(bad_file))
        assert summary["errors"] == 1

    def test_unrecognized_structure(self, tmp_path):
        weird_file = tmp_path / "weird.json"
        weird_file.write_text(json.dumps({"unexpected": "format"}))
        summary = run_backfill(str(weird_file))
        assert summary["errors"] == 1

    def test_empty_array(self, tmp_path):
        """An empty array should be treated as unrecognized."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("[]")
        summary = run_backfill(str(empty_file))
        assert summary["errors"] == 1
