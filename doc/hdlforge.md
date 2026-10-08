HDLForge

## Project selection and working directory

Startup selects the project once in `hdlforge_environment.bash`. It searches
from the launch directory upward for the nearest `.hdlforge.json` or
`.hdlforge.toml`, stopping at a Git checkout boundary. Multiple candidates in
one directory require an explicit selection. `--project FILE` and
`--project=FILE` override discovery; relative filenames resolve against the
original launch directory. Symlinks resolve to the actual project file.

Implicit discovery never changes directories: commands execute from the launch
directory. An explicit `--project` is the only selection mode that changes the
working directory, and it enters the selected file's containing directory
before environment setup and dispatch. The launcher passes the absolute project
filename to native tools and exports it as `HDLFORGE_PROJECT_FILE`.
`HDLFORGE_PROJECT_FOLDER` is the selected project directory; it is configuration
metadata, not a promise that `PWD` has changed. Environment leaf lookup and JSON
shortcuts consume that same selection. Relative VCD capture paths and externally
invoked Verilator source lists keep their original launch-directory base.
Source-file arguments do not select a different project; use `--project` for an
external source's project.

Nested commands retain an explicit project choice when searching that same
directory, including directories with multiple project files. Changing to a
different project selects the nearest project there. Fresh launches ignore an
inherited project filename. Every command follows the same directory rule;
`eval-cmd`, project shortcuts and native tools have no separate cwd policy.

## Dotted commands

The installed `native_command_help.json` is the source of truth for executable
command leaves, contextual help and completion. An incomplete path prints its
available children and modifiers without launching a tool.

```bash
hdlforge
hdlforge vivado
hdlforge vivado.build
hdlforge vivado.build.synth_example.run
hdlforge vivado.build.synth_example.latest.impl.impl_example.run
hdlforge sim-verilator.sim --SimTargetName full_sim
hdlforge vivado.console.send --cmd 'open_checkpoint design.dcp'
hdlforge --dry-run eval-cmd 'python3 script.py --argument value'
hdlforge eval-cmd.help
hdlforge eval-cmd-argv.help
hdlforge aliases.testing.integration_test.sim.example.run_all
```

`continue` preserves the existing configured-run continuation behavior. `new`
requests a new synthesis. Implementation selectors identify their synthesis,
implementation and operation as shown by completion.

Project shortcut lookup is explicit through `aliases.<path>` and
limited to `LLM_orch`. Bare shortcut paths are not auto-detected. Project-file
discovery for startup and environment setup remains automatic.

`eval-cmd SHELL_TEXT...` gives every remaining command part to Bash `eval`.
Bash joins those parts with spaces and evaluates the resulting shell text. A
conventional quoted shell command remains one part, while launchers may allow
their own expansion to produce several parts. The `eval-cmd` name is the
boundary; no separate `--` is required. HDLForge master flags must precede it.
Every later token belongs to the evaluated command, even when it looks like
`--project`, `--dry-run` or another master flag. `--dry-run` resolves the
environment and prints the effective command and working directory without
executing it. `--tool`, top-level `--cmd`, `--eval_json` and `--append` are
internal or removed. The console's local `--cmd` still supplies its Tcl payload.

`eval-cmd-argv PROGRAM [ARG...]` is the argument-preserving counterpart. Its
name is also the boundary, and no separate `--` is required. It executes
`PROGRAM` directly and passes each later item as one argument, without reparsing
any of them as shell text. If a later token matches an HDLForge master flag,
HDLForge warns on stderr that the token remains a program argument and explains
that the flag must move before `eval-cmd-argv` to affect HDLForge. `--help` and
`-h` are excluded because they are common child-program arguments. The warning
never changes or removes an argument.

```bash
hdlforge --dry-run eval-cmd 'python3 script.py --argument value'
hdlforge --env-python '["sources/tests"]' eval-cmd python3 script.py --argument value
exec hdlforge eval-cmd-argv "$script_path" "$@"
```

Use `eval-cmd` for intentional shell syntax such as pipes, redirects and
variable expansion. Use `eval-cmd-argv` for launchers and arguments containing
whitespace or shell operators that must remain literal.

## Master flags

