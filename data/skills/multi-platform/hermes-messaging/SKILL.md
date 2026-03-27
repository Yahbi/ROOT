---
name: hermes-messaging
description: Send messages and execute tasks across multiple platforms via HERMES
version: 1.0.0
author: ROOT
tags: [messaging, telegram, discord, slack, hermes]
platforms: [darwin, linux, win32]
---

# Multi-Platform Messaging via HERMES

From HERMES gateway architecture.

## When to Use
- ROOT needs to reach Yohan on a specific platform
- Task requires sending notifications or updates
- Cross-platform coordination needed

## Supported Platforms
- **Telegram** — Rich formatting, file uploads
- **Discord** — Server channels, embeds
- **Slack** — Workspace messaging
- **WhatsApp** — No markdown, MEDIA:/path for attachments
- **Signal** — Encrypted messaging
- **Home Assistant** — IoT/smart home integration

## Platform-Specific Rules
- WhatsApp/Signal: No markdown formatting, plain text only
- Discord/Slack: Native file upload support
- Telegram: Full markdown, inline keyboards
- All: MEDIA:/path/to/file for attachments

## Integration
- Delegate to HERMES connector with platform + message
- HERMES handles authentication and delivery
- Check delivery status in HERMES session DB
