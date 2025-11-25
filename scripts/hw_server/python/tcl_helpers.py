"""TCL Command Helper Functions"""

import sys
import os

# Handle both direct execution and module import
if __name__ == "__main__" or not __package__:
    # Running as script directly, use absolute imports
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from connect_and_read_dna import VivadoTCLConsole
else:
    # Running as module, use relative imports
    from .connect_and_read_dna import VivadoTCLConsole


def send_tcl_command(console: VivadoTCLConsole, command: str, timeout: float = 10.0) -> str:
    """Send a TCL command and return output."""
    return console.send_command(command, timeout=timeout)


