HDLForge

## Project selection and working directory

Startup selects the project once in `hdlforge_environment.bash`. It searches
from the launch directory upward for the nearest `.hdlforge.json` or
`.hdlforge.toml`, stopping at a Git checkout boundary. Multiple candidates in
one directory require an explicit selection. `--project FILE` and
`--project=FILE` override discovery; relative filenames resolve against the
original launch directory. Symlinks resolve to the actual project file.

Commands execute from the selected file's containing directory. The launcher
passes its absolute filename to native tools and exports it as
`HDLFORGE_PROJECT_FILE`, with the working directory in `ROOT_FOLDER`.
Environment leaf lookup and JSON shortcuts consume that same selection.
Relative VCD capture paths and externally invoked Verilator source lists keep
their original launch-directory base. Source-file arguments do not select a
different project; use `--project` for an external source's project.

Nested commands retain an explicit project choice when searching that same
directory, including directories with multiple project files. Changing to a
different project selects the nearest project there. Fresh launches ignore an
inherited project filename. An `eval-cmd` invocation with no selected project retains its
launch directory when the repository environment is otherwise available.

## SSH configuration inventory

Run these from the repository root to use its `*.hdlforge.json`, or select
`--json PATH` explicitly. These commands need only Python's standard library;
they do not connect to hosts or execute SSH `Match exec` commands.

```bash
hdlforge ssh.import --json fpga.hdlforge.json --ssh-config ~/.ssh/config --dry-run
hdlforge ssh.import --json fpga.hdlforge.json
hdlforge ssh.verify --json fpga.hdlforge.json
hdlforge ssh.export --json fpga.hdlforge.json --dry-run
hdlforge ssh.merge --json fpga.hdlforge.json --input laptop.json --input lab.json --dry-run
hdlforge ssh.merge --json fpga.hdlforge.json --input lab.json --on-collision incoming
hdlforge ssh.export --help
```

Actions accept `--help`; write actions support `--dry-run` and `--force`.

The inventory belongs to the **local** hostname and local user:
`settings.env.<local-host>.<local-user>.ssh_config`. Defaults come from the
current machine and login user; select another environment with
`--local-host NAME --local-user NAME`. These select inventory ownership, not
remote login credentials. Each input to merge uses this same explicit scope;
other hosts, users, and repository settings are preserved.

```json
{
  "settings": {
    "env": {
      "fpga-dev-1": {
        "ykarmon": {
          "ssh_config": {
            "ch4dev-03": {
              "HostName": "ch4dev-03",
              "User": "yoav.karmon",
              "Port": 22
            },
            "ch4fpgadev-01": {
              "HostName": "ch4fpgadev-01",
              "User": "yoav.karmon",
              "Port": 22
            }
          }
        }
      }
    }
  }
}
```

There is no version, preamble, host list or multiline configuration blob.
The destination host is the dictionary key; its value is an SSH option
dictionary. Repeated directives such as `IdentityFile` use arrays of values.
Import discards standalone comments and whitespace; export generates consistent
SSH syntax. Values retain SSH quoting, and numeric ports are stored as integers.
Global settings, `Include`, `Match`, wildcard/negated patterns, multi-alias
blocks and repeated Host blocks are rejected before import writes anything:
this scoped host dictionary cannot preserve their precedence. SSH directives
are never executed during import or verification.

Import replaces only the selected environment's inventory. Export replaces the
selected SSH file, so review its diff before applying. Verification compares
host options rather than whitespace or comments and reports host collisions;
it does not certify SSH syntax or reachability.

The connection **Host alias**, compared case-insensitively, is the merge key.
Different aliases sharing one `HostName` remain separate. Duplicate JSON object
keys are rejected. Merge reads the destination's selected inventory first,
followed by each `--input` in order. Identical settings are reported as
`DUPLICATE` and deduplicated; differing settings for the same host are reported
as `COLLISION` with source filenames. Default collision policy is `error`
(no write). Explicit `--on-collision keep` keeps the first entry; `incoming`
uses the last. `--force` skips approval but never chooses a collision policy.

Writes show a unified diff and prompt `Apply changes? [y/N]`; EOF or declining
leaves files untouched. `--force` retains the diff and backup but skips the
prompt. Every changed existing destination gets a sibling backup named
`<filename>.<YYYYMMDDTHHMMSS.microsecondsZ>.bak`, with private permissions.
New files have no previous content to back up and are created with mode 0600.
Existing destination permissions are retained. Writes use atomic replacement;
symlink destinations are refused (select the resolved path explicitly).
Changes detected during approval abort the write.

Dry-run, verification, cancellation, and unchanged files create no backups or
other writes. Exit codes: 0 for success/clean verification, 1 for cancellation
or verification differences/collisions, 2 for invalid input/unresolved merge
collisions. Inventories and diffs can contain sensitive SSH options; review
their contents before committing or sharing.

Bitstream-only regeneration uses the normal Vivado build selector:

```bash
hdlforge vivado.build.impl.synth_production.latest.impl_production.bitstream.<impl_timestamp>
```

Select a dated synthesis in place of `latest` when needed. Completion lists
existing completed implementation attempts after `.bitstream.`; a literal
newest timestamped implementation must be complete to select `latest`.
HDLForge snapshots the final routed checkpoint and original paired LTX files,
then writes a new bitstream in the implementation's `bitstream_runs/<timestamp>/`.
The original implementation's USERID timestamp is retained. No synthesis,
placement, routing, physical optimization or current-source/XDC reload occurs.
Original implementation outputs remain intact. Regeneration uses the normal
background launcher, `runme.log`, `vivado.build.status`, Ctrl-C detach and
`vivado.build.stop_all`. No extra JSON setting or project Tcl helper is required.
New runs record the final checkpoint in `info/last_routed_checkpoint.txt`.
Legacy examples use `<top>_postroute_physopt.dcp` or `<top>_routed.dcp`.

