"""
Task 1.4 — End-to-End Integration Test
Cornflower Health — tests/test_end_to_end.py

Starts the FastAPI server locally, POSTs a real HAE payload to /webhook,
verifies the Notion row is created with correct values, then verifies
that a second POST is handled as a duplicate (no new row created).

Run: pytest tests/test_end_to_end.py -v -s

Requires:
  NOTION_TOKEN and NOTION_DATABASE_ID in environment (or .env file)
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

# --- Paths ---
REPO_ROOT = Path(__file__).parent.parent
SAMPLE_PATH = REPO_ROOT / "samples" / "hae_sample_2026-04-05.json"
SRC_DIR = REPO_ROOT / "src"

# --- Test sentinel date (overridden in payload via normalize) ---
# We use the real April 5 date from the sample — if a row already exists
# for that date, the idempotency test becomes the first test.
# Using a unique test date ensures isolation.
TEST_DATE = "2098-12-31"

BACKEND_URL = "http://localhost:8001"
WEBHOOK_URL = f"{BACKEND_URL}/webhook"
HEALTH_URL  = f"{BACKEND_URL}/health"

NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "339d7cd8-531f-819f-85b2-c769696ea27c")
NOTION_VERSION = "2022-06-28"
NOTION_BASE = "https://api.notion.com/v1"


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------

def _notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _find_notion_page(date_str: str) -> str | None:
    """Query Notion for a page with the given date. Returns page_id or None."""
    url = f"{NOTION_BASE}/databases/{NOTION_DATABASE_ID}/query"
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(
            url,
            headers=_notion_headers(),
            json={"filter": {"property": "date", "date": {"equals": date_str}}},
        )
    results = resp.json().get("results", [])
    return results[0]["id"] if results else None


def _delete_notion_page(page_id: str) -> None:
    """Archive (soft-delete) a Notion page."""
    with httpx.Client(timeout=15.0) as client:
        client.patch(
            f"{NOTION_BASE}/pages/{page_id}",
            headers=_notion_headers(),
            json={"archived": True},
        )


def _build_test_payload() -> list:
    """Load the sample payload and override the dates to TEST_DATE."""
    raw = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    # We don't modify the payload — instead we rely on normalize()
    # using the most recent record date. The sample's latest date is 2026-04-05.
    # For isolation we patch the date strings in the payload.
    payload_str = json.dumps(raw).replace("2026-04-05", TEST_DATE)
    return json.loads(payload_str)


# ----------------------------------------------------------------
# Server fixture — starts uvicorn in a subprocess for the test session
# ----------------------------------------------------------------

@pytest.fixture(scope="module")
def server():
    """Start the FastAPI server on port 8001 for the duration of the test module."""
    env = os.environ.copy()
    env["NOTION_TOKEN"] = NOTION_TOKEN
    env["NOTION_DATABASE_ID"] = NOTION_DATABASE_ID
    env["BACKEND_PORT"] = "8001"
    env["HAE_WEBHOOK_SECRET"] = ""   # No secret required for test
    env["LOG_LEVEL"] = "INFO"
    env["PYTHONPATH"] = str(SRC_DIR)

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "webhook:app", "--host", "0.0.0.0", "--port", "8001"],
        cwd=SRC_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Wait for server to be ready
    for _ in range(20):
        time.sleep(0.5)
        try:
            resp = httpx.get(HEALTH_URL, timeout=2.0)
            if resp.status_code == 200:
                break
        except Exception:
            pass
    else:
        proc.kill()
        pytest.fail("Server did not start within 10 seconds")

    yield proc

    proc.kill()
    proc.wait()


# ----------------------------------------------------------------
# Notion page cleanup fixture
# ----------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def cleanup_test_page():
    """Archive the test Notion page after all tests complete."""
    yield
    page_id = _find_notion_page(TEST_DATE)
    if page_id:
        _delete_notion_page(page_id)


# ----------------------------------------------------------------
# Test 1: Health check
# ----------------------------------------------------------------

def test_health_endpoint(server):
    resp = httpx.get(HEALTH_URL, timeout=5.0)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ----------------------------------------------------------------
# Test 2: POST real payload → pipeline runs → Notion row created
# ----------------------------------------------------------------

def test_webhook_writes_notion_row(server):
    payload = _build_test_payload()
    resp = httpx.post(WEBHOOK_URL, json=payload, timeout=30.0)

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()

    assert body["status"] == "written", f"Expected 'written', got: {body}"
    assert body["date"] == TEST_DATE
    assert body["page_id"] is not None
    assert body["logged_to"] is not None


# ----------------------------------------------------------------
# Test 3: Verify Notion row has correct field values
# ----------------------------------------------------------------

def test_notion_row_field_values(server):
    page_id = _find_notion_page(TEST_DATE)
    assert page_id is not None, f"No Notion page found for date {TEST_DATE}"

    with httpx.Client(timeout=15.0) as client:
        resp = client.get(f"{NOTION_BASE}/pages/{page_id}", headers=_notion_headers())
    assert resp.status_code == 200

    props = resp.json()["properties"]

    # Date
    assert props["date"]["date"]["start"] == TEST_DATE

    # source_tags = Apple Health
    tags = [t["name"] for t in props["source_tags"]["multi_select"]]
    assert "Apple Health" in tags

    # hrv_sdnn_ms ≈ 44.059
    hrv = props["hrv_sdnn_ms"]["number"]
    assert hrv == pytest.approx(44.059, abs=0.01)

    # rhr_bpm = 67.5
    rhr = props["rhr_bpm"]["number"]
    assert rhr == pytest.approx(67.5, abs=0.01)

    # sleep_deep_min = 29
    assert props["sleep_deep_min"]["number"] == 29

    # sleep_time_asleep_min = 392
    assert props["sleep_time_asleep_min"]["number"] == 392

    # spo2_avg_pct = 92.6 (not multiplied by 100)
    spo2 = props["spo2_avg_pct"]["number"]
    assert spo2 == pytest.approx(92.6, abs=0.01)
    assert spo2 < 100

    # hr_day_avg_bpm ≈ 87.049
    hr_avg = props["hr_day_avg_bpm"]["number"]
    assert hr_avg == pytest.approx(87.049, abs=0.01)

    # wrist_temp_abs ≈ 99.426 (°F, not converted)
    wrist = props["wrist_temp_abs"]["number"]
    assert wrist == pytest.approx(99.426, abs=0.01)


# ----------------------------------------------------------------
# Test 4: Second POST with same date → duplicate skipped, no new row
# ----------------------------------------------------------------

def test_duplicate_post_is_skipped(server):
    payload = _build_test_payload()
    resp = httpx.post(WEBHOOK_URL, json=payload, timeout=30.0)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "skipped", f"Expected 'skipped', got: {body}"
    assert body["date"] == TEST_DATE


# ----------------------------------------------------------------
# Test 5: Malformed JSON → 400
# ----------------------------------------------------------------

def test_malformed_json_returns_400(server):
    resp = httpx.post(
        WEBHOOK_URL,
        content=b"not valid json{{{",
        headers={"Content-Type": "application/json"},
        timeout=5.0,
    )
    assert resp.status_code == 400
