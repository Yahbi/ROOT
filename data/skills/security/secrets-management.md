---
name: Secrets Management
description: Centralize and automate secrets management using HashiCorp Vault, AWS Secrets Manager, and rotation automation
version: "1.0.0"
author: ROOT
tags: [security, secrets-management, vault, AWS-secrets-manager, credentials, rotation]
platforms: [all]
difficulty: intermediate
---

# Secrets Management

Eliminate hardcoded credentials, centralize secrets storage, and automate rotation
to prevent credential-based breaches.

## Why Secrets Management Fails

Most common secrets mistakes:
1. **Hardcoded in source code** — leaked via git history
2. **In .env files committed to git** — should be in .gitignore and not shared
3. **Long-lived API keys** — not rotated, leak survives forever
4. **Shared credentials** — no audit trail of who did what
5. **Unencrypted in configuration files** — config file access = full compromise

## HashiCorp Vault

### Setup and Policy

```python
import hvac

def setup_vault_client(vault_url: str, token: str) -> hvac.Client:
    client = hvac.Client(url=vault_url, token=token)
    assert client.is_authenticated(), "Vault authentication failed"
    return client

# Read a secret
def get_secret(vault_client: hvac.Client, path: str, key: str) -> str:
    secret = vault_client.secrets.kv.v2.read_secret_version(
        path=path,
        mount_point="secret"
    )
    return secret["data"]["data"][key]

# Write a secret
def set_secret(vault_client: hvac.Client, path: str, data: dict):
    vault_client.secrets.kv.v2.create_or_update_secret(
        path=path,
        secret=data,
        mount_point="secret"
    )

# Usage
vault = setup_vault_client("https://vault.company.com", os.environ["VAULT_TOKEN"])
db_password = get_secret(vault, "database/prod", "password")
api_key = get_secret(vault, "external-apis/stripe", "api_key")
```

### Vault Dynamic Secrets (Database)

```python
# Vault generates temporary database credentials on-demand
def get_dynamic_db_credentials(vault_client: hvac.Client,
                                 database_role: str = "readonly") -> dict:
    """Get temporary database credentials that expire automatically."""
    creds = vault_client.secrets.database.generate_credentials(name=database_role)
    return {
        "username": creds["data"]["username"],
        "password": creds["data"]["password"],
        "lease_id": creds["lease_id"],
        "lease_duration": creds["lease_duration"],  # Seconds until expiry
    }

# Configure database secret engine (one-time setup)
def configure_database_secret_engine(vault_client: hvac.Client, db_config: dict):
    vault_client.secrets.database.configure(
        name="postgresql",
        plugin_name="postgresql-database-plugin",
        connection_url=db_config["connection_url"],
        allowed_roles=["readonly", "readwrite"],
    )

    vault_client.secrets.database.create_role(
        name="readonly",
        db_name="postgresql",
        creation_statements=[
            "CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';",
            "GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";"
        ],
        default_ttl="1h",
        max_ttl="24h"
    )
```

### Vault Policies (Least Privilege)

```hcl
# policies/app-readonly.hcl
path "secret/data/app/config" {
  capabilities = ["read"]
}

path "secret/data/database/readonly" {
  capabilities = ["read"]
}

# Deny write access
path "secret/data/+/+" {
  capabilities = ["deny"]
}
```

```python
def create_vault_policy(vault_client: hvac.Client, policy_name: str, hcl_policy: str):
    vault_client.sys.create_or_update_policy(
        name=policy_name,
        policy=hcl_policy
    )

def create_app_token(vault_client: hvac.Client, policy: str, ttl: str = "24h") -> str:
    """Create a short-lived token for an application."""
    token = vault_client.auth.token.create(
        policies=[policy],
        ttl=ttl,
        renewable=False  # Force fresh login, don't extend
    )
    return token["auth"]["client_token"]
```

## AWS Secrets Manager

