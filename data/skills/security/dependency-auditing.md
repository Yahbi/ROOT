---
name: Dependency Auditing
description: CVE scanning, SBOM generation, supply chain security, lock file integrity
version: "1.0.0"
author: ROOT
tags: [security, dependencies, CVE, SBOM, supply-chain, audit]
platforms: [all]
---

# Dependency Auditing

Systematically identify and remediate vulnerabilities in your software supply chain.

## CVE Scanning

### Automated Scanning Pipeline
```bash
# Python: pip-audit (uses OSV database, better coverage than safety)
pip-audit --strict --desc on --format json -o audit.json
pip-audit -r requirements.txt --fix  # Auto-fix with compatible versions

# Node.js: npm audit with actionable output
npm audit --omit=dev --audit-level=high
npx better-npm-audit audit  # Cleaner output, CI-friendly exit codes

# Multi-language: Trivy (covers Python, Node, Go, Rust, Java, OS packages)
trivy fs --severity HIGH,CRITICAL --exit-code 1 .
trivy image --ignore-unfixed myapp:latest
```

### CI Integration
- Run scanning on every PR and block merge on HIGH/CRITICAL findings
- Schedule nightly full scans (catch newly disclosed CVEs against existing deps)
- Pin scanner versions in CI to avoid false positive churn
- Allowlist known false positives in `.trivyignore` or `pip-audit.toml` with justification

## SBOM Generation

### Standards
| Format | Use Case | Tool |
|--------|----------|------|
| CycloneDX | Security-focused, VEX support | `cyclonedx-py`, `syft` |
| SPDX | License compliance, regulatory | `syft`, `spdx-tools` |

### Generation Commands
```bash
# CycloneDX from Python environment
cyclonedx-py environment -o sbom.json --format json

# Syft: multi-language SBOM from source or container
syft dir:. -o cyclonedx-json > sbom.json
syft myapp:latest -o spdx-json > sbom-spdx.json
```

### SBOM Lifecycle
- Generate SBOM at build time and publish alongside releases
- Store SBOMs in artifact registry (not just source control)
- When a new CVE drops, query existing SBOMs to find affected deployments
- Automate with `grype sbom.json` to scan an SBOM without rebuilding

## Supply Chain Security

### Lock File Integrity
- Always commit lock files (`requirements.txt` with hashes, `package-lock.json`, `poetry.lock`)
- Verify hashes on install: `pip install --require-hashes -r requirements.txt`
- Detect lock file tampering in CI: diff lock file against last known-good commit
- Never run `pip install` without version pins in production builds

### Dependency Pinning Strategy
```
# requirements.txt with hashes (strongest guarantee)
cryptography==42.0.5 \
    --hash=sha256:abc123... \
    --hash=sha256:def456...

# Acceptable: exact pins without hashes (verify via lock file)
fastapi==0.111.0
pydantic==2.7.1

# Unacceptable in production: ranges or unpinned
fastapi>=0.100  # Could pull breaking or vulnerable version
```

### Typosquatting and Malicious Packages
- Verify package names before adding: check PyPI/npm page, author, download count
- Use `pip install --dry-run` to preview what would be installed
- Monitor for name confusion: `python-dateutil` vs `dateutil`, `requests` vs `request`
- Enable package signature verification where available (Sigstore for PyPI)

## Remediation Workflow

### Triage Decision Matrix
| Severity | Exploitable? | In Production? | Action | SLA |
|----------|-------------|----------------|--------|-----|
| Critical | Yes | Yes | Hotfix immediately | 24 hours |
| Critical | No | Yes | Patch in next release | 72 hours |
| High | Yes | Yes | Patch urgently | 1 week |
| High | No | No | Schedule in sprint | 2 weeks |
| Medium/Low | Any | Any | Batch in maintenance | 30 days |

### Update Strategy
1. Check changelog for breaking changes before upgrading
2. Run full test suite against the updated dependency
3. Update one dependency at a time (isolate regressions)
4. Use Dependabot or Renovate for automated PR creation with CI validation
