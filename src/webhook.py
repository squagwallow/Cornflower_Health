"""
Task 1.1 + 1.4 — Webhook Endpoint with Full Pipeline
Cornflower Health project — src/webhook.py

Accepts HAE POST payloads, validates the shared secret, logs raw JSON to logs/,
normalizes the payload, writes to Notion, and returns the outcome.

Pipeline: POST /webhook → validate → log → normalize() → notion_writer.write()
"""

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

    # --- Auth: accept Bearer token OR X-Webhook-Secret header ---
    auth_header = request.headers.get("Authorization", "")
    secret_header = request.headers.get("X-Webhook-Secret", "")

    provided_secret = ""
    if auth_header.startswith("Bearer "):
        provided_secret = auth_header.removeprefix("Bearer ").strip()
    elif secret_header:
        provided_secret = secret_header.strip()

    if HAE_WEBHOOK_SECRET and provided_secret != HAE_WEBHOOK_SECRET:
        logger.warning("Rejected request — invalid or missing webhook secret")
        raise HTTPException(status_code=401, detail="Unauthorized")

    # --- Parse body ---
    try:
        raw_body = await request.body()
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
    if result["status"] in ("written", "skipped"):
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
    """Simple liveness check."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("webhook:app", host="0.0.0.0", port=BACKEND_PORT, reload=False)
