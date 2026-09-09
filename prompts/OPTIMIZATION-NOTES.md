# Master Prompt v1 → v2 — What Changed and Why

Reference notes for `agentic-ai-developer.md`. v1 was the original 27-section master prompt.

## Headline

| | v1 | v2 |
|---|---|---|
| Length | ~4,500–5,000 words (estimate — original not archived here) | 1,905 words |
| Sections | 27 | 20 |
| Approval gate | Fires on every request | Scoped by request size |
| Discovery | Uncapped (~40-item checklist) | Max 5 questions, architecture-relevant only |

Roughly a 60% token reduction per turn, with more enforceable rules — the cuts were prose, not capability.

## The four changes that matter most

**1. Scope router (new §3).** v1 applied the full Discovery → Spec → Approval → Build pipeline to everything, including a typo fix. Every request now routes to TRIVIAL / SMALL / NEW SYSTEM / REVIEW, and only NEW SYSTEM gets the heavy path. This was v1's biggest practical failure — process so heavy you stop using the agent for real work.

**2. Discovery cap (§4).** v1 said "ask one question at a time" and then listed ~40 discovery items — a 40-turn interrogation. v2 caps at 5, restricted to what actually changes architecture, with everything else assumed and listed for correction.

**3. SDK contradiction resolved (§8).** v1 §8 preferred the OpenAI Agents SDK; v1 §9 said don't hardcode a single provider. Nothing resolved it. v2 gives a three-step decision rule: match the project's existing provider → otherwise pick on requirements → abstract only when multi-provider is a stated requirement.

**4. Escape hatch (§3, §19).** v1 had no path for "just build it." v2 requires dropping to the lightest viable workflow when the user says so, and lists interrogating a user who already said build as a hard never.

## Other fixes

- **§27 vs §4 contradiction** — v1 mandated a fixed opening question while also forbidding questions with known answers. v2 makes the opener conditional on actually lacking a brief.
- **Deduplication** — "never fabricate results" appeared in v1 §17, §18, §19, §24; "not every problem needs an agent" in §2, §3, §24. Consolidated into §12 (Honesty) and §19 (Never).
- **Untestable directives made checkable** — "write production-quality Python" became eight literal rules (type hints, no bare except, timeouts on external calls, ~400-line file cap, etc.). A model can verify itself against these; it cannot verify itself against an adjective.
- **Vercel default corrected (§15)** — Vercel's execution limits make it a poor host for the long-running Python agents this prompt exists to build. Now routed by runtime: serverless → Vercel; long-running agents/workers → container host, with Hetzner + Docker called out as the cheapest option and a required monthly cost estimate.
- **Testing guidance split** — TDD for pure functions and tools; **evaluation cases** for prompt-driven behavior. Unit-testing model prose produces false confidence.
- **Reporting scaled (§16)** — v1's 15-section report ran even for one-file fixes. Now three lines for small work, full report for new systems.
- **Modes given triggers (§17)** — v1 listed 9 modes with no entry rules. Now the scope router sets entry mode, and the user can force one by name.
- **Removed** — the decorative `INPUT ↓ UNDERSTAND ↓ PLAN…` diagram (constrains nothing), and the textbook-style chapters in v1 §5, §13, §16, §17, whose content survives as rules in §4, §9, and §11.

## Kept deliberately

The agent-vs-non-agent suitability ladder, the approval gate concept, the four-level prompt-injection trust hierarchy, and the "Not tested" honesty rule. These are the parts most developer-agent prompts get wrong — v1 had them right.

## Deployment note

Both v1 and v2 assume knowledge sources about Aamir are supplied separately. Neither contains biographical facts, by design: the "never invent information about Aamir" rule only holds if the prompt itself never models what that information looks like.
