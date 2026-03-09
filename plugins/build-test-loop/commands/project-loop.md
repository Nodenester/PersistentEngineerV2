---
description: Start autonomous multi-stage development loop with configurable stage types
argument-hint: "<project-description>" [--build-command "<cmd>"] [--test-url "<url>"] [--max-iterations <n>]
---

# Project-Loop Command Implementation

When this command is invoked, you MUST:

1. **Clean up previous state** (delete old tracking files)
2. **Parse the arguments** from the command invocation
3. **Auto-detect build command and test URL** (if not provided)
4. **Create the state file** at `.claude/project-loop.local.md`
5. **Start the ANALYZE phase** immediately

## Cleanup Previous State (ALWAYS DO THIS FIRST!)

Before starting, remove any leftover files from previous runs:

```bash
rm -f .claude/build-test-loop.local.md 2>/dev/null || true
rm -f .claude/project-loop.local.md 2>/dev/null || true
rm -f .claude/walkthrough.md 2>/dev/null || true
rm -rf .claude/stages 2>/dev/null || true
mkdir -p .claude
```

This ensures a fresh start every time.

## Argument Parsing

Extract these from the user's command:
- First argument (required): The project/feature description
- `--build-command "<cmd>"` (optional - YOU figure it out if not provided!)
- `--test-url "<url>"` (optional - YOU figure it out if not provided!)
- `--max-iterations <n>` (optional, default: 500)

## Determine Build & Test Settings (YOU Figure This Out!)

**You have a full computer with all runtimes installed. LOOK at the project and determine:**

1. **Examine Project Structure** - Use `code-structure-analyzer` or read files:
   - What language/framework is this?
   - What are the entry points?
   - How do you build and run it?

2. **Build Command** - Based on what you find:
   - `package.json` → Check "scripts" for build/dev/start commands
   - `*.csproj` → `dotnet build` then `dotnet run`
   - `Cargo.toml` → `cargo build` then `cargo run`
   - `go.mod` → `go build` then run the binary
   - `pom.xml` → `mvn clean install` then `mvn spring-boot:run`

3. **Test URL** - Start the dev server and note the port from output:
   - Web apps show "Listening on http://localhost:XXXX"
   - Use whatever port it reports

4. **Non-web projects** - Just run and verify the output directly

**DO NOT rely on auto-detect scripts** - you're intelligent, examine the codebase!

## State File Creation

Create `.claude/project-loop.local.md` with this format:

```yaml
---
enabled: true
phase: "analyze"
iteration: 0
max_iterations: <from args or 500>
build_command: "<from args or auto-detected>"
test_url: "<from args or auto-detected>"
original_prompt: "<project description from args>"
stages: []
current_stage: 0
stage_phase: "none"
develop_failures: 0
total_develop_failures: 0
workflow_mode: "build"
deployment_type: "local"
---

# Project-Loop State

**Status:** ANALYZE
**Iteration:** 0 / <max_iterations>
**Workflow:** BUILD | **Deploy:** LOCAL

## Project

<original_prompt>

## Stages

(Stages will be defined during ANALYZE phase)

---
*State file - Do not edit manually during active loop*
```

## Starting Message

After creating the state file, output:

```
🚀 Project-Loop v1.5 started!

Project: <project description>
Build: <build_command>
Test URL: <test_url>
Max iterations: <max_iterations>

Starting ANALYZE phase...
```

Then IMMEDIATELY begin the ANALYZE phase work (the Stop hook will guide you through it).

---

# Project-Loop v1.5 Documentation

An advanced autonomous development system that breaks your project into stages and executes each with the appropriate workflow.

## Quick Start

**Just describe what you want to build:**

```bash
/project-loop "Build a user authentication system with login, registration, and password reset"
```

That's it! The agent will:
1. Analyze your project and break it into logical stages
2. Examine the codebase to determine build commands and test URLs
3. Determine the best workflow for each stage
4. Execute each stage autonomously - running, testing, and fixing
5. Loop until everything works

**The agent has a full computer** - it can run any runtime (Node, .NET, Rust, Python, Go, Java) and test any kind of application!

## Stage Types

The system supports 5 stage types with different behaviors:

| Type | Plan | Develop | Test | Loops | Use For |
|------|------|---------|------|-------|---------|
| `investigate` | ✓ | ✗ | ✓ | ✗ | Finding bugs, exploring issues |
| `build` | ✓ | ✓ | ✓ | ✓ | Building new features |
| `fix` | ✗ | ✓ | ✓ | ✓ | Quick fixes, patches |
| `verify` | ✗ | ✗ | ✓ | ✗ | Final verification |
| `document` | ✓ | ✗ | ✗ | ✗ | Documentation only |

### Stage Type Behaviors

**investigate** - Browser test first to find issues
- Creates a plan for what to look for
- Tests in browser, documents findings
- Does NOT loop (findings are documented and you move on)

