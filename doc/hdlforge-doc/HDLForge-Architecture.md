# HDLForge Architecture

> **📘 Main Documentation:** [HDLForge.md](HDLForge.md)

This document explains HDLForge's internal architecture for developers extending or debugging the system.

---

## 1. Design Philosophy

**Two-Stage Execution Model:** Separates environment management from build logic.

**Why?**
- **Bash:** Handles OS-level concerns (environment, directories)
- **Python:** Handles build logic (configuration, tool orchestration)
- **Clean separation:** Easy extension and debugging

---

## 2. High-Level Architecture

```
User Command: hdlforge <tool> [options]
    ↓
┌─────────────────────────────────────┐
│ Bash Wrapper (hdlforge)             │
│  • Parse arguments                  │
│  • Discover project file            │
│  • cd to project directory          │
│  • Call update_repo_path (env)      │
│  • exec python3 tasks.py            │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ Python Core (tasks.py)              │
│  • ProjectLoader (config)           │
│  • Command routing                  │
│  • Tool execution                   │
└──────────────┬──────────────────────┘
               ↓
        Tool Output
```

### File Structure

```
hdlforge/project_setup/
├── hdlforge            # Bash wrapper
├── tasks.py            # Python core
├── project_loader.py   # Config loader
├── json_file_handler.py # Centralized JSON read/write with merging
├── vivado_property.py  # Vivado set_property command handler
├── update_sources_from_xpr.py # Extract files/properties from XPR
├── project_detector.py # File detection
└── logs/              # Execution logs
```

---

## 3. Bash Wrapper

**Location:** `hdlforge/project_setup/hdlforge`

### Key Responsibilities

1. **Argument Parsing** - Extract `--project` flag
2. **Project Discovery** - Auto-detect or explicit path
3. **Directory Navigation** - `cd` to project directory
4. **Environment Setup** - Call `update_repo_path`
5. **Logging** - Capture output to log files
6. **Python Execution** - `exec python3 tasks.py "$@"`

### Execution Flow

```bash
# 1. Parse arguments
PROJECT_FILE="..."  # from --project flag

# 2. Resolve directory
PROJECT_DIR="$(dirname "$PROJECT_FILE_PATH")"

# 3. Navigate
cd "$PROJECT_DIR"

# 4. Setup environment
source ~/.bashrc
update_repo_path  # Sets REPO_TOP, PATH, PYTHONPATH

# 5. Export for Python
export ROOT_FOLDER="$PROJECT_DIR"

# 6. Execute Python
cd "$TASKS_DIR"
exec python3 tasks.py "$@" | tee -a "$log_file"
```

### Environment Variables Set

| Variable | Purpose |
|----------|---------|
| `REPO_TOP` | Git repository root (auto-detected) |
| `ROOT_FOLDER` | Project file search directory |
| `PATH` | Updated with repository tools |
| `PYTHONPATH` | Updated with repository modules |

---

## 4. Python Core

**Location:** `hdlforge/project_setup/tasks.py`

### Architecture

```python
tasks.py
├─ capture_environment_variables()  # Re-capture bash env
├─ ArgumentParser (argparse)        # Parse CLI
├─ ProjectLoader                     # Load config
│   ├─ _get_project_file_path()     # Auto-detect/explicit
│   ├─ _load_project_file()         # Parse JSON/TOML
│   └─ _resolve_working_path()      # $REPO_TOP expansion
├─ Tool Functions
│   ├─ Verilator()                  # cocotb.runner integration
│   └─ vivado()                     # TCL generation
└─ Utility Functions
```

### Command Routing

```python
args = parser.parse_args()

if args.command == 'Verilator':
    Verilator(c, args.project, args.step, args.clean, 
              args.SimTargetName, args.flags, args.extra_env)
elif args.command == 'vivado':
    vivado(c, args.project, args.step, args.run_flow, args.clean)
```

### Verilator Function

```python
def Verilator(c, project, step, clean, SimTargetName, flags, extra_env):
    project_loader = ProjectLoader(project)
    SimTarget = project_loader.get_sim_target(SimTargetName)
    sources = project_loader.get_verilator_sources()
    
    runner = get_runner("verilator")
    if 'build' in step: runner.build(verilog_sources=sources, ...)
    if 'sim' in step: runner.test(test_module=..., ...)
```

