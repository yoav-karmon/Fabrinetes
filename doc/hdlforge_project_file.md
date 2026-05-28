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
      "sim_targets": [
        {
          "name": "basic_test",
          "top_module": "top",
          "python_file": "tests/test_top.py",
          "test_name": "test_basic",
          "build_args": ["--trace"],
          "PYTHONPATH": ["tests"]
        }
      ]
    }
  }

Run Verilator:
  hdlforge --tool Verilator --step build --SimTargetName basic_test
  hdlforge --tool Verilator --step sim --SimTargetName basic_test

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

  "LLM_orch": {
    "testing": {
      "sim": {
        "basic": "hdlforge --tool Verilator --step sim --SimTargetName basic_test"
      }
    }
  }

Run LLM_orch shortcut:
  hdlforge --eval_json testing.sim.basic

Append flags to shortcut:
  hdlforge --eval_json testing.sim.basic --eval_json_append '<extra flags>'

Set env vars in a shortcut:

  "name": "ENV_VAR=value hdlforge --eval_json <shortcut.path>"

  ENV_VAR=value is set only for that command.

Inline path inject, then reuse:

  "LLM_orch": {
    "testing": {
      "base": "hdlforge --tool <tool> <tool args>",
      "with_python": "add_to_pythonpath <python path>; hdlforge --eval_json testing.base",
      "with_tool": "add_to_path <tool path>; hdlforge --eval_json testing.base"
    }
  }

  add_to_pythonpath and add_to_path come from bashrc-root/bashrc-func.
  both check for duplicates before adding.
  relative paths are relative to REPO_TOP.
  the nested hdlforge call inherits the updated environment.

Recursive shortcut calls:

  "LLM_orch": {
    "testing": {
      "sim": {
        "basic": "hdlforge --tool Verilator --step sim --SimTargetName basic_test",
        "basic_with_flags": "hdlforge --eval_json testing.sim.basic --eval_json_append '<extra flags>'"
      }
    }
  }

  testing.sim.basic_with_flags calls testing.sim.basic.
  --eval_json_append injects extra command-line flags into the inner shortcut.

Useful checks:
  jq '.LLM_orch | keys' <project>.hdlforge.json
  hdlforge --tool Verilator --help
  hdlforge --tool vivado --help
