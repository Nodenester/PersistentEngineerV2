# Build-Test-Loop Plugin v1.5.0

**Autonomous development loops for any project, any size.**

Two powerful commands:
- `/build-test-loop` - Simple single-task loop (Plan → Build → Test)
- `/project-loop` - Advanced multi-stage projects with configurable stage types

---

## Quick Start

### Simple Task (build-test-loop)

```bash
/build-test-loop "Add a dark mode toggle that persists in localStorage"
```

Walk away. Come back to working, tested code.

### Complex Project (project-loop)

```bash
/project-loop "Build user authentication with login, registration, password reset, and 2FA"
```

The system will:
1. Analyze and break into logical stages
2. Execute each stage with the appropriate workflow
3. Loop until everything works
4. Complete when all stages pass

---

## Two Commands, Two Use Cases

### /build-test-loop - Single Tasks

Best for:
- Adding a single feature
- Fixing a specific bug
- Implementing one component

Flow:
```
PLAN → DEVELOP → TEST → (loop if failed) → DONE
```

### /project-loop - Multi-Stage Projects

Best for:
- Building entire features with multiple parts
- Debugging complex issues
- Large development efforts

Flow:
```
ANALYZE → [Stage 1] → [Stage 2] → ... → [Stage N] → COMPLETE

Each stage can be:
- investigate (test first, find issues)
- build (plan → develop → test, loops)
- fix (develop → test, loops)
- verify (test only)
- document (plan only)
```

---

## /build-test-loop

### Usage

```bash
/build-test-loop "<task description>"
```

### With Options

```bash
/build-test-loop "Your task" \
  --build-command "npm run build" \
  --test-url "http://localhost:3000" \
  --max-iterations 50
```

### How It Works

1. **PLAN** - Creates implementation plan
2. **DEVELOP** - Codes until build succeeds
3. **TEST** - Verifies in browser
4. **LOOP** - If tests fail, back to develop
5. **DONE** - When tests pass

### Signals

- `<promise>PLAN_COMPLETE</promise>` → Move to DEVELOP
- `<promise>BUILD_SUCCESS</promise>` → Move to TEST
- `<promise>TESTS_PASSED</promise>` → Done!
- `<promise>TESTS_FAILED</promise>` → Back to DEVELOP

### Cancel

```bash
/cancel-build-test-loop
```

---

## /project-loop v1.5

### Usage

```bash
/project-loop "<project description>"
```

### Stage Types

| Type | Plan | Develop | Test | Loops | Use For |
|------|------|---------|------|-------|---------|
| `investigate` | ✓ | ✗ | ✓ | ✗ | Finding bugs, exploring |
| `build` | ✓ | ✓ | ✓ | ✓ | New features |
| `fix` | ✗ | ✓ | ✓ | ✓ | Quick fixes |
| `verify` | ✗ | ✗ | ✓ | ✗ | Final checks |
| `document` | ✓ | ✗ | ✗ | ✗ | Docs only |

### Stage Definition

**Simple (auto-detected types):**
```yaml
stages: ["Investigate Issues", "Fix Authentication", "Verify Everything"]
```

**Advanced (explicit types):**
```yaml
stages: [
  {"name": "Find Bugs", "type": "investigate"},
  {"name": "Fix Them", "type": "fix"},
  {"name": "Final Check", "type": "verify"}
]
```

**Custom overrides:**
```yaml
stages: [
  {
    "name": "Special Stage",
    "type": "build",
    "has_plan": false,
    "loop_on_failure": false
  }
]
```

### File Organization

```
.claude/
├── project-loop.local.md      # State machine
├── walkthrough.md             # Project overview (created once)
└── stages/                    # Per-stage documentation
    ├── stage-1-plan.md
    ├── stage-1-notes.md
    └── ...
```

### Workflow Modes

**DEBUG** - When request mentions testing, debugging, finding issues
```bash
/project-loop "Find and fix the login bugs"
```

**BUILD** - When request mentions adding, creating, implementing
```bash
/project-loop "Add shopping cart with checkout"
```

**HYBRID** - Complex requests needing both
```bash
/project-loop "Investigate performance and implement optimizations"
```

### Deployment Types

Detected from project files:
- **LOCAL** - Test immediately on localhost
- **CICD** - Push, wait for pipeline, then test
- **MANUAL** - Build locally, deploy manually

### Signals

- `<promise>ANALYZE_COMPLETE</promise>` → Stages defined
- `<promise>STAGE_PLAN_COMPLETE</promise>` → Stage planned
- `<promise>STAGE_BUILD_SUCCESS</promise>` → Stage builds
- `<promise>STAGE_TESTS_PASSED</promise>` → Next stage
- `<promise>STAGE_TESTS_FAILED</promise>` → Loop or continue

