# Runbook: RDS PostgreSQL restore (automated backups / PITR)

**Status:** written ahead of the RDS instance itself — `infra/terraform`
is currently a scaffold with no resources (see its README). This runbook
documents the intended procedure and will be finalized (exact commands,
parameter names) once the Terraform RDS module exists and Production
automated backups + point-in-time recovery are actually enabled. Treat
the AWS CLI commands below as the expected shape, not yet verified
against a real instance.

## What "automated backups + PITR" gives you

RDS PostgreSQL, with `backup_retention_period > 0`:
- Takes a daily automated snapshot during the configured backup window.
- Continuously archives transaction logs, allowing restore to **any
  second** within the retention window (point-in-time recovery), not
  just to a snapshot boundary.
- Retention is planned at 7 days for nonprod, 14–35 days for Production
  (final number TBD when the Terraform module is written — driven by how
  far back a "we didn't notice for N days" incident could realistically
  go).

**Critical constraint:** RDS restore-from-backup and restore-to-point-in-time
both always create a **brand-new** DB instance — there is no in-place
restore. The old (possibly corrupted) instance is never overwritten
automatically. This is why every restore is really a two-phase
operation: *restore*, then a deliberate *cutover* (or, for
investigation-only restores, no cutover at all).

## When to use this runbook

- Data corruption or an incorrect bulk write/delete in Production that
  needs to be inspected or reversed (e.g. a bad migration, a bad admin
  action, an application bug that wrote wrong data at scale).
- Verifying disaster-recovery readiness (the periodic nonprod restore
  test below).
- **Not** for routine rollback of a single order/mapping — use the
  existing audit trail (`order_events`, `audit_events`,
  `supplier_attempts`) and a targeted manual fix first; a full restore is
  a last resort because of the blast radius (see "What you lose" below).

## What you lose

Any restore target is necessarily *before* the incident. Restoring to
time T discards all writes between T and now on the restored copy —
that's the whole database, not just the bad rows. For Production, this
means real customer orders/payments placed after T would not exist on
the restored instance. Before cutting Production over to a restored
instance, this runbook's cutover step requires an explicit
reconciliation pass (see step 5) to avoid silently losing legitimate
post-T orders.

## Procedure

### 1. Identify the target restore time

Pick the latest point *before* the corrupting event, in UTC. Cross-check
against `order_events`/`audit_events`/CloudWatch alarms to bound it — err
slightly earlier rather than later; a slightly-stale restore is
recoverable via reconciliation (step 5), a too-late one may include the
bad write.

### 2. Restore to a new instance (never in place)

```sh
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier timechain-prod \
  --target-db-instance-identifier timechain-prod-restore-YYYYMMDD-HHMM \
  --restore-time 2026-08-14T03:00:00Z \
  --db-subnet-group-name <private-db-subnet-group> \
  --vpc-security-group-ids <db-security-group-id> \
  --no-multi-az \
  --no-publicly-accessible
```

For "restore into nonprod" specifically (the eventual test described
below), instead restore from a Production snapshot into the **nonprod**
VPC/subnet group/security groups, on a nonprod-sized instance class —
never reuse Production networking for a test restore.

This takes some time to provision (minutes, scales with data size).
Poll with `aws rds describe-db-instances --db-instance-identifier
timechain-prod-restore-YYYYMMDD-HHMM --query 'DBInstances[0].DBInstanceStatus'`
until `available`.

### 3. Verify the restored data

Connect to the restored instance directly (not through the application)
and confirm:
- The suspected bad write/deletion is absent.
- Row counts on key tables (`orders`, `order_items`, `payments`) are
  sane relative to the target time.
- `alembic current` on the restored instance matches a real migration
  head — a restore mid-migration is a red flag, not something to paper
  over.

### 4. Decide: investigation-only, or full cutover?

- **Investigation-only** (most common): extract the specific rows/data
  needed (e.g. `pg_dump --table=orders --where=...`, or a targeted
  `SELECT`), apply a manual, reviewed fix to the live Production
  database, then **terminate the restored instance**. No application
  downtime, no cutover risk.
- **Full cutover** (only for the "the live database is unusable" case):
  continue to step 5.

### 5. Cutover (full-restore case only)

1. Put the app in maintenance mode: `CHECKOUT_ENABLED=false` (see
   `.env.example` / Secrets Manager) so no new orders are accepted
   during cutover.
2. **Reconciliation pass**: diff orders/payments on the live (pre-cutover)
   instance against the restored instance for the window between the
   restore time and now. Any real customer order in that window must be
   manually replayed onto the restored instance before it becomes
   authoritative — this is the step that prevents silently losing
   legitimate orders (see "What you lose" above).
3. Update the `DATABASE_URL` secret in AWS Secrets Manager to point at
   the restored instance's endpoint.
4. Restart the `api` and `worker` ECS services (force new deployment) so
   they pick up the new connection string.
5. Verify `/healthz`, then a single real checkout end-to-end in a
   controlled way before setting `CHECKOUT_ENABLED=true` again.
6. Rename instances once confirmed stable: the restored instance takes
   over the `timechain-prod` identifier (or DNS/connection string is
   repointed permanently); the old instance is kept, stopped (not
   deleted), for a defined retention window in case the cutover itself
   needs to be reversed.

## Testing restore into nonprod

Do this periodically (cadence TBD — proposed quarterly, or after any
material schema change) so the procedure above is proven, not
theoretical:

1. Take (or use the latest automated) Production snapshot.
2. Restore it into the **nonprod** account/VPC per step 2 above.
3. Run `alembic current` and a handful of read-only sanity queries
   against it.
4. Confirm nonprod application code can connect to it (read-only smoke
   test, not a full cutover rehearsal — nonprod already has its own
   database for actual nonprod traffic).
5. Terminate the test-restore instance immediately after — it is not a
   long-lived resource and should not linger accruing cost or becoming a
   second copy of Production data to secure.
6. Record the date and any friction encountered in this file's "Test
   log" section below, so drift between this runbook and reality gets
   caught early rather than at incident time.

## Test log

| Date | Restored from | Result | Notes |
| --- | --- | --- | --- |
| _(none yet — RDS doesn't exist)_ | | | |
