# ADR 0001: Record architecture decisions

- Status: Accepted
- Date: 2026-10-22
- Deciders: maintainers

## Context
We need a lightweight, reviewable record of significant technical decisions that both humans and AI agents can read as context.

## Decision
We use Architecture Decision Records (Michael Nygard format) in `docs/adr/NNNN-title.md`, created with `/adr` from `docs/templates/adr.md`.
ADRs are immutable once accepted. A change in direction gets a new ADR that supersedes the old one.

## Consequences
- Agents (especially `architect`) read `docs/adr/` before proposing designs, so they don't reopen settled decisions.
- Each significant decision costs a small amount of writing.
