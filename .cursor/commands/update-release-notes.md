# Update Release Notes Workflow for Fabrinetes repo

*****do the following only for Fabrinetes repo*****

## Overview
This command creates/updates release notes documentation for the phy10gbaser project.

**IMPORTANT**: This command does NOT create git tags and does NOT commit changes. This is used to accumulate updates of release notes. Use this command to iteratively build release notes before committing or tagging.

## Workflow

### 1. Determine Version
- Check current tags: `git tag -l`
- Determine next version (e.g., V1.0, V1.1, V2.0)
- Ask user for version number if not provided

### 2. Review Changes Since Last Tag
- Find last tag: `git describe --tags --abbrev=0` (or use V1.0 if first tag)
- Review commits since last tag: `git log <last-tag>..HEAD --oneline`
- Review uncommitted changes: `git status --short` and `git diff --name-status`
- **Note**: This includes both committed and uncommitted changes to accumulate all updates
- Summarize changes for release notes

### 3. Create/Update Release Notes
- Path: `Fabrinetes/release_notes/V[VERSION].md`
- **Read current document**: If file exists, read the current release notes file to preserve existing content
- If file exists: Update with new changes (merge with existing content)
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

## Release Notes Path

- **Location**: `Fabrinetes/release_notes/`
- **File naming**: `V[VERSION].md` (e.g., `V1.0.md`, `V1.1.md`)
- **Configuration**: Path stored in `phy10gbaser.hdlforge.json` under `settings.release_notes_path`

## Execution Steps

1. **Check current state**:
   - List existing tags
   - Check if release notes file exists for version
   - Review commits since last tag
   - Review uncommitted changes

2. **Create/update release notes**:
   - Read current release notes file if it exists (to preserve existing content)
   - Read template from `release_notes/README.md`
   - Analyze git commits since last tag
   - Analyze uncommitted changes (if any)
   - Create or update `V[VERSION].md` file (merge new changes with existing content)
   - **CRITICAL**: Include Git Tag name in header: `**Git Tag:** V[VERSION]`
   - Include all relevant changes

3. **Review release notes**:
   - Display release notes file path to user
   - Ask user to review the content
   - Wait for user confirmation
   - Allow user to edit if needed

## User Interaction

After reviewing changes, ask user:
- Confirm version number
- **Review release notes file** (display path and wait for confirmation)
- Confirm release notes content is correct

**CRITICAL - NO GIT OPERATIONS**: 
- **This command does NOT create git tags** - Use `tag-with-release-notes` command for tagging
- **This command does NOT commit changes** - File is created/updated in working directory only
- **This is purely for accumulating updates** - Build release notes iteratively before committing
- Release notes file will be created/updated in the working directory
- User must manually commit the release notes file when ready
- User must use `tag-with-release-notes` command when ready to tag and commit

## Notes

- Release notes are project-specific (phy10gbaser)
- **This is a read-only git operation** - No tags created, no commits made
- **Purpose**: Accumulate and document updates iteratively
- Release notes file can be edited manually after creation
- Use `tag-with-release-notes` command when ready to tag and commit
- This command is safe to run multiple times to update release notes as development progresses

