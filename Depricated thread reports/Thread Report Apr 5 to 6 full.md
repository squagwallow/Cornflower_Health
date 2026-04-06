<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Thread Report

## 1. Thread scope

This thread was trying to solve: **How to build a complete, accurate, operational setup guide for a health tracking system inside Claude Pro's Projects feature**, specifically to support an Apple Health → Notion automation project. The focus was on five concrete areas: Projects setup mechanics, Memory feature behavior with health data, model selection strategy, Apple Health connector integration inside Projects, and usage/rate limit optimization.

## 2. Confirmed facts

- Claude Projects are created via the web interface (`claude.ai`) only; mobile apps cannot create new projects or access Artifacts.[^1][^2][^3]
- Project instructions persist across all conversations in a project and function as a persistent system prompt.[^4][^5]
- No official character limit is documented for Project instructions; one user reported 306K characters without hitting a cap, but the effective ceiling is the 200K-token context window.[^6][^7]
- File uploads: 30 MB per file, unlimited files per project, 200K-token context limit on extracted text.[^8][^9][^10]
- Project files use RAG (Retrieval-Augmented Generation) — only relevant sections are loaded per query, not full files.[^7][^11]
- Project file content is cached; repeated queries against cached files do not re-consume usage limits.[^11]
- Claude Memory and Project knowledge bases are architecturally separate; Memory is project-scoped and uses lossy summarization (~1,500–1,750 words).[^12][^13][^14]
- Apple Health connector data is explicitly excluded from memory and model training per Anthropic's official healthcare announcement and Consumer Health Data Privacy Policy.[^15][^16]
- The Apple Health connector is mobile-only (iOS/Android app), US-only, beta, available to Pro/Max subscribers.[^17][^18][^19]
- No native per-project default model setting exists in claude.ai as of early 2026.[^20]
- Claude Pro usage limits: dual-layer system with a 5-hour rolling window (~45 messages for Sonnet) and a 7-day weekly cap.[^21][^22][^23]
- Claude Pro consumer accounts are NOT HIPAA-compliant; HIPAA compliance requires Claude for Work or API with a BAA.[^24][^25]
- Tool/connector definitions are injected into every message and can cost 100–500 tokens each; disabling unused connectors saves significant quota.[^26][^7]


## 3. Attempts made

- Searched official Claude documentation, help center articles, Anthropic blog posts, and privacy policies for Projects, Memory, model limits, and Apple Health connector details.
- Searched community reports (Reddit, user blogs, tutorials) for undocumented operational details like instruction limits, per-project model defaults, and connector behavior.
- Cross-referenced conflicting model naming (Sonnet 4.5 vs 4.6, Opus 4.5 vs 4.6) against API documentation.
- Investigated whether Memory blocks health data by default and whether Project instructions can override this.
- Mapped usage optimization strategies specific to connector-heavy workflows.


## 4. What failed or proved fragile

- **No official character limit for Project instructions** — relies on community reports, not Anthropic documentation.[^6]
- **Whether manually-typed health data (non-connector) is excluded from Memory** is undocumented; only connector-sourced data exclusion is confirmed.[^27][^28]
- **Exact token overhead for the Apple Health connector's tool definition** is not published; only general connector overhead figures exist.[^26]
- **Model naming volatility** — Sonnet 4.5/4.6 and Opus 4.5/4.6 are referenced interchangeably across sources; API docs are the only authoritative source.[^29][^30]
- **No per-project model default** — a frequently requested but unimplemented feature, making workflow automation more manual.[^20]


## 5. What appeared to work

