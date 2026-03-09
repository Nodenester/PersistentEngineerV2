# HOW TO USE BUILD-TEST-LOOP

## The Simplest Explanation

**You:** Give it a task
**Plugin:** Does everything automatically
**You:** Come back to working code

---

## Step-by-Step

### 1. Install (One Time)

```bash
cd C:\Users\nestor\build-test-loop-plugin
```

Your plugin is already here! ✅

### 2. Use It

Go to ANY project:

```bash
# React project
cd C:\Users\nestor\my-react-app
claude --plugin-dir C:\Users\nestor\build-test-loop-plugin
```

```bash
# Or Python project
cd C:\Users\nestor\my-flask-api
claude --plugin-dir C:\Users\nestor\build-test-loop-plugin
```

```bash
# Or ANY project
cd C:\Users\nestor\whatever
claude --plugin-dir C:\Users\nestor\build-test-loop-plugin
```

### 3. Give It ONE Command

```bash
/build-test-loop "Add a dark mode toggle that saves preference"
```

### 4. Walk Away

Literally. Close the laptop. Go do something else.

### 5. Come Back

```bash
cat .claude\build-test-loop.local.md
```

Look for: `phase: "done"`

**If you see `done` → It worked! Check your code!** ✅

---

## What It Auto-Detects

| You Have | It Detects Build Command | It Detects URL |
|----------|-------------------------|----------------|
| `package.json` (React) | `npm run build` | `http://localhost:3000` |
| `package.json` (Vite) | `npm run build` | `http://localhost:5173` |
| `package.json` (Next.js) | `npm run build` | `http://localhost:3000` |
| `yarn.lock` | `yarn build` | (framework-based) |
| `pnpm-lock.yaml` | `pnpm run build` | (framework-based) |
| `go.mod` | `go build ./...` | `http://localhost:8080` |
| `Cargo.toml` | `cargo build` | `http://localhost:8080` |
| `pyproject.toml` | `pytest` | `http://localhost:8000` |
| `requirements.txt` | `pytest` | `http://localhost:5000` |
| `pom.xml` | `mvn clean install` | `http://localhost:8080` |
| `build.gradle` | `./gradlew build` | `http://localhost:8080` |
| `*.csproj` | `dotnet build` | `http://localhost:5000` |

**It's smart. It figures it out.**

---

## Example Usage

### Example 1: React App

```bash
cd my-react-app
claude --plugin-dir C:\Users\nestor\build-test-loop-plugin
```

In Claude:
```bash
/build-test-loop "Add a user profile dropdown with logout button"
```

**What happens:**
1. Detects `npm run build` + `http://localhost:3000`
2. Plans the dropdown component
3. Codes until it builds
4. Tests in browser
5. Loops if tests fail
6. Stops when working ✅

### Example 2: Python API

```bash
cd my-flask-api
claude --plugin-dir C:\Users\nestor\build-test-loop-plugin
```

In Claude:
```bash
/build-test-loop "Create /api/users endpoint with GET, POST, DELETE"
```

**What happens:**
1. Detects `pytest` + `http://localhost:5000`
2. Plans the API routes
3. Codes until tests pass
4. Tests endpoints in browser
5. Loops if tests fail
6. Stops when working ✅

### Example 3: Go Service

```bash
cd my-go-service
claude --plugin-dir C:\Users\nestor\build-test-loop-plugin
```

In Claude:
```bash
/build-test-loop "Add health check endpoint with database status"
```

**What happens:**
1. Detects `go build ./...` + `http://localhost:8080`
2. Plans the health endpoint
3. Codes until it compiles
4. Tests endpoint in browser
5. Loops if tests fail
6. Stops when working ✅

---

## Monitoring (Optional)

Want to watch it work?

**Terminal 1:**
```bash
claude --plugin-dir C:\Users\nestor\build-test-loop-plugin
/build-test-loop "Your task"
```

**Terminal 2:**
```bash
# Windows
powershell
while ($true) { Clear-Host; Get-Content .claude\build-test-loop.local.md; Start-Sleep -Seconds 2 }
```

You'll see the phase change in real-time:
- `phase: "plan"` → Planning...
- `phase: "develop"` → Coding...
- `phase: "test"` → Testing...
- `phase: "done"` → FINISHED! ✅

---

## Canceling

Changed your mind?

```bash
/cancel-build-test-loop
```

Done. Loop stops on next iteration.

---

## Override (Rare)

Only if auto-detection doesn't work:

```bash
/build-test-loop "Your task" \
  --build-command "your custom command" \
  --test-url "http://localhost:YOUR_PORT"
```

But honestly, try without these first. Auto-detection is good.

---

## Tips for Success

### ✅ Good Tasks
- "Add pagination to user table with 10 per page"
- "Create login form with email validation"
- "Add search bar that filters as you type"
- "Implement shopping cart with quantity controls"

### ❌ Bad Tasks
- "Make it better" (too vague)
- "Fix bugs" (which bugs?)
- "Add features" (which features?)

### 💡 Pro Tip
**Be specific about what you want tested:**

```bash
/build-test-loop "Add dark mode toggle that:
- Switches between light and dark themes
- Shows sun/moon icon
- Persists in localStorage
- Applies on page load"
```

The more specific, the better the tests, the better the final code.

---

## Troubleshooting

### "It's not detecting my build command"
Check what it detected:
```bash
python C:\Users\nestor\build-test-loop-plugin\hooks\auto_detect.py
```

If wrong, override:
```bash
/build-test-loop "Your task" --build-command "your actual command"
```

### "Loop won't start"
- Is Python 3 installed? `python --version` or `python3 --version`
- Is the plugin path correct?
- Check `.claude\build-test-loop.local.md` - does it exist?

### "Stuck in develop phase"
- Check if build command actually works manually
- Look at the transcript - what errors?
- Try simpler task first to verify setup

### "Tests keep failing"
- Is the test URL correct?
- Is dev server running?
- Check task description - is it testable?

---

## That's It!

Seriously. That's the whole plugin:

1. `cd your-project`
2. `claude --plugin-dir C:\Users\nestor\build-test-loop-plugin`
3. `/build-test-loop "Your task"`
4. Walk away
5. Come back to working code

**ONE COMMAND. ZERO CONFIG. FULL AUTONOMY.**

---

## Want Permanent Install?

Instead of `--plugin-dir` every time:

```bash
# Copy to Claude plugins folder
mkdir -p ~/.claude/plugins
cp -r C:\Users\nestor\build-test-loop-plugin ~/.claude/plugins/

# Then just use:
cd any-project
claude
/build-test-loop "Your task"
```

Done! Now it's always available.

---

**Questions? Check:**
- `README.md` - Full documentation
- `ONESHOT.md` - One-shot usage examples
- `QUICKSTART.md` - Quick start guide
- `examples/example-session.md` - Complete walkthrough

**Now go build something! 🚀**
