---
name: debugging
description: Systematic approach to diagnosing and fixing software bugs
version: 1.0.0
author: ROOT
tags: [debugging, bugs, troubleshooting, development]
platforms: [darwin, linux, win32]
---

# Debugging Methodology

## Procedure
1. Reproduce: Get a reliable reproduction case
2. Isolate: Narrow to smallest failing unit
3. Hypothesize: Form theory about root cause
4. Test: Add logging/assertions to verify
5. Fix: Minimal change that fixes the issue
6. Verify: Confirm fix doesn't break other things
7. Prevent: Add test to prevent regression

## Common Root Causes
- Variable shadowing
- Off-by-one errors
- Async race conditions
- Null/None propagation
- Type coercion surprises
- Stale cache or state
