# Global Cursor Rules - Apply to All Sessions

## Session Startup Guidelines
- On session start, ensure the cursor_send_box folder exists
- If cursor_send_box folder does not exist, create it
- Verify that .gitignore includes cursor_send_box/ to ignore the folder
- Use cursor_send_box/ for temporary development files and notes
- Workflow plans should be written as .md files in cursor_send_box/
- Helper files, scripts, and other temporary files should be located in cursor_send_box/

## Code Style Guidelines
- Write clean, readable, and well-documented code
- Use meaningful variable and function names
- Follow language-specific conventions (PEP 8 for Python, etc.)
- Add comments for complex logic
- Keep functions focused and single-purpose

## Documentation Standards
- Write clear docstrings for functions and classes
- Include parameter descriptions and return values
- Add inline comments for non-obvious code
- Update documentation when code changes

## Error Handling
- Use appropriate exception handling
- Provide meaningful error messages
- Log errors appropriately
- Handle edge cases gracefully

## Security Best Practices
- Never hardcode sensitive information (passwords, API keys)
- Use environment variables for configuration
- Validate user inputs
- Follow principle of least privilege

## Performance Considerations
- Optimize for readability first, performance second
- Profile before optimizing
- Use appropriate data structures
- Avoid premature optimization

## Testing
- Write tests for critical functionality
- Use descriptive test names
- Test edge cases and error conditions
- Keep tests simple and focused
- ALWAYS test with the test container (fabrinetes-dev-testing) when testing Fabrinetes functionality

## Git Practices
- NEVER commit or push changes without explicit user request
- Review code before committing
- Group changes by subject/topic in separate commits

## Docker/Container Guidelines
- Use multi-stage builds when appropriate
- Minimize image layers
- Use specific version tags
- Clean up temporary files
- Document container purpose and usage

## File Organization
- Use consistent directory structure
- Group related files together
- Use descriptive file and directory names
- Keep configuration files organized

## Terminal Output Guidelines
- NEVER use non-ASCII characters (emojis, special symbols) in terminal output
- Use ASCII-only characters for maximum compatibility
- Use standard ASCII symbols like [!], [X], [OK] instead of emojis
- Ensure all terminal output is compatible with basic terminals

## Communication
- Be clear and concise in explanations
- Provide context when asking questions
- Use examples to illustrate points
- Be respectful and collaborative
