# Roadmap Status

Last updated after PR #25.

## Completed

```text
MVP-0.0 — Python local scaffold
MVP-0.1 — persisted approval requests
CI — Python test workflow
Approval integrity — stale patch protection
MVP-0.2 — deterministic task operations
MVP-0.3 — approval UX hardening
MVP-0.4 — local JSONL activity records
MVP-0.5 — workspace registry
```

## Current capability baseline

```text
The control plane can receive commands, select workspaces, read the vault, propose patches, save approval requests, manage approvals, protect stale approvals, commit changes to Git, and record command plus approval activity as JSONL.
```

## Current next roadmap item

```text
Phase 1 — Project-native operator
```

Immediate targets:

```text
project status reporting
project summary
risk summary
next-action recommendation
real-vault operating loop
```

## Known follow-up

```text
ROADMAP.md still needs an inline status refresh. This separate file exists because the large roadmap rewrite was blocked by the write-safety layer.
```
