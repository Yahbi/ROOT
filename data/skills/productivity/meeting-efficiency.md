---
name: Meeting Efficiency
description: Agenda templates, timeboxing, async alternatives, action items
version: "1.0.0"
author: ROOT
tags: [productivity, meetings, timeboxing, async, facilitation]
platforms: [all]
---

# Meeting Efficiency

Run meetings that produce decisions and action items, or replace them with async alternatives.

## Before the Meeting: Should This Be a Meeting?

### Decision Tree
```
Do you need real-time discussion?
  └── No → Send a document or message instead
  └── Yes → Do you need more than 2 people?
      └── No → Have a quick call or walk-over
      └── Yes → Schedule a meeting with an agenda
```

### Async Alternatives
| Meeting Type | Async Replacement |
|-------------|-------------------|
| Status update | Written update in Slack/doc (2-3 bullets per person) |
| FYI announcement | Email or recorded Loom video |
| Simple decision | Slack poll or RFC document with comment period |
| Code walkthrough | PR with detailed description + recorded demo |
| Brainstorming | Shared doc where everyone adds ideas over 24h, then discuss top 5 |

### The Meeting Cost Calculator
```
Meeting cost = number_of_attendees × duration_hours × avg_hourly_rate
  8 people × 1 hour × $75/hr = $600 per meeting
  Weekly for a year: $600 × 50 = $30,000

Ask: Would you write a $600 check for this meeting?
```

## Agenda Design

### Effective Agenda Template
```markdown
# Meeting: [Topic]
**Date**: YYYY-MM-DD  **Duration**: 30 min  **Facilitator**: [Name]

## Purpose
[One sentence: What decision or outcome should this meeting produce?]

## Pre-Read (complete before meeting)
- [Link to document, PR, or context]
- [Specific question to think about in advance]

## Agenda
1. [Topic] — [Owner] — [Time] — [Goal: Decide/Discuss/Inform]
2. [Topic] — [Owner] — [Time] — [Goal]
3. Action items and next steps — All — 5 min

## Attendees
- Required: [people whose input is needed for the decision]
- Optional: [people who should know but can read notes instead]
```

### Agenda Rules
- Every agenda item has a time box, an owner, and a goal type (Decide/Discuss/Inform)
- "Inform" items should be async whenever possible (do not read slides aloud)
- Share the agenda 24 hours in advance (attendees arrive prepared or decline)
- No agenda = decline the meeting. This is a cultural norm worth establishing

## During the Meeting

### Timeboxing
- Set a visible timer for each agenda item
- When time expires: "We have 2 minutes left on this topic. Can we decide, or do we need a follow-up?"
- Parking lot: write off-topic items on a list, address after the meeting or in a separate session
- Hard stop: end at the scheduled time regardless (respect people's next commitment)

### Facilitation Techniques
| Technique | When to Use | How |
|-----------|------------|-----|
| Round-robin | Quiet voices drowned out | Each person speaks in turn, no interruptions |
| Silent brainstorm | Groupthink dominating | Everyone writes ideas on sticky notes (2 min), then share |
| Fist-of-five | Quick consensus check | Hold up 1-5 fingers (1=disagree, 5=strong agree) |
| Disagree and commit | Decision stalled | State positions, pick one, everyone commits regardless |
| Parking lot | Off-topic tangent | "Great point — let's park that and follow up separately" |

### Meeting Hygiene
- Start on time (do not penalize punctual people by waiting for latecomers)
- One conversation at a time (no side channels or multitasking)
- Notes taken in real time in a shared document (not from memory after the meeting)
- Camera on for remote meetings when possible (non-verbal cues matter)

## After the Meeting

### Action Item Format
```markdown
## Action Items
- [ ] [Specific action] — @owner — due [date]
- [ ] [Specific action] — @owner — due [date]
- [ ] [Specific action] — @owner — due [date]

## Decisions Made
- [Decision 1]: [Rationale]
- [Decision 2]: [Rationale]

## Parking Lot (follow up separately)
- [Topic] — @owner to schedule
```

### Action Item Rules
- Every action item has an owner and a due date (no orphans)
- Send notes within 1 hour of the meeting (while memory is fresh)
- Review action items at the start of the next recurring meeting
- If an action item is not done after two meetings, escalate or drop it

## Recurring Meeting Audit

### Quarterly Review Questions
1. Is this meeting still necessary? (Would anyone notice if we cancelled it?)
2. Can the frequency be reduced? (Weekly to biweekly, biweekly to monthly?)
3. Are the right people in the room? (Too many → observers read notes instead)
4. Is the duration right? (Most 1-hour meetings can be 30 minutes with a tight agenda)
5. Are we producing decisions and action items? (If not, convert to async format)
