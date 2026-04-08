---
name: Automation Mindset
description: ROI calculation, scripting thresholds, maintenance cost, documentation
version: "1.0.0"
author: ROOT
tags: [productivity, automation, scripting, ROI, efficiency]
platforms: [all]
---

# Automation Mindset

Decide what to automate, when to automate it, and how to maintain automation sustainably.

## ROI Calculation

### The XKCD-Informed Decision
Before automating, calculate whether it is worth the investment:

```
Time saved = frequency × time_per_occurrence × expected_lifetime
Time to automate = development_time + testing_time + documentation_time

ROI positive when: time_saved > time_to_automate × 1.5
(1.5x multiplier accounts for maintenance)
```

### Quick Reference Table
| Frequency | Time Saved Per Run | Automate If Build Time < |
|-----------|-------------------|--------------------------|
| Daily | 5 minutes | 2 days |
| Daily | 30 minutes | 2 weeks |
| Weekly | 15 minutes | 2 days |
| Weekly | 1 hour | 1 week |
| Monthly | 30 minutes | 4 hours |
| Monthly | 4 hours | 1 week |
| Yearly | 1 hour | Not worth it (document instead) |

### Hidden Benefits (Not in the Math)
- Reduced error rate (humans make mistakes on repetitive tasks)
- Reduced context switching (manual tasks interrupt deep work)
- Knowledge preservation (the script is documentation)
- Scalability (manual process that works for 10 items breaks at 1,000)
- Delegation (automated tasks can be triggered by anyone, not just the expert)

## Scripting Thresholds

### Level 0: Document It
- Task is rare (< monthly) or one-time
- Write a step-by-step checklist in a runbook
- Future you (or a teammate) can follow the steps
- Cost: 15 minutes. Value: prevents "how did we do this last time?"

### Level 1: One-Liner or Alias
```bash
# If you type it more than 3 times, make an alias
alias deploy="git push origin main && ssh prod 'cd /app && git pull && systemctl restart app'"
alias dbbackup="sqlite3 data/memory.db '.backup /backup/memory_$(date +%Y%m%d).db'"
```

### Level 2: Shell Script
```bash
#!/bin/bash
# If it has 3+ steps or any conditional logic, make a script
set -euo pipefail  # Exit on error, undefined var, pipe failure

DB_PATH="${1:?Usage: backup.sh <db_path>}"
BACKUP_DIR="/backup/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"
sqlite3 "$DB_PATH" ".backup ${BACKUP_DIR}/$(basename $DB_PATH)"
echo "Backup completed: ${BACKUP_DIR}/$(basename $DB_PATH)"
```

### Level 3: Full Automation
- Task runs on a schedule (cron, systemd timer, CI/CD)
- Includes error handling, logging, alerting on failure
- Tested and documented
- Has a monitoring dashboard or health check

### Decision Criteria
| Signal | Action |
|--------|--------|
| Done it manually 3 times | Write a script (Level 2) |
| Script runs successfully 5 times | Schedule it (Level 3) |
| Multiple people need to run it | Add to CI/CD or shared tooling |
| Error-prone manual steps | Automate regardless of frequency |
| Involves credentials | Automate to avoid credential exposure |

## Maintenance Cost

### The Hidden Tax of Automation
Every automated process requires ongoing maintenance:
- Dependencies update and break things
- Infrastructure changes invalidate assumptions
- Edge cases emerge over time
- Someone must respond when the automation fails

### Keeping Maintenance Low
- Use standard tools (cron, systemd, CI/CD) over custom schedulers
- Fail loudly: if automation breaks, alert immediately (silent failure is worse than no automation)
- Idempotent scripts: safe to re-run without side effects
- Health checks: script reports success/failure, monitored externally
- Simple > clever: a 10-line bash script beats a 200-line Python script for simple tasks

### Automation Debt
- Review automated processes quarterly: still needed? Still working correctly?
- Delete automations that no longer serve a purpose (reduce maintenance surface)
- Monitor execution frequency: if a scheduled task never fires, it might be misconfigured

## Documentation for Automation

### Every Script Needs
```bash
#!/bin/bash
# WHAT: Backs up all SQLite databases to /backup/ with date prefix
# WHY:  Disaster recovery — restores are tested monthly
# WHEN: Runs daily at 02:00 via cron (see: crontab -l)
# WHO:  Contact: @ops-team
# DEPS: sqlite3, /backup/ mount point
# ARGS: None (uses hardcoded paths)
# EXIT: 0 = success, 1 = backup failed, 2 = verification failed
```

### Runbook for Manual Fallback
- Every automated process should have a manual fallback documented
- "If the backup script fails, run these 3 commands manually"
- This ensures the task can still be completed during automation outages
- The manual steps also serve as documentation of what the automation does
