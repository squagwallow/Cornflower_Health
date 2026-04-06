<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Thread Report

## 1. Thread scope

- Explore how to use AI models for daily health check‑ins based on Athlytic/Apple Watch data and screenshots.
- Evaluate whether local vision models, Perplexity Health, and different prompting strategies could support an Apple Health → Notion–style automation and “Athlytic‑mimic” health coach.
- Clarify how Perplexity modes (Ask vs Deep research) and “reasoning” relate to this workflow.


## 2. Confirmed facts

- The user wants a daily health‑coach‑style workflow that interprets Athlytic or Apple Watch data and supports day‑to‑day decisions.
- The user currently has Pro accounts on both Perplexity and Claude and is considering canceling one.
- The user’s core daily data sources include Athlytic screenshots and Apple Watch data via Apple Health.
- Perplexity has:
    - A standard “Ask” mode.
    - A “Deep research” mode that performs heavier, multi‑step research for a query.
- The user’s Perplexity UI does not expose any explicit “reasoning mode” toggle.
- Perplexity Health can connect to Apple Health and other wearables, and can use that data to answer personalized health questions, but it does not reproduce Athlytic’s proprietary algorithms.
- Athlytic uses Apple Health data (including HRV, resting HR, sleep, exertion) and computes proprietary recovery and exertion/strain scores on a 0–100 style scale.


## 3. Attempts made

- Conceptual design of a **two‑tier AI setup**:
    - A lightweight, cheap model for routine logging and reflections.
    - A stronger multimodal model for occasional deep, evidence‑informed decisions.
- Discussion of a **local vision AI + database**:
    - Desktop: local vision model watches a folder of screenshots, extracts text/metrics, and writes into a local DB (e.g., SQLite/notes).
    - Phone: acknowledge that fully local vision is much harder; likely need to sync to desktop or use cloud.
- Evaluation of **Perplexity Health** as a potential replacement/augmenter for Athlytic:
    - Use Apple Health integration so the AI can read similar raw metrics.
    - Let it act as an evidence‑aware explainer/coach on top of those metrics.
- Proposal of an **Athlytic‑mimic system prompt** that:
    - Accepts HRV, HRV baseline, RHR, RHR baseline, exertion, sleep, and notes.
    - Produces: recovery score 0–100, recovery zone (red/yellow/green), exertion recommendation, coaching suggestions, and watch‑outs.
- Suggestion to use **Deep research** to:
    - Research how recovery scores are usually constructed.
    - Help design scoring formulas and refine the long system prompt.
- Discussion of **self‑refinement / self‑testing**:
    - Having an AI agent iteratively critique and rewrite the Athlytic‑mimic prompt, potentially via an automated loop.
    - A more modest version: test the prompt on 5–10 real days of data and ask the model to critique its own behavior.


## 4. What failed or proved fragile

- **Local vision on phone**:
    - Recognized as technically possible but practically fragile/annoying (difficult deployment, niche tooling, friction versus benefit).
- **Local vision for screenshots as main cost saver**:
    - Identified as likely unnecessary since a few daily screenshots are not the main driver of Pro‑plan resource usage.
- **User understanding of “reasoning mode”**:
    - Initial instructions assumed a visible reasoning toggle; the user does not see such a control, so that guidance was misleading in their specific UI context.


## 5. What appeared to work

- Framing **Ask vs Deep research**:
    - Ask for day‑to‑day prompt iteration and daily check‑ins.
    - Deep research for occasional heavier design/research tasks.
- The **starter Athlytic‑mimic prompt**:
    - Provides a concrete, reusable template the user can paste into an AI system to generate structured daily outputs.
- Conceptual role of **Perplexity Health**:
    - Treat it as a data‑aware, evidence‑referencing coach that interprets Apple Health data, not as a drop‑in replacement for Athlytic’s algorithm.
- Clarifying that the user does *not* need to manage hidden reasoning settings; using strong models plus Deep research is sufficient in their plan.


## 6. Recommendations made in this thread

- Use a **hybrid model approach**:
    - Cheap model for routine logging; strong multimodal model for interpretation and evidence‑based decisions.
    - Status: **Still plausible** (general pattern; not tied to a specific vendor).
