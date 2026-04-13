---
name: design-frontend
description: Plan and design hardened frontend systems with authentication, hosting, CDN, CI/CD, and AI integration. Follows a 4-phase lifecycle — Research → Plan (BRD) → Design Doc → QA Review — to produce principal-level architecture documents with trade-off matrices, sequence diagrams, and conditional recommendations.
user_invocable: true
---

# Design Frontend Skill

> **Context:** This skill operates in the `wireframes/` directory. After making changes, run `make wire-export` to export static builds, then `make dist` to rebuild `dist/public/` with encryption.

Design hardened frontend systems at a principal engineer level. This skill produces architecture design documents, not implementation code.

## Lifecycle: Research → Plan → Design Doc → QA Review

---

## Phase 1: Research

Research is a **prerequisite** to planning. Do not skip or abbreviate it.

### What to research
- **Hosting platforms**: managed (Amplify, Netlify, Vercel, Cloudflare Pages), self-hosted (VPS, Docker), static (S3, GitHub Pages)
- **Auth mechanisms**: platform-native (Cognito, Netlify Identity, Cloudflare Access), third-party (Clerk, Auth0, Supabase Auth, Firebase Auth), DIY (Express session, shared passphrase, OAuth)
- **CI/CD options**: git-push deploy, GitHub Actions, manual
- **AI integration readiness**: does the platform offer native AI services? How easy to add later?
- **Pricing**: free tiers, per-MAU costs, bandwidth limits, compute credits
- **Community wisdom**: how are others solving similar problems? Forum discussions, blog posts

### How to research
- Use **WebSearch** for current pricing, feature comparisons, and community discussions
- Use **WebFetch** for any URLs the user provides — extract key facts, don't just link
- Use **Explore agents** for codebase analysis (current architecture, storage model, build process)
- Capture **every reference link with context** (what was learned, not just the URL)

### Research output format
Research flows directly into the Plan (Phase 2). It is not a separate deliverable. Every option evaluated should appear in a table with: type, pricing, reference link, and a one-line assessment.

---

## Phase 2: Plan (Business Requirements Document)

The plan IS the business requirements document. It captures all research and defines what the design doc must deliver.

### Required sections

1. **Problem Statement** — what we're solving and why (2-3 sentences)
2. **Current Architecture** — what exists today (bullet list: frontend, backend, infra, CI/CD, auth, storage)
3. **Stakeholder Needs** — table of stakeholder → need
4. **Key Constraints** — things that limit options (e.g., filesystem storage, build process, budget, scale)
5. **Options Evaluated** — comprehensive tables organized by category:
   - Hosting platforms (with type, pricing, reference)
   - Auth mechanisms (platform-native, third-party, DIY — with free tier, cost-after, best-for)
   - AI integration readiness (scored HIGH/MEDIUM/LOW with rationale)
   - CI/CD options
   - Pricing detail for leading options
6. **Essential Trade-Offs** — the 5-7 key dimensions along which options diverge:
   - Codebase impact vs. platform power
   - Auth richness vs. simplicity
   - Serverless vs. persistent server
   - AI integration path (invest now vs. migrate later)
   - Cost trajectory (demo scale vs. growth scale)
   - Vendor lock-in
   - Migration complexity from current state
7. **Design Doc Requirements** — what sections the design doc must include and what quality bar it must meet
8. **Consolidated Reference Links** — every URL researched, organized by topic

### Quality bar for the plan
- Every option evaluated has a reference link
- Trade-offs are named dimensions, not buried in prose
- Constraints are explicit and drive the option evaluation (e.g., "filesystem storage rules out pure serverless")
- The plan is complete enough that someone else could write the design doc from it

---

## Phase 3: Design Document

Takes the Plan/BRD as input. Produces a principal-level architecture document at `docs/design-{topic}.md`.

### Required sections

1. **Executive Summary** — problem + recommendation + rationale in ONE paragraph. A busy executive should be able to read this and know the answer.

2. **Architecture Options** — each viable option with:
   - **Mermaid diagram** (`graph TB` for component/deployment diagrams) — NOT ASCII art
   - 3-5 bullet summary of how it works
   - Key advantage and key disadvantage

