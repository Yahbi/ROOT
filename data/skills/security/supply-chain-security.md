---
name: Supply Chain Security
description: Secure software supply chain through dependency scanning, SBOM generation, and code signing
version: "1.0.0"
author: ROOT
tags: [security, supply-chain, SBOM, dependency-scanning, code-signing, SLSA, sigstore]
platforms: [all]
difficulty: advanced
---

# Supply Chain Security

Modern software depends on hundreds of third-party packages. A single compromised
dependency can affect millions of downstream users. Secure your supply chain systematically.

## Dependency Vulnerability Scanning

### Python Dependencies

```bash
# Install dependency scanner
pip install safety pip-audit

# Safety check (free tier)
safety check --full-report

# pip-audit (Google, uses OSV database)
pip-audit -r requirements.txt --output=json

# Parse pip-audit results
pip-audit -r requirements.txt --output=json 2>/dev/null | python3 -c "
import json, sys
results = json.load(sys.stdin)
critical = [v for v in results['dependencies'] if any(
    vuln['aliases'] or vuln['id'] for vuln in v.get('vulns', [])
)]
print(f'Found {len(critical)} packages with vulnerabilities')
for pkg in critical:
    for vuln in pkg.get('vulns', []):
        print(f'  {pkg[\"name\"]}=={pkg[\"version\"]}: {vuln[\"id\"]} - {vuln[\"description\"][:100]}')
"
```

### Node.js Dependencies

```bash
# Built-in npm audit
npm audit
npm audit --json | jq '.vulnerabilities | to_entries | map({package: .key, severity: .value.severity}) | sort_by(.severity)'

# Yarn
yarn audit --json

# Snyk (more comprehensive)
snyk test --all-projects --severity-threshold=high

# Check for outdated packages
npm outdated
```

### Automated Dependency Updates

```yaml
# .github/dependabot.yml — auto-create PRs for dependency updates
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 10
    reviewers:
      - "security-team"
    ignore:
      - dependency-name: "boto3"
        update-types: ["version-update:semver-major"]

  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
    groups:
      dev-dependencies:
        patterns: ["eslint*", "jest*", "@types/*"]
```

## Software Bill of Materials (SBOM)

```python
import json
import subprocess

def generate_sbom(project_path: str, format: str = "spdx") -> dict:
    """Generate SBOM in SPDX or CycloneDX format."""
    if format == "spdx":
        result = subprocess.run(
            ["syft", project_path, "-o", "spdx-json"],
            capture_output=True, text=True
        )
        sbom = json.loads(result.stdout)
    elif format == "cyclonedx":
        result = subprocess.run(
            ["cyclonedx-py", "--format", "json", "--output", "-"],
            capture_output=True, text=True, cwd=project_path
        )
        sbom = json.loads(result.stdout)

    return sbom

def analyze_sbom_risk(sbom: dict) -> dict:
    """Analyze SBOM for license, vulnerability, and provenance risks."""
    packages = extract_packages(sbom)

    license_risks = []
    LICENSE_RISK = {
        "GPL-2.0": "copyleft — can affect commercial distribution",
        "GPL-3.0": "copyleft — stricter than GPL-2.0",
        "AGPL-3.0": "copyleft — applies to SaaS use",
        "CC-BY-SA": "copyleft for content",
    }

    for pkg in packages:
        if pkg.get("license") in LICENSE_RISK:
            license_risks.append({
                "package": pkg["name"],
                "license": pkg["license"],
                "risk": LICENSE_RISK[pkg["license"]]
            })

    return {
        "total_packages": len(packages),
        "license_risks": license_risks,
        "packages_without_license": [p for p in packages if not p.get("license")],
        "sbom_generated_at": datetime.now().isoformat()
    }
```

## Code Signing

```bash
# Sign container images with Cosign (Sigstore)
# Install: brew install cosign

# Generate key pair
cosign generate-key-pair

# Sign image after build
cosign sign --key cosign.key my-registry/my-image:sha256-abc123...

# Verify before deployment
cosign verify --key cosign.pub my-registry/my-image:sha256-abc123...

# Sign with keyless (OIDC-based, no long-lived keys)
cosign sign --yes my-registry/my-image:sha256-abc123...
# Uses GitHub/GitLab OIDC token in CI/CD — transparently logged in Rekor
```