Every command inherits `tree.master_flags`: `--project`, `--env-path`,
`--env-python`, `--env-var`, `--allow-env-overwrite`, `--no-print`, `--dry-run`,
`--help` and `-h`. They appear in every command's help. Commands other than
`eval-cmd` and `eval-cmd-argv` retain support for placement before or after
their command path. For both execution commands, place every master flag before
the command name because the complete tail belongs to it. Action-local
modifiers follow their owning command.
Environment arrays accept literal JSON or a dotted data leaf in the selected
project; `--env-var` uses an array of single-key objects.

```bash
hdlforge --env-python '["sources/tests"]' eval-cmd 'python3 -m integration_test.example'
hdlforge aliases.testing.example --env-var '[{"TESTCASE":"example"}]'
hdlforge --allow-env-overwrite --env-var '[{"TESTCASE":"changed"}]' eval-cmd 'printenv TESTCASE'
```

Nested invocations preserve inherited environment values by default. New keys
and path entries can be added. A changed inherited value is skipped with a
stderr warning; `--allow-env-overwrite` permits replacing it on that invocation
and emits the normal overwrite warning. Permission is not inherited by further
nested launches. Equal values are quiet. Reserved launcher variables remain
protected even with the flag. First-launch repository/project/CLI precedence
is unchanged.

## Maintained build definitions

Each synthesis/IP definition's `script` path, relative to the project JSON,
determines its run folder: new attempts live beside that script in
`_<timestamp>/`. For example, `script: "compilation/subproject/synth/run.tcl"`
produces `compilation/subproject/synth/_<timestamp>/`. The JSON run name and CLI
selector stay unchanged; there is no per-run output-path setting. Each run must
have its own folder, and its maintained implementation scripts remain beside
the synthesis script. Implementation attempts still live under the selected
synthesis attempt's `impl_runs/<implementation>/_<timestamp>/`.

Existing flat `compilation/<run>/run.tcl` configurations behave identically.
No shared output root or registry is required. The legacy `output_root` field
is ignored; source inputs must still satisfy the repository snapshot rules.
Only generated attempts match the root `_*` ignore rule.
Changing a script's folder redirects future lookup and output;
existing attempts are not moved or migrated automatically.

A synthesis or implementation definition contains `script`, one `sources`
array and (for synthesis) `impl_runs`. IP producers
use `kind: "ip"` so the launcher creates private writable IP inputs and records
freshness hashes. The manifest has no part, top, defines or Vivado property maps.

The maintained Tcl owns all design choices, including threads:
`set_param general.maxThreads 8`, `create_project -in_memory -part $part`,
language/read options and properties. Declare the identity with
`::hdlforge::design $top $part`; resolve each snapshotted input with
`::hdlforge::source_path <declared-path>`. JSON lists RTL, IP, constraints,
Tcl and other helper files together under `sources`; it does not choose how
Vivado reads them. Input directories are preserved under `snapshot/source`.
Declare dynamic dependencies explicitly.

Implementations declare all their inputs, including IPs. The parent checkpoint
is supplied as `input_dcp` in runtime metadata and verified by hash. Tcl's design
identity must match the parent. New attempts use the implementation definition
in the full project JSON saved inside the synthesis snapshot, and copy only
its declared saved inputs. Generated metadata records stage, part and top
for artifact discovery; those are runtime results, not project configuration.

## Persistent Vivado Tcl console

```bash
hdlforge vivado.console.start
hdlforge vivado.console.send --cmd 'open_checkpoint design.dcp'
hdlforge vivado.console.source --file inspect.tcl
hdlforge vivado.console.interactive
hdlforge vivado.console.status
hdlforge vivado.console.restart
hdlforge vivado.console.stop
```

The selected HDLForge JSON identifies the persistent tmux console. It needs no
XPR or exported project Tcl and starts without opening or creating a project.
Use `send` or `source` for unrestricted Tcl, including opening checkpoints or
explicitly opening an existing project for inspection. Detach with Ctrl-b d.
Use generic Tcl submission for interactive inspection. Stop and restart
terminate the managed console without export prompts. They do not manage
non-project build workers.

Each response retains native output, Tcl results, errors and structured records.
`--raw` suppresses summary tables; `--json` emits a response envelope.
`print-json`, `install-json --json-file FILE --key LLM_orch.vivado`, and
`update-json` maintain reusable console shortcuts while preserving siblings.
All managed synthesis, implementation and bitstream generation uses the
non-project build commands documented above.

## Environment initialization

