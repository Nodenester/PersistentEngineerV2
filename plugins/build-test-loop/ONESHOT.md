# ⚡ ONE-SHOT USAGE GUIDE

**The entire plugin in one command. Just describe what you want, walk away, come back to working code.**

## The Magic Command

```bash
/build-test-loop "Your task description here"
```

That's literally it. No configuration. No setup. Just your task.

## What Happens Automatically

### 1. 🔍 Auto-Detection (Instant)

The plugin scans your project and figures out:

| Project Type | Build Command Detected | Test URL Detected |
|-------------|----------------------|------------------|
| **React (Vite)** | `npm run build` | `http://localhost:5173` |
| **React (CRA)** | `npm run build` | `http://localhost:3000` |
| **Next.js** | `npm run build` | `http://localhost:3000` |
| **Vue** | `npm run build` | `http://localhost:8080` |
| **Angular** | `npm run build` | `http://localhost:4200` |
| **Svelte** | `npm run build` | `http://localhost:5173` |
| **Python (Flask)** | `pytest` | `http://localhost:5000` |
| **Python (Django)** | `pytest` | `http://localhost:8000` |
| **Go** | `go build ./... && go test ./...` | `http://localhost:8080` |
| **Rust** | `cargo build` | `http://localhost:8080` |
| **Java (Maven)** | `mvn clean install` | `http://localhost:8080` |
| **Java (Gradle)** | `./gradlew build` | `http://localhost:8080` |
| **.NET** | `dotnet build` | `http://localhost:5000` |

**Detects package manager too:** npm, yarn, pnpm, bun - uses the right one automatically!

### 2. 📋 Planning Phase (Autonomous)

Claude creates a detailed plan:
- Files needed
- Components to build
- How to test it

### 3. 🔨 Development Phase (Autonomous)

Claude codes until it builds successfully:
- Writes code
- Runs build command
- Fixes errors
- Repeats until clean build

### 4. 🧪 Test Phase (Autonomous)

Claude tests in actual browser:
- Starts dev server
- Uses browser automation
- Verifies functionality
- **If tests fail → back to step 3!**

### 5. ✅ Done!

Only stops when:
- Build succeeds ✓
- Tests pass ✓

## Real Examples

### Example 1: React Component
```bash
cd my-react-app
claude
```

```bash
/build-test-loop "Add a user profile dropdown in the navbar with logout button"
```

**Auto-detects:**
- Build: `npm run build` (or yarn/pnpm if you use those)
- URL: `http://localhost:3000`

**Result:** Fully working dropdown, tested in browser, ready to ship.

---

### Example 2: Python API
```bash
cd my-flask-api
claude
```

```bash
/build-test-loop "Create /api/users endpoint with GET, POST, PUT, DELETE and email validation"
```

**Auto-detects:**
- Build: `pytest`
- URL: `http://localhost:5000`

**Result:** Complete CRUD API with validation, tests passing.

---

### Example 3: Go Microservice
```bash
cd my-go-service
claude
```

```bash
/build-test-loop "Add health check endpoint at /health with database connection status"
```

**Auto-detects:**
- Build: `go build ./... && go test ./...`
- URL: `http://localhost:8080`

**Result:** Health endpoint working, tests passing, compiles clean.

---

### Example 4: Rust Web App
```bash
cd my-rocket-app
claude
```

```bash
/build-test-loop "Implement rate limiting middleware with configurable requests per minute"
```

**Auto-detects:**
- Build: `cargo build`
- URL: `http://localhost:8080`

**Result:** Rate limiting working, tests verify limits.

---

## When You Want to Watch

Open two terminals:

**Terminal 1:**
```bash
claude
/build-test-loop "Your task"
```

**Terminal 2:**
```bash
watch -n 2 cat .claude/build-test-loop.local.md
```

Watch the progress in real-time!

## When You Want to Walk Away

```bash
# Start it
/build-test-loop "Build the entire admin dashboard with user management"

# Close laptop, go get coffee, come back in 20 minutes
# Check results
cat .claude/build-test-loop.local.md
```

If it shows `phase: "done"` → You're good! ✅

## Override Auto-Detection (Rare)

Only needed for unusual setups:

```bash
# Custom build command
/build-test-loop "Your task" --build-command "make build && make test"

# Custom test URL
/build-test-loop "Your task" --test-url "http://localhost:9000"

# Both
/build-test-loop "Your task" \
  --build-command "bazel build //..." \
  --test-url "http://localhost:4000"
```

## Tips for Best Results

### ✅ Be Specific
```bash
# Good
/build-test-loop "Add pagination to user table with 10 users per page and next/prev buttons"

# Bad
/build-test-loop "Add pagination"
```

### ✅ Include Test Criteria
```bash
# Good
/build-test-loop "Add search bar that filters table as you type and highlights matches"

# Bad
/build-test-loop "Add search"
```

### ✅ One Feature at a Time
```bash
# Good
/build-test-loop "Add dark mode toggle"
# Then after it completes:
/build-test-loop "Add user preferences panel"

# Bad (too big)
/build-test-loop "Rebuild entire UI with dark mode, preferences, settings, and themes"
```

## Typical Timeline

| Project Complexity | Iterations | Time (Approx) |
|-------------------|-----------|---------------|
| **Simple component** | 5-15 | 2-5 minutes |
| **Medium feature** | 15-30 | 5-10 minutes |
| **Complex feature** | 30-60 | 10-20 minutes |
| **Multiple components** | 60-100 | 20-40 minutes |

*Times vary based on API speed and project size*

## Canceling

Changed your mind?

```bash
/cancel-build-test-loop
```

Or just close Claude. The state is saved in `.claude/build-test-loop.local.md`.

## Troubleshooting

### "Wrong build command detected"
```bash
# Override it
/build-test-loop "Your task" --build-command "your actual build command"
```

### "Wrong test URL"
```bash
# Override it
/build-test-loop "Your task" --test-url "http://localhost:YOUR_PORT"
```

### "Loop keeps failing"
- Check `.claude/build-test-loop.local.md` to see what phase it's stuck in
- Read the transcript to see what errors occurred
- Try a simpler version of the task first
- Cancel and retry: `/cancel-build-test-loop` then start again

## The Power of One-Shot

**Before this plugin:**
```
You: "Add dark mode"
Claude: *writes code*
You: "Now test it"
Claude: *tests*
You: "It doesn't persist, fix it"
Claude: *fixes*
You: "Test again"
Claude: *tests*
You: "Good!"
```
*10+ back-and-forth messages*

**With this plugin:**
```
You: /build-test-loop "Add dark mode that persists"
*close laptop*
*come back*
Done! ✅
```
*One command. Zero supervision.*

---

## Next Level: Chain Tasks

```bash
# Task 1
/build-test-loop "Add user authentication"
# *wait for completion*

# Task 2
/build-test-loop "Add password reset flow"
# *wait for completion*

# Task 3
/build-test-loop "Add email verification"
# *wait for completion*
```

Or write a simple script:
```bash
#!/bin/bash
claude << EOF
/build-test-loop "Add auth"
EOF

# Wait for completion (check state file)
while grep -q "enabled: true" .claude/build-test-loop.local.md; do
  sleep 10
done

claude << EOF
/build-test-loop "Add password reset"
EOF
```

---

**That's it. One command. Infinite possibilities.** 🚀