```python
# Verify image signature before Kubernetes deployment
import subprocess

def verify_image_signature(image: str, allowed_identities: list) -> bool:
    """Verify container image signature before deployment."""
    result = subprocess.run(
        ["cosign", "verify", "--certificate-identity-regexp",
         "|".join(allowed_identities),
         "--certificate-oidc-issuer", "https://token.actions.githubusercontent.com",
         image],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        raise SecurityException(f"Image signature verification failed for {image}: {result.stderr}")

    return True
```

## SLSA Framework (Supply chain Levels for Software Artifacts)

```
SLSA Level 1: Provenance documented (how was it built?)
SLSA Level 2: Provenance signed and tamper-evident
SLSA Level 3: Source and build platforms are audited
SLSA Level 4: All builds hermetic; no single person can influence build
```

### GitHub Actions SLSA Provenance

```yaml
# .github/workflows/build-with-provenance.yml
name: Build with SLSA Provenance

on:
  push:
    tags: ["v*"]

jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      digests: ${{ steps.hash.outputs.digests }}

    steps:
      - uses: actions/checkout@v4

      - name: Build artifact
        run: python setup.py bdist_wheel

      - name: Generate SHA256 hash
        id: hash
        run: |
          sha256sum dist/*.whl > SHA256SUMS
          echo "digests=$(cat SHA256SUMS | base64 -w0)" >> $GITHUB_OUTPUT

  provenance:
    needs: build
    permissions:
      actions: read
      id-token: write
      contents: write

    uses: slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@v1.9.0
    with:
      base64-subjects: "${{ needs.build.outputs.digests }}"
```

## Private Package Registry

```python
# Prevent dependency confusion attacks — use private registry
# pip.conf or .piprc

PIP_CONFIG = """
[global]
index-url = https://pypi.company.com/simple/
extra-index-url = https://pypi.org/simple/
trusted-host = pypi.company.com
"""

# Namespace protection — register package names even if empty
INTERNAL_PACKAGES = ["company-utils", "company-auth", "company-models"]
# Register all these on public PyPI to prevent squatting

def check_dependency_confusion_risk(requirements: list) -> list:
    """Identify internal packages that could be confused with public ones."""
    risks = []
    for package in requirements:
        if is_internal_package(package):
            if exists_on_public_pypi(package):
                risks.append({
                    "package": package,
                    "risk": "confusion_possible",
                    "public_version": get_public_version(package),
                    "internal_version": get_internal_version(package)
                })
    return risks
```

## CI/CD Supply Chain Hardening

```yaml
# .github/workflows/hardened-ci.yml
name: Hardened CI Pipeline

on: push

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read          # Minimum required
      packages: write         # Only if publishing to GHCR

    steps:
      # Pin actions to specific commit SHA (not tags — tags can be moved)
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2

      # Verify action integrity
      - name: Harden GitHub Actions runner
        uses: step-security/harden-runner@91182cccc01eb5e233562a7571e2a896aab6c66e  # v2.10.1
        with:
          egress-policy: audit  # Monitor unexpected outbound connections

      - name: Scan dependencies before build
        run: |
          pip-audit -r requirements.txt --fail-on-severity HIGH
          safety check -r requirements.txt

      - name: Build
        run: make build

      - name: Scan built image
        uses: aquasecurity/trivy-action@18f2510ee396bbf400402c5a99a12d65e67fdb3d  # v0.28.0
        with:
          scan-type: image
          exit-code: 1         # Fail CI if critical vulns found
          severity: CRITICAL,HIGH
```

## Package Integrity Verification

```python
import hashlib
import requests

def verify_package_integrity(package_name: str, version: str, expected_hash: str) -> bool:
    """Verify downloaded package matches expected hash (lock file based)."""
    response = requests.get(
        f"https://pypi.org/pypi/{package_name}/{version}/json"
    )
    package_info = response.json()

    for url_info in package_info["urls"]:
        if url_info["packagetype"] == "bdist_wheel":
            actual_hash = url_info["digests"]["sha256"]
            if actual_hash == expected_hash:
                return True
            else:
                raise SecurityException(
                    f"Hash mismatch for {package_name}=={version}! "
                    f"Expected: {expected_hash}, Got: {actual_hash}"
                )

    return False

# pip uses requirements.txt with hashes for integrity
# requirements.txt with hashes:
# requests==2.31.0 \
#   --hash=sha256:58cd2187423d9b4… \
#   --hash=sha256:942c5a758f98d7…
```
