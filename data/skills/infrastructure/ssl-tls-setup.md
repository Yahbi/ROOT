---
name: SSL/TLS Setup
description: Let's Encrypt automation, cert rotation, HSTS, cipher suites, mTLS
version: "1.0.0"
author: ROOT
tags: [infrastructure, ssl, tls, certificates, HSTS, mTLS, encryption]
platforms: [all]
---

# SSL/TLS Setup

Configure TLS correctly to protect data in transit with strong encryption and automated certificate management.

## Let's Encrypt Automation

### Certbot Setup
```bash
# Install and obtain certificate
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d example.com -d www.example.com

# Auto-renewal (certbot installs a systemd timer by default)
sudo systemctl status certbot.timer
# Test renewal: sudo certbot renew --dry-run
```

### ACME DNS Challenge (for wildcards and internal servers)
```bash
# Wildcard certificate requires DNS-01 challenge
sudo certbot certonly --dns-cloudflare \
  --dns-cloudflare-credentials ~/.secrets/cloudflare.ini \
  -d "*.example.com" -d example.com

# cloudflare.ini contents:
# dns_cloudflare_api_token = YOUR_API_TOKEN
```

### Certificate Renewal Best Practices
- Certificates renew 30 days before expiration (default)
- Deploy renewal hooks to reload web server: `--deploy-hook "systemctl reload nginx"`
- Monitor certificate expiry independently (do not trust auto-renewal blindly)
- Alert if certificate expires in < 14 days: `echo | openssl s_client -connect host:443 2>/dev/null | openssl x509 -noout -dates`

## Cipher Suite Configuration

### Nginx TLS Configuration
```nginx
ssl_protocols TLSv1.2 TLSv1.3;          # Drop TLS 1.0, 1.1 (insecure)
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;            # Let client choose (TLS 1.3 handles this)
ssl_session_timeout 1d;
ssl_session_cache shared:SSL:10m;
ssl_session_tickets off;                  # Disable for forward secrecy
ssl_stapling on;                          # OCSP stapling (faster validation)
ssl_stapling_verify on;
```

### TLS Version Decision
| Version | Status | Action |
|---------|--------|--------|
| TLS 1.0 | Deprecated | Disable everywhere |
| TLS 1.1 | Deprecated | Disable everywhere |
| TLS 1.2 | Current | Required minimum for most compliance |
| TLS 1.3 | Preferred | Enable everywhere (faster handshake, better security) |

## HSTS (HTTP Strict Transport Security)

### Configuration
```
# Header (start with short max-age, increase after verification)
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
```

### Deployment Steps
1. Ensure all HTTP redirects to HTTPS work correctly across all subdomains
2. Set `max-age=300` (5 minutes) initially to catch misconfigurations
3. Test thoroughly: mixed content, subdomains, internal tools
4. Increase to `max-age=63072000` (2 years) after validation
5. Submit to HSTS preload list: hstspreload.org (permanent, difficult to undo)

### HSTS Pitfalls
- `includeSubDomains` affects ALL subdomains (internal tools, staging)
- Preload list inclusion is effectively permanent (removal takes months)
- If any subdomain cannot serve HTTPS, do NOT use `includeSubDomains`

## Mutual TLS (mTLS)

### Service-to-Service Authentication
```nginx
# Server configuration (requires client certificate)
ssl_client_certificate /etc/ssl/ca.crt;   # CA that signed client certs
ssl_verify_client on;                       # Require valid client cert
ssl_verify_depth 2;                         # CA chain depth
```

### Certificate Generation for mTLS
```bash
# Generate CA (once)
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 \
  -days 3650 -noenc -keyout ca.key -out ca.crt -subj "/CN=Internal CA"

# Generate service certificate signed by CA
openssl req -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 \
  -noenc -keyout service.key -out service.csr -subj "/CN=my-service"
openssl x509 -req -in service.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out service.crt -days 365
```

### mTLS Operational Concerns
- Short-lived certificates (24h-30d) reduce blast radius of key compromise
- Automate rotation with SPIFFE/SPIRE or Vault PKI engine
- Certificate revocation: use short TTLs instead of CRL/OCSP for internal services
- Monitor certificate expiry across all services (centralized dashboard)

## Testing and Validation

### Quick Checks
```bash
# Test TLS configuration (look for A+ grade)
curl https://www.ssllabs.com/ssltest/analyze.html?d=example.com

# Check certificate details
openssl s_client -connect example.com:443 < /dev/null 2>/dev/null | \
  openssl x509 -noout -subject -issuer -dates -ext subjectAltName

# Test specific TLS version support
openssl s_client -connect example.com:443 -tls1_2
openssl s_client -connect example.com:443 -tls1_3
```

### Security Checklist
- [ ] TLS 1.0 and 1.1 disabled
- [ ] HSTS header with appropriate max-age
- [ ] OCSP stapling enabled
- [ ] Certificate auto-renewal tested and monitored
- [ ] No mixed content (HTTP resources on HTTPS pages)
- [ ] Forward secrecy ciphers only (ECDHE-based)
