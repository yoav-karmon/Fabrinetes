# Tag and Release Notes Workflow for Fabrinetes repo

*****do the following only for Fabrinetes repo*****

## Overview
This command creates a git tag and creates/updates release notes documentation for the phy10gbaser project.

## Workflow

### 0. Pre-flight Checks
- **CRITICAL**: Check for uncommitted changes: `git status --short`
  - If there are uncommitted changes, **REJECT** the command and inform user they must commit or stash changes first
- **CRITICAL**: Check for unpushed commits: `git log origin/$(git branch --show-current)..HEAD`
  - If there are unpushed commits, **REJECT** the command and inform user they must push commits first
- Only proceed if working directory is clean and all commits are pushed

### 1. Determine Version
- Check current tags: `git tag -l`
- Determine next version (e.g., V1.0, V1.1, V2.0)
- Ask user for version number if not provided

### 2. Review Changes Since Last Tag
- Find last tag: `git describe --tags --abbrev=0` (or use V1.0 if first tag)
- Review commits since last tag: `git log <last-tag>..HEAD --oneline`
- Summarize changes for release notes

### 3. Create/Update Release Notes
- Path: `Fabrinetes/release_notes/V[VERSION].md`
- **Read current document**: If file exists, read the current release notes file to preserve existing content
- **Note**: The release notes file may already contain accumulated changes from using the `update-release-notes` command
- If file exists: Update with new changes (merge with existing accumulated content)
- If file doesn't exist: Create new file using template from README.md
- **CRITICAL**: Must include Git Tag name in the header: `**Git Tag:** V[VERSION]`
- Include:
  - Git Tag name in header (e.g., `**Git Tag:** V1.0`)
  - Summary of changes
  - Added features
  - Changed behavior
  - Fixed issues
  - Known issues (if any)
  - Migration guide (if needed)
  - Related commits
  - Files changed

### 4. Review Release Notes
- **CRITICAL**: Ask user to review the release notes file before proceeding
- Display the release notes file path: `Fabrinetes/release_notes/V[VERSION].md`
- Wait for user confirmation that they have reviewed and approved the content
- Allow user to make edits if needed
- Only proceed to tagging after user confirms release notes are correct

### 5. Create Git Tag
- Tag name: `V[VERSION]` (e.g., V1.0, V1.1)
- Tag message: Short summary (1-2 lines) matching release notes summary
- Use annotated tag: `git tag -a V[VERSION] -m "tag message"`
- Point to current HEAD commit

### 6. Push Tag
- Push tag to remote: `git push origin V[VERSION]`

## Release Notes Template

When creating a new release notes file, use this structure:

```markdown
# Release Notes - V[VERSION]

**Release Date:** YYYY-MM-DD  
**Git Tag:** V[VERSION]  
**Commit:** [commit-hash]

**IMPORTANT**: The Git Tag field must match the actual git tag name (e.g., V1.0, V1.1, V2.0)

## Summary
Brief one-paragraph summary of this release.

## Added
- New feature 1
- New feature 2

## Changed
- Modified behavior of feature X
- Updated interface Y

## Fixed
- Bug fix description
- Issue resolution

## Known Issues
- Known issue 1: Description and workaround (if available)
- Known issue 2: Description and expected fix version (if known)

## Migration Guide
### Breaking Changes
- Change 1: How to migrate
- Change 2: Steps to update

### Deprecations
- Deprecated feature: Replacement guidance

## Technical Details
[Optional: Code examples, implementation details]

## Related Commits
- commit-hash - Commit message
- commit-hash - Commit message

## Files Changed
- path/to/file1.sv
- path/to/file2.sv
```

## Tag Message Guidelines

- **Keep it short**: 1-2 lines maximum
- **Match summary**: Should align with release notes summary
- **Be descriptive**: Key change or milestone
- **Examples**:
  - Good: "network index now match cable index"
  - Good: "Add idle counter requiring 255 idles before lock"
  - Bad: "Update"

## Release Notes Path

- **Location**: `Fabrinetes/release_notes/`
- **File naming**: `V[VERSION].md` (e.g., `V1.0.md`, `V1.1.md`)
- **Configuration**: Path stored in `phy10gbaser.hdlforge.json` under `settings.release_notes_path`

## Execution Steps

0. **Pre-flight validation**:
   - Check for uncommitted changes: `git status --short`
   - **REJECT if uncommitted changes exist** - User must commit or stash first
   - Check for unpushed commits: `git log origin/$(git branch --show-current)..HEAD`
   - **REJECT if unpushed commits exist** - User must push commits first
   - Abort command if validation fails

1. **Check current state**:
   - List existing tags
   - Check if release notes file exists for version
   - Review commits since last tag

2. **Create/update release notes**:
   - Read current release notes file if it exists (to preserve existing accumulated content)
   - **Note**: File may already contain changes accumulated via `update-release-notes` command
   - Read template from `release_notes/README.md`
   - Analyze git commits since last tag
   - Create or update `V[VERSION].md` file (merge new changes with existing content)
   - **CRITICAL**: Include Git Tag name in header: `**Git Tag:** V[VERSION]`
   - Include all relevant changes

3. **Review release notes**:
   - Display release notes file path to user
   - Ask user to review the content
   - Wait for user confirmation before proceeding
   - Allow user to edit if needed

4. **Create git tag**:
   - Create annotated tag with short message
   - Tag current HEAD commit
   - Verify tag was created

5. **Push to remote**:
   - Push tag to origin
   - Confirm push succeeded

## User Interaction

After reviewing changes, ask user:
- Confirm version number
- Confirm tag message
- **Review release notes file** (display path and wait for confirmation)
- Confirm release notes content is correct
- Proceed with tag creation and push

**Important**: The release notes file must be reviewed and approved by the user before creating the tag. Do not proceed to tag creation until the user explicitly confirms the release notes are correct.

## Notes

- Release notes are project-specific (phy10gbaser)
- Tags are repository-wide
- Always use annotated tags (`-a` flag) for better metadata
- Release notes should be committed before or with the tag
- Tag message should be concise; details go in release notes
- **Pre-flight validation**: Command will reject if there are uncommitted changes or unpushed commits
- User must have a clean working directory and all commits pushed before tagging