`hdlforge_environment.bash` owns project selection, startup and overlays.
`HDLFORGE_CALLED=1` marks an initialized chain. On the first launch, HDLForge
uses the selected project directory, or the launch directory when no project is
selected, to find the owning Git root. It evaluates the repository-root JSON's
`settings.env.<host>.<user>` through jq before clearing caller exports, then
evaluates the selected project JSON as an overlay when it is a different file.
Select host/user with `HOST_MACHINE` and `HDLFORGE_HOST_USER` before launch.

Every launch must start inside a Git repository. Nested calls cannot reuse
another repository's environment. The root must contain exactly one
`.hdlforge.json` and an entry for the selected host/user with all six keys:
`path`, `path_import`, `pythonpath`, `pythonpath_import`, `variables`,
`variables_import`. Path/import fields are arrays; variables is an object.
Empty arrays/objects are valid. Missing entries or invalid types fail before
any runnable command, including JSON and path-management actions, executes.
Contextual help is resolved before runtime environment initialization.

Imports name same-typed leaves in that root JSON, for example
`"path_import": ["settings.env.shared.base.path"]`. Dotted host/user names
are matched as complete JSON keys. A referenced leaf's sibling `*_import`
list is expanded recursively, then its local values apply. Imports run in
listed order before the selected host/user's local values. Missing references
and cycles fail before changing the environment. Variable replacements warn
with the name only. Paths use the existing prepend/deduplication helpers:
later additions take precedence, and duplicates retain their existing place.
Repository imports run once per initialized chain. Nested commands revalidate
the repository identity and mandatory root JSON, then reuse the already
evaluated repository environment. Project/CLI overlays keep the normal nested
overwrite protection.

The fresh environment retains login identity, terminal/display access, locale,
timezone, temporary-directory settings and SSH-agent access. Arbitrary caller
exports are dropped. PATH/PYTHONPATH start from a minimal executable baseline
and configured repository paths. Tool settings and literal string variables
come from the JSON. The parent shell is unchanged.

Every invocation, including nested ones, overlays the selected project's
environment, then `--env-path`, `--env-python` and `--env-var`. Nested calls
retain the repo baseline without rediscovering or resetting it. Paths resolve
relative to their owning JSON and are deduplicated. CLI paths resolve relative
to the project directory. Changed variable values produce a stderr warning
with the variable name and layer; identical assignments are quiet. Values are
literal, including quotes, dollar signs and trailing newlines. Internal launcher
variables and PATH/PYTHONPATH cannot be replaced through `--env-var`.

## Path management

```bash
hdlforge paths.show
hdlforge paths.show-all
hdlforge paths.init-base-path
hdlforge paths.init-base-pythonpath
hdlforge paths.install-shell
hdlforge paths.update-repo --project repo.hdlforge.json
```

`show` reports effective paths; `show-all` reports configured host/user pairs.
The two `init-base-*` actions print shell exports from the evaluated environment.
`install-shell` installs the launcher and completion in the user's bashrc.
`update-repo` updates an already valid repository environment configuration;
it cannot bypass missing or invalid mandatory base fields. Normal startup is
automatic; management actions are not prerequisites.

## Shared command tree

`native_command_help.json` stores `tree.commands` and `tree.master_flags`.
Each dot selects a child in `commands`; a dynamic provider resolves project
shortcut paths or build selectors. Executable leaves declare their internal
dispatch arguments and allowed `flags`. The same resolver validates launch
arguments and supplies help/completion state. Internal dispatcher arguments
are implementation details, not a second public command syntax.

Flags declare arity, repeatability, values/providers and optional `when`
conditions (`present`, `equals`, `all`, `any`, `not`). Every static command or
flag has a sibling `#name` description. Dynamic project shortcuts use their
own sibling descriptions. Metadata is display-only.

Completion reads configuration without setting up environments or contacting
tools. It consumes only tokens before the cursor and treats the complete
`eval-cmd` and `eval-cmd-argv` tails as opaque. Double-Tab displays descriptions;
normal completion inserts tokens only. Unknown commands/options and anonymous
passthrough fail.

Related references: `hdlforge_project_file.md`, `how_hdlforge_keeps_paths_clean.md`.


## JSON maintenance

Every tool that reads a configurable project section exposes `update-json`
and `lint-json`: `paths`, `aliases`, `sim-verilator`,
`vivado.build`, `vivado.console`, and `vivado.monitor`.
`vivado.update-json` / `vivado.lint-json` cover all three Vivado sections.

