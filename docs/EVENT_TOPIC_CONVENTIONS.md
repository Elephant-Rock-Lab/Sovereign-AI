# Phase 3 event topic conventions

This document drafts the event topic and envelope conventions for a future Phase 3 event fabric.

These conventions are preparatory only. They do not introduce broker dependencies, Solace runtime wiring, A2A transport code, MCP integration, or any external message bus requirement.

## Goals

- Preserve the current local-first control-plane contract.
- Keep event naming stable before a broker is introduced.
- Make command, task, approval, artifact, memory, and system events easy to route later.
- Keep correlation IDs visible across the full command lifecycle.

## Topic naming pattern

Proposed topic names use dot-separated segments:

```text
sovereign.<workspace>.<domain>.<event>
```

Where:

- `sovereign` is the product namespace.
- `<workspace>` is a workspace slug such as `demo-project`.
- `<domain>` is the bounded context that owns the event.
- `<event>` is a lower-kebab-case event name derived from the canonical event type.

Workspace-independent system topics may use:

```text
sovereign.system.<domain>.<event>
```

## Topic families

### Command topics

```text
sovereign.<workspace>.command.received
sovereign.<workspace>.command.completed
sovereign.<workspace>.command.rejected
```

Command topics represent user or interface intent entering and leaving the control plane.

### Task topics

```text
sovereign.<workspace>.task.planned
sovereign.<workspace>.task.completed
sovereign.<workspace>.task.rejected
```

Task topics represent task planning, task mutation results, and read-only task analysis outcomes.

### Approval topics

```text
sovereign.<workspace>.approval.requested
sovereign.<workspace>.approval.approved
sovereign.<workspace>.approval.rejected
```

Approval topics represent explicit human approval boundaries. They should never be skipped for durable writes that require approval.

### Patch and audit topics

```text
sovereign.<workspace>.patch.proposed
sovereign.<workspace>.patch.applied
sovereign.<workspace>.audit.committed
```

Patch and audit topics describe the write path from proposed change through durable Git audit.

### Artifact topics

```text
sovereign.<workspace>.artifact.created
sovereign.<workspace>.artifact.updated
sovereign.<workspace>.artifact.archived
```

Artifact topics are reserved for future generated assets such as reports, exported summaries, or review packets.

### Memory topics

```text
sovereign.<workspace>.memory.observed
sovereign.<workspace>.memory.proposed
sovereign.<workspace>.memory.approved
sovereign.<workspace>.memory.rejected
```

Memory topics are reserved for future memory workflows. Proposed or durable memory changes should remain approval-gated until a stricter memory policy exists.

### System heartbeat topics

```text
sovereign.system.health.heartbeat
sovereign.system.health.degraded
sovereign.system.health.recovered
```

System heartbeat topics are for runtime health and operational visibility once a brokered event layer exists.

## Envelope expectations

The current `EventEnvelope` model remains the source of truth for envelope shape. Future broker adapters should preserve these fields:

```text
msg_id
timestamp
event_type
sender
recipient
workspace
priority
ttl_seconds
correlation_id
payload
```

Additional adapter-specific metadata may be added outside the canonical payload, but adapters should not mutate the canonical envelope fields.

## Correlation rules

- Every command lifecycle starts with one `correlation_id`.
- Derived events from the same command must preserve that `correlation_id`.
- Approval, patch, audit, and task completion events for the same user command should share the same `correlation_id`.
- A new `correlation_id` should be created only for a new user command or independent system workflow.

## Phase 3 non-goals

This document does not add:

- Solace broker configuration.
- A2A transport code.
- MCP runtime integration.
- Background workers.
- Remote queue consumers.
- New durable event storage paths.
- New production authentication or authorization behavior.

Those belong in later implementation PRs after the local control-plane contract remains stable under tests.
