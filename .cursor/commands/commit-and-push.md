review all files changed using git diff
group files by LOGICAL SUBJECT (not by file count)
- One logical feature/refactoring = One commit (even if it touches many files)
- Multiple unrelated changes = Multiple commits
- Example: "Refactor struct to individual signals" = 1 commit (touches 6 files)
- Example: "Fix bug A" + "Add feature B" = 2 commits (even if same file)
create 1 commit per LOGICAL SUBJECT with 1 liner commit messages
push