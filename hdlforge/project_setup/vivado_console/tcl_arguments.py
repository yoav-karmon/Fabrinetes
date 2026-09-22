"""Quote a single Tcl argument without evaluating user input."""

def tcl_word(value: object) -> str:
    """Encode one Tcl argument without substitution or brace balancing hazards."""
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("[", "\\[").replace("\n", "\\n").replace("\r", "\\r") + '"'
