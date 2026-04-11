---
name: Notification Systems
description: Multi-channel alerting with priority routing, escalation chains, and delivery optimization
version: "1.0.0"
author: ROOT
tags: [automation, notifications, alerting, escalation, messaging]
platforms: [all]
---

# Notification Systems

Design and operate multi-channel alerting systems that deliver the right message to the right person at the right time with appropriate urgency.

## Multi-Channel Architecture

### Channel Selection Matrix

| Channel | Latency | Interruption | Rich Content | Confirmation | Best For |
|---------|---------|-------------|-------------|-------------|----------|
| Push notification | <1s | High | Low | No | Critical alerts |
| SMS | 1-5s | High | Low | Delivery receipt | Emergency fallback |
| Telegram | <1s | Medium | Medium | Read receipt | Technical alerts, bots |
| Discord | <1s | Medium | High | Reaction-based | Team alerts, status updates |
| Email | 1-60s | Low | High | Open tracking | Reports, summaries, non-urgent |
| Slack | <1s | Medium | High | Read receipt | Team collaboration alerts |
| Webhook | <1s | None | High | HTTP 200 | System-to-system integration |

### Channel Redundancy
- **Primary + fallback**: If Telegram fails, fall back to email + SMS; never rely on single channel
- **Deduplication**: Hash `(message_type, recipient, time_window)` to prevent duplicate alerts across channels
- **Rate limiting per channel**: Telegram max 30 messages/second; SMS varies by provider; respect limits
- **Quiet hours**: Suppress non-critical alerts 10PM-7AM local time; critical always deliver immediately

## Priority Routing Framework

### Priority Levels
- **P0 - Critical**: System down, security breach, financial loss; ALL channels simultaneously; require acknowledgment
- **P1 - High**: Degraded performance, failed trades, threshold breach; push + Telegram; escalate if no ack in 10min
- **P2 - Medium**: Anomalies, warnings, scheduled task failures; Telegram or Discord; batch if >5 per hour
- **P3 - Low**: Informational, status updates, daily digests; email or Discord; batch into hourly/daily summary
- **P4 - Debug**: Verbose logging, diagnostic data; webhook to logging system only; never interrupt humans

### Routing Logic
```
priority = assess_severity(event)
channels = PRIORITY_CHANNEL_MAP[priority]
for channel in channels:
    if within_rate_limit(channel) and not in_quiet_hours(channel, priority):
        send(channel, message, priority)
        if priority <= P1:
            schedule_escalation(event, ack_timeout=600)
```

## Escalation Chains

- **Level 1**: Automated response (restart service, retry operation); attempt self-healing first
- **Level 2**: Primary on-call (10-minute ack timeout); receives alert on all high-priority channels
- **Level 3**: Secondary on-call (20-minute ack timeout from L2 start); triggered if L2 doesn't acknowledge
- **Level 4**: Team lead / management (30-minute ack timeout); implies L2 and L3 are unavailable or unable
- **Level 5**: External escalation (vendor support, emergency contacts); for critical incidents only
- **Ack mechanism**: Telegram inline button, Slack emoji reaction, or API callback to confirm receipt
- **Auto-resolve**: If alert condition clears before acknowledgment, send resolution notification and cancel escalation

## Message Design Principles

- **Title**: Action-oriented; include severity and system (e.g., "[P1] Trading Engine: Order Execution Timeout")
- **Context**: What happened, current impact, affected systems/users
- **Action required**: Clear next step (investigate, acknowledge, escalate, none)
- **Links**: Deep link to dashboard, logs, or runbook; reduce time-to-action
- **Deduplication key**: Include in metadata; prevent alert fatigue from repeated identical alerts
- **Batching**: Group related P3/P4 alerts into digest every 15-60 minutes; never batch P0/P1

## Alert Fatigue Prevention

- **Suppression windows**: After alert fires, suppress identical alerts for N minutes (5min P1, 30min P2, 2hr P3)
- **Correlation**: Group related alerts into incidents; send single notification for incident, not per-alert
- **Threshold tuning**: Review alert thresholds monthly; if >50% of alerts require no action, thresholds are too sensitive
- **Alert scoring**: Track `action_rate = alerts_requiring_action / total_alerts`; target > 70%
- **Rotation**: Rotate on-call responsibility; burnout from constant alerting degrades response quality
- **Metric**: If average team member receives > 20 alerts/day, the system needs tuning

## Delivery Optimization

- **Retry logic**: Exponential backoff (1s, 2s, 4s, 8s); max 3 retries; switch channel after 3 failures
- **Idempotency**: Use unique message IDs; receivers should deduplicate by ID
- **Ordering guarantees**: For sequential events, include sequence number; receiver processes in order
- **Batching**: For P3/P4, batch into digests every 15-60 min; reduces noise by 80%+
- **Template versioning**: Version message templates; roll out new formats gradually; monitor delivery/open rates

## Risk Management

- **Channel outage**: Monitor channel health; auto-switch to backup if primary delivery rate drops below 95%
- **Credential rotation**: API tokens for Telegram/Discord/Slack expire or get revoked; auto-alert on auth failures
- **Message content security**: Never include credentials, PII, or sensitive financial data in alert bodies
- **Audit trail**: Log every notification: timestamp, channel, recipient, priority, delivery status, ack time
- **Cost monitoring**: SMS costs $0.01-0.05/message; set monthly budget caps; prefer free channels (Telegram, Discord) for volume
