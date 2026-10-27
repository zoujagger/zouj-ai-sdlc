# Intents: the shared intent repository

Every change starts here. One folder per intent, numbered in sequence:

```
docs/intents/
  0001-csv-export/
    intent.md   # need: problem, outcome, users/systems, constraints      (/intent)  ✋ PO validates
    spec.md     # requirements + design, flags, policy conflicts            (/spec)    ✋ accepted
    plan.md     # Plan-mode plan, tasks, deviation log                      (/plan)    ✋ engineer accepts
```

See a finished example in [`docs/examples/0001-csv-export/`](../examples/0001-csv-export/).
Create one with `/intent "<need>"` or `scripts/new-intent.sh <slug>`. Check status with `/sdlc <id>`.
Intents also come from the GitHub **Intent** issue form, from alerts (`claude-maintain.yml`), scans, and postmortem action items.

Each file's `status:` field tracks the gates. The product owner watches this folder (see `.github/CODEOWNERS`).
If an external tool (Jira, ServiceNow) is the source of truth for intents, `intent.md` just links to the ticket. See `docs/governance.md`.
