# Vivado Project File Extractor

Extract file lists and properties from Vivado project files using Python XML parsing.

## Overview

This module provides a fast Python-based solution to extract files and their properties directly from Vivado `.xpr` project files (XML format). This approach is **much faster** than TCL parsing or Vivado batch mode (~600x faster).

## Scripts

### `extract_from_xpr.py`

Extracts file list and properties from Vivado `.xpr` project files by parsing the XML directly.

**Usage:**
```bash
# JSON output (recommended)
python3 extract_from_xpr.py <project.xpr> --json

# Simple list output (one file per line)
python3 extract_from_xpr.py <project.xpr>

# Specify fileset (default: sources_1)
python3 extract_from_xpr.py <project.xpr> sources_1 --json
```

**Output Format (JSON):**
```json
{
  "files": [
    {
      "path": "/full/path/to/file.sv",
      "properties": {
        "Library": "xil_defaultlib",
        "UsedIn": ["synthesis", "implementation", "simulation"]
      }
    }
  ]
}
```

**Features:**
- ✅ Fast XML parsing (no Vivado required)
- ✅ Extracts all file properties from FileInfo elements
- ✅ Resolves Vivado path variables ($PPRDIR, $PSRCDIR, etc.)
- ✅ Supports multiple filesets
- ✅ JSON or simple text output

**Performance:**
- XML extraction: ~0.05 seconds
- Vivado batch mode: ~30 seconds
- **~600x faster**

## Example

```bash
cd ~/repo/fpga/fpga_projects/phy10gbaser
python3 ~/repo/Fabrinetes/scripts/tcl_parser/extract_from_xpr.py \
    _vivado/phy10gbaser/phy10gbaser.xpr --json
```

## Path Resolution

The script automatically resolves Vivado path variables:
- `$PPRDIR` = directory containing the `.xpr` file
- `$PSRCDIR` = sources directory (typically `_vivado/project_name/project_name.srcs`)

Paths are resolved to absolute paths for consistency.
