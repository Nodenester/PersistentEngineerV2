#!/usr/bin/env python3
"""
Project-Loop Stop Hook v1.6.0

A sophisticated autonomous development loop with:
- Configurable stage types (investigate, build, fix, verify, document)
- Per-stage behavior (skip plan, skip develop, skip test, loop on failure)
- Unlimited stages
- Smart workflow detection
- Separate file responsibilities

Stage Types:
- investigate: Test first to find issues (plan → test, no develop, no loop)
- build: Full development cycle (plan → develop → test, loops on failure)
- fix: Quick fixes (develop → test, loops on failure)
- verify: Just test existing work (test only, no loop)
- document: Documentation only (plan only, no test)

After all stages complete, enters REVIEW phase:
- Reviews all bugs/notes from all stages
- Decides if critical fixes are needed
- Can loop back with new fix stages (preserves context from previous pass)
- Only completes when truly done

State tracked in .claude/project-loop.local.md
Stage plans stored in .claude/stages/stage-N-plan.md
Overview in .claude/walkthrough.md (created once during ANALYZE)
"""

import sys
import json
import os
import re
from pathlib import Path


# =============================================================================
# STAGE TYPE PRESETS
# =============================================================================

STAGE_TYPES = {
    "investigate": {
        "has_plan": True,
        "has_develop": False,
        "has_test": True,
        "loop_on_failure": False,
        "description": "Browser testing to investigate and document issues"
    },
    "build": {
        "has_plan": True,
        "has_develop": True,
        "has_test": True,
        "loop_on_failure": True,
        "description": "Full development cycle with planning, coding, and testing"
    },
    "fix": {
        "has_plan": False,
        "has_develop": True,
        "has_test": True,
        "loop_on_failure": True,
        "description": "Quick fixes without detailed planning"
    },
    "verify": {
        "has_plan": False,
        "has_develop": False,
        "has_test": True,
        "loop_on_failure": False,
        "description": "Verification testing only, no development"
    },
    "document": {
        "has_plan": True,
        "has_develop": False,
        "has_test": False,
        "loop_on_failure": False,
        "description": "Documentation and planning only, no testing"
    }
}


def get_stage_config(stage):
    """Get the full configuration for a stage, applying type presets and overrides"""
    # Handle string stages (simple format) - default to "build" type
    if isinstance(stage, str):
        # Auto-detect type from name keywords
        name_lower = stage.lower()
        if any(kw in name_lower for kw in ["investigate", "debug", "find", "discover", "explore"]):
            stage_type = "investigate"
        elif any(kw in name_lower for kw in ["verify", "confirm", "check", "validate", "final"]):
            stage_type = "verify"
        elif any(kw in name_lower for kw in ["fix", "repair", "patch", "hotfix"]):
            stage_type = "fix"
        elif any(kw in name_lower for kw in ["document", "docs", "readme", "write-up"]):
            stage_type = "document"
        else:
            stage_type = "build"

        return {
            "name": stage,
            "type": stage_type,
            "description": "",
            **STAGE_TYPES[stage_type]
        }

    # Handle object stages (advanced format)
    stage_type = stage.get("type", "build")
    if stage_type not in STAGE_TYPES:
        stage_type = "build"

    # Start with type presets
    config = {
        "name": stage.get("name", "Unnamed Stage"),
        "type": stage_type,
        "description": stage.get("description", ""),
        **STAGE_TYPES[stage_type]
    }

    # Apply explicit overrides if provided
    for key in ["has_plan", "has_develop", "has_test", "loop_on_failure"]:
        if key in stage:
            config[key] = stage[key]

    return config


def read_state_file():
    """Read state from .claude/project-loop.local.md"""
    state_path = Path.cwd() / ".claude" / "project-loop.local.md"

    if not state_path.exists():
        return None

    content = state_path.read_text(encoding="utf-8")

    # Parse YAML frontmatter
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
    if not match:
        return None

    frontmatter = match.group(1)

    # Default state
    state = {
        "enabled": False,
        "phase": "analyze",
        "iteration": 0,
        "max_iterations": 500,  # Increased for complex projects
        "build_command": "npm run build",
        "test_url": "http://localhost:3000",
        "original_prompt": "",
        "stages": [],
        "current_stage": 0,
        "stage_phase": "none",
        "develop_failures": 0,
        "total_develop_failures": 0,
        "workflow_mode": "build",  # build, debug, hybrid
        "deployment_type": "local",  # local, cicd, manual
        "review_pass": 1,  # Track which review pass we're on
        "original_stage_count": 0  # Track stages before any review additions
    }

    for line in frontmatter.split('\n'):
        if ':' in line:
            idx = line.index(':')
            key = line[:idx].strip()
            value = line[idx+1:].strip()

            if key == "enabled":
                state[key] = value.lower() in ['true', 'yes', '1']
            elif key in ["iteration", "max_iterations", "current_stage", "develop_failures", "total_develop_failures", "review_pass", "original_stage_count"]:
                try:
                    state[key] = int(value)
                except:
                    pass
            elif key == "stages":
                try:
                    state[key] = json.loads(value)
                except:
                    state[key] = []
            elif key in ["phase", "stage_phase", "build_command", "test_url", "original_prompt", "workflow_mode", "deployment_type"]:
                state[key] = value.strip('"\'')

    return state


