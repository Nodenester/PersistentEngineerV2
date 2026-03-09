---
description: Start autonomous Plan → Build → Test loop with browser verification
argument-hint: "<task-description>" [--build-command "<cmd>"] [--test-url "<url>"] [--max-iterations <n>]
---

# Build-Test-Loop Command Implementation

When this command is invoked, you MUST:

1. **Clean up previous state** (delete old tracking files)
2. **Parse the arguments** from the command invocation
3. **Auto-detect build command and test URL** (if not provided)
4. **Create the state file** at `.claude/build-test-loop.local.md` with the configuration
5. **Start the loop** by outputting a message and waiting for the Stop hook to take over

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
- First argument (required): The task description
- `--build-command "<cmd>"` (optional - YOU figure it out if not provided!)
- `--test-url "<url>"` (optional - YOU figure it out if not provided!)
- `--max-iterations <n>` (optional, default: 50)

## Determine Build & Test Settings (YOU Figure This Out!)

**You have a full computer with all runtimes installed. LOOK at the project and determine:**

1. **Build Command** - Examine project files:
   - `package.json` → Look at "scripts" section for build/dev commands
   - `*.csproj`/`*.sln` → Use `dotnet build`
   - `Cargo.toml` → Use `cargo build`
   - `pyproject.toml`/`setup.py` → Use `pip install -e .` or `python -m build`
   - `go.mod` → Use `go build ./...`
   - `pom.xml` → Use `mvn clean install`

2. **Test URL** - After starting the dev server, note what port it uses:
   - Run the dev server command (e.g., `npm run dev`)
   - Check the output for the URL (usually localhost:PORT)
   - Use that as your test URL

3. **For CLI/non-web projects** - Just run the program directly and verify output

**DO NOT rely on scripts** - you're smart enough to read the project files and figure it out!

## State File Creation

Create `.claude/build-test-loop.local.md` with this exact format:

```yaml
---
enabled: true
phase: "plan"
iteration: 0
max_iterations: <from args or 50>
build_command: "<from args or npm run build>"
test_url: "<from args or http://localhost:3000>"
original_prompt: "<task description from args>"
develop_failures: 0
---

# Build-Test-Loop State

**Current Phase:** plan
**Iteration:** 0 / <max_iterations>
**Build Command:** `<build_command>`
**Test URL:** <test_url>

## Phase Progression

1. ⏳ **PLAN** - Create implementation plan
2. ⏳ **DEVELOP** - Build until finnished with task and compilation succeeds
3. ⏳ **TEST** - Verify with web testing
4. ⏳ **DONE** - All tests passed!

## Original Task

<original_prompt>

---
*This file is managed by build-test-loop plugin. Edit carefully.*
```

## Starting Message

After creating the state file, output:

```
🚀 Build-Test-Loop started!

Phase: PLAN
Task: <task description>
Build: <build_command>
Test URL: <test_url>
Max iterations: <max_iterations>

The loop will now begin. The Stop hook will control phase transitions automatically.
```

Then IMMEDIATELY attempt to stop (which will trigger the Stop hook and start the PLAN phase).

---

# Build-Test-Loop Documentation

Start an autonomous development loop that:
1. **Plans** your implementation
2. **Develops** until the build succeeds
3. **Tests** in the browser to verify it works
4. **Loops back** to develop if tests fail
5. **Completes** when all tests pass

## 🚀 ONE-SHOT USAGE (Recommended!)

**Just give it your task - the agent figures out the rest:**

```bash
/build-test-loop "Add a dark mode toggle to the settings page"
```

That's it! The agent will:
- ✅ Examine your project to determine build commands
- ✅ Start the dev server and note the test URL
- ✅ Run the entire plan → build → test loop
- ✅ Loop until tests pass

## Advanced Usage (Manual Override)

Only use this if you want to specify exact commands:

```bash
/build-test-loop "Your task description" \
  --build-command "custom build command" \
  --test-url "http://localhost:9000" \
  --max-iterations 100
```

## Arguments

The first argument is your task description. Everything after that is optional:

- `--build-command "<cmd>"` - Command to build the project (default: `npm run build`)
- `--test-url "<url>"` - URL to test in browser (default: `http://localhost:3000`)
- `--max-iterations <n>` - Safety limit for iterations (default: 50)

## How It Works

### Phase 1: PLAN
- Creates detailed implementation plan
- Identifies files, components, dependencies
- Plans testing approach
- Outputs: `<promise>PLAN_COMPLETE</promise>`

### Phase 2: DEVELOP
- Implements the solution iteratively
- Runs build command after each change
- Analyzes build errors and fixes them
- Loops until build succeeds
- Outputs: `<promise>BUILD_SUCCESS</promise>`

### Phase 3: TEST
- Uses browser automation to test functionality
- Verifies all requirements are met
- Documents test results
- Outputs: `<promise>TESTS_PASSED</promise>` or `<promise>TESTS_FAILED</promise>`

### Loop Back
- If tests fail → returns to DEVELOP phase
- Tracks number of develop-test cycles
- Continues until tests pass or max iterations reached

## Examples

### Simple React Feature
```bash
/build-test-loop "Add a user profile dropdown in the navbar with logout button"
```

### With Custom Build
```bash
/build-test-loop "Implement shopping cart with add/remove items" \
  --build-command "npm run build && npm run test" \
  --test-url "http://localhost:3000/cart"
```

### Backend API
```bash
/build-test-loop "Create /api/users CRUD endpoint with validation" \
  --build-command "go build ./cmd/server" \
  --test-url "http://localhost:8080"
```

## State Management

State is tracked in `.claude/build-test-loop.local.md`:

```yaml
---
enabled: true
phase: "develop"
iteration: 12
max_iterations: 50
build_command: "npm run build"
test_url: "http://localhost:3000"
original_prompt: "Add dark mode toggle"
develop_failures: 1
---
```

## Canceling

To stop the loop early:

```bash
/cancel-build-test-loop
```

Or edit `.claude/build-test-loop.local.md` and set `enabled: false`

## Tips for Success

### ✅ Good Task Descriptions
- "Add authentication with JWT tokens and login page"
- "Implement real-time chat with WebSocket connection"
- "Create admin dashboard with user management table"

### ❌ Vague Descriptions
- "Make it better" (too vague)
- "Fix everything" (no clear goal)
- "Add some features" (unspecified)

### Build Commands
- **Node/React:** `npm run build` or `npm run build && npm test`
- **Python:** `python -m build` or `pytest`
- **Go:** `go build ./...`
- **Rust:** `cargo build`
- **Java:** `mvn clean install`

### Test URLs
- Development server: `http://localhost:3000`
- Specific page: `http://localhost:3000/dashboard`
- API endpoint: `http://localhost:8080/api/health`

## Completion Signals

The loop looks for these exact strings in Claude's output:

- `<promise>PLAN_COMPLETE</promise>` - Planning done
- `<promise>BUILD_SUCCESS</promise>` - Build succeeded
- `<promise>TESTS_PASSED</promise>` - Tests passed (success!)
- `<promise>TESTS_FAILED</promise>` - Tests failed (loop back)

Make sure your task requirements are testable in a browser!

## Safety

- Always includes `--max-iterations` safety limit (default: 50)
- Loop stops if max iterations reached
- State file tracks progress
- Can cancel anytime with `/cancel-build-test-loop`

---

*Inspired by the Ralph Wiggum technique - persistent iteration until success!*
