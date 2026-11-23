# .aiops: this repo's lifecycle artifacts

Each change to the plugin lives in `.aiops/NNNN-slug/` (`intent.md` → `spec.md` → `plan.md` → `review.md`); run
`bin/sdlc status`. The consumer-facing version of this file is `templates/scaffold/.aiops/README.md`.

Intent `0006` has no folder on purpose: it is reserved for the guard-gap backlog (see `docs/roadmap.md` and
[Known gaps](../docs/architecture.md#known-gaps-intent-0006)).
