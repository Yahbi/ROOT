---
name: Security Monitoring
description: Design and operate security monitoring, SIEM, log aggregation, and threat detection systems
category: security
difficulty: advanced
version: "1.0.0"
author: ROOT
tags: [security, monitoring, SIEM, threat-detection, log-analysis, SOC, detection-engineering]
platforms: [all]
---

# Security Monitoring

Build comprehensive visibility into your environment to detect threats, investigate incidents, and demonstrate compliance.

## Monitoring Architecture

```
Log Sources          Collection           SIEM/Analysis         Response
─────────────        ──────────           ─────────────         ────────
Applications    →    Agents (Beats,   →   Elasticsearch/    →   Alerts
Network devices      Fluentd)             Splunk/Sentinel       Tickets
Cloud APIs      →    Log forwarding   →   Correlation rules →   Automated SOAR
Endpoints       →    API polling          Threat Intel          Incident response
Auth systems    →    Kafka pipeline       ML detection
```

## Log Collection Strategy

### What to Collect

| Source | Events | Priority |
|--------|--------|----------|
| Authentication systems | Login success/fail, MFA, password changes | Critical |
| API gateways | All requests with user, status, latency | Critical |
| Network firewalls | Accept/deny with src/dst, port, bytes | High |
| DNS | All queries per host | High |
| Endpoint (EDR) | Process creation, file writes, network connections | High |
| Cloud APIs | All management plane calls (CloudTrail, GCP Audit) | Critical |
| Database | Authentication, privilege changes, bulk queries | High |
| CI/CD pipeline | Build triggers, deployments, secret access | Medium |

### Log Format Standardization (ECS — Elastic Common Schema)
```json
{
  "@timestamp": "2024-01-15T10:23:45.123Z",
  "event": {
    "kind": "event",
    "category": "authentication",
    "type": "start",
    "outcome": "failure"
  },
  "user": {
    "name": "john.smith@company.com",
    "id": "user_123"
  },
  "source": {
    "ip": "203.0.113.45",
    "geo": {"country_iso_code": "RU"}
  },
  "service": {
    "name": "api-gateway",
    "environment": "production"
  },
  "event.reason": "Invalid password",
  "tags": ["auth", "production"]
}
```

## Detection Engineering

### Detection Model Tiers
| Tier | Type | Example | False Positive Rate |
|------|------|---------|-------------------|
| 0 | Signature | Known malware hash | Very Low |
| 1 | Rule-based | 5 failed logins → lockout alert | Low-Medium |
| 2 | Behavioral | User logging in from new country | Medium |
| 3 | ML/Statistical | Anomalous data transfer volume | Higher |

### Detection Rule Framework (Sigma)
```yaml
title: Brute Force Login Attempt
id: a2f68e0e-a2c0-4cf6-bc9b-123abc456def
description: Detect multiple failed login attempts from single IP
status: production
logsource:
  category: authentication
  service: api-gateway
detection:
  selection:
    event.outcome: failure
    event.category: authentication
  timeframe: 5m
  condition: selection | count(user.name) by source.ip > 10
level: high
tags:
  - attack.credential_access
  - attack.T1110.003   # MITRE ATT&CK — Password Spraying
falsepositives:
  - Misconfigured application with incorrect credentials
  - Automated testing without throttling
```

### MITRE ATT&CK Coverage Mapping
Map every detection rule to ATT&CK techniques to identify coverage gaps:

```
Initial Access   → Monitor: phishing emails, exposed services
Execution        → Monitor: script execution, scheduled tasks
Persistence      → Monitor: new accounts, cron jobs, startup modifications
Privilege Escalation → Monitor: sudo usage, SUID execution, token manipulation
Defense Evasion  → Monitor: log clearing, tool usage, obfuscated commands
Credential Access → Monitor: LSASS access, keylogger, password spraying
Discovery        → Monitor: network scans, AD queries, cloud enumeration
Lateral Movement → Monitor: remote execution, credential reuse across hosts
Collection       → Monitor: bulk file reads, clipboard access, screen capture
Exfiltration     → Monitor: large outbound transfers, DNS tunneling, cloud uploads
```

## Critical Security Use Cases

