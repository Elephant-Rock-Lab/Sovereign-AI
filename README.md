# Sovereign AI MVP-0

A local-first, Python-only control-plane scaffold for building the **Sovereign AI**: a sovereign personal AI system that operates against auditable local workspaces instead of acting as an unconstrained chatbot.

MVP-0 proves the first safe loop:

```text
User command
→ local orchestrator
→ workspace selection
→ Obsidian-compatible Markdown/YAML vault read
→ patch proposal
→ policy check
→ approval gate
→ vault write
→ Git audit commit
→ user response
```

This repository intentionally starts small. It does **not** give agents browser, shell, email, calendar, or autonomous skill-installation authority yet. Those capabilities should be added later behind capability tokens, sandboxes, event queues, and explicit approval policy.

---

## Why this exists

The long-term Sovereign Cortex architecture combines local agents, workspace memory, project-native execution, event routing, and Git-backed auditability. The risk is trying to wire every component together before the control plane exists.

This MVP focuses on the core invariant:

> An AI may propose durable changes, but the control plane decides whether those changes are allowed, whether approval is required, and how the change is audited.

MVP-0 is therefore the smallest useful seed of the larger system.

---

## Current capabilities

- Reads a project workspace from `vault/<workspace>/`.
- Parses Obsidian-compatible Markdown files with YAML frontmatter.
- Recognizes a narrow demo command: moving the website launch task to next Friday.
- Produces a patch instead of writing directly by default.
- Evaluates the patch through a local policy engine.
- Applies the patch only when `--auto-approve` is supplied.
- Commits approved changes to Git.
- Emits canonical event envelopes that can later map onto Solace/A2A topics.

---

## Repository layout

```text
sovereign-cortex-mvp/
  src/sovereign_cortex/
    __init__.py
    cli.py             # CLI entrypoint for the local demo loop
    events.py          # canonical event envelope and task/patch models
    git_audit.py       # Git initialization and commit wrapper
    orchestrator.py    # local command → patch → policy → apply workflow
    policy.py          # capability token and approval policy logic
    vault.py           # Markdown/YAML vault reader and writer
    workspace.py       # workspace registry and scoped capability issuance

  vault/demo-project/
    tasks/
      competitor-research.md
      launch-website.md

  docs/
    ARCHITECTURE.md    # MVP scope and future integration notes

  tests/
    test_orchestrator.py
    test_policy.py

  pyproject.toml
  README.md
```

---

## Requirements

- Python 3.11+
- Git
- A POSIX-like shell for the commands below

Python dependencies are declared in `pyproject.toml`:

- `pydantic`
- `PyYAML`

---

## Quick start

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run the safe, patch-only demo:

```bash
python -m sovereign_cortex.cli \
  "Move the website launch task to next Friday and explain the dependency impact" \
  --date 2026-06-05
```

Expected result:

- status: `proposed`
- no file is changed
- a unified diff is printed
- events are printed at the end

Apply the proposed patch and create a Git audit commit:

```bash
python -m sovereign_cortex.cli \
  "Move the website launch task to next Friday and explain the dependency impact" \
  --date 2026-06-05 \
  --auto-approve
```

You can also use the installed console script:

```bash
cortex \
  "Move the website launch task to next Friday and explain the dependency impact" \
  --date 2026-06-05
```

---

## Demo command behavior

The current orchestrator is deliberately narrow. It looks for a command containing:

```text
launch
next friday
```

Then it reads:

```text
vault/demo-project/tasks/launch-website.md
```

It updates the YAML frontmatter:

```yaml
due: 2026-06-12
updated_by: sovereign-cortex-mvp
last_change_reason: User requested moving launch task to next Friday.
```

It also updates the `## Cortex Notes` section with a dependency-impact note based on the task metadata.

This narrow behavior is intentional. The first milestone is not natural-language breadth; it is proving the safe control-plane loop.

---

## Safety model

MVP-0 is **patch-first**.

The orchestrator does not directly mutate the workspace during normal execution. It creates a `ProposedPatch`, then asks the `PolicyEngine` whether the patch is allowed and whether approval is required.

A patch is rejected if:

- its target path escapes the workspace;
- its target path is outside the token's write scope;
- the capability token has expired.

A patch requires approval if:

- it is marked `requires_human_approval=True`;
- it is medium or high risk.

For MVP-0, `--auto-approve` is the temporary approval mechanism. The next milestone should replace that with persisted approval requests.

---

## Event model

Events use the `EventEnvelope` model in `events.py`.

Current event types:

