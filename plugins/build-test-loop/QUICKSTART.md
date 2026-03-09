# Quick Start Guide

## 30-Second Setup

```bash
# 1. Go to your project
cd my-react-app

# 2. Start Claude with the plugin
claude --plugin-dir C:/Users/nestor/build-test-loop-plugin

# 3. Give it ONE command
/build-test-loop "Add a click counter button that shows number of clicks"

# 4. Done! Walk away and come back to working code.
```

That's it. Seriously.

---

## What Just Happened?

When you ran that one command, the plugin:

✅ **Auto-detected** `npm run build` (saw your package.json)
✅ **Auto-detected** `http://localhost:3000` (saw React)
✅ **Planned** the counter implementation
✅ **Coded** until it compiled
✅ **Tested** in actual browser
✅ **Fixed** any issues
✅ **Verified** tests pass
✅ **Stopped** when done

**Zero configuration. Zero supervision needed.**

---

## Installation (One Time)

### Fastest Way (Use Directly)
```bash
cd your-project
claude --plugin-dir /path/to/build-test-loop-plugin
```

### Permanent Install
```bash
# Copy to plugins directory
cp -r build-test-loop-plugin ~/.claude/plugins/

# Then just use normally
cd any-project
claude
/build-test-loop "your task"
```

---

## Your First Real Task

Pick a feature you need:

```bash
/build-test-loop "Add dark mode toggle to settings that persists in localStorage"
```

Now walk away. Seriously. Go get coffee. ☕

Come back in 5-10 minutes and check:

```bash
cat .claude/build-test-loop.local.md
```

If you see `phase: "done"` → It worked! ✅

---

## What Happens?

```
User: /build-test-loop "Add counter button"
  ↓
Stop Hook creates: .claude/build-test-loop.local.md
  ↓
PLAN Phase → Claude plans implementation
  ↓
Outputs: <promise>PLAN_COMPLETE</promise>
  ↓
DEVELOP Phase → Claude codes + builds iteratively
  ↓
Outputs: <promise>BUILD_SUCCESS</promise>
  ↓
TEST Phase → Claude tests in browser
  ↓
Either:
  <promise>TESTS_PASSED</promise> → DONE! ✅
  <promise>TESTS_FAILED</promise> → Back to DEVELOP 🔄
```

## Real-World Examples

### React Component
```bash
/build-test-loop "Add a search bar to the navbar with live filtering"
```
Auto-detects: npm/yarn/pnpm + http://localhost:3000

### Python API
```bash
/build-test-loop "Create /api/products endpoint with CRUD and validation"
```
Auto-detects: pytest + http://localhost:5000

### Go Service
```bash
/build-test-loop "Add health check endpoint with database status"
```
Auto-detects: go build + http://localhost:8080

### Rust Web App
```bash
/build-test-loop "Implement rate limiting middleware"
```
Auto-detects: cargo build + http://localhost:8080

### Complex Feature (More Time)
```bash
/build-test-loop "Implement real-time chat with WebSocket" \
  --max-iterations 100
```

### Custom Build (Only If Needed)
```bash
/build-test-loop "Add login form" \
  --build-command "make build && make test" \
  --test-url "http://localhost:9000"
```

## Monitoring

Check progress anytime:

```bash
cat .claude/build-test-loop.local.md
```

You'll see:
- Current phase (plan/develop/test/done)
- Iteration count
- Build command
- Test URL
- Number of failures

## Canceling

If you need to stop:

```bash
/cancel-build-test-loop
```

Or manually edit `.claude/build-test-loop.local.md`:
```yaml
enabled: false
```

## Tips for Success

### ✅ DO
- Be specific about what to build
- Include testable criteria
- Point to the right URL with `--test-url`
- Use build commands that verify correctness
- Set realistic `--max-iterations`

### ❌ DON'T
- Use vague descriptions
- Ask for "fixes" without specifics
- Forget to specify test URL for features
- Set max-iterations too low (< 20)

## Common Issues

### "Loop not starting"
- Check Python 3 is installed: `python3 --version`
- Verify plugin loaded: `claude --debug`

### "Stuck in DEVELOP phase"
- Check build command actually works
- Look at build errors in transcript
- Try simpler task first

### "Tests keep failing"
- Verify test URL is correct
- Check dev server is running
- Review what's being tested
- Simplify test criteria

## Next Steps

1. Try the examples in `examples/example-session.md`
2. Read the full README for advanced usage
3. Experiment with different build commands
4. Try complex multi-phase features!

## Getting Help

- Read full docs: `README.md`
- Check examples: `examples/`
- Debug mode: `claude --debug`

---

**Ready? Start your first loop!** 🚀

```bash
/build-test-loop "Your task here"
```
