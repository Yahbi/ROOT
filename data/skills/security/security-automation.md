---
name: Security Automation
description: Automate security scanning, response, and compliance using SAST, DAST, SOAR, and DevSecOps pipelines
category: security
difficulty: advanced
version: "1.0.0"
author: ROOT
tags: [security, devsecops, automation, SAST, DAST, SOAR, CI-CD, security-pipeline]
platforms: [all]
---

# Security Automation

Embed security checks throughout the development lifecycle and automate threat response to achieve consistent security at scale.

## DevSecOps Pipeline

### Shift-Left Security Model
```
Code       → Commit    → Build      → Test      → Deploy     → Runtime
IDE plugin   Pre-commit  SAST scan    DAST scan   Config check  SIEM/SOAR
Secret scan  Secret scan  SCA/deps     Pen tests   Container     Anomaly
             Lint rules   SBOM gen    API fuzzing  security      detection
```

### Security Gates per Stage
| Stage | Tool | Gate (Fail Build If) |
|-------|------|----------------------|
| IDE | VS Code Security plugins, Semgrep LSP | Developer feedback only |
| Pre-commit | gitleaks, detect-secrets, semgrep | Any secrets or critical findings |
| SAST | CodeQL, Semgrep CI, Bandit | Critical or High severity |
| SCA | Snyk, Dependabot, Trivy | CVSS >= 7 with fix available |
| Container scan | Trivy, Grype | Critical CVE in final image |
| DAST | OWASP ZAP, Nuclei | OWASP Top 10 vulnerabilities |
| IaC scan | Checkov, tfsec, KICS | Critical misconfigurations |
| Secrets | Gitleaks, TruffleHog | Any secret in code or history |

## SAST Configuration

### Semgrep (Multi-Language SAST)
```yaml
# .semgrep.yml
rules:
  - id: sql-injection-python
    patterns:
      - pattern: |
          cursor.execute($QUERY % ...)
      - pattern: |
          cursor.execute($QUERY.format(...))
    message: "Potential SQL injection via string formatting"
    severity: ERROR
    languages: [python]

  - id: hardcoded-credentials
    patterns:
      - pattern: |
          $VAR = "..."
      - metavariable-regex:
          metavariable: $VAR
          regex: "(password|secret|api_key|token|passwd)"
    message: "Hardcoded credential detected"
    severity: ERROR
    languages: [python, javascript, java]
```

### CodeQL (GitHub Advanced Security)
```yaml
# .github/workflows/codeql.yml
- uses: github/codeql-action/init@v3
  with:
    languages: python, javascript
    queries: security-extended   # security-extended includes more vulnerability classes

- uses: github/codeql-action/autobuild@v3

- uses: github/codeql-action/analyze@v3
  with:
    category: "/language:python"
    upload: true
    output: sarif-results
```

## Secret Scanning

### Gitleaks Pre-Commit Hook
```toml
# .gitleaks.toml
[[rules]]
id = "generic-api-key"
description = "Generic API Key"
regex = '''(?i)(api_key|apikey|api-key)\s*[=:]\s*['"]?([a-zA-Z0-9]{20,})'''
secretGroup = 2
entropy = 3.7

[[rules]]
id = "aws-access-key"
description = "AWS Access Key ID"
regex = '''(A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}'''
```

```bash
# Pre-commit hook installation
pip install pre-commit gitleaks
cat > .pre-commit-config.yaml << EOF
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks
EOF
pre-commit install
```

### TruffleHog (CI Pipeline)
```yaml
- name: Scan for secrets
  uses: trufflesecurity/trufflehog@main
  with:
    path: ./
    base: ${{ github.event.repository.default_branch }}
    head: HEAD
    extra_args: --debug --only-verified
```

## Infrastructure as Code Security

### Checkov (Terraform / CloudFormation / Kubernetes)
```bash
# Scan Terraform
checkov -d terraform/ --framework terraform \
  --check CKV_AWS_18,CKV_AWS_19 \   # Specific check IDs
  --output sarif \
  --output-file-path reports/

# Scan Kubernetes manifests
checkov -d k8s/ --framework kubernetes \
  --soft-fail-on MEDIUM \   # Only fail on HIGH+
  --compact

# Custom check example
# checkov/custom_checks/ensure_no_privileged_containers.py
from checkov.common.models.enums import CheckResult, CheckCategories
from checkov.kubernetes.checks.resource.base_container_check import BaseK8Check

class PrivilegedContainerCheck(BaseK8Check):
    def __init__(self):
        super().__init__("Ensure containers are not privileged",
                         "CKV_CUSTOM_001", CheckCategories.GENERAL_SECURITY,
                         ["Deployment", "Pod"])

    def scan_container_conf(self, metadata, conf):
        if conf.get("securityContext", {}).get("privileged"):
            return CheckResult.FAILED
        return CheckResult.PASSED
```