3. **Trade-Off Matrix** — single table, options as columns, dimensions as rows:
   ```
   | Dimension        | Option A | Option B | Option C |
   |------------------|----------|----------|----------|
   | Setup effort     | 2-4 hrs  | 6-10 hrs | 8-16 hrs |
   | Monthly cost     | $4-6     | $0       | $0       |
   | Auth quality     | Adequate | Good     | Excellent|
   | AI readiness     | MEDIUM   | HIGH     | LOW      |
   | Codebase impact  | ~50 LOC  | ~200 LOC | ~300 LOC |
   | Vendor lock-in   | None     | Moderate | Moderate |
   ```

4. **Sequence Diagrams** — mermaid `sequenceDiagram` format for the recommended option(s):
   - Happy path: user login → session → access content → submit feedback
   - Error path: login failure, expired session, network error
   - MUST use mermaid syntax — NOT ASCII art

5. **Conditional Recommendations** — NOT a single answer. Structure as:
   ```
   Choose X if: [criteria]
   Choose Y if: [different criteria]
   Choose Z if: [yet another set of criteria]
   ```

6. **Migration Path** — from current state to recommended option:
   - What changes (frontend, backend, infra, CI/CD)
   - Data migration (if any)
   - Downtime expectations
   - Rollback plan

7. **Risk Assessment** — table of risk → likelihood → impact → mitigation

8. **Reference Links** — consolidated from the plan, organized by topic

### What makes a good design doc
- **No redundancy** — each section has a unique purpose. Don't repeat the trade-off matrix content in the architecture options section.
- **Mermaid diagrams, not ASCII** — use `graph TB` for component diagrams, `sequenceDiagram` for flows. These render in GitHub, VS Code, and most markdown viewers.
- **Diagrams first, prose second** — a reader should understand the architecture from diagrams alone. Prose explains nuance.
- **Conditional, not dogmatic** — the recommendation section gives criteria for choosing, not a single answer.
- **Quantified, not vague** — "~50 lines of code" not "minimal changes"; "$4-6/mo" not "cheap"
- **Complete auth flow** — covers login, session management, logout, token refresh, social login redirect

---

## Phase 4: QA Review Checklist

After the design doc is written, review it against this checklist. Every item should be `- [x]`.

### Structure
- [ ] Has executive summary (problem + recommendation in 1 paragraph)
- [ ] Has mermaid architecture diagrams (`graph TB` for component/deployment, `sequenceDiagram` for auth flows) — NOT ASCII art
- [ ] Has trade-off matrix with ALL dimensions scored
- [ ] Has conditional recommendations ("choose X if...")
- [ ] Has migration path with rollback plan
- [ ] Has risk assessment table (risk → likelihood → impact → mitigation)
- [ ] Has consolidated reference links, organized by topic

### Content Quality
- [ ] Trade-offs are explicit dimensions, not buried in prose
- [ ] No redundant content across sections (each section has a unique purpose)
- [ ] Cost analysis covers both demo scale AND growth scale projections
- [ ] AI integration readiness is scored per option (HIGH/MEDIUM/LOW) with rationale
- [ ] Sequence diagrams cover happy path AND error cases (auth failure, expired session, network error)
- [ ] Vendor lock-in evaluated and scored per option
- [ ] Codebase impact quantified (lines of code, files changed, dependencies added)
- [ ] Migration path accounts for: data migration, downtime, rollback, CI/CD changes

### Completeness
- [ ] ALL options from the research/plan phase are represented in the design doc
- [ ] Reference links are consolidated, clickable, and organized
- [ ] Auth flow covers: login, session management, logout, token refresh, social login redirect
- [ ] Pricing includes free tier limits AND cost-after for each option
- [ ] Community wisdom / real-world usage is referenced (not just vendor docs)

### Anti-Patterns to Flag
- [ ] Recommendation is conditional, not dogmatic (no single "just use X")
- [ ] Architecture diagrams exist (not just prose descriptions of components)
- [ ] No "TBD" or "TODO" items left unresolved
- [ ] No option dismissed without explicit rationale
- [ ] Cost projections are not just "free" — include what happens at 10x, 100x scale

---

## When to Use This Skill

Use `/design-frontend` when:
- Planning a new frontend system with auth, hosting, or infrastructure decisions
- Evaluating hosting platforms (AWS, Netlify, Vercel, Cloudflare, VPS)
- Adding authentication to an existing frontend
- Planning CI/CD for a frontend project
- Evaluating AI integration readiness of different platforms
- Migrating from one hosting/auth platform to another

Do NOT use for:
- Visual design review (use `/design-review`)
- Functional QA testing (use `/qa-test`)
- Implementation (exit this skill and write code)
