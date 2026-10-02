# HDLForge project files

The [HDLForge reference](hdlforge.md) is the authoritative source for project
selection, working paths, environment setup, command syntax and JSON maintenance.

A `<name>.hdlforge.json` file owns paths relative to its containing directory.
Use `--project FILE` to select it explicitly. Commands belong under
`LLM_orch` with sibling `#name` descriptions and are invoked through
`hdlforge aliases.<path>`.

Initialize missing fields before validating a tool's section:

```bash
hdlforge sim-verilator.update-json --project chip.hdlforge.json --dry-run
hdlforge sim-verilator.update-json --project chip.hdlforge.json
hdlforge sim-verilator.lint-json --project chip.hdlforge.json
hdlforge vivado.build.update-json --project chip.hdlforge.json
hdlforge vivado.build.lint-json --project chip.hdlforge.json
```

The update preserves existing values and adds empty fields where appropriate.
Fill those fields with the actual inputs before running a build.
Non-project Vivado definitions and maintained Tcl examples are in
[`vivado_build_example_README.md`](../hdlforge/project_setup/vivado_build_example_README.md).