- Avoid over‑investing in **local vision** for 4 screenshots/day; keep cloud multimodal for that small workload and focus savings on limiting heavy research tasks.
    - Status: **Still plausible** for current usage levels.
- Use **Perplexity Health** as an explainer/coach on top of Apple Health data, not a replacement for Athlytic; keep Athlytic for its proprietary readiness scores.
    - Status: **Still plausible**, but **implementation details may evolve** with future product changes.
- Build an **Athlytic‑mimic system prompt** that:
    - Approximates recovery scores, classifies zones, and generates behavioral suggestions while explicitly *not* claiming to replicate Athlytic’s proprietary algorithm.
    - Status: **Still plausible**.
- Use **Deep research** selectively to design and refine the prompt and scoring logic; use standard Ask for everyday use to conserve credits.
    - Status: **Still plausible**.
- Use **self‑refinement** in a *lightweight* way (model critiques its own prompt after running on real data) rather than a full automatic prompt‑optimization loop.
    - Status: **Still plausible**.
- Advice about explicit **“reasoning mode” toggles** and per‑thread reasoning settings.
    - Status: **Superseded by later direction / Unclear**, given the user’s UI does not expose such toggles.


## 7. Artifacts worth preserving

- **Athlytic‑mimic starter prompt structure** (paraphrased, not full text):
    - Role: cautious, evidence‑informed training‑readiness coach.
    - Inputs: today’s HRV, 60‑day HRV baseline, today’s RHR, RHR baseline, yesterday’s exertion/strain, sleep duration/quality, notes on illness/stress.
    - Steps:

1. Extract data and explicitly mark missing values.
2. Compute a transparent, approximate 0–100 recovery score driven primarily by HRV vs baseline, secondarily by RHR vs baseline; conservative if conflicting/illness.
3. Map score to zones: 0–33 red (recover), 34–66 yellow (modify), 67–100 green (push).
4. Recommend today’s exertion range (low/moderate/high) with rationale.
5. Provide 3–5 specific behavioral suggestions.
6. Flag multi‑day negative trends and suggest medical consultation if persistent.
7. Keep response under ~250 words with a fixed section order (data summary, recovery, exertion recommendation, suggestions, watch‑outs).
- **Architecture concept**:
    - Apple Health / Athlytic data → AI “coach” layer → structured summary and recommendations → (implied next step) storage in Notion or similar.
- **Design principle**:
    - Separate “score engine” (Athlytic) from “interpretation/coach engine” (LLM with prompt) to avoid trying to reverse‑engineer proprietary algorithms.


## 8. Open questions left unresolved

- Exact formulas or numerical mapping from HRV/RHR deviations to the 0–100 recovery score in the Athlytic‑mimic prompt.
- How to persist the AI’s daily outputs into Notion (fields, schema, automation tools).
- Whether Perplexity Health’s Apple Health integration, as implemented today, exposes enough granularity and history to fully replace screenshots for this project.
- Concrete decision criteria for which Pro subscription (Perplexity vs Claude) the user will keep, based on real usage metrics.
- Whether more automated prompt‑optimization (multi‑variant testing, scoring) would materially improve outcomes for this single‑user workflow.


## 9. Usefulness score

- **Score: 4/5**
- Reason: The thread surfaces a clear conceptual architecture, an actionable starter prompt, and realistic constraints around local vs cloud processing and Perplexity modes. It does not yet specify exact formulas, Notion schemas, or end‑to‑end automation details, so it’s strong on framing and weaker on implementation specifics.


## 10. Repo-ready summary

This thread documents early design work for an AI‑assisted “training readiness coach” layered on top of Apple Health and Athlytic data. It clarifies that Athlytic’s proprietary recovery/exertion algorithms should be treated as the scoring engine, while an LLM (via Perplexity/Claude) acts as a separate interpretation and coaching layer driven by a structured system prompt. The discussion rejects heavy local‑vision setups as overkill for a few daily screenshots, recommends using Perplexity’s Ask for everyday prompts and Deep research for occasional design work, and introduces a reusable Athlytic‑mimic prompt pattern that outputs a 0–100 recovery score, zone classification, exertion recommendation, and behavioral suggestions. Several implementation details (exact formulas, Notion schema, and long‑term tool choice) remain open for future threads.

