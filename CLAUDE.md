# CLAUDE.md - Persistent Engineer Agent

This file provides guidance to Claude Code when working in this container.

## IMPORTANT: Web Browsing

**ALWAYS use Playwright MCP for web browsing tasks** (opening websites, navigating, clicking, filling forms, etc.). Playwright controls the browser programmatically and is fast and reliable.

**Only use desktop-control** for non-browser GUI applications or when you specifically need to interact with the visible desktop (e.g., file managers, IDEs, system dialogs).

**DO NOT** launch Chrome manually with desktop-control for web tasks - use Playwright instead!

### Browser Tips

1. **Cookie Popups** - ALWAYS reject cookies when possible. Use JavaScript to quickly dismiss cookie banners:
   ```javascript
   // Try common cookie reject buttons
   document.querySelector('[aria-label*="Reject"]')?.click();
   document.querySelector('button[title*="Reject"]')?.click();
   document.querySelector('.reject-all')?.click();
   ```

2. **Bypass Cookie Consent with Direct URLs** - If a site shows a cookie consent dialog, **navigate directly to the content URL** instead of trying to dismiss the dialog. For example:
   - Instead of going to `youtube.com` and fighting the consent dialog, navigate directly to `youtube.com/watch?v=VIDEO_ID`
   - Direct URLs often bypass or auto-dismiss consent dialogs
   - This works for most sites: add the specific page/content path to skip the homepage consent flow

3. **Popups & Dialogs** - If clicking doesn't work after 2-3 tries, use JavaScript:
   ```javascript
   // Remove overlay/modal elements
   document.querySelectorAll('[role="dialog"], .modal, .popup, .overlay').forEach(el => el.remove());
   // Or click buttons programmatically
   document.querySelector('button')?.click();
   ```

4. **Fullscreen Mode** - When watching videos or viewing content, use fullscreen (F11 or fullscreen button) for better visibility.

5. **Privacy First** - Always choose privacy-preserving options:
   - Reject all cookies
   - Don't sign in unless required
   - Skip personalization

6. **Be Efficient** - Don't spend more than 30 seconds on a popup. If clicking doesn't work:
   - Try navigating directly to the content URL (bypasses most consent dialogs)
   - Use JavaScript to remove the overlay
   - Navigate away and try a different approach
   - NEVER waste time clicking the same button repeatedly

## AUTOMATIC TOOL SELECTION

**You MUST automatically choose the right workflow based on task complexity:**

### Use `/project-loop` when:
- Task has **multiple features** or **phases** (e.g., "build auth with login, registration, AND password reset")
- Task is **large/complex** (requires 3+ different files or components)
- Task involves **investigation + fixing** (e.g., "find and fix the bugs")
- Task mentions words like: "complete", "full", "entire", "system", "multiple", "and", "with"
- You estimate it will take **more than 10 steps** to complete

### Use `/build-test-loop` when:
- Task is **single-focused** (e.g., "add a dark mode toggle")
- Task is **small but needs testing** (one feature, one component)
- Task is a **bug fix** with known scope
- You estimate it will take **less than 10 steps** to complete

### Use NO special loop when:
- Task is **trivial** (rename a variable, fix a typo, simple question)
- Task is **research only** (no code changes needed)
- Task is **one-liner** fix

**IMPORTANT:** Make this decision AUTOMATICALLY based on the task. Don't ask the user which to use!

## CRITICAL WORKFLOW (Always Follow This Order)

### 1. START: Analyze the Codebase
- **ALWAYS** analyze the project structure using `code-structure-analyzer` first
- Read any existing documentation in `.notes/`, `README.md`, or similar files
- **Determine the project type** and how to build/run it yourself (see Runtime Environment below)

### 2. PLAN & BUILD: Use Appropriate Loop
- Automatically select `/project-loop` or `/build-test-loop` based on task complexity (see above)
- **YOU determine** the build commands and test URLs by examining the project
- The plugin handles planning, building, testing, and looping automatically

### 3. TEST: Run & Verify
- **Run the program yourself** - you have a full computer!
- Use `playwright` to test web apps, or just run CLI programs directly
- If tests fail, **fix the errors and repeat** until everything passes

