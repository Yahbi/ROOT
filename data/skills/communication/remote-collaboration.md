---
name: Remote Collaboration
description: Async communication, documentation-first culture, timezone management, tools
version: "1.0.0"
author: ROOT
tags: [communication, remote-work, async, collaboration, timezone, documentation]
platforms: [all]
---

# Remote Collaboration

Build effective remote teams by defaulting to async communication and deliberate documentation practices.

## Async-First Communication

### The Async Hierarchy
| Priority | Channel | Response Time | Use For |
|----------|---------|---------------|---------|
| 1 (default) | Long-form doc (Notion, Google Docs) | 24-48 hours | Decisions, proposals, design docs |
| 2 | Threaded message (Slack thread, Linear comment) | 4-8 hours | Questions, updates, feedback |
| 3 | Direct message | 2-4 hours | Personal matters, quick clarifications |
| 4 | Scheduled call | Arranged | Complex discussions, relationship building |
| 5 (rare) | Unscheduled call/page | Immediate | Production incidents, genuine emergencies |

### Writing Effective Async Messages
```
Bad: "Hey, can we talk about the API?"

Good: "I'm proposing we change the /api/chat endpoint to accept
streaming responses. Here's the context:
- Current: Buffered response, average 3.2s wait
- Proposed: Server-sent events, first token in ~200ms
- Trade-off: More complex client code, but 16x better perceived latency
- I need: Your input on whether SSE or WebSocket is better for our stack
- Deadline: Decision by Friday so we can include in next sprint"
```

### Async Decision-Making
1. **Proposer** writes a decision document with context, options, and recommendation
2. **Reviewers** comment within 48-hour review window
3. **Silence = consent**: If no objections after review period, the proposal is accepted
4. **Disagree and commit**: If no consensus, decision-maker decides, all commit
5. Document the decision and rationale (ADR or meeting notes)

## Documentation-First Culture

### What to Document
| Document | Purpose | Update Frequency |
|----------|---------|-----------------|
| Project README | How to set up, run, and contribute | On every setup change |
| Architecture diagram | System overview for onboarding | Quarterly or on major changes |
| API documentation | Endpoint reference for consumers | On every API change |
| Runbooks | How to handle common incidents | After every incident |
| Decision log (ADRs) | Why we made key decisions | On every significant decision |
| Team handbook | Processes, norms, tools | Quarterly review |

### Writing for Remote Audiences
- Over-communicate context (readers do not have the hallway conversation)
- Use headings and bullet points (scannable > prose)
- Link to related documents (remote workers cannot walk over and ask)
- Include screenshots and diagrams (visual context reduces ambiguity)
- State assumptions explicitly (do not assume shared context)

### The 30-Minute Documentation Rule
If you explained something to someone in a call or DM, spend 30 minutes writing it down afterward. The next person with the same question will find the document instead of interrupting you.

## Timezone Management

### Overlap Windows
```
Team across US Pacific, US Eastern, and Europe (CET):

Pacific:  06:00 ████████████████████░░░░  22:00
Eastern:  09:00 ░░░████████████████████░  01:00
CET:      15:00 ░░░░░░░░░████████████████ 07:00

Overlap (all three): 09:00-12:00 Pacific / 12:00-15:00 Eastern / 18:00-21:00 CET
→ Schedule all-hands meetings in this window
→ All other communication is async
```

### Timezone Norms
- Always specify timezone in meeting invites and deadlines ("Friday 5pm PT")
- Use a shared timezone tool (worldtimebuddy.com) in team bookmarks
- Never expect immediate response outside someone's working hours
- Rotate meeting times for fairness if team spans 8+ hour difference
- Record all meetings (absentees catch up async)

### Handoff Practices
- End-of-day summary: what you completed, what is in progress, what is blocked
- Shared project board visible to all timezones (Linear, Jira, GitHub Projects)
- Tag the next timezone when handing off: "@europe-team: PR ready for review"

## Remote Meeting Best Practices

### Default to Cameras On (with Exceptions)
- Camera-on builds connection and enables non-verbal communication
- Acceptable camera-off: listening-only in large meetings, bad connection, personal reasons
- Never mandate cameras without providing psychological safety

### Meeting Structure for Remote
| Duration | Format | Example |
|----------|--------|---------|
| 15 min | Standup: text update + voice only for blockers | Daily sync |
| 30 min | Agenda-driven, one decision per meeting | Sprint planning, design review |
| 60 min | Deep discussion with pre-read required | Architecture review, retrospective |
| 90 min+ | Avoid. Break into multiple sessions | Workshop (if needed, include breaks) |

## Tools and Practices

### Essential Remote Stack
| Category | Tool | Purpose |
|----------|------|---------|
| Async comms | Slack (with threads enforced) | Day-to-day communication |
| Documentation | Notion or Confluence | Knowledge base, meeting notes, RFCs |
| Project tracking | Linear or GitHub Projects | Task management, sprint planning |
| Video calls | Zoom or Google Meet | Synchronous meetings (recorded) |
| Whiteboarding | Excalidraw or Miro | Visual collaboration, architecture diagrams |
| Code review | GitHub PRs | Async code discussion with inline comments |

### Building Remote Culture
- Virtual coffee chats: 15-minute 1-on-1s with random teammates (weekly)
- Team channel for non-work topics (pets, hobbies, wins)
- Quarterly in-person meetups if budget allows (relationship building)
- Celebrate wins publicly in team channel (remote teams miss the spontaneous applause)
- Assume good intent in text (messages lack tone; add emoji or explicit tone when needed)
