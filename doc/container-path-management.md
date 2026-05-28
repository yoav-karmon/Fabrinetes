Container path management

Container baseline:
  bashrc-root captures:
    INIT_PATH
    INIT_PYTHONPATH

Repo switch:
  update_repo_path
    resets PATH to INIT_PATH
    resets PYTHONPATH to INIT_PYTHONPATH
    finds current git repo
    sets REPO_TOP
    sources <REPO_TOP>/init_repo_env.sh if it exists

Repo init file:
  <REPO_TOP>/init_repo_env.sh

Use:
  add_to_path "<repo tool path>"
  add_to_pythonpath "<repo python path>"

Rules:
  relative paths are relative to REPO_TOP
  add_to_path skips duplicates
  add_to_pythonpath skips duplicates
  update_repo_path removes duplicate PATH entries
  update_repo_path removes duplicate PYTHONPATH entries

Manual refresh:
  cd <repo>
  update_repo_path

HDLForge:
  hdlforge sources ~/.bashrc
  hdlforge runs update_repo_path
  hdlforge captures PATH, PYTHONPATH, REPO_TOP
