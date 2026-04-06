# Architecture Plan

This document describes the current and planned system architecture, compares the Make.com approach to a backend-first approach, and illustrates both the daily ingestion flow and the historical backfill flow.

---

## Approach Comparison

### Option A: Make.com (No-Code Middleware)

```
HAE webhook → Make.com scenario → Notion API
```

**How it was attempted:**
- HAE configured to send daily webhook POST to a Make.com webhook URL
- Make scenario responsible for parsing nested JSON, mapping fields, and writing to Notion via the Notion module

**Why it was rejected:**

| Problem | Detail |
|---|---|
| Nested JSON parsing | Make's JSON parser requires manual iterator configuration for arrays; HAE sleep analysis has nested sub-arrays that were difficult to traverse reliably |
| Brittle syntax | Make's expression language produced syntax errors that were time-consuming to debug in the UI |
| Silent failure risk | If HAE changes a field name or nesting level, the Make scenario fails silently or writes null without alerting |
| No version control | Make scenarios cannot be version-controlled in Git; changes are opaque |
| Context loss | AI-assisted debugging sessions lost context between threads, requiring repeated re-explanation of the payload structure |
| Limited logic | Conditional field handling (metrics absent on some days), deduplication, and error logging are awkward to implement in Make |

**Conclusion:** Make.com is suitable for simple, flat payloads with low complexity. It is not suitable for this project's nested payload structure, deduplication requirements, and long-term maintainability needs.

---

### Option B: Backend-First (Recommended)

```
HAE webhook → Backend endpoint → Normalize + validate → Notion API
```

**Why it is preferred:**

| Benefit | Detail |
|---|---|
| Full control over parsing | Any JSON structure can be handled in code, including nested arrays and optional fields |
| Version-controlled logic | The normalization code lives in Git alongside this documentation |
| Explicit error handling | Missing fields, malformed payloads, and Notion API failures can be caught and logged |
| Idempotency | The backend can check for an existing Notion row for a given date before writing |
| Testable | Unit tests can be written against real payload samples saved in `samples/` |
| AI-thread compatible | Future AI threads can read the code and documentation in this repo rather than reverse-engineering a Make scenario |

**Assumption:** The backend can be a minimal HTTP server (e.g., Python/FastAPI, Node.js/Express, or a serverless function). It does not need to be complex.

---

## Daily Ingestion Flow

```
[Apple Watch]
    │  (syncs throughout day)
    ▼
[iPhone — Apple Health]
    │
    ▼
[Health Auto Export app]
    │  Scheduled daily export (e.g., 08:00 local time)
    │  HTTP POST → backend webhook URL
    ▼
[Backend — /webhook endpoint]
    │  1. Receive and log raw payload
    │  2. Extract health_date (from sleepEnd or device timestamp)
    │  3. Check Notion: does a row for this date already exist?
    │     ├── Yes → Update or skip (configurable)
    │     └── No  → Continue
    │  4. Normalize fields (HAE names → internal names)
    │  5. Apply unit conversions if needed (SpO2 decimal → percent, etc.)
    │  6. Build Notion page payload
    │  7. Write to Notion database
    │  8. Log result (success / field-level errors)
    ▼
[Notion database — one row per day]
```

---

## Historical Backfill Flow

See [`backfill-plan.md`](backfill-plan.md) for full detail.

```
[iPhone — Apple Health]
    │  (6+ months of historical data)
    │  Export via Health Auto Export: CSV or JSON
    ▼
[Local file(s) on development machine]
    │
    ▼
[Backfill script]
    │  1. Read records in chronological order (oldest first)
    │  2. For each record:
    │     a. Normalize fields (same logic as live pipeline)
    │     b. Set source_tags = "backfill_csv" (or "backfill_json")
    │     c. Check Notion: row for this date exists?
    │        ├── Yes → Skip (do not overwrite live data)
    │        └── No  → Write row
    │  3. Rate-limit writes (e.g., 1–3 req/sec) to avoid Notion API limits
    │  4. Log every write, skip, and error
    ▼
[Notion database — backfilled historical rows]
```

---

## Backend Hosting Options

> **Assumption:** No hosting decision has been made yet. The following options are listed for consideration.

| Option | Pros | Cons |
|---|---|---|
| Local (Mac/Python) | Zero cost; easy to debug | Requires machine to be on and reachable; no uptime guarantee |
| Serverless function (Vercel, Netlify, Cloudflare Workers) | Low cost; always available; easy deploy | Cold starts; limited execution time for complex logic |
| Lightweight cloud VM (Railway, Fly.io, Render) | Always-on; full control; easy to scale | Small monthly cost; slightly more setup |
| Self-hosted VPS | Full control; lowest long-term cost | Setup overhead; you manage uptime |

For v1, a serverless function (e.g., a Vercel or Railway deployment of a Python/FastAPI endpoint) is a reasonable default. The backend logic should be minimal enough to fit within serverless constraints.

---

## Security Considerations

- The webhook endpoint should require a shared secret token in the request header (set in HAE and validated in the backend).
- Never commit secrets, tokens, or private Notion integration keys to this repository.
- Use environment variables for all credentials.
- Store a `.env.example` file (with placeholder values) to document required environment variables.

---

*Last updated: 2026-04-06*