Non-project implementation bitstream identity:
  The shared runtime sets BITSTREAM.CONFIG.USERID immediately before write_bitstream
  from launch_epoch (UTC Unix seconds), fixed for that implementation launch.
  New launches and reruns get new values. The run log and info/bitstream_timestamp.json
  record the value. Source XDC files are not rewritten; USR_ACCESS/version remains
  design-controlled. Existing bitstreams and saved runtime snapshots are unchanged.

## Dotted commands

The installed `native_command_help.json` is the source of truth for executable
command leaves, contextual help and completion. An incomplete path prints its
available children and modifiers without launching a tool.

```bash
hdlforge
hdlforge vivado
hdlforge vivado.build
hdlforge vivado.build.synth.synth_example.new
hdlforge vivado.build.impl.synth_example.latest.impl_example.new
hdlforge vivado.build.synth.synth_example.continue
hdlforge Verilator.sim --SimTargetName full_sim
hdlforge vivado.console.send --cmd 'open_checkpoint design.dcp'
hdlforge eval-cmd 'python3 script.py --argument value' --dry-run
hdlforge eval-cmd.help
hdlforge project-shortcuts.testing.integration_test.sim.example.run_all
```

`continue` preserves the existing configured-run continuation behavior. `new`
requests a new synthesis. Implementation selectors identify their synthesis,
implementation and operation as shown by completion.

Project shortcut lookup is explicit through `project-shortcuts.<path>` and
limited to `LLM_orch`. Bare shortcut paths are not auto-detected. Project-file
discovery for startup and environment setup remains automatic.

`eval-cmd` accepts exactly one quoted shell command. Its `--dry-run` resolves
the environment and prints the command and working directory without executing
the payload. Arguments for scripts belong inside that quoted command or in a
dedicated script. `--tool`, top-level `--cmd`, `--eval_json` and `--append` are
removed. The console's local `--cmd` still supplies its Tcl payload.

## Master flags

Every command inherits `tree.master_flags`: `--project`, `--env-path`,
`--env-python`, `--env-var`, `--allow-env-overwrite`, `--no-print`, `--dry-run`,
`--help` and `-h`. They appear in every command's help/completion and may be
placed before or after its anchor. Action-local modifiers follow the command.
Environment arrays accept literal JSON or a dotted data leaf in the selected
project; `--env-var` uses an array of single-key objects.

```bash
hdlforge eval-cmd 'python3 -m integration_test.example' --env-python '["sources/tests"]'
hdlforge project-shortcuts.testing.example --env-var '[{"TESTCASE":"example"}]'
hdlforge eval-cmd 'printenv TESTCASE' --allow-env-overwrite --env-var '[{"TESTCASE":"changed"}]'
```

Nested invocations preserve inherited environment values by default. New keys
and path entries can be added. A changed inherited value is skipped with a
stderr warning; `--allow-env-overwrite` permits replacing it on that invocation
and emits the normal overwrite warning. Permission is not inherited by further
nested launches. Equal values are quiet. Reserved launcher variables remain
protected even with the flag. First-launch repository/project/CLI precedence
is unchanged.

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
Inspection actions (`get_runs`, `run_info`, `group_info`, `run_status`) operate
on the project explicitly opened in that console. `set_run_property` reads or
edits its properties. `close_project` keeps the console alive and refuses to
close active runs. Stop and restart terminate the managed console without
export prompts. They do not manage non-project build workers.

Each response retains native output, Tcl results, errors and structured records.
`--raw` suppresses summary tables; `--json` emits a response envelope.
`print-json`, `install-json --json-file FILE --key LLM_orch.vivado`, and
`update-json` maintain reusable console shortcuts while preserving siblings.
All managed synthesis, implementation and bitstream generation uses the
non-project build commands documented above.

LLM_orch:
  hdlforge <shortcut.path>
  hdlforge <shortcut.path> --append '<extra flags>'
  hdlforge eval-cmd '<shell command>'
  hdlforge --no-print eval-cmd '<shell command>'
  hdlforge eval-cmd '<shell command>' --append '<extra flags>'
  hdlforge --env-python '["sources/tests"]' --cmd 'python3 -m package.tool'
  hdlforge eval-cmd 'my_tool --flag value' --env-path '["tools"]'

## Environment initialization

`hdlforge_environment.bash` owns project selection, startup and overlays.
`HDLFORGE_CALLED=1` marks an initialized chain. On the first launch, HDLForge
finds the selected working directory's Git root and reads the root JSON's
`settings.env.<host>.<user>` through jq before clearing caller exports.
Select host/user with `HOST_MACHINE` and `HDLFORGE_HOST_USER` before launch.

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
hdlforge path_manager.show
hdlforge path_manager.show-all
hdlforge path_manager.init-base-path
hdlforge path_manager.init-base-pythonpath
hdlforge path_manager.install-shell
hdlforge path_manager.update-repo --project repo.hdlforge.json
```

`show` reports effective paths; `show-all` reports configured host/user pairs.
The two `init-base-*` actions print shell exports from the incoming environment.
`install-shell` installs the launcher and completion in the user's bashrc.
`update-repo` records the current host/user configuration where missing.
Normal startup is automatic; management actions are not prerequisites.

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
tools. It consumes only tokens before the cursor and treats option values and
the eval payload as opaque. Double-Tab displays descriptions; normal completion
inserts tokens only. Unknown commands/options and anonymous passthrough fail.

Related references: `hdlforge_project_file.md`, `how_hdlforge_keeps_paths_clean.md`.