---

## 5. Project Loader

**Location:** `hdlforge/project_setup/project_loader.py`

**JSON File Handling:** `hdlforge/project_setup/json_file_handler.py`

### Purpose

Single source of truth for project configuration.

### Key Methods

```python
class ProjectLoader:
    def __init__(self, project_file: Optional[str] = None):
        """Load and parse project configuration"""
        self.project_file_path = self._get_project_file_path(project_file)
        self._project_data = self._load_project_file()
        self._working_path = self._resolve_working_path()
    
    @property
    def working_path(self) -> Path:
        """Get resolved project directory"""
    
    @property
    def verilator_settings(self) -> dict:
        """Get verilator_settings section"""
    
    @property
    def vivado_settings(self) -> dict:
        """Get vivado_settings section"""
    
    def get_sim_target(self, name: str) -> Optional[dict]:
        """Find simulation target by name"""
    
    def get_verilator_sources(self) -> List[dict]:
        """Get files marked with verilator: true"""
    
    def get_vivado_sources(self) -> List[dict]:
        """Get files marked with vivado: true"""
```

### Project File Discovery

**Auto-Detection:**
1. Use `ROOT_FOLDER` from environment (set by bash wrapper)
2. Search for `*.hdlforge.json` (preferred) or `*.hdlforge.toml`
3. Require exactly one file

**Explicit:**
- Use path from `--project` flag
- Resolve to absolute path

### Path Resolution

```python
def _resolve_working_path(self) -> Path:
    """Expand $REPO_TOP and resolve to absolute path"""
    project_path = self._project_data['settings']['project_path']
    expanded = os.path.expandvars(project_path)  # $REPO_TOP → /path/to/repo
    return Path(expanded).resolve()
```

---

## 6. Environment Management

### The `update_repo_path` Function

**Location:** Typically in `~/.bashrc` or repository's `bashrc-func`

**Purpose:** Detect Git repository and configure environment

```bash
update_repo_path() {
    # 1. Detect Git root
    repo_root=$(git rev-parse --show-toplevel 2>/dev/null)
    
    # 2. Set REPO_TOP
    export REPO_TOP="$repo_root"
    
    # 3. Source repo environment
    [[ -f "$REPO_TOP/init_repo_env.sh" ]] && source "$REPO_TOP/init_repo_env.sh"
    
    # 4. Update PATH
    export PATH="$REPO_TOP/bin:$REPO_TOP/scripts:$PATH"
    
    # 5. Update PYTHONPATH
    export PYTHONPATH="$REPO_TOP/python:$REPO_TOP/lib/python:$PYTHONPATH"
    
    # 6. Remove duplicates
    PATH=$(remove_duplicates "$PATH")
    PYTHONPATH=$(remove_duplicates "$PYTHONPATH")
}
```

### Environment Variable Flow

```
Initial Shell
    ↓
Bash: source ~/.bashrc
    ↓
Bash: update_repo_path
    ↓ (sets REPO_TOP, PATH, PYTHONPATH)
Bash: export ROOT_FOLDER
    ↓
Python: capture_environment_variables()
    ↓ (re-runs update_repo_path in subprocess)
Python: os.environ has all variables
```

---

## 7. Directory Navigation

### Navigation Flow

```
User's CWD
    ↓
[BASH] Parse --project → Resolve PROJECT_DIR
    ↓
[BASH] cd PROJECT_DIR
    ↓
[BASH] update_repo_path (uses PROJECT_DIR as context)
    ↓
[BASH] export ROOT_FOLDER=PROJECT_DIR
    ↓
[BASH] cd TASKS_DIR
    ↓
[BASH] exec python3 tasks.py
    ↓
[PYTHON] ProjectLoader uses ROOT_FOLDER
    ↓
[PYTHON] Resolves working_path from config
    ↓
[PYTHON] All operations relative to working_path
```

### Directory Reference

| Directory | Variable | Purpose |
|-----------|----------|---------|
| User's initial CWD | - | Where user ran command |
| Project directory | `PROJECT_DIR` | Project file location |
| Tasks directory | `TASKS_DIR` | Python script location, logs |
| Working directory | `working_path` | Source resolution, build outputs |
| Repository root | `REPO_TOP` | Path expansion in JSON |

