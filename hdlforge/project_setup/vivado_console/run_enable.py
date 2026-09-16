"""Persist HDLForge run availability in Vivado's native run DESCRIPTION property."""

import base64


def tcl_word(value: object) -> str:
    """Encode one Tcl argument without substitution or brace balancing hazards."""
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("[", "\\[").replace("\n", "\\n").replace("\r", "\\r") + '"'


ENABLED = "[HDLForge:enabled]"
DISABLED = "[HDLForge:disabled]"


def is_enabled(description: str, legacy_disabled: bool = False) -> bool:
    lines = description.splitlines()
    if DISABLED in lines:
        return False
    return ENABLED in lines or not legacy_disabled


def blocked(run: dict, runs: list) -> bool:
    """A disabled synthesis run disables its entire group, including direct child actions."""
    parent = next((item for item in runs if item["name"] == run.get("parent_run")), None)
    return not run.get("enabled", True) or (parent is not None and not parent.get("enabled", True))


def set_enabled(console, names: list[str], enabled: bool) -> None:
    """Edit only HDLForge marker lines; preserve each run's existing description."""
    script = "foreach name [list " + " ".join(tcl_word(name) for name in names) + "] {\n"
    script += r'''
        set run [get_runs $name]
        set lines {}
        foreach line [split [get_property DESCRIPTION $run] "\n"] {
            if {$line ni {{[HDLForge:enabled]} {[HDLForge:disabled]}}} {lappend lines $line}
        }
'''
    script += "lappend lines " + tcl_word(ENABLED if enabled else DISABLED) + "\n"
    script += 'set_property DESCRIPTION [join $lines "\\n"] $run\n}\n'
    with console.locked():
        console.request(script)


def export_markers(console, output) -> None:
    """Vivado omits run descriptions from write_project_tcl; retain marked ones explicitly."""
    text = console.request(r'''
        foreach run [get_runs] {
            set description [get_property DESCRIPTION $run]
            if {[regexp {\[HDLForge:(enabled|disabled)\]} $description]} {
                puts "[binary encode base64 -maxlen 0 $run]\t[binary encode base64 -maxlen 0 [encoding convertto utf-8 $description]]"
            }
        }
    ''')
    lines = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) == 2:
            name, description = [base64.b64decode(part).decode() for part in parts]
            lines.append(f"set_property DESCRIPTION {tcl_word(description)} [get_runs {tcl_word(name)}]")
    if lines:
        with output.open("a") as handle:
            handle.write("\n# Preserve HDLForge run enable/disable markers and original descriptions.\n" + "\n".join(lines) + "\n")