```bash
hdlforge paths.update-json --project fpga.hdlforge.json --dry-run
hdlforge paths.update-json --project fpga.hdlforge.json
hdlforge vivado.build.update-json --project chip.hdlforge.json --dry-run
hdlforge vivado.build.update-json --project chip.hdlforge.json
hdlforge vivado.build.lint-json --project chip.hdlforge.json
hdlforge sim-verilator.lint-json --project simulation.hdlforge.json
```

Updates add missing required keys, including empty placeholders. Existing
values, custom keys, comments represented by JSON `#` keys, and credentials
remain intact. Invalid container types fail without rewriting the document.
Dry-run reports only added key paths and does not write files. Unchanged
documents retain their original bytes and modification time. Writes are atomic
and reject a concurrent content change.

Lint reports missing keys, invalid types, retired build fields, and unresolved
configured source/script/include paths. Empty placeholders pass structural
lint; they do not make an otherwise empty build runnable. Simulation inputs
resolve relative to the selected project file. Environment lint uses the startup
import resolver and validates paths for the selected host/user; filesystem checks
reflect that machine. Output directories need not exist before a build.
Alias lint parses native HDLForge invocations without executing shell commands.

Schema maintenance runs after project selection and before environment
initialization, so an incomplete environment document can be repaired.
Select the repository-root JSON for `paths`.
`paths.update-repo` selects that root document automatically.
Generic tools taking only command-line inputs need no project schema.

The root commands are `aliases`, `discover`, `eval-cmd`, `eval-cmd-argv`, `hw-server`,
`network`, `paths`, `sim-verilator`, `tshark`,
`vivado`, and `waveform`. They are lowercase with distinct initial letters.
The command tree supplies the executable routes, help, and tab-completion.

## Non-project monitoring

`vivado.monitor` discovers attempts in the folders containing the configured
synthesis/IP scripts. Parent IDs connect synthesis,
implementation and bitstream attempts. The monitor reads `build.log` (or historical `logs/runme.log`)
and timing reports in `artifacts/` and `work/`; it does not consult XPRs.
Use `vivado.build.status` for build-worker status and
`vivado.console` for interactive Tcl.

```bash
hdlforge vivado.monitor.start
hdlforge vivado.monitor.scan
hdlforge vivado.monitor.status
hdlforge vivado.monitor.tail --run PROJECT.SELECTOR.RUN_ID --no-follow
hdlforge vivado.monitor.stop
```

Monitor settings live at `vivado.monitor`. Lifecycle hooks and optional
collection execute explicitly configured argument arrays; `{run}` expands
to the absolute non-project attempt directory and `{project}` to the project
directory. No project-mode collector is configured. Builds keep snapshots and
artifacts directly in each attempt. Monitor control does not stop build workers.

## Bulk IP selection

HDLForge builds the explicitly selected run. Batch selection belongs to the
project's alias or script, outside the Vivado builder schema.
The FPGA IP batch and publishing scripts accept their own repeatable
`--skip RUN [RUN ...]` option. Aliases can bind an exclusion list in the script
command. Direct build commands remain available for every configured run.


## Build attempts and timing experiments

```text
vivado.build.<synthesis>.run
vivado.build.<synthesis>.<attempt>.status
vivado.build.<synthesis>.<attempt>.stop
vivado.build.<synthesis>.<attempt>.impl.<implementation>.run
vivado.build.<synthesis>.<attempt>.impl.<implementation>.<attempt>.status
vivado.build.<synthesis>.<attempt>.impl.<implementation>.<attempt>.stop
vivado.build.<synthesis>.<attempt>.impl.<implementation>.bitstream.<attempt>
```

`.run` always creates a fresh attempt. Rename completed synthesis or implementation
attempt folders freely while keeping the configured synthesis/implementation
folders and relative tree intact. Completion displays those folder names; IDs
stay in metadata. `latest` is selected by manifest creation time.

HDLForge scans the configured synthesis folder for valid attempt manifests.
The saved synthesis project JSON defines its implementations. Their launch commands
remain visible before synthesis finishes; launching without the synthesis checkpoint
fails with its missing path. Unrelated or
invalid subfolders do not become launchable commands.