### Impossible Travel Detection
```python
from geopy.distance import geodesic
from datetime import datetime

def detect_impossible_travel(events: list[dict]) -> list[dict]:
    """Flag logins from geographically impossible locations."""
    suspicious = []
    by_user = group_by_user(events)

    for user, user_events in by_user.items():
        sorted_events = sorted(user_events, key=lambda e: e["timestamp"])

        for i in range(1, len(sorted_events)):
            prev = sorted_events[i - 1]
            curr = sorted_events[i]

            time_diff_hours = (curr["timestamp"] - prev["timestamp"]).total_seconds() / 3600
            distance_km = geodesic(
                (prev["geo"]["lat"], prev["geo"]["lon"]),
                (curr["geo"]["lat"], curr["geo"]["lon"])
            ).kilometers

            # Max travel speed: 900 km/h (airplane)
            if time_diff_hours > 0 and distance_km / time_diff_hours > 900:
                suspicious.append({
                    "user": user,
                    "prev_location": prev["geo"]["country"],
                    "curr_location": curr["geo"]["country"],
                    "distance_km": distance_km,
                    "time_hours": time_diff_hours,
                    "alert": "Impossible travel detected",
                })

    return suspicious
```

### Data Exfiltration Detection
```sql
-- Detect anomalous data transfer volumes
WITH daily_user_transfers AS (
    SELECT
        user_id,
        DATE(timestamp) AS date,
        SUM(bytes_transferred) AS daily_bytes,
        AVG(SUM(bytes_transferred)) OVER (
            PARTITION BY user_id
            ORDER BY DATE(timestamp)
            ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING
        ) AS avg_30d_bytes
    FROM network_logs
    WHERE direction = 'outbound'
    GROUP BY user_id, DATE(timestamp)
)
SELECT
    user_id,
    date,
    daily_bytes,
    avg_30d_bytes,
    daily_bytes / NULLIF(avg_30d_bytes, 0) AS ratio
FROM daily_user_transfers
WHERE daily_bytes / NULLIF(avg_30d_bytes, 0) > 5   -- 5x normal volume
  AND daily_bytes > 1073741824                        -- > 1 GB absolute threshold
ORDER BY ratio DESC;
```

### Privilege Escalation Detection
```yaml
# Detect use of sudo to sensitive commands
- rule: Suspicious Sudo Command
  condition: >
    evt.type = execve
    and user.name != root
    and proc.name = sudo
    and (proc.args contains "chmod 777"
         or proc.args contains "useradd"
         or proc.args contains "visudo"
         or proc.args contains "/bin/bash")
```

## SIEM Implementation (Elastic Stack)

### Index Strategy
```yaml
# Index lifecycle policy — hot/warm/cold/delete
indices:
  - name: logs-auth-*
    hot_phase: 7 days (SSD, replicas=1)
    warm_phase: 30 days (HDD, replicas=0)
    cold_phase: 90 days (read-only, compressed)
    delete_phase: 365 days

  - name: logs-network-*
    hot_phase: 3 days
    warm_phase: 14 days
    delete_phase: 90 days
```

### Alert Tuning Process
1. **New rule**: Set threshold conservatively high — low alert volume, some misses
2. **Monitor**: Track true positive rate, false positive rate over 2 weeks
3. **Tune**: Adjust threshold, add exclusions for known benign patterns
4. **Document**: Add false positive guidance to alert runbook
5. **Review**: Quarterly review of all rules — delete stale/ineffective rules

## SOC Workflows

### Alert Triage (L1 Analyst)
```
1. Receive alert in SIEM/ticketing system
2. Check severity and alert description
3. Pull logs: what triggered the alert? What happened before and after?
4. Enrich: IP reputation, user risk score, asset criticality
5. Classify:
   - True Positive: Escalate to L2 for investigation
   - False Positive: Close with documentation; submit for rule tuning
   - Benign True Positive: Known behavior (e.g., pen test, scanner)
6. Update ticket with findings and classification
Target SLA: < 15 min for Critical, < 1 hour for High
```

### Mean Time to Detect (MTTD) Improvement
- Test detections with simulated attacks (purple team exercises)
- Track: alert created time vs. actual attack time from logs
- Common MTTD gap: attackers active for days before detection → improve behavioral detections

## Metrics & KPIs

| Metric | Target | Measurement |
|--------|--------|------------|
| MTTD (Mean Time to Detect) | < 1 hour for Critical | Alert time - earliest log evidence |
| MTTR (Mean Time to Respond) | < 4 hours for Critical | Containment time - alert time |
| False Positive Rate | < 20% per rule | FP / (TP + FP) per rule |
| Log Coverage | > 95% of critical assets | Assets sending logs / total assets |
| Detection Coverage | > 70% MITRE ATT&CK | Mapped rules / total techniques |
| Dwell Time | < 24 hours | Time from first indicator to containment |
