# Enhanced ContainerInfo Member Processing Plan

## Overview
Refactor ContainerInfo to use a more robust member processing system where each member returns `(value, resolved_value, errors)` and has its own processing function.

## Task List

### Phase 1: Core Infrastructure
1. **Create MemberResult dataclass** - Define a dataclass to hold `(value, resolved_value, errors)` for each member
2. **Create member processing functions** - Implement individual processing functions for each member type
3. **Refactor ContainerInfo.__init__** - Update initialization to use the new member processing system
4. **Update validation system** - Modify validate_paths to work with the new member processing results

### Phase 2: Member-Specific Processing
5. **Process config file member** - Implement processing for config file (resolve + verify existence)
6. **Process working directory member** - Implement processing for working directory (resolve + verify existence)
7. **Process dockerfile member** - Implement processing for dockerfile (resolve + verify existence)
8. **Process package list member** - Implement processing for package list (resolve + verify existence)
9. **Process tarball member** - Implement processing for tarball (resolve + verify existence)
10. **Process mount members** - Implement processing for mounts (resolve + verify existence)
11. **Process X11 path member** - Implement processing for X11 path (resolve + verify existence)

### Phase 3: Integration and Testing
12. **Update all command files** - Modify run, build, commit, restore to use new member processing
13. **Test all commands** - Verify all commands work correctly with new system
14. **Update error handling** - Ensure error messages are clear and helpful
15. **Code cleanup** - Remove old validation logic and consolidate functions

### Phase 4: Optimization
16. **File size optimization** - Keep files under ~400 lines by reusing functions
17. **Cache operations** - Identify and consolidate repeated operations
18. **Helper function creation** - Create new helper files if needed
19. **README update** - Document the new enhanced member processing system

## Success Criteria
- Each ContainerInfo member has its own processing function
- All members return `(value, resolved_value, errors)` tuple
- Commands use the new member processing system
- Error handling is robust and clear
- Files remain under ~400 lines
- All tests pass
