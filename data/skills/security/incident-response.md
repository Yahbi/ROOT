---
name: Incident Response
description: Detection, containment, eradication, recovery, and post-mortem procedures
version: "1.0.0"
author: ROOT
tags: [security, incident-response, DFIR, post-mortem, SOC]
platforms: [all]
---

# Incident Response

Structured approach to detecting, containing, and recovering from security incidents.

## Detection Phase

### Indicators of Compromise (IoCs)
- Unexpected outbound connections to unknown IPs (check netstat, firewall logs)
- Anomalous login patterns: impossible travel, credential stuffing bursts, off-hours access
- File integrity changes: unexpected modifications to binaries, configs, or cron jobs
- Database query anomalies: bulk SELECT on PII tables, DROP/ALTER from application accounts
- Resource spikes: sudden CPU/memory/network usage without corresponding traffic increase

### Monitoring Stack
| Layer | Tool | What It Catches |
|-------|------|-----------------|
| Network | Suricata, Zeek | C2 traffic, lateral movement, data exfiltration |
| Host | OSSEC, osquery | File changes, process anomalies, rootkits |
| Application | Structured logs + SIEM | Auth failures, injection attempts, API abuse |
| Cloud | CloudTrail, GuardDuty | IAM changes, S3 exposure, unusual API calls |

## Containment

### Immediate Actions (First 15 Minutes)
1. **Isolate** affected systems from the network (do NOT power off -- preserve memory)
2. **Revoke** compromised credentials: rotate API keys, invalidate sessions, disable accounts
3. **Block** known attacker IPs at WAF/firewall level
4. **Preserve** evidence: snapshot disk images, capture memory dumps, export logs
5. **Notify** incident commander and establish communication channel (dedicated Slack/Teams)

### Containment Decision Matrix
| Scenario | Action | Risk |
|----------|--------|------|
| Single compromised host | Network isolate, image disk | Low -- limited blast radius |
| Compromised API key | Rotate key, audit usage logs | Medium -- check what was accessed |
| Database breach | Restrict DB access, snapshot, audit queries | High -- PII exposure |
| Supply chain compromise | Pin known-good dependency versions, block CI | Critical -- wide blast radius |

## Eradication

### Root Cause Analysis
- Trace the attack vector: phishing email, vulnerable dependency, exposed endpoint
- Identify persistence mechanisms: cron jobs, SSH keys, backdoor accounts, modified binaries
- Verify eradication: re-scan with updated signatures, check all similar systems
- Patch the vulnerability that enabled initial access

## Recovery

### Return to Service
1. Restore from known-good backups (verify backup integrity with checksums)
2. Rebuild compromised systems from infrastructure-as-code (never trust a cleaned system)
3. Deploy with enhanced monitoring: lower alert thresholds for 30 days
4. Staged rollout: canary first, then gradual traffic increase
5. Verify application behavior matches pre-incident baselines

## Post-Mortem Template

```markdown
# Incident Post-Mortem: [INCIDENT-ID]
## Summary: One-sentence description of what happened
## Timeline: Chronological events with UTC timestamps
## Impact: Users affected, data exposed, financial cost, downtime duration
## Root Cause: Technical explanation of the vulnerability exploited
## What Went Well: Detection speed, containment effectiveness, communication
## What Went Poorly: Gaps in monitoring, slow response, missing runbooks
## Action Items:
- [ ] [P0] Patch vulnerability X (owner: @engineer, due: 48h)
- [ ] [P1] Add detection rule for attack pattern Y (owner: @security, due: 1 week)
- [ ] [P2] Update runbook for scenario Z (owner: @oncall, due: 2 weeks)
## Lessons Learned: What changes to prevent recurrence
```

## Severity Classification

| Level | Criteria | Response Time | Escalation |
|-------|----------|---------------|------------|
| SEV-1 | Data breach, full system compromise | Immediate, all-hands | CISO + Legal + Exec |
| SEV-2 | Partial compromise, active attacker | < 1 hour | Security team + Engineering lead |
| SEV-3 | Attempted attack, no breach confirmed | < 4 hours | Security team |
| SEV-4 | Vulnerability discovered, no exploit | < 24 hours | Ticket + scheduled fix |