- Using RAG-based file retrieval with explicit instructions to "read all project knowledge files" improves consistency.[^31][^11]
- Disabling unused connectors before sessions reduces token overhead significantly.[^7][^26]
- Using Haiku for routine check-ins (~30% of Sonnet's quota cost) and reserving Opus for deep analysis is quota-efficient.[^23][^32]
- Starting new chats for each session (rather than extending long threads) reduces cumulative context costs.[^33]
- Uploading health data to Project knowledge base (cached) rather than pasting inline reduces repeated token consumption.[^11]


## 6. Recommendations made in this thread

| Recommendation | Label | Rationale |
| :-- | :-- | :-- |
| Keep Project instructions concise to preserve context window | Still plausible | Officially recommended by Anthropic[^7] |
| Disable Memory for health tracking; use manual knowledge base files instead | Still plausible | Memory is lossy and has sensitive-data constraints; files are exact[^12][^34] |
| Use Haiku for daily check-ins, Sonnet for handoffs, Opus for weekly analysis | Still plausible | Matches model cost/intelligence tradeoffs[^23][^32] |
| Disable Apple Health connector when not actively querying health data | Still plausible | Tool definitions consume tokens per message[^7][^26] |
| Start new chats per session; rely on knowledge base for persistence | Still plausible | Reduces cumulative context costs[^11][^33] |
| Anonymize sensitive health data in consumer Claude Pro accounts | Still plausible | Consumer accounts are not HIPAA-compliant[^24][^25] |
| Include explicit instructions to "read all project files before responding" | Still plausible | Compensates for RAG's selective retrieval[^31] |
| Verify training data opt-out status in Settings → Privacy | Still plausible | Post-Sept 2025 policy allows training opt-in[^35][^36] |

## 7. Artifacts worth preserving

**Architecture concept:**

- Hybrid workflow: Web interface for Project setup/management + mobile app for Apple Health queries (connector is mobile-only).[^3][^19]

**Usage optimization pattern:**

```
Daily check-in → Haiku (connector disabled unless needed)
Weekly analysis → Opus (connector enabled, fresh chat)
Handoff doc generation → Sonnet (structured output, fresh chat)
```

**Key configuration checklist:**

- Settings → Capabilities → Memory: Toggle off "Generate memory from chat history" for health project.[^34]
- Settings → Privacy → "Improve Claude for everyone": Verify opt-out status.[^36]
- Settings → Search and tools: Disable connectors when not in use.[^7]
- iOS Settings → Health → Data Access \& Devices → Claude: Configure data types globally.[^19]

**Token efficiency heuristics:**

- Tool definitions: 100–500 tokens each per message.[^26]
- Haiku: ~30% of Sonnet's quota cost.[^23]
- Opus: ~3–5x Sonnet's quota cost.[^23]
- Cached project files: No re-consumption on repeated queries.[^11]


## 8. Open questions left unresolved

- Does manually-typed health data (not from the Apple Health connector) get silently excluded from Memory summarization, or is only connector-sourced data protected?
- What is the exact token cost of the Apple Health connector's tool definition per message?
- Is there a hard character limit for Project instructions, or is it truly unbounded up to the context window ceiling?
- Can Project instructions reliably prevent Memory from summarizing sensitive content, or is server-side filtering independent of instructions?


## 9. Usefulness score

**Score: 5/5**

This thread produced a comprehensive, citation-backed operational reference covering all five target areas with confidence flags. It distinguishes confirmed facts from undocumented gaps, provides actionable optimization strategies, and preserves specific configuration paths. Directly reusable for documentation and workflow design.

## 10. Repo-ready summary

This thread (April 5–6, 2026) produced a complete operational setup guide for building a health tracking system in Claude Pro's Projects feature. Key findings: Projects use RAG-based file retrieval with caching (reducing repeated token costs); Memory is separate from Projects and excludes Apple Health connector data from storage/training, but manually-typed health data behavior is undocumented; the Apple Health connector is mobile-only and cannot be scoped per-project; no per-project model default exists; and Claude Pro uses a dual-layer rate limit (5-hour rolling window + 7-day cap). Recommendations include disabling Memory for health tracking, using Haiku for routine check-ins, disabling unused connectors, and anonymizing PHI in consumer accounts. Confidence is high on most claims, but three areas remain undocumented: manual health data Memory exclusion, exact connector token overhead, and Project instruction character limits.

<div align="center">⁂</div>

[^1]: https://aionx.co/claude-ai-reviews/claude-projects-feature-guide/

[^2]: https://www.youtube.com/watch?v=KLQTBYpVGVw

[^3]: https://aionx.co/claude-ai-reviews/claude-pro-mobile-app-features/

[^4]: https://www.reddit.com/r/ClaudeAI/comments/1gfcu3u/does_each_chat_in_a_claude_project_have_a_200k/

[^5]: https://freeacademy.ai/lessons/custom-instructions-projects

[^6]: https://www.reddit.com/r/claudexplorers/comments/1rd99qn/my_projects_instructions_is_now_306k_characters/

[^7]: https://support.claude.com/en/articles/11647753-how-do-usage-and-length-limits-work

[^8]: https://www.datastudios.org/post/claude-file-upload-limits-and-supported-formats-in-2025

[^9]: https://www.datastudios.org/post/claude-file-upload-limits-and-supported-formats-explained

[^10]: https://fast.io/resources/claude-file-upload-limit/

[^11]: https://support.claude.com/en/articles/9797557-usage-limit-best-practices

[^12]: https://toolpod.dev/blog/claude-memory-continuity-projects

[^13]: https://unmarkdown.com/blog/ai-memory-tools-compared

[^14]: https://www.cnet.com/tech/services-and-software/anthropic-brings-claudes-memory-feature-to-all-paid-users/

[^15]: https://www.anthropic.com/news/healthcare-life-sciences

[^16]: https://www.anthropic.com/legal/consumer-health-data-privacy-policy

[^17]: https://www.mactrast.com/2026/01/claude-ai-iphone-app-gains-apple-health-integration-in-the-us/

[^18]: https://www.macrumors.com/2026/01/22/claude-ai-adds-apple-health-connectivity/

[^19]: https://support.claude.com/en/articles/11869619-using-claude-with-ios-apps

[^20]: https://www.reddit.com/r/ClaudeAI/comments/1nuj34u/allow_a_default_model_to_be_selected_per_project/

[^21]: https://www.heyuan110.com/posts/ai/2026-02-28-claude-rate-limits/

[^22]: https://portkey.ai/blog/claude-code-limits/

[^23]: https://aionx.co/claude-ai-reviews/claude-pro-message-limits/

[^24]: https://aionx.co/claude-ai-reviews/claude-pro-data-privacy/

[^25]: https://platform.claude.com/docs/en/build-with-claude/api-and-data-retention

[^26]: https://www.mindstudio.ai/blog/claude-code-mcp-server-token-overhead

[^27]: https://www.reddit.com/r/claudexplorers/comments/1rpcyag/anthropic_injected_claudes_memory_without_consent/

[^28]: https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool

[^29]: https://www.nxcode.io/resources/news/claude-ai-complete-guide-models-pricing-features-2026

[^30]: https://platform.claude.com/docs/en/about-claude/models/overview

[^31]: https://www.reddit.com/r/claudexplorers/comments/1qyytyb/project_vs_main_chat/

[^32]: https://dev.to/dr_hernani_costa/claude-ai-models-2025-opus-vs-sonnet-vs-haiku-guide-24mn

[^33]: https://www.jdhodges.com/blog/claude-ai-usage-limits/

[^34]: https://xtrace.ai/blog/how-to-manage-claude-memory

[^35]: https://www.smithstephen.com/p/claude-flips-the-privacy-default

[^36]: https://char.com/blog/anthropic-data-retention-policy/

