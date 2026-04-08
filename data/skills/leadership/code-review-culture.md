---
name: Code Review Culture
description: Review guidelines, PR size limits, async reviews, constructive feedback
version: "1.0.0"
author: ROOT
tags: [leadership, code-review, pull-requests, feedback, engineering-culture]
platforms: [all]
---

# Code Review Culture

Establish code review practices that improve code quality, share knowledge, and maintain team velocity.

## Review Guidelines

### What to Look For (Priority Order)
1. **Correctness**: Does the code do what it claims? Edge cases handled? Race conditions?
2. **Security**: Input validation, auth checks, secret exposure, injection vectors
3. **Architecture**: Does it fit the existing patterns? Will it scale? Is the abstraction right?
4. **Readability**: Can someone unfamiliar understand this in 5 minutes? Clear naming?
5. **Testing**: Are the important paths tested? Are the tests testing behavior, not implementation?
6. **Performance**: Only if there's evidence of a problem (premature optimization is waste)

### Review Time Expectations
| PR Size | Review SLA | Reviewer Focus |
|---------|-----------|----------------|
| Small (< 100 lines) | Same day | Quick scan, approve if correct |
| Medium (100-400 lines) | Within 24 hours | Full review, test locally if risky |
| Large (400+ lines) | Discuss splitting first | Break into reviewable chunks |

### Reviewer Responsibilities
- Review within SLA (blocked PRs block team velocity)
- Test the change locally for anything touching critical paths
- Approve when "good enough" — do not pursue perfection
- Distinguish between blocking issues and nit-picks (prefix nits with "nit:")

## PR Size and Structure

### Optimal PR Size
- Target: < 200 lines of changed code (excluding generated files)
- Research shows review effectiveness drops sharply after 400 lines
- Large PRs get rubber-stamped; small PRs get genuine review

### Strategies for Small PRs
- **Stacked PRs**: Break feature into sequential PRs (DB migration → model → API → UI)
- **Feature flags**: Merge incomplete features behind flags (code in prod, not activated)
- **Extract refactoring**: Separate refactoring PR from feature PR (easier to review each)
- **Interface first**: PR 1 adds interface/types, PR 2 adds implementation

### PR Description Template
```markdown
## What
[One sentence: what does this change?]

## Why
[Context: why is this change needed? Link to issue/ticket]

## How
[Brief technical approach, especially if non-obvious]

## Testing
[How was this tested? What should the reviewer verify?]

## Screenshots
[If UI change, before/after screenshots]
```

## Async Review Process

### Making PRs Self-Reviewable
- Write a thorough PR description (reviewer should not need to ask "why")
- Add inline comments on your own PR explaining non-obvious decisions
- Include test results, performance benchmarks, or screenshots as applicable
- Mark draft PRs as draft (do not request review until ready)

### Review Workflow
1. Author opens PR with description and self-review comments
2. CI runs automatically (tests, lint, type checks must pass before review)
3. Reviewer receives notification, reviews within SLA
4. Author responds to all comments (resolve or discuss)
5. Reviewer approves or requests changes (max 2 round trips before synchronous discussion)
6. Author merges after approval (squash merge for clean history)

### Avoiding Review Bottlenecks
- Rotate reviewers (do not funnel all PRs through one senior engineer)
- Any team member can review any PR (knowledge sharing > gatekeeper expertise)
- Auto-assign reviewers via CODEOWNERS or round-robin
- Escalation: if no review after SLA, author pings in team channel

## Constructive Feedback

### Comment Categories
| Prefix | Meaning | Author Action |
|--------|---------|---------------|
| (none) | Blocking issue, must fix | Fix before merge |
| `nit:` | Style preference, minor | Fix if easy, skip if not |
| `question:` | Seeking understanding | Respond with explanation |
| `suggestion:` | Optional improvement idea | Consider for this or future PR |
| `praise:` | Something done well | Appreciate and continue |

### Feedback Principles
- Comment on the code, not the person ("This function is hard to follow" not "You wrote confusing code")
- Explain why, not just what ("This could cause a race condition because..." not "Don't do this")
- Offer alternatives when criticizing ("Consider using X instead, because...")
- Ask questions instead of making demands ("What happens if this is called twice?")
- Give praise for good patterns (positive reinforcement shapes behavior)

### Handling Disagreements
1. First round: exchange written arguments with technical reasoning
2. Second round: if still disagreed, have a 10-minute synchronous call
3. Third round: if unresolved, defer to team lead or architecture decision record
4. Never let a disagreement block a PR for more than 48 hours
