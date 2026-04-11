---
name: Security Monitoring and SIEM
description: Implement SIEM correlation rules, alert triage, and security operations center workflows
version: "1.0.0"
author: ROOT
tags: [security, SIEM, monitoring, SOC, detection, alerting, Splunk, Elastic]
platforms: [all]
difficulty: intermediate
---

# Security Monitoring and SIEM

Build a detection program that finds real threats in a sea of noise.
The goal: high signal-to-noise ratio, fast triage, and few missed detections.

## SIEM Architecture

```
Log Sources → Collection Layer → SIEM Platform → Detection → Alerting
(firewalls,    (Beats, Fluentd)  (Splunk/Elastic)  (rules,     (PagerDuty,
servers, apps)                                       ML)         Slack)
```

## Log Source Priority

| Source | Priority | Key Events |
|--------|----------|-----------|
| Authentication systems | Critical | Failed logins, MFA bypass, privilege escalation |
| Identity Provider (IdP) | Critical | SSO events, account changes, impossible travel |
| Network firewalls | High | Blocked connections, unusual outbound traffic |
| DNS | High | DGA domains, newly registered, known malicious |
| EDR/Endpoint | High | Process creation, file changes, lateral movement |
| Web application logs | High | Authentication failures, injection attempts |
| Cloud (CloudTrail, GCP Audit) | High | IAM changes, resource creation, data access |
| Email gateway | Medium | Phishing detection, attachment scanning |

## Detection Rule Writing

### Splunk SPL Rules

```spl
-- Brute force detection (10+ failed logins in 5 minutes)
index=auth sourcetype=auth
| where action="failed_login"
| bin _time span=5m
| stats count AS failed_attempts by user, src_ip, _time
| where failed_attempts >= 10
| eval severity=if(failed_attempts>=50, "critical", "high")
| table _time, user, src_ip, failed_attempts, severity

-- Impossible travel detection
index=auth sourcetype=auth action=success
| stats earliest(_time) as first_login, earliest(src_ip) as first_ip,
        latest(_time) as second_login, latest(src_ip) as second_ip
        by user
| eval time_diff = second_login - first_login
| eval distance_km = geo_distance(first_ip, second_ip)  # Custom command or lookup
| where time_diff < 7200 AND distance_km > 1000  # 2 hours, 1000km
| eval speed_kph = distance_km / (time_diff / 3600)
| where speed_kph > 800  # Faster than commercial aviation

-- New admin account creation
index=security EventCode=4720 OR EventCode=4728
| where TargetUserName != "*$" AND SubjectUserName != "SYSTEM"
| stats first(_time) as created, first(SubjectUserName) as creator,
        first(TargetUserName) as new_account by host
| lookup privileged_accounts user AS new_account OUTPUT is_expected
| where is_expected != "true"
| table created, creator, new_account, host
```

### Elastic KQL/EQL Rules

```python
# Elasticsearch Security Rule (via API)
rule_config = {
    "name": "Suspicious PowerShell with Encoded Command",
    "description": "Detects PowerShell with -EncodedCommand flag — common malware technique",
    "severity": "high",
    "risk_score": 73,
    "type": "eql",
    "language": "eql",
    "query": """
        process where host.os.type == "windows"
        and event.type == "start"
        and process.name : ("powershell.exe", "pwsh.exe")
        and process.args : ("-enc", "-EncodedCommand", "-EncodedC*")
        and not process.parent.name : ("WmiPrvSE.exe", "svchost.exe")
    """,
    "filters": [],
    "actions": [{
        "action_type_id": ".slack",
        "params": {
            "message": "PowerShell encoded command detected on {{context.rule.name}}"
        }
    }],
    "throttle": "1h",    # Max 1 alert per hour for same host
    "exceptions_list": [{"id": "powershell-whitelist"}]
}
```

## Alert Triage Workflow

