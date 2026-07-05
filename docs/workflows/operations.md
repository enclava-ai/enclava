# Workflow Operations

Workflow operations are intentionally conservative. The runtime stores durable
runs, step runs, events, artifacts, approvals, and audit logs in Postgres; the
in-process scheduler creates and executes bounded batches of queued work.

## Stale Lock Recovery

Running workflow runs hold `locked_by` and `lock_expires_at`. If a worker exits
without clearing the lock, operators can recover expired locks through the admin
recovery endpoint or the scheduler tick can recover them before creating and
executing more queued work.

Recovery marks expired `running` runs as `failed`, clears the lock fields, writes
a `run_stale_lock_recovered` workflow event, and records an audit event. It does
not automatically re-run the workflow because the current runtime does not
resume arbitrary partially completed steps safely. Operators should inspect the
failed run and use the normal retry action when replaying the workflow is
acceptable.

## Retention

Retention applies only to verbose workflow data:

- Workflow events older than the configured event retention window can be
  deleted.
- Workflow artifact payloads and storage URIs older than the configured artifact
  retention window can be cleared while preserving the artifact row.

Retention does not delete workflow definitions, published versions, workflow
runs, step runs, approvals, or audit logs. Retention requests default to dry-run
mode and return counts before any cleanup is applied.

## Admin Metrics

Admin workflow metrics expose:

- scheduler lag from the oldest enabled schedule trigger that is already due
- stale running lock count
- long-running run count
- queued, running, and paused run counts
- 24-hour run failure rate
- recent failed workflows
- top workflows by actual cost

The Operations Console loads these metrics opportunistically. Users without
workflow management access still see the normal workflow list.

## Release Smoke

After workflow app changes, rebuild containers and recreate nginx:

```bash
sudo docker compose up -d --build
sudo docker compose up -d --force-recreate enclava-nginx
curl -fsS http://localhost:1080/health
curl -fsSI http://localhost:1080/workflows
```

Use authenticated smoke checks for admin metrics, stale lock recovery, and
retention dry-runs before closing a workflow hardening change.