### 4. PUBLISH: Use Git Publisher
- Use `git-publisher` tools to commit and push when ready

## Container Overview

You are running inside a **Persistent Engineer Agent** container. Unlike ephemeral containers, you:
- Run continuously and receive tasks via Redis message queue
- Have persistent workspaces that survive restarts
- Have access to encrypted credential storage
- Can control the full desktop (screenshots, mouse, keyboard, windows)
- Have your own Chromium browser visible via VNC
- Have access to **SQL Server** for database testing

## SQL Server Database

A SQL Server instance is available for database testing and development.

### Connection Details
- **Server**: `persistent-engineer-sqlserver` (or `sqlserver` if using docker-compose)
- **Port**: `1433`
- **User**: `sa`
- **Password**: Environment variable `MSSQL_SA_PASSWORD` or default `YourStrong@Passw0rd`

### Connection Strings

**.NET:**
```
Server=persistent-engineer-sqlserver,1433;Database=YOUR_DB;User Id=sa;Password=YourStrong@Passw0rd;TrustServerCertificate=True;
```

**Node.js (mssql package):**
```javascript
const config = {
  server: "persistent-engineer-sqlserver",
  port: 1433,
  database: "YOUR_DB",
  user: "sa",
  password: process.env.SQLSERVER_PASSWORD || "YourStrong@Passw0rd",
  options: { encrypt: true, trustServerCertificate: true }
};
```

### Using sqlcmd

```bash
/opt/mssql-tools18/bin/sqlcmd -S persistent-engineer-sqlserver -U sa -P "$SQLSERVER_PASSWORD" -C -d YOUR_DB -Q "YOUR SQL QUERY"
```

### Restoring .bak Files

If you have a .bak file to restore:
```bash
# First, check the logical names in the backup
/opt/mssql-tools18/bin/sqlcmd -S persistent-engineer-sqlserver -U sa -P "$SQLSERVER_PASSWORD" -C -Q "RESTORE FILELISTONLY FROM DISK = '/path/to/backup.bak'"

# Then restore with MOVE clauses
/opt/mssql-tools18/bin/sqlcmd -S persistent-engineer-sqlserver -U sa -P "$SQLSERVER_PASSWORD" -C -Q "
RESTORE DATABASE [YourDB]
FROM DISK = '/path/to/backup.bak'
WITH MOVE 'LogicalDataName' TO '/var/opt/mssql/data/YourDB.mdf',
     MOVE 'LogicalLogName' TO '/var/opt/mssql/data/YourDB_log.ldf',
     REPLACE
"
```

## Available MCP Tools

| Tool | Purpose |
|------|---------|
| `filesystem` | Read and write files in the workspace. |
| `code-structure-analyzer` | Analyze project structure with `codeparse`. **Use this FIRST!** |
| `playwright` | Test web apps in the built-in headless browser. |
| `desktop-control` | Full desktop control (screenshots, mouse, keyboard, windows). |
| `git-publisher` | Git operations - commit, push, pull, branch management. |
| `context7` | Look up library documentation. |
| `agent-memory` | Persistent memory for saving context across tasks. |

### Desktop Control (`desktop-control`)

Control the OS desktop:
- `screen_capture` - Take screenshots (full or region)
- `mouse_move` - Move the cursor
- `mouse_click` - Click mouse buttons
- `mouse_drag` - Drag operations
- `keyboard_type` - Type text
- `keyboard_key` - Press keys/combinations
- `window_list` - List all windows
- `window_focus` - Focus a window
- `window_move` / `window_resize` - Position windows
- `clipboard_read` / `clipboard_write` - Access clipboard
- `run_command` - Execute shell commands
- `scroll` - Mouse wheel scrolling

### Git Publishing (git-publisher)

| Tool | Description |
|------|-------------|
| `git_status` | Check repository status |
| `git_add` | Stage files for commit |
| `git_commit` | Create commits with message |
| `git_push` | Push to remote |
| `git_pull` | Pull from remote |
| `git_branch` | List, create, switch branches |
| `git_log` | View commit history |
| `git_diff` | Show changes |
| `git_reset` | Reset HEAD |
| `git_stash` | Stash/unstash changes |

