# Sovereign AI Roadmap

## North Star

Build a **local-first, auditable personal AI control plane** that turns user intent into bounded, reviewable, workspace-scoped action.

The system must remain:

```text
local-first
patch-first
approval-gated
Git-audited
workspace-scoped
event-ready
tool-constrained
memory-transparent
```

The goal is not to build an unconstrained autonomous agent. The goal is to build a **sovereign agency kernel**.

## Current Status

### Completed

```text
MVP-0.0 — Python local scaffold
MVP-0.1 — persisted approval requests
CI — Python test workflow
Approval integrity — stale patch protection
```

The control plane can now:

```text
receive a command
select a workspace
read the vault
propose a patch
save approval requests
approve/reject requests
apply approved patches
guard against stale approvals
commit changes to Git
run CI on PRs
```

### In Progress

```text
MVP-0.2 — deterministic task operations
```

Scope:

```text
Create task
Mark task done
Change task owner
Shift due date
Show dependency impact
```

All write operations must remain patch-first and approval-gated.

## Phase 0 — Local Control Plane

### MVP-0.2 — Task Operations

Goal: make the local control plane useful for real project management.

Required operations:

```text
Create task ...
Mark ... done
Change owner of ... to ...
Shift ... due date by N days/weeks
Show dependency impact for ...
```

Exit criteria:

```text
All write operations create approval requests.
Read-only queries do not create approval requests.
Task lookup works by title, id, or path keyword.
CI passes.
README documents supported command forms.
```

### MVP-0.3 — Approval UX Hardening

Goal: make approval management reliable enough for daily use.

Features:

```text
cortex approvals list --status pending
cortex approvals show <id>
cortex approvals diff <id>
cortex approvals approve <id>
cortex approvals reject <id>
cortex approvals prune --older-than N
```

Exit criteria:

```text
CLI never exposes Python tracebacks for expected approval failures.
Approval conflicts explain the exact file and reason.
Rejected approvals keep an audit artifact.
Approved approvals record commit hash.
```

### MVP-0.4 — Event Log

Goal: make every control-plane decision reconstructable.

Add:

```text
events/
  YYYY-MM-DD.jsonl
```

Capture:

```text
CommandReceived
PatchProposed
PolicyChecked
ApprovalRequested
PatchApproved
PatchRejected
PatchApplied
AuditCommitted
TaskCompleted
TaskRejected
```

Exit criteria:

```text
Every command writes an event trail.
Every event has correlation_id.
Approval artifacts reference event correlation_id.
Tests verify event log creation.
```

### MVP-0.5 — Workspace Registry

Goal: support more than the demo project.

Add:

```text
workspaces.yaml
```

Example:

```yaml
workspaces:
  demo-project:
    vault_root: vault/demo-project
    default_policy: local_safe
  website-launch:
    vault_root: vault/website-launch
    default_policy: local_safe
```

Exit criteria:

```text
CLI can target --workspace <name>.
Policy scopes are workspace-specific.
Path traversal remains blocked.
```

## Phase 1 — Project-Native Operator

Goal: operate against Obsidian-compatible project files as the source of truth.

Features:

```text
task creation
task updates
dependency inspection
status reporting
project summary
risk summary
next-action recommendation
```

Exit criteria:

```text
The system can manage one real project vault safely.
All changes are Markdown/YAML patches.
All durable writes require approval or explicit auto-approval policy.
All changes are Git-audited.
```

## Phase 2 — Interface Layer

Goal: expose the local control plane through thin interfaces.

Targets:

```text
CLI
FastAPI local endpoint
Cherry Studio integration
QwenPaw or Telegram bridge
```

Rules:

```text
Interfaces submit intent.
Interfaces do not directly mutate files.
Interfaces do not bypass policy.
Interfaces do not hold broad tool authority.
```

Exit criteria:

```text
A chat message can create an approval request.
A user can approve/reject from CLI or bridge.
All activity still flows through the control plane.
```

## Phase 3 — Event Fabric

Goal: introduce asynchronous event flow without losing control.

Likely stack:

```text
Solace Agent Mesh
A2A-style event envelopes
MCP-compatible tool/resource adapters
```

Topics:

```text
user/{channel}/command
task/{workspace}/created
task/{workspace}/approval_requested
task/{workspace}/approved
task/{workspace}/completed
artifact/{workspace}/created
memory/{workspace}/candidate
system/heartbeat
```

Exit criteria:

```text
Local orchestrator can publish and consume events.
Approval workflow survives process restarts.
Events can be replayed for audit.
No agent communicates by hidden direct mutation.
```

## Phase 4 — Sandboxed Tools

Goal: add execution tools without granting ambient authority.

Candidate tools:

```text
browser research
filesystem operations
shell commands
API calls
calendar draft actions
email draft actions
```

Security requirements:

```text
short-lived capability tokens
workspace-scoped file access
sandboxed shell/browser execution
no direct outbound email without approval
no calendar mutation without approval
no self-granted permissions
```

Exit criteria:

```text
Tool calls are policy-checked.
Tool calls are logged as events.
High-risk tool calls require approval.
Tool results are attached as artifacts.
```

## Phase 5 — Memory

Goal: add transparent, editable memory.

Memory tiers:

```text
workspace memory
user preference memory
skill memory
execution trace memory
```

Promotion pipeline:

```text
trace
→ candidate memory
→ evidence links
→ conflict check
→ approval or safe auto-policy
→ committed memory
→ Git audit
```

Exit criteria:

```text
No opaque memory writes.
Every memory has provenance.
Memory can be listed, edited, rejected, or reverted.
Workspace memory is isolated.
```

## Phase 6 — Learning and Skills

Goal: allow the system to improve workflows without self-expanding authority.

Skill rules:

```text
Skills may suggest new procedures.
Skills may not grant themselves permissions.
Skills may not bypass policy.
Skills must be versioned.
Skills must be inspectable.
```

Exit criteria:

```text
Successful workflows can be saved as skills.
Skills run only inside explicit capability scopes.
Users can disable or revert skills.
```

## Phase 7 — Council Mode

Goal: add multi-agent critique for high-stakes decisions.

Use cases:

```text
architecture decisions
financial analysis
career decisions
project risk review
strategic planning
```

Pattern:

```text
optimist
pessimist
risk analyst
domain expert
synthesizer
```

Rules:

```text
Council mode advises.
Council mode does not execute.
Dissent is preserved.
Assumptions are explicit.
Sources/artifacts are linked.
```

Exit criteria:

```text
The system can produce structured debate.
Consensus and dissent are both visible.
No action is taken without separate approval.
```

## Phase 8 — Distributed Sovereign Cortex

Goal: distribute the system across trusted personal infrastructure.

Components:

```text
EasyTier mesh
home server
laptop node
phone bridge
Cloudflare edge adapters
GitHub audit/sync
Solace event mesh
```

Exit criteria:

```text
Private services remain on private mesh.
Public edge services are thin bridges.
State is auditable and recoverable.
Agents can hibernate/resume safely.
```

## Non-Negotiable Engineering Rules

```text
No direct write without policy.
No durable write without patch or explicit safe policy.
No high-risk action without approval.
No memory promotion without provenance.
No tool call outside capability scope.
No hidden authority escalation.
No agent edits its own audit trail.
No background task exceeds budget envelope.
```

## Near-Term Priority Order

```text
1. Finish and merge MVP-0.2 task operations.
2. Link ROADMAP.md from README.
3. Add approval diff command.
4. Add event log JSONL.
5. Add workspace registry.
6. Add local FastAPI endpoint.
7. Add chat bridge.
```