```python
import boto3
import json

class AWSSecretsManager:
    def __init__(self, region: str = "us-east-1"):
        self.client = boto3.client("secretsmanager", region_name=region)

    def get_secret(self, secret_name: str) -> dict:
        """Retrieve secret value from AWS Secrets Manager."""
        response = self.client.get_secret_value(SecretId=secret_name)

        if "SecretString" in response:
            return json.loads(response["SecretString"])
        else:
            # Binary secret
            return {"binary": response["SecretBinary"]}

    def create_secret(self, name: str, value: dict, description: str = "") -> str:
        """Create a new secret."""
        response = self.client.create_secret(
            Name=name,
            Description=description,
            SecretString=json.dumps(value),
            Tags=[
                {"Key": "Environment", "Value": "production"},
                {"Key": "ManagedBy", "Value": "terraform"},
            ]
        )
        return response["ARN"]

    def rotate_secret(self, secret_name: str, rotation_lambda_arn: str) -> dict:
        """Enable automatic rotation via Lambda."""
        return self.client.rotate_secret(
            SecretId=secret_name,
            RotationLambdaARN=rotation_lambda_arn,
            RotationRules={
                "AutomaticallyAfterDays": 30,
                "Duration": "2h"  # Lambda timeout
            }
        )

# Lambda function for database password rotation
def lambda_rotate_db_password(event, context):
    """Lambda handler for RDS password rotation."""
    secret_id = event["SecretId"]
    step = event["Step"]
    token = event["ClientRequestToken"]

    secrets = AWSSecretsManager()
    sm = boto3.client("secretsmanager")

    if step == "createSecret":
        # Generate new password
        new_password = secrets_manager.get_random_password(
            PasswordLength=32, ExcludeCharacters='/"@\\'
        )["RandomPassword"]
        sm.put_secret_value(
            SecretId=secret_id,
            ClientRequestToken=token,
            SecretString=json.dumps({**current_secret, "password": new_password}),
            VersionStages=["AWSPENDING"]
        )

    elif step == "setSecret":
        # Apply new password to the database
        pending = sm.get_secret_value(SecretId=secret_id, VersionStage="AWSPENDING")
        new_creds = json.loads(pending["SecretString"])
        update_db_password(new_creds["username"], new_creds["password"])

    elif step == "testSecret":
        # Verify new credentials work
        pending = sm.get_secret_value(SecretId=secret_id, VersionStage="AWSPENDING")
        new_creds = json.loads(pending["SecretString"])
        test_db_connection(new_creds)

    elif step == "finishSecret":
        # Promote AWSPENDING to AWSCURRENT
        sm.update_secret_version_stage(
            SecretId=secret_id,
            VersionStage="AWSCURRENT",
            MoveToVersionId=token,
            RemoveFromVersionId=get_current_version_id(secret_id)
        )
```

## Secret Scanning

```bash
# Detect secrets in code before they reach git
# Install git-secrets or trufflehog

# git-secrets: block commits with secrets
git secrets --install
git secrets --register-aws

# trufflehog: scan git history for leaked secrets
trufflehog git file:///path/to/repo --json

# gitleaks: fast, comprehensive scanning
gitleaks detect --source=. --report-format=sarif --report-path=gitleaks.sarif

# Add to pre-commit hooks
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/zricethezav/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
```

```python
def scan_secrets_in_code(path: str) -> list:
    """Scan codebase for accidentally committed secrets."""
    SECRET_PATTERNS = [
        (r"(?i)(password|passwd|pwd)\s*=\s*['\"][^'\"]{8,}", "potential_password"),
        (r"(?i)(api[_-]?key|apikey)\s*=\s*['\"][A-Za-z0-9+/]{20,}", "potential_api_key"),
        (r"sk-[A-Za-z0-9]{48}", "openai_api_key"),
        (r"xoxb-[A-Za-z0-9-]{50}", "slack_bot_token"),
        (r"-----BEGIN (RSA |EC )?PRIVATE KEY-----", "private_key"),
        (r"AKIA[0-9A-Z]{16}", "aws_access_key_id"),
        (r"(?i)stripe.*sk_live_[A-Za-z0-9]{24}", "stripe_secret_key"),
    ]

    findings = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", ".venv"}]
        for filename in files:
            if filename.endswith((".py", ".js", ".ts", ".yaml", ".yml", ".json", ".env", ".conf")):
                filepath = os.path.join(root, filename)
                with open(filepath, "r", errors="ignore") as f:
                    content = f.read()
                    for pattern, secret_type in SECRET_PATTERNS:
                        matches = re.findall(pattern, content)
                        for match in matches:
                            findings.append({
                                "file": filepath,
                                "secret_type": secret_type,
                                "severity": "critical"
                            })
    return findings
```

## Secrets Management Best Practices

| Practice | Implementation |
|----------|---------------|
| Centralized store | Vault or AWS Secrets Manager — never local files |
| Short TTL credentials | Database: 1 hour, API keys: 24 hours |
| Rotation automation | Lambda or Vault agent for automatic rotation |
| Audit logging | Every secret access logged with user + IP |
| Break-glass procedure | Emergency access with CISO approval + audit |
| Secret scanning in CI | Block commits containing secrets (pre-commit hooks) |
| Separate by environment | dev/staging/prod secrets in separate paths |
| No sharing of credentials | Every service gets its own credential |