**build** - Full development cycle
- Plans the implementation
- Develops until build succeeds
- Tests in browser
- Loops back to develop if tests fail

**fix** - Quick fixes without detailed planning
- Jumps straight to development
- Tests after fixing
- Loops until tests pass

**verify** - Just test existing work
- No planning, no development
- Only browser testing
- Documents results and moves on

**document** - Documentation only
- Creates documentation/plans
- No testing
- Moves to next stage when done

## Defining Stages

### Simple Format (Auto-Detected Types)

Stage types are auto-detected from keywords in the name:

```yaml
stages: ["Investigate Login Bug", "Fix Authentication", "Verify Everything Works"]
```

- "Investigate", "Debug", "Find", "Explore" → `investigate`
- "Fix", "Repair", "Patch" → `fix`
- "Verify", "Confirm", "Check", "Final" → `verify`
- "Document", "Docs", "Readme" → `document`
- Everything else → `build`

### Advanced Format (Explicit Types)

For full control, use objects:

```yaml
stages: [
  {"name": "Find All Bugs", "type": "investigate"},
  {"name": "Fix Critical Issues", "type": "fix"},
  {"name": "Add New Feature", "type": "build"},
  {"name": "Final Verification", "type": "verify"}
]
```

### Custom Overrides

Override any default behavior:

```yaml
stages: [
  {
    "name": "Special Stage",
    "type": "build",
    "has_plan": false,
    "has_test": true,
    "loop_on_failure": false
  }
]
```

## File Organization

```
.claude/
├── project-loop.local.md      # State machine (YAML frontmatter)
├── walkthrough.md             # Project overview (created during ANALYZE)
└── stages/                    # Per-stage documentation
    ├── stage-1-plan.md        # Stage 1 plan
    ├── stage-1-notes.md       # Stage 1 notes/findings
    ├── stage-2-plan.md
    └── ...
```

**Important:**
- `walkthrough.md` is created ONCE during ANALYZE and shows the high-level project plan
- Stage plans go in `.claude/stages/` - one file per stage
- The state file tracks progress but shouldn't be edited manually

## Workflow Modes

The system detects the appropriate workflow from your request:

**DEBUG Mode** - When you mention testing, finding bugs, debugging
```bash
/project-loop "Find and fix the authentication bugs users are reporting"
```

**BUILD Mode** - When you mention adding, creating, implementing
```bash
/project-loop "Add a shopping cart with checkout flow"
```

**HYBRID Mode** - Complex requests needing both
```bash
/project-loop "Investigate performance issues and implement optimizations"
```

## Deployment Types

Detected from project files (CLAUDE.md, .github/workflows/):

- **LOCAL** - Build and test immediately on localhost
- **CICD** - Push to git, wait for CI/CD, then test
- **MANUAL** - Build locally, manual deployment steps

## Usage Examples

### Debug Workflow
```bash
/project-loop "Users report login sometimes fails - investigate and fix"
```
Creates stages like:
1. Investigate Login Issues (investigate)
2. Fix Authentication Bugs (fix)
3. Verify Login Works (verify)

### Feature Development
```bash
/project-loop "Build real-time chat with rooms and message history"
```
Creates stages like:
1. Chat Infrastructure (build)
2. Room Management (build)
3. Message History (build)
4. Final Integration (verify)

### Large Project
```bash
/project-loop "Build a complete e-commerce platform with products, cart, checkout, and admin"
```
Creates 10+ stages covering each major feature area.

## Advanced Options

```bash
/project-loop "Your project" \
  --build-command "npm run build && npm test" \
  --test-url "http://localhost:3000" \
  --max-iterations 1000
```

## Signals

The system uses these signals to control flow:

| Signal | Meaning |
|--------|---------|
| `<promise>ANALYZE_COMPLETE</promise>` | Analysis done, stages defined |
| `<promise>STAGE_PLAN_COMPLETE</promise>` | Stage planning complete |
| `<promise>STAGE_BUILD_SUCCESS</promise>` | Development/build succeeded |
| `<promise>STAGE_TESTS_PASSED</promise>` | Tests passed, move to next stage |
| `<promise>STAGE_TESTS_FAILED</promise>` | Tests failed (loops or moves on based on config) |

## Canceling

```bash
/cancel-project-loop
```

Or manually set `enabled: false` in `.claude/project-loop.local.md`

## Tips

### Good Project Descriptions
- "Build user authentication with social login, email verification, and 2FA"
- "Investigate why the API returns 500 errors and fix the issues"
- "Add dark mode support that persists across sessions"

### Stage Count
- No limit on stages! Use as many as needed
- Simple fix → 1-2 stages
- Medium feature → 3-5 stages
- Large project → 10-20+ stages

### Workflow Selection
- Use `investigate` when you don't know what's wrong yet
- Use `build` for new features
- Use `fix` when you know what to fix
- Use `verify` for final checks

---

*Project-Loop v1.5 - Autonomous development for any project, any size*