def update_state_file(state):
    """Update state file with new values - ONLY state, no documentation"""
    state_path = Path.cwd() / ".claude" / "project-loop.local.md"
    state_path.parent.mkdir(exist_ok=True)

    # Ensure stages directory exists
    stages_dir = Path.cwd() / ".claude" / "stages"
    stages_dir.mkdir(exist_ok=True)

    # Build stages display
    stages_display = ""
    stages_list = state.get("stages", [])
    for i, stage in enumerate(stages_list):
        stage_config = get_stage_config(stage)
        if i < state["current_stage"]:
            status = "[x]"
        elif i == state["current_stage"]:
            status = "[>]"
        else:
            status = "[ ]"
        stage_type = stage_config["type"]
        stages_display += f"{status} Stage {i+1}: {stage_config['name']} ({stage_type})\n"

    if not stages_display:
        stages_display = "(Stages will be defined during ANALYZE phase)\n"

    # Current stage info
    current_stage_name = ""
    current_stage_type = ""
    if stages_list and state["current_stage"] < len(stages_list):
        current_config = get_stage_config(stages_list[state["current_stage"]])
        current_stage_name = current_config["name"]
        current_stage_type = current_config["type"]

    content = f"""---
enabled: {str(state['enabled']).lower()}
phase: "{state['phase']}"
iteration: {state['iteration']}
max_iterations: {state['max_iterations']}
build_command: "{state['build_command']}"
test_url: "{state['test_url']}"
original_prompt: "{state['original_prompt']}"
stages: {json.dumps(state.get('stages', []))}
current_stage: {state['current_stage']}
stage_phase: "{state.get('stage_phase', 'none')}"
develop_failures: {state['develop_failures']}
total_develop_failures: {state.get('total_develop_failures', 0)}
workflow_mode: "{state.get('workflow_mode', 'build')}"
deployment_type: "{state.get('deployment_type', 'local')}"
review_pass: {state.get('review_pass', 1)}
original_stage_count: {state.get('original_stage_count', 0)}
---

# Project-Loop State

**Status:** {state['phase'].upper().replace('_', ' ')}
**Iteration:** {state['iteration']} / {state['max_iterations']}
**Workflow:** {state.get('workflow_mode', 'build').upper()} | **Deploy:** {state.get('deployment_type', 'local').upper()}

## Project

{state['original_prompt']}

## Stages

{stages_display}
**Current:** Stage {state['current_stage'] + 1 if stages_list else 0} / {len(stages_list)} {f'- {current_stage_name}' if current_stage_name else ''}
**Phase:** {state.get('stage_phase', 'none')} {f'({current_stage_type} type)' if current_stage_type else ''}

## Stats

- Iterations: {state['iteration']}
- Stage failures: {state['develop_failures']}
- Total failures: {state.get('total_develop_failures', 0)}
- Review pass: {state.get('review_pass', 1)}
- Original stages: {state.get('original_stage_count', len(stages_list))}

---
*State file - Do not edit manually during active loop*
"""

    state_path.write_text(content, encoding="utf-8")


