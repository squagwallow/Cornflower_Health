# Agentic Tool Cost & Routing Guidelines

This document instructs any agentic LLM tool working on the Cornflower Health project
on how to classify tasks by credit intensity and route work efficiently.

---

## The Core Rule

**Before starting any task, ask: does this require running code, calling APIs, or
operating the computer? If no — it should not consume agentic credits.**

Agentic tools (Perplexity Computer, Claude Cowork, Claude Code, etc.) are expensive
per task because they use computer-use, multi-step tool calls, and large context windows.
Text-only LLMs (Claude.ai chat, ChatGPT, Gemini) cost a fraction of that for the same
informational output.

---

## Task Classification

### Tier 1 — Agentic Required
*Use Claude Cowork, Perplexity Computer, or similar. These tasks cannot be done without
tool access.*

- Writing or modifying Python files
- Running scripts and interpreting output
- Calling the Notion or GitHub API
- Debugging errors from logs
- Deploying changes to Render
- Reading file contents from a live repo
- Any task that requires sequential tool calls

### Tier 2 — Text LLM (standard chat)
*Route to Claude.ai, ChatGPT, or any conversational LLM. Paste the relevant context.*

- Writing or editing markdown documentation
- Writing handoff briefs when the facts are already known
- Summarizing the project state from pasted doc content
- Reviewing existing code and providing written feedback (no execution needed)
- Designing algorithms or scoring logic on paper before implementation
- Explaining how something works
- Drafting prompts for future agentic sessions

### Tier 3 — Research / User-Paste Tasks
*The user should copy a prompt into a free or low-cost LLM. These are pure knowledge
questions with no project-specific context required.*

- Research questions about third-party tools (e.g., HAE payload format, Notion API behavior)
- Comparing methodologies (e.g., Athlytic vs Bevel HRV approaches)
- Medical/physiological background (e.g., deep sleep norms, HRV interpretation)
- Asking about best practices for a specific technology
- General debugging theory without needing to see the actual code

---

## Instructions for Agentic Tools Starting a New Session

1. **Read this file and the most recent handoff doc before doing anything else.**

2. **Classify each requested task** using the tiers above before beginning.

3. **For any Tier 2 task**, stop and tell the user:
   > "This task (e.g., updating the handoff doc) doesn't require tool use. To save credits,
   > paste the following prompt into a regular Claude or ChatGPT chat: [prompt]"

4. **For any Tier 3 task**, stop and tell the user:
   > "This is a research question that doesn't require project access. Paste this into any
   > free LLM: [prompt]"

5. **Batch all Tier 1 tasks** into a single session where possible. Don't open a new
   agentic session just to make one small file edit.

6. **End every agentic session by:**
   - Writing a new handoff doc (`docs/handoff-YYYY-MM-DD.md`) in the repo
   - Committing and pushing ALL changed files to the `main` branch on GitHub
   - Updating `docs/current-state.md` if the overall project state changed
   - Updating `docs/implementation-backlog.md` if tasks were completed or added

---

## Prompt Templates for Common Tier 2 / Tier 3 Offloads

### Tier 2: Write a handoff doc
```
I am working on the Cornflower Health project, a Python + Notion health dashboard.
Here is what happened in the last session:

[paste session summary]

Please write a concise handoff doc in this format:
- Recent Accomplishments
- Key Design Decisions
- Immediate Next Steps (numbered, prioritized)
- Critical Credentials & References
```

### Tier 3: HRV methodology research
```
Compare the HRV data collection and interpretation philosophies behind the Athlytic
and Bevel iOS health apps. Athlytic appears to weight recent samples heavily and
integrates HRV from mindfulness sessions; Bevel appears to use a tighter distribution
and is less responsive to swings. What are the underlying methodological differences
(e.g., RMSSD vs SDNN, morning vs overnight measurement, sample source)? What are the
tradeoffs of each approach for daily recovery scoring?
```

### Tier 3: Notion API question
```
I am using the Notion API version 2022-06-28 with a Python httpx client.
[describe specific question — e.g., how to create linked database views programmatically]
```

---

## Current Session Cost Reference

| Tool | Relative Cost | Best For |
|------|--------------|----------|
| Claude Cowork (Sonnet) | High | Code, API calls, multi-step tasks |
| Perplexity Computer | High | Code, browser tasks |
| Claude.ai Pro chat | Medium | Docs, design, analysis |
| Claude.ai free / ChatGPT | Low | Research, Q&A, drafting |
| Claude Haiku (API) | Very Low | Bulk text processing |
