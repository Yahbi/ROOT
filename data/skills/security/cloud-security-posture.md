---
name: Cloud Security Posture Management
description: Continuously assess and remediate cloud misconfigurations across AWS, GCP, and Azure
version: "1.0.0"
author: ROOT
tags: [security, cloud, CSPM, AWS, GCP, Azure, misconfiguration, compliance]
platforms: [all]
difficulty: intermediate
---

# Cloud Security Posture Management (CSPM)

Continuously identify and remediate cloud misconfigurations that expose your
organization to data breaches, unauthorized access, and compliance violations.

## Common Critical Misconfigurations

### AWS S3 Bucket Security

```python
import boto3

def audit_s3_buckets() -> list:
    """Audit all S3 buckets for public access and encryption issues."""
    s3 = boto3.client("s3")
    issues = []

    buckets = s3.list_buckets()["Buckets"]

    for bucket in buckets:
        name = bucket["Name"]

        # Check public access block settings
        try:
            pab = s3.get_public_access_block(Bucket=name)["PublicAccessBlockConfiguration"]
            if not all(pab.values()):
                issues.append({
                    "bucket": name,
                    "issue": "public_access_not_fully_blocked",
                    "severity": "critical",
                    "details": pab,
                    "remediation": "Enable all Public Access Block settings"
                })
        except s3.exceptions.NoSuchPublicAccessBlockConfiguration:
            issues.append({
                "bucket": name,
                "issue": "no_public_access_block_configuration",
                "severity": "critical",
                "remediation": "Configure Public Access Block immediately"
            })

        # Check bucket ACL
        acl = s3.get_bucket_acl(Bucket=name)
        for grant in acl["Grants"]:
            if grant["Grantee"].get("URI") == "http://acs.amazonaws.com/groups/global/AllUsers":
                issues.append({
                    "bucket": name,
                    "issue": "publicly_accessible_via_acl",
                    "severity": "critical",
                    "permission": grant["Permission"],
                    "remediation": "Remove AllUsers grants from bucket ACL"
                })

        # Check encryption
        try:
            s3.get_bucket_encryption(Bucket=name)
        except Exception:
            issues.append({
                "bucket": name,
                "issue": "no_default_encryption",
                "severity": "high",
                "remediation": "Enable AES-256 or AWS KMS default encryption"
            })

    return issues
```

### AWS IAM Security Audit

```python
def audit_iam_posture() -> list:
    """Identify dangerous IAM configurations."""
    iam = boto3.client("iam")
    issues = []

    # Check for users with direct admin policies (should use roles)
    users = iam.list_users()["Users"]
    for user in users:
        policies = iam.list_attached_user_policies(UserName=user["UserName"])["AttachedPolicies"]
        for policy in policies:
            if policy["PolicyArn"] == "arn:aws:iam::aws:policy/AdministratorAccess":
                issues.append({
                    "resource": f"IAM User: {user['UserName']}",
                    "issue": "user_has_direct_admin_access",
                    "severity": "high",
                    "remediation": "Use IAM roles with temporary credentials instead"
                })

    # Check for access keys older than 90 days
    for user in users:
        keys = iam.list_access_keys(UserName=user["UserName"])["AccessKeyMetadata"]
        for key in keys:
            if key["Status"] == "Active":
                age_days = (datetime.now(timezone.utc) - key["CreateDate"]).days
                if age_days > 90:
                    issues.append({
                        "resource": f"IAM User: {user['UserName']}",
                        "issue": "access_key_older_than_90_days",
                        "severity": "medium",
                        "key_age_days": age_days,
                        "remediation": "Rotate access keys; implement 90-day rotation policy"
                    })

    # Check root account activity
    credential_report = get_credential_report(iam)
    root_row = next(r for r in credential_report if r["user"] == "<root_account>")

    if root_row["mfa_active"] == "false":
        issues.append({
            "resource": "Root Account",
            "issue": "root_account_no_mfa",
            "severity": "critical",
            "remediation": "Enable MFA on root account immediately"
        })

    if root_row.get("access_key_1_active") == "true":
        issues.append({
            "resource": "Root Account",
            "issue": "root_account_has_access_keys",
            "severity": "critical",
            "remediation": "Delete root account access keys — use IAM roles"
        })

    return issues
```

### Security Group Audit

