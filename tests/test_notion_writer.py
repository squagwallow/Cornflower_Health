"""
Live integration tests for src/notion_writer.py
Hits the real Notion database — requires NOTION_TOKEN env var.

Run: pytest tests/test_notion_writer.py -v -s

Tests:
  1. write() creates a new Notion page for the April 5 sample date
  2. write() skips a duplicate (idempotency)
  3. Spot-checks that key fields landed in Notion correctly

Uses a unique test date (2099-01-01) so it never collides with real data.
Cleans up the test page after the run.
"""

import json
import os
import sys
import time
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from normalize import normalize
from notion_writer import (
    NOTION_BASE,
    NOTION_DATABASE_ID,
    NOTION_VERSION,
    _headers,
    _query_existing,
    write,
)

SAMPLE_PATH = Path(__file__).parent.parent / "samples" / "hae_sample_2026-04-05.json"

# Use a sentinel date that will never appear in real data
TEST_DATE = "2099-01-01"


def _delete_page(page_id: str) -> None:
    """Archive (soft-delete) a Notion page by ID."""
    url = f"{NOTION_BASE}/pages/{page_id}"
    with httpx.Client(timeout=15.0) as client:
        client.patch(url, headers=_headers(), json={"archived": True})


@pytest.fixture(scope="module")
def raw_payload():
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def test_record(raw_payload):
    """Normalize the April 5 payload but override the date to the sentinel."""
    rec = normalize(raw_payload, target_date="2026-04-05")
    rec["date"] = TEST_DATE  # Override so we write to a throwaway date
    return rec


@pytest.fixture(scope="module")
def created_page_id(test_record):
    """Write the test record once; yield the page_id; clean up after all tests."""
    result = write(test_record)
    assert result["status"] == "written", f"Expected 'written', got: {result}"
    page_id = result["page_id"]
    yield page_id
    # Teardown: archive the test page
    _delete_page(page_id)


# ----------------------------------------------------------------
# Test 1: page is created
# ----------------------------------------------------------------

def test_write_returns_written_status(created_page_id):
    assert created_page_id is not None
    assert len(created_page_id) > 0


# ----------------------------------------------------------------
# Test 2: idempotency — second write must be skipped
# ----------------------------------------------------------------

def test_duplicate_write_is_skipped(test_record):
    result = write(test_record)
    assert result["status"] == "skipped", f"Expected 'skipped', got: {result}"
    assert "Duplicate skipped" in result["message"]


# ----------------------------------------------------------------
# Test 3: spot-check field values in the created Notion page
# ----------------------------------------------------------------

def test_page_fields_in_notion(created_page_id, test_record):
    """Fetch the created page and verify key numeric fields match."""
    url = f"{NOTION_BASE}/pages/{created_page_id}"
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(url, headers=_headers())
    assert resp.status_code == 200, f"Could not fetch page: {resp.text}"

    props = resp.json()["properties"]

    # Date
    assert props["date"]["date"]["start"] == TEST_DATE

    # hrv_sdnn_ms
    hrv = props.get("hrv_sdnn_ms", {}).get("number")
    assert hrv is not None
    assert abs(hrv - test_record["hrv_sdnn_ms"]) < 0.01

    # rhr_bpm
    rhr = props.get("rhr_bpm", {}).get("number")
    assert rhr == pytest.approx(67.5, abs=0.01)

    # sleep_deep_min
    deep = props.get("sleep_deep_min", {}).get("number")
    assert deep == 29

    # sleep_time_asleep_min
    asleep = props.get("sleep_time_asleep_min", {}).get("number")
    assert asleep == 392

    # spo2_avg_pct — must not have been multiplied by 100
    spo2 = props.get("spo2_avg_pct", {}).get("number")
    assert spo2 == pytest.approx(92.6, abs=0.01)
    assert spo2 < 100

    # source_tags
    tags = [t["name"] for t in props.get("source_tags", {}).get("multi_select", [])]
    assert "Apple Health" in tags

    # sleep_bedtime stored as rich text
    bedtime_blocks = props.get("sleep_bedtime", {}).get("rich_text", [])
    if bedtime_blocks:
        assert "2026-04-04" in bedtime_blocks[0]["text"]["content"]
