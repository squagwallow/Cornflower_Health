"""
Task 1.1 — Webhook Endpoint (Logging Stub)
Cornflower Health project — src/webhook.py

Accepts HAE POST payloads, validates the shared secret, logs raw JSON to logs/,
and returns HTTP 200. No Notion integration in this file (that is Task 1.3+).
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response

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
        # Non-fatal — still return 200 so HAE doesn't retry

    return Response(
        content=json.dumps({"status": "received", "logged_to": str(log_path)}),
        media_type="application/json",
        status_code=200,
    )


@app.get("/health")
async def health() -> dict:
    """Simple liveness check."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("webhook:app", host="0.0.0.0", port=BACKEND_PORT, reload=False)
