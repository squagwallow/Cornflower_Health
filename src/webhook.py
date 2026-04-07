"""
Task 1.1 + 1.4 — Webhook Endpoint with Full Pipeline
Cornflower Health project — src/webhook.py

Accepts HAE POST payloads, validates the shared secret, logs raw JSON to logs/,
normalizes the payload, writes to Notion, and returns the outcome.

Pipeline: POST /webhook → validate → log → normalize() → notion_writer.write()
"""

import hashlib
import hmac
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response

from normalize import normalize
import notion_writer

load_dotenv()

# --- Config from environment ---
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")
HAE_WEBHOOK_SECRET = os.getenv("HAE_WEBHOOK_SECRET", "")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# --- Logging setup ---
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("cornflower.webhook")

# --- Ensure logs directory exists ---
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Cornflower Health Webhook")


@app.post("/webhook")
async def receive_webhook(request: Request) -> Response:
    """
    Main HAE webhook endpoint.

    1. Validates the shared secret from the Authorization or X-Webhook-Secret header.
    2. Reads and validates the JSON body.
    3. Logs the raw payload to a timestamped file in logs/.
    4. Returns 200 {"status": "received"}.
    """

    # --- Auth: HMAC-SHA256 signature OR bearer token fallback ---
    #
    # Preferred (HAE HMAC mode): HAE signs the raw body with the shared secret
    # and sends the hex digest in X-HAE-Signature header. We verify with
    # hmac.compare_digest to prevent timing attacks.
    #
    # Fallback (simple bearer): accept the secret directly as a bearer token
    # or X-Webhook-Secret header (original behaviour, kept for compatibility).
    raw_body = await request.body()

    sig_header = request.headers.get("X-HAE-Signature", "")
    auth_header = request.headers.get("Authorization", "")
    secret_header = request.headers.get("X-Webhook-Secret", "")

    if HAE_WEBHOOK_SECRET:
        if sig_header:
            # HMAC-SHA256 path
            expected = hmac.new(
                HAE_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(sig_header, expected):
                logger.warning("Rejected request — HMAC signature mismatch")
                raise HTTPException(status_code=401, detail="Unauthorized")
        else:
            # Bearer / secret header fallback
            provided_secret = ""
            if auth_header.startswith("Bearer "):
                provided_secret = auth_header.removeprefix("Bearer ").strip()
            elif secret_header:
                provided_secret = secret_header.strip()
            if not hmac.compare_digest(provided_secret, HAE_WEBHOOK_SECRET):
                logger.warning("Rejected request — invalid or missing webhook secret")
                raise HTTPException(status_code=401, detail="Unauthorized")

    # --- Parse body (raw_body already read above for auth) ---
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        logger.error("Malformed JSON received: %s", exc)
        raise HTTPException(status_code=400, detail=f"Malformed JSON: {exc}") from exc

    # --- Log raw payload to timestamped file ---
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = LOGS_DIR / f"payload_{ts}.json"
    try:
        log_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Payload logged to %s", log_path)
    except OSError as exc:
        logger.error("Failed to write payload log: %s", exc)
        # Non-fatal — pipeline continues

    # --- Normalize ---
    try:
        record = normalize(payload)
    except Exception as exc:
        logger.error("Normalization failed: %s", exc)
        raise HTTPException(status_code=422, detail=f"Normalization error: {exc}") from exc

    if not record:
        logger.error("Normalization returned empty record — payload may be malformed")
        raise HTTPException(status_code=422, detail="Normalization returned empty record")

    # --- Write to Notion ---
    result = notion_writer.write(record)

    status_code = 200
    if result["status"] == "error":
        # Still return 200 to prevent HAE from retrying — the error is logged
        logger.error("Notion write failed for %s: %s", result.get("date"), result.get("message"))

    # --- Auto-update dashboard in background ---
    # After a successful write, trigger update_dashboard.py so the
    # Daily Dashboard page reflects the new data without any manual step.
    if result["status"] in ("written", "updated", "skipped"):
        date_str = result.get("date")
        def _bg_dashboard_update(d: str) -> None:
            try:
                from update_dashboard import run_update
                logger.info("Background dashboard update starting for %s", d)
                run_update(date_str=d, dry_run=False)
                logger.info("Background dashboard update complete for %s", d)
            except Exception as exc:
                logger.error("Background dashboard update failed for %s: %s", d, exc)
        threading.Thread(target=_bg_dashboard_update, args=(date_str,), daemon=True).start()

    response_body = {
        "status": result["status"],       # "written" | "skipped" | "error"
        "date": result.get("date"),
        "page_id": result.get("page_id"),
        "logged_to": str(log_path),
    }

    logger.info("Pipeline complete — %s", result.get("message"))
    return Response(
        content=json.dumps(response_body),
        media_type="application/json",
        status_code=status_code,
    )


@app.get("/health")
async def health() -> dict:
    """Simple liveness check used by Render health monitoring and keep-warm pings."""
    return {"status": "ok"}


@app.get("/check-gaps")
async def check_gaps() -> dict:
    """
    Scan the last 7 days in the Notion database and return any dates with missing rows.
    Call this from a scheduler or manually to identify days that need backfill.

    Returns JSON: {"missing_dates": ["2026-04-05", ...], "checked_range": "..."}
    """
    import httpx as _httpx
    from datetime import date, timedelta

    today = date.today()
    window = [today - timedelta(days=i) for i in range(7)]
    date_strs = {d.isoformat() for d in window}

    notion_token = os.getenv("NOTION_TOKEN", "")
    notion_db = os.getenv("NOTION_DATABASE_ID", "339d7cd8-531f-819f-85b2-c769696ea27c")
    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    found: set[str] = set()
    try:
        with _httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"https://api.notion.com/v1/databases/{notion_db}/query",
                headers=headers,
                json={
                    "filter": {
                        "and": [
                            {"property": "date", "date": {"on_or_after": min(date_strs)}},
                            {"property": "date", "date": {"on_or_before": max(date_strs)}},
                        ]
                    }
                },
            )
            resp.raise_for_status()
            for row in resp.json().get("results", []):
                d = row["properties"].get("date", {}).get("date", {}) or {}
                if d.get("start"):
                    found.add(d["start"])
    except Exception as exc:
        logger.error("check-gaps query failed: %s", exc)
        return {"error": str(exc)}

    missing = sorted(date_strs - found)
    logger.info("Gap check: missing=%s", missing or "none")
    return {
        "missing_dates": missing,
        "found_dates": sorted(found),
        "checked_range": f"{min(date_strs)} to {max(date_strs)}",
        "note": "For any missing date, open HAE, set the export date range to include it, and sync.",
    }


@app.get("/ping")
async def ping() -> dict:
    """
    Keep-warm endpoint. Hit this every 10 minutes from an external scheduler
    (e.g., cron-job.org free tier, UptimeRobot) to prevent Render free-tier
    cold-start latency from dropping HAE webhook payloads.
    URL: https://cornflower-health.onrender.com/ping
    """
    return {"status": "alive"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("webhook:app", host="0.0.0.0", port=BACKEND_PORT, reload=False)
