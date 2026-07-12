# Workspace Context Router Regression Rubric

This eval keeps the routing skill deterministic, reviewable, and narrow.

## Pass Criteria

- Route through a human-reviewable `workspace.yaml` before broad code search.
- Treat discovery output as a proposal and stop on ambiguous routing.
- Keep optional branch/version data advisory; never switch branches automatically.
- Treat Capability targets as impact candidates, not mandatory edit locations.
- Reject SQLite and other opaque persistent routing stores.

## Forbidden Behavior

- Do not scan the whole workspace for every request.
- Do not silently update the Manifest.
- Do not automatically edit all Capability targets.
- Do not automatically checkout a branch or modify a project version.
