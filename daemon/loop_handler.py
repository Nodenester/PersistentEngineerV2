#!/usr/bin/env python3
"""
Loop Handler - Implements project-loop and build-test-loop logic

This module handles the autonomous development loops that allow Claude to:
1. Plan multi-stage projects
2. Build and test iteratively
3. Loop until tests pass
4. Continue through multiple stages

The agent can trigger these loops by:
1. User explicitly sending /project-loop or /build-test-loop commands
2. Agent outputting <start-project-loop> or <start-build-test-loop> signals
"""

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import logging

logger = logging.getLogger('LoopHandler')


class LoopType(Enum):
    PROJECT_LOOP = "project-loop"
    BUILD_TEST_LOOP = "build-test-loop"
    CROSS_WORKSPACE_LOOP = "cross-workspace-loop"  # Multi-repo/workspace tasks


class Phase(Enum):
    ANALYZE = "analyze"
    PLAN = "plan"
    DEVELOP = "develop"
    TEST = "test"
    REANALYZE = "reanalyze"  # Check if more work needed after all stages
    COMPLETE = "complete"


class StageType(Enum):
    INVESTIGATE = "investigate"
    BUILD = "build"
    FIX = "fix"
    VERIFY = "verify"
    DOCUMENT = "document"


@dataclass
class LoopState:
    """State tracking for development loops."""
    enabled: bool = True
    loop_type: LoopType = LoopType.PROJECT_LOOP
    phase: Phase = Phase.ANALYZE
    iteration: int = 0
    max_iterations: int = 500
    build_command: str = ""
    test_url: str = ""
    original_prompt: str = ""
    stages: List[Dict[str, Any]] = field(default_factory=list)
    current_stage: int = 0
    stage_phase: str = "none"
    develop_failures: int = 0
    total_develop_failures: int = 0
    workflow_mode: str = "build"
    deployment_type: str = "local"
    # Cross-workspace support
    target_workspaces: List[str] = field(default_factory=list)  # Workspaces involved in this task
    current_workspace: str = ""  # Currently active workspace
    is_cross_workspace: bool = False  # Whether this is a cross-workspace task

    def to_dict(self) -> Dict[str, Any]:
        return {
            'enabled': self.enabled,
            'loop_type': self.loop_type.value,
            'phase': self.phase.value,
            'iteration': self.iteration,
            'max_iterations': self.max_iterations,
            'build_command': self.build_command,
            'test_url': self.test_url,
            'original_prompt': self.original_prompt,
            'stages': self.stages,
            'current_stage': self.current_stage,
            'stage_phase': self.stage_phase,
            'develop_failures': self.develop_failures,
            'total_develop_failures': self.total_develop_failures,
            'workflow_mode': self.workflow_mode,
            'deployment_type': self.deployment_type,
            # Cross-workspace fields
            'target_workspaces': self.target_workspaces,
            'current_workspace': self.current_workspace,
            'is_cross_workspace': self.is_cross_workspace,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LoopState':
        state = cls()
        state.enabled = data.get('enabled', True)
        state.loop_type = LoopType(data.get('loop_type', 'project-loop'))
        state.phase = Phase(data.get('phase', 'analyze'))
        state.iteration = data.get('iteration', 0)
        state.max_iterations = data.get('max_iterations', 500)
        state.build_command = data.get('build_command', '')
        state.test_url = data.get('test_url', '')
        state.original_prompt = data.get('original_prompt', '')
        state.stages = data.get('stages', [])
        state.current_stage = data.get('current_stage', 0)
        state.stage_phase = data.get('stage_phase', 'none')
        state.develop_failures = data.get('develop_failures', 0)
        state.total_develop_failures = data.get('total_develop_failures', 0)
        state.workflow_mode = data.get('workflow_mode', 'build')
        state.deployment_type = data.get('deployment_type', 'local')
        # Cross-workspace fields
        state.target_workspaces = data.get('target_workspaces', [])
        state.current_workspace = data.get('current_workspace', '')
        state.is_cross_workspace = data.get('is_cross_workspace', False)
        return state


class LoopHandler:
    """Handles project-loop and build-test-loop execution."""

    # Signals that Claude outputs to control the loop
    SIGNALS = {
        'ANALYZE_COMPLETE': r'<promise>ANALYZE_COMPLETE</promise>',
        'STAGE_PLAN_COMPLETE': r'<promise>STAGE_PLAN_COMPLETE</promise>',
        'STAGE_BUILD_SUCCESS': r'<promise>STAGE_BUILD_SUCCESS</promise>',
        'BUILD_SUCCESS': r'<promise>BUILD_SUCCESS</promise>',
        'STAGE_TESTS_PASSED': r'<promise>STAGE_TESTS_PASSED</promise>',
        'TESTS_PASSED': r'<promise>TESTS_PASSED</promise>',
        'STAGE_TESTS_FAILED': r'<promise>STAGE_TESTS_FAILED</promise>',
        'TESTS_FAILED': r'<promise>TESTS_FAILED</promise>',
        'PROJECT_COMPLETE': r'<promise>PROJECT_COMPLETE</promise>',
        'LOOP_COMPLETE': r'<promise>LOOP_COMPLETE</promise>',
        'MORE_WORK_NEEDED': r'<promise>MORE_WORK_NEEDED</promise>',  # Re-analyze found more to do
        'TASK_FULLY_COMPLETE': r'<promise>TASK_FULLY_COMPLETE</promise>',  # Re-analyze confirmed done
    }

    # Patterns for agent-initiated loops
    AGENT_TRIGGERS = {
        'project_loop': r'<start-project-loop>(.*?)</start-project-loop>',
        'build_test_loop': r'<start-build-test-loop>(.*?)</start-build-test-loop>',
    }

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self.state_file = workspace_path / '.claude' / 'loop-state.json'
        self.state: Optional[LoopState] = None

    def detect_loop_command(self, task: str) -> Tuple[Optional[LoopType], str, List[str]]:
        """
        Detect if task starts with /project-loop, /build-test-loop, or /cross-workspace-loop.
        Returns (loop_type, extracted_task, target_workspaces) or (None, original_task, []).
        """
        task = task.strip()

        # Check for /cross-workspace-loop first (more specific)
        # Format: /cross-workspace-loop workspace1,workspace2 "task description"
        if task.startswith('/cross-workspace-loop'):
            remaining = task[len('/cross-workspace-loop'):].strip()
            # Parse workspaces (comma-separated before the task)
            workspaces = []
            if remaining and not remaining.startswith('"') and not remaining.startswith("'"):
                # First part is workspaces
                parts = remaining.split(None, 1)  # Split on first whitespace
                if len(parts) >= 1:
                    workspaces = [w.strip() for w in parts[0].split(',') if w.strip()]
                    remaining = parts[1] if len(parts) > 1 else ""
            # Extract task
            extracted = remaining.strip()
            if extracted.startswith('"') and extracted.endswith('"'):
                extracted = extracted[1:-1]
            elif extracted.startswith("'") and extracted.endswith("'"):
                extracted = extracted[1:-1]
            return LoopType.CROSS_WORKSPACE_LOOP, extracted, workspaces

        # Check for /project-loop
        if task.startswith('/project-loop'):
            extracted = task[len('/project-loop'):].strip()
            # Remove quotes if present
            if extracted.startswith('"') and extracted.endswith('"'):
                extracted = extracted[1:-1]
            elif extracted.startswith("'") and extracted.endswith("'"):
                extracted = extracted[1:-1]
            return LoopType.PROJECT_LOOP, extracted, []

        # Check for /build-test-loop
        if task.startswith('/build-test-loop'):
            extracted = task[len('/build-test-loop'):].strip()
            if extracted.startswith('"') and extracted.endswith('"'):
                extracted = extracted[1:-1]
            elif extracted.startswith("'") and extracted.endswith("'"):
                extracted = extracted[1:-1]
            return LoopType.BUILD_TEST_LOOP, extracted, []

        return None, task, []

    def detect_agent_trigger(self, output: str) -> Tuple[Optional[LoopType], Optional[str]]:
        """
        Detect if Claude output contains a signal to start a loop.
        Returns (loop_type, task) or (None, None).
        """
        # Check for project-loop trigger
        match = re.search(self.AGENT_TRIGGERS['project_loop'], output, re.DOTALL)
        if match:
            return LoopType.PROJECT_LOOP, match.group(1).strip()

        # Check for build-test-loop trigger
        match = re.search(self.AGENT_TRIGGERS['build_test_loop'], output, re.DOTALL)
        if match:
            return LoopType.BUILD_TEST_LOOP, match.group(1).strip()

        return None, None

    def detect_signals(self, output: str) -> List[str]:
        """Detect completion/status signals in Claude's output."""
        found = []
        for name, pattern in self.SIGNALS.items():
            if re.search(pattern, output):
                found.append(name)
        return found

    def initialize_loop(self, loop_type: LoopType, task: str,
                       build_command: str = "", test_url: str = "",
                       target_workspaces: List[str] = None) -> LoopState:
        """Initialize a new development loop."""
        # Create .claude directory
        claude_dir = self.workspace_path / '.claude'
        claude_dir.mkdir(parents=True, exist_ok=True)

        # Clean up previous state
        for f in ['loop-state.json', 'project-loop.local.md', 'build-test-loop.local.md', 'walkthrough.md']:
            (claude_dir / f).unlink(missing_ok=True)

        stages_dir = claude_dir / 'stages'
        if stages_dir.exists():
            for f in stages_dir.iterdir():
                f.unlink()

        # Detect workflow mode from task
        workflow_mode = self._detect_workflow_mode(task)

        # Determine initial phase based on loop type
        if loop_type == LoopType.CROSS_WORKSPACE_LOOP:
            initial_phase = Phase.ANALYZE
        elif loop_type == LoopType.PROJECT_LOOP:
            initial_phase = Phase.ANALYZE
        else:
            initial_phase = Phase.PLAN

        # Create state
        self.state = LoopState(
            enabled=True,
            loop_type=loop_type,
            phase=initial_phase,
            iteration=0,
            max_iterations=500,
            build_command=build_command,
            test_url=test_url,
            original_prompt=task,
            workflow_mode=workflow_mode,
            # Cross-workspace fields
            target_workspaces=target_workspaces or [],
            current_workspace=target_workspaces[0] if target_workspaces else "",
            is_cross_workspace=loop_type == LoopType.CROSS_WORKSPACE_LOOP,
        )

        self._save_state()
        logger.info(f"Initialized {loop_type.value} for task: {task[:50]}...")
        return self.state

    def _detect_workflow_mode(self, task: str) -> str:
        """Detect workflow mode from task description."""
        task_lower = task.lower()

        debug_keywords = ['debug', 'find', 'investigate', 'test', 'check', 'bug', 'issue', 'problem', 'error']
        build_keywords = ['add', 'create', 'implement', 'build', 'develop', 'make', 'new']

        has_debug = any(kw in task_lower for kw in debug_keywords)
        has_build = any(kw in task_lower for kw in build_keywords)

        if has_debug and has_build:
            return 'hybrid'
        elif has_debug:
            return 'debug'
        else:
            return 'build'

    def get_phase_prompt(self) -> str:
        """Get the prompt for the current phase."""
        if not self.state:
            return ""

        if self.state.loop_type == LoopType.CROSS_WORKSPACE_LOOP:
            return self._get_cross_workspace_prompt()
        elif self.state.loop_type == LoopType.PROJECT_LOOP:
            return self._get_project_loop_prompt()
        else:
            return self._get_build_test_loop_prompt()

    def _get_cross_workspace_prompt(self) -> str:
        """Get prompt for cross-workspace loop based on current phase."""
        phase = self.state.phase

        if phase == Phase.ANALYZE:
            return self._get_cross_workspace_analyze_prompt()
        elif phase == Phase.PLAN:
            return self._get_cross_workspace_plan_prompt()
        elif phase == Phase.DEVELOP:
            return self._get_cross_workspace_develop_prompt()
        elif phase == Phase.TEST:
            return self._get_cross_workspace_test_prompt()
        elif phase == Phase.REANALYZE:
            return self._get_reanalyze_prompt()
        else:
            return "The cross-workspace loop is complete."

    def _get_cross_workspace_analyze_prompt(self) -> str:
        """Get the ANALYZE phase prompt for cross-workspace tasks."""
        workspaces_list = "\n".join([f"- **{ws}**: /workspace/projects/{ws}" for ws in self.state.target_workspaces])

        return f'''# CROSS-WORKSPACE-LOOP: ANALYZE PHASE

You are working on a **cross-workspace task** that spans multiple repositories/projects!

**Task:** {self.state.original_prompt}

## Target Workspaces

{workspaces_list}

## Your Goals

1. **Analyze ALL target workspaces** - Use `code-structure-analyzer` on each
2. **Understand how they connect** - APIs, shared types, dependencies
3. **Plan coordinated changes** - What needs to change in each workspace
4. **Define workspace-targeted stages** - Each stage specifies which workspace it modifies

## CRITICAL: Stage Format for Cross-Workspace

Each stage MUST specify its target workspace:

```json
{{
  "stages": [
    {{"name": "Add API endpoint", "type": "build", "workspace": "backend"}},
    {{"name": "Update API client", "type": "build", "workspace": "frontend"}},
    {{"name": "Add shared types", "type": "build", "workspace": "shared"}},
    {{"name": "Integration test", "type": "verify", "workspace": "frontend"}}
  ],
  "workspaces": {{
    "backend": {{"build_command": "dotnet build", "test_url": "http://localhost:5000"}},
    "frontend": {{"build_command": "npm run build", "test_url": "http://localhost:3000"}}
  }}
}}
```

## Important Notes

- You can READ files from ANY workspace at any time
- Each stage only MODIFIES the specified workspace
- Think about the ORDER of changes (dependencies first)
- Consider how to test cross-workspace integration

Create a walkthrough at `.claude/walkthrough.md` explaining how the workspaces interact.

When analysis is complete, output: <promise>ANALYZE_COMPLETE</promise>
'''

    def _get_cross_workspace_plan_prompt(self) -> str:
        """Get the PLAN phase prompt for cross-workspace tasks."""
        if self.state.stages and self.state.current_stage >= len(self.state.stages):
            return self._get_reanalyze_prompt()

        if not self.state.stages:
            return f'''# CROSS-WORKSPACE-LOOP: PLAN PHASE

**Task:** {self.state.original_prompt}
**Target Workspaces:** {', '.join(self.state.target_workspaces)}

No stages were defined. Create a plan for implementing changes across the workspaces.

When your plan is complete, output: <promise>STAGE_PLAN_COMPLETE</promise>
'''

        stage = self.state.stages[self.state.current_stage]
        stage_name = stage.get('name', f'Stage {self.state.current_stage + 1}')
        stage_type = stage.get('type', 'build')
        stage_workspace = stage.get('workspace', self.state.current_workspace or 'default')
        stage_num = self.state.current_stage + 1

        return f'''# CROSS-WORKSPACE-LOOP: PLAN PHASE - Stage {stage_num}

**Stage:** {stage_name}
**Type:** {stage_type}
**TARGET WORKSPACE:** {stage_workspace}
**Workspace Path:** /workspace/projects/{stage_workspace}

**Original Task:** {self.state.original_prompt}

## Your Goals

Create a plan for this stage at `.claude/stages/stage-{stage_num}-plan.md`:

1. What changes need to be made IN {stage_workspace}
2. What files in {stage_workspace} will be modified
3. How other workspaces will consume these changes
4. How to verify this stage works

**Remember:** This stage ONLY modifies {stage_workspace}, but you can read from all workspaces.

When your plan is complete, output: <promise>STAGE_PLAN_COMPLETE</promise>
'''

    def _get_cross_workspace_develop_prompt(self) -> str:
        """Get the DEVELOP phase prompt for cross-workspace tasks."""
        stage_workspace = self.state.current_workspace
        if self.state.stages and self.state.current_stage < len(self.state.stages):
            stage = self.state.stages[self.state.current_stage]
            stage_workspace = stage.get('workspace', stage_workspace)

        build_cmd = self.state.build_command or "auto-detect"

        stage_info = ""
        if self.state.stages and self.state.current_stage < len(self.state.stages):
            stage = self.state.stages[self.state.current_stage]
            stage_info = f"\n**Current Stage:** {stage.get('name', 'Unknown')}"

        return f'''# CROSS-WORKSPACE-LOOP: DEVELOP PHASE

**Task:** {self.state.original_prompt}{stage_info}
**TARGET WORKSPACE:** {stage_workspace}
**Workspace Path:** /workspace/projects/{stage_workspace}
**Build Command:** {build_cmd}
**Iteration:** {self.state.iteration}

## Your Goals

1. **Work in {stage_workspace}** - cd to /workspace/projects/{stage_workspace}
2. **Implement the changes** according to your plan
3. **Run the build** to verify compilation
4. **Fix any build errors** before proceeding

## Cross-Workspace Tips

- You can READ from other workspaces to understand interfaces/types
- But ONLY WRITE to {stage_workspace} in this stage
- Later stages will update other workspaces

When the build succeeds with no errors, output: <promise>BUILD_SUCCESS</promise>
'''

    def _get_cross_workspace_test_prompt(self) -> str:
        """Get the TEST phase prompt for cross-workspace tasks."""
        stage_workspace = self.state.current_workspace
        if self.state.stages and self.state.current_stage < len(self.state.stages):
            stage = self.state.stages[self.state.current_stage]
            stage_workspace = stage.get('workspace', stage_workspace)

        return f'''# CROSS-WORKSPACE-LOOP: TEST PHASE

**Task:** {self.state.original_prompt}
**Testing Workspace:** {stage_workspace}

## Your Goals

1. **Test the changes in {stage_workspace}**
2. **If this affects other workspaces**, verify they still work
3. **Run integration tests** if applicable

## Testing Approach

- Unit test the changes in {stage_workspace}
- If APIs changed, verify consumers still work
- Use playwright for web UI testing

If all tests pass: <promise>TESTS_PASSED</promise>
If tests fail: <promise>TESTS_FAILED</promise>
'''

    def get_current_stage_workspace(self) -> Optional[str]:
        """Get the workspace for the current stage, or None if not in a stage."""
        if not self.state or not self.state.stages:
            return self.state.current_workspace if self.state else None

        if self.state.current_stage < len(self.state.stages):
            stage = self.state.stages[self.state.current_stage]
            return stage.get('workspace', self.state.current_workspace)

        return self.state.current_workspace

    def _get_project_loop_prompt(self) -> str:
        """Get prompt for project-loop based on current phase."""
        phase = self.state.phase

        if phase == Phase.ANALYZE:
            return self._get_analyze_prompt()
        elif phase == Phase.PLAN:
            return self._get_stage_plan_prompt()
        elif phase == Phase.DEVELOP:
            return self._get_develop_prompt()
        elif phase == Phase.TEST:
            return self._get_test_prompt()
        elif phase == Phase.REANALYZE:
            return self._get_reanalyze_prompt()
        else:
            return "The project loop is complete."

    def _get_build_test_loop_prompt(self) -> str:
        """Get prompt for build-test-loop based on current phase."""
        phase = self.state.phase

        if phase == Phase.PLAN:
            return self._get_simple_plan_prompt()
        elif phase == Phase.DEVELOP:
            return self._get_develop_prompt()
        elif phase == Phase.TEST:
            return self._get_test_prompt()
        else:
            return "The build-test loop is complete."

    def _get_analyze_prompt(self) -> str:
        """Get the ANALYZE phase prompt."""
        return f'''# PROJECT-LOOP: ANALYZE PHASE

You are in the ANALYZE phase of a project-loop for this task:

**Task:** {self.state.original_prompt}

## Your Goals

First, check if this is an **existing project** or a **new project from scratch**:

### If workspace has existing code:
1. **Analyze the codebase** using `code-structure-analyzer` to understand the project
2. **Read existing documentation** (README.md, CLAUDE.md, .notes/, etc.)
3. **Break down the task** into logical stages based on what needs to be modified

### If workspace is empty (new project from scratch):
1. **Plan the project architecture** - what framework, structure, and components are needed
2. **Create initial project structure** - set up the basic files and folders
3. **Break down the task** into logical stages for building the project

## Creating Your Plan

Create a walkthrough at `.claude/walkthrough.md` with:
- Project overview (existing or planned)
- Key files and their purposes
- Your planned stages

## Stage Types

Define stages using these types:
- `investigate` - Find issues, explore (no looping)
- `build` - Build new features (full cycle with looping)
- `fix` - Quick fixes (no planning, just fix and test)
- `verify` - Final verification (test only)
- `document` - Documentation only (no testing)

## CRITICAL: Output Format

After your analysis, you MUST output your stages as JSON in this exact format:

```json
{{
  "stages": [
    {{"name": "Stage 1 Name", "type": "build"}},
    {{"name": "Stage 2 Name", "type": "build"}},
    {{"name": "Final Verification", "type": "verify"}}
  ],
  "build_command": "npm run build or dotnet build or cargo build etc",
  "test_url": "http://localhost:PORT or empty string if CLI app"
}}
```

## CRITICAL: Signal Completion

After outputting the JSON stages, you MUST output this signal on its own line:

<promise>ANALYZE_COMPLETE</promise>

This signal tells the daemon to proceed to the next phase. Without it, the loop will not continue!
'''

    def _get_stage_plan_prompt(self) -> str:
        """Get the PLAN phase prompt for current stage."""
        # Check if all defined stages are complete
        if self.state.stages and self.state.current_stage >= len(self.state.stages):
            # All stages done - trigger reanalyze instead of immediate completion
            return f'''# PROJECT-LOOP: RE-ANALYZE PHASE

All {len(self.state.stages)} defined stages have been completed. Now evaluate if the original task is fully done:

**Original Task:** {self.state.original_prompt}

## Your Goals

1. Review all the work completed so far
2. Test the implementation end-to-end
3. Determine if the task is truly complete

If the task is **fully complete**, output: <promise>TASK_FULLY_COMPLETE</promise>

If **more work is needed**, define additional stages as JSON and output: <promise>MORE_WORK_NEEDED</promise>
'''

        # If no stages were defined, create a default implementation stage
        if not self.state.stages:
            return f'''# PROJECT-LOOP: PLAN PHASE - Implementation

**Task:** {self.state.original_prompt}

The stages could not be parsed from the analysis phase. Please create a plan to implement the task directly.

## Your Goals

1. Create a detailed implementation plan at `.claude/stages/stage-1-plan.md`
2. List all files to create/modify
3. Define how to test/verify success
4. Identify build commands needed

When your plan is complete, output: <promise>STAGE_PLAN_COMPLETE</promise>
'''

        stage = self.state.stages[self.state.current_stage]
        stage_name = stage.get('name', f'Stage {self.state.current_stage + 1}')
        stage_type = stage.get('type', 'build')
        stage_num = self.state.current_stage + 1

        return f'''# PROJECT-LOOP: PLAN PHASE - Stage {stage_num}

**Stage:** {stage_name}
**Type:** {stage_type}
**Original Task:** {self.state.original_prompt}

## Your Goals

Create a detailed plan for this stage at `.claude/stages/stage-{stage_num}-plan.md`:

1. What specific changes need to be made
2. Which files will be modified/created
3. What tests will verify success
4. Any dependencies or prerequisites

Read the walkthrough at `.claude/walkthrough.md` for context.

When your plan is complete, output: <promise>STAGE_PLAN_COMPLETE</promise>
'''

    def _get_simple_plan_prompt(self) -> str:
        """Get the simple PLAN prompt for build-test-loop."""
        return f'''# BUILD-TEST-LOOP: PLAN PHASE

**Task:** {self.state.original_prompt}

## Your Goals

1. **Analyze the codebase** to understand what needs to change
2. **Create a brief plan** - what files to modify and how
3. **Identify the build command** and test approach

Keep the plan simple and focused. When ready, output: <promise>STAGE_PLAN_COMPLETE</promise>
'''

    def _get_develop_prompt(self) -> str:
        """Get the DEVELOP phase prompt."""
        build_cmd = self.state.build_command or "auto-detect"

        stage_info = ""
        if self.state.loop_type == LoopType.PROJECT_LOOP and self.state.stages:
            stage = self.state.stages[self.state.current_stage]
            stage_info = f"\n**Current Stage:** {stage.get('name', 'Unknown')}"

        return f'''# {'PROJECT' if self.state.loop_type == LoopType.PROJECT_LOOP else 'BUILD-TEST'}-LOOP: DEVELOP PHASE

**Task:** {self.state.original_prompt}{stage_info}
**Build Command:** {build_cmd}
**Iteration:** {self.state.iteration}

## Your Goals

1. **Implement the changes** according to your plan
2. **Run the build** to verify compilation: `{build_cmd}`
3. **Fix any build errors** before proceeding

## Important

- Read your plan if you created one
- Make incremental changes and test frequently
- Fix ALL build errors before moving to testing

When the build succeeds with no errors, output: <promise>BUILD_SUCCESS</promise>

If you cannot fix a build error after multiple attempts, describe the issue and output: <promise>TESTS_FAILED</promise>
'''

    def _get_test_prompt(self) -> str:
        """Get the TEST phase prompt."""
        test_url = self.state.test_url or "the running application"

        return f'''# {'PROJECT' if self.state.loop_type == LoopType.PROJECT_LOOP else 'BUILD-TEST'}-LOOP: TEST PHASE

**Task:** {self.state.original_prompt}
**Test URL:** {test_url}

## Your Goals

1. **Start the application** if not already running
2. **Test the functionality** using Playwright or manual verification
3. **Verify the changes work** as expected

## Testing Approach

- Use `playwright` MCP tool to interact with web applications
- Check that your changes are visible and functional
- Test edge cases if applicable

## Output

If all tests pass: <promise>TESTS_PASSED</promise>
If tests fail: <promise>TESTS_FAILED</promise> (then loop back to fix)
'''

    def _get_reanalyze_prompt(self) -> str:
        """Get the REANALYZE phase prompt - check if task is truly complete."""
        completed_stages = self.state.stages[:self.state.current_stage] if self.state.stages else []
        stage_summary = "\n".join([f"  - {s.get('name', 'Unknown')}: COMPLETED" for s in completed_stages])

        return f'''# PROJECT-LOOP: RE-ANALYZE PHASE

**Original Task:** {self.state.original_prompt}

## Completed Stages

{stage_summary if stage_summary else "  (No stages recorded)"}

## Your Goals

All planned stages have been completed. Now you must **verify the task is truly done**:

1. **Review the original task** - What was asked?
2. **Check what was accomplished** - Read the walkthrough and code changes
3. **Test the complete solution** - Does everything work together?
4. **Identify any gaps** - Is anything missing or broken?

## Decision

After your review, output ONE of these signals:

**If the task is FULLY COMPLETE:**
- All requirements are met
- Everything works correctly
- No more work needed
Output: <promise>TASK_FULLY_COMPLETE</promise>

**If MORE WORK is needed:**
- Missing features
- Bugs discovered
- Integration issues
- Additional requirements

First, create NEW stages for the remaining work as JSON:
```json
{{
  "stages": [
    {{"name": "Fix X", "type": "fix"}},
    {{"name": "Add Y", "type": "build"}}
  ]
}}
```

Then output: <promise>MORE_WORK_NEEDED</promise>

The loop will continue with your new stages until the task is truly complete.
'''

    def process_signals(self, signals: List[str]) -> Tuple[bool, str]:
        """
        Process detected signals and update state.
        Returns (should_continue, next_prompt).
        """
        if not self.state:
            return False, ""

        logger.info(f"Processing signals: {signals}")

        # Handle completion signals
        if 'PROJECT_COMPLETE' in signals or 'LOOP_COMPLETE' in signals:
            self.state.phase = Phase.COMPLETE
            self.state.enabled = False
            self._save_state()
            return False, "Loop complete!"

        # Handle phase-specific signals
        if self.state.loop_type == LoopType.PROJECT_LOOP:
            return self._process_project_loop_signals(signals)
        else:
            return self._process_build_test_loop_signals(signals)

    def _process_project_loop_signals(self, signals: List[str]) -> Tuple[bool, str]:
        """Process signals for project-loop."""
        phase = self.state.phase

        if phase == Phase.ANALYZE and 'ANALYZE_COMPLETE' in signals:
            # Move to planning first stage
            self.state.phase = Phase.PLAN
            self.state.current_stage = 0
            self._save_state()
            return True, self.get_phase_prompt()

        if phase == Phase.PLAN and 'STAGE_PLAN_COMPLETE' in signals:
            # If no stages defined, create a default one
            if not self.state.stages:
                self.state.stages = [{"name": "Implementation", "type": "build"}]
                self.state.current_stage = 0
                logger.info("Created default stage since none were defined")
            # Move to develop
            self.state.phase = Phase.DEVELOP
            self._save_state()
            return True, self.get_phase_prompt()

        if phase == Phase.DEVELOP and ('BUILD_SUCCESS' in signals or 'STAGE_BUILD_SUCCESS' in signals):
            # Move to test
            self.state.phase = Phase.TEST
            self._save_state()
            return True, self.get_phase_prompt()

        if phase == Phase.TEST:
            if 'TESTS_PASSED' in signals or 'STAGE_TESTS_PASSED' in signals:
                # Move to next stage or RE-ANALYZE
                self.state.current_stage += 1
                stages_count = len(self.state.stages) if self.state.stages else 1
                if self.state.current_stage >= stages_count:
                    # All stages done - go to REANALYZE to check if truly complete
                    self.state.phase = Phase.REANALYZE
                    self._save_state()
                    logger.info(f"All {stages_count} stages complete, entering REANALYZE phase")
                    return True, self.get_phase_prompt()
                else:
                    self.state.phase = Phase.PLAN
                    self._save_state()
                    return True, self.get_phase_prompt()

            if 'TESTS_FAILED' in signals or 'STAGE_TESTS_FAILED' in signals:
                # Loop back to develop
                self.state.phase = Phase.DEVELOP
                self.state.develop_failures += 1
                self.state.total_develop_failures += 1
                self._save_state()
                return True, self.get_phase_prompt()

        if phase == Phase.REANALYZE:
            if 'TASK_FULLY_COMPLETE' in signals or 'PROJECT_COMPLETE' in signals:
                # Task is truly done
                self.state.phase = Phase.COMPLETE
                self.state.enabled = False
                self._save_state()
                logger.info("Task confirmed complete after re-analysis")
                return False, "Task fully complete!"

            if 'MORE_WORK_NEEDED' in signals:
                # More work needed - new stages should have been parsed
                # Reset to plan the new stages
                self.state.current_stage = 0
                self.state.phase = Phase.PLAN
                self.state.iteration += 1
                self._save_state()
                logger.info(f"More work needed, continuing with {len(self.state.stages)} new stages")
                return True, self.get_phase_prompt()

        # No recognized signal, continue with same phase
        self.state.iteration += 1
        self._save_state()
        return True, self.get_phase_prompt()

    def _process_build_test_loop_signals(self, signals: List[str]) -> Tuple[bool, str]:
        """Process signals for build-test-loop."""
        phase = self.state.phase

        if phase == Phase.PLAN and 'STAGE_PLAN_COMPLETE' in signals:
            self.state.phase = Phase.DEVELOP
            self._save_state()
            return True, self.get_phase_prompt()

        if phase == Phase.DEVELOP and ('BUILD_SUCCESS' in signals or 'STAGE_BUILD_SUCCESS' in signals):
            self.state.phase = Phase.TEST
            self._save_state()
            return True, self.get_phase_prompt()

        if phase == Phase.TEST:
            if 'TESTS_PASSED' in signals or 'STAGE_TESTS_PASSED' in signals:
                self.state.phase = Phase.COMPLETE
                self.state.enabled = False
                self._save_state()
                return False, "Build-test loop complete!"

            if 'TESTS_FAILED' in signals or 'STAGE_TESTS_FAILED' in signals:
                self.state.phase = Phase.DEVELOP
                self.state.develop_failures += 1
                self._save_state()
                return True, self.get_phase_prompt()

        self.state.iteration += 1
        self._save_state()
        return True, self.get_phase_prompt()

    def update_stages(self, stages_json: str):
        """Update stages from Claude's ANALYZE output."""
        try:
            data = json.loads(stages_json)
            self.state.stages = data.get('stages', [])
            if data.get('build_command'):
                self.state.build_command = data['build_command']
            if data.get('test_url'):
                self.state.test_url = data['test_url']
            self._save_state()
            logger.info(f"Updated stages: {len(self.state.stages)} stages defined")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse stages JSON: {e}")

    def _save_state(self):
        """Save state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.state.to_dict(), indent=2))

    def load_state(self) -> Optional[LoopState]:
        """Load state from file if exists."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                self.state = LoopState.from_dict(data)
                return self.state
            except Exception as e:
                logger.warning(f"Failed to load loop state: {e}")
        return None

    def is_active(self) -> bool:
        """Check if a loop is currently active."""
        return self.state is not None and self.state.enabled

    def get_status(self) -> Dict[str, Any]:
        """Get current loop status."""
        if not self.state:
            return {'active': False}

        return {
            'active': self.state.enabled,
            'type': self.state.loop_type.value,
            'phase': self.state.phase.value,
            'iteration': self.state.iteration,
            'current_stage': self.state.current_stage,
            'total_stages': len(self.state.stages),
            'task': self.state.original_prompt[:100],
        }
