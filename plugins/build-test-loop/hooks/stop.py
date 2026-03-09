#!/usr/bin/env python3
"""
Build-Test-Loop Stop Hook

Controls the multi-phase autonomous loop:
1. PLAN - Initial planning phase
2. DEVELOP - Build until successful compilation
3. TEST - Web testing to verify functionality
4. Loop back to DEVELOP if tests fail
5. Complete when tests pass

State is tracked in .claude/build-test-loop.local.md
"""

import sys
import json
import os
import re
from pathlib import Path


def read_state_file():
    """Read state from .claude/build-test-loop.local.md"""
    state_path = Path.cwd() / ".claude" / "build-test-loop.local.md"

    if not state_path.exists():
        return None

    content = state_path.read_text(encoding="utf-8")

    # Parse YAML frontmatter
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
    if not match:
        return None

    frontmatter = match.group(1)

    # Parse key-value pairs from YAML
    state = {
        "enabled": False,
        "phase": "plan",
        "iteration": 0,
        "max_iterations": 50,
        "build_command": "npm run build",
        "test_url": "http://localhost:3000",
        "original_prompt": "",
        "develop_failures": 0
    }

    for line in frontmatter.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()

            # Handle different types
            if key in ["enabled"]:
                state[key] = value.lower() in ['true', 'yes', '1']
            elif key in ["iteration", "max_iterations", "develop_failures"]:
                try:
                    state[key] = int(value)
                except:
                    pass
            elif key in ["phase", "build_command", "test_url", "original_prompt"]:
                # Remove quotes if present
                state[key] = value.strip('"\'')

    return state


def update_state_file(state):
    """Update state file with new values"""
    state_path = Path.cwd() / ".claude" / "build-test-loop.local.md"

    # Create .claude directory if it doesn't exist
    state_path.parent.mkdir(exist_ok=True)

    content = f"""---
enabled: {str(state['enabled']).lower()}
phase: "{state['phase']}"
iteration: {state['iteration']}
max_iterations: {state['max_iterations']}
build_command: "{state['build_command']}"
test_url: "{state['test_url']}"
original_prompt: "{state['original_prompt']}"
develop_failures: {state['develop_failures']}
---

# Build-Test-Loop State

**Current Phase:** {state['phase']}
**Iteration:** {state['iteration']} / {state['max_iterations']}
**Build Command:** `{state['build_command']}`
**Test URL:** {state['test_url']}

## Phase Progression

1. ✓ **PLAN** - Create implementation plan
2. {'✓' if state['phase'] in ['test', 'done'] else '⏳'} **DEVELOP** - Build until compilation succeeds
3. {'✓' if state['phase'] == 'done' else '⏳'} **TEST** - Verify with web testing
4. {'✓' if state['phase'] == 'done' else '⏳'} **DONE** - All tests passed!

## Completion Signals

- **PLAN_COMPLETE** - Planning finished, ready to develop
- **BUILD_SUCCESS** - Build succeeded, ready to test
- **TESTS_PASSED** - All tests passed, mission complete!
- **TESTS_FAILED** - Tests failed, back to develop mode

---
*This file is managed by build-test-loop plugin. Edit carefully.*
"""

    state_path.write_text(content, encoding="utf-8")


