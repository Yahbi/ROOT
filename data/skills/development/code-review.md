---
name: code-review
version: "1.0"
description: Review code for quality and bugs
category: development
tags: [code, review, quality]
triggers: [review this code, check code quality, find bugs in code]
---

# Code Review

## Purpose
Systematically review code for correctness, readability, performance, security vulnerabilities, and adherence to best practices, providing actionable feedback to improve quality.

## Steps
1. Understand the context: what the code is supposed to do and why the change was made
2. Check correctness: verify logic, edge cases, boundary conditions, and error handling
3. Evaluate readability: naming conventions, function size, comments, and code structure
4. Assess performance: identify unnecessary computations, N+1 queries, or memory issues
5. Scan for security issues: input validation, injection risks, authentication gaps, secret exposure
6. Verify test coverage: confirm tests exist for critical paths and edge cases
7. Provide feedback categorized by severity (critical, high, medium, low) with specific suggestions

## Output Format
A structured code review with findings organized by severity level, each including the file and line reference, description of the issue, and a suggested fix or improvement.