```python
class AlertTriage:
    def triage_alert(self, alert: dict) -> dict:
        """Structured alert triage process."""
        triage_result = {
            "alert_id": alert["id"],
            "severity": alert["severity"],
            "triage_analyst": get_oncall_analyst(),
            "triage_start": datetime.now().isoformat(),
        }

        # Step 1: Context enrichment
        context = self.enrich_alert_context(alert)
        triage_result["enrichment"] = context

        # Step 2: False positive assessment
        fp_score = self.assess_false_positive_likelihood(alert, context)
        triage_result["false_positive_score"] = fp_score

        # Step 3: Decision
        if fp_score > 0.9:
            triage_result["decision"] = "false_positive"
            triage_result["reason"] = self.identify_fp_reason(alert, context)
            self.suppress_similar(alert)
        elif fp_score > 0.5:
            triage_result["decision"] = "needs_investigation"
            triage_result["next_steps"] = self.suggest_investigation_steps(alert)
        else:
            triage_result["decision"] = "confirmed_threat"
            triage_result["next_steps"] = self.create_incident(alert)

        return triage_result

    def enrich_alert_context(self, alert: dict) -> dict:
        """Enrich alert with threat intel and asset context."""
        context = {}

        # IP reputation
        if "src_ip" in alert:
            context["ip_reputation"] = self.threat_intel.lookup_ip(alert["src_ip"])
            context["ip_geolocation"] = self.geoip.lookup(alert["src_ip"])

        # User context
        if "user" in alert:
            context["user_info"] = self.hr_directory.get_user(alert["user"])
            context["user_recent_activity"] = self.get_user_recent_events(alert["user"])
            context["user_is_admin"] = self.is_privileged_user(alert["user"])

        # Asset context
        if "host" in alert:
            context["host_info"] = self.asset_inventory.get_host(alert["host"])
            context["host_criticality"] = self.asset_inventory.get_criticality(alert["host"])

        return context
```

## Alert Fatigue Management

Alert fatigue kills SOC effectiveness. Tune rules aggressively:

```python
def analyze_alert_quality(alerts: list, period_days: int = 30) -> dict:
    """Identify noisy rules to tune or suppress."""
    rule_stats = {}

    for alert in alerts:
        rule_id = alert["rule_id"]
        if rule_id not in rule_stats:
            rule_stats[rule_id] = {"total": 0, "true_positive": 0, "false_positive": 0}

        rule_stats[rule_id]["total"] += 1
        if alert["disposition"] == "true_positive":
            rule_stats[rule_id]["true_positive"] += 1
        elif alert["disposition"] == "false_positive":
            rule_stats[rule_id]["false_positive"] += 1

    # Flag rules with > 90% false positive rate
    noisy_rules = []
    for rule_id, stats in rule_stats.items():
        if stats["total"] == 0:
            continue
        fp_rate = stats["false_positive"] / stats["total"]
        if fp_rate > 0.90 and stats["total"] > 10:
            noisy_rules.append({
                "rule_id": rule_id,
                "fp_rate": fp_rate,
                "total_alerts": stats["total"],
                "recommendation": "tune" if fp_rate < 0.98 else "disable"
            })

    return {
        "total_rules": len(rule_stats),
        "noisy_rules": sorted(noisy_rules, key=lambda x: x["total_alerts"], reverse=True),
        "overall_fp_rate": sum(s["false_positive"] for s in rule_stats.values()) /
                           max(sum(s["total"] for s in rule_stats.values()), 1)
    }
```

## SOC Metrics

```python
SOC_KPIS = {
    "mean_time_to_detect_hours": "Average time from attack start to first alert",
    "mean_time_to_respond_hours": "Average time from alert to analyst triage start",
    "mean_time_to_contain_hours": "Average time from triage to threat contained",
    "false_positive_rate": "% alerts that are false positives (target < 30%)",
    "true_positive_rate": "% actual threats detected (track missed detections)",
    "alert_volume_per_analyst": "Alerts per analyst per day (target < 30)",
    "escalation_rate": "% alerts escalated to incident (expected 5-15%)",
    "sla_compliance": "% critical alerts triaged within 15 minutes",
}
```

## Runbook Templates

```markdown
# Runbook: Brute Force Login Alert

## Alert: Multiple failed authentication attempts

## Severity: Medium (escalate to High if > 1000 attempts or admin account)

## Triage Steps
1. Identify target account and source IP
2. Check IP reputation: `lookup_ip(src_ip)` — is it known bad?
3. Check geolocation: is the source country expected for this user?
4. Check account type: is the target account privileged?
5. Check for success after failures: did brute force succeed?

## Response Actions

If IP is known bad:
  - Block IP at firewall immediately
  - Check all other activity from this IP

If brute force succeeded:
  - Escalate to P1 Incident — possible account compromise
  - Disable account pending investigation
  - Follow account compromise runbook

If brute force failed and IP is unknown:
  - Add IP to blocklist if > 100 attempts
  - Document and close as low-risk

## Escalation
- Targeted admin account → immediate escalation to SOC lead
- > 1000 attempts from single IP → WAF block + ticket
- Evidence of success → Incident declaration
```
