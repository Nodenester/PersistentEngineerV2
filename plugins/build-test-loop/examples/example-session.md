# Example Session: Building a Dark Mode Toggle

This example shows a complete build-test-loop session for adding a dark mode toggle.

## Starting the Loop

**User:**
```bash
/build-test-loop "Add a dark mode toggle button in the settings page. It should switch between light and dark themes, persist the choice in localStorage, and apply the theme on page load." \
  --build-command "npm run build" \
  --test-url "http://localhost:3000/settings"
```

**Claude:**
```
🚀 Build-Test-Loop started!

Phase: PLAN
Task: Add a dark mode toggle button in the settings page...
Build: npm run build
Test URL: http://localhost:3000/settings
Max iterations: 50

The loop will now begin. The Stop hook will control phase transitions automatically.
```

[Claude attempts to stop → Stop hook blocks and injects PLAN prompt]

---

## Phase 1: PLAN (Iterations 1-3)

**Stop Hook → Claude:**
```
**PLANNING PHASE**

Create a detailed implementation plan for this task:

Add a dark mode toggle button in the settings page...

Your plan should include:
1. Required files and their purposes
2. Key functions/components to implement
3. Dependencies needed
4. Build process verification steps
5. What needs to be tested in the browser

When your plan is complete and documented, output: <promise>PLAN_COMPLETE</promise>
```

**Claude's Planning Work:**

*Iteration 1:*
- Analyzes the codebase
- Identifies settings page component
- Plans CSS variables approach

*Iteration 2:*
- Details localStorage API usage
- Plans React useState hook for theme
- Identifies useEffect for persistence

*Iteration 3:*
- Documents testing approach
- Creates implementation checklist
- Outputs: `<promise>PLAN_COMPLETE</promise>`

**Stop Hook Response:**
```
✅ Planning complete! Moving to DEVELOP phase...
```

---

## Phase 2: DEVELOP (Iterations 4-15)

**Stop Hook → Claude:**
```
**DEVELOPMENT PHASE** (Attempt #1)

Implement the planned solution and get it to build successfully.

Build command: `npm run build`

Work iteratively:
1. Implement/fix code
2. Run the build command
3. If build fails, analyze errors and fix
4. Repeat until build succeeds

When the build succeeds, output: <promise>BUILD_SUCCESS</promise>
```

**Claude's Development Work:**

*Iteration 4-5:*
- Adds CSS variables to App.css
- Creates theme context
- Build fails: TypeScript error in context

*Iteration 6-7:*
- Fixes TypeScript types
- Adds theme toggle button to Settings component
- Build fails: Missing import

*Iteration 8-9:*
- Fixes imports
- Implements localStorage logic
- Build fails: ESLint error (unused variable)

*Iteration 10-11:*
- Fixes ESLint issues
- Adds useEffect for theme application
- Build succeeds!
- Outputs: `<promise>BUILD_SUCCESS</promise>`

**Stop Hook Response:**
```
✅ Build succeeded! Moving to WEB TESTING phase...
```

---

## Phase 3: TEST (Iterations 12-14) - First Attempt

**Stop Hook → Claude:**
```
**WEB TESTING PHASE**

The build succeeded! Now verify the implementation works correctly in the browser.

Test URL: http://localhost:3000/settings

Steps:
1. Start the development server if needed
2. Use browser automation tools to test the functionality
3. Verify all requirements from the original task are met
4. Document what you tested

If ALL tests pass, output: <promise>TESTS_PASSED</promise>
If ANY test fails, output: <promise>TESTS_FAILED</promise> and describe what failed
```

**Claude's Testing Work:**

*Iteration 12:*
- Starts dev server
- Navigates to http://localhost:3000/settings
- Takes screenshot

*Iteration 13:*
- Finds dark mode toggle button
- Clicks it
- Theme switches to dark!

*Iteration 14:*
- Refreshes page
- **BUG FOUND:** Theme doesn't persist - reverts to light mode
- Outputs: `<promise>TESTS_FAILED</promise>`

  **Test failure:** Dark mode preference not persisting across page refreshes. The theme reverts to light mode after reload.

**Stop Hook Response:**
```
❌ Tests failed! Looping back to DEVELOP phase (failure #1)...
```

---

## Phase 2: DEVELOP (Iterations 15-20) - Second Attempt

**Stop Hook → Claude:**
```
**DEVELOPMENT PHASE** (Attempt #2)

Implement the planned solution and get it to build successfully.

Build command: `npm run build`
```

**Claude's Development Work:**

*Iteration 15-16:*
- Analyzes the issue: useEffect not running on mount
- Adds dependency array to useEffect
- Adds initial theme load from localStorage

*Iteration 17-18:*
- Refactors theme initialization logic
- Ensures localStorage is checked before first render
- Build succeeds!
- Outputs: `<promise>BUILD_SUCCESS</promise>`

**Stop Hook Response:**
```
✅ Build succeeded! Moving to WEB TESTING phase...
```

---

## Phase 3: TEST (Iterations 19-22) - Second Attempt

**Claude's Testing Work:**

*Iteration 19:*
- Navigates to settings page
- Verifies toggle button exists

*Iteration 20:*
- Clicks toggle → Dark mode activates
- Checks localStorage → `theme: "dark"` stored correctly

*Iteration 21:*
- Refreshes page
- **SUCCESS:** Dark mode persists!
- Clicks toggle again → Light mode
- Checks localStorage → `theme: "light"`

*Iteration 22:*
- Refreshes again → Light mode persists
- Tests complete!
- Outputs: `<promise>TESTS_PASSED</promise>`

**Stop Hook Response:**
```
🎉 All tests passed! Build-Test-Loop completed successfully!
```

[Loop exits successfully]

---

## Final State

`.claude/build-test-loop.local.md`:
```yaml
---
enabled: false
phase: "done"
iteration: 22
max_iterations: 50
build_command: "npm run build"
test_url: "http://localhost:3000/settings"
original_prompt: "Add a dark mode toggle button..."
develop_failures: 1
---
```

## Summary

- **Total iterations:** 22
- **Phases:**
  - PLAN: 3 iterations
  - DEVELOP (1st attempt): 8 iterations → Build success
  - TEST (1st attempt): 3 iterations → Tests failed
  - DEVELOP (2nd attempt): 6 iterations → Build success
  - TEST (2nd attempt): 4 iterations → Tests passed ✅
- **Develop-Test cycles:** 1 (one failure, one success)
- **Result:** Feature fully implemented and verified!

## Key Takeaways

1. **Planning prevented scope creep** - Clear plan kept implementation focused
2. **Build loop caught errors early** - TypeScript, ESLint issues fixed before testing
3. **Browser testing found real bug** - Persistence issue only visible in browser
4. **Feedback loop worked** - Failed test triggered fix-and-retest cycle
5. **Automated verification** - No manual intervention needed

The whole process was autonomous from start to finish!
