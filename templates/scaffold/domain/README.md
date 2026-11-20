# Domain model

This directory holds the domain model: the state machines, business rules and workflows of this system, declared
once and validated on every `make check`. It belongs to the opt-in `dsl` part of zouj-ai-sdlc
(`sdlc setup --with dsl`).

- **Model first.** While this directory exists, every `spec.md` needs a `## Domain DSL` section. The section names
  the `domain/<name>.dsl.json` files the change adds or edits, or says `No domain changes` for a purely technical or
  UI change. The Data model and API contracts are derived from the model, not the other way round.
- **Plan Step 1.** The plan's first step updates these files and runs `make validate-dsl` red, then green, before
  any application code.
- **Validated.** `make validate-dsl` (part of `make check`) runs `scripts/validate-dsl.py`, which uses only the
  Python standard library. Each problem is printed with its file and JSON path, for example
  `domain/order.dsl.json: $.transitions[2].to: unknown state "Shipped"`.

## Format
One JSON object per `domain/<name>.dsl.json` file. Every file has:

| Key | Value |
|---|---|
| `dsl` | `1`, the format version |
| `kind` | `state_machine`, `rules` or `workflow` |
| `name` | an identifier (letters, digits, `_`, `-`; starting with a letter), unique across `domain/` |
| `description` | optional text |

Any other key is an error, so a typo surfaces instead of being ignored. The strings in `guard`, `when` and `then`
name domain concepts; nothing evaluates them.

### `state_machine`
| Key | Value |
|---|---|
| `states` | a non-empty list of unique state names |
| `initial` | one of `states` |
| `final` | optional: a list of states |
| `transitions` | a list of `{"from", "to", "event"}` with an optional `"guard"`; `from` and `to` are states, and each `from` + `event` pair is unique |

```json
{
  "dsl": 1,
  "kind": "state_machine",
  "name": "ticket",
  "states": ["open", "in_progress", "closed"],
  "initial": "open",
  "final": ["closed"],
  "transitions": [
    {"from": "open", "to": "in_progress", "event": "start"},
    {"from": "in_progress", "to": "closed", "event": "resolve", "guard": "all checks done"}
  ]
}
```

### `rules`
| Key | Value |
|---|---|
| `rules` | a non-empty list of `{"id", "when", "then"}` with an optional `"description"`; ids are unique, `when` and `then` are non-empty text |

```json
{
  "dsl": 1,
  "kind": "rules",
  "name": "limits",
  "rules": [
    {"id": "R1", "when": "a request exceeds the daily limit", "then": "the request is refused"}
  ]
}
```

### `workflow`
| Key | Value |
|---|---|
| `steps` | a non-empty list of `{"id"}` with an optional `"next"` (a list of step ids) and `"description"`; ids are unique |
| `start` | one of the step ids |

```json
{
  "dsl": 1,
  "kind": "workflow",
  "name": "review",
  "start": "submit",
  "steps": [
    {"id": "submit", "next": ["check"]},
    {"id": "check", "next": ["accept", "reject"]},
    {"id": "accept"},
    {"id": "reject"}
  ]
}
```

## Limits
Only regular `*.dsl.json` files directly in `domain/` are read: a link, a file over 1 MiB, or nesting deeper than 64
levels is reported as a problem. Other files, like this README, are ignored.