```python
def audit_security_groups() -> list:
    """Find overly permissive security groups."""
    ec2 = boto3.client("ec2")
    sgs = ec2.describe_security_groups()["SecurityGroups"]
    issues = []

    DANGEROUS_PORTS = {22: "SSH", 3389: "RDP", 3306: "MySQL", 5432: "PostgreSQL",
                       6379: "Redis", 27017: "MongoDB", 9200: "Elasticsearch"}

    for sg in sgs:
        for rule in sg["IpPermissions"]:
            from_port = rule.get("FromPort", 0)
            to_port = rule.get("ToPort", 65535)

            for ip_range in rule.get("IpRanges", []):
                cidr = ip_range["CidrIp"]
                if cidr == "0.0.0.0/0":  # Open to internet
                    # Check for dangerous ports
                    for port, service in DANGEROUS_PORTS.items():
                        if from_port <= port <= to_port:
                            issues.append({
                                "security_group": sg["GroupId"],
                                "sg_name": sg["GroupName"],
                                "issue": f"internet_accessible_{service.lower()}",
                                "port": port,
                                "severity": "critical" if port in {22, 3389} else "high",
                                "remediation": f"Restrict port {port} to specific IP ranges"
                            })

                    # 0.0.0.0/0 on ALL traffic
                    if from_port == 0 and to_port == 65535:
                        issues.append({
                            "security_group": sg["GroupId"],
                            "issue": "all_traffic_from_internet",
                            "severity": "critical",
                            "remediation": "Remove 0.0.0.0/0 all-traffic ingress rule"
                        })

    return issues
```

## Automated Remediation

```python
def auto_remediate_s3_public_access(bucket_name: str, dry_run: bool = True) -> dict:
    """Automatically enable S3 Public Access Block."""
    s3 = boto3.client("s3")

    action = {
        "bucket": bucket_name,
        "action": "enable_public_access_block",
        "dry_run": dry_run
    }

    if not dry_run:
        s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True
            }
        )
        action["status"] = "remediated"
    else:
        action["status"] = "dry_run_only"

    return action
```

## Compliance Framework Checks

```python
COMPLIANCE_CHECKS = {
    "CIS_AWS_1.4": {
        "control": "Do not setup access keys during initial root account setup",
        "check": "root_account_no_access_keys",
        "severity": "critical"
    },
    "CIS_AWS_2.1.2": {
        "control": "Ensure MFA Delete is enabled on S3 buckets",
        "check": "s3_mfa_delete_enabled",
        "severity": "medium"
    },
    "SOC2_CC6.1": {
        "control": "Encryption at rest for all data stores",
        "check": "all_s3_buckets_encrypted",
        "severity": "high"
    },
    "HIPAA_164.312": {
        "control": "Access control to ePHI systems",
        "check": "iam_mfa_required_all_users",
        "severity": "critical"
    }
}

def run_compliance_check(framework: str) -> dict:
    """Run all checks for a compliance framework."""
    results = {"passed": [], "failed": [], "score": 0}

    framework_checks = {k: v for k, v in COMPLIANCE_CHECKS.items() if k.startswith(framework)}

    for control_id, control in framework_checks.items():
        passed = execute_check(control["check"])
        if passed:
            results["passed"].append(control_id)
        else:
            results["failed"].append({
                "control": control_id,
                "description": control["control"],
                "severity": control["severity"]
            })

    results["score"] = len(results["passed"]) / max(len(framework_checks), 1) * 100
    return results
```

## CSPM Tool Comparison

| Tool | Best For | Coverage | Cost |
|------|---------|----------|------|
| AWS Security Hub | AWS-native, free tier | AWS only | Free + $0.001/check |
| Prisma Cloud | Multi-cloud enterprise | AWS/GCP/Azure/K8s | Enterprise |
| Wiz | Fast deployment, agentless | Multi-cloud | Enterprise |
| Lacework | Anomaly detection + CSPM | Multi-cloud | Enterprise |
| Prowler | Open source, scriptable | AWS/GCP/Azure | Free |
| ScoutSuite | Open source, offline | Multi-cloud | Free |

## Daily CSPM Workflow

```python
def daily_cspm_sweep() -> dict:
    """Daily automated posture check."""
    all_issues = (
        audit_s3_buckets() +
        audit_iam_posture() +
        audit_security_groups()
    )

    critical_issues = [i for i in all_issues if i["severity"] == "critical"]
    high_issues = [i for i in all_issues if i["severity"] == "high"]

    if critical_issues:
        alert_security_team(
            severity="P0",
            message=f"{len(critical_issues)} CRITICAL cloud misconfigurations found",
            details=critical_issues
        )

    # Auto-remediate safe low-risk issues
    for issue in [i for i in all_issues if i.get("auto_remediate", False)]:
        auto_remediate(issue)

    return {"critical": len(critical_issues), "high": len(high_issues), "total": len(all_issues)}
```
