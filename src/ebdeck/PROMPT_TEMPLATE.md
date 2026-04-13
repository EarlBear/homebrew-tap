# How to Prompt a New Deck

Copy this prompt template, fill in the blanks, and have an LLM generate a `content/*.yaml` file. Then run any of the three generators via Docker.

---

## Prompt Template

```
Generate an investor pitch deck YAML file for the following company.
Use the schema from content/investor-pitch.yaml as the format reference.

Company: [NAME]
Industry: [INDUSTRY]
Stage: [Seed / Series A / Series B / etc.]
One-liner: [WHAT THE COMPANY DOES IN ONE SENTENCE]

Key metrics:
- ARR: [AMOUNT]
- Customers: [COUNT]
- Growth: [RATE]
- Team size: [COUNT]

The ask:
- Raising: [AMOUNT]
- Use of funds: [BREAKDOWN]

Tone: Professional, confident, data-driven.
Audience: Venture capital investors.

Output format: YAML matching the content/investor-pitch.yaml schema.
Include speaker notes for each slide.
Available layouts: title, section, content, metrics, closing.
```

## Render via Docker

```bash
# Marp — warm & earthy style → Markdown (then PDF/PPTX)
docker compose run marp
docker compose run marp-pdf
docker compose run marp-pptx

# Slidev — modern & tech-forward → Markdown (for Slidev dev server)
docker compose run slidev

# python-pptx — natural & organic → native editable .pptx
docker compose run pptx

# Custom content file:
docker compose run pptx /data/content/my-deck.yaml /data/brand.yaml
```

## Output Locations

| POC | Output |
|-----|--------|
| Marp | `poc-marp/output/deck.md`, `deck.pdf`, `deck.pptx` |
| Slidev | `poc-slidev/output/slides.md` |
| python-pptx | `poc-pptx/output/deck.pptx` |
