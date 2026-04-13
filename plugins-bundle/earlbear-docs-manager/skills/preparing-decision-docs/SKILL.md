---
name: preparing-decision-docs
description: When a task is blocked on many user decisions, prepare a single checkbox markdown doc the user can fill in asynchronously instead of a rapid-fire Q&A thread. Use when you have >3 decisions pending, or when decisions have meaningful trade-offs the user needs space to think about.
allowed-tools: Write, Read, Edit
---

# Preparing decision docs

When work is blocked on many user decisions, a decision doc beats a rapid-fire Q&A thread. The user fills it in on their own time, you execute on their answers in one pass.

## When to use this

- **>3 decisions pending** that share context — a Q&A thread would force the user to re-load context for each question.
- **Decisions have real trade-offs** — not yes/no, not obvious defaults.
- **Decisions are independent-ish** — answering Q3 doesn't change whether Q5 is relevant (if it does, the doc needs a different shape: a flowchart or a conditional section).
- **User has indicated they want async review** — e.g., "give me something to fill in" or "I'll get back to you on this."

**Don't use** for one or two decisions — just ask directly. Don't use when the decisions are urgent — the doc adds latency.

## Structure

Save to `docs/<topic>/decisions-<YYYY-MM-DD>.md` (or wherever the active work lives). One file per decision session.

### Header

```markdown
# <Topic> decisions — <date>

Check one box per question. For any "Other" option, write your answer on the blank line.

Each question has **Context**, **Why decide now**, **Trade-offs**, and an **Example**.
```

### Per-question template

Every question has **five** sections. Skipping any of them makes the doc feel thin — the user will come back asking "why does this matter?" or "what does option B actually look like?"

```markdown
### Q<N>. <Short question title>

**Context.** What's going on. What produced this question. What's already been decided
around it. Ground the reader in the situation in 2–4 sentences.

**Why decide now.** What's blocked on this decision. Why it can't wait or be inferred.
Makes the cost of not deciding visible.

**Trade-offs.**

- **A. <Option name>.** What it costs, what it buys, what the risk is.
- **B. <Option name>.** Same shape.
- **C. <Option name>.** (if applicable)

**Example.** A concrete rendering of what the chosen option looks like in practice —
a sample commit message, a final file path, a snippet of the resulting content, a
command that would run. The goal: the user should be able to picture the outcome,
not just the label.

- [ ] **A.** <option A one-liner>
- [ ] **B.** <option B one-liner>
- [ ] **C.** <option C one-liner>
- [ ] **Other:** _________________________________________________

---
```

Critical formatting rules (learned the hard way):

1. **Blank line between the trade-offs bullet list and the checkbox bullet list.** Without the blank line, many markdown renderers merge them into one list and the checkboxes lose their `[ ]` rendering.
2. **`---` horizontal rule between questions.** Visual separation is essential when the doc is long.
3. **One blank line between each `**Section.**` block.** Improves scannability.
4. **The "Other" option always gets a blank line** (`_________`) to write on. Even if you don't expect it to be used, having it signals you're not forcing a false dichotomy.

### Footer

End with the proposed execution sequence **if** the user picks a default path, plus a
clear signal phrase:

```markdown
## Proposed execution sequence (if you answer 1A, 2A, ...)

1. <step>
2. <step>
...

Defer to next session: <items that fall out if the default path isn't chosen>

---

Once you check the boxes, save the file and tell me "decisions saved" — I'll read it and execute.
```

The signal phrase ("decisions saved") is important — it gives the user a clear handoff verb instead of guessing when you should read the file back.

## Content guidelines

**Context.** Write the reason the question exists. Often this means explaining a finding
from a previous step, a constraint you discovered, or a rule that was agreed on earlier.
Don't assume the user remembers — they will have context-switched.

**Why decide now.** Makes the cost of deferral visible. If you can't articulate why it
can't wait, the question probably shouldn't be in the doc — defer it yourself.

**Trade-offs.** The hardest section to write well. Rules:

- Lead each option with what it *costs* and what it *buys*, not just a restatement of
  the option name.
- Name the risk, not just the benefit. "Fastest. Atomic. Downside: mid-batch mistakes
  land with 20 correct ones" is better than "Fastest and atomic."
- If there's a recommended option, say so explicitly ("Recommended" in parens) — but
  only if the trade-off section makes it clear *why*.
- Don't invent false choices. If option C is obviously bad, drop it — the user doesn't
  want to evaluate obviously-bad options.

**Example.** Concrete, not abstract. Show the actual commit message, the actual final
path, the actual resulting file content, the actual command — whatever the unit of
work produces. If you can't write a concrete example, you probably don't understand
the option well enough to offer it.

## Anti-patterns

- **Thin questions.** One-sentence context + two-word options. The user has to guess
  what the trade-off even is. Fix: add context and trade-offs, or don't ask.
- **Leading the witness.** Phrasing options so one is obviously correct. Either trust
  the user with the real trade-offs or just act on the default without asking.
- **Too many questions.** Decision fatigue is real. If you have 20 questions, group or
  pre-decide the easy ones and only surface the hard ones. Explicitly call out
  "pre-decided" items so the user can override if they disagree.
- **Missing the execution sequence footer.** Without it, the user doesn't know what
  happens after they fill in the doc. The footer is the contract.
- **Forgetting the signal phrase.** "Tell me when you're done" is vague. "Tell me
  'decisions saved'" is a verb the user can say.

## Iterating on the doc

If the user pushes back on an initial draft (too thin, wrong rendering, missing
context), rewrite the whole file with `Write`, not scattered `Edit`s. The doc is small
enough that a full rewrite is cleaner than patching, and it ensures formatting rules
stay consistent across all questions.

Common iteration triggers:
- "Too little information" → add Context/Why/Trade-offs/Example detail.
- "Preview looks weird" → check for missing blank lines before checkbox lists.
- "Add examples" → add the **Example** section if missing; make existing examples
  more concrete.
- "Why does this matter?" → the **Why decide now** section is too thin.

## When to skip this entirely

- One or two simple questions — just ask.
- Urgent decisions — the async latency is too high.
- Decisions that depend on each other — a flowchart or a conditional walkthrough is
  better than independent questions.
- Decisions where you have enough context to just pick a reasonable default and move —
  don't manufacture questions to cover yourself.