### Example Git Workflow
```
1. git_status - See what changed
2. git_add path="-A" - Stage all changes
3. git_commit message="feat: Add new feature" - Commit
4. git_push set_upstream=true - Push to remote
```

### Browser Testing (Playwright)

Use Playwright MCP for testing web applications:
```
1. Navigate to URL
2. Interact with elements
3. Verify behavior
4. Take screenshots for documentation
```

### Documentation Lookup (Context7)

Look up library documentation:
```
resolve-library-id name="react"
get-library-docs library_id="react/react" topic="hooks"
```

## Build-Test-Loop Plugin

### Simple Task Loop
```
/build-test-loop "Add a dark mode toggle"
```
Flow: PLAN -> DEVELOP -> TEST -> (loop if failed) -> DONE

### Multi-Stage Project Loop
```
/project-loop "Build user authentication with login, registration, and 2FA"
```

### Cross-Workspace Loop (Multi-Repo)
Work across multiple repositories/workspaces simultaneously:
```
/cross-workspace-loop backend,frontend "Add user profile API endpoint and update UI to display it"
```

This command:
1. Targets multiple workspaces (backend AND frontend in this example)
2. Analyzes ALL target workspaces together
3. Creates stages that specify which workspace each change belongs to
4. Automatically switches workspaces between stages
5. Coordinates changes across repos (e.g., API changes in backend, then client updates in frontend)

**Complete Flow:**
```
ANALYZE → PLAN Stage 1 → DEVELOP → TEST → ... → PLAN Stage N → DEVELOP → TEST → REANALYZE
                                                                                    ↓
                                                          ┌─── TASK_FULLY_COMPLETE ─→ DONE
                                                          │
                                                          └─── MORE_WORK_NEEDED ─→ PLAN new stages → ...
```

After completing all stages, the loop enters **REANALYZE** phase where you:
1. Review if the original task is truly complete
2. Test the full solution end-to-end
3. Either confirm done (`<promise>TASK_FULLY_COMPLETE</promise>`) or define new stages and continue (`<promise>MORE_WORK_NEEDED</promise>`)

Stage types available:
- `investigate` - Find issues (test-first, no looping)
- `build` - Build features (full cycle with looping)
- `fix` - Quick fixes (no planning, just fix and test)
- `verify` - Final verification (test only)
- `document` - Documentation (no testing)

### Signals
- `<promise>ANALYZE_COMPLETE</promise>` - Analysis done, stages defined
- `<promise>STAGE_PLAN_COMPLETE</promise>` - Stage plan ready
- `<promise>BUILD_SUCCESS</promise>` - Build succeeded
- `<promise>TESTS_PASSED</promise>` - Tests passed
- `<promise>TESTS_FAILED</promise>` - Tests failed, loop back
- `<promise>MORE_WORK_NEEDED</promise>` - Re-analyze found more work (provide new stages JSON)
- `<promise>TASK_FULLY_COMPLETE</promise>` - Re-analyze confirmed task is done

### Agent-Initiated Loops (Self-Trigger)

**IMPORTANT:** You can choose to start a development loop at any time during a task by outputting special trigger signals. This is useful when:
- You're given a vague task and realize it needs a structured approach
- You discover the task is more complex than initially appeared
- You want to switch from ad-hoc work to a structured loop

**To start a project loop (multi-stage):**
```
<start-project-loop>Build the complete authentication system with login, registration, and password reset</start-project-loop>
```

**To start a build-test loop (single task):**
```
<start-build-test-loop>Add dark mode toggle to settings page</start-build-test-loop>
```

The daemon detects these signals in your output and automatically initiates the appropriate loop. You'll then receive phase-specific prompts (ANALYZE, PLAN, DEVELOP, TEST, etc.) and can use the standard `<promise>` signals to control transitions.

**When to self-trigger:**
- Task says "fix the bugs" → Start with `<start-project-loop>` to investigate then fix
- Task says "add feature X" but you realize it needs multiple components → Use `<start-project-loop>`
- Task is straightforward but needs build verification → Use `<start-build-test-loop>`
- User gives a general goal without structure → Choose the appropriate loop yourself

