---
name: Secrets Management
description: SOPS, Vault, environment variables, rotation, and secure secret handling
version: "1.0.0"
author: ROOT
tags: [devops, secrets, security, vault, encryption, rotation]
platforms: [all]
---

# Secrets Management

Store, distribute, and rotate secrets securely across environments.

## Secret Storage Approaches

### Environment Variables
- **Best for**: Simple deployments, 12-factor apps, CI/CD pipelines
- Load from `.env` files locally, injected by orchestrator in production
- Never commit `.env` to version control (add to `.gitignore`)
- Limitation: no versioning, no audit trail, visible in process listings

### HashiCorp Vault
- **Best for**: Multi-service architectures, dynamic secrets, compliance requirements
- Features: dynamic database credentials, automatic rotation, audit logging
- Access via API: application authenticates with Vault, receives time-limited secret
- High availability with Raft or Consul backend

### SOPS (Secrets OPerationS)
- **Best for**: Encrypted secrets in git, GitOps workflows
- Encrypts values in YAML/JSON while keeping keys visible (easy code review)
- Integrates with AWS KMS, GCP KMS, Azure Key Vault, PGP
- Secret changes tracked in git history (who changed what, when)

### Cloud-Native
- AWS Secrets Manager / Parameter Store
- GCP Secret Manager
- Azure Key Vault
- Best when already invested in one cloud platform

## Secret Rotation

### Rotation Schedule
| Secret Type | Rotation Frequency | Method |
|------------|-------------------|--------|
| API keys | Every 90 days | Generate new, update apps, revoke old |
| Database passwords | Every 90 days | Vault dynamic secrets (automatic) |
| TLS certificates | Before expiry (auto-renew) | Let's Encrypt + cert-manager |
| Encryption keys | Annually | Key versioning with old key support |
| Service account tokens | Every 30 days | Automated via CI/CD |

### Zero-Downtime Rotation Pattern
1. Generate new secret alongside old secret
2. Update application to accept both old and new (dual-read)
3. Deploy application update
4. Switch to writing with new secret only
5. Revoke old secret after grace period (24-48 hours)

## Security Practices

### What Counts as a Secret
- API keys and tokens (OpenAI, Stripe, AWS, etc.)
- Database connection strings with credentials
- Encryption keys and signing keys
- OAuth client secrets
- Webhook signing secrets
- TLS private keys

### Secret Hygiene
- Use unique secrets per environment (dev, staging, prod)
- Use unique secrets per service (not shared credentials)
- Minimum secret length: 32 characters, cryptographically random
- Never log secrets (redact in log output with pattern matching)
- Never pass secrets via URL query parameters (logged by web servers)

## Audit and Compliance

### Audit Requirements
- Log every secret access: who, when, which secret, from where
- Alert on unusual access patterns (access from new IP, bulk reads)
- Quarterly review: which secrets exist, who has access, when last rotated
- Revoke access immediately when team members leave

### Pre-Commit Scanning
- Use `gitleaks` or `trufflehog` as pre-commit hooks
- Scan for high-entropy strings and known secret patterns
- CI/CD should also scan for leaked secrets in PRs
- If a secret is committed: rotate immediately, do not just delete from history
