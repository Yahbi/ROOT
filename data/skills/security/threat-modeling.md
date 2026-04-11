---
name: Threat Modeling
description: STRIDE analysis, attack trees, trust boundaries, and data flow diagrams
version: "1.0.0"
author: ROOT
tags: [security, threat-modeling, STRIDE, attack-trees, DFD]
platforms: [all]
---

# Threat Modeling

Systematically identify and prioritize security threats before they become vulnerabilities.

## STRIDE Framework

### Threat Categories
| Category | Threat | Example | Mitigation |
|----------|--------|---------|------------|
| **S**poofing | Impersonating another identity | Forged JWT, stolen API key | MFA, certificate pinning, PKCE |
| **T**ampering | Modifying data in transit or at rest | SQL injection, man-in-the-middle | Input validation, TLS, HMAC signatures |
| **R**epudiation | Denying actions were performed | User denies placing order | Audit logs, digital signatures, timestamps |
| **I**nformation Disclosure | Unauthorized data access | Verbose error messages, S3 misconfiguration | Encryption at rest/transit, least privilege |
| **D**enial of Service | Making system unavailable | DDoS, resource exhaustion, regex DoS | Rate limiting, CDN, input bounds |
| **E**levation of Privilege | Gaining unauthorized access | IDOR, JWT role manipulation, path traversal | RBAC enforcement, input validation |

### STRIDE Per Element
Apply STRIDE to each component in your data flow diagram:
- **External entities** (users, APIs): Spoofing, Repudiation
- **Data flows** (network calls): Tampering, Information Disclosure
- **Data stores** (databases, files): Tampering, Information Disclosure, DoS
- **Processes** (services, functions): All six categories

## Data Flow Diagrams (DFDs)

### Building the DFD
1. Identify external entities: users, third-party APIs, admin interfaces
2. Map processes: application servers, background workers, LLM services
3. Identify data stores: databases, caches, file systems, message queues
4. Draw data flows: HTTP requests, database queries, queue messages
5. Mark trust boundaries: internet/DMZ, DMZ/internal, internal/database

### Trust Boundary Analysis
Every trust boundary crossing is a potential attack surface:
- Internet to load balancer: TLS termination, WAF rules, rate limiting
- Load balancer to application: Internal TLS, authentication verification
- Application to database: Connection encryption, parameterized queries, least-privilege DB user
- Application to third-party API: API key storage, response validation, timeout enforcement

## Attack Trees

### Construction Method
```
Root Goal: Steal user credentials
├── [OR] Exploit application vulnerability
│   ├── [AND] SQL injection on login form
│   │   ├── Find unparameterized query
│   │   └── Extract credentials table
│   └── [AND] XSS to steal session cookie
│       ├── Find reflected XSS endpoint
│       └── Inject cookie-stealing payload
├── [OR] Compromise infrastructure
│   ├── Exploit unpatched server CVE
│   └── Access misconfigured S3 bucket
└── [OR] Social engineering
    ├── Phishing email to admin
    └── Credential stuffing from breach database
```

### Prioritization
Score each leaf node: `Risk = Likelihood x Impact`
- Likelihood: skill required, access needed, detection probability
- Impact: data sensitivity, user count, regulatory consequence
- Focus on high-risk paths first -- not all threats need immediate mitigation

## Threat Model Document

### Template Structure
1. **System description**: What does the system do, who uses it
2. **DFD**: Visual diagram with trust boundaries marked
3. **Threat enumeration**: STRIDE applied to each DFD element
4. **Risk ranking**: Each threat scored by likelihood and impact
5. **Mitigations**: Existing controls and planned improvements
6. **Assumptions**: What we assume is secure (and shouldn't)
7. **Review cadence**: Quarterly, or on major architecture changes

## When to Threat Model

- Before building: design phase catches issues cheapest
- New feature with auth/data changes: any new trust boundary crossing
- After a security incident: validate the model missed the attack vector
- Dependency update with new network calls: new data flows = new threats
- At minimum: review existing threat model every quarter
