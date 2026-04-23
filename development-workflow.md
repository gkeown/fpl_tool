# Development Workflow

Every major change follows a three-phase cycle: **Plan → Code → Review**. No phase is skipped. The review phase loops back to code until the change meets the quality bar defined in the plan.

---

## Phase 1: Plan

**Trigger:** User requests a feature, story, bug fix, or refactor.

**Process:**
1. A planning agent produces a full specification before any code is written.
2. The spec is saved as a plan file and presented to the user for approval.

**Spec contents:**
- **Objective** — What problem this solves, in one sentence. Take a note of the exact prompt the user has given along with the one sentence summary.
- **Scope** — What is in scope and what is explicitly out of scope.
- **Files to create or modify** — Every file that will be touched, with a summary of the change.
- **API changes** — New or modified endpoints, request/response schemas, status codes.
- **Database changes** — New migrations, schema changes, index additions.
- **Frontend changes** — New routes, components, state changes, UI behaviour.
- **Infrastructure changes** — Terraform resources, environment variables, CI workflows.
- **Acceptance criteria** — Concrete, testable conditions that define "done". These are what the review phase evaluates against.
- **Test plan** — What tests will be written or updated, and what they cover.
- **Risks and trade-offs** — Anything the user should be aware of before approving.

**Exit criteria:** User approves the plan (or revises it until approved). No code is written until the plan is approved.

---

## Phase 2: Code

**Trigger:** Plan is approved.

**Process:**
1. Implementation follows the plan spec exactly. Deviations from the plan are flagged to the user before proceeding.
2. For changes that span multiple independent areas (e.g., backend + frontend + infrastructure), parallel coding agents may be used in isolated worktrees.
3. All code follows the standards in `CLAUDE.md`. The plan does not override `CLAUDE.md` — if they conflict, raise it before coding.
4. Tests are written alongside the implementation, not after.

**What gets committed:**
- Application code changes
- Database migrations
- Test additions or updates
- Configuration or infrastructure changes

**What does not get committed until review passes:**
- Nothing is committed prematurely. Code is written and ready for review before any commit.

---

## Phase 3: Review

**Trigger:** Code phase is complete.

**Process:**
1. A review agent reads all changes and evaluates them against:
   - The acceptance criteria from the plan
   - The coding standards in `CLAUDE.md`
   - General best practices (security, performance, maintainability)
   - Test coverage and quality
2. The review produces a structured report:

### Review report format

```
## Review: [Change Title]

### Acceptance Criteria
- [ ] Criterion 1 — PASS / FAIL (explanation)
- [ ] Criterion 2 — PASS / FAIL (explanation)

### Code Quality
- **Issues found:** (list of specific problems with file:line references)
- **Suggestions:** (optional improvements, clearly marked as non-blocking)

### Security
- Any new attack surface or vulnerability introduced?

### Performance
- Any N+1 queries, missing indexes, unnecessary re-renders, or large payloads?

### Test Coverage
- Are the acceptance criteria covered by tests?
- Are edge cases tested?

### Verdict: APPROVED / CHANGES REQUESTED
```

3. If **CHANGES REQUESTED**: the report lists specific issues. Code phase resumes to address them. Then review runs again. This loop continues until the review verdict is **APPROVED**.
4. If **APPROVED**: changes are committed.

---

## The Loop

```
User Request
    │
    ▼
┌─────────┐
│  PLAN   │◄──── User revises
│         │
└────┬────┘
     │ User approves
     ▼
┌─────────┐
│  CODE   │◄──── Review requests changes
│         │
└────┬────┘
     │ Implementation complete
     ▼
┌─────────┐
│ REVIEW  │
│         │──── Changes requested? ──► Back to CODE
└────┬────┘
     │ Approved
     ▼
  COMMIT
```

---

## Exceptions

- **Trivial changes** (typo fixes, config value changes, single-line bug fixes) do not require the full cycle. Use judgement — if the change touches logic, it gets the cycle.
- **Urgent hotfixes** may compress the cycle but must still have a review pass before merging to main.
- **The user can override** any phase. If the user says "skip the plan" or "commit without review", comply — but note the deviation.

---

## Principles

- **The plan is a contract.** It sets expectations for what will be built. Surprises in the code phase mean the plan was incomplete.
- **The review is impartial.** It evaluates the code as written, not the intent behind it. A good plan with poor implementation still fails review.
- **The loop converges.** Each review cycle should have fewer issues than the last. If the same issues recur, the root cause is in the approach, not the fix — escalate to the user.
- **Nothing is personal.** Review findings are about the code, not the coder. The goal is the best possible solution.
