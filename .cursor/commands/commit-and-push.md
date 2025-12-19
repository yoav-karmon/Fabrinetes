# Commit and Push Workflow for Fabrinetes


*****do the follwing only for Fabrinetes repo*****
## Review Phase
1. Review all changed files using `git diff`
2. Review all untracked files
3. Group files by **logical subject** (not by file count)

## Commit Organization Rules
- **Large files and tarballs**: Use Git LFS
- **One logical feature/refactoring = One commit** (even if it touches many files)
- **Multiple unrelated changes = Multiple commits**
- Examples:
  - "Refactor struct to individual signals" = 1 commit (may touch 6 files)
  - "Fix bug A" + "Add feature B" = 2 commits (even if in the same file)

## Commit Creation
- Create one commit per logical subject
- Use concise one-line commit messages
- List commits in the following format:
```
<number>. <commit message>
```

For each commit, list all affected files relative to the repository root.

## Confirmation
After listing all commits, ask the user if they want to:
- Make changes to the commit plan
- Push and commit all commits using: git push ssh://git@github.com/yoav-karmon/Fabrinetes.git
- Push and commit a specific commit (by number) using: 

`git push ssh://git@github.com/yoav-karmon/Fabrinetes.git`