```text
CommandReceived
TaskPlanned
PolicyChecked
PatchProposed
PatchApproved
PatchApplied
AuditCommitted
TaskCompleted
TaskRejected
```

Each event includes:

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

The schema is intentionally compatible with a future Solace/A2A event layer. In MVP-0 the events are local objects; later they can be serialized and published onto topics such as:

```text
user/{channel}/command
task/{workspace}/created
task/{workspace}/approved
task/{workspace}/completed
artifact/{workspace}/created
memory/{workspace}/candidate
system/heartbeat
```

---

## Workspace and vault model

A workspace is a scoped project environment.

In MVP-0, the demo workspace is:

```text
vault/demo-project/
```

The current workspace token allows reads and writes under:

```text
tasks/
notes/
memory/
```

The vault format is plain Markdown with YAML frontmatter. Example:

```markdown
---
id: launch-website
title: Launch Website
status: planned
due: 2026-06-05
dependencies:
  - competitor-research
owner: local-user
---
# Launch Website

Publish the landing page, verify analytics, and send the launch announcement.
```

This keeps the project state human-readable, Git-friendly, and compatible with Obsidian-style workflows.

---

## Running tests

Install test dependencies if needed:

```bash
pip install pytest
```

Run:

```bash
pytest
```

Current tests cover:

- policy rejection for workspace path escape attempts;
- policy approval behavior for scoped task patches;
- orchestrator patch proposal for the launch task demo.

---

## Development principles

1. **Control plane before autonomy**  
   No broad agent authority should be added until policy, approval, audit, and revocation are explicit.

2. **Patch before write**  
   Agents should propose changes before mutating durable state.

3. **Workspace isolation**  
   Every project should have its own files, memory, permissions, and future skill set.

4. **Git as audit log**  
   Durable changes should produce reviewable diffs and reversible commits.

5. **Capability-based access**  
   Agents should receive scoped, short-lived permissions instead of ambient authority.

6. **Local-first by default**  
   Private project state should stay local unless explicitly routed elsewhere.

---

## Roadmap

### MVP-0.1 — persisted approval requests

Replace `--auto-approve` with approval artifacts:

```text
approval_requests/
  pending/*.json
  approved/*.json
  rejected/*.json
```

Target flow:

```text
command
→ patch proposed
→ approval request saved
→ user approves by ID
→ patch applied
→ Git commit
```

### MVP-0.2 — broader project operations

Add support for:

- creating a new task;
- marking a task done;
- changing task owner;
- shifting due dates by relative intervals;
- listing dependency impacts without applying changes.

### MVP-0.3 — local API

Add a FastAPI service around the orchestrator:

```text
POST /commands
GET /approvals
POST /approvals/{id}/approve
POST /approvals/{id}/reject
GET /events/{correlation_id}
```

### MVP-1 — Solace event fabric

Replace direct local calls with event publication/subscription:

```text
CLI/API/QwenPaw bridge
→ command event
→ orchestrator worker
→ policy event
→ approval event
→ patch event
→ audit event
```

### MVP-2 — chat bridge

Add a thin QwenPaw or Telegram bridge:

```text
chat message
→ command event
→ approval response
→ chat reply
```

The bridge should not perform heavy reasoning or direct writes.

### MVP-3 — sandboxed effectors

Add OpenClaw-style tools only behind scoped capability tokens and sandboxing:

- browser research;
- safe shell commands;
- file operations;
- external API calls.

### MVP-4 — memory and learning

Add Hermes/ML-Master-style learning as candidate generation, not silent self-modification:

```text
execution trace
→ candidate lesson
→ evidence links
→ conflict check
→ approval policy
→ committed workspace memory
```

---

## Non-goals for MVP-0

MVP-0 does not include:

- autonomous browser control;
- shell execution tools;
- email or calendar writes;
- Solace broker integration;
- Cloudflare Workers;
- QwenPaw/Telegram bridge;
- Hermes skill evolution;
- ML-Master memory consolidation;
- multi-agent roundtable reasoning;
- vector databases;
- production authentication.

Those are later phases, after the control-plane contract is stable.

---

## Suggested next issue

**Implement persisted approval requests.**

Acceptance criteria:

- `cortex "..."` saves a pending approval request instead of only printing a diff.
- `cortex approvals list` shows pending approvals.
- `cortex approvals approve <id>` applies the patch and commits it.
- `cortex approvals reject <id>` marks the request rejected without writing files.
- Approval artifacts are stored as JSON and include the patch, policy decision, event correlation ID, timestamp, and workspace.