Each attempt owns `manifest.json` (resolved inputs/hashes, command, tool version,
process information, stage events, status and result) and `build.log` (launcher,
runner and Vivado output). Snapshot inputs stay under `snapshot/`, results under
`artifacts/`, and auxiliary Vivado files under `work/`. Each attempt also owns
`.manifest.lock` for atomic updates and `.run.lock` for worker/cleanup exclusion.
Status, stop-all and the monitor enumerate the configured run folders and their
implementation/bitstream children; they do not read or write a global registry.
Status reads manifests without modifying them. Cancellation is recorded under
the parent attempt's manifest lock before an automatic child can register.
Existing `_run_registry.json` and `_run_registry.lock` files are left untouched.

`vivado.build.clean_ignore_artifacts` also removes orphan `_<run-id>.run.lock`
files after their attempts have been deleted, including leftovers from earlier
cleanup calls. It preserves held locks, locks for existing attempts, tracked or
non-ignored files, symlinks and locks whose ownership cannot be established.
Use `--dry-run` to preview both attempt and orphan-lock cleanup.

Build lint checks existing declared inputs and literal `::hdlforge::source_path`
references in run Tcl and declared Tcl helpers against each run's JSON `sources`.
Dynamic Tcl expressions are still checked at execution time.

Synthesis saves the project JSON and declared implementation Tcl/XDC, then prepares
every `impl_runs/<implementation>/snapshot/`. Only actual synthesis and implementation
attempts get `work/` and `artifacts/`; configured run folders hold inputs.
Each prepared snapshot copies only that implementation's declared files from the
synthesis snapshot, plus the project JSON. Edit the prepared Tcl/XDC for timing
experiments. Implementation Tcl filenames are preserved in every snapshot.
The synthesis snapshot's project JSON selects the implementation's `script`;
HDLForge resolves its relative path inside the prepared `snapshot/`, then
copies and executes it inside the new attempt. Missing copies fail without
falling back to live sources. Each implementation `.run` freezes its
current settings into a new attempt against that synthesis checkpoint. Multiple
attempts can run independently, preserving earlier settings/results. There are no `.new`, `.continue`, or `.rerun` build actions.

Rename and save completed attempt folders with Git when useful. Include the
producing synthesis checkpoint with any saved implementation; use `git add -f`
for ignored snapshots and review the staged files. Do not rename active attempts.
See the [example layout and workflow](../hdlforge/project_setup/vivado_build_example_README.md).
Global `status`, `lint-json`, `stop_all` and cleanup remain under `vivado.build`.

Each synthesis snapshot contains a full, unchanged copy of the selected
`*.hdlforge.json`, preserving its filename. Source → synthesis copies the files
declared by synthesis and its implementations. Synthesis → implementation uses
only the selected implementation's `script` and `sources` from that saved JSON.
The manifest records resolved paths and execution metadata; it does not choose
the file list. Implementation never refreshes inputs from the live project.
Synthesis prepares each `impl_runs/<impl>/snapshot/` with its own declared
files. For timing experiments, edit that implementation's prepared Tcl/XDC;
every `.run` copies those inputs into a fresh attempt. Source selection remains
in the synthesis snapshot's project JSON and must reference that implementation's
prepared inputs. Earlier attempts remain unchanged. Constraints stay in snapshots.

Snapshot copies preserve repository-relative directories and filenames directly
beneath `snapshot/`, including the run Tcl. There are no added `source/` or
`scripts/` input containers. The repository root is the top of every snapshot. The saved JSON stays at
its repository-relative project path; its script paths resolve relative to that
project folder inside the snapshot. Only the attempt copy is executed. Inputs
outside the repository are rejected; no `_external` directory is created.

## Checkout-local Git SSH configuration

Use `git-config.update-dry-run` to preview, `git-config.update` to apply, and
`git-config.verify` to compare the checkout's local `core.sshCommand` with the
current local host/user's `settings.env.<host>.<user>.ssh_config_file` in the
repository-root JSON. The file path is repository-relative and must exist
inside the repository. The update uses `ssh -F` with its resolved absolute
path. It changes only local Git configuration, not the SSH file or global Git
settings. Separate checkouts are independent; users sharing a checkout share
its local Git setting. Submodules are not updated automatically.

New compilation attempts store their execution/checkpoint-use lock in
`<attempt>/.run.lock`. Synthesis, implementation and bitstream consumers use
that same lock, and artifact cleanup takes it exclusively before deletion.
The file may remain after completion: only a held OS lock means it is busy.
It is deleted together with the attempt. Existing external run-ID locks are
still honored for older attempts so running workers retain protection; the
existing orphan-lock cleanup handles those after their attempts are removed.
