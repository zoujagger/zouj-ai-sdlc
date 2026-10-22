---
name: policy-ux
description: UX guidelines (advisory). Apply when writing spec.md or building/reviewing any user-facing interface, copy, error message, or interaction flow.
user-invocable: false
---

# UX guidelines (advisory)

<!-- Replace with your design system and UX principles. -->

- Use existing design-system components before creating new ones. Link the component in spec.md.
- Every flow defines empty, loading, error, and success states.
- Error messages say what happened and what the user can do next. No raw error codes.
- Keyboard navigable, visible focus, labels on all inputs, color contrast ≥ 4.5:1.
- Destructive actions need confirmation or undo.
- Frontend work: produce a mock-up from intent.md (e.g. with Claude Design) before spec acceptance, and attach before/after screenshots to the PR.