---

## 8. Complete Sequence Example

```
hdlforge Verilator --step build --SimTargetName my_test
    ↓
BASH: Parse args → cd PROJECT_DIR → update_repo_path (sets REPO_TOP) 
      → export ROOT_FOLDER → exec python3 tasks.py
    ↓
PYTHON: capture_environment_variables() → parse_args() 
      → ProjectLoader (auto-detect JSON, resolve paths)
      → Verilator() (get target, collect sources, cocotb.runner.build)
    ↓
SUBPROCESS: Verilator compiles → Output: _verilator/my_test/
```

---

## 9. Extension Points

### Adding New Tools

1. Add argparse subcommand in `tasks.py`
2. Create tool function: `def mytool(c, project, ...)`
3. Add routing: `if args.command == 'mytool': mytool(...)`
4. Add JSON schema: `{"mytool_settings": {...}}`

### Adding ProjectLoader Features

```python
@property
def mytool_settings(self) -> dict:
    return self._project_data.get('mytool_settings', {})
```

### JSONFileHandler - Centralized JSON Management

**Location:** `hdlforge/project_setup/json_file_handler.py`

**Purpose:** Centralized handler for all JSON file read/write operations with automatic optimization.

**Key Features:**
- **Automatic merging:** Files with identical `hdlforge_properties` and `vivado_properties` are merged
- **Compact formatting:** Properties formatted as single-line JSON
- **Centralized operations:** All JSON operations go through this handler

**Usage:**
```python
from json_file_handler import JSONFileHandler

# Read JSON file
data = JSONFileHandler.read_json_file(Path('project.hdlforge.json'))

# Write JSON file (with automatic merging and formatting)
JSONFileHandler.write_json_file(Path('project.hdlforge.json'), data, merge_records=True)
```

**Integration:**
- `ProjectLoader._load_project_data()` uses `JSONFileHandler.read_json_file()`
- `ProjectLoader.save_project_data()` uses `JSONFileHandler.write_json_file()`
- All JSON operations are centralized through this handler

---

## 10. Debugging

### Enable Verbose Output

**Bash:**
```bash
# Edit hdlforge script
set -x  # Before exec
```

**Python:**
```python
# Add to tasks.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Inspect Environment

```bash
# After hdlforge runs
echo $REPO_TOP
echo $ROOT_FOLDER
env | grep -E "(REPO|ROOT|PROJECT)"
```

### Check Logs

```bash
# HDLForge logs
ls -lt hdlforge/project_setup/logs/
tail -f hdlforge/project_setup/logs/hdlforge_*.log

# Tool logs
cat <project>/_verilator/<target>/*.log
cat <project>/_vivado/<project>/vivado.log
```

### Common Issues

**REPO_TOP not set** → Check `update_repo_path` exists in `~/.bashrc`
**Project file not found** → Use `--project` with explicit path
**Python import errors** → Check `PYTHONPATH` includes required modules

---

## 11. Performance

**Typical Overhead:**
- Bash wrapper: 50-100ms
- Python startup: 100-200ms
- ProjectLoader: 10-50ms
- **Total: ~200-350ms**

**Tool Execution Time:**
- Verilator: 1-60 seconds
- Vivado: 1-60 minutes

**Conclusion:** HDLForge overhead is negligible.

---

## 12. Additional Resources

- **Main Documentation:** [HDLForge.md](HDLForge.md)
- **Verilator Guide:** [HDLForge-Verilator.md](HDLForge-Verilator.md)
- **Vivado Guide:** [HDLForge-Vivado.md](HDLForge-Vivado.md)
- **Verilator Examples:** [HDLForge-Verilator-Examples.md](HDLForge-Verilator-Examples.md)
- **Vivado Examples:** [HDLForge-Vivado-Examples.md](HDLForge-Vivado-Examples.md)

---

## Document History

**Last Updated:** Commit `e8ac713cdcf020cde9acfcc3e58270fa519a5ddb` - Consolidate and reorganize HDLForge documentation into hdlforge-doc/ (2025-11-11)
