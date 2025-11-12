# HDLForge Documentation

This directory contains comprehensive documentation for the HDLForge build system.

## 📚 Documentation Structure

### Level 1: Overview & Quick Start
- **[HDLForge.md](HDLForge.md)** - Main documentation entry point
  - Quick start guide
  - Architecture overview
  - Basic usage
  - Links to detailed documentation

### Level 2: Tool-Specific Guides (~320-410 lines each)
- **[HDLForge-Verilator.md](HDLForge-Verilator.md)** - Verilator/Cocotb simulation
  - Configuration structure
  - Essential commands
  - Common errors & solutions
  - Best practices

- **[HDLForge-Vivado.md](HDLForge-Vivado.md)** - Vivado FPGA implementation
  - Configuration structure
  - Essential commands
  - Run flows
  - Common errors & solutions

- **[HDLForge-Architecture.md](HDLForge-Architecture.md)** - Internal architecture
  - Design philosophy
  - Bash/Python execution model
  - ProjectLoader details
  - Extension points

### Level 3: Detailed Examples (~370-380 lines each)
- **[HDLForge-Verilator-Examples.md](HDLForge-Verilator-Examples.md)** - Complete working examples
  - Simple counter test
  - Advanced FIFO test with monitors
  - Full code samples

- **[HDLForge-Vivado-Examples.md](HDLForge-Vivado-Examples.md)** - Complete working examples
  - LED blinker project
  - Multi-flow design
  - Constraint examples

### Migration & Supplemental
- **[HDLForge_v2_Migration_Guide.md](HDLForge_v2_Migration_Guide.md)** - Migration guide for v2.0

## 🎯 Quick Navigation

**New to HDLForge?** → Start with [HDLForge.md](HDLForge.md)

**Using Verilator?** → [HDLForge-Verilator.md](HDLForge-Verilator.md) + [Examples](HDLForge-Verilator-Examples.md)

**Using Vivado?** → [HDLForge-Vivado.md](HDLForge-Vivado.md) + [Examples](HDLForge-Vivado-Examples.md)

**Extending HDLForge?** → [HDLForge-Architecture.md](HDLForge-Architecture.md)

## 📊 Documentation Philosophy

This documentation follows a **"big picture → details"** structure:

1. **Smaller line counts** = Higher-level overviews
2. **Larger line counts** = More detailed implementations

This ensures:
- Fast loading for LLM context windows
- Easy navigation from overview to detail
- Single source of truth for each concept
- Progressive disclosure of complexity

## 📁 File Organization

```
hdlforge-doc/
├── README.md                          (this file)
├── HDLForge.md                        (317 lines - overview)
├── HDLForge-Verilator.md             (323 lines - guide)
├── HDLForge-Vivado.md                (367 lines - guide)
├── HDLForge-Architecture.md          (406 lines - internals)
├── HDLForge-Verilator-Examples.md    (383 lines - examples)
├── HDLForge-Vivado-Examples.md       (373 lines - examples)
├── HDLForge_v2_Migration_Guide.md    (migration)
└── CONSOLIDATION_SUMMARY.md          (consolidation notes)
```

## 🔗 Related Documentation

- **[Fabrinetes Main README](../../README.md)** - Project overview
- **[Documentation Index](../DOCUMENTATION_INDEX.md)** - All Fabrinetes docs

---

*Documentation optimized for efficient LLM context windows and progressive learning.*

---

## Document History

**Last Updated:** Commit `e8ac713cdcf020cde9acfcc3e58270fa519a5ddb` - Consolidate and reorganize HDLForge documentation into hdlforge-doc/ (2025-11-11)

