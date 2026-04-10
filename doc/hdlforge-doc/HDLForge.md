# HDLForge API Reference

This is the single source of truth for HDLForge's generic API, CLI behavior, project-file structure, and internal execution model.

Scope:

- generic HDLForge CLI and configuration behavior belongs here in `Fabrinetes`
- project-specific workflows belong in the consuming repository
- `fpga`-wide guidance belongs under `fpga/.cursor/...`
- `phy10gbaser`-specific guidance belongs under `fpga/fpga_projects/phy10gbaser/...`

This document intentionally does **not** duplicate project-specific usage patterns or examples.

---

## 1. CLI Model

HDLForge supports two invocation modes.

### Direct tool mode

Use `--tool` for HDLForge's built-in tools:

```bash
hdlforge --tool <tool_name> [options]
```

Current built-in tools relevant to FPGA flows:

- `Verilator`
- `vivado`

Examples:

```bash
hdlforge --tool Verilator --step build --SimTargetName <target>
hdlforge --tool Verilator --step sim --SimTargetName <target>

hdlforge --tool vivado --generate_prj_with_external_tcl --clean -f
hdlforge --tool vivado --list_runs
hdlforge --tool vivado --syn <synth_run_name>
```

### LLM_orch shortcut mode

If `--tool` is omitted, HDLForge interprets positional arguments as a path inside `LLM_orch` in the active project file.

```bash
hdlforge <path...>
```

Examples:

```bash
hdlforge trigger_test sim all
hdlforge vivado project write_tcl
```

---

## 2. Help And Discovery

Working help commands:

```bash
hdlforge
hdlforge --tool Verilator --help
hdlforge --tool vivado --help
```

Project discovery modes:

| Mode | Usage | Notes |
|------|-------|-------|
| Auto-detect | `cd <project_dir> && hdlforge --tool ...` | Requires exactly one `*.hdlforge.json` or `*.hdlforge.toml` in the current directory |
| Explicit | `hdlforge --project path/to/project.hdlforge.json --tool ...` | Works from any directory |

JSON is preferred over TOML when both formats are present.

---

## 3. Project File Schema

Current HDLForge project files use tool-specific sections.

### Minimal example

```json
{
  "settings": {
    "project_name": "my_project",
    "project_path": "$REPO_TOP/my_project"
  },
  "verilator": {
    "config": {
      "build_dir": "_verilator",
      "includes_paths": ["sources/include"],
      "sim_targets": [
        {
          "name": "basic_test",
          "top_module": "top",
          "python_file": "tests/test_top.py",
          "test_name": "test_basic",
          "build_args": ["--trace"],
          "PYTHONPATH": ["tests"]
        }
      ],
      "sources": [
        "sources/rtl/top.sv"
      ]
    }
  },
  "vivado": {
    "config": {
      "build_dir": "_vivado",
      "project_name": "my_vivado_project",
      "lint_ignore_error_codes": [],
      "lint_ignore_warning_codes": []
    },
    "external_config": {
      "filename": "sources/XDC/my_project.tcl"
    }
  },
  "LLM_orch": {
    "sim": {
      "all": "hdlforge --tool Verilator --step sim --SimTargetName basic_test"
    }
  }
}
```

### Section ownership

| Section | Purpose |
|---------|---------|
| `settings` | Project identity and working path |
| `verilator.config` | Verilator build settings, sources, and sim targets |
| `vivado.config` | Vivado build settings and lint filters |
| `vivado.external_config` | External Vivado TCL used to create the project |
| `LLM_orch` | Named shortcut commands resolved from positional arguments |

### Important current behavior

- The older `verilator_settings` and `vivado_settings` layout is legacy.
- `verilator.config.sources` is the active Verilator source list.
- Vivado structure is driven by the external TCL file, not by a JSON `runs_flow` block.

---

## 4. Verilator Reference

Use direct tool mode:

```bash
hdlforge --tool Verilator --step build --SimTargetName <target>
hdlforge --tool Verilator --step sim --SimTargetName <target>
```

Common options:

- `--project <path>`
- `--clean`
- `--flags "<extra flags>"`
- `--extra-env "KEY=value,KEY2=value"`

### Sim target fields

| Field | Meaning |
|-------|---------|
| `name` | Value used with `--SimTargetName` |
| `top_module` | HDL top module |
| `python_file` | Python testbench file |
| `test_name` | Optional Cocotb testcase name |
| `build_args` | Verilator compile flags |
| `PYTHONPATH` | Additional Python import paths |

### Typical outputs

- `_verilator/<run>/dump.vcd`
- `_verilator/<run>/results.xml`
- `_verilator/<run>/cocotb_verilator_output.log`

Open waves with:

```bash
gtkwave _verilator/<run>/dump.vcd
```

### Common problems

Missing RTL file:

```text
Cannot find file containing module ...
```

Checks:

- verify `verilator.config.sources`
- verify path resolution from the project file location

Missing include file:

```text
cannot find include file
```

Check `verilator.config.includes_paths`.

Python import failure:

```text
ModuleNotFoundError: ...
```

Check `python_file` and `PYTHONPATH`.

Requested testcase not executed:

```text
Requested testcase ... was not executed
```

Check `test_name` and any `TESTCASE=` override passed through `--extra-env`.

---

## 5. Vivado Reference

Use direct tool mode:

