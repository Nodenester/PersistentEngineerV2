---
description: Cancel the active project-loop
---

# Cancel Project-Loop Command Implementation

When this command is invoked, you MUST:

1. **Read** `.claude/project-loop.local.md`
2. **Parse** the current state to show progress
3. **Update** the `enabled` field to `false`
4. **Confirm** the cancellation with progress summary

If the file doesn't exist, inform the user that no project loop is currently active.

## Implementation Steps

1. Read the state file and extract:
   - Current phase
   - Current stage number and name
   - Total stages
   - Iteration count
   - Develop failures

2. Update the YAML frontmatter to set `enabled: false`

3. Output a summary like:

```
✋ Project-Loop canceled!

Progress saved:
- Phase: <current phase>
- Stage: <current> / <total> - <stage name>
- Stage type: <type>
- Iterations: <count>
- Failures overcome: <count>

Files preserved:
- State: .claude/project-loop.local.md
- Walkthrough: .claude/walkthrough.md
- Stage plans: .claude/stages/

The loop will stop on the next iteration.
You can resume later by setting enabled: true in the state file.
```

---

# Cancel Project-Loop Documentation

Cancels the currently running project-loop by disabling it in the state file.

## Usage

```bash
/cancel-project-loop
```

This will:
1. Set `enabled: false` in `.claude/project-loop.local.md`
2. Show you the current progress
3. Preserve all state for potential resumption

## What Gets Preserved

When you cancel, everything is saved:

```
.claude/
├── project-loop.local.md      # Full state (can resume from here)
├── walkthrough.md             # Project overview
└── stages/                    # All stage plans and notes
    ├── stage-1-plan.md
    ├── stage-1-notes.md
    └── ...
```

## Resuming

To resume a canceled loop:

1. Open `.claude/project-loop.local.md`
2. Change `enabled: false` to `enabled: true`
3. The loop will continue from where it left off

Or start fresh:

1. Delete `.claude/project-loop.local.md`
2. Run `/project-loop` with your description again

## Manual Cancel

You can also manually edit `.claude/project-loop.local.md` and set:

```yaml
enabled: false
```

The loop will stop on the next iteration.

## Viewing Progress

Even after canceling, you can review:

- **Overall progress:** Check `walkthrough.md` for completed stages (marked [x])
- **Stage details:** Look in `.claude/stages/` for plans and notes
- **Statistics:** The state file shows iterations and failure counts

---

*Cancel anytime, resume anytime - your progress is always preserved*
