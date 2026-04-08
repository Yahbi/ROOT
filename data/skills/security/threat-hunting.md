---
name: Threat Hunting
description: Proactively search for hidden threats in your environment using hypothesis-driven investigation
version: "1.0.0"
author: ROOT
tags: [security, threat-hunting, DFIR, SOC, detection, adversary]
platforms: [all]
difficulty: advanced
---

# Threat Hunting

Threat hunting is proactive — assume attackers are already in your environment
and systematically search for evidence of compromise before alerts trigger.

## Threat Hunting Process

```
1. Hypothesis → What attacker technique am I hunting for?
2. Gather Data → Collect relevant logs and telemetry
3. Investigate → Apply analytics and search patterns
4. Uncover → Find evidence of malicious activity (or confirm clean)
5. Inform → Update detection rules, close gaps
```

## Hunt Hypothesis Sources

- **MITRE ATT&CK**: Browse TTP matrix for relevant techniques
- **Threat Intelligence**: Known TTPs for threats targeting your sector
- **Vulnerability News**: Exploit released for unpatched CVE in your stack
- **Internal Risk Assessment**: What high-value assets would an attacker target?
- **Peer incidents**: Other companies in your industry reported breach

## Common Hunt Scenarios

### Hunt 1: Lateral Movement via Pass-the-Hash

**Hypothesis**: Attacker has compromised one Windows workstation and is moving laterally using stolen NTLM hashes.

```kql
// Kibana/SIEM KQL — detect NTLM authentication with mismatched workstation
SecurityEvent
| where EventID == 4624  // Successful logon
| where LogonType == 3   // Network logon
| where AuthenticationPackageName == "NTLM"
| where WorkstationName != ComputerName  // Remote NTLM — suspicious
| summarize count() by TargetUserName, WorkstationName, IpAddress, bin(TimeGenerated, 1h)
| where count_ > 10  // Multiple NTLM auths from same IP in 1 hour
| order by count_ desc
```

**Indicators of Compromise**:
- Same user authenticating from multiple workstations within minutes
- NTLM auth to multiple servers from a single source
- Logons at unusual hours (3am) from workstations
- Logons to servers the user normally doesn't access

### Hunt 2: Beaconing (C2 Communication)

**Hypothesis**: Malware is calling back to attacker infrastructure on regular intervals.

```python
import pandas as pd
import numpy as np

def detect_beaconing(dns_logs: pd.DataFrame, threshold_std: float = 0.3) -> pd.DataFrame:
    """Detect periodic DNS beaconing by low variance in request intervals."""
    dns_logs["timestamp"] = pd.to_datetime(dns_logs["timestamp"])

    results = []
    for (src_ip, domain), group in dns_logs.groupby(["src_ip", "domain"]):
        if len(group) < 10:  # Need enough data points
            continue

        group = group.sort_values("timestamp")
        intervals = group["timestamp"].diff().dt.total_seconds().dropna()

        mean_interval = intervals.mean()
        std_interval = intervals.std()
        coefficient_of_variation = std_interval / mean_interval if mean_interval > 0 else 1

        # Low CV = very regular = beaconing
        if coefficient_of_variation < threshold_std and 60 <= mean_interval <= 3600:
            results.append({
                "src_ip": src_ip,
                "domain": domain,
                "mean_interval_sec": mean_interval,
                "cv": coefficient_of_variation,
                "request_count": len(group),
                "confidence": "high" if coefficient_of_variation < 0.1 else "medium"
            })

    return pd.DataFrame(results).sort_values("cv")
```

### Hunt 3: Living Off the Land (LOLBins)

**Hypothesis**: Attacker is using legitimate Windows binaries to avoid detection.

