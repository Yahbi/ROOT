---
name: Disaster Recovery
description: RPO/RTO targets, backup verification, failover procedures, runbook template
version: "1.0.0"
author: ROOT
tags: [infrastructure, disaster-recovery, backup, failover, RPO, RTO, runbook]
platforms: [all]
---

# Disaster Recovery

Plan, test, and execute recovery procedures to minimize data loss and downtime during outages.

## RPO and RTO

### Definitions
- **RPO (Recovery Point Objective)**: Maximum acceptable data loss measured in time. RPO of 1 hour means you can lose up to 1 hour of data.
- **RTO (Recovery Time Objective)**: Maximum acceptable downtime. RTO of 30 minutes means the system must be operational within 30 minutes.

### Tier Classification
| Tier | RPO | RTO | Strategy | Cost |
|------|-----|-----|----------|------|
| Tier 1 (Critical) | 0 (zero data loss) | < 15 min | Active-active, synchronous replication | $$$$$ |
| Tier 2 (Important) | < 1 hour | < 1 hour | Warm standby, async replication | $$$ |
| Tier 3 (Standard) | < 24 hours | < 4 hours | Cold standby, daily backups | $$ |
| Tier 4 (Non-critical) | < 7 days | < 24 hours | Backup restore from archive | $ |

### Setting Targets
- Calculate cost of downtime per hour (revenue loss + reputation + SLA penalties)
- Compare against cost of achieving each RPO/RTO tier
- Different systems can have different tiers (auth = Tier 1, analytics = Tier 3)

## Backup Strategy

### 3-2-1 Rule
- **3** copies of data (production + 2 backups)
- **2** different storage media (local disk + cloud object storage)
- **1** offsite copy (different region or provider)

### Backup Verification
```bash
#!/bin/bash
# Automated backup verification (run weekly)
BACKUP_FILE="$1"
TEMP_DB="/tmp/verify_$(date +%s).db"

# 1. Verify file integrity
sha256sum --check "${BACKUP_FILE}.sha256" || { echo "CHECKSUM FAILED"; exit 1; }

# 2. Restore to temporary location
cp "$BACKUP_FILE" "$TEMP_DB"

# 3. Run integrity check
RESULT=$(sqlite3 "$TEMP_DB" "PRAGMA integrity_check;")
[ "$RESULT" = "ok" ] || { echo "INTEGRITY FAILED: $RESULT"; exit 1; }

# 4. Verify data recency (last record within expected window)
LAST_TS=$(sqlite3 "$TEMP_DB" "SELECT MAX(created_at) FROM memories;")
echo "Last record: $LAST_TS"

# 5. Cleanup
rm "$TEMP_DB"
echo "Backup verification PASSED"
```

### Untested Backups Are Not Backups
- Schedule monthly restore drills (restore backup to staging, verify data)
- Automate verification: checksum, integrity check, row count comparison
- Test full recovery procedure, not just file restoration
- Document time taken for each restore (compare against RTO target)

## Failover Procedures

### Database Failover
| Database | Failover Method | Automatic? | Data Loss Risk |
|----------|----------------|------------|----------------|
| PostgreSQL + Patroni | Promotes standby to primary | Yes | Minimal (async lag) |
| SQLite + Litestream | Restore from S3 replica | Manual | Seconds of data |
| Redis Sentinel | Promotes replica to primary | Yes | Async replication lag |
| Managed (RDS, Cloud SQL) | Multi-AZ automatic failover | Yes | Zero (synchronous) |

### Application Failover Checklist
1. DNS failover: update records or use health-check-based routing (Route 53, Cloudflare)
2. Connection strings: applications must reconnect to new primary (connection poolers help)
3. Cache warming: new instances may have cold caches (expect higher origin load)
4. Queue replay: verify no messages were lost during failover window
5. Verify: run smoke tests against the failover environment before routing traffic

## Runbook Template

```markdown
# Runbook: [System] Recovery

## Trigger Conditions
- [What alerts or symptoms trigger this runbook]

## Prerequisites
- Access to: [list accounts, VPNs, tools needed]
- Credentials: [where to find them, NOT the credentials themselves]

## Steps
1. **Assess**: Check [monitoring dashboard URL] to confirm scope
2. **Notify**: Post in #incidents channel, page on-call if SEV-1/2
3. **Contain**: [Specific containment steps]
4. **Recover**:
   a. [Step-by-step recovery commands]
   b. [Expected output at each step]
   c. [What to do if a step fails]
5. **Verify**: Run smoke tests [URL/command]
6. **Communicate**: Update status page, notify stakeholders

## Rollback
- [How to undo the recovery if it makes things worse]

## Post-Recovery
- [ ] Schedule post-mortem within 48 hours
- [ ] Update this runbook with any discoveries
- [ ] Verify monitoring caught the issue (add alerts if not)

## Contacts
- Primary on-call: [rotation link]
- Escalation: [who to contact if on-call cannot resolve]
- Vendor support: [support ticket URLs, SLA response times]
```

## DR Testing Schedule

| Test Type | Frequency | Scope | Duration |
|-----------|-----------|-------|----------|
| Backup restore | Monthly | Single database to staging | 1 hour |
| Failover drill | Quarterly | Full stack failover to secondary | Half day |
| Chaos engineering | Monthly | Kill random components, verify recovery | 2 hours |
| Full DR exercise | Annually | Complete recovery from scratch in new region | Full day |
