![Project Banner](https://github.com/Elephant-Rock-Lab/Sovereign-AI/blob/ef51175e54ef712ba235b58d1b3e74e44ed14507/Banner.png)

# Sovereign AI MVP-0

A local-first, Python control-plane scaffold for building **Sovereign AI**: a sovereign personal AI system that operates against auditable local workspaces instead of acting as an unconstrained chatbot.

MVP-0 proves the first safe loop:

```text
User command
→ local orchestrator
→ workspace selection
→ Obsidian-compatible Markdown/YAML vault read
→ patch proposal
→ policy check
→ persisted approval request
→ approval or rejection
→ vault write
→ Git audit commit
→ user response
```

This repository intentionally starts small. It does **not** give agents browser, shell, email, calendar, or autonomous skill-installation authority yet. Those capabilities should be added later behind capability tokens, sandboxes, event queues, and explicit approval policy.

For the long-term project sequence, see [ROADMAP.md](ROADMAP.md).

---

## Why this exists

The long-term Sovereign AI architecture combines local agents, workspace memory, project-native execution, event routing, and Git-backed auditability. The risk is trying to wire every component together before the control plane exists.

This MVP focuses on the core invariant:

> An AI may propose durable changes, but the control plane decides whether those changes are allowed, whether approval is required, and how the change is audited.

MVP-0 is therefore the smallest useful seed of the larger system.

---

## Current capabilities

- Reads a project workspace from `vault/<workspace>/`.
- Parses Obsidian-compatible Markdown files with YAML frontmatter.
- Produces patches instead of writing directly by default.
- Evaluates patches through a local policy engine.
- Saves human approval requests under `approval_requests/`.
- Approves or rejects persisted approval requests from the CLI.
- Guards approvals against stale workspace state.
- Commits approved changes to Git.
- Emits canonical event envelopes that can later map onto Solace/A2A topics.
- Runs Python tests in GitHub Actions CI.

---

## Repository layout

```text
sovereign-ai/
  src/sovereign_cortex/
    __init__.py
    approvals.py       # persisted approval queue and conflict checks
    cli.py             # CLI entrypoint
    events.py          # canonical event envelope and task/patch models
    git_audit.py       # Git initialization and commit wrapper
    orchestrator.py    # local command → patch → policy workflow
    policy.py          # capability token and approval policy logic
    vault.py           # Markdown/YAML vault reader and writer
    workspace.py       # workspace registry and scoped capability issuance

  vault/demo-project/
    tasks/
      competitor-research.md
      launch-website.md

  docs/
    ARCHITECTURE.md

  tests/
    test_approvals.py
    test_orchestrator.py
    test_policy.py

  ROADMAP.md
  pyproject.toml
  README.md
```

---

## Requirements

- Python 3.11+
- Git
- A POSIX-like shell for the commands below

Python dependencies are declared in `pyproject.toml`.

---

## Quick start

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run the patch-first demo:

```bash
python -m sovereign_cortex.cli \
  "Move the website launch task to next Friday and explain the dependency impact" \
  --date 2026-06-05
```

Expected result:

- an approval request is saved;
- no project file is changed yet;
- a unified diff is printed;
- events are printed at the end.

Approve the saved request:

```bash
cortex approvals list
cortex approvals show <approval-id>
cortex approvals approve <approval-id>
```

Reject a saved request:

```bash
cortex approvals reject <approval-id> --reason "Not now"
```

For deterministic demos or trusted local development, you can still apply immediately:

```bash
python -m sovereign_cortex.cli \
  "Move the website launch task to next Friday and explain the dependency impact" \
  --date 2026-06-05 \
  --auto-approve
```

---

## Approval model

Approval artifacts are stored locally under:

```text
approval_requests/
  pending/*.json
  approved/*.json
  rejected/*.json
```

Approval records include:

```text
approval_id
status
workspace
command_text
correlation_id
patch
policy_decision
commit_hash
rejection_reason
```

Approving a request applies the patch and commits the changed workspace file. Rejecting a request moves the artifact without mutating project files.

Approval requests are protected against stale workspace state:

- update patches require the current file content to match the saved `patch.before` baseline;
- create patches require the target file not to exist;
- conflicts leave the approval request pending and print a clean CLI error.

---

## Safety model

MVP-0 is **patch-first**.

The orchestrator creates a `ProposedPatch`, then asks the `PolicyEngine` whether the patch is allowed and whether approval is required.

A patch is rejected if:

- its target path escapes the workspace;
- its target path is outside the token's write scope;
- the capability token has expired.

A patch requires approval if:

- it is marked `requires_human_approval=True`;
- it is medium or high risk.

The non-negotiable rule is:

```text
No durable write without policy, approval, and audit.
```

---

## Event model

Events use the `EventEnvelope` model in `events.py`.

Current event types include:

```text
CommandReceived
TaskPlanned
PolicyChecked
PatchProposed
ApprovalRequested
PatchApproved
PatchRejected
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

The schema is intentionally compatible with a future Solace/A2A event layer.

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

The vault format is plain Markdown with YAML frontmatter. This keeps project state human-readable, Git-friendly, and compatible with Obsidian-style workflows.

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

GitHub Actions also runs the Python test suite on pushes to `main` and pull requests.

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

The roadmap is maintained in [ROADMAP.md](ROADMAP.md).

Near-term priorities:

```text
1. Finish and merge MVP-0.2 task operations.
2. Add approval diff command.
3. Add event log JSONL.
4. Add workspace registry.
5. Add local FastAPI endpoint.
6. Add chat bridge.
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