def check_transcript_for_signal(hook_input, signal):
    """Check if a completion signal appears in the transcript file"""
    debug_path = Path.cwd() / ".claude" / "project-loop-debug.log"

    def log_debug(msg):
        try:
            with open(debug_path, "a", encoding="utf-8") as f:
                f.write(f"{msg}\n")
        except:
            pass

    log_debug(f"\n=== Checking for signal: {signal} ===")
    log_debug(f"Hook input keys: {list(hook_input.keys()) if isinstance(hook_input, dict) else 'N/A'}")

    transcript_path = hook_input.get("transcript_path", "")

    if not transcript_path:
        log_debug("No transcript_path in hook input")
        return False

    log_debug(f"Transcript path: {transcript_path}")

    if transcript_path.startswith("~"):
        transcript_path = os.path.expanduser(transcript_path)

    transcript_file = Path(transcript_path)

    if not transcript_file.exists():
        log_debug(f"Transcript file not found: {transcript_file}")
        return False

    try:
        last_assistant_content = ""
        with open(transcript_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    msg_type = entry.get("type", "")
                    if msg_type == "assistant":
                        content = entry.get("message", {}).get("content", [])
                        if isinstance(content, list):
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

        found = signal in last_assistant_content
        log_debug(f"Signal '{signal}' found: {found}")

        return found

    except Exception as e:
        log_debug(f"Error reading transcript: {e}")
        return False


# =============================================================================
# PHASE PROMPTS - Give Claude freedom while providing structure
# =============================================================================

def get_analyze_prompt(state):
    """Prompt for the ANALYZE phase - break project into stages"""
    return f"""## ANALYZE PHASE - Understand & Structure the Project

You have complete freedom to analyze this project and break it into logical stages. Work like a senior developer planning a project.

### Your Task

**Project Request:**
{state['original_prompt']}

### Step 1: Understand the Project

Read these files if they exist (don't worry if they don't):
- `CLAUDE.md` or `.claude.md` - Project-specific instructions
- `README.md` - Project documentation
- `.github/workflows/` - CI/CD configuration
- `package.json`, `Cargo.toml`, `go.mod`, etc. - Project type

### Step 2: Determine Workflow & Deployment

**Workflow Mode** (based on the request):
- **DEBUG** - Request mentions testing, finding bugs, debugging, "why isn't X working"
- **BUILD** - Request mentions adding, creating, implementing new features
- **HYBRID** - Complex requests needing both investigation and building

**Deployment Type** (from project files):
- **LOCAL** - No CI/CD, test on localhost immediately
- **CICD** - GitHub Actions, Azure Pipelines, etc. - must push and wait
- **MANUAL** - Build locally, deploy manually

### Step 3: Create Stages

Break the work into logical stages. Use as many or as few as needed:
- Simple bug fix → 1-2 stages
- Medium feature → 3-5 stages
- Large project → 10+ stages (no limit!)

**Stage Types Available:**
- `investigate` - Browser test first to find/document issues (no coding)
- `build` - Full cycle: plan → code → test (loops until tests pass)
- `fix` - Quick fixes: code → test (loops until tests pass)
- `verify` - Just test existing work (no coding, no looping)
- `document` - Documentation only (no testing)

### Step 4: Create Files

1. **Create `.claude/walkthrough.md`** with:
   - Project overview
   - Workflow mode & deployment type
   - Test URL (from CLAUDE.md or detected)
   - All stages with descriptions
   - Progress checklist

2. **Update the state file** `.claude/project-loop.local.md`
   Edit the `stages:` line with your stages as JSON array.

   Simple format (type auto-detected from name):
   ```
   stages: ["Investigate Issues", "Fix Authentication", "Verify All Working"]
   ```

   Or advanced format with explicit types:
   ```
   stages: [{{"name": "Find Bugs", "type": "investigate"}}, {{"name": "Fix Them", "type": "fix"}}, {{"name": "Final Check", "type": "verify"}}]
   ```

### Step 5: Signal Completion

When you've created walkthrough.md and updated the stages, output:

<promise>ANALYZE_COMPLETE</promise>

---

**Build command:** `{state['build_command']}`
**Test URL:** {state['test_url']}

You have full autonomy. Structure this however makes sense for the project!
"""


def get_stage_plan_prompt(state, stage_config):
    """Prompt for STAGE_PLAN phase"""
    stage_num = state["current_stage"] + 1
    stage_name = stage_config["name"]
    stage_type = stage_config["type"]

    return f"""## STAGE {stage_num} PLANNING: {stage_name}

**Stage Type:** {stage_type}
**Behavior:** {'Will loop on test failure' if stage_config['loop_on_failure'] else 'No looping - document results and move on'}

### Your Task

Create a plan for this stage. You have full freedom in how you approach it.

### What This Stage Should Accomplish

Based on the walkthrough.md and project goals, determine:
1. What specific tasks need to be done
2. What files will be modified/created
3. How you'll know it's complete
4. What to test (if this stage has testing)

### Create Stage Plan

Save your plan to: `.claude/stages/stage-{stage_num}-plan.md`

Include whatever structure makes sense:
- Task list
- Technical approach
- Files to modify
- Testing criteria
- Any dependencies or prerequisites

### Signal Completion

When your plan is ready, output:

<promise>STAGE_PLAN_COMPLETE</promise>

---

**Build command:** `{state['build_command']}`
**Test URL:** {state['test_url']}
**Workflow:** {state.get('workflow_mode', 'build')} | **Deploy:** {state.get('deployment_type', 'local')}
"""


def get_stage_develop_prompt(state, stage_config):
    """Prompt for STAGE_DEVELOP phase"""
    stage_num = state["current_stage"] + 1
    stage_name = stage_config["name"]
    stage_type = stage_config["type"]
    attempt = state["develop_failures"] + 1

    # Check if this is a re-attempt after test failure
    retry_note = ""
    if state["develop_failures"] > 0:
        retry_note = f"""
### Previous Attempt Failed

This is attempt #{attempt}. The previous test phase found issues.
Review what went wrong and fix it. Check `.claude/stages/stage-{stage_num}-notes.md` for test results.
"""

    return f"""## STAGE {stage_num} DEVELOPMENT: {stage_name}

**Stage Type:** {stage_type} | **Attempt:** #{attempt}
{retry_note}

### Your Task

Execute the work planned for this stage. You have full autonomy.

### Guidelines

1. **Reference your plan:** `.claude/stages/stage-{stage_num}-plan.md`

2. **Work iteratively:**
   - Make changes
   - Build frequently: `{state['build_command']}`
   - Fix any build errors before continuing

3. **Deployment ({state.get('deployment_type', 'local')}):**
   {"- Just build locally, no push needed" if state.get('deployment_type') == 'local' else "- Commit and push when ready" if state.get('deployment_type') == 'cicd' else "- Build locally, deploy as needed"}

4. **Document as you go:**
   - Note any issues or decisions in `.claude/stages/stage-{stage_num}-notes.md`

### Signal Completion

When your development work is complete and building successfully, output:

<promise>STAGE_BUILD_SUCCESS</promise>

---

**Build command:** `{state['build_command']}`
**Original task:** {state['original_prompt']}
"""


def get_stage_test_prompt(state, stage_config):
    """Prompt for STAGE_TEST phase"""
    stage_num = state["current_stage"] + 1
    stage_name = stage_config["name"]
    stage_type = stage_config["type"]
    loops = stage_config["loop_on_failure"]

    return f"""## STAGE {stage_num} TESTING: {stage_name}

**Stage Type:** {stage_type}
**On Failure:** {'Will return to development for fixes' if loops else 'Document issues and continue to next stage'}

### Your Task

Test the work for this stage. You have full freedom in how you test.

### Testing Approach

1. **Check deployment status** (if using CI/CD):
   ```bash
   gh run list --limit 3
   ```
   - If failed: {'Signal STAGE_TESTS_FAILED to fix and retry' if loops else 'Document the failure and signal STAGE_TESTS_FAILED'}
   - If in progress: Wait and check again
   - If succeeded: Continue to browser testing

2. **Browser Testing:**
   - Navigate to: {state['test_url']}
   - Test the functionality from your stage plan
   - Check console for errors
   - Verify everything works as expected

3. **Document Results:**
   - Save findings to `.claude/stages/stage-{stage_num}-notes.md`
   - Be specific about what passed and what failed

### Signal Results

**If ALL tests pass:**
<promise>STAGE_TESTS_PASSED</promise>

**If ANY test fails:**
<promise>STAGE_TESTS_FAILED</promise>
{"(This will return you to development to fix the issues)" if loops else "(This will document the failure and move to the next stage)"}

---

**Test URL:** {state['test_url']}
**Stage plan:** `.claude/stages/stage-{stage_num}-plan.md`
"""


def get_review_prompt(state):
    """Prompt for REVIEW phase - final assessment before completion"""
    num_stages = len(state.get("stages", []))
    review_pass = state.get("review_pass", 1)

    previous_pass_note = ""
    if review_pass > 1:
        previous_pass_note = f"""
### Previous Review Passes

This is review pass #{review_pass}. You've already done {review_pass - 1} previous fix cycle(s).
The fix stages from previous passes are already included in your stage history.
Consider if the remaining issues are truly critical or can be documented as known issues.
"""

    return f"""## REVIEW PHASE - Final Assessment Before Completion

All {num_stages} planned stages have been executed. Now it's time for a final review.
{previous_pass_note}
### Your Task

Review ALL findings from this project and decide: **Are we truly done?**

### Step 1: Gather All Findings

Read through all stage documentation:
```
.claude/stages/stage-*-notes.md   (test results and observations)
.claude/stages/stage-*-bugs.md    (bugs found during testing)
.claude/stages/stage-*-plan.md    (what was planned)
.claude/walkthrough.md            (project overview)
```

### Step 2: Create Review Summary

Create a review document at `.claude/stages/review-{review_pass}.md` with:

1. **Bugs Found** - List ALL bugs discovered across all stages
   - Severity (CRITICAL, HIGH, MEDIUM, LOW)
   - Current status (fixed, unfixed, documented)

2. **Tests Passed** - What's working correctly

3. **Outstanding Issues** - What still needs attention
   - Can it wait for a future release?
   - Is it blocking core functionality?

### Step 3: Make Your Decision

**Option A: We're Done!**
- All critical/high bugs are fixed
- Core functionality works as expected
- Remaining issues are LOW severity or documented edge cases

Signal: <promise>REVIEW_COMPLETE</promise>

**Option B: Need More Fixes!**
- There are CRITICAL or HIGH severity bugs still unfixed
- Core functionality is broken
- The original task is not actually complete

If you need more fixes, create a JSON array of new fix stages in your review document:
```
## Required Fix Stages
```json
["Fix critical auth bug", "Fix data loss issue", "Verify all fixes working"]
```
```

Then signal: <promise>REVIEW_NEEDS_FIXES</promise>

### Guidelines

- **Be honest** - Don't mark as complete if there are real problems
- **Be practical** - Not every minor issue needs fixing now
- **Document** - Even if done, make sure all findings are recorded
- **Consider scope** - Focus on the original task requirements

### Original Task

{state['original_prompt']}

---

**Iterations so far:** {state['iteration']}
**Stages completed:** {num_stages}
**Review pass:** {review_pass}
"""


def get_complete_prompt(state):
    """Prompt for project completion"""
    num_stages = len(state.get("stages", []))
    review_pass = state.get("review_pass", 1)

    return f"""## PROJECT COMPLETE!

All {num_stages} stages have been completed and review passed!

### Summary

- **Total iterations:** {state['iteration']}
- **Stages completed:** {num_stages}
- **Development retries:** {state.get('total_develop_failures', 0)}
- **Review passes:** {review_pass}

### Documentation

- **Walkthrough:** `.claude/walkthrough.md`
- **Stage plans & results:** `.claude/stages/`
- **Review summary:** `.claude/stages/review-{review_pass}.md`
- **State:** `.claude/project-loop.local.md`

The project loop is now finished. Review the walkthrough and review summary for a complete record of all work.

Great job! The autonomous development loop has successfully completed the project.
"""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def parse_fix_stages_from_review(review_pass):
    """Parse fix stages from review document if agent wants to loop back"""
    review_path = Path.cwd() / ".claude" / "stages" / f"review-{review_pass}.md"

    if not review_path.exists():
        return []

    content = review_path.read_text(encoding="utf-8")

    # Look for JSON array of fix stages in the review document
    # Format: ```json\n["Fix X", "Fix Y"]\n```
    # Or just look for a JSON array after "Required Fix Stages"
    import re

    # Try to find JSON array
    json_match = re.search(r'```json\s*\n(\[.*?\])\s*\n```', content, re.DOTALL)
    if json_match:
        try:
            stages = json.loads(json_match.group(1))
            if isinstance(stages, list) and len(stages) > 0:
                return stages
        except json.JSONDecodeError:
            pass

    # Also try inline JSON array
    inline_match = re.search(r'Required Fix Stages.*?(\[.*?\])', content, re.DOTALL | re.IGNORECASE)
    if inline_match:
        try:
            stages = json.loads(inline_match.group(1))
            if isinstance(stages, list) and len(stages) > 0:
                return stages
        except json.JSONDecodeError:
            pass

    return []


# =============================================================================
# MAIN STATE MACHINE
# =============================================================================

def main():
    hook_input = json.load(sys.stdin)
    state = read_state_file()

    # If not enabled or no state file, allow stop
    if not state or not state.get("enabled"):
        sys.exit(0)

    # Increment iteration
    state["iteration"] += 1

    # Check for max iterations safety
    if state["iteration"] >= state["max_iterations"]:
        print(json.dumps({"decision": "allow"}))
        state["enabled"] = False
        state["phase"] = "max_iterations_reached"
        update_state_file(state)
        sys.exit(0)

    current_phase = state["phase"]
    stages = state.get("stages", [])

    # =========================================================================
    # ANALYZE PHASE
    # =========================================================================
    if current_phase == "analyze":
        if check_transcript_for_signal(hook_input, "ANALYZE_COMPLETE"):
            # Re-read state to get updated stages
            state = read_state_file()
            stages = state.get("stages", [])

            if not stages or len(stages) == 0:
                prompt = get_analyze_prompt(state)
                prompt += "\n\n**NOTE:** Stages array is empty! Make sure to update `.claude/project-loop.local.md` with your stages."
                print(json.dumps({
                    "decision": "block",
                    "reason": prompt,
                    "systemMessage": f"Project-Loop #{state['iteration']} | Stages not found - please update state file"
                }))
                update_state_file(state)
                sys.exit(0)

            # Move to first stage
            state["current_stage"] = 0
            stage_config = get_stage_config(stages[0])

            # Determine first phase based on stage type
            if stage_config["has_plan"]:
                state["phase"] = "stage_plan"
                state["stage_phase"] = "plan"
            elif stage_config["has_develop"]:
                state["phase"] = "stage_develop"
                state["stage_phase"] = "develop"
            elif stage_config["has_test"]:
                state["phase"] = "stage_test"
                state["stage_phase"] = "test"
            else:
                # Stage has nothing to do, skip to next
                state["current_stage"] = 1
                if state["current_stage"] >= len(stages):
                    state["phase"] = "complete"
                    state["enabled"] = False

            state["develop_failures"] = 0
            update_state_file(state)

            if state["phase"] == "complete":
                print(json.dumps({"decision": "allow"}))
            else:
                next_config = get_stage_config(stages[state["current_stage"]])
                if state["phase"] == "stage_plan":
                    prompt = get_stage_plan_prompt(state, next_config)
                elif state["phase"] == "stage_develop":
                    prompt = get_stage_develop_prompt(state, next_config)
                else:
                    prompt = get_stage_test_prompt(state, next_config)

                print(json.dumps({
                    "decision": "block",
                    "reason": prompt,
                    "systemMessage": f"Project-Loop #{state['iteration']} | Analysis complete! {len(stages)} stages. Starting Stage 1..."
                }))
            sys.exit(0)
        else:
            update_state_file(state)
            prompt = get_analyze_prompt(state)
            print(json.dumps({
                "decision": "block",
                "reason": prompt,
                "systemMessage": f"Project-Loop #{state['iteration']} | Analyzing project..."
            }))
            sys.exit(0)

    # =========================================================================
    # STAGE_PLAN PHASE
    # =========================================================================
    elif current_phase == "stage_plan":
        stage_config = get_stage_config(stages[state["current_stage"]])

        if check_transcript_for_signal(hook_input, "STAGE_PLAN_COMPLETE"):
            # Determine next phase based on stage type
            if stage_config["has_develop"]:
                state["phase"] = "stage_develop"
                state["stage_phase"] = "develop"
                prompt = get_stage_develop_prompt(state, stage_config)
                msg = f"Stage {state['current_stage']+1} planned! Moving to DEVELOP..."
            elif stage_config["has_test"]:
                state["phase"] = "stage_test"
                state["stage_phase"] = "test"
                prompt = get_stage_test_prompt(state, stage_config)
                msg = f"Stage {state['current_stage']+1} planned! Moving to TEST..."
            else:
                # Document-only stage, move to next stage
                return advance_to_next_stage(state, stages, hook_input)

            update_state_file(state)
            print(json.dumps({
                "decision": "block",
                "reason": prompt,
                "systemMessage": f"Project-Loop #{state['iteration']} | {msg}"
            }))
            sys.exit(0)
        else:
            update_state_file(state)
            prompt = get_stage_plan_prompt(state, stage_config)
            print(json.dumps({
                "decision": "block",
                "reason": prompt,
                "systemMessage": f"Project-Loop #{state['iteration']} | Planning Stage {state['current_stage']+1}..."
            }))
            sys.exit(0)

    # =========================================================================
    # STAGE_DEVELOP PHASE
    # =========================================================================
    elif current_phase == "stage_develop":
        stage_config = get_stage_config(stages[state["current_stage"]])

        if check_transcript_for_signal(hook_input, "STAGE_BUILD_SUCCESS"):
            # Determine next phase
            if stage_config["has_test"]:
                state["phase"] = "stage_test"
                state["stage_phase"] = "test"
                update_state_file(state)
                prompt = get_stage_test_prompt(state, stage_config)
                print(json.dumps({
                    "decision": "block",
                    "reason": prompt,
                    "systemMessage": f"Project-Loop #{state['iteration']} | Stage {state['current_stage']+1} builds! Moving to TEST..."
                }))
            else:
                # No test phase, move to next stage
                return advance_to_next_stage(state, stages, hook_input)
            sys.exit(0)
        else:
            update_state_file(state)
            prompt = get_stage_develop_prompt(state, stage_config)
            print(json.dumps({
                "decision": "block",
                "reason": prompt,
                "systemMessage": f"Project-Loop #{state['iteration']} | Developing Stage {state['current_stage']+1}..."
            }))
            sys.exit(0)

    # =========================================================================
    # STAGE_TEST PHASE
    # =========================================================================
    elif current_phase == "stage_test":
        stage_config = get_stage_config(stages[state["current_stage"]])

        if check_transcript_for_signal(hook_input, "STAGE_TESTS_PASSED"):
            return advance_to_next_stage(state, stages, hook_input)

        elif check_transcript_for_signal(hook_input, "STAGE_TESTS_FAILED"):
            if stage_config["loop_on_failure"]:
                # Loop back to develop (or plan if no develop)
                state["develop_failures"] += 1
                state["total_develop_failures"] = state.get("total_develop_failures", 0) + 1

                if stage_config["has_develop"]:
                    state["phase"] = "stage_develop"
                    state["stage_phase"] = "develop"
                    update_state_file(state)
                    prompt = get_stage_develop_prompt(state, stage_config)
                    print(json.dumps({
                        "decision": "block",
                        "reason": prompt,
                        "systemMessage": f"Project-Loop #{state['iteration']} | Tests failed! Back to DEVELOP (attempt #{state['develop_failures']+1})..."
                    }))
                elif stage_config["has_plan"]:
                    state["phase"] = "stage_plan"
                    state["stage_phase"] = "plan"
                    update_state_file(state)
                    prompt = get_stage_plan_prompt(state, stage_config)
                    print(json.dumps({
                        "decision": "block",
                        "reason": prompt,
                        "systemMessage": f"Project-Loop #{state['iteration']} | Tests failed! Back to PLAN (attempt #{state['develop_failures']+1})..."
                    }))
                else:
                    # Can't loop back, move to next stage anyway
                    return advance_to_next_stage(state, stages, hook_input)
            else:
                # No looping, move to next stage
                return advance_to_next_stage(state, stages, hook_input)
            sys.exit(0)
        else:
            update_state_file(state)
            prompt = get_stage_test_prompt(state, stage_config)
            print(json.dumps({
                "decision": "block",
                "reason": prompt,
                "systemMessage": f"Project-Loop #{state['iteration']} | Testing Stage {state['current_stage']+1}..."
            }))
            sys.exit(0)

    # =========================================================================
    # REVIEW PHASE - Final assessment before completion
    # =========================================================================
    elif current_phase == "review":
        review_pass = state.get("review_pass", 1)

        if check_transcript_for_signal(hook_input, "REVIEW_COMPLETE"):
            # All done! Truly complete now.
            state["phase"] = "complete"
            state["stage_phase"] = "done"
            state["enabled"] = False
            update_state_file(state)

            print(json.dumps({"decision": "allow"}))
            sys.exit(0)

        elif check_transcript_for_signal(hook_input, "REVIEW_NEEDS_FIXES"):
            # Parse fix stages from review document
            fix_stages = parse_fix_stages_from_review(review_pass)

            if not fix_stages:
                # No fix stages specified, ask again
                update_state_file(state)
                prompt = get_review_prompt(state)
                prompt += "\n\n**NOTE:** You signaled REVIEW_NEEDS_FIXES but no fix stages were found. Please create a JSON array of fix stages in your review document."
                print(json.dumps({
                    "decision": "block",
                    "reason": prompt,
                    "systemMessage": f"Project-Loop #{state['iteration']} | No fix stages found - please specify fixes"
                }))
                sys.exit(0)

            # Add fix stages to the stages list
            current_stages = state.get("stages", [])

            # Convert fix stage names to fix-type stages
            for fix_name in fix_stages:
                if isinstance(fix_name, str):
                    current_stages.append({"name": f"[Pass {review_pass + 1}] {fix_name}", "type": "fix"})
                elif isinstance(fix_name, dict):
                    fix_name["name"] = f"[Pass {review_pass + 1}] {fix_name.get('name', 'Fix')}"
                    if "type" not in fix_name:
                        fix_name["type"] = "fix"
                    current_stages.append(fix_name)

            state["stages"] = current_stages
            state["review_pass"] = review_pass + 1

            # Resume from current stage (first new fix stage)
            # current_stage was already at len(original stages), now we have more
            first_new_stage = state["current_stage"]

            # Get the first new stage config and determine its first phase
            new_stage_config = get_stage_config(current_stages[first_new_stage])

            if new_stage_config["has_plan"]:
                state["phase"] = "stage_plan"
                state["stage_phase"] = "plan"
                prompt = get_stage_plan_prompt(state, new_stage_config)
            elif new_stage_config["has_develop"]:
                state["phase"] = "stage_develop"
                state["stage_phase"] = "develop"
                prompt = get_stage_develop_prompt(state, new_stage_config)
            elif new_stage_config["has_test"]:
                state["phase"] = "stage_test"
                state["stage_phase"] = "test"
                prompt = get_stage_test_prompt(state, new_stage_config)
            else:
                # Edge case - stage has nothing, should not happen for fix type
                state["phase"] = "review"
                prompt = get_review_prompt(state)

            state["develop_failures"] = 0
            update_state_file(state)

            print(json.dumps({
                "decision": "block",
                "reason": prompt,
                "systemMessage": f"Project-Loop #{state['iteration']} | Review found issues! Starting {len(fix_stages)} fix stages (Pass {review_pass + 1})..."
            }))
            sys.exit(0)
        else:
            # Continue review
            update_state_file(state)
            prompt = get_review_prompt(state)
            print(json.dumps({
                "decision": "block",
                "reason": prompt,
                "systemMessage": f"Project-Loop #{state['iteration']} | Reviewing all findings (Pass {review_pass})..."
            }))
            sys.exit(0)

    # If phase is "complete" or unknown, allow stop
    print(json.dumps({"decision": "allow"}))
    sys.exit(0)


def advance_to_next_stage(state, stages, hook_input):
    """Helper to advance to the next stage or complete"""
    state["current_stage"] += 1
    state["develop_failures"] = 0

    # Update walkthrough.md progress (mark previous stage complete)
    try:
        walkthrough_path = Path.cwd() / ".claude" / "walkthrough.md"
        if walkthrough_path.exists():
            content = walkthrough_path.read_text(encoding="utf-8")
            # Find and mark the Nth checkbox as complete
            count = [0]
            def replace_nth(match):
                count[0] += 1
                if count[0] == state["current_stage"]:  # Previous stage (we already incremented)
                    return '[x]'
                return match.group(0)
            content = re.sub(r'\[ \]', replace_nth, content)
            walkthrough_path.write_text(content, encoding="utf-8")
    except:
        pass

    if state["current_stage"] >= len(stages):
        # All stages executed - go to REVIEW phase (not complete!)
        state["phase"] = "review"
        state["stage_phase"] = "review"
        # Store original stage count if this is the first review
        if state.get("original_stage_count", 0) == 0:
            state["original_stage_count"] = len(stages)
        update_state_file(state)

        # Mark all remaining checkboxes in walkthrough
        try:
            walkthrough_path = Path.cwd() / ".claude" / "walkthrough.md"
            if walkthrough_path.exists():
                content = walkthrough_path.read_text(encoding="utf-8")
                content = re.sub(r'\[ \]', '[x]', content)
                walkthrough_path.write_text(content, encoding="utf-8")
        except:
            pass

        prompt = get_review_prompt(state)
        print(json.dumps({
            "decision": "block",
            "reason": prompt,
            "systemMessage": f"Project-Loop #{state['iteration']} | All {len(stages)} stages complete! Entering REVIEW phase..."
        }))
        sys.exit(0)

    # Start next stage
    next_stage_config = get_stage_config(stages[state["current_stage"]])

    # Determine first phase of next stage
    if next_stage_config["has_plan"]:
        state["phase"] = "stage_plan"
        state["stage_phase"] = "plan"
        prompt = get_stage_plan_prompt(state, next_stage_config)
    elif next_stage_config["has_develop"]:
        state["phase"] = "stage_develop"
        state["stage_phase"] = "develop"
        prompt = get_stage_develop_prompt(state, next_stage_config)
    elif next_stage_config["has_test"]:
        state["phase"] = "stage_test"
        state["stage_phase"] = "test"
        prompt = get_stage_test_prompt(state, next_stage_config)
    else:
        # Stage has nothing, recurse to skip it
        return advance_to_next_stage(state, stages, hook_input)

    update_state_file(state)
    print(json.dumps({
        "decision": "block",
        "reason": prompt,
        "systemMessage": f"Project-Loop #{state['iteration']} | Stage {state['current_stage']} complete! Starting Stage {state['current_stage']+1}..."
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
