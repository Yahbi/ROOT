---
name: Audit Logging
description: What to log, retention policies, compliance requirements, and tamper-proof logging
version: "1.0.0"
author: ROOT
tags: [security, audit, logging, compliance, tamper-proof]
platforms: [all]
---

# Audit Logging

Implement comprehensive audit trails for security monitoring, incident response, and compliance.

## What to Log

### Authentication Events
- Login success and failure (with IP, user agent, timestamp)
- Password changes and resets
- MFA enrollment and verification
- Session creation and termination
- API key creation, usage, and revocation

### Authorization Events
- Access denied attempts (who tried to access what)
- Permission changes (role assignments, privilege escalation)
- Resource access for sensitive data (PII, financial records)
- Admin actions (user management, configuration changes)

### Data Events
- Create, read, update, delete on sensitive records
- Data exports and bulk operations
- Schema changes and migrations
- Backup and restore operations

### System Events
- Configuration changes
- Deployment events
- Service start/stop/restart
- Error and exception events

## Log Format

### Structured Event Schema
```json
{
  "timestamp": "2026-04-08T12:00:00Z",
  "event_type": "auth.login.success",
  "actor": {"id": "user_123", "type": "user", "ip": "203.0.113.1"},
  "resource": {"type": "session", "id": "sess_456"},
  "action": "create",
  "outcome": "success",
  "metadata": {"user_agent": "...", "mfa_used": true},
  "request_id": "req_789"
}
```

### Naming Convention
- Use dot-separated event types: `auth.login.success`, `data.user.update`, `admin.role.assign`
- Consistent actor/resource/action/outcome structure across all events
- Include request_id for correlation with application logs

## Retention Policy

| Log Type | Retention | Justification |
|----------|----------|---------------|
| Authentication logs | 1 year | Security investigation, compliance |
| Access logs | 90 days | Operational debugging |
| Admin action logs | 3 years | Compliance, forensics |
| Data modification logs | 7 years | Regulatory (SOX, HIPAA) |
| System event logs | 30 days | Operational |

## Tamper-Proof Logging

### Immutability Strategies
- Write-once storage: S3 with Object Lock, WORM-compliant storage
- Append-only log streams: Kafka with retention, no deletion
- Hash chaining: each log entry includes hash of previous entry (blockchain-like)
- Separate log infrastructure: logs stored in system that application code cannot modify

### Integrity Verification
- Compute daily hash digest of all audit entries
- Store digests in separate system (cross-verification)
- Alert if any log entry is modified or deleted
- Periodic integrity audits: compare log digests quarterly

## Implementation Checklist

- [ ] All authentication events logged with actor, IP, outcome
- [ ] All authorization failures logged
- [ ] Sensitive data access logged (read and write)
- [ ] Admin actions logged with before/after state
- [ ] Log storage is separate from application infrastructure
- [ ] Retention policies configured and enforced automatically
- [ ] Logs are searchable and queryable (ELK, CloudWatch, Splunk)
- [ ] Alerts configured for suspicious patterns (brute force, privilege escalation)
- [ ] Tamper protection enabled (write-once or hash chaining)
- [ ] Regular review: quarterly audit log review with security team