```kql
// Hunt for suspicious use of legitimate admin tools
DeviceProcessEvents
| where FileName in ("powershell.exe", "cmd.exe", "wscript.exe", "mshta.exe",
                     "regsvr32.exe", "certutil.exe", "bitsadmin.exe")
| where InitiatingProcessFileName !in ("explorer.exe", "services.exe", "svchost.exe")
| where ProcessCommandLine has_any ("-EncodedCommand", "DownloadString", "IEX",
                                    "Invoke-Expression", "wget", "/transfer",
                                    "base64", "bypass", "-nop", "-noexit")
| project TimeGenerated, DeviceName, AccountName, FileName, ProcessCommandLine
| order by TimeGenerated desc
```

### Hunt 4: Data Exfiltration via DNS

**Hypothesis**: Attacker is tunneling data out via DNS queries (high entropy domain names).

```python
import math
from collections import Counter

def calculate_entropy(text: str) -> float:
    """Shannon entropy — high entropy = random-looking = suspicious."""
    freq = Counter(text.lower())
    length = len(text)
    return -sum((count/length) * math.log2(count/length) for count in freq.values())

def detect_dns_tunneling(dns_logs: pd.DataFrame) -> pd.DataFrame:
    suspects = []
    for _, row in dns_logs.iterrows():
        subdomain = row["domain"].split(".")[0]  # e.g., "xHj3kL9mP2..." in "xHj3kL9mP2.evil.com"

        entropy = calculate_entropy(subdomain)
        length = len(subdomain)

        # High entropy, long subdomain = likely data exfil
        if entropy > 3.5 and length > 30:
            suspects.append({
                "domain": row["domain"],
                "subdomain": subdomain,
                "entropy": entropy,
                "length": length,
                "src_ip": row["src_ip"],
                "timestamp": row["timestamp"]
            })

    return pd.DataFrame(suspects)
```

## MITRE ATT&CK Mapping

When you find malicious activity, map it to ATT&CK:

```python
ATTCK_MAPPING = {
    "lateral_movement_ntlm": {
        "technique_id": "T1550.002",
        "technique_name": "Pass the Hash",
        "tactic": "Lateral Movement",
        "kill_chain_phase": "Exploitation"
    },
    "c2_beaconing": {
        "technique_id": "T1071.001",
        "technique_name": "Application Layer Protocol: Web Protocols",
        "tactic": "Command and Control"
    },
    "dns_tunneling": {
        "technique_id": "T1048.003",
        "technique_name": "Exfiltration Over Unencrypted Non-C2 Protocol",
        "tactic": "Exfiltration"
    }
}
```

## Hunt Playbook Template

```markdown
# Hunt: [Name]

## Hypothesis
[Statement of suspected attacker behavior]

## Threat Actor Alignment
MITRE ATT&CK: T[XXXX] — [Technique Name]
Threat actors known to use this: [Groups from CTI]

## Data Required
- [ ] Windows Security Event Logs (Domain Controllers)
- [ ] DNS logs (recursive resolvers)
- [ ] Proxy/Web gateway logs
- [ ] EDR telemetry (process creation, network, file)

## Hunt Queries
[KQL/SPL/SQL queries with explanations]

## Investigation Steps
1. Run initial detection query
2. Triage results: [normal/suspicious/malicious criteria]
3. For suspicious results: [pivot and expand investigation]

## Indicators of Compromise
[What a positive finding looks like]

## False Positive Considerations
[Legitimate activity that may trigger these queries]

## Outcomes
- [ ] No evidence found → hunt complete, document
- [ ] Confirmed incident → escalate to IR team
- [ ] Detection gap found → create SIEM rule
```

## Detection Engineering Output

After each hunt, create a detection rule to automate future detection:

```yaml
# detection_rule.yaml
id: detect_pass_the_hash_lateral_movement
name: "Lateral Movement via Pass-the-Hash"
description: "Detects NTLM authentication patterns consistent with PtH attacks"
severity: HIGH
tactic: Lateral Movement
technique: T1550.002
data_sources:
  - Windows Security Events
query: |
  [SIEM query from hunt]
threshold: 5 events per 1 hour per source IP
response_actions:
  - Isolate source workstation
  - Reset credentials for targeted account
  - Notify SOC lead
false_positive_rate: LOW
hunt_origin: 2026-04-08 — Incident hypothesis from peer breach report
```
