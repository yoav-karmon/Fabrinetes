# Environment bootstrap owned by the HDLForge launcher.
hdlforge_prepare_environment() {
    local installation_dir="$HDLFORGE_INSTALL_DIR"
    local installation_root="$FABRINETES"

    source "$installation_root/.devcontainer/bashrc-func" || return 1

    # Drop previous repository additions, then restore configured container tools.
    export PATH="${INIT_PATH-${PATH}}"
    export PYTHONPATH="${INIT_PYTHONPATH-${PYTHONPATH:-}}"
    if [ -f /etc/profile.d/init_env.sh ]; then
        source /etc/profile.d/init_env.sh >/dev/null || {
            echo "error: HDLForge could not load /etc/profile.d/init_env.sh" >&2
            return 1
        }
    fi
    if [ -n "${VIVADO_SETTINGS:-}" ]; then
        if [ ! -r "$VIVADO_SETTINGS" ]; then
            echo "error: Vivado settings file is not readable: $VIVADO_SETTINGS" >&2
            return 1
        fi
        source "$VIVADO_SETTINGS" >/dev/null || {
            echo "error: HDLForge could not load Vivado settings: $VIVADO_SETTINGS" >&2
            return 1
        }
    fi

    # Machine configuration may name a different checkout; use the invoked one.
    export FABRINETES="$installation_root"
    export HDLFORGE="$installation_dir"
    add_to_path "$installation_dir"
    [ ! -d "$HOME/.local/bin" ] || add_to_path "$HOME/.local/bin"
    export INIT_PATH="$(remove_duplicates_from_path "$PATH")"
    export INIT_PYTHONPATH="$(remove_duplicates_from_path "$PYTHONPATH")"
    update_repo_path
}
