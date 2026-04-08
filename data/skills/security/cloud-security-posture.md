---
name: Cloud Security Posture
description: Continuously assess and enforce security configuration across AWS, GCP, and Azure cloud environments
category: security
difficulty: advanced
version: "1.0.0"
author: ROOT
tags: [security, cloud-security, CSPM, AWS, GCP, Azure, CIS-benchmarks, IAM, misconfiguration]
platforms: [aws, gcp, azure]
---

# Cloud Security Posture Management (CSPM)

Continuously discover, assess, and remediate cloud misconfigurations before they become breaches.

## Core CSPM Capabilities

| Capability | Purpose | Tools |
|-----------|---------|-------|
| Asset inventory | Know every resource across accounts | AWS Config, Cloud Asset Inventory |
| Configuration assessment | Check against CIS benchmarks | Prowler, ScoutSuite, Checkov |
| Identity analysis | Find overly permissive IAM | IAM Access Analyzer, PMapper |
| Drift detection | Alert when config deviates from baseline | AWS Config Rules, Sentinel |
| Compliance reporting | Generate SOC2, PCI, HIPAA evidence | Security Hub, SCC |
| Threat detection | Identify suspicious cloud API activity | GuardDuty, SCC, Defender |

## AWS Security Foundations

### Account Structure (AWS Organizations)
```
Root (Management Account)
├── Security OU
│   ├── Security Tooling Account (GuardDuty master, Security Hub, Config aggregator)
│   └── Log Archive Account (CloudTrail, VPC Flow Logs, Config snapshots)
├── Production OU
│   ├── Prod Account 1
│   └── Prod Account 2
├── Non-Production OU
│   └── Staging / Dev accounts
└── Shared Services OU
    └── Network hub, shared services
```

### Service Control Policies (SCPs)
```json
// Deny disabling CloudTrail (applied at OU level)
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyDisableCloudTrail",
      "Effect": "Deny",
      "Action": [
        "cloudtrail:StopLogging",
        "cloudtrail:DeleteTrail",
        "cloudtrail:UpdateTrail"
      ],
      "Resource": "*",
      "Condition": {
        "ArnNotLike": {
          "aws:PrincipalArn": "arn:aws:iam::*:role/SecurityBreakGlassRole"
        }
      }
    }
  ]
}
```

### Critical AWS Security Controls

| Control | Service | Configuration |
|---------|---------|---------------|
| CloudTrail (all regions) | CloudTrail | Management + data events, S3 + CloudWatch |
| MFA for root | IAM | Hardware MFA, access key deleted |
| Password policy | IAM | Min 14 chars, 90-day rotation, no reuse |
| VPC Flow Logs | VPC | All VPCs, all traffic |
| Config Recorder | AWS Config | All regions, all resources |
| GuardDuty | GuardDuty | All regions, S3 protection, EKS protection |
| Security Hub | Security Hub | CIS AWS Benchmark, AWS Foundational Best Practices |
| Access Analyzer | IAM | All regions, all resource types |

## IAM Security

### Principle of Least Privilege
```python
# Analyze effective permissions with IAM Access Analyzer
import boto3

analyzer = boto3.client('accessanalyzer')

# Find externally accessible resources
findings = analyzer.list_findings(
    analyzerArn='arn:aws:access-analyzer:us-east-1:123456789:analyzer/ConsoleAnalyzer',
    filter={"status": {"eq": ["ACTIVE"]}},
)

for finding in findings['findings']:
    print(f"Resource: {finding['resource']}")
    print(f"Principal: {finding['principal']}")
    print(f"Action: {finding['action']}")
```

### IAM Permission Boundaries
```json
// Limit what role can be created by a developer team
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:*", "dynamodb:*", "lambda:*"],
      "Resource": "*"
    },
    {
      "Effect": "Deny",
      "Action": ["iam:CreateRole", "iam:AttachRolePolicy"],
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "iam:PermissionsBoundary": "arn:aws:iam::123456789:policy/DeveloperBoundary"
        }
      }
    }
  ]
}
```

### Common IAM Anti-Patterns to Detect
- Wildcard actions (`"Action": "*"`) on sensitive services (IAM, billing, KMS)
- EC2 instance profiles with `AdministratorAccess`
- Long-lived IAM user access keys (> 90 days)
- Roles assumable by `*` principal without conditions
- Policies allowing `iam:PassRole` without restricting which roles

## S3 Security

### S3 Block Public Access (Organization Level)
```bash
# Enable at organization level — overrides all bucket settings
aws s3control put-public-access-block \
  --account-id 123456789012 \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

### S3 Bucket Security Checklist
- [ ] Block all public access enabled
- [ ] Server-side encryption enabled (SSE-S3 minimum, SSE-KMS for sensitive data)
- [ ] Bucket policy denies non-HTTPS access (`aws:SecureTransport: false → Deny`)
- [ ] Access logging enabled for sensitive buckets
- [ ] Object Lock enabled for compliance/immutability requirements
- [ ] Bucket policy restricts access to specific VPC endpoints or IP ranges

## Prowler — Cloud Security Assessment

```bash
# Install and run Prowler against AWS account
pip install prowler

# Full CIS benchmark scan
prowler aws --compliance cis_level2_aws

# Specific checks
prowler aws -c check11 check12 check13   # Specific CIS checks

# Output to Security Hub
prowler aws --security-hub \
  --region us-east-1 \
  --output-formats json

# Continuous mode (schedule with cron)
prowler aws --status FAIL --severity critical,high \
  --output-filename daily_scan \
  --output-directory /reports/$(date +%Y%m%d)
```

## GCP Security Command Center

```bash
# Enable SCC and its built-in detectors
gcloud services enable securitycenter.googleapis.com

# List active findings
gcloud scc findings list organizations/123456789 \
  --filter="state=ACTIVE AND severity=CRITICAL" \
  --format="table(name, category, resourceName, eventTime)"

# Export findings to BigQuery for trend analysis
gcloud scc findings list organizations/123456789 \
  --format=json | bq insert project:dataset.scc_findings
```

## Network Security Posture

### VPC Security Baseline
```python
import boto3

def find_overly_permissive_security_groups():
    ec2 = boto3.client('ec2')
    groups = ec2.describe_security_groups()['SecurityGroups']

    issues = []
    for sg in groups:
        for rule in sg.get('IpPermissions', []):
            for cidr in rule.get('IpRanges', []):
                if cidr['CidrIp'] == '0.0.0.0/0':
                    if rule.get('FromPort') != 443 and rule.get('FromPort') != 80:
                        issues.append({
                            "sg_id": sg['GroupId'],
                            "port": rule.get('FromPort'),
                            "protocol": rule.get('IpProtocol'),
                            "issue": "Unrestricted inbound access"
                        })
    return issues
```

### Network Security Rules
- Never allow SSH (port 22) or RDP (3389) from 0.0.0.0/0
- Use Systems Manager Session Manager instead of SSH bastion hosts
- Enable VPC Flow Logs on all VPCs; ship to centralized log account
- Use AWS Network Firewall or equivalent for east-west traffic inspection

## Posture Scoring

| Domain | Weight | Checks |
|--------|--------|--------|
| Identity & Access | 30% | MFA, least privilege, key rotation |
| Data Protection | 25% | Encryption at rest/transit, public exposure |
| Logging & Monitoring | 20% | CloudTrail, Flow Logs, GuardDuty |
| Network Security | 15% | SG rules, NACLs, VPC design |
| Incident Response | 10% | Runbooks, response team, contacts |

Target: > 85% posture score per account; Critical findings = automatic fail regardless of score.
