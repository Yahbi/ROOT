---
name: Zero Trust Architecture
description: Identity verification, micro-segmentation, least privilege, continuous validation
version: "1.0.0"
author: ROOT
tags: [security, zero-trust, identity, micro-segmentation, least-privilege]
platforms: [all]
---

# Zero Trust Architecture

Never trust, always verify. Every request is treated as potentially hostile regardless of network location.

## Core Principles

### 1. Verify Explicitly
- Authenticate and authorize every request using all available signals
- Signals: user identity, device health, location, time, resource sensitivity
- No request is trusted based on network position alone (VPN != trusted)

### 2. Least Privilege Access
- Grant minimum permissions required for the current task
- Time-bound access: temporary credentials expire automatically
- Just-in-time (JIT) elevation: request elevated access per-session, not permanently
- Default deny: if no explicit allow rule exists, block the request

### 3. Assume Breach
- Design systems as if an attacker is already inside the network
- Segment blast radius: compromise of one service should not cascade
- Monitor and log everything for post-incident investigation
- Encrypt data at rest and in transit, even on internal networks

## Identity Verification

### Strong Authentication
```
Authentication Strength Ladder:
1. Password only                    → Unacceptable
2. Password + SMS OTP               → Weak (SIM swap vulnerable)
3. Password + TOTP app              → Acceptable minimum
4. Password + hardware key (FIDO2)  → Strong
5. Passwordless FIDO2/passkeys      → Strongest
```

### Service-to-Service Identity
- Mutual TLS (mTLS): both client and server present certificates
- SPIFFE/SPIRE: workload identity framework for dynamic environments
- Service mesh identity: Istio/Linkerd inject mTLS sidecars automatically
- Never use shared secrets between services -- use per-service credentials

## Micro-Segmentation

### Network Segmentation Strategy
| Zone | Access Policy | Examples |
|------|--------------|---------|
| Public | Rate-limited, WAF-protected | Load balancer, CDN edge |
| DMZ | Authenticated, scoped access | API gateway, reverse proxy |
| Application | Service-to-service mTLS only | Backend services, workers |
| Data | Strict IP allowlist + auth | Databases, object storage |
| Management | MFA + VPN + JIT access | Admin panels, CI/CD, SSH |

### Application-Level Segmentation
- Each microservice has its own network policy (deny all ingress by default)
- Allow only specific service-to-service communication paths
- Database access restricted to specific application services (not all pods)
- Kubernetes: use NetworkPolicy objects to enforce pod-to-pod rules

## Continuous Validation

### Session Security
- Re-evaluate trust on every request, not just at login
- Step-up authentication for sensitive operations (payment, config changes)
- Session duration limits: 8 hours maximum, re-auth for high-risk actions
- Device posture checks: OS version, disk encryption, endpoint protection

### Monitoring and Anomaly Detection
- Baseline normal behavior per user, service, and network path
- Alert on deviations: unusual data volumes, new network connections, privilege escalation
- Correlate signals across identity, network, and application layers
- Automated response: temporarily block anomalous sessions pending review

## Implementation Roadmap

### Phase 1: Identity Foundation (Month 1-2)
- Deploy SSO with MFA for all human access
- Implement service accounts with short-lived credentials
- Audit and remove shared credentials and long-lived API keys

### Phase 2: Network Controls (Month 3-4)
- Segment networks by sensitivity zone
- Deploy service mesh with mTLS for service-to-service communication
- Implement network policies (default deny ingress)

### Phase 3: Continuous Monitoring (Month 5-6)
- Deploy centralized logging with correlation IDs
- Implement anomaly detection on authentication and access patterns
- Automate response to high-confidence threats (session revocation, IP blocking)