### Cancel

```bash
/cancel-project-loop
```

---

## Examples

### Simple Feature
```bash
/build-test-loop "Add a user profile dropdown in the navbar"
```

### Debug Session
```bash
/project-loop "Users report intermittent 500 errors - investigate and fix"
```
Creates stages:
1. Investigate API Errors (investigate)
2. Fix Server Issues (fix)
3. Verify Stability (verify)

### Large Feature
```bash
/project-loop "Build real-time chat with rooms, presence, and message history"
```
Creates stages:
1. Chat Infrastructure (build)
2. Room Management (build)
3. User Presence (build)
4. Message History (build)
5. Final Integration (verify)

### Full Application
```bash
/project-loop "Build e-commerce platform with products, cart, checkout, payments, and admin"
```
Creates 10+ stages covering each feature area.

---

## Auto-Detection

Both commands auto-detect:

**Build Commands:**
- Node.js → `npm/yarn/pnpm run build`
- Python → `pytest` or `python -m build`
- Go → `go build ./...`
- Rust → `cargo build`
- Java → `mvn clean install` or `./gradlew build`
- .NET → `dotnet build`

**Test URLs:**
- Vite → `http://localhost:5173`
- Next.js/CRA → `http://localhost:3000`
- Vue CLI → `http://localhost:8080`
- Angular → `http://localhost:4200`
- Flask → `http://localhost:5000`
- Django/FastAPI → `http://localhost:8000`

---

## Safety Features

- **Max iterations** - Prevents infinite loops (default: 50 for build-test-loop, 500 for project-loop)
- **Cancel commands** - Stop anytime
- **State persistence** - Resume later
- **Progress tracking** - Full visibility

---

## Tips

### Good Task Descriptions

✅ Specific and testable:
- "Add dark mode toggle that persists in localStorage"
- "Fix the login form validation errors"
- "Build user profile page with editable fields"

❌ Vague:
- "Make it better"
- "Fix bugs"
- "Add features"

### Stage Count (project-loop)

No limit! Use what makes sense:
- Bug fix → 1-2 stages
- Small feature → 2-3 stages
- Medium feature → 4-6 stages
- Large project → 10-20+ stages

### When to Use Which

Use `/build-test-loop` when:
- Single, focused task
- Clear success criteria
- One feature or fix

Use `/project-loop` when:
- Multiple related features
- Need to investigate first
- Large development effort
- Want stage-by-stage progress

---

## Architecture

```
build-test-loop/
├── .claude-plugin/
│   └── plugin.json              # Metadata (v1.5.0)
├── hooks/
│   ├── hooks.json               # Hook registration
│   ├── stop.py                  # build-test-loop controller
│   ├── stop_project.py          # project-loop controller (v1.5)
│   └── auto_detect.py           # Project detection
├── commands/
│   ├── build-test-loop.md       # Simple loop command
│   ├── project-loop.md          # Multi-stage command (v1.5)
│   ├── cancel-build-test-loop.md
│   └── cancel-project-loop.md
└── README.md
```

---

## Version History

### v1.5.0 (Current)
- **Stage Types** - 5 configurable types (investigate, build, fix, verify, document)
- **Per-Stage Behavior** - Skip plan, skip develop, skip test, loop control
- **Unlimited Stages** - No artificial limits
- **Better File Organization** - Separate walkthrough.md and stages/ directory
- **Workflow Detection** - DEBUG, BUILD, HYBRID modes
- **Deployment Awareness** - LOCAL, CICD, MANUAL types
- **Increased max_iterations** - 500 default for project-loop

### v1.4.0
- Multi-stage project support
- Walkthrough.md generation
- Basic workflow modes

### v1.0.0
- Initial release
- build-test-loop command
- Plan → Build → Test cycle

---

## Philosophy

> "Just keep planning, building, testing... Just keep planning, building, testing..."

This plugin embodies:
1. **Iteration over perfection** - Let the loop refine the work
2. **Automated verification** - Builds AND tests must pass
3. **Failure as feedback** - Test failures drive improvements
4. **Persistence** - Keep trying until success
5. **Freedom** - Give Claude autonomy to solve problems

---

## Credits

- Inspired by the [Ralph Wiggum Technique](https://ghuntley.com/ralph/) by Geoffrey Huntley
- Built for [Claude Code](https://claude.ai/claude-code)

## Author

nestor

## License

MIT

---

**Walk away. Come back to working code.** 🚀
