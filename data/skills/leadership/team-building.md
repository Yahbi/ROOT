---
name: Team Building
description: Hiring, onboarding, 1-on-1s, psychological safety, team topologies
version: "1.0.0"
author: ROOT
tags: [leadership, team-building, hiring, onboarding, psychological-safety, management]
platforms: [all]
---

# Team Building

Build and maintain high-performing engineering teams through deliberate practices.

## Hiring

### Interview Process Design
1. **Screening call** (30 min): Motivation, experience overview, role fit, logistics
2. **Technical assessment** (60-90 min): Real-world problem, not algorithm puzzles
3. **System design** (60 min): Architecture discussion at appropriate seniority level
4. **Team fit** (45 min): Collaboration style, communication, values alignment
5. **Reference check**: Ask specific behavioral questions, not just "would you rehire?"

### What to Evaluate
| Signal | How to Assess | Red Flag |
|--------|--------------|----------|
| Problem-solving | Give ambiguous problem, watch how they clarify | Jumps to solution without understanding problem |
| Communication | Explain technical decision to non-technical person | Cannot adjust communication to audience |
| Collaboration | Pair programming exercise | Dismisses input, defensive about feedback |
| Growth mindset | Ask about recent failure and what they learned | Blames others, no self-reflection |
| Technical depth | Deep-dive on a project they led | Cannot explain decisions behind their own work |

### Structured Scoring
- Score each dimension independently (1-4 scale) before discussing with other interviewers
- Make hire/no-hire decision BEFORE group debrief (avoid anchoring bias)
- Document specific evidence for each score (not "gut feeling")

## Onboarding

### First Week Checklist
- [ ] Development environment set up and first commit merged (day 1-2)
- [ ] Architecture walkthrough with diagrams (day 2)
- [ ] Paired with onboarding buddy (not their manager)
- [ ] Access to all tools: repo, CI/CD, monitoring, communication channels
- [ ] Meet team members 1-on-1 (15 min each)
- [ ] First real task assigned (small, well-scoped, not a "toy" project)

### 30-60-90 Day Plan
| Period | Goal | Metric |
|--------|------|--------|
| 30 days | Ship first meaningful contribution, understand codebase | PR merged, can navigate code independently |
| 60 days | Own a feature end-to-end, participate in on-call | Completed feature, handled on-call shift |
| 90 days | Contribute to design discussions, mentor newer joiners | Design doc authored, identified improvement |

## 1-on-1 Meetings

### Structure (30 minutes, weekly)
- **Their agenda first** (15 min): What do they want to discuss? Blockers, concerns, ideas
- **Your agenda** (10 min): Feedback, context, upcoming changes
- **Growth** (5 min): Career goals, learning opportunities, stretch assignments

### Effective Questions
- "What's the biggest obstacle you're facing right now?"
- "What's something that's working well that we should do more of?"
- "Is there anything you'd change about how the team operates?"
- "What skill do you want to develop in the next 3 months?"
- "How do you feel about your workload?" (energy/engagement, not just hours)

### Anti-Patterns
- Using 1-on-1s for status updates (use standups or async updates for that)
- Canceling regularly (signals their time is not valued)
- Talking more than listening (aim for 70% them, 30% you)
- Avoiding difficult conversations (address issues early when they are small)

## Psychological Safety

### Behaviors That Build Safety
- Admit your own mistakes publicly ("I was wrong about X, here's what I learned")
- React to bad news with curiosity, not blame ("What can we learn from this?")
- Explicitly invite dissent ("What could go wrong with this plan?")
- Thank people for raising concerns, even when the concern is wrong
- Follow through on commitments made in team discussions

### Measuring Psychological Safety
Ask in anonymous surveys:
1. "If I make a mistake on this team, it is held against me" (reverse scored)
2. "Members of this team are able to bring up problems and tough issues"
3. "It is safe to take a risk on this team"
4. "I feel confident that no one on this team would undermine me"

## Team Topologies

### Four Team Types (Skelton & Pais)
| Type | Purpose | Example |
|------|---------|---------|
| Stream-aligned | Deliver value for a business domain | Feature team, product team |
| Platform | Reduce cognitive load for stream teams | Internal dev platform, CI/CD |
| Enabling | Help stream teams adopt new capabilities | Architecture guild, ML enablement |
| Complicated-subsystem | Own deep specialist knowledge | ML model team, cryptography |

### Interaction Modes
- **Collaboration**: Two teams work closely together (temporary, high bandwidth)
- **X-as-a-Service**: One team provides a service, other team consumes it (clear API)
- **Facilitating**: Enabling team coaches stream team (transfer knowledge, then step back)
