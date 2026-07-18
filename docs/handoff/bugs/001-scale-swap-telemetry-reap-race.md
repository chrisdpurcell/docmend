---
bug_id: '001'
date: 2026-07-18
title: Scale swap telemetry reap race
services: [scale-qualification]
status: fixed
---

# Scale swap telemetry reap race

## Cause

After a valid child `VmSwap` sample, Linux can briefly expose a structurally valid live `/proc/<pid>/status` record without `VmSwap` before exposing the terminal zombie snapshot. The supervisor called `Popen.poll()` during that recoverable gap. If the child had exited, `poll()` reaped it and removed the terminal `/proc` record before the supervisor could recover the required swap evidence.

A separate exit-coincident path also retained the earlier valid peak when the later status record was unreadable or structurally invalid, incorrectly treating incomplete telemetry as complete.

## Fix

When a valid sample is followed by the exact recoverable no-`VmSwap` gap, the supervisor waits one sampling interval and reads status again before polling. Initial gaps retain their existing behavior. If post-sample telemetry is unreadable or structurally invalid when exit is observed, swap availability is cleared unconditionally and qualification fails closed.

Regression tests cover the valid-sample → live-gap → zombie transition and unreadable, missing-field, and duplicate-field exit-coincident failures. The final installed-wheel one-million-file qualification recorded zero child swap for every stage.

## Lesson

`Popen.poll()` is not an observation-only liveness probe after process exit: it may reap the child and erase terminal `/proc` evidence. When correctness depends on terminal procfs telemetry, sample the recoverable transition before polling, and never let a prior valid sample mask a later invalid terminal observation.