## DAST Automation

### OWASP ZAP Baseline Scan
```bash
# Passive scan (non-intrusive — safe for production)
docker run -v $(pwd):/zap/wrk/:rw owasp/zap2docker-stable \
  zap-baseline.py -t https://staging.myapp.com \
  -r zap_report.html -J zap_report.json \
  --auto --level WARN

# Full scan (active — staging only)
docker run owasp/zap2docker-stable \
  zap-full-scan.py -t https://staging.myapp.com \
  -r full_report.html \
  -c zap_config.conf
```

### Nuclei (Template-Based Scanning)
```yaml
# Custom nuclei template
id: exposed-debug-endpoint
info:
  name: Debug Endpoint Exposed
  severity: high
  tags: [exposure, debug]

requests:
  - method: GET
    path:
      - "{{BaseURL}}/debug"
      - "{{BaseURL}}/api/debug"
      - "{{BaseURL}}/__debug__"
    matchers:
      - type: status
        status: [200]
      - type: word
        words: ["debug", "stack trace", "exception"]
        condition: or
```

```bash
# Run against target list
nuclei -l targets.txt -t cves/ -t exposures/ \
  -severity critical,high \
  -o results.json -json
```

## SOAR (Security Orchestration, Automation, and Response)

### Automated Incident Response Playbook
```python
async def phishing_response_playbook(alert: dict):
    """Automated playbook for phishing email detection."""

    sender = alert["sender_email"]
    recipient = alert["recipient_email"]
    email_id = alert["email_id"]

    # 1. Block sender at email gateway
    await block_email_sender(sender)

    # 2. Extract and analyze URLs
    urls = extract_urls(alert["email_body"])
    threat_intel = await check_urls_against_virustotal(urls)

    # 3. If malicious URLs confirmed, quarantine email
    if any(u["malicious"] for u in threat_intel):
        await quarantine_email(email_id)
        await notify_recipient(recipient, "A phishing email was removed from your inbox")

        # 4. Check if anyone clicked the link
        clickers = await query_proxy_logs_for_urls(urls, lookback_hours=24)
        if clickers:
            severity = "HIGH"
            await force_password_reset(clickers)
            await revoke_sessions(clickers)
        else:
            severity = "MEDIUM"

    # 5. Create SIEM ticket
    await create_incident_ticket({
        "title": f"Phishing email from {sender}",
        "severity": severity,
        "status": "auto_contained",
        "evidence": threat_intel,
        "affected_users": clickers,
    })
```

### Alert Enrichment Pipeline
```python
async def enrich_alert(raw_alert: dict) -> dict:
    """Enrich raw SIEM alert with context before human review."""
    ip = raw_alert.get("source_ip")
    user = raw_alert.get("username")

    enrichments = await asyncio.gather(
        geoip_lookup(ip),
        threat_intel_check(ip),           # VirusTotal, AbuseIPDB
        check_user_risk_score(user),
        get_recent_user_activity(user),
        check_asset_criticality(raw_alert.get("hostname")),
    )

    return {**raw_alert, "enrichments": dict(zip(
        ["geo", "threat_intel", "user_risk", "recent_activity", "asset_criticality"],
        enrichments
    ))}
```

## Compliance Automation

### CIS Benchmarks (via Lynis / Inspector)
```bash
# Linux host hardening audit
lynis audit system --cronjob \
  --logfile /var/log/lynis.log \
  --report-file /var/log/lynis-report.dat

# Parse score
grep "hardening index" /var/log/lynis.log
```

### Automated Compliance Reporting
```python
def generate_compliance_report(standard: str = "SOC2") -> dict:
    controls = load_controls(standard)
    results = {}

    for control in controls:
        evidence = collect_evidence(control.id)
        status = evaluate_control(control, evidence)
        results[control.id] = {
            "status": status,        # PASS, FAIL, NOT_APPLICABLE
            "evidence": evidence,
            "last_checked": datetime.utcnow().isoformat(),
        }

    passing = sum(1 for r in results.values() if r["status"] == "PASS")
    return {
        "standard": standard,
        "score": passing / len(results) * 100,
        "controls": results,
        "generated_at": datetime.utcnow().isoformat(),
    }
```

## Security Metrics Dashboard

| Metric | Target | Measurement |
|--------|--------|------------|
| SAST findings (Critical) | 0 open | CodeQL/Semgrep results |
| Mean time to fix Critical | < 24h | Ticket open → close time |
| CI security gate pass rate | > 95% | Non-security failures don't count |
| Secrets in code | 0 | Gitleaks scan results |
| IaC policy compliance | > 98% | Checkov pass rate |
| DAST High findings (staging) | 0 before release | ZAP scan results |
