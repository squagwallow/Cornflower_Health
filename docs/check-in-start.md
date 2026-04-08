# How to Start a Daily Health Check-In

Paste the prompt below at the start of a new session. It tells the LLM exactly where to start and what to do.

---

## Start Prompt (copy and paste this)

```
Start my daily Cornflower Health check-in.

Begin by reading the following files from the Cornflower_Health GitHub repo (https://github.com/squagwallow/Cornflower_Health):
1. docs/coaching-prompt.md — your full instructions and scoring algorithms
2. logs/context/persistent-flags.md — always-active protocol and baseline context
3. logs/context/running-summary.md — recent session history

Then fetch today's row from the Notion Daily Health Metrics database (ID: 339d7cd8-531f-819f-85b2-c769696ea27c) using the Notion connector.

Follow the session steps in coaching-prompt.md exactly. If any critical fields are missing, ask me for Athlytic or Bevel screenshots before delivering the brief.
```

---

## Notes

- Use this prompt in **Cowork** (Claude desktop) with the **Notion connector enabled**.
- The LLM fetches its own instructions from git — you do not need to paste the coaching prompt manually.
- At the end of the session, ask the LLM to write the session close to `logs/context/running-summary.md` and `logs/insights/YYYY-MM-DD.md`, then commit and push.
- If you want to add subjective context before the brief (energy level, notable events, stress), add it after pasting the start prompt on a new line.
