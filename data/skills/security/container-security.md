---
name: Container Security
description: Secure Docker containers and Kubernetes workloads through image hardening, runtime protection, and policy enforcement
category: security
difficulty: advanced
version: "1.0.0"
author: ROOT
tags: [security, containers, docker, kubernetes, OPA, Falco, image-scanning, pod-security]
platforms: [linux, kubernetes]
---

# Container Security

Secure containers and Kubernetes workloads from build time through runtime with defense in depth.

## Container Security Layers

```
Image Build   → Registry      → Cluster Admission → Runtime
Minimal base    Scan on push    Pod Security        Falco runtime
Non-root user   Sign with       OPA/Gatekeeper      detection
No secrets      Cosign          Network Policy      Audit logs
Multi-stage     Quarantine      Resource limits     Syscall filter
```

## Docker Image Hardening

### Dockerfile Best Practices
```dockerfile
# Use minimal base image — prefer distroless or alpine
FROM gcr.io/distroless/python3-debian12

# Or alpine with explicit version pinning
FROM python:3.12.1-alpine3.19

# Multi-stage build — exclude build tools from final image
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM gcr.io/distroless/python3-debian12 AS runtime
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY app/ ./app/

# Run as non-root user (distroless has 'nonroot' built in)
USER nonroot:nonroot

# Explicit CMD (no shell form — prevents shell injection)
CMD ["/usr/bin/python3", "-m", "app.main"]
```

### Image Scanning with Trivy
```bash
# Scan for CVEs, secrets, and misconfigurations
trivy image --severity HIGH,CRITICAL \
  --exit-code 1 \
  --ignore-unfixed \
  myapp:v1.2.3

# Scan in CI pipeline with SARIF output (GitHub Security tab)
trivy image --format sarif --output trivy-results.sarif myapp:v1.2.3

# Scan filesystem (pre-build)
trivy fs --scanners vuln,secret,config \
  --severity CRITICAL,HIGH \
  .

# Scan running container
trivy image --input $(docker save myapp:v1.2.3) --format json
```

### Image Signing with Cosign
```bash
# Generate signing key pair
cosign generate-key-pair

# Sign image after CI build
cosign sign --key cosign.key myregistry/myapp:v1.2.3@sha256:abc123...

# Verify before deployment (in admission controller)
cosign verify --key cosign.pub myregistry/myapp:v1.2.3

# Keyless signing with OIDC (GitHub Actions)
- name: Sign image
  run: cosign sign --yes $IMAGE_URI@$IMAGE_DIGEST
  env:
    COSIGN_EXPERIMENTAL: "1"
```

## Kubernetes Pod Security

### Pod Security Standards (Kubernetes 1.25+)
```yaml
# Apply to namespace
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    pod-security.kubernetes.io/enforce: restricted    # Enforce restricted policy
    pod-security.kubernetes.io/enforce-version: v1.28
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/audit: restricted
```

### Secure Pod Spec
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    spec:
      # No root
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
        fsGroup: 10001
        seccompProfile:
          type: RuntimeDefault      # Apply seccomp syscall filter

      containers:
      - name: myapp
        image: myregistry/myapp:v1.2.3@sha256:abc123  # Pin by digest
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop: ["ALL"]           # Drop all Linux capabilities
            add: []                 # Add only what's absolutely necessary

        # Resource limits prevent DoS
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"

        # No secrets as environment variables — use volumes or secret store
        volumeMounts:
        - name: tmp
          mountPath: /tmp           # Writable temp (for readOnlyRootFilesystem)

      automountServiceAccountToken: false    # Disable if not needed
      hostNetwork: false
      hostPID: false
      hostIPC: false

      volumes:
      - name: tmp
        emptyDir: {}
```

## OPA Gatekeeper Policies

### Deny Privileged Containers
```yaml
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sNoPrivilege
metadata:
  name: no-privileged-containers
spec:
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Pod"]
---
apiVersion: templates.gatekeeper.sh/v1beta1
kind: ConstraintTemplate
metadata:
  name: k8snoprivilege
spec:
  crd:
    spec:
      names:
        kind: K8sNoPrivilege
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package k8snoprivilege
        violation[{"msg": msg}] {
          c := input.review.object.spec.containers[_]
          c.securityContext.privileged
          msg := sprintf("Container %v must not run as privileged", [c.name])
        }
```

### Require Image Signatures (Cosign + Gatekeeper)
```yaml
# Using Kyverno (simpler alternative to Gatekeeper)
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-image-signatures
spec:
  validationFailureAction: Enforce
  rules:
    - name: check-image-signature
      match:
        any:
        - resources:
            kinds: [Pod]
      verifyImages:
      - imageReferences: ["myregistry/*"]
        attestors:
        - count: 1
          entries:
          - keys:
              publicKeys: |-
                -----BEGIN PUBLIC KEY-----
                MFkwEwYH...
                -----END PUBLIC KEY-----
```

## Network Policies

### Default Deny + Explicit Allow
```yaml
# Default deny all ingress and egress in namespace
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
---
# Allow specific traffic
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-myapp
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: myapp
  policyTypes: [Ingress, Egress]
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: nginx-ingress
    ports:
    - protocol: TCP
      port: 8080
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432
```

## Runtime Security with Falco

### Falco Rules (Detect Suspicious Behavior)
```yaml
# /etc/falco/rules.d/custom_rules.yaml

- rule: Shell Spawned in Container
  desc: Detect shell execution inside a container (may indicate intrusion)
  condition: >
    spawned_process
    and container
    and shell_procs
    and not proc.pname in (shell_procs)
  output: "Shell spawned in container (user=%user.name command=%proc.cmdline container=%container.name image=%container.image.repository)"
  priority: WARNING
  tags: [container, shell, intrusion]

- rule: Write to Sensitive File
  desc: Detect writes to /etc or system binaries in container
  condition: >
    open_write
    and container
    and (fd.name startswith /etc/ or fd.name startswith /usr/bin/)
    and not proc.name in (package managers)
  output: "Write to sensitive path (file=%fd.name user=%user.name container=%container.name)"
  priority: ERROR
  tags: [container, filesystem]
```

## Secrets Management in Kubernetes

### External Secrets Operator (AWS Secrets Manager / Vault)
```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: db-credentials
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: db-secret
  data:
  - secretKey: DB_PASSWORD
    remoteRef:
      key: production/myapp/db
      property: password
```

## Container Security Checklist

### Build Time
- [ ] Base image pinned by digest (not `latest`)
- [ ] No secrets in Dockerfile or build args
- [ ] Non-root user configured
- [ ] Read-only root filesystem set
- [ ] Multi-stage build removes dev dependencies
- [ ] Trivy scan passing (no Critical CVEs)
- [ ] Image signed with Cosign

### Runtime
- [ ] Pod Security Standard: `restricted` enforced
- [ ] All capabilities dropped
- [ ] Resource limits set
- [ ] Network policies in place (default deny)
- [ ] Service account token not automounted unless needed
- [ ] Falco running in cluster
- [ ] Secrets from external secret store (not env vars)
