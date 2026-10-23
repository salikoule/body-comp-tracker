# Body Composition Tracker (Anvil)

Personal body-composition coach on **Anvil**, using **craftify-library** for UI (KPI cards, theme, login patterns) and **BodyCoach** server rules (ported from the FastAPI `body-comp` backend).

## Features

- **Anvil Users** — email sign-up / sign-in (`users.yml`).
- **Data tables** — `profiles`, `weight_logs`, `week_logs` (each row linked to the signed-in user).
- **Coach** — `craftify_library.BodyCoach` proposes plans, issues weekly calories, adapts on check-in.
- **Screens** — Profile (first visit) → Home (targets + log weight) → Sunday check-in. No login UI for now (single local session auto-starts on open).

## Local run

Prerequisites: same as [craftify-library/docs/LOCAL-DEV.md](../craftify-library/docs/LOCAL-DEV.md) (Java 21, Postgres, sibling deps).

```bash
chmod +x scripts/dev-server.sh
./scripts/dev-server.sh
# http://localhost:3031
```

In the Anvil IDE, add **craftify-library** as a dependency if you sync to cloud (`ST3GINETRT4QJYDC`).

## Tests

Coach unit tests live in **craftify-library** (pure Python):

```bash
cd ../craftify-library && .venv/bin/python -m pytest tests/test_body_coach*.py -q
```

## Product contract

Behaviour follows `body-comp/docs/plans/2026-10-20-1049-feat-body-composition-coach-plan.md` (AE1 etc.).
