---
name: Container and Kubernetes Security
description: Secure containerized workloads with pod security policies, network policies, and runtime security
version: "1.0.0"
author: ROOT
tags: [security, kubernetes, containers, Docker, pod-security, network-policy, OPA]
platforms: [all]
difficulty: advanced
---

# Container and Kubernetes Security

Containers expand attack surface — secure them at the image, runtime, and orchestration layers.

## Container Image Security

### Secure Dockerfile Patterns

```dockerfile
# Multi-stage build to minimize attack surface
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage — copy only what's needed
FROM python:3.11-slim AS production

# Don't run as root
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY src/ ./src/

# Set secure defaults
RUN chmod -R 550 /app && chown -R appuser:appgroup /app

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

EXPOSE 8000
ENTRYPOINT ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Image Scanning

```bash
# Trivy — comprehensive vulnerability scanner
trivy image --severity HIGH,CRITICAL --exit-code 1 my-image:latest

# Grype — Anchore's image scanner
grype my-image:latest --fail-on high

# Scan in CI/CD pipeline
trivy image \
  --format sarif \
  --output trivy-results.sarif \
  --exit-code 1 \
  --ignore-unfixed \
  --severity CRITICAL,HIGH \
  my-registry/my-image:$GITHUB_SHA
```

## Kubernetes Pod Security

### Pod Security Standards

```yaml
# Apply Pod Security Standards at namespace level
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    pod-security.kubernetes.io/enforce: restricted      # Strictest level
    pod-security.kubernetes.io/enforce-version: v1.28
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/audit: restricted

---
# Secure Pod specification
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
  namespace: production
spec:
  replicas: 3
  template:
    spec:
      # No host namespaces
      hostNetwork: false
      hostPID: false
      hostIPC: false

      # Service account with minimal permissions
      serviceAccountName: web-app-sa
      automountServiceAccountToken: false

      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault  # Apply default syscall filter

      containers:
      - name: web-app
        image: my-registry/web-app:sha256-abc123...
        securityContext:
          allowPrivilegeEscalation: false
          privileged: false
          readOnlyRootFilesystem: true    # Prevent filesystem writes
          capabilities:
            drop: ["ALL"]                # Remove all Linux capabilities
            add: ["NET_BIND_SERVICE"]    # Only add what's needed

        resources:
          requests:
            cpu: "100m"
            memory: "256Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"

        # Volume for writable paths
        volumeMounts:
        - name: tmp-dir
          mountPath: /tmp
        - name: app-logs
          mountPath: /app/logs

      volumes:
      - name: tmp-dir
        emptyDir: {}
      - name: app-logs
        emptyDir: {}
```

## Network Policies

```yaml
# Default deny all ingress and egress
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}  # Apply to all pods
  policyTypes:
  - Ingress
  - Egress

---
# Allow specific traffic only
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: web-app-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: web-app

  policyTypes:
  - Ingress
  - Egress

  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx   # Only from ingress controller
    ports:
    - protocol: TCP
      port: 8000

  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres         # Only to database
    ports:
    - protocol: TCP
      port: 5432
  - to:                         # DNS resolution
    - namespaceSelector:
        matchLabels:
          name: kube-system
    ports:
    - protocol: UDP
      port: 53
```

## RBAC for Kubernetes

```yaml
# Service account with minimal permissions
apiVersion: v1
kind: ServiceAccount
metadata:
  name: web-app-sa
  namespace: production

---
# Role — only what the app needs
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: web-app-role
  namespace: production
rules:
- apiGroups: [""]
  resources: ["configmaps"]
  resourceNames: ["app-config"]     # Specific configmap only
  verbs: ["get"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: web-app-rolebinding
  namespace: production
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: web-app-role
subjects:
- kind: ServiceAccount
  name: web-app-sa
  namespace: production
```

## OPA/Gatekeeper Policy Enforcement

```yaml
# Gatekeeper ConstraintTemplate — enforce image from trusted registry
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: allowedimageregistry
spec:
  crd:
    spec:
      names:
        kind: AllowedImageRegistry
      validation:
        properties:
          allowedRegistries:
            type: array
            items:
              type: string
  targets:
  - target: admission.k8s.gatekeeper.sh
    rego: |
      package allowedimageregistry

      violation[{"msg": msg}] {
        container := input.review.object.spec.containers[_]
        not starts_with_allowed_registry(container.image)
        msg := sprintf("Image '%v' is not from an allowed registry", [container.image])
      }

      starts_with_allowed_registry(image) {
        registry := input.parameters.allowedRegistries[_]
        startswith(image, registry)
      }

---
# Apply the constraint
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: AllowedImageRegistry
metadata:
  name: require-trusted-registry
spec:
  match:
    kinds:
    - apiGroups: ["*"]
      kinds: ["Pod"]
    namespaces: ["production", "staging"]
  parameters:
    allowedRegistries:
      - "my-registry.company.com/"
      - "gcr.io/my-project/"
```

## Runtime Security with Falco

```yaml
# Falco rules for detecting runtime threats
- rule: Terminal Shell in Container
  desc: Container has terminal shell started (possible interactive intrusion)
  condition: >
    spawned_process
    and container
    and shell_procs
    and proc.tty != 0
    and not proc.pname in (shell_binaries)
  output: >
    Shell started in container (user=%user.name container=%container.name
    image=%container.image.repository shell=%proc.name parent=%proc.pname
    cmdline=%proc.cmdline)
  priority: WARNING
  tags: [container, shell, mitre_execution]

- rule: Cryptocurrency Mining Detected
  desc: Detects known cryptocurrency mining process names
  condition: >
    spawned_process
    and proc.name in (xmrig, minerd, cpuminer, cgminer, bfgminer)
  output: >
    Crypto miner detected (proc=%proc.name container=%container.name
    image=%container.image.repository user=%user.name)
  priority: CRITICAL
```

## Kubernetes Security Audit

```python
import subprocess
import json

def run_kube_bench() -> dict:
    """Run CIS Kubernetes Benchmark checks."""
    result = subprocess.run(
        ["kube-bench", "--json"],
        capture_output=True, text=True
    )
    findings = json.loads(result.stdout)

    critical_fails = [
        check for section in findings["Controls"]
        for check in section["tests"]
        for result in check["results"]
        if result["status"] == "FAIL" and check["scored"]
    ]

    return {
        "total_checks": sum(s["total_tests"] for s in findings["Controls"]),
        "failed_checks": len(critical_fails),
        "critical_failures": critical_fails[:10],  # Top 10 for report
        "score": findings.get("TotalPass", 0) / max(findings.get("TotalChecks", 1), 1) * 100
    }
```

## Security Checklist

- [ ] Images built from minimal base (distroless or slim)
- [ ] No packages installed with package managers at runtime
- [ ] Containers running as non-root user
- [ ] readOnlyRootFilesystem: true
- [ ] All Linux capabilities dropped
- [ ] Resource limits set (CPU and memory)
- [ ] Network policies enforcing least privilege connectivity
- [ ] Secrets from Vault or sealed-secrets (not plaintext ConfigMaps)
- [ ] Image signatures verified before deployment
- [ ] Falco or equivalent runtime security monitoring enabled
- [ ] RBAC: service accounts with minimal permissions
- [ ] Pod Security Standards: restricted level enforced
