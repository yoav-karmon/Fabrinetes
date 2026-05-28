How HDLForge keeps paths clean

PATH between containers -> bashrc-root


PATH /PYTHONPATH between repos -> <REPO_TOP>/init_repo_env.sh

  <REPO_TOP>/init_repo_env.sh:
    add_to_path "<repo tool path>"
    add_to_pythonpath "<repo python path>"

  relative paths are relative to REPO_TOP.
  add_to_path checks for duplicates before adding.
  add_to_pythonpath checks for duplicates before adding.

Update path in a shell:
  update_repo_path

HDLForge:

  hdlforge auto-captures the correct environment from the launch directory (or --project file path).
