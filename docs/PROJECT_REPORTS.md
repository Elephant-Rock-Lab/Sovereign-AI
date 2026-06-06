# Project Report Commands

Sovereign AI supports read-only project report commands for the selected workspace.

These commands read Markdown/YAML task files and write activity records, but they do not create approval requests and do not mutate project files.

## Project summary

```bash
python -m sovereign_cortex.cli "Project summary" --date 2026-06-06
```

Reports:

```text
total tasks
status counts
scheduled due dates
overdue active tasks
tasks due in the next 7 days
dependency counts
```

## Project risk report

```bash
python -m sovereign_cortex.cli "Project risk report" --date 2026-06-06
```

Reports:

```text
active overdue tasks
tasks with dependencies
declared dependency count
unowned task count
```

Completed tasks are excluded from active overdue counts.

## Next action

```bash
python -m sovereign_cortex.cli "Next action" --date 2026-06-06
```

The recommendation is deterministic:

```text
1. Ignore completed tasks.
2. Prefer tasks with the earliest due date.
3. Place unscheduled tasks after scheduled tasks.
4. Break ties by task title.
```

## Current limitation

The report commands are currently routed at the CLI layer. Issue #30 tracks moving this routing into `LocalOrchestrator` so the CLI can remain a thinner presentation layer.