def check_transcript_for_signal(hook_input, signal):
    """Check if a completion signal appears in the transcript file"""
    debug_path = Path.cwd() / ".claude" / "build-test-loop-debug.log"

    def log_debug(msg):
        try:
            with open(debug_path, "a", encoding="utf-8") as f:
                f.write(f"{msg}\n")
        except:
            pass

    log_debug(f"\n=== Checking for signal: {signal} ===")
    log_debug(f"Hook input keys: {list(hook_input.keys()) if isinstance(hook_input, dict) else 'N/A'}")

    # Get the transcript path from hook input
    transcript_path = hook_input.get("transcript_path", "")

    if not transcript_path:
        log_debug("No transcript_path in hook input")
        return False

    log_debug(f"Transcript path: {transcript_path}")

    # Handle path - could be absolute or with ~ for home
    if transcript_path.startswith("~"):
        transcript_path = os.path.expanduser(transcript_path)

    transcript_file = Path(transcript_path)

    if not transcript_file.exists():
        log_debug(f"Transcript file not found: {transcript_file}")
        return False

    # Read the transcript file (JSONL format - one JSON object per line)
    try:
        last_assistant_content = ""
        with open(transcript_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    # Check if this is an assistant message
                    msg_type = entry.get("type", "")
                    if msg_type == "assistant":
                        # Get content - could be string or list of content blocks
                        content = entry.get("message", {}).get("content", [])
                        if isinstance(content, list):
                            # Extract text from content blocks
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    last_assistant_content = block.get("text", "")
                                elif isinstance(block, str):
                                    last_assistant_content = block
                        elif isinstance(content, str):
                            last_assistant_content = content
                except json.JSONDecodeError:
                    continue

        log_debug(f"Last assistant content (last 500 chars): ...{last_assistant_content[-500:] if last_assistant_content else 'EMPTY'}")

        # Check for signal in the last assistant message
        found = signal in last_assistant_content
        log_debug(f"Signal '{signal}' found: {found}")

        return found

    except Exception as e:
        log_debug(f"Error reading transcript: {e}")
        return False


def get_phase_prompt(phase, state):
    """Get the prompt for a given phase"""

    if phase == "plan":
        return f"""**PLANNING PHASE**

Create a detailed implementation plan for this task:

{state['original_prompt']}

**IMPORTANT: Check for project-specific instructions!**
Look for and READ these files if they exist:
- `CLAUDE.md` or `.claude.md` - Project-specific instructions for Claude
- `README.md` - Project documentation
- `.github/workflows/` - CI/CD pipeline configuration

These files may contain CRITICAL information about:
- Deployment pipelines (GitHub Actions → Azure, Vercel, etc.)
- Wait times needed between push and testing
- Specific test URLs or environments
- Custom build/deploy workflows
- Any project-specific requirements

Your plan should include:
1. Required files and their purposes
2. Key functions/components to implement
3. Dependencies needed
4. Build process verification steps
5. What needs to be tested in the browser
6. **Deployment workflow** - Does this project deploy via CI/CD? How long to wait?

When your plan is complete and documented, output: <promise>PLAN_COMPLETE</promise>

Build command that will be used: `{state['build_command']}`
Test URL: {state['test_url']}
"""

    elif phase == "develop":
        return f"""**DEVELOPMENT PHASE** (Attempt #{state['develop_failures'] + 1})

Implement the planned solution and get it to build successfully.

Build command: `{state['build_command']}`

Work iteratively:
1. Implement/fix code
2. Run the build command
3. If build fails, analyze errors and fix
4. Repeat until build succeeds

**Project-Specific Workflow:**
Check your plan and `CLAUDE.md`/`.claude.md` for any special requirements:
- Does this project use CI/CD (GitHub Actions, Azure Pipelines, etc.)?
- Do you need to commit and push for deployment?
- Are there any pre-deployment steps?

If this project deploys via CI/CD:
1. Commit your changes
2. Push to the appropriate branch
3. Note that you'll need to WAIT for deployment in the TEST phase

When the build succeeds (locally), output: <promise>BUILD_SUCCESS</promise>

Original task: {state['original_prompt']}
"""

    elif phase == "test":
        return f"""**WEB TESTING PHASE**

Test the implementation in the browser.

Test URL: {state['test_url']}

**STEP 1: VERIFY DEPLOYMENT (if using CI/CD)**

If this project deploys via GitHub Actions → Azure/Vercel/etc.:

1. **Check CI/CD status FIRST:**
   ```bash
   gh run list --limit 3
   ```

2. **If the run FAILED:**
   - Output: TESTS_FAILED
   - Describe: "CI/CD deployment failed - need to fix and redeploy"
   - DO NOT proceed to browser testing!

3. **If the run is IN PROGRESS:**
   - Wait for it to complete
   - Check status every 30 seconds: `gh run view <run-id>`

4. **If the run SUCCEEDED:**
   - Wait 1-2 minutes for server to update
   - Then proceed to browser testing

**STEP 2: BROWSER TESTING**

Use browser automation tools (mcp__claude-in-chrome__*) to:

1. **Navigate** to: {state['test_url']}
2. **Take screenshot** to verify page loaded
3. **Test functionality** from your plan
4. **Document results**

**STEP 3: REPORT RESULTS**

If ALL tests pass: TESTS_PASSED
If ANY test fails: TESTS_FAILED (describe what failed)

**DO NOT output TESTS_PASSED if:**
- CI/CD deployment failed
- You couldn't reach the test URL
- Any planned feature doesn't work

Original task: {state['original_prompt']}
"""

    return None


def main():
    # Read hook input from stdin
    hook_input = json.load(sys.stdin)

    # Read current state
    state = read_state_file()

    # If not enabled or no state file, allow stop
    if not state or not state.get("enabled"):
        sys.exit(0)

    # Increment iteration
    state["iteration"] += 1

    # Check for max iterations safety
    if state["iteration"] >= state["max_iterations"]:
        print(json.dumps({
            "decision": "allow"
        }))
        state["enabled"] = False
        update_state_file(state)
        sys.exit(0)

    # Phase-specific logic
    current_phase = state["phase"]

    if current_phase == "plan":
        # Check if planning is complete
        if check_transcript_for_signal(hook_input, "PLAN_COMPLETE"):
            # Move to develop phase
            state["phase"] = "develop"
            state["develop_failures"] = 0
            update_state_file(state)

            prompt = get_phase_prompt("develop", state)
            print(json.dumps({
                "decision": "block",
                "reason": prompt,
                "systemMessage": f"🔄 Build-Test-Loop iteration {state['iteration']} | ✅ Planning complete! Moving to DEVELOP phase..."
            }))
            sys.exit(0)
        else:
            # Continue planning
            update_state_file(state)
            prompt = get_phase_prompt("plan", state)
            print(json.dumps({
                "decision": "block",
                "reason": prompt,
                "systemMessage": f"🔄 Build-Test-Loop iteration {state['iteration']} | 📋 Continue planning..."
            }))
            sys.exit(0)

    elif current_phase == "develop":
        # Check if build succeeded
        if check_transcript_for_signal(hook_input, "BUILD_SUCCESS"):
            # Move to test phase
            state["phase"] = "test"
            update_state_file(state)

            prompt = get_phase_prompt("test", state)
            print(json.dumps({
                "decision": "block",
                "reason": prompt,
                "systemMessage": f"🔄 Build-Test-Loop iteration {state['iteration']} | ✅ Build succeeded! Moving to WEB TESTING phase..."
            }))
            sys.exit(0)
        else:
            # Continue developing
            update_state_file(state)
            prompt = get_phase_prompt("develop", state)
            print(json.dumps({
                "decision": "block",
                "reason": prompt,
                "systemMessage": f"🔄 Build-Test-Loop iteration {state['iteration']} | 🔨 Continue developing..."
            }))
            sys.exit(0)

    elif current_phase == "test":
        # Check if tests passed
        if check_transcript_for_signal(hook_input, "TESTS_PASSED"):
            # Success! Complete the loop
            state["phase"] = "done"
            state["enabled"] = False
            update_state_file(state)

            print(json.dumps({
                "decision": "allow"
            }))
            sys.exit(0)

        # Check if tests failed
        elif check_transcript_for_signal(hook_input, "TESTS_FAILED"):
            # Loop back to develop phase
            state["phase"] = "develop"
            state["develop_failures"] += 1
            update_state_file(state)

            prompt = get_phase_prompt("develop", state)
            print(json.dumps({
                "decision": "block",
                "reason": prompt,
                "systemMessage": f"🔄 Build-Test-Loop iteration {state['iteration']} | ❌ Tests failed! Looping back to DEVELOP phase (failure #{state['develop_failures']})..."
            }))
            sys.exit(0)
        else:
            # Continue testing
            update_state_file(state)
            prompt = get_phase_prompt("test", state)
            print(json.dumps({
                "decision": "block",
                "reason": prompt,
                "systemMessage": f"🔄 Build-Test-Loop iteration {state['iteration']} | 🧪 Continue testing..."
            }))
            sys.exit(0)

    # If phase is "done" or unknown, allow stop
    print(json.dumps({
        "decision": "allow"
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
