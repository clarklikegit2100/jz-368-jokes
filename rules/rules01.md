# Project Development Rules

These rules must be followed throughout the development process to maintain code quality, version traceability, and full control over repository changes.

## Pull Request (PR) Policy

- **Avoid creating Pull Requests (PRs) whenever possible**, especially for minor changes, small fixes, or routine updates.
- Prefer making changes directly in the designated working branch without creating unnecessary PRs.
- If a PR is absolutely necessary, its source branch must follow the naming convention:
  - **Allowed:** `mybranch/<descriptive-name>`
  - **Not allowed:** `claude/<descriptive-name>`
- Do not create a PR without my explicit approval.

## Authorship and Co-Author Policy

- **Do not add `Claude` as a co-author** in any commit or Pull Request by default.
- Do not automatically include attribution such as `Co-authored-by: Claude` in commit messages, PR descriptions, or other Git metadata.
- Exceptions are permitted only when I have explicitly reviewed and approved the attribution.
- All authorship and attribution decisions must remain under my control.

## Version Tracking and Changelog Management

- Maintain a `CHANGELOG.md` file in the project's root directory.
- Update this file whenever changes are made to the project, including changes that have not yet been released.
- Each version entry should document:
  - **Version information:** Version number and release date, when applicable.
  - **New features:** Newly implemented functionality and improvements.
  - **Modifications:** Changes to existing functionality, architecture, or behavior.
  - **Bug fixes:** Issues resolved in the current version.
  - **Known issues:** Newly discovered bugs, limitations, and unresolved problems.
  - **Future improvements:** Recommended refinements, pending tasks, and issues to address in subsequent versions.
- Keep changelog entries clear, concise, and organized chronologically, with the latest version appearing first.
- Ensure that unresolved issues are carried forward and tracked until they are addressed.

## Git Commit and Push Policy

- **Never execute `git commit` or `git push` without my explicit authorization.**
- Do not automatically commit, push, merge, or publish any changes to GitHub.
- You may modify local project files and prepare changes for review, but all changes must remain local until I approve them.
- After completing a task:
  1. Summarize all modified, added, and deleted files.
  2. Explain the main changes and their purpose.
  3. Report any outstanding issues, risks, or required follow-up actions.
  4. Update `CHANGELOG.md` accordingly.
  5. Leave the final review, commit, and push operations to me.

**Final Principle:** All repository changes must remain under my supervision. AI assistants may implement and document changes locally, but must not independently create PRs, assign AI co-authorship, commit, push, or merge code without my explicit approval.



## Git branches (all GitHub projects)

- Work only on the `main` branch. Do not create new branches (local or on GitHub), even when a tool or
  harness suggests one (e.g. a `claude/` branch).