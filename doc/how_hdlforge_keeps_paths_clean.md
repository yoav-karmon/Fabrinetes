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

  Its launcher resolves its installation from the executable path and calls
  hdlforge_environment.bash. It does not source ~/.bashrc or require FABRINETES
  to be set before launch. A full executable path works from a fresh shell.

  The bootstrap restores the base paths, loads /etc/profile.d/init_env.sh when
  available and the configured VIVADO_SETTINGS script, and adds its own bin
  directory. It then snapshots the tool paths before applying init_repo_env.sh.
  Nested calls therefore retain HDLForge and vendor tools even when inherited
  INIT_PATH was captured before those tools were configured.
