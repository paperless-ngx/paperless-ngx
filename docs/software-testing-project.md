# Software Testing Project: R08 + K01

## Scope

The team tests a pinned Paperless-ngx baseline as an independent QA team. The selected technique is K01 Property-Based Testing. Keep the implementation narrow: one or two deterministic modules with rich input domains, at least three explicit properties, automatic input generation, shrinking, and reproducible counterexamples.

Do not attempt to test the whole repository. Do not target public/demo systems.

## Required Deliverables

The course brief requires:

1. System purpose, actors, use cases, module/dependency tree, and data flow.
2. At least one component/container diagram and explanations of three to five relevant modules.
3. Reproducible environment, versions, build/run commands, services, seed data, and at least three working business flows.
4. K01 theory, scope, assumptions, risks, and measurable pass/fail criteria.
5. A test model describing input, precondition, invariant/oracle, and test data.
6. Automated tests or a harness with dependencies and one-command execution.
7. Logs, metrics, defects or anomalous behavior, and root-cause analysis. If no defect is found, provide coverage/score/threshold evidence.
8. The pinned commit/tag, test configuration, and instructions for reproducing results on a clean machine.

K01 specifically requires at least three properties, generated tests, and saved counterexamples.

## Cycles

| Cycle | Dates | Goal |
| --- | --- | --- |
| 1 | 02/10/2026-09/10/2026 | Onboarding, pinned baseline, architecture, candidate modules, report skeleton |
| 2 | 10/10/2026-20/10/2026 | Property design, generators, criteria, and midterm package |
| 3 | 21/10/2026-20/11/2026 | Automation, execution, shrinking, metrics, defects, and analysis |
| 4 | 21/11/2026-final defense | Reproduction, final report, demo, and peer review |

The official midterm is **20/10/2026**. The final-defense date follows the university schedule.

## Team Workflow

- Pick an issue from the project board and move it to `In Progress`.
- Create a short branch from `dev`; do not work directly on `dev`.
- Keep each pull request focused on one issue and request the reviewer named in that issue.
- Run the narrowest relevant checks locally before opening the pull request.
- Attach evidence to the issue or pull request: command, seed, counterexample, log, metric, screenshot, or report section.
- Squash merge after one approval. Delete the merged branch.

The repository already includes upstream GitHub Actions for backend, frontend, lint, documentation, Docker, and static analysis. Reuse those workflows. Add a coursework-specific job only if the K01 tests are not covered by the backend workflow.

## Current Assignment

Each member owns two issues of comparable scope: one analysis/design deliverable and one implementation/integration deliverable. The project board is the source of truth for owner, cycle, size, status, and deliverable.