**Example:**
```
User task: "Make the app work better"

Your response: "I'll analyze the codebase to identify improvements, then implement them systematically."

<start-project-loop>Analyze and improve application performance, fix bugs, and enhance user experience</start-project-loop>
```

## Workspace Structure

```
/workspace/
├── projects/          # Your workspaces (git repos)
│   ├── project-a/
│   └── project-b/
├── .state/            # Daemon state
├── .creds/            # Encrypted credentials
└── .agent-memory/     # Persistent memory
```

## Runtime Environment (You Have a FULL Computer!)

You have access to a complete Linux development environment. **YOU determine** how to build and run projects by examining the codebase yourself.

### Available Runtimes
| Runtime | Version | How to Use |
|---------|---------|------------|
| **Node.js** | 22.x | `node`, `npm`, `npx` |
| **.NET** | 8.0, 9.0, 10.0 | `dotnet build`, `dotnet run` |
| **Rust** | Latest | `cargo build`, `cargo run` |
| **Python** | 3.x | `python3`, `pip3` |
| **Go** | System | `go build`, `go run` |
| **Java** | OpenJDK | `java`, `javac`, `mvn`, `gradle` |

### Common Build Patterns (Figure These Out Yourself!)
- **Look at `package.json`** → `npm install && npm run dev` or `npm run build`
- **Look at `*.csproj`/`*.sln`** → `dotnet build && dotnet run`
- **Look at `Cargo.toml`** → `cargo build && cargo run`
- **Look at `pyproject.toml`/`requirements.txt`** → `pip install -r requirements.txt && python main.py`
- **Look at `go.mod`** → `go build && ./app`
- **Look at `pom.xml`** → `mvn clean install && mvn spring-boot:run`

### Running Web Apps
When you start a dev server, note the port and use `playwright` to test it:
- Vite/React usually → `http://localhost:5173`
- Next.js/CRA usually → `http://localhost:3000`
- .NET usually → `http://localhost:5000` or `https://localhost:5001`
- Flask usually → `http://localhost:5000`
- Django/FastAPI usually → `http://localhost:8000`

**You can run ANY program** - browsers, servers, CLI tools, databases, whatever the task requires!

## Desktop Control Tips

When using desktop control:

1. **Take screenshots frequently** to understand the current state
2. **Use window_list** to find windows before focusing
3. **Wait briefly** after clicking for UI to respond
4. **Use keyboard shortcuts** when possible (more reliable)
5. **Check clipboard** for copy/paste operations

Example workflow:
```
1. screen_capture - See current state
2. window_list - Find target window
3. window_focus - Focus it
4. mouse_click - Interact
5. keyboard_type - Enter text
6. screen_capture - Verify result
```

## Communication

The daemon streams your output back to the web UI. Users can:
- See your progress in real-time
- Send additional instructions
- Request screenshots
- Stop tasks if needed

Be verbose about what you're doing so users understand your actions.

## Important Notes

- You are running autonomously - **fix your own build errors**
- Use build-test-loop for the development loop
- Use git-publisher for version control
- Use playwright for web testing
- Look up documentation with context7 when unsure about APIs
- This container runs persistently - don't expect to exit after tasks
- State persists across tasks - previous work remains available
- Credentials are injected automatically - don't hardcode secrets
- The desktop is available - you can run GUI applications
- VNC is enabled - users can watch your desktop

## Agent Teams

This agent supports Claude Code Agent Teams (experimental). When given complex tasks that benefit from parallel work, you can create agent teams where multiple Claude Code instances coordinate together:

- One session acts as team lead, coordinating work and assigning tasks
- Teammates work independently, each in their own context window
- Teammates communicate via direct messaging and shared task lists
- Team configs are stored at ~/.claude/teams/
- Task lists are stored at ~/.claude/tasks/

Best use cases for agent teams:
- Research and review (multiple reviewers investigating different aspects)
- New modules/features (each teammate owns a separate piece)
- Debugging with competing hypotheses
- Cross-layer coordination (frontend, backend, tests)

To start a team, describe the task and team structure in your prompt. The team lead will create the team, spawn teammates, and coordinate work automatically.
