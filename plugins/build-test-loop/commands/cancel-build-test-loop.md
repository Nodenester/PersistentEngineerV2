---
description: Cancel the active build-test-loop
---

# Cancel Build-Test-Loop Command Implementation

When this command is invoked, you MUST:

1. **Read** `.claude/build-test-loop.local.md`
2. **Update** the `enabled` field to `false`
3. **Confirm** the cancellation to the user

If the file doesn't exist, inform the user that no loop is currently active.

After updating, output: "✋ Build-Test-Loop canceled. The loop will stop on the next iteration."

---

# Cancel Build-Test-Loop Documentation

Cancels the currently running build-test-loop by disabling it in the state file.

## Usage

```bash
/cancel-build-test-loop
```

This will:
1. Set `enabled: false` in `.claude/build-test-loop.local.md`
2. Allow Claude to stop normally on the next iteration

## Alternative

You can also manually edit `.claude/build-test-loop.local.md` and set:

```yaml
enabled: false
```

The loop will stop on the next iteration.

## Resume

To resume a canceled loop, you can:
1. Edit the state file and set `enabled: true`
2. Or start a new loop with `/build-test-loop`

Note: Starting a new loop will reset all progress and start from the PLAN phase.
