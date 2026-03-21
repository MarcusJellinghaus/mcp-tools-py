---
allowed-tools: Bash(gh issue create *)
workflow-stage: issue-discussion
suggested-next: discuss -> issue_update -> issue_approve
---

# Create GitHub Issue

Based on our prior discussion, create a GitHub issue.

**Instructions:**
1. Extract the issue title and body from the conversation context
2. Use a clear, descriptive title
3. Include relevant details from our discussion in the body
4. Use markdown formatting for better readability

**Create the issue using:**
```bash
gh issue create --title "TITLE" --body "BODY"
```

If no prior discussion context is found, respond: "No discussion context found. Please discuss the feature or bug first before creating an issue."
