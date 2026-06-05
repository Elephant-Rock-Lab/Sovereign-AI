# Architecture Notes

## MVP-0 scope

MVP-0 is local-only and Python-only. It establishes the control-plane contract before adding Solace, QwenPaw, Cloudflare, OpenClaw, Hermes, or ML-Master.

## Canonical loop

```text
CommandReceived
TaskPlanned
PolicyChecked
PatchProposed
PatchApproved
PatchApplied
AuditCommitted
TaskCompleted
```

## Later integration points

- Solace/A2A: replace direct local orchestration calls with event publication/subscription.
- QwenPaw/Telegram: bridge incoming chat commands into `CommandReceived` events.
- OpenClaw: attach as a sandboxed effector with short-lived capability tokens.
- Hermes: add skill proposal, not direct skill installation.
- ML-Master: add trace consolidation into candidate memories.
- Obsidian PM: expand vault parser to support plugin-specific task/Gantt formats.
