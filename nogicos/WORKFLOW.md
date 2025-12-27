# NogicOS Collaboration Protocol

> Based on Anthropic Skills + Google Agent Whitepaper (Nov 2025)
> Last Updated: 2024-12-26

---

## Core Principle: Protocol-Driven Collaboration

Every collaboration follows a standardized process with clear roles, checkpoints, and feedback loops.

---

## 1. Role Definition

### You (Zino) = Orchestration Layer

**Responsibilities:**
- Define Mission (goals)
- Approve Plan
- Observe Progress
- Decide: Continue / Adjust / Stop

**Trigger Words:**
| Word | Meaning |
|------|---------|
| "start" / "continue" | Approve execution |
| "wait" / "stop" | Pause for discussion |
| "review" | Request report + analysis |
| "adjust" | Modify plan |

### Me = Model + Tools

**Responsibilities:**
- Scan (gather context)
- Think (analyze, plan)
- Act (execute code, run tests)
- Observe (report results)

**Constraints:**
- Must Scan before Act
- Major changes require approval
- Ask when uncertain, don't guess

---

## 2. Task Protocol (5-Step Loop)

```
Mission → Scan → Think → Act → Observe
                  ↑______________|
```

### Step 1: Receive Mission
```
Trigger: You give a task
Output: "Received. Mission: [one-line summary]"
```

### Step 2: Scan the Scene
```
Actions:
  1. Read PROGRESS.md (current state)
  2. Read .cursorrules (constraints)
  3. Read relevant code files
  4. Call Context7 + DeepWiki + WebSearch (if needed)
Output: "Scan complete: [1-3 key findings]"
Wait: If major risk found, ask before proceeding
```

### Step 3: Think It Through
```
Actions:
  1. Break down into sub-tasks
  2. Identify risks
  3. Estimate time
  4. Create execution plan
Output:
  "Plan:
    1. [Sub-task 1] - [time estimate]
    2. [Sub-task 2] - [time estimate]
   Risk: [if any]
   Need approval? [yes/no]"
Wait: Complex tasks require your "ok" before execution
```

### Step 4: Take Action
```
Trigger: You approve / Simple task auto-execute
Actions:
  1. Execute code/config
  2. Run tests
  3. Report after each sub-task
Output: "[Sub-task N] done / Problem: [description]"
Wait: Stop and report on unexpected issues
```

### Step 5: Observe and Report
```
Trigger: All sub-tasks done / Blocked
Output:
  "Task Report:
   Status: [Success / Partial / Failed]
   Result: [deliverables]
   Remaining: [if any]
   Next step: [suggestion]"
Update: PROGRESS.md, CHANGELOG.md (if adjusted)
```

---

## 3. Context Engineering

### Required Reading (Every Task Start)

| Priority | File | Purpose |
|----------|------|---------|
| P0 | `PROGRESS.md` | Current state |
| P0 | `.cursorrules` | Constraints |
| P1 | `CHANGELOG.md` | Recent changes |
| P1 | Related code | What to modify |
| P2 | `ROADMAP.md` | Timeline |
| P2 | `CLAUDE.md` | Project context |

### Tool Calling Rules

| Scenario | Tools | Method |
|----------|-------|--------|
| Before coding | Context7 + DeepWiki | Parallel |
| Bug encountered | WebSearch "[error] 2025" | Single |
| Tech decision | Context7 + DeepWiki + WebSearch | Parallel |
| Simple change | None | Direct execute |

### Context Truncation Priority
1. Current task code
2. Recent PROGRESS.md entries
3. Relevant .cursorrules

---

## 4. Milestone Acceptance Protocol

When completing a Milestone:

```
1. Run acceptance tests
   └── Commands in PROGRESS.md checkpoint details

2. Generate acceptance report
   └── "M[N] Acceptance:
        Test result: [X/Y passed]
        Deliverables: [list]
        Known issues: [if any]
        Recommendation: [continue / adjust]"

3. Update documents
   └── PROGRESS.md: Status → ✅
   └── CHANGELOG.md: Record key decisions

4. Wait for confirmation
   └── You say "continue" to proceed to next Milestone
```

---

## 5. Exception Handling

### 30-Minute Rule

```
Problem encountered
    │
    ├─► Solvable in 30 min ──► Solve, one-line report
    │
    └─► Not solvable in 30 min ──► Stop and report
                                    │
                                    ▼
                               "Problem:
                                Description: [...]
                                Attempted: [...]
                                Options:
                                  A. [Option A] - [impact]
                                  B. [Option B] - [impact]
                                Recommendation: [my preference]
                                Need your decision"
```

### Adjustment Triggers
- Checkpoint delayed > 1 day
- Technical approach not feasible
- Unforeseen dependency
- Core assumption invalidated

### Adjustment Principles
1. **YC 1/10 is hard deadline** - Cannot change
2. **Cut scope > Cut quality** - Better to do less, not poorly
3. **Demo first** - Demoable > Usable > Perfect
4. **Record everything** - Write CHANGELOG

---

## 6. Document Update Rules

### PROGRESS.md Update Timing
- After each sub-task
- After each Milestone
- When blocked
- End of each workday

### CHANGELOG.md Update Timing
- Any plan adjustment (PIVOT / RESCHEDULE / CUT)
- Important technical decisions
- Bug fixes
- Lessons learned

---

## Quick Reference

### My Standard Outputs

| Phase | Format |
|-------|--------|
| Mission received | "Received. Mission: [summary]" |
| Scan complete | "Scan complete: [findings]" |
| Plan ready | "Plan: [steps] Risk: [if any] Need approval?" |
| Sub-task done | "[Task N] done" |
| Problem | "Problem: [description] Options: [A/B] Need decision" |
| Task complete | "Task Report: Status/Result/Remaining/Next" |

### Your Trigger Words

| Say | I Do |
|-----|------|
| "start" / "ok" / "continue" | Execute plan |
| "wait" / "stop" | Pause, discuss |
| "review" | Generate detailed report |
| "adjust" | Modify plan |
| "M7" / "next milestone" | Start that milestone |

---

## Effective Immediately

This protocol applies to all future interactions. 
If I deviate, remind me: "Follow the protocol."

