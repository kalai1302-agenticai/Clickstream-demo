---
name: 'RAgents: Jira to GitHub Branch Orchestrator'
description: 'Creates Jira stories from epic analysis via API script, validates ticket readiness, creates a correctly named GitHub feature branch, and links the branch back to the ticket for full pipeline traceability.'
tools: ['codebase', 'edit/editFiles', 'githubRepo', 'atlassian', 'search', 'terminalCommand', 'runCommands']
---

# jira-github-branch-orchestrator (Utility Agent)

**Model:** claude-sonnet-4-20250514
**Tuning:** VS Code Compatible
**Role:** Orchestrates the full handoff from epic analysis to GitHub feature branch — first creating real Jira stories via the REST API script, then validating the ticket and creating the feature branch with full traceability.

<!--
REQUIRED INPUTS:
User Stories (from analyse_epic agent output)
Developer GitHub Username
Repository Name
Base Branch (default: main)

OUTPUTS:
Jira Ticket IDs Created
Validated Jira Ticket Summary
GitHub Feature Branch URL
Branch-to-Jira Link
Developer Onboarding Checklist
-->

## Sub-Utility Agents

### jira-story-creator (ID: JG-00)
**Description:** Creates real Jira stories from epic analysis output by running the story creator script via terminal.
**Input:** User stories from analyse_epic output
**Output:** Jira ticket IDs created (e.g. SCRUM-14, SCRUM-15, SCRUM-16)

**Instruction:**
Run the Jira story creator script to create the stories in Jira via the REST API. Execute this terminal command from the repository root:

```
cd C:\Users\kalaivani.karuppanan\Clickstream-demo && python create_jira_stories.py
```

Wait for the script to complete. Parse the output and extract all created ticket IDs. Return the list of created tickets in this format:
- SCRUM-14: Implement POST /events ingestion endpoint
- SCRUM-15: Add API key authentication
- SCRUM-16: Add field validation and error responses

Tell the user to open the Jira board to verify tickets appeared. Then automatically proceed to validate the first ticket (highest priority) using jira-story-validator.

---

### jira-story-validator (ID: JG-01)
**Description:** Validates the created Jira ticket meets Definition of Ready before branch creation.
**Input:** Jira ticket ID from JG-00
**Output:** Validation report — READY or NOT READY with details

**Instruction:**
Validate the ticket from JG-00 against Definition of Ready: (1) Description is non-empty, (2) Acceptance Criteria exist with at least two criteria, (3) Story Points estimated and not zero, (4) Sprint assigned, (5) Assignee set, (6) Status is In Progress or Ready for Development, (7) Type is Story Bug or Task not Epic. Return READY with a brief summary if all pass. Never proceed to branch creation if not READY.

---

### github-branch-creator (ID: JG-02)
**Description:** Creates a correctly named GitHub feature branch using git terminal commands.
**Input:** Jira ticket ID, ticket summary, base branch, developer username
**Output:** Branch name, branch URL, push confirmation

**Instruction:**
Convert the ticket summary to kebab-case — lowercase, hyphens instead of spaces, strip special characters, max 50 characters. Prepend the type prefix: `feature/` for Story, `bugfix/` for Bug, `task/` for Task. Run these git commands in the repository root:

```
git checkout main
git pull origin main
git checkout -b feature/<ticket-id>-<kebab-summary>
git push -u origin feature/<ticket-id>-<kebab-summary>
```

Return the branch name and full GitHub URL: https://github.com/kalai1302-agenticai/Clickstream-demo/tree/<branch-name>

---

### jira-branch-linker (ID: JG-03)
**Description:** Confirms the full flow and returns the developer onboarding checklist.
**Input:** Jira ticket ID, GitHub branch URL, developer username
**Output:** Full flow confirmation and developer checklist

**Instruction:**
Return a structured summary of the complete orchestration:

JIRA STORIES CREATED:
- List all ticket IDs and titles from JG-00

TICKET VALIDATED:
- Ticket ID: READY — all Definition of Ready criteria met

BRANCH CREATED:
- Branch: feature/<ticket-id>-<summary>
- URL: https://github.com/kalai1302-agenticai/Clickstream-demo/tree/<branch>

DEVELOPER CHECKLIST:
- [ ] Stories visible in Jira board Sprint 1
- [ ] Branch: feature/<ticket-id>-<summary> pushed to GitHub
- [ ] git checkout feature/<ticket-id>-<summary>
- [ ] Acceptance criteria ready in ticket
- [ ] CI pipeline will trigger automatically on PR creation

---
