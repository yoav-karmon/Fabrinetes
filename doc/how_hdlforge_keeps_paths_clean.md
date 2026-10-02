# HDLForge environment paths

The launcher owns a single startup implementation in
`hdlforge/project_setup/hdlforge_environment.bash`.

1. Select the project from the launch directory or `--project`.
2. On the first launch only, validate repository host/user settings and rebuild
   the child environment, including PATH and PYTHONPATH.
3. Apply the selected project overlay on every invocation.
4. Apply CLI additions last and remove duplicate paths.

Repository-relative entries use the repository JSON's directory; project
entries use the selected file's directory. Nested launches keep the baseline.
Changed variable assignments warn on stderr without printing values.

Use `hdlforge paths.show` to inspect effective paths and
`hdlforge paths.show-all` for configured environments.
See [HDLForge](hdlforge.md#environment-initialization) for the environment
contract, retained runtime variables and management commands.