```bash
hdlforge --tool vivado --generate_prj_with_external_tcl --clean -f
hdlforge --tool vivado --lint
hdlforge --tool vivado --list_runs
hdlforge --tool vivado --syn <synth_run_name>
hdlforge --tool vivado --impl <synth_run_name>
hdlforge --tool vivado --bit <synth_run_name>
hdlforge --tool vivado --all <synth_run_name>
hdlforge --tool vivado --reset_run <synth_run_name>
hdlforge --tool vivado --write_tcl
hdlforge --tool vivado --file_add --file_path <path>
hdlforge --tool vivado --file_remove --file_path <path>
hdlforge --tool vivado --clean_logs
```

### Current execution model

- `--generate_prj_with_external_tcl` creates the `.xpr` project from the external TCL file.
- `--syn`, `--impl`, `--bit`, and `--all` take a **synth run name** such as `synth_1`.
- `--impl` and `--bit` operate on child implementation runs associated with that synth run.
- `--reset_run` resets the synth run and its child implementation runs.

### What belongs in the external TCL

The external TCL is the source of truth for:

- `create_project`
- FPGA part selection
- top module
- source and constraint lists
- run creation and relationships
- project-specific TCL setup

### Typical outputs

- `_vivado/<project>/<project>.xpr`
- `_vivado/<project>/<project>.runs/<run>/`
- `_vivado/<project>/<project>.runs/<impl_run>/*.bit`
- `_vivado/<project>/<project>.runs/<run>/runme.log`

Open the GUI with:

```bash
cd _vivado/<project_name>
vivado <project_name>.xpr
```

### Common problems

Project not created yet:

- `--list_runs`, `--syn`, or `--write_tcl` may fail if the `.xpr` does not exist yet
- fix by running `hdlforge --tool vivado --generate_prj_with_external_tcl --clean -f`

Missing source or constraint:

- verify the external TCL contents
- verify paths relative to the project root and TCL file

No child implementation runs found:

- verify the synth run name
- verify the external TCL created child impl runs for that synth run

---

## 6. LLM_orch Reference

`LLM_orch` maps positional CLI paths to shell commands.

Example structure:

```json
"LLM_orch": {
  "group": {
    "action": {
      "run": "hdlforge --tool Verilator --step sim --SimTargetName basic_test"
    }
  }
}
```

Resolution example:

```bash
hdlforge group action run
```

Resolves to:

```text
LLM_orch.group.action.run
```

Helpful discovery commands:

```bash
jq '.LLM_orch | keys' *.hdlforge.json
jq '.LLM_orch' *.hdlforge.json
```

Generic rule:

- generic `LLM_orch` mechanism belongs here
- project-specific shortcut naming and workflow conventions belong in the consuming project docs

---

## 7. Internal Architecture

HDLForge uses a two-stage execution model:

1. The bash wrapper handles environment setup, project discovery, directory changes, and logging.
2. The Python core parses arguments, loads the project file, and dispatches tool implementations.

### Main components

| Component | Role |
|-----------|------|
| `hdlforge/project_setup/hdlforge` | Bash wrapper |
| `hdlforge/project_setup/tasks.py` | Python CLI parser and dispatcher |
| `hdlforge/project_setup/project_file.py` | Current project-file loader |
| `hdlforge/project_setup/verilator_tasks.py` | Verilator implementation |
| `hdlforge/project_setup/vivado_tasks.py` | Vivado implementation |

### Environment flow

```text
user shell -> hdlforge wrapper -> source ~/.bashrc -> update_repo_path
-> set REPO_TOP / ROOT_FOLDER -> exec tasks.py
-> Python loads project file and executes the selected tool
```

Important variables:

- `REPO_TOP`
- `ROOT_FOLDER`
- `HDLFORGE_ORIG_DIR`

### Design boundary

- Fabrinetes documents the reusable HDLForge API and internals
- consuming repos document how they use HDLForge for their own builds, tests, and shortcuts

---

## 8. Migration Notes

### Legacy command style

Older docs used positional built-in tools:

```bash
hdlforge Verilator --step build --SimTargetName <target>
hdlforge vivado --step syn --run-flow default
```

### Current command style

Use `--tool` for built-in tools:

```bash
hdlforge --tool Verilator --step build --SimTargetName <target>
hdlforge --tool vivado --syn synth_1
```

Shortcut mode remains positional:

```bash
hdlforge trigger_test sim all
```

Legacy schema names to replace:

| Legacy | Current |
|--------|---------|
| `verilator_settings` | `verilator.config` |
| `vivado_settings` | `vivado.config` + `vivado.external_config` |
| `sources.files` for Verilator | `verilator.config.sources` |
| Vivado `--step ... --run-flow ...` | direct flags like `--syn synth_1` |

---

## 9. Ownership Boundary

Use this rule when deciding where documentation belongs:

- generic HDLForge API, schema, CLI, and internal behavior: `Fabrinetes`
- repo-wide workflow around HDLForge: `fpga`
- project-specific HDLForge usage for `phy10gbaser`: `fpga/fpga_projects/phy10gbaser`

Examples of **project-specific** content that should not live here:

- which `LLM_orch` shortcuts a project prefers
- how a project shards integration sims
- which run names or boards a project uses operationally
- project-specific release, deployment, or test policy

## Document History

Updated as the single HDLForge API source of truth in Fabrinetes.
