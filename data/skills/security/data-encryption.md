---
name: Data Encryption
description: At-rest, in-transit, and field-level encryption for data protection
version: "1.0.0"
author: ROOT
tags: [security, encryption, data-protection, TLS, AES]
platforms: [all]
---

# Data Encryption

Protect data at rest, in transit, and at the field level to ensure confidentiality.

## Encryption at Rest

### Database Encryption
- **Transparent Data Encryption (TDE)**: Encrypts entire database files
- PostgreSQL: use pgcrypto extension or filesystem-level encryption
- SQLite: use SQLCipher for encrypted database files
- Cloud: Enable default encryption (AWS RDS, GCP Cloud SQL encrypt at rest by default)

### File and Disk Encryption
- LUKS (Linux): Full disk encryption for servers
- Cloud: EBS encryption (AWS), Persistent Disk encryption (GCP)
- Object storage: S3 server-side encryption (SSE-S3, SSE-KMS, or SSE-C)

### Key Management
- Never store encryption keys alongside encrypted data
- Use a Key Management Service: AWS KMS, GCP Cloud KMS, HashiCorp Vault
- Key hierarchy: master key encrypts data keys, data keys encrypt data (envelope encryption)
- Rotate data encryption keys annually, master keys every 2-3 years

## Encryption in Transit

### TLS Configuration
- Minimum TLS 1.2 (prefer TLS 1.3 where supported)
- Disable weak cipher suites (RC4, 3DES, MD5-based)
- Enable HSTS: `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- Certificate pinning for mobile apps (prevents MITM with rogue CAs)

### Internal Service Communication
- Use mTLS (mutual TLS) between microservices
- Service mesh (Istio, Linkerd) automates mTLS certificate management
- Even internal traffic should be encrypted — zero-trust networking

## Field-Level Encryption

### When to Use
- Encrypt specific sensitive fields: SSN, credit card, health data, PII
- Different fields may need different access controls
- Compliance requirements (PCI DSS, HIPAA) may mandate field-level protection

### Implementation Pattern
1. Identify sensitive fields per data model
2. Encrypt before storage using AES-256-GCM (authenticated encryption)
3. Store encrypted value + IV (initialization vector) + key version
4. Decrypt only when needed, only by authorized services
5. Search: use blind index (hash of value) for equality lookups without decrypting

### Algorithm Selection
| Algorithm | Use Case | Notes |
|-----------|---------|-------|
| AES-256-GCM | General data encryption | Authenticated, fast, standard |
| ChaCha20-Poly1305 | Mobile/embedded | Fast without hardware AES support |
| RSA-OAEP | Key exchange, small payloads | Asymmetric, slow for large data |
| Argon2id | Password hashing | Not encryption — hashing only |

## Compliance Considerations

- **PCI DSS**: Credit card data must be encrypted at rest and in transit, key rotation required
- **HIPAA**: PHI must be encrypted, access logged, breach notification required
- **GDPR**: Encryption as technical measure, data subject access rights apply to encrypted data
- **SOC 2**: Encryption requirements for data in transit and at rest

## Checklist

- [ ] TLS 1.2+ enforced for all external connections
- [ ] Internal service communication encrypted (mTLS or VPN)
- [ ] Sensitive database fields encrypted with AES-256-GCM
- [ ] Encryption keys managed via KMS (not in application code)
- [ ] Key rotation schedule defined and automated
- [ ] Passwords hashed with Argon2id (never encrypted — hashing is one-way)
