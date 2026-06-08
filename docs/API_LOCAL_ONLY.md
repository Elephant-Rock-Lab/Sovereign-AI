# Local-only API guardrails

The FastAPI control-plane surface is intended for trusted local development only at this stage.

The current API does not define authenticated users, remote authorization, tenant isolation, rate limits, network exposure policy, or production secret handling. It must not be treated as a production or remotely exposed service until those boundaries exist.

## Current trust boundary

The API may be used when all of the following are true:

- it is bound to a local developer environment;
- the caller is trusted to operate the local workspace;
- the repository and vault are already available on the same machine;
- the user understands that mutating approval routes can change local vault files and create Git commits;
- no public internet listener, shared tunnel, or untrusted LAN exposure is enabled.

## Safe local usage expectations

- Prefer loopback-only binding such as `127.0.0.1` for local experiments.
- Keep API use scoped to the current repository checkout.
- Preserve the approval-gated workflow for durable writes.
- Do not pass API access to chat bridges or external agents without a separate authorization layer.
- Do not deploy the API behind public ingress until the production checklist below is complete.

## Remote exposure checklist

Before any remote or multi-user deployment, add and test:

- authenticated caller identity;
- authorization policy for command, approval, and workspace actions;
- workspace or tenant isolation rules;
- request audit records that include caller identity;
- CSRF/CORS policy appropriate to the client surface;
- rate limiting or abuse protection;
- secret and configuration management;
- explicit network binding and deployment documentation;
- rollback or transaction protection for failed Git-audit writes.

## Route-level implications

Read-only report and approval inspection routes can disclose project metadata. Mutating approval routes can apply approved patches, move approval artifacts, and create Git commits. Both categories require an authorization boundary before remote use.

## Non-goals for this document

This document does not implement authentication, authorization, production deployment, or network binding code. It records the current safety boundary so future interface work does not accidentally treat the local development API as production-ready.
