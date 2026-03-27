---
name: debugging
version: "1.0"
description: Systematic debugging methodology
category: development
tags: [debug, troubleshooting, bugs]
triggers: [debug this issue, troubleshoot a bug, find the root cause]
---

# Debugging

## Purpose
Apply a systematic debugging methodology to identify, isolate, and fix bugs efficiently by narrowing down root causes rather than guessing at solutions.

## Steps
1. Reproduce the bug reliably with a minimal set of steps and inputs
2. Gather evidence: read error messages, stack traces, logs, and relevant state
3. Form a hypothesis about the root cause based on the evidence
4. Isolate the problem by narrowing scope (binary search through code, bisecting commits)
5. Verify the hypothesis with targeted logging, breakpoints, or unit tests
6. Implement the fix addressing the root cause, not just the symptom
7. Verify the fix resolves the issue without introducing regressions, then add a test to prevent recurrence

## Output Format
A debugging report with the bug description, reproduction steps, root cause analysis, the fix applied, verification results, and any regression test added.
