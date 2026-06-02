HDLForge project file

File name:
  <project>.hdlforge.json

Project root:
  the folder containing the HDLForge project file.

Paths:
  source paths are relative to the project root.
  test paths are relative to the project root.
  TCL paths are relative to the project root.

Verilator setup:

  "verilator": {
    "config": {
      "build_dir": "_verilator",
      "includes_paths": ["sources/include"],
      "sources": [
        "sources/rtl/top.sv"
      ],
      "sim_targets": {
        "basic_test": {
          "top_module": "top",
          "python_file": "tests/test_top.py",
          "test_name": "test_basic",
          "build_args": ["--trace"]
        }
      }
    }
  }

Run Verilator:
  hdlforge --tool Verilator --step build --SimTargetName basic_test
  hdlforge --tool Verilator --step sim --SimTargetName basic_test
  hdlforge --tool Verilator --step lint --SimTargetName basic_test
  hdlforge --tool Verilator --step lint --SimTargetName basic_test --lint-file sources/rtl/top.sv

Vivado setup:

  "vivado": {
    "config": {
      "build_dir": "_vivado",
      "project_name": "my_vivado_project"
    },
    "external_config": {
      "filename": "sources/XDC/project.tcl"
    }
  }

Run Vivado:
  hdlforge --tool vivado --generate_prj_with_external_tcl

LLM_orch setup:

  "verilator": {
    "config": {
      "sim_targets": {
        "basic_test": {
          "top_module": "top",
          "python_file": "tests/test_top.py",
          "env": {
            "pythonpath": ["tests"]
          }
        }
      }
    }
  },
  "LLM_orch": {
    "testing": {
      "sim": {
        "basic": "hdlforge --tool Verilator --step sim --SimTargetName basic_test --env-python verilator.config.sim_targets.basic_test.env.pythonpath"
      }
    }
  }

Run LLM_orch shortcut:
  hdlforge testing.sim.basic

Append flags to shortcut:
  hdlforge testing.sim.basic --append '<extra flags>'

Set env vars in a shortcut:

  "name": "ENV_VAR=value hdlforge <shortcut.path>"

  ENV_VAR=value is set only for that command.

Native env handoff, then reuse:

  "verilator": {
    "config": {
      "sim_targets": {
        "basic_test": {
          "top_module": "top",
          "python_file": "tests/test_top.py",
          "env": {
            "pythonpath": ["tests"]
          }
        }
      }
    }
  },
  "LLM_orch": {
    "testing": {
      "base": "hdlforge --tool <tool> <tool args>",
      "with_python": "hdlforge --env-python verilator.config.sim_targets.basic_test.env.pythonpath testing.base",
      "with_tool_path": "hdlforge --env-path '[\"tools\"]' testing.base",
      "with_env_vars": "hdlforge --env-var '[{\"FOO\":\"bar\"}]' testing.base"
    }
  }

  --env-python and --env-path are native HDLForge wrapper options.
  they accept JSON arrays of strings, validate JSON, verify each path exists,
  deduplicate paths, and carry the env state through nested hdlforge calls.
  relative paths are resolved from the HDLForge project folder before
  add_to_pythonpath/add_to_path. --env-var accepts a JSON array of
  single-key objects, validates env keys, stringifies values, and carries env
  vars through nested calls. pass project JSON leaves directly, or pass raw
  JSON arrays when a value is not stored in the project JSON.

Recursive shortcut calls:

  "LLM_orch": {
    "testing": {
      "sim": {
        "basic": "hdlforge --tool Verilator --step sim --SimTargetName basic_test",
        "basic_with_flags": "hdlforge testing.sim.basic --append '<extra flags>'"
      }
    }
  }

  testing.sim.basic_with_flags calls testing.sim.basic.
  --append injects extra command-line flags into the inner shortcut.

Useful checks:
  jq '.LLM_orch | keys' <project>.hdlforge.json
  hdlforge --tool Verilator --help
  hdlforge --tool vivado --help
