# Commit and Push Workflow for Fabrinetes


*****do the follwing only for Fabrinetes repo*****
## pre commit: Review Phase
1. Review all changed files using `git diff`
2. Review all untracked files
3. Group files by **logical subject** (not by file count)

## Commit Organization Rules
- **Large files and tarballs**: Use Git LFS
- **One logical feature/refactoring = One commit** (even if it touches many files)
- **Multiple unrelated changes = Multiple commits**
- offer untracked file ignore or add
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

## Commit Confirmation 
After listing all commits, ask the user to selection option by number (in this order):
1. commit all commits (always first option)
2. Make changes to the commit plan and loop backhere
3. (other option you think shoule be here) + and loop backhere



## push Confirmation 
After listing all commits, ask the user to selection option by number (in this order):
1. Push all commits to both servers: `git push origin main && git push github main`
2. Push to local server only: `git push origin main`
3. Push to open source only: `git push github main`
4. (other option you think should be here) + and loop back here

### Remotes
| Name | URL | Description |
|------|-----|-------------|
| `origin` | GitLab (internal) | Local/internal server |
| `github` | `ssh://git@github.com/yoav-karmon/Fabrinetes.git` | Open source (GitHub) |


## post commit or push
- update fpga repo pointer (this is submodule)





