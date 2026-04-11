---
name: Identity and Access Management
description: Implement zero-trust IAM with RBAC, least privilege, MFA, and privileged access management
version: "1.0.0"
author: ROOT
tags: [security, IAM, zero-trust, RBAC, MFA, privileged-access, LDAP, OAuth]
platforms: [all]
difficulty: intermediate
---

# Identity and Access Management

Control who has access to what, enforce least privilege, and detect identity-based
attacks before they result in data breaches.

## IAM Design Principles

1. **Least Privilege**: Grant only the permissions needed for the specific task
2. **Zero Trust**: Never trust, always verify — even internal users
3. **Defense in Depth**: Multiple layers: SSO + MFA + RBAC + session monitoring
4. **Separation of Duties**: No single person can complete a sensitive action alone
5. **Just-in-Time Access**: Temporary elevated access rather than permanent admin
6. **Regular Review**: Quarterly access reviews — remove unused permissions

## Role-Based Access Control (RBAC)

```python
from enum import Enum
from dataclasses import dataclass
from typing import Set

class Permission(Enum):
    # Read permissions
    READ_USERS = "users:read"
    READ_FINANCIALS = "financials:read"
    READ_SYSTEM_LOGS = "system:logs:read"
    READ_CUSTOMER_DATA = "customers:read"

    # Write permissions
    WRITE_USERS = "users:write"
    WRITE_FINANCIALS = "financials:write"
    MANAGE_BILLING = "billing:manage"

    # Admin permissions
    ADMIN_SYSTEM = "system:admin"
    ADMIN_IAM = "iam:admin"
    ADMIN_AUDIT = "audit:read"

@dataclass
class Role:
    name: str
    permissions: Set[Permission]
    max_session_hours: int = 8
    requires_mfa: bool = True

ROLES = {
    "viewer": Role(
        name="Viewer",
        permissions={Permission.READ_USERS, Permission.READ_CUSTOMER_DATA},
        requires_mfa=False
    ),
    "analyst": Role(
        name="Analyst",
        permissions={Permission.READ_USERS, Permission.READ_CUSTOMER_DATA,
                    Permission.READ_FINANCIALS, Permission.READ_SYSTEM_LOGS},
    ),
    "engineer": Role(
        name="Engineer",
        permissions={Permission.READ_USERS, Permission.READ_CUSTOMER_DATA,
                    Permission.READ_SYSTEM_LOGS, Permission.WRITE_USERS},
        max_session_hours=8
    ),
    "admin": Role(
        name="Admin",
        permissions=set(Permission),  # All permissions
        max_session_hours=4,          # Shorter sessions for high privilege
        requires_mfa=True
    )
}

def check_permission(user: dict, required_permission: Permission) -> bool:
    """Check if user has a specific permission."""
    user_role = ROLES.get(user.get("role"))
    if not user_role:
        return False

    # Check MFA requirement
    if user_role.requires_mfa and not user.get("mfa_verified"):
        return False

    # Check session age
    session_age_hours = (datetime.now() - user["session_start"]).seconds / 3600
    if session_age_hours > user_role.max_session_hours:
        return False

    return required_permission in user_role.permissions
```

## OAuth 2.0 / OIDC Implementation

```python
from authlib.integrations.flask_client import OAuth
import secrets

oauth = OAuth()

def setup_oauth(app, provider_config: dict):
    """Configure OAuth2/OIDC provider."""
    oauth.init_app(app)
    oauth.register(
        name="provider",
        server_metadata_url=provider_config["discovery_url"],
        client_id=provider_config["client_id"],
        client_secret=provider_config["client_secret"],
        client_kwargs={
            "scope": "openid email profile groups",
        }
    )

def generate_login_url(redirect_uri: str) -> tuple:
    """Generate OAuth login URL with CSRF protection."""
    state = secrets.token_urlsafe(32)  # CSRF token
    nonce = secrets.token_urlsafe(32)   # Replay attack prevention

    redirect_url = oauth.provider.create_authorization_url(
        redirect_uri=redirect_uri,
        state=state,
        nonce=nonce
    )
    return redirect_url, state, nonce

def process_oauth_callback(code: str, state: str, stored_state: str) -> dict:
    """Process OAuth callback and validate tokens."""
    # Validate CSRF state
    if not secrets.compare_digest(state, stored_state):
        raise SecurityException("Invalid state parameter — possible CSRF attack")

    # Exchange code for tokens
    token = oauth.provider.authorize_access_token()
    id_token = token.get("id_token")

    # Validate ID token (signature, expiry, nonce, audience)
    user_info = oauth.provider.parse_id_token(token)

    return {
        "user_id": user_info["sub"],
        "email": user_info["email"],
        "groups": user_info.get("groups", []),
        "access_token": token["access_token"],
        "token_expiry": datetime.now() + timedelta(seconds=token["expires_in"])
    }
```

## Multi-Factor Authentication

