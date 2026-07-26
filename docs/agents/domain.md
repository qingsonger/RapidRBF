# Domain Docs

How the engineering skills should consume this repository's domain documentation.

## Before exploring, read these

- `CONTEXT.md` at the repository root.
- Relevant ADRs under `docs/adr/`.

If these files do not exist, proceed silently. The domain-modeling workflows create them lazily when terms or decisions are resolved.

## Configured layout

This repository uses a single-context layout:

```text
/
├── CONTEXT.md
├── docs/adr/
└── src/
```

## Use the glossary's vocabulary

When output names a domain concept, use the term defined in `CONTEXT.md`. Avoid synonyms that the glossary explicitly rejects.

If a needed concept is missing, reconsider whether it belongs to the project or note the gap for domain modeling.

## Flag ADR conflicts

If proposed work contradicts an existing ADR, surface the conflict explicitly instead of silently overriding it.
