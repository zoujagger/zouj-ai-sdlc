---
id: 0001
title: Greet people in their own language
status: Draft          # Draft → Approved (human types `Intent Approved 0001`) · Closed
owner: you
initiator: the zouj-ai-sdlc sandbox
source: a sample need, to practise the workflow
created: __DATE__
---

# Intent: Greet people in their own language

## Problem
`src/greet.py` always answers in English ("Hello, Ada!"). Users who prefer French or Spanish get an English greeting.

## Desired outcome
- A caller can ask for a greeting in English, French or Spanish.
- English stays the default, so existing callers see no change.

## Users & systems affected
- Users: callers of `greet()`.
- Systems: `src/greet.py` and its tests. No data, no integrations.

## Constraints
- Python standard library only.
- `make check` stays green.

## Out of scope
- Detecting the language automatically.
- Languages other than English, French and Spanish.

## Open questions
- [ ] What should happen for an unsupported language: fall back to English, or raise an error? (you)