```python
import pyotp
import qrcode

class MFAManager:
    def generate_totp_secret(self, user_id: str) -> dict:
        """Generate TOTP secret for a new MFA enrollment."""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)

        provisioning_uri = totp.provisioning_uri(
            name=user_id,
            issuer_name="YourApp"
        )

        # Generate QR code for authenticator app
        qr = qrcode.make(provisioning_uri)

        # Store TOTP secret securely (encrypted at rest)
        save_mfa_secret(user_id, encrypt(secret))

        return {
            "secret": secret,           # Show once, then discard
            "qr_code": qr,
            "provisioning_uri": provisioning_uri
        }

    def verify_totp(self, user_id: str, code: str) -> bool:
        """Verify a TOTP code."""
        secret = decrypt(get_mfa_secret(user_id))
        totp = pyotp.TOTP(secret)

        # Check current and adjacent time windows (±30 seconds for clock skew)
        is_valid = totp.verify(code, valid_window=1)

        if is_valid:
            # Prevent replay attacks — mark code as used
            if is_code_already_used(user_id, code):
                return False
            mark_code_used(user_id, code)

        return is_valid

    def verify_backup_code(self, user_id: str, code: str) -> bool:
        """Verify one-time backup code."""
        backup_codes = get_backup_codes(user_id)
        code_hash = hashlib.sha256(code.encode()).hexdigest()

        if code_hash in backup_codes:
            invalidate_backup_code(user_id, code_hash)
            return True
        return False
```

## Privileged Access Management (PAM)

```python
class PrivilegedAccessManager:
    """Just-in-time privileged access with approval workflow."""

    def request_elevated_access(self, requestor: str, target_resource: str,
                                  access_level: str, reason: str,
                                  duration_hours: int = 2) -> dict:
        """Request temporary elevated access."""
        request = {
            "id": str(uuid.uuid4()),
            "requestor": requestor,
            "target_resource": target_resource,
            "access_level": access_level,
            "reason": reason,
            "requested_duration_hours": duration_hours,
            "requested_at": datetime.now().isoformat(),
            "status": "pending",
            "approver": self.get_approver(access_level),
        }

        self.notify_approver(request)
        return request

    def approve_access(self, request_id: str, approver: str, approved_hours: int) -> dict:
        """Approve and provision temporary elevated access."""
        request = self.get_request(request_id)

        if request["approver"] != approver:
            raise PermissionDenied("Not authorized to approve this request")

        # Provision temporary credential
        temp_credential = self.provision_temp_access(
            user=request["requestor"],
            resource=request["target_resource"],
            level=request["access_level"],
            expires_at=datetime.now() + timedelta(hours=approved_hours)
        )

        # Enhanced monitoring for session
        self.enable_enhanced_monitoring(request["requestor"], temp_credential["session_id"])

        # Schedule automatic revocation
        self.schedule_revocation(temp_credential["session_id"],
                                  datetime.now() + timedelta(hours=approved_hours))

        return temp_credential

    def provision_temp_access(self, user: str, resource: str, level: str,
                               expires_at: datetime) -> dict:
        """Create temporary, time-limited credentials."""
        # Use AWS STS AssumeRole for AWS resources
        sts = boto3.client("sts")
        response = sts.assume_role(
            RoleArn=f"arn:aws:iam::123456789:role/{level}-role",
            RoleSessionName=f"{user}-{datetime.now().strftime('%Y%m%d%H%M')}",
            DurationSeconds=int((expires_at - datetime.now()).total_seconds())
        )
        return {
            "session_id": response["Credentials"]["SessionToken"][:20],
            "access_key": response["Credentials"]["AccessKeyId"],
            "secret_key": response["Credentials"]["SecretAccessKey"],
            "session_token": response["Credentials"]["SessionToken"],
            "expires_at": expires_at.isoformat()
        }
```

## Access Review Process

```python
def run_quarterly_access_review(all_users: list, all_roles: dict) -> dict:
    """Generate access review report for approval."""
    review_items = []

    for user in all_users:
        last_login_days = (datetime.now() - user["last_login"]).days
        role = all_roles.get(user["role"])

        # Flag for review:
        flags = []
        if last_login_days > 90:
            flags.append("inactive_90_days")
        if user["role"] in ("admin", "superuser") and last_login_days > 30:
            flags.append("privileged_inactive_30_days")
        if user.get("department") == "departed":
            flags.append("offboarded_user_has_access")
        if len(role.permissions) > 10 and user.get("job_title") in ("intern", "contractor"):
            flags.append("excessive_permissions_for_role")

        if flags:
            review_items.append({
                "user": user["email"],
                "current_role": user["role"],
                "last_login": user["last_login"],
                "flags": flags,
                "recommended_action": "disable" if "offboarded" in flags else "reduce_access",
                "reviewer": user.get("manager")
            })

    return {
        "review_date": datetime.now().date().isoformat(),
        "total_users": len(all_users),
        "items_requiring_review": len(review_items),
        "review_items": review_items
    }
```

## Identity Security Monitoring

```python
IDENTITY_THREAT_SIGNALS = {
    "impossible_travel": "Login from location > 800km from previous location in < 2 hours",
    "new_location": "Login from country not seen in past 30 days",
    "brute_force": "5+ failed logins within 10 minutes",
    "credential_stuffing": "Valid login after multiple failed attempts on other accounts",
    "off_hours_admin": "Admin activity outside business hours (10pm-6am local time)",
    "bulk_data_access": "User accessing > 10x their average data volume",
    "mfa_fatigue": "15+ MFA push requests in 30 minutes",
}

def detect_identity_threats(login_events: list) -> list:
    """Run behavioral analytics on login events."""
    alerts = []

    for event in login_events:
        # Check impossible travel
        prev_login = get_previous_login(event["user_id"])
        if prev_login:
            distance = haversine(prev_login["location"], event["location"])
            time_delta = (event["timestamp"] - prev_login["timestamp"]).seconds / 3600
            speed = distance / max(time_delta, 0.001)

            if speed > 800 and distance > 200:
                alerts.append({
                    "type": "impossible_travel",
                    "user": event["user_id"],
                    "distance_km": distance,
                    "speed_kph": speed,
                    "severity": "high"
                })

    return alerts
```
